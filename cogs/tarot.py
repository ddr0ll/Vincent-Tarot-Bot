import discord
from discord.ext import commands
from discord import app_commands

from comds import *

from discord.ui import LayoutView, Container, TextDisplay, Separator, MediaGallery

def add_sep(container: Container, spacing="small"):
    try:
        sp = discord.enums.SeparatorSpacing.large if spacing == "large" else discord.enums.SeparatorSpacing.small
        container.add_item(Separator(visible=True, spacing=sp))
    except AttributeError:
        container.add_item(Separator(visible=True))


class Cards(LayoutView):
    def __init__(self, title, body, conclusion, media, spread_type):
        super().__init__(timeout=None)

        container = Container(accent_color=0xFAD6A5)

        gallery = MediaGallery()
        gallery.add_item(media=media)
        container.add_item(gallery)
        add_sep(container)

        text1 = f'# {title}'
        container.add_item(TextDisplay(text1))
        add_sep(container)

        text2 = '### 🃏 Разбор расклада'
        container.add_item(TextDisplay(text2))
        add_sep(container)

        text3 = f'**{body}**'
        container.add_item(TextDisplay(text3))
        add_sep(container)

        text4 = '### 🔮 Послание Арканов'
        container.add_item(TextDisplay(text4))
        add_sep(container)

        text5 = f'{conclusion}'
        container.add_item(TextDisplay(text5))

        self.add_item(container)


class Ball(LayoutView):
    def __init__(self, user, message, answer):
        super().__init__(timeout=None)

        container = Container(accent_color=0xFAD6A5)

        if message != 'default message placeholder':
            text1 = (
                f'### {user}\n'
                f'**{message}**'
            )
            container.add_item(TextDisplay(text1))
            add_sep(container)

        text2 = (
            f'### 🔮 Ball Said:\n'
            f'**{answer}**'
        )
        container.add_item(TextDisplay(text2))
        add_sep(container)

        self.add_item(container)


class Tarot(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    tarot = app_commands.Group(name='tarot', description='Расклады Таро !')

    @tarot.command(name='one', description='1 карта - ответ на любой вопрос!')
    @app_commands.checks.cooldown(1, 20)
    async def one(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer()
        spread_type = 'one'
        cards = draw_cards(spread_type=spread_type)
        cards_text = description(cards)

        response = await llm_answer(question=message, spread_type=spread_type, cards_text=cards_text)

        lst, info = splt(response)

        title = "🔮 Расклад из Одной Карты"
        body = "\n".join(info)
        conclusion = lst[-1]
        media = f'https://res.cloudinary.com/dxdalfpbk/image/upload/v1776122503/{cards[0].image}'

        await interaction.followup.send(view=Cards(title, body, conclusion, media, spread_type))

    @tarot.command(name='three', description='3 карты - ответ на любой вопрос!')
    @app_commands.checks.cooldown(1, 20)
    async def three(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer()
        spread_type = 'three'
        cards = draw_cards(spread_type=spread_type)
        cards_text = description(cards)
        images = crtimg(cards)

        response = await llm_answer(question=message, spread_type=spread_type, cards_text=cards_text)

        res = await rolling(images)

        # SAVING THE IMAGE
        buffer = BytesIO()
        res.save(buffer, format="png")
        buffer.seek(0)
        res = discord.File(buffer, filename='res.png')

        lst, info = splt(response)

        title = '🔮 Расклад из Трёх Карт'
        body = "\n".join(info)
        conclusion = lst[-1]
        media = f"attachment://{res.filename}"

        await interaction.followup.send(view=Cards(title, body, conclusion, media, spread_type), file=res)

    @tarot.command(name='relationship', description='Расклад на отношения - 6 карт')
    @app_commands.checks.cooldown(1, 20)
    async def relationship(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer()
        spread_type = 'relationship'
        cards = draw_cards(spread_type=spread_type)
        cards_text = description(cards)
        images = crtimg(cards)

        response = await llm_answer(question=message, spread_type=spread_type, cards_text=cards_text)

        res = await rolling(images)

        # SAVING THE IMAGE
        buffer = BytesIO()
        res.save(buffer, format="png")
        buffer.seek(0)
        res = discord.File(buffer, filename='res.png')

        lst, info = splt(response)

        title = '🔮 Расклад на Отношения'
        body = "\n".join(info)
        conclusion = lst[-1]
        media = f"attachment://{res.filename}"

        await interaction.followup.send(view=Cards(title, body, conclusion, media, spread_type), file=res)

    @tarot.command(name="day", description="Расклад на день ! - 1 карта")
    @app_commands.checks.cooldown(1, 20)
    async def day(self, interaction: discord.Interaction):
        await interaction.response.defer()
        spread_type = 'day'
        cards = draw_cards(spread_type=spread_type)
        cards_text = description(cards)

        response = await llm_answer_day(spread_type=spread_type, cards_text=cards_text)

        lst, info = splt(response)

        title = "🔮 Расклад на День"
        body = "\n".join(info)
        conclusion = lst[-1]
        media = f'https://res.cloudinary.com/dxdalfpbk/image/upload/v1776122503/{cards[0].image}'

        await interaction.followup.send(view=Cards(title, body, conclusion, media, spread_type))

    @app_commands.command(name="ball", description='Спроси что угодно')
    @app_commands.checks.cooldown(1, 5)
    async def ball(self, interaction: discord.Interaction, message: str = "default message placeholder"):
        choices = {
            'positive': [
                "Да, без лишних вопросов",
                "Всё говорит в пользу да",
                "Определённо да",
                "Да, и даже не думай сомневаться",
                "Похоже, судьба за",
                "Ответ очевиден — да",
                "Можно смело идти вперёд",
                "Да, звучит правильно",
                "Это твой шанс — да",
                "Всё складывается в “да”",
                "Да, время пришло",
                "Прямо чувствуется “да”",
                "Однозначно стоит попробовать",
                "Да, и без оглядки назад",
                "Вселенная кивает “да”"
            ],
            'negative': [
                "Лучше даже не начинать",
                "Всё складывается против",
                "Ответ холодный — нет",
                "Здесь явно не твоё",
                "Плохое время для этого",
                "Не стоит тратить силы",
                "Всё говорит “остановись”",
                "Сейчас точно мимо",
                "Забудь об этом",
                "Риск слишком высокий",
                "Лучше отпусти это",
                "Нет, и точка",
                "Не туда идёшь",
                "Чувствуется сильное “нет”",
                "Закрой эту дверь"
            ]
        }


        user = interaction.user
        answer = random.choice(choices[random.choice(list(choices.keys()))])

        await interaction.response.send_message(view=Ball(user, message, answer))

async def setup(bot: commands.Bot):
    await bot.add_cog(Tarot(bot))