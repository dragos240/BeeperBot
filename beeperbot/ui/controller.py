from pathlib import Path
from typing import Any, Optional
import os.path

import gradio as gr
from gradio.external_utils import yaml

from ..bot import DiscordBot
from ..settings import Settings
from ..log import log
from .layout import Layout
from .worker import Worker


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
            outputs=[layout.character_dropdown,
                     layout.instruction_template_dropdown])

        # Generation mode config
        layout.generation_mode_radio.value = self.settings.mode
        layout.generation_mode_radio.input(
            self.handle_generation_mode_select,
            inputs=layout.generation_mode_radio,
            outputs=[layout.character_dropdown,
                     layout.instruction_template_dropdown])

        if layout.settings.mode == "instruct":
            layout.instruction_template_dropdown.visible = True
            layout.instruction_template_dropdown.value \
                = self.settings.instruction_template
        layout.instruction_template_dropdown.choices \
            = self.load_template_choices()
        # TODO Add loading from settings
        layout.instruction_template_dropdown.select(
            self.handle_instruction_template_select,
            inputs=layout.instruction_template_dropdown)

        for name, control in layout.controls.items():
            # TODO Implement a better way to fetch the values without getattr
            if control.label is None:
                continue
            control.value = getattr(self.settings.params, name)
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
            log.info("This shouldn't be reached. If it does, create an "
                     + "issue")
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
        # This sets the value in memory
        self.layout.discord_token_textbox.value = token
        # This sets the value in the UI
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
        return [self.layout.character_dropdown.update(
            choices=self.load_character_choices()),
            self.layout.instruction_template_dropdown.update(
            choices=self.load_template_choices())]

    def handle_generation_mode_select(self,
                                      mode: str):
        self.discord_bot.mode = mode
        print("Changed generation mode to %s" % mode)

        if mode == "instruct":
            instruction_template_state = \
                self.layout.instruction_template_dropdown.update(visible=True)
        else:
            instruction_template_state = \
                self.layout.instruction_template_dropdown.update(visible=False)

        return [self.layout.character_dropdown.update(
            choices=self.load_character_choices()),
            instruction_template_state]

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
        if self.discord_bot.instruction_template:
            settings.instruction_template \
                = self.discord_bot.instruction_template
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
        for filepath in Path(path).glob("*.yaml"):
            characters.append(filepath.stem)

        return characters

    def load_template_choices(self):
        templates = []
        for filepath in Path("instruction-templates").glob("*.yaml"):
            templates.append(filepath.stem)

        return templates

    def handle_character_select(self, character: str):
        log.info("Selected character: %s", character)

        char_path = Path(f"characters/{character}.yaml")
        self.discord_bot.character = "None"
        if not char_path.exists():
            return
        if self.worker is not None and self.worker.is_running():
            self.discord_bot.update_character(character)
        else:
            self.discord_bot.character = character

        if self.discord_bot.character:
            log.info("Loaded %s successfully!", character)

    def handle_instruction_template_select(self, template: str):
        log.info("Selected template: %s", template)
        base_path = "instruction-templates"
        template_path = f"{base_path}/{template}.yaml"
        if not os.path.exists(template_path):
            return
        self.discord_bot.instruction_template = template

        log.info("Loaded %s successfully!", template_path)
