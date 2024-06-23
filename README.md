# Автоматизация крипоигры Blum
Познакомился с этой игрой только недавно. Прикольная концепция с игрой, друзьями, ежедневками и т.д. Но самое бесячее - конечно же игра, в особенности когда из-за ежедневных наград собираешь сотню билетиков
тыкать на монетки становится невыносимо.
Вообщем этот бот забираем ежедневку, использует все билетики, тыкает фарминг, собирает награду с друзей
## Установка
### Подготовка
Нужен `Python 3.12` ну и всё
### Процесс
1. Открываем терминал в папке репозитория и прописываем
```
pip install -r requirements.txt
```
2. В файле `config.py` в `NICKNAMES` прописываем наши имена аккаунтов, будет что-то наподобии
```
NICKNAMES = ['Я', 'Любимая', 'Олег']
```
3. (Опционально) Также имеются некоторые конфигурационные настройки
```
GAME_CLAIM_MIN_MAX = range(X, Y)
```
- выбор награды в диапазоне от X до Y (не советую ставить выше 275)
```
GAME_MIN_WAIT = X
```
- ожидание между играми одного аккаунта (не советую ставить меньше 30)
4. Запускаем скрипт командой
```
python main.py
```
5. Следуем инструкциям
