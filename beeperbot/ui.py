from pathlib import Path
from time import sleep
from typing import Any, Dict, Optional
import asyncio
from threading import Thread

import gradio as gr

from .bot import DiscordBot
from .settings import Settings, Params
from .log import log


class Layout:
    """The layout of the UI

    Attributes:
        tab_bot: bot tab
        tab_token_config: Token config tab

        bot_on_toggle: On/off toggle for the bot
        character_dropdown: List of characters
        controls: Gradio controls
        reset_sliders: Reset sliders button
        settings: Settings (linked to a file)
        settings_save: Settings save button

        discord_token_textbox: Textbox to use for entering a Discord token
        discord_token_save: Save button

        controller: The controller for the UI elements
    """
    # Tabs
    tab_bot: gr.Tab
    tab_token_config: gr.Tab

    # bot tab
    bot_on_toggle: gr.Button
    character_dropdown: gr.Dropdown
    refresh_characters_button: gr.Button
    generation_mode_radio: gr.Radio

    controls: Dict[str, gr.Slider]
    settings: Settings
    starting_channel: gr.Textbox
    channel_whitelist: gr.Textbox
    channel_blacklist: gr.Textbox
    reset_sliders: gr.Button
    settings_save: gr.Button

    # Token config tab
    discord_token_textbox: gr.Textbox
    discord_token_save: gr.Button

    # Others
    controller: "Controller"

    def layout_ui(self, launch: bool = False):
        """Sets up the UI elements

        Args:
            launch (bool): Whether or not to launch a server (default: `False`)
        """
        self.settings = Settings()
        params: Params = self.settings.params
        self.controls = {}
        with gr.Blocks() as ui:
            self.tab_bot = gr.Tab(
                label="Bot")
            self.tab_token_config = gr.Tab(
                label="Config")

            # Bot tab
            with self.tab_bot:
                with gr.Row():
                    self.bot_on_toggle = gr.Button(
                        value="Toggle Start/Stop")
                with gr.Row():
                    with gr.Column():
                        self.character_dropdown_note = gr.Markdown(
                            value=(
                                "**Note**: `instruct` and `chat` load from "
                                + "different source folders. "
                                + "`instruct` loads from `instruct-contexts` "
                                + "and `chat` loads from `characters`. "
                                + "See README.md for details."))
                        self.generation_mode_radio = gr.Radio(
                            ["chat", "instruct"],
                            label="Generation Mode")
                    with gr.Column():
                        self.refresh_characters_button = gr.Button(
                            value="Refresh Characters",
                            elem_id="refresh-characters")
                        self.character_dropdown = gr.Dropdown(
                            label="Character")
                with gr.Row():
                    with gr.Column():
                        # Param controls
                        self.controls["temperature"] \
                            = gr.Slider(0.01, 1.99,
                                        value=params.temperature,
                                        step=0.01, label='temperature')
                        self.controls["top_p"] \
                            = gr.Slider(0.0, 1.0,
                                        value=params.top_p,
                                        step=0.01, label='top_p')
                        self.controls["top_k"] \
                            = gr.Slider(0, 200,
                                        value=params.top_k,
                                        step=1, label='top_k')
                        self.controls["repetition_penalty"] = gr.Slider(
                            0.0, 4096.0,
                            value=params.repetition_penalty,
                            step=0.01, label='repetition_penalty')
                    with gr.Column():
                        self.starting_channel = gr.Textbox(
                            label="Starting Channel",
                            interactive=True)
                        self.channel_whitelist = gr.Textbox(
                            label="Channel Whitelist",
                            placeholder="Leave blank to disable",
                            interactive=True)
                        self.channel_blacklist = gr.Textbox(
                            label="Channel Blacklist",
                            placeholder="Leave blank to disable",
                            interactive=True)
                with gr.Row():
                    self.reset_sliders = gr.Button(
                        value="Reset Sliders")
                    self.settings_save = gr.Button(
                        value="Save Settings")

            # Token config tab
            with self.tab_token_config:
                with gr.Row():
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
    settings: Settings

    def __init__(self,
                 discord_bot: DiscordBot,
                 token: str,
                 settings: Settings):
        self.thread = None
        self.discord_bot = discord_bot
        self.token = token
        self.settings = settings

    def is_running(self):
        return self.thread is not None \
            and self.thread.is_alive()

    async def start_bot(self):
        if self.discord_bot.is_closed():
            self.discord_bot = DiscordBot(self.settings)
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
    settings: Settings
    discord_bot: DiscordBot
    worker: Optional[Worker]

    def __init__(self, layout: Layout):
        self.layout = layout
        self.settings = layout.settings
        self.discord_bot = DiscordBot(self.settings)
        self.worker = None

        # Bot tab
        layout.bot_on_toggle.click(self.handle_on_toggle)

        # Character dropdown config
        layout.character_dropdown.choices = self.load_character_choices()
        layout.character_dropdown.value = self.settings.character
        layout.character_dropdown.select(
            self.handle_character_select,
            inputs=layout.character_dropdown)

        # Refresh characters config
        layout.refresh_characters_button.click(
            self.handle_refresh_characters,
            outputs=layout.character_dropdown)

        # Generation mode config
        layout.generation_mode_radio.value = self.settings.mode
        layout.generation_mode_radio.input(
            self.handle_generation_mode_select,
            inputs=layout.generation_mode_radio,
            outputs=layout.character_dropdown)

        for name, control in layout.controls.items():
            # TODO Implement a better way to fetch the values without getattr
            control.value = getattr(self.settings.params, control.label)
            key_textbox = gr.Textbox(visible=False, value=name)
            control.change(self.handle_param_change,
                           inputs=[key_textbox, control])

        layout.starting_channel.value = self.settings.starting_channel
        layout.starting_channel.change(self.handle_starting_channel,
                                       inputs=layout.starting_channel)

        layout.channel_whitelist.value = self.settings.channel_whitelist
        layout.channel_whitelist.input(self.handle_channel_whitelist,
                                       inputs=layout.channel_whitelist)

        layout.channel_blacklist.value = self.settings.channel_blacklist
        layout.channel_blacklist.change(self.handle_channel_blacklist,
                                        inputs=layout.channel_blacklist)

        layout.reset_sliders.click(self.handle_reset_sliders,
                                   outputs=[*layout.controls.values()])

        layout.settings_save.click(self.handle_settings_save)

        # Config tab
        layout.discord_token_textbox.value = self.load_token_value()
        layout.discord_token_textbox.change(
            self.on_token_change,
            inputs=layout.discord_token_textbox)

        layout.discord_token_save.click(self.handle_save_token)

    def start_worker(self):
        """Creates a worker and starts it"""
        token = self.load_token_value()
        if token and self.worker is None:
            self.worker = Worker(self.discord_bot, token, self.settings)
            self.worker.start()
        elif self.worker is not None \
                and self.worker.discord_bot.is_closed():
            self.worker.start()
        else:
            # This shouldn't be reached. If it does, create an issue
            log.info("Oops! This is awkward...")
            if self.worker is None:
                log.info("Worker is None")
            else:
                log.info("Worker is not None")
                if self.worker.discord_bot.is_closed():
                    log.info("Bot is closed")

    def on_token_change(self, token: str):
        """Called on change of token value

        Args:
            token (str): The new token value
        """
        self.layout.discord_token_textbox.update(value=token)

    def handle_on_toggle(self):
        """Is called when the start/stop toggle button is clicked"""
        print("bot_on_toggle clicked")
        if self.worker is not None \
                and self.worker.is_running():
            self.worker.stop()
        else:
            self.start_worker()

    def handle_refresh_characters(self):
        return self.layout.character_dropdown.update(
            choices=self.load_character_choices())

    def handle_generation_mode_select(self,
                                      mode: str):
        self.discord_bot.mode = mode
        print("Changed generation mode to %s" % mode)

        return self.layout.character_dropdown.update(
            choices=self.load_character_choices())

    def handle_param_change(self, key: str, value: Any):
        """Is called when a param value is changed

        Args:
            key (str): The name of the param
            value (Any): The new value
        """
        setattr(self.discord_bot.params, key, value)

    def handle_starting_channel(self, data: str):
        if type(data) is str:
            self.discord_bot.starting_channel = data

        self.layout.starting_channel.update(value=data)

    def handle_channel_whitelist(self, data: str):
        if type(data) is str:
            self.discord_bot.channel_whitelist = data

        self.layout.channel_whitelist.update(value=data)

    def handle_channel_blacklist(self, data: str):
        if type(data) is str:
            self.discord_bot.channel_blacklist = data

        self.layout.channel_blacklist.update(value=data)

    def handle_reset_sliders(self):
        defaults = self.settings.params.defaults
        values = []
        for name, slider in self.layout.controls.items():
            values.append(slider.update(value=defaults[name]))

        return values

    def handle_settings_save(self):
        settings = self.settings

        settings.mode = self.discord_bot.mode
        settings.character = self.discord_bot.character
        settings.params = self.discord_bot.params
        settings.starting_channel = self.discord_bot.starting_channel
        settings.channel_whitelist = self.discord_bot.channel_whitelist
        settings.channel_blacklist = self.discord_bot.channel_blacklist
        settings.save_to_file()

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
        path = "characters"
        if self.discord_bot.mode == "instruct":
            path = "instruct-contexts"
        for filepath in Path(path).glob(f"*.yaml"):
            characters.append(filepath.stem)

        return characters

    def handle_character_select(self, character: str):
        log.info("Selected character: %s", character)

        base_path = "characters"
        if self.discord_bot.mode == "instruct":
            base_path = "instruct-contexts"
        char_path = Path(f"{base_path}/{character}.yaml")
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
