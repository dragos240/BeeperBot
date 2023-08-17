from pathlib import Path
from time import sleep
from typing import Dict, List, Optional
import logging as log
import asyncio
from threading import Thread

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
                    self.bot_stop.interactive = False

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


class Worker:
    thread: Optional[Thread]
    discord_bot: DiscordBot
    token: str
    do_stop: bool

    def __init__(self,
                 discord_bot: DiscordBot,
                 token: str):
        self.thread = None
        self.discord_bot = discord_bot
        self.token = token
        self.do_stop = False

    def is_running(self):
        return self.thread is not None \
            and self.thread.is_alive()

    async def start_bot(self):
        if self.discord_bot.is_closed():
            self.discord_bot = DiscordBot({"character": "None"})
        await self.discord_bot.start(self.token)
        await self.discord_bot.wait_until_ready()

    def start_coroutine(self):
        asyncio.run(self.start_bot())

    def start(self):
        if not self.is_running():
            log.info("Bot not running, attempting to start")
            if self.discord_bot.loop is None:
                print("Bot loop is None, creating new one")
                self.discord_bot.loop = asyncio.new_event_loop()
            self.thread = Thread(target=self.start_coroutine)
            self.thread.start()

    def stop(self):
        loop = self.discord_bot.loop
        if self.is_running():
            asyncio.run_coroutine_threadsafe(self.discord_bot.close(), loop)

            while not self.discord_bot.is_closed():
                log.debug("Waiting until closed")
                sleep(1)

        log.info("Discord connection closed")


class Controller:
    """Controller for the UI elements

    Attributes:
        layout: The Layout to connect with
        character: A Dict containing character data
    """
    layout: Layout
    discord_bot: DiscordBot
    worker: Optional[Worker]

    def __init__(self, layout: Layout):
        self.layout = layout
        self.discord_bot = DiscordBot({"character": "None"})
        self.worker = None

        layout.bot_start.click(self.handle_start,
                               outputs=[
                                   layout.bot_stop,
                                   layout.bot_start
                               ])
        layout.bot_stop.click(self.handle_stop,
                              outputs=[
                                  layout.bot_start,
                                  layout.bot_stop
                              ])

        layout.discord_token_textbox.value = self.load_token_value()
        layout.discord_token_textbox.change(
            self.on_token_change,
            inputs=layout.discord_token_textbox)

        layout.discord_token_save.click(self.handle_save_token)

        layout.character_dropdown.choices = self.load_character_choices()
        layout.character_dropdown.select(
            self.handle_character_select,
            inputs=layout.character_dropdown)

    def start_worker(self):
        """Creates a worker and starts it"""
        token = self.load_token_value()
        if token and self.worker is None:
            self.worker = Worker(self.discord_bot, token)
            self.worker.start()
        elif self.worker is not None \
                and self.worker.discord_bot.is_closed():
            self.worker.start()
        else:
            log.info("Oops! This is awkward...")
            if self.worker is None:
                log.info("Worker is None")
            else:
                log.info("Worker is not None")
                if self.worker.discord_bot.is_closed():
                    log.info("Bot is closed")

    def on_token_change(self, token: str):
        self.layout.discord_token_textbox.update(value=token)

    def handle_start(self) -> List[Dict]:
        """Is called when the start button is clicked

        Returns:
            List[Dict]: A list of UI elements to update
        """
        print("handle_start clicked")
        self.start_worker()

        return [self.layout.bot_stop.update(interactive=True),
                self.layout.bot_start.update(interactive=False)]

    def handle_stop(self):
        """Is called when the stop button is clicked

        Returns:
            List[Dict]: A list of UI elements to update
        """
        print("handle_stop clicked")
        if self.worker is not None:
            self.worker.stop()

        return [self.layout.bot_start.update(interactive=True),
                self.layout.bot_stop.update(interactive=False)]

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
            self.discord_bot.character = "None"
            return

        char_path = Path(f"characters/{character}.yaml")
        if char_path.exists():
            self.discord_bot.character = character

        if self.discord_bot.character:
            log.info("Loaded %s successfully!", character)
