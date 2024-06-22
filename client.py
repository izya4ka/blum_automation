import asyncio
import json
import random
import time
from datetime import datetime

import aiohttp
import pyrogram
from pyrogram.errors import SessionPasswordNeeded, SessionExpired

from config import API_ID, API_HASH, GAME_CLAIM_MIN_MAX, GAME_MIN_WAIT


class Client:
    def __init__(self, name):
        self.headers = {'Authorization': '',
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, "
                                      "like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0", }
        self.name = name
        self.prefix = lambda: f"[ {self.name} ] [ {datetime.now().strftime('%H:%M:%S %d.%m.%Y')} ]"
        self.to_wait = 0

    async def sign_in_telegram(self):
        """
        Логинимся в Телеграм
        :return:
        """
        client = pyrogram.Client(self.name, API_ID, API_HASH)
        await client.connect()
        phone_number = input(f"{self.prefix()} [Telegram] Введите номер телефона в международном формате: ")
        phone_code = await client.send_code(phone_number)

        phone_code_hash = phone_code.phone_code_hash
        code = input(f"{self.prefix()} [Telegram] Введите код из SMS: ")
        try:
            await client.sign_in(phone_number, phone_code_hash, code)
        except SessionPasswordNeeded:
            password = input(f"{self.prefix()} [Telegram] Введите пароль: ")
            await client.check_password(password)
        return await client.export_session_string()

    async def refresh_token(self):
        """
        Перезапрашиваем Bearer-токен с сервером Blum
        """
        print(f"{self.prefix()} [Telegram] Получение нового токена...")
        headers = {
            'Content-Type': 'application/json',
        }

        try:
            with open('sessions.json', 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            with open('sessions.json', 'w') as f:
                data = {}
        except json.decoder.JSONDecodeError:
            data = {}

        try:
            tg_session = data[self.name]
        except KeyError:
            with open('sessions.json', 'w') as f:
                tg_session = await self.sign_in_telegram()
                data[self.name] = tg_session
                f.write(json.dumps(data))

        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                client = pyrogram.Client(self.name, session_string=tg_session)
            except SessionPasswordNeeded:
                password = input(f"{self.prefix()} [Telegram] Введите пароль: ")
                await client.check_password(password)
            except SessionExpired:
                print(f"{self.prefix()} [Telegram] Ваша сессия истекла, войдите ещё раз")
                new_session = await self.sign_in_telegram()
                client = pyrogram.Client(self.name, session_string=new_session)

            await client.start()
            web_view = await client.invoke(pyrogram.raw.functions.messages.RequestWebView(
                peer=await client.resolve_peer('BlumCryptoBot'),
                bot=await client.resolve_peer('BlumCryptoBot'),
                platform='android',
                from_bot_menu=False,
                url='https://telegram.blum.codes/'
            ))
            query = web_view.url[42:-71].replace("%3D", "=").replace("%26", "&").replace("%25", "%")
            await client.stop()
            data = {
                "query": query
            }

            res = await session.post("https://gateway.blum.codes/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP",
                                     json=data)
            self.headers['Authorization'] = 'Bearer ' + (await res.json())['token']['access']

    """
    {
    "availableBalance": "27949.96"      Баланс
    "playPasses": 29,                   Количество билетов
    "timestamp": 1718732419651,         Время запроса
    "farming": {
        "startTime": 1718730233783,     Начало добычи
        "endTime": 1718759033783,       Конец добычи
        "earningsRate": "0.002",        Скорость добычи
        "balance": "4.37"               
        }
    "message": "Invalid jwt token"      Будет только это, если токен неверный
    }
    """

    async def get_status(self, session: aiohttp.client.ClientSession):
        """
        Получаем статус нашего аккаунта (основные данные)
        :param session: сессия aiohttp.ClientSession
        :return:
        """
        req = await (await session.get("https://game-domain.blum.codes/api/v1/user/balance")).json()
        try:
            req['availableBalance']
        except KeyError:
            raise TokenException
        return req

    def print_status(self, status):
        """
        Выводим статус аккаунта
        :param status: словарь со статусом, который мы получили в функции get_status
        """
        print(f"{self.prefix()} Баланс: {status["availableBalance"]}")
        print(
            f"{self.prefix()} Время запроса: {datetime.fromtimestamp(status["timestamp"] / 1000).strftime('%H:%M:%S %d-%m-%Y')}")

    async def game_get(self, session: aiohttp.client.ClientSession):
        """
        Получаем уникальный идентификатор игры
        :param session: сессия aiohttp.ClientSession
        :return:
        """
        req = await session.post("https://game-domain.blum.codes/api/v1/game/play")
        return (await req.json())['gameId']

    async def game_claim(self, game_id: str, points: int, session: aiohttp.client.ClientSession):
        """
        Функция, которая обеспечивает получение награды
        :param game_id: уникальный идентификатор игры, получаемый из функции game_get
        :param points: количество монеток, которые выбраны из промежутка
        :param session: сессия aiohttp.ClientSession
        :return:
        """
        payload = {
            "gameId": game_id,
            "points": points
        }
        req = await session.post("https://game-domain.blum.codes/api/v1/game/claim", data=payload)
        return req.status

    async def game_play(self, session: aiohttp.client.ClientSession):
        """
        Играем в игру

        Что мы делаем:
            - Отправляем запрос на получение идентификатора самой игры
            - Ждём секунд 40, типа мы реально что-то там тыкаем
            - Выбираем какое-то число из промежутка GAME_CLAIM_MIN_MAX. Оно и будет нашей наградой
            - Отправляем запрос на получение награды, всё просто как деревенский туалет
        :param session: сессия aiohttp.ClientSession
        """
        print(f"{self.prefix()} [Игра] Отправлен запрос на игру...")
        game_id = await self.game_get(session)  # Получаем ID игры
        await asyncio.sleep(GAME_MIN_WAIT)  # Ждём окончания игры
        points = random.choice(GAME_CLAIM_MIN_MAX)  # Выбираем награду случайно ( в пределах диапазона :) )
        status_code = await self.game_claim(game_id, points, session)  # PROFIT!!!
        if status_code == 200:
            print(f"{self.prefix()} [Игра] Получено за игру {points} монеток!")
        else:
            raise GameException()

    async def farm_games(self, session: aiohttp.client.ClientSession):
        """
        Просто цикл, который фармит игры, пока билетики не кончатся
        :param session: сессия aiohttp.ClientSession
        """
        while True:
            try:
                status = await self.get_status(session)
                if status["playPasses"] != 0:
                    await self.game_play(session)
                else:
                    print(f"{self.prefix()} [Игра] Билетов нет!")
                    break
            except TokenException:
                print(f"{self.prefix()} Неверный токен!")
                break
            except GameException:
                print(f"{self.prefix()} [Игра] Проблема с игрой, продолжаем...")

    async def start_farming(self, session: aiohttp.client.ClientSession):
        """
        Отправляем запрос на старт того самого восьмичасового фарминга
        :param session: сессия aiohttp.ClientSession
        """
        res = await session.post("https://game-domain.blum.codes/api/v1/farming/start")
        self.to_wait = (await res.json())['endTime'] / 1000 - time.time() + 10
        print(f"{self.prefix()} [Фарминг] Фарминг будет окончен через", int(self.to_wait),
              'секунд.')

    async def claim_farming(self, session: aiohttp.client.ClientSession):
        """
        Забираем награду с фарминга
        :param session: сессия aiohttp.ClientSession
        """
        res = await session.post("https://game-domain.blum.codes/api/v1/farming/claim")
        if res.ok:
            print(f"{self.prefix()} [Фарминг] Фарминг завершён. Текущий баланс:",
                  (await res.json())['availableBalance'])
        else:
            print(f"{self.prefix()} [Фарминг] Произошла ошибка")
        self.to_wait = 0

    async def process_farming(self, session: aiohttp.client.ClientSession):
        """
        Обрабатываем весь фарминг, тоесть начало и конец
        :param session: сессия aiohttp.ClientSession
        """
        status = await self.get_status(session)
        try:
            farming_status = status["farming"]
            if (farming_status['endTime'] / 1000) <= time.time():
                await self.claim_farming(session)
                await self.start_farming(session)
            else:
                self.to_wait = farming_status['endTime'] / 1000 - time.time()
                print(f"{self.prefix()} [Фарминг] Фарминг будет окончен через", int(self.to_wait),
                      'секунд.')
        except KeyError:
            await self.start_farming(session)

    async def friends_claim(self, session: aiohttp.client.ClientSession):
        """
        Забираем бонусы с друзей
        :param session: сессия aiohttp.ClientSession
        """
        friend_bal = await session.get("https://gateway.blum.codes/v1/friends/balance")
        can_claim = (await friend_bal.json())['canClaim']

        status = await self.get_status(session)
        if can_claim:
            result = await (await session.post("https://gateway.blum.codes/v1/friends/claim")).json()
            print(f"{self.prefix()} [Друзья] Собрано {result['claimBalance']}. Текущий баланс:",
                  status['availableBalance'])
        else:
            print(f"{self.prefix()} [Друзья] Пока невозможно собрать деньги.")

    async def everyday_claim(self, session: aiohttp.client.ClientSession):
        """
        Забираем ежедневные бонусы
        :param session: сессия aiohttp.ClientSession
        """
        resp = await session.post("https://game-domain.blum.codes/api/v1/daily-reward?offset=-180")
        if await resp.text() == 'OK':
            print(f"{self.prefix()} [Ежедневная награда] Собрана.")
        else:
            print(f"{self.prefix()} [Ежедневная награда] Ещё не доступна.")

    async def start(self):
        """
        Все функции в этом объекте просто засовываются в бесконечный ицкл
        и выполняются когда заканчивается фарминг (ну или когда вы запускаете скрипт)
        """
        while True:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                try:
                    status = await self.get_status(session)
                    self.print_status(status)

                    await self.everyday_claim(session)  # Забираем ежедневку
                    await self.process_farming(session)  # Обрабатываем восьмичасовой фарминг
                    await self.friends_claim(session)  # Обрабатываем друзей
                    await self.farm_games(session)  # Фармим билетики

                except TokenException:
                    await self.refresh_token()  # Перезапрашиваем токен, если что он обновится
            await asyncio.sleep(self.to_wait)  # Ждём окончания фарминга


class TokenException(Exception):
    pass


class GameException(Exception):
    pass


class InvalidSession(Exception):
    pass
