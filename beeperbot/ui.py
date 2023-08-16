from pathlib import Path
from typing import Dict, Optional
import logging as log
import asyncio

import gradio as gr

from .bot import DiscordBot


class Layout:
    """The layout of the UI

    Attributes:
        tab_bot: bot tab
        tab_config: Config tab
        bot_start: Start button for bot
        bot_stop: Stop button for bot
        discord_token_textbox: Textbox to use for entering a Discord token
        discord_token_save: Save button
        character_dropdown: List of characters
        controller: The controller for the UI elements
    """
    # Tabs
    tab_bot: gr.Tab
    tab_config: gr.Tab

    # bot tab
    bot_start: gr.Button
    bot_stop: gr.Button

    # Config tab
    discord_token_textbox: gr.Textbox
    discord_token_save: gr.Button

    character_dropdown: gr.Dropdown

    # Others
    controller: "Controller"

    def layout_ui(self, launch: bool = False):
        """Sets up the UI elements

        Args:
            launch (bool): Whether or not to launch a server (default: `False`)
        """
        with gr.Blocks() as ui:
            self.tab_bot = gr.Tab(
                label="Bot")
            self.tab_config = gr.Tab(
                label="Config")

            with self.tab_bot:
                with gr.Row():
                    self.bot_start = gr.Button(
                        value="Start")
                    self.bot_stop = gr.Button(
                        value="Stop")

            with self.tab_config:
                with gr.Row():
                    # Config
                    self.discord_token_textbox = gr.Textbox(
                        label="Discord token",
                        value="",
                        interactive=True)
                    self.discord_token_save = gr.Button(
                        value="Save")
                with gr.Row():
                    self.character_dropdown = gr.Dropdown(
                        label="Character")

            self.controller = Controller(self)

            if launch:
                ui.launch()


class Controller:
    """Controller for the UI elements

    Attributes:
        layout: The Layout to connect with
        character: A Dict containing character data
    """
    layout: Layout
    character: str
    discord_bot: Optional[DiscordBot]

    def __init__(self, layout: Layout):
        self.layout = layout
        self.character = ""
        self.discord_bot = None

        layout.bot_start.click(self.handle_start)
        layout.bot_stop.click(self.handle_stop)

        layout.discord_token_textbox.value = self.load_token_value()
        layout.discord_token_textbox.change(
            self.on_token_change,
            inputs=layout.discord_token_textbox)
        layout.discord_token_save.click(self.handle_save_token)
        layout.character_dropdown.choices = self.load_character_choices()
        layout.character_dropdown.select(
            self.handle_character_select,
            inputs=layout.character_dropdown)

    def on_token_change(self, token: str):
        self.layout.discord_token_textbox.value = token
        self.layout.discord_token_textbox.update()

    def handle_start(self):
        async def start():
            if self.discord_bot is not None:
                await self.discord_bot.close()
            self.discord_bot = DiscordBot({"character": self.character})

            await self.discord_bot.start(self.load_token_value())

        asyncio.run(start())

    def handle_stop(self):
        async def stop():
            if self.discord_bot is None:
                return
            await self.discord_bot.close()

        asyncio.run(stop())

    def load_token_value(self):
        try:
            with open("beeperbot-token.txt") as f:
                return f.read()
        except OSError:
            pass

        return ""

    def handle_save_token(self):
        token = self.layout.discord_token_textbox.value

        print("Writing save token", token)

        with open("beeperbot-token.txt", "w") as f:
            f.write(token)

    def load_character_choices(self):
        characters = []
        for ext in ["yml", "yaml", "json"]:
            for filepath in Path("characters").glob(f"*.{ext}"):
                characters.append(filepath.stem)

        log.info("len(characters): %d", len(characters))

        return characters

    def handle_character_select(self, character: str):
        log.info("Selected character: %s", character)

        if character == "None":
            self.character = "None"
            return

        char_path = Path(f"characters/{character}.yaml")
        if char_path.exists():
            self.character = character

        if self.character:
            log.info("Loaded %s successfully!", character)
