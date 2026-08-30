import asyncio
import logging
import random
from io import BytesIO

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import ActionRow, Button, Container, MediaGallery, Separator, TextDisplay

from tarot_logic import (
    Card,
    crtimg,
    description,
    draw_cards,
    llm_answer,
    llm_answer_day,
    llm_answer_yesno,
    parse_tarot_response,
    rolling,
)
from discord.ui import LayoutView
logger = logging.getLogger("cogs.tarot")


async def get_accent_color(bot, guild_id: int | None) -> int:
    """
    Possible accent color retrieving logic here

    settings = await bot.get_settings(guild_id)
    if settings and "embed_color" in settings:
        color_hex = settings["embed_color"].replace("#", "")
        return int(color_hex, 16)
    """
    return 0xFAD6A5


def add_sep(container: Container, visible: bool = True, spacing: str = "small", **kwargs):
    # Accepted keywords: visible & visable
    is_visible = kwargs.get("visable", visible)
    try:
        sp = discord.enums.SeparatorSpacing.large if spacing == "large" else discord.enums.SeparatorSpacing.small
        container.add_item(Separator(visible=is_visible, spacing=sp))
    except AttributeError:
        container.add_item(Separator(visible=is_visible))


# BASE VIEWS :
class InitialView(LayoutView):
    def __init__(
        self,
        author_id: int,
        card_image: str,
        cards: list[Card],
        text_title: str,
        result_caption: str,
        spread_type: str,
        prediction_task: asyncio.Task,
        caption_title: str | None,
        question: str | None,
        accent_color=0xFAD6A5,
    ):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.card_image = card_image    # link to an image
        self.cards = cards
        self.caption_title = caption_title
        self.text_title = text_title
        self.result_caption = result_caption
        self.spread_type = spread_type
        self.question = question
        self.prediction_task = prediction_task
        self.message = None
        self.accent_color = accent_color

        container = Container(accent_color=accent_color)

        # Caption Title (function definition)
        if self.caption_title:
            container.add_item(TextDisplay(caption_title))

        # 1. Gallery
        if isinstance(card_image, str):
            gallery = MediaGallery()
            media = card_image

            gallery.add_item(media=media)
            container.add_item(gallery)
            add_sep(container)
        else:
            logger.error('Invalid card_image format')

        # 2. Text Display {card.name_ru}
        container.add_item(TextDisplay(self.text_title))
        add_sep(container)

        # 3. ActionRow with button
        self.btn_get = Button(
            label="Трактовка",
            emoji="🃏",
            style=discord.ButtonStyle.blurple
        )
        self.btn_get.callback = self.get_interpretation
        container.add_item(ActionRow(self.btn_get))

        self.add_item(container)

    def recreate_task(self):
        raise NotImplementedError('A subclass must implement the `recreate_task` method')

    # Discord message 'Loading' View Creation Method
    def get_loading_view(self):
        loading_view = LoadingView(
            caption_title=self.caption_title,
            text_title=self.text_title,
            card_image=self.card_image,
            accent_color=self.accent_color
        )
        return loading_view

    # Discord message 'Final Response' View Creation Method
    def get_final_view(self, response):
        energy, interpretation, advice = parse_tarot_response(response)
        final_view = FinalView(
            card_name='\n'.join([f'### - {card.name_ru}' + (' (перевернутая)' if card.reversed else '') for card in self.cards]),
            energy=energy,
            interpretation=interpretation,
            advice=advice,
            card_image=self.card_image,
            question=self.question,
            text_title=self.text_title,
            result_caption=self.result_caption,
            accent_color=self.accent_color,
        )
        return final_view

    # Enforcing author-only interactions
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Это не твой расклад! Вытяни свою карту с помощью команды `/tarot day`.",
                ephemeral=True,
            )
            return False
        return True

    # Getting card Interpretation
    async def get_interpretation(self, interaction: discord.Interaction):
        # 1. Check if the task is done. If done but failed, recreate it.
        recreate = False
        if self.prediction_task.done():
            try:
                self.prediction_task.result()
            except Exception:
                recreate = True

        if recreate:
            self.prediction_task = self.recreate_task()

        # 2. If the task is still running, show the loading view while awaiting it.
        if not self.prediction_task.done():
            loading_view = self.get_loading_view()
            await interaction.response.edit_message(view=loading_view)
            try:
                response = await self.prediction_task
            except Exception as e:
                # Restore the initial view so user can try again
                try:
                    await interaction.edit_original_response(view=self)
                    await interaction.followup.send(
                        "❌ Произошла ошибка при генерации расклада. Пожалуйста, попробуйте еще раз.",
                        ephemeral=True
                    )
                except Exception:
                    pass

            final_view = self.get_final_view(response)
            await interaction.edit_original_response(view=final_view)
            self.stop()
        else:
            # Task is already done successfully, read the cached result immediately
            try:
                response = self.prediction_task.result()
            except Exception as e:
                try:
                    # Since we haven't responded yet, we should use edit_message to show initial view/error state
                    await interaction.response.send_message(
                        "❌ Произошла ошибка при генерации расклада. Пожалуйста, попробуйте еще раз.",
                        ephemeral=True
                    )
                    await interaction.edit_original_response(view=self)
                except Exception:
                    pass
                raise e

            final_view = self.get_final_view(response)
            await interaction.response.edit_message(view=final_view)
            self.stop()

    async def on_timeout(self) -> None:
        self.btn_get.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

# 'Final Response' View
class FinalView(LayoutView):
    def __init__(
        self,
        card_name: str,
        energy: str,
        interpretation: str,
        advice: str,
        question: str | None,
        text_title: str,
        result_caption: str,
        card_image: str,
        accent_color=0xFAD6A5,
    ):
        super().__init__(timeout=None)

        container = Container(accent_color=accent_color)

        # Caption Title (function definition)
        if question:
            container.add_item(TextDisplay(f'{result_caption}\n>>> {question}'))
            add_sep(container)
        else:
            container.add_item(TextDisplay(f'# :cloud: Совет Таро'))
            add_sep(container)

        # 1. Gallery
        if isinstance(card_image, str):
            gallery = MediaGallery()
            media = card_image

            gallery.add_item(media=media)
            container.add_item(gallery)
            add_sep(container, visible=True, spacing="large")
        else:
            logger.error('Invalid card_image format')

        # 2. Text Sections: Energy, Card Name, Interpretation, Advice
        container.add_item(TextDisplay(text_title))
        add_sep(container, visible=True, spacing="large")

        text_energy = f"-# *{energy}*"
        container.add_item(TextDisplay(text_energy))
        add_sep(container, visible=True, spacing="small")

        container.add_item(TextDisplay("```Трактовка```"))
        add_sep(container, visible=False, spacing="small")

        container.add_item(TextDisplay(card_name))
        add_sep(container, visible=True, spacing="small")

        container.add_item(TextDisplay(interpretation))
        add_sep(container, visible=True, spacing="small")

        container.add_item(TextDisplay("```Практический совет```"))
        add_sep(container, visible=False, spacing="small")

        container.add_item(TextDisplay(advice))

        self.add_item(container)

# 'Loading' View
class LoadingView(LayoutView):
    def __init__(self, caption_title: str | None, text_title: str, card_image: str, accent_color=0xFAD6A5):
        super().__init__(timeout=None)

        container = Container(accent_color=accent_color)

        # Caption Title (function definition)
        if caption_title:
            container.add_item(TextDisplay(caption_title))

        # 1. Gallery
        if isinstance(card_image, str):
            gallery = MediaGallery()
            media = card_image

            gallery.add_item(media=media)
            container.add_item(gallery)
            add_sep(container)
        else:
            logger.error('Invalid card_image format')

        # 2. Text Display
        container.add_item(TextDisplay(text_title))
        add_sep(container)

        # 3. Text Display loading indicator instead of ActionRow
        container.add_item(TextDisplay("# :crystal_ball: Трактуем карты..."))

        self.add_item(container)

# Specific Functions Views :
class TarotVerdictInitialView(InitialView):
    def __init__(
        self,
        author_id: int,
        card_image: str,
        cards: list[Card],
        text_title: str,
        result_caption: str,
        spread_type: str,
        prediction_task: asyncio.Task,
        question: str,
        caption_title: str,
        accent_color: int = 0xFAD6A5,
    ):
        super().__init__(
            author_id=author_id,
            card_image=card_image,
            cards=cards,
            caption_title=caption_title,
            text_title=text_title,
            result_caption=result_caption,
            spread_type=spread_type,
            question=question,
            prediction_task=prediction_task,
            accent_color=accent_color,
        )

    def recreate_task(self):
        cards_text = description(self.cards)
        return asyncio.create_task(llm_answer_yesno(question=self.question, spread_type=self.spread_type, cards_text=cards_text))

class TarotDayInitialView(InitialView):
    def __init__(
        self,
        author_id: int,
        card_image: str,
        cards: list[Card],
        text_title: str,
        result_caption: str,
        spread_type: str,
        prediction_task: asyncio.Task,
        caption_title: str = None,
        accent_color: int = 0xFAD6A5,
    ):
        super().__init__(
            author_id=author_id,
            card_image=card_image,
            cards=cards,
            caption_title=caption_title,
            text_title=text_title,
            result_caption=result_caption,
            spread_type=spread_type,
            question=None,
            prediction_task=prediction_task,
            accent_color=accent_color
        )

    def recreate_task(self):
        cards_text = description(self.cards)
        return asyncio.create_task(llm_answer_day(spread_type=self.spread_type, cards_text=cards_text))

class TarotMainInitialView(InitialView):
    def __init__(
        self,
        author_id: int,
        card_image: str,
        cards: list[Card],
        text_title: str,
        result_caption: str,
        spread_type: str,
        prediction_task: asyncio.Task,
        question: str,
        caption_title: str,
        accent_color: int = 0xFAD6A5,
    ):
        super().__init__(
            author_id=author_id,
            card_image=card_image,
            cards=cards,
            caption_title=caption_title,
            text_title=text_title,
            result_caption=result_caption,
            spread_type=spread_type,
            question=question,
            prediction_task=prediction_task,
            accent_color=accent_color
        )

    def recreate_task(self):
        cards_text = description(self.cards)
        return asyncio.create_task(llm_answer(question=self.question, spread_type=self.spread_type, cards_text=cards_text))

class Ball(LayoutView):
    def __init__(self, user, message, answer, accent_color=0xFAD6A5):
        super().__init__(timeout=None)

        container = Container(accent_color=accent_color)

        text1 = f"### {user} спрашивает\n**{message}**"
        container.add_item(TextDisplay(text1))
        add_sep(container)

        text2 = f"### 🔮 Ответ:\n**{answer}**"
        container.add_item(TextDisplay(text2))
        add_sep(container)

        self.add_item(container)

class Binary(LayoutView):
    def __init__(self, accent_color=0xFAD6A5):
        super().__init__(timeout=None)

        container = Container(accent_color=accent_color)
        num = random.randint(0,1)
        definitions = {0: '**False**', 1: '**True**'}
        container.add_item(TextDisplay(f'`{num}`'))
        add_sep(container)
        container.add_item(TextDisplay(definitions[num]))
        self.add_item(container)

# Tarot Cog Class Instance
class Tarot(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("Tarot Cog loaded.")

    # Tarot Command Group
    tarot = app_commands.Group(name="tarot", description="Расклады Таро !")

    # Tarot Bot Commands:

    @tarot.command(name="ask", description="1 карта - ответ на любой вопрос!")
    @app_commands.describe(
        question="Ваш вопрос к Картам", hide="Выберите, сделать ли ответ публичным"
    )
    @app_commands.rename(question="вопрос", hide="скрыть_ответ")
    @app_commands.choices(
        hide=[
            app_commands.Choice(name="Да", value=1),
            app_commands.Choice(name="Нет", value=0),
        ]
    )
    @app_commands.checks.cooldown(1, 20)
    async def one(self, interaction: discord.Interaction, question: str, hide: app_commands.Choice[int] | None = None):
        hide = hide.value if hide is not None else 0
        await interaction.response.defer(ephemeral=bool(hide))

        spread_type = "one"
        cards = draw_cards(spread_type=spread_type)
        cards_text = description(cards)

        caption_title = f"# :sparkles: Расклад из Одной Карты\n>>> {question}"
        text_title = "\n".join(
            [f"## - {card.name_ru}" + (" (перевернутая)" if card.reversed else "") for card in cards]
        )

        result_caption = '# :cloud: Совет Таро'

        prediction_task = asyncio.create_task(
            llm_answer(question=question, spread_type=spread_type, cards_text=cards_text)
        )
        card_image = f"https://res.cloudinary.com/dxdalfpbk/image/upload/v1776122503/{cards[0].image}"

        accent_color = await get_accent_color(self.bot, interaction.guild_id)
        view = TarotMainInitialView(
            author_id=interaction.user.id,
            card_image=card_image,
            cards=cards,
            caption_title=caption_title,
            text_title=text_title,
            result_caption=result_caption,
            spread_type=spread_type,
            prediction_task=prediction_task,
            question=question,
            accent_color=accent_color,
        )

        msg = await interaction.followup.send(view=view)
        view.message = msg

    @tarot.command(name="trio", description="3 карты - ответ на любой вопрос!")
    @app_commands.describe(
        question="Ваш вопрос к Картам", hide="Выберите, сделать ли ответ публичным"
    )
    @app_commands.rename(question="вопрос", hide="скрыть_ответ")
    @app_commands.choices(
        hide=[
            app_commands.Choice(name="Да", value=1),
            app_commands.Choice(name="Нет", value=0),
        ]
    )
    @app_commands.checks.cooldown(1, 20)
    async def three(self, interaction: discord.Interaction, question: str, hide: app_commands.Choice[int] | None = None):
        hide = hide.value if hide is not None else 0
        await interaction.response.defer(ephemeral=bool(hide))

        spread_type = "three"
        cards = draw_cards(spread_type=spread_type)
        cards_text = description(cards)
        images = crtimg(cards)

        prediction_task = asyncio.create_task(llm_answer(question=question, spread_type=spread_type, cards_text=cards_text))

        res = await rolling(images)
        # SAVING THE IMAGE
        buffer = BytesIO()
        res.save(buffer, format="png")
        buffer.seek(0)
        res = discord.File(buffer, filename="res.png")

        caption_title = f"# :sparkles: Расклад из Трёх Карт\n>>> {question}"
        text_title = "\n".join(
            [f"## - {card.name_ru}" + (" (перевернутая)" if card.reversed else "") for card in cards]
        )

        result_caption = '# :cloud: Совет Таро'

        card_image = f"attachment://{res.filename}"

        accent_color = await get_accent_color(self.bot, interaction.guild_id)
        view = TarotMainInitialView(
            author_id=interaction.user.id,
            card_image=card_image,
            cards=cards,
            caption_title=caption_title,
            text_title=text_title,
            result_caption=result_caption,
            spread_type=spread_type,
            prediction_task=prediction_task,
            question=question,
            accent_color=accent_color,
        )

        msg = await interaction.followup.send(view=view, file=res)
        view.message = msg

    @tarot.command(name="love", description="Расклад на отношения - 6 карт")
    @app_commands.describe(
        question="Ваш вопрос к Картам", hide="Выберите, сделать ли ответ публичным"
    )
    @app_commands.rename(question="вопрос", hide="скрыть_ответ")
    @app_commands.choices(
        hide=[
            app_commands.Choice(name="Да", value=1),
            app_commands.Choice(name="Нет", value=0),
        ]
    )
    @app_commands.checks.cooldown(1, 20)
    async def relationship(self, interaction: discord.Interaction, question: str, hide: app_commands.Choice[int] | None = None):
        hide = hide.value if hide is not None else 0
        await interaction.response.defer(ephemeral=bool(hide))

        spread_type = "relationship"
        cards = draw_cards(spread_type=spread_type)
        cards_text = description(cards)
        images = crtimg(cards)

        prediction_task = asyncio.create_task(llm_answer(question=question, spread_type=spread_type, cards_text=cards_text))

        res = await rolling(images)
        # SAVING THE IMAGE
        buffer = BytesIO()
        res.save(buffer, format="png")
        buffer.seek(0)
        res = discord.File(buffer, filename="res.png")

        caption_title = f"# :sparkles: Расклад на Отношения\n>>> {question}"
        text_title = "\n".join(
            [f"## - {card.name_ru}" + (" (перевернутая)" if card.reversed else "") for card in cards]
        )

        result_caption = '# :cupid: Совет Таро'

        card_image = f"attachment://{res.filename}"

        accent_color = await get_accent_color(self.bot, interaction.guild_id)
        view = TarotMainInitialView(
            author_id=interaction.user.id,
            card_image=card_image,
            cards=cards,
            caption_title=caption_title,
            text_title=text_title,
            result_caption=result_caption,
            spread_type=spread_type,
            prediction_task=prediction_task,
            question=question,
            accent_color=accent_color
        )

        msg = await interaction.followup.send(view=view, file=res)
        view.message = msg

    @tarot.command(name="daily", description="Расклад на день ! - 1 карта")
    @app_commands.describe(hide="Выберите, сделать ли ответ публичным")
    @app_commands.rename(hide="скрыть_ответ")
    @app_commands.choices(
        hide=[
            app_commands.Choice(name="Да", value=1),
            app_commands.Choice(name="Нет", value=0),
        ]
    )
    @app_commands.checks.cooldown(1, 20)
    async def day(self, interaction: discord.Interaction, hide: app_commands.Choice[int] | None = None):
        hide = hide.value if hide is not None else 0
        await interaction.response.defer(ephemeral=bool(hide))

        spread_type = "day"
        cards = draw_cards(spread_type=spread_type)
        cards_text = description(cards)

        text_title = f"# :sparkles: Карта дня {cards[0].name_ru}" + (
            " (перевернутая)" if cards[0].reversed else ""
        )

        result_caption = '# :cloud: Совет Таро'

        prediction_task = asyncio.create_task(llm_answer_day(spread_type=spread_type, cards_text=cards_text))
        card_image = f"https://res.cloudinary.com/dxdalfpbk/image/upload/v1776122503/{cards[0].image}"

        accent_color = await get_accent_color(self.bot, interaction.guild_id)
        view = TarotDayInitialView(
            author_id=interaction.user.id,
            card_image=card_image,
            cards=cards,
            text_title=text_title,
            result_caption=result_caption,
            spread_type=spread_type,
            prediction_task=prediction_task,
            accent_color=accent_color,
        )
        msg = await interaction.followup.send(view=view)
        view.message = msg

    @tarot.command(name='verdict', description='Четкий ответ, Да или Нет, на основании Одной Выпавшей Карты')
    @app_commands.describe(
        question="Ваш вопрос к Картам", hide="Выберите, сделать ли ответ публичным"
    )
    @app_commands.rename(question="вопрос", hide="скрыть_ответ")
    @app_commands.choices(
        hide=[
            app_commands.Choice(name="Да", value=1),
            app_commands.Choice(name="Нет", value=0),
        ]
    )
    @app_commands.checks.cooldown(1, 20)
    async def verdict(self, interaction: discord.Interaction, question: str, hide: app_commands.Choice[int] | None = None):
        hide = hide.value if hide is not None else 0
        await interaction.response.defer(ephemeral=bool(hide))

        spread_type = "verdict"
        cards = draw_cards(spread_type=spread_type)
        cards_text = description(cards)

        caption_title = f"# :sparkles: Да/Нет\n>>> {question}"
        text_title = "\n".join(
            [f"## - {card.name_ru}" + (" (перевернутая)" if card.reversed else "") for card in cards]
        )

        result_caption = '# :cloud: Совет Таро'

        prediction_task = asyncio.create_task(
            llm_answer_yesno(question=question, spread_type=spread_type, cards_text=cards_text)
        )
        card_image = f"https://res.cloudinary.com/dxdalfpbk/image/upload/v1776122503/{cards[0].image}"

        accent_color = await get_accent_color(self.bot, interaction.guild_id)
        view = TarotVerdictInitialView(
            author_id=interaction.user.id,
            card_image=card_image,
            cards=cards,
            caption_title=caption_title,
            text_title=text_title,
            result_caption=result_caption,
            spread_type=spread_type,
            prediction_task=prediction_task,
            question=question,
            accent_color=accent_color,
        )
        msg = await interaction.followup.send(view=view)
        view.message = msg

    @app_commands.command(name="ball", description="Спроси магический шар, и он решит твою судьбу (или просто ответит Да/Нет)")
    @app_commands.describe(question='Ваш вопрос к Магическому Шару')
    @app_commands.checks.cooldown(1, 5)
    async def ball(self, interaction: discord.Interaction, question: str):
        choices = {
            "positive": [
                "Да, без лишних вопросов",
                "Всё говорит в пользу да",
                "Определённо да",
                "Да, и даже не думай сомневаться",
                "Похоже, судьба за",
                "Ответ очевиден — да",
                "Можно смело идти вперёд",
                "Да, звучит правильно",
                "Это твой шанс — да",
                'Всё складывается в "да"',
                "Да, время пришло",
                'Прямо чувствуется "да"',
                "Однозначно стоит попробовать",
                "Да, и без оглядки назад",
                'Вселенная кивает "да"',
            ],
            "negative": [
                "Лучше даже не начинать",
                "Всё складывается против",
                "Ответ холодный — нет",
                "Здесь явно не твоё",
                "Плохое время для этого",
                "Не стоит тратить силы",
                'Всё говорит "остановись"',
                "Сейчас точно мимо",
                "Забудь об этом",
                "Риск слишком высокий",
                "Лучше отпусти это",
                "Нет, и точка",
                "Не туда идёшь",
                'Чувствуется сильное "нет"',
                "Закрой эту дверь",
            ],
        }

        user = interaction.user
        answer = random.choice(choices[random.choice(list(choices.keys()))])

        accent_color = await get_accent_color(self.bot, interaction.guild_id)
        await interaction.response.send_message(view=Ball(user, question, answer, accent_color=accent_color))

    @app_commands.command(name='binary', description='Бросьте монетку !')
    @app_commands.checks.cooldown(1, 3)
    async def binary(self, interaction: discord.Interaction):
        accent_color = await get_accent_color(self.bot, interaction.guild_id)
        await interaction.response.send_message(view=Binary(accent_color=accent_color))


async def setup(bot: commands.Bot):
    await bot.add_cog(Tarot(bot))