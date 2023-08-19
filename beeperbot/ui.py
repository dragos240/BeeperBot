from pathlib import Path
from time import sleep
from typing import Any, Dict, List, Optional
import logging as log
import asyncio
from threading import Thread

import gradio as gr
from gradio.external_utils import yaml

from .bot import DiscordBot


default_params: Dict = {
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 20,
    "repetition_penalty": 1.15,
}

default_config: Dict = {
    "character": "None"
}

CONFIG_PATH = "beeperbot.yaml"


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
    bot_on_toggle: gr.Button

    character_dropdown: gr.Dropdown
    params: Dict[str, gr.Slider]
    reset_sliders: gr.Button
    settings_save: gr.Button

    # Config tab
    discord_token_textbox: gr.Textbox
    discord_token_save: gr.Button

    # Others
    controller: "Controller"

    def layout_ui(self, launch: bool = False):
        """Sets up the UI elements

        Args:
            launch (bool): Whether or not to launch a server (default: `False`)
        """
        self.params = {}
        with gr.Blocks() as ui:
            self.tab_bot = gr.Tab(
                label="Bot")
            self.tab_config = gr.Tab(
                label="Config")

            with self.tab_bot:
                with gr.Row():
                    self.bot_on_toggle = gr.Button(
                        value="Toggle Start/Stop")
                with gr.Row():
                    self.character_dropdown = gr.Dropdown(
                        label="Character")
                with gr.Row():
                    with gr.Column():
                        # Param controls
                        self.params["temperature"] \
                            = gr.Slider(0.01, 1.99,
                                        value=default_params['temperature'],
                                        step=0.01, label='temperature')
                        self.params["top_p"] \
                            = gr.Slider(0.0, 1.0,
                                        value=default_params['top_p'],
                                        step=0.01, label='top_p')
                        self.params["top_k"] \
                            = gr.Slider(0, 200,
                                        value=default_params['top_k'],
                                        step=1, label='top_k')
                        self.params["repetition_penalty"] = gr.Slider(
                            0.0, 4096.0,
                            value=default_params['repetition_penalty'],
                            step=0.01, label='repetition_penalty')
                    with gr.Column():
                        self.reset_sliders = gr.Button(
                            value="Reset Sliders")
                        self.settings_save = gr.Button(
                            value="Save Settings")

            # Config
            with self.tab_config:
                with gr.Row():
                    # Config
                    self.discord_token_textbox = gr.Textbox(
                        label="Discord token",
                        value="",
                        interactive=True)
                    self.discord_token_save = gr.Button(
                        value="Save")

            self.controller = Controller(self)

            if launch:
                ui.launch()


class Worker:
    thread: Optional[Thread]
    discord_bot: DiscordBot
    token: str
    config: Dict[str, Any]

    def __init__(self,
                 discord_bot: DiscordBot,
                 token: str,
                 config: Dict[str, Any]):
        self.thread = None
        self.discord_bot = discord_bot
        self.token = token
        self.config = config

    def is_running(self):
        return self.thread is not None \
            and self.thread.is_alive()

    async def start_bot(self):
        if self.discord_bot.is_closed():
            self.discord_bot = DiscordBot(self.config)
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
            self.thread = None

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
    config: Dict
    discord_bot: DiscordBot
    worker: Optional[Worker]

    def __init__(self, layout: Layout):
        self.layout = layout
        self.config = self.get_config()
        self.discord_bot = DiscordBot(self.config)
        self.worker = None

        # Bot tab
        layout.bot_on_toggle.click(self.handle_on_toggle)

        layout.character_dropdown.choices = self.load_character_choices()
        layout.character_dropdown.value = self.config["character"]
        layout.character_dropdown.select(
            self.handle_character_select,
            inputs=layout.character_dropdown)

        for key, value in layout.params.items():
            value.value = self.config["params"][value.label]
            key_textbox = gr.Textbox(visible=False, value=key)
            value.change(self.handle_param_change,
                         inputs=[key_textbox, value])

        layout.reset_sliders.click(self.handle_reset_sliders,
                                   outputs=[*layout.params.values()])

        layout.settings_save.click(self.handle_config_save)

        # Config tab
        layout.discord_token_textbox.value = self.load_token_value()
        layout.discord_token_textbox.change(
            self.on_token_change,
            inputs=layout.discord_token_textbox)

        layout.discord_token_save.click(self.handle_save_token)

    def get_config(self) -> Dict:
        config = default_config.copy()
        config["params"] = default_params.copy()
        config_path = Path(CONFIG_PATH)

        if config_path.exists():
            with open(config_path, "r") as f:
                config.update(yaml.full_load(f.read()))
        else:
            with open(config_path, "w") as f:
                f.write(yaml.dump(config))

        return config

    def start_worker(self):
        """Creates a worker and starts it"""
        token = self.load_token_value()
        if token and self.worker is None:
            self.worker = Worker(self.discord_bot, token, self.config)
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

    def handle_on_toggle(self):
        """Is called when the start/stop toggle button is clicked
        """
        print("bot_on_toggle clicked")
        if self.worker is not None \
                and self.worker.is_running():
            self.worker.stop()
        else:
            self.start_worker()

    def handle_param_change(self, key: str, value: Any):
        self.discord_bot.params[key] = value

    def handle_reset_sliders(self):
        values = []
        for name, slider in self.layout.params.items():
            values.append(slider.update(value=default_params[name]))

        return values

    def handle_config_save(self):
        config = self.get_config()

        config["character"] = self.discord_bot.character
        config["params"] = self.discord_bot.params
        with open(CONFIG_PATH, "w") as f:
            f.write(yaml.dump(config))

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

        return characters

    def handle_character_select(self, character: str):
        log.info("Selected character: %s", character)

        char_path = Path(f"characters/{character}.yaml")
        if char_path.exists():
            if self.worker is not None and self.worker.is_running():
                self.discord_bot.update_character(character)
            else:
                self.discord_bot.character = character
        else:
            self.discord_bot.character = "None"
            return

        if self.discord_bot.character:
            log.info("Loaded %s successfully!", character)
