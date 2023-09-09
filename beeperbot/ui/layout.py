from typing import Dict

import gradio as gr

from ..settings import Settings, Params


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
    instruction_template_dropdown: gr.Dropdown
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

    def __init__(self,
                 settings: Settings) -> None:
        self.settings = settings
        params: Params = self.settings.params
        self.controls = {}
        with gr.Blocks():
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
                    self.character_dropdown_note = gr.Markdown(
                        value=(
                            "**Note**: `instruct` and `chat` load from "
                            + "different source folders. "
                            + "`instruct` loads from `instruct-contexts` "
                            + "and `chat` loads from `characters`. "
                            + "See README.md for details."))
                with gr.Row():
                    self.generation_mode_radio = gr.Radio(
                        ["chat", "instruct"],
                        label="Generation Mode")
                    self.refresh_characters_button = gr.Button(
                        value="Refresh Characters/Templates",
                        elem_id="refresh-characters")
                with gr.Row():
                    self.character_dropdown = gr.Dropdown(
                        label="Character")
                    self.instruction_template_dropdown = gr.Dropdown(
                        label="Insruction Template",
                        visible=False)
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
