![App Screenshot](https://res.cloudinary.com/dxdalfpbk/image/upload/v1778331705/Github_Vincent_Banner.png)

# ИИ Таролог на Вашем Сервере

## Discord-бот с раскладами Таро, ежедневными предсказаниями и интерактивными командами для гадания.

| Характеристика | Технология / Описание |
| :--- | :--- |
| ⚙️ **Основа бота** | `discord.py` |
| 🎨 **Стилизация сообщений** | `discord.ui` |
| 🎛️ **Интерфейс** | Discord Message Components V2 |
| 🧠 **ИИ Агент** | [Google Gemma-3n-e4b-it](https://build.nvidia.com/google/gemma-3n-e4b-it/modelcard) |
| ⚡ **Асинхронные запросы** | `aiohttp` |
| 💾 **Работа с файлами** | Временные файлы обрабатываются через ОЗУ (RAM) |

# Команды Бота
```text
/tarot
    ├── day - Расклад на одну карту Таро с предсказанием на день.
    │
    ├── one - Расклад на одну карту Таро с возможностью задать вопрос Картам.
    │
    ├── three - Расклад на три карты Таро с возможностью задать вопрос Картам.
    │
    └── relationship - Расклад на шесть карт на тему Отношений, с возможностью задать вопрос Картам.

/ball
    └── Магический Шар - Задайте вопрос, на который можно ответить да или нет, и позвольте духам (или рандому) решить.

/docs tarot
    └── Краткая документация команд.
```


# Структура Проeкта
```text
root/
├──cogs/
│   ├── docs.py
│   └── tarot.py
│
├── main.py
├── comds.py
├── storage.py
│
├── .env
├── requirements.txt
├── .gitignore
└── README.md
```

# Зависимости
```text
 discord.py>=2.7.1
 python-dotenv>=1.2.2
 aiohttp>=3.13.5
 pydantic>=2.13.0
 pillow>=12.2.0
```
#

![App Screenshot](https://res.cloudinary.com/dxdalfpbk/image/upload/v1778343380/special_thanks.png)

### Сотрудничество: [Venturas](https://github.com/Venturas1)
### Вдохновение и ассеты: [Magerko](https://github.com/Magerko) & [читать оригинал](https://t.me/magerdev1/56?single)
                                                                                                    
