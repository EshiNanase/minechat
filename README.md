# minechat-w-gui

Игра с интерфейсом a.k.a убийца телеграма. Вы играете за бабушку Зину - обычную бабушку, играющую в майнкрафт. Однажды Зина получила хост и порт одного приватного Darknet чата по майнкрафту. Узнайте тайны этого чата и его постояльцев - Евы и Влада. Что скрывают эти гуманоидные существа и почему они боятся Зину? Ответы на эти вопросы вы найдете в игре Minechat!
![Screenshot](https://github.com/EshiNanase/minechat-w-gui/blob/main/screen.png)

## Установка игры

### Скопируйте репозиторий
```sh
https://github.com/EshiNanase/minechat-w-gui.git
```

### Установите python 3.9 и необходимые библиотеки
```sh
pip install -r requirements.txt
```

## Запуск игры

### Флажки

```sh
--host HOST - указать хост (default=minechat.dvmn.org)
--writing_port PORT - указать порт записи на сервер (default=5000)
--listening_port PORT - указать порт чтения чата с сервера (default=5000)
--debug - нужно ли логирование информации с сервера в терминал (необязательно)
```

### Запуск
```sh
python main.py + флажки
```
