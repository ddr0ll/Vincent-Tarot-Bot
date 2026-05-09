import os
from pydantic import BaseModel
from typing import List, Optional
import random
from storage import FULL_DECK

from PIL import Image

import asyncio
import aiohttp

from io import BytesIO

invoke_url = os.getenv("INVOKE_URL")
AUTHORIZATION = os.getenv("AUTHORIZATION")

stream = False
headers = {
  "Authorization": AUTHORIZATION,
  "Accept": "text/event-stream" if stream else "application/json"
}

class Card(BaseModel):
    id: int
    name: str
    name_ru: str
    meaning: str
    keywords: List[str]
    position: Optional[str] = None
    reversed: bool = False
    image: Optional[str] = None

async def llm_answer_day(spread_type: str, cards_text: str):
    prompt = f'''
                Выступи в роли опытного таролога.
                На основе одной выпавшей карты Таро сделай точный и конкретный прогноз на день для человека.

                Не используй вступлений, пояснений о себе или заключений — предоставляй только сам прогноз.

                Структурируй ответ следующим образом:

                Начни с общего прогноза дня.
                Кратко раскрой, как энергия карты проявится в событиях, эмоциях и возможных ситуациях.
                Заверши конкретным практическим советом на день в размере строго одного законченного предложения, совет должен быть написан с абзаца, это важно.

                Тип расклада: "{spread_type}"
                Выпавшая карта:
                {cards_text}

                Требования к ответу:

                Максимальная длина ответа: 500 символов.
                Ответ должен быть полностью завершённым и логически цельным в пределах 1000 символов.
                Прогноз должен быть чётким, конкретным и описывать, как именно пройдёт день.
                Не задавай вопросов и не упоминай пользователя напрямую.
                Если информация не помещается, приоритизируй краткость и завершённость мысли, не обрывай текст.
                Не превышай лимит ни при каких условиях.

                Твой прогноз:
                '''

    payload = {
        "model": "google/gemma-3n-e4b-it",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "temperature": 0.20,
        "top_p": 0.70,
        "frequency_penalty": 0.00,
        "presence_penalty": 0.00,
        "stream": stream
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(invoke_url, headers=headers, json=payload) as res:
                response = await res.json()
                return response["choices"][0]["message"]["content"]

    except Exception as e:
        return f"Error occurred: {e}"


async def llm_answer(question: str, spread_type: str, cards_text: str):
    prompt = f'''
                Выступи в роли опытного таролога. Дай глубокое, но понятное толкование расклада Таро, синтезируя значения карт в единый связный рассказ.
                Важное требование к оформлению: обязательно разделяй текст на несколько логических абзацев. Текст не должен идти сплошным полотном.
                Не используй вступлений, приветствий, пояснений о себе или шаблонных концовок — предоставляй только само толкование.
                Структурируй ответ строго следующим образом:
                Первый абзац: Общий вывод и основная энергия расклада.
                Второй (и при необходимости третий) абзац: Краткое раскрытие значения каждой карты в контексте её позиции, вплетенное в общую логику ответа.
                Финальный абзац: Обязательный практический совет, выделенный в отдельный абзац в самом конце текста.
                Вопрос пользователя: "{question}"
                Тип расклада: "{spread_type}"
                Выпавшие карты:
                {cards_text}
                Требования к ответу:
                Максимальная длина всего текста: 1000 символов.
                Ответ должен быть полностью завершённым и осмысленно законченным в пределах лимита.
                Если информация не помещается, приоритизируй краткость и емкость формулировок, не обрывай текст.
                Не превышай лимит в 1000 символов ни при каких условиях.
                Твое толкование:
                 '''
    payload = {
        "model": "google/gemma-3n-e4b-it",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "temperature": 0.20,
        "top_p": 0.70,
        "frequency_penalty": 0.00,
        "presence_penalty": 0.00,
        "stream": stream
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(invoke_url, headers=headers, json=payload) as res:
                response = await res.json()
                return response["choices"][0]["message"]["content"]

    except Exception as e:
        return f"Error occurred: {e}"


# ----------------------------------------------------------------------------------------------------------------
# TAROT FUNCTIONS:
def get_spread_positions(spread_type: str) -> List[str]:
    if spread_type == "one":
        return ["Ситуация"]
    elif spread_type == "three":
        return ["Прошлое", "Настоящее", "Будущее"]
    elif spread_type == "relationship":
        return ["Вы", "Партнер", "Связь", "Сильные стороны", "Слабые стороны", "Совет"]
    elif spread_type == "day":
        return ["Выпавшая карта"]
    return []


def draw_cards(spread_type: str) -> List[Card]:
    positions = get_spread_positions(spread_type)
    num_cards = len(positions)

    shuffled_deck = FULL_DECK.copy()
    random.shuffle(shuffled_deck)

    drawn_cards = []
    for i in range(num_cards):
        card_data = shuffled_deck[i]
        card = Card(
            id=card_data["id"],
            name=card_data["name"],
            name_ru=card_data["name_ru"],
            meaning=card_data["meaning"],
            keywords=card_data.get("keywords", []),
            position=positions[i],
            reversed=random.random() < 0.3,
            image=card_data.get("image")
        )
        drawn_cards.append(card)

    return drawn_cards


def crtimg(cards):
    images = []
    for card in cards:
        images.append(f'https://res.cloudinary.com/dxdalfpbk/image/upload/v1776122504/{card.image}')
    return images


def description(cards):
    cards_description = []
    for card in cards:
        reversed_text = " (перевернутая)" if card.reversed else ""
        cards_description.append(
            f"- Позиция '{card.position}': {card.name_ru}{reversed_text}. Ключевое значение: {card.meaning}.")
    cards_text = "\n".join(cards_description)
    return cards_text


def splt(response):
    lst = response.split('\n')

    for i in range(len(lst) - 1, -1, -1):
        if any(c.isalpha() for c in lst[i]):
            lst[i] = ' >>> ' + lst[i]

            info = ''.join(lst[:-1]).strip()
            info = info.split('. ')
            return lst, info
        else:
            lst.pop(i)
    return ["Empty"], ["Empty"]


async def rolling(images):
    render = []

    async with aiohttp.ClientSession() as session:
        tasks = [download(session, url) for url in images]
        bytess = await asyncio.gather(*tasks)
        for response in bytess:
            if response:
                result = Image.open(BytesIO(response))
                render.append(result)

    if not render:
        return None

    width = sum(image.width for image in render)
    height = max(image.height for image in render)

    res = Image.new('RGB', (width, height))

    x = 0
    for img in render:
        res.paste(img, (x, 0))
        x += img.width

    return res

async def download(session, url):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.read()
    except Exception as e:
        return f'Error occurred during download: {e}'
    return None