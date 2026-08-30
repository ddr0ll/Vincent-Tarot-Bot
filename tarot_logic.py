import os
from dotenv import load_dotenv
import asyncio
import random
from io import BytesIO

import aiohttp
from PIL import Image
from pydantic import BaseModel

from tarot_deck import FULL_DECK

load_dotenv()
invoke_url = os.getenv("INVOKE_URL")
AUTHORIZATION = os.getenv('AUTHORIZATION')
reasoning_lvl = str(os.getenv('REASONING_LVL'))
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
    keywords: list[str]
    position: str | None = None
    reversed: bool = False
    image: str | None = None

# PARSING
def parse_tarot_response(response: str):
    """
    Разбирает структурированный ответ ИИ по тегам [ENERGY], [INTERPRETATION], [ADVICE].
    Возвращает кортеж: (energy, interpretation, advice)
    """
    energy = ""
    interpretation = ""
    advice = ""

    import re

    # Регулярные выражения для поиска контента между тегами
    energy_match = re.search(r"\[ENERGY\](.*?)(\[INTERPRETATION\]|\[ADVICE\]|$)", response, re.DOTALL | re.IGNORECASE)
    interpretation_match = re.search(
        r"\[INTERPRETATION\](.*?)(\[ENERGY\]|\[ADVICE\]|$)", response, re.DOTALL | re.IGNORECASE
    )
    advice_match = re.search(r"\[ADVICE\](.*)", response, re.DOTALL | re.IGNORECASE)

    if energy_match:
        energy = energy_match.group(1).strip()
    if interpretation_match:
        interpretation = interpretation_match.group(1).strip()
    if advice_match:
        advice = advice_match.group(1).strip()

    # Очистка от случайных остатков тегов
    for tag in ["[ENERGY]", "[INTERPRETATION]", "[ADVICE]", "ENERGY", "INTERPRETATION", "ADVICE"]:
        energy = energy.replace(tag, "")
        interpretation = interpretation.replace(tag, "")
        advice = advice.replace(tag, "")

    # Очистка лишних пробелов и символов новой строки
    energy = energy.strip()
    interpretation = interpretation.strip()
    advice = advice.strip()

    # Graceful fallback на случай, если разбор по тегам совсем не удался
    if not interpretation or len(interpretation) < 10:
        # Пытаемся разделить просто по абзацам
        paragraphs = [p.strip() for p in response.split("\n") if p.strip()]
        if len(paragraphs) >= 3:
            energy = paragraphs[0]
            interpretation = "\n\n".join(paragraphs[1:-1])
            advice = paragraphs[-1]
        elif len(paragraphs) == 2:
            energy = "Энергия дня гармонична и сбалансирована."
            interpretation = paragraphs[0]
            advice = paragraphs[1]
        else:
            energy = "Энергия дня направлена на внутренний фокус и осознанность."
            interpretation = response
            advice = "Постарайтесь провести этот день осознанно и спокойно."

    return energy, interpretation, advice

# ----------------------------------------------------------------------------------------------------------------
# LLM FUNCTIONS
async def llm_answer_day(spread_type: str, cards_text: str):
    prompt = f'''
                Выступи в роли опытного таролога.
                На основе одной выпавшей карты Таро сделай точный и конкретный прогноз на день для человека.

                Не используй вступлений, приветствий, пояснений о себе или шаблонных заключений — предоставляй только сам прогноз, строго структурированный с использованием специальных тегов.

                Твой ответ ДОЛЖЕН содержать ровно три раздела, каждый из которых начинается с соответствующего тега с новой строки:

                [ENERGY]
                Здесь кратко опиши, какая энергия сегодня исходит от выпавшей карты (влияние, настрой, фокус дня). Начни прямо с текста (например: "Энергия дня направлена на..."). Не используй заголовков. Максимум 1-2 предложения.

                [INTERPRETATION]
                Здесь напиши подробный прогноз/трактовку карты: как её значение проявится в событиях, эмоциях, делах или мыслях человека. Опиши день целостно и глубоко. Максимум 3-4 предложения.

                [ADVICE]
                Здесь напиши конкретный практический совет на день. Начни прямо с текста совета. Максимум 1-2 предложения.

                Тип расклада: "{spread_type}"
                Выпавшая карта:
                {cards_text}

                Требования к ответу:
                - Пиши ответ строго на русском языке, не используя английские слова и термины
                - Ответ должен строго содержать теги [ENERGY], [INTERPRETATION] и [ADVICE] перед каждым разделом.
                - Не используй другие разметки тегов или заголовки.
                - Общая длина ответа должна быть в пределах 1000 символов.
                - Пиши на русском языке в мудром, поддерживающем и глубоком тоне опытного таролога.
                - Не задавай вопросов и не упоминай пользователя напрямую.

                Твой структурированный прогноз:
                '''

    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                ]
            }
        ],
        "model": "moonshotai/kimi-k3",
        "max_tokens": 16384,
        "seed": 0,
        "stream": stream,
        "temperature": 1,
        "reasoning_effort": reasoning_lvl
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(invoke_url, headers=headers, json=payload) as res:
            res.raise_for_status()
            response = await res.json()
            return response["choices"][0]["message"]["content"]

async def llm_answer_yesno(question: str, spread_type: str, cards_text: str):
    prompt = f'''
                Выступи в роли опытного таролога.
                На основе одной выпавшей карты Таро дай четкий и конкретный ответ "Да" или "Нет" на поставленный вопрос пользователя, а также кратко поясни его.

                Не используй вступлений, приветствий, пояснений о себе или шаблонных заключений — предоставляй только сам ответ, строго структурированный с использованием специальных тегов.

                Твой ответ ДОЛЖЕН содержать ровно три раздела, каждый из которых начинается с соответствующего тега с новой строки:

                [ENERGY]
                Здесь кратко опиши, какая энергия исходит от выпавшей карты в контексте вопроса (влияние, настрой, фокус). Начни прямо с текста (например: "Энергия карты направлена на..."). Не используй заголовков. Максимум 1-2 предложения.

                [INTERPRETATION]
                Здесь напиши четкий ответ "Да" или "Нет" на поставленный вопрос и дай подробную трактовку/обоснование: как значение карты отвечает на него. Опиши ситуацию целостно и глубоко. Максимум 3-4 предложения.

                [ADVICE]
                Здесь напиши конкретный практический совет по ситуации. Начни прямо с текста совета. Максимум 1-2 предложения.

                Вопрос пользователя: "{question}"
                Тип расклада: "{spread_type}"
                Выпавшая карта:
                {cards_text}

                Требования к ответу:
                - Пиши ответ строго на русском языке, не используя английские слова и термины
                - Ответ должен строго содержать теги [ENERGY], [INTERPRETATION] и [ADVICE] перед каждым разделом.
                - В разделе [INTERPRETATION] обязательно должен присутствовать четкий ответ "Да" или "Нет" на поставленный вопрос.
                - Не используй другие разметки тегов или заголовки.
                - Общая длина ответа должна быть в пределах 1000 символов.
                - Пиши на русском языке в мудром, поддерживающем и глубоком тоне опытного таролога.
                - Не задавай вопросов и не упоминай пользователя напрямую.

                Твой структурированный ответ:
                '''

    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                ]
            }
        ],
        "model": "moonshotai/kimi-k3",
        "max_tokens": 16384,
        "seed": 0,
        "stream": stream,
        "temperature": 1,
        "reasoning_effort": reasoning_lvl
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(invoke_url, headers=headers, json=payload) as res:
            res.raise_for_status()
            response = await res.json()
            return response["choices"][0]["message"]["content"]

async def llm_answer(question: str, spread_type: str, cards_text: str):
    prompt = f'''
                    Выступи в роли опытного таролога.
                    Дай глубокое, но понятное толкование расклада Таро, синтезируя значения карт в единый связный рассказ на основе Вопроса пользователя, Выпавших карт и Типа расклада.

                    Не используй вступлений, приветствий, пояснений о себе или шаблонных заключений — предоставляй только само толкование, строго структурированное с использованием специальных тегов.

                    Твой ответ ДОЛЖЕН содержать ровно три раздела, каждый из которых начинается с соответствующего тега с новой строки:

                    [ENERGY]
                    Здесь кратко опиши общий вывод и основную энергию расклада (влияние, настрой, ключевая тема). Начни прямо с текста (например: "Основная энергия расклада направлена на..."). Не используй заголовков. Максимум 1-2 предложения.

                    [INTERPRETATION]
                    Здесь напиши подробную трактовку расклада: раскрой значение каждой карты в контексте её позиции, ОБЯЗАТЕЛЬНО вплетая их в общую логику ответа и СВЯЗЫВАЯ С ВОПРОСОМ и ОБЬЕДИНЯЯ в единый связный рассказ. Опиши ситуацию целостно и глубоко. Максимум 3-5 предложений.

                    [ADVICE]
                    Здесь напиши конкретный практический совет по раскладу. Начни прямо с текста совета. Максимум 1-2 предложения.

                    Вопрос пользователя: "{question}"
                    Тип расклада: "{spread_type}"
                    Выпавшие карты:
                    {cards_text}

                    Требования к ответу:
                    - Пиши ответ строго на русском языке, не используя английские слова и термины
                    - Ответ должен строго содержать теги [ENERGY], [INTERPRETATION] и [ADVICE] перед каждым разделом.
                    - Не используй другие разметки тегов или заголовки.
                    - Общая длина ответа должна быть в пределах 1000 символов.
                    - Ответ должен быть полностью завершённым и осмысленно законченным в пределах лимита.
                    - Если информация не помещается, приоритизируй краткость и емкость формулировок, не обрывай текст.
                    - Не превышай лимит в 1000 символов ни при каких условиях.
                    - Пиши на русском языке в мудром, поддерживающем и глубоком тоне опытного таролога.
                    - Не задавай вопросов и не упоминай пользователя напрямую.

                    Твое структурированное толкование:
                    '''

    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                ]
            }
        ],
        "model": "moonshotai/kimi-k3",
        "max_tokens": 16384,
        "seed": 0,
        "stream": stream,
        "temperature": 1,
        "reasoning_effort": reasoning_lvl
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(invoke_url, headers=headers, json=payload) as res:
            res.raise_for_status()
            response = await res.json()
            return response["choices"][0]["message"]["content"]


# ----------------------------------------------------------------------------------------------------------------
# TAROT FUNCTIONS:
def get_spread_positions(spread_type: str) -> list[str]:
    if spread_type == "one":
        return ["Ситуация"]
    elif spread_type == "three":
        return ["Прошлое", "Настоящее", "Будущее"]
    elif spread_type == "relationship":
        return ["Вы", "Партнер", "Связь", "Сильные стороны", "Слабые стороны", "Совет"]
    elif spread_type == "day":
        return ["Выпавшая карта"]
    elif spread_type == "verdict":
        return ["Выпавшая карта"]
    return []


def draw_cards(spread_type: str) -> list[Card]:
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
            image=card_data.get("image"),
        )
        drawn_cards.append(card)

    return drawn_cards


def crtimg(cards):
    images = []
    for card in cards:
        images.append(f"https://res.cloudinary.com/dxdalfpbk/image/upload/v1776122504/{card.image}")
    return images


def description(cards):
    cards_description = []
    for card in cards:
        reversed_text = " (перевернутая)" if card.reversed else ""
        cards_description.append(
            f"- Позиция '{card.position}': {card.name_ru}{reversed_text}. Ключевое значение: {card.meaning}."
        )
    cards_text = "\n".join(cards_description)
    return cards_text


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

    res = Image.new("RGB", (width, height))

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
        return f"Error occurred during download: {e}"
    return None
