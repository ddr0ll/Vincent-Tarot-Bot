import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import LayoutView, Container, TextDisplay, Separator, MediaGallery
import os

tarot = os.getenv('TAROT_COMMAND_ID')

def add_sep(container: Container, spacing="small"):     # Anything except 'large' will be considered Small Spacing
    try:
        sp = discord.enums.SeparatorSpacing.large if spacing == "large" else discord.enums.SeparatorSpacing.small
        container.add_item(Separator(visible=True, spacing=sp))
    except AttributeError:
        container.add_item(Separator(visible=True))

class Help(LayoutView):
    def __init__(self):
        super().__init__(timeout=None)

        container = Container(accent_color=0xFAD6A5)

        gallery = MediaGallery()
        gallery.add_item(media="https://cdn.discordapp.com/attachments/1492697583426998484/1494625512998436915/VincentBannerImmerse.png?ex=69e349fb&is=69e1f87b&hm=e3592fafb32bbadf0b31a8810b7ef352c061bc388411dbba193548ae2e867339&")
        container.add_item(gallery)
        add_sep(container)

        text1 = '# Команды:'
        container.add_item(TextDisplay(text1))
        add_sep(container)

        text2 = f'- </tarot daily:{tarot}>\n**Расклад карт Таро на День в размере Одной Карты**'
        container.add_item(TextDisplay(text2))
        add_sep(container)

        text3 = f'- </tarot verdict:{tarot}>\n**Строгое «Да» или «Нет» на основе энергетики Одной Карты**'
        container.add_item(TextDisplay(text3))
        add_sep(container)

        text4 = f'- </tarot ask:{tarot}>\n**Расклад Таро в размере Одной Карты**\nВ обязательном поле "message" - введите свой вопрос картам'
        container.add_item(TextDisplay(text4))
        add_sep(container)

        text5 = f'- </tarot trio:{tarot}>\n**Расклад Таро в размере Трёх Карт**\nВ обязательном поле "message" - введите свой вопрос картам'
        container.add_item(TextDisplay(text5))
        add_sep(container)

        text6 = f'- </tarot love:{tarot}>\n**Расклад Таро на Отношения в размере Шести Карт**\nВ обязательном поле "message" - введите свой вопрос картам на тему отношений'
        container.add_item(TextDisplay(text6))
        add_sep(container)


        self.add_item(container)


class tarot_docs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    docs_commands = app_commands.Group(name='docs', description='📄 Документация бота')

    @docs_commands.command(name='tarot', description='Документация Таро')
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        await interaction.channel.send(view=Help())

        await interaction.followup.send('Sent you the docs !', ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(tarot_docs(bot))