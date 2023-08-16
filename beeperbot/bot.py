import logging as log
from typing import Dict, List
from pprint import pformat

import requests
import discord

DEFAULT_BASE_URL = "http://localhost:5000"
CHAT_ENDPOINT = f"{DEFAULT_BASE_URL}/api/v1/chat"


class DiscordBot(discord.Client):
    """Discord bot the UI uses"""

    character: str
    channels: List

    def __init__(self, config: Dict):
        self.character = config["character"]

    async def on_ready(self):
        self.channels = list(self.get_all_channels())

        log.info("Connected to discord!")

    async def on_message(self, message: discord.Message):
        if message.channel.name != "bot-testing":
            return
        try:
            async with message.channel.typing():
                self.handle_response(message)
        except discord.DiscordException as e:
            log.error("Exception while processing message: %s",
                      message.clean_content,
                      exc_info=e)

    def handle_response(self, message: discord.Message):
        request = self.create_request(message)
        self.poll_api(request)

    def create_request(self, message: discord.Message):
        user_input = message.clean_content

        request = {
            'user_input': user_input,
            # 'max_new_tokens': 250,
            # 'auto_max_new_tokens': False,
            # Need to actually set this somehow
            'history': {"internal": [], "visible": []},
            'mode': 'chat',
            'character': self.character,
            'your_name': 'You',
            'name1': message.author.display_name,
            # 'name2': 'name of character', # Optional
            # 'context': 'character context', # Optional
            # 'greeting': 'greeting', # Optional
            # 'name1_instruct': 'You', # Optional
            # 'name2_instruct': 'Assistant', # Optional
            # 'context_instruct': 'context_instruct', # Optional
            # 'turn_template': 'turn_template', # Optional
            'regenerate': False,
            '_continue': False,
            # 'preset': 'None',
            # 'do_sample': True,
            # 'temperature': 0.7,
            # 'top_p': 0.1,
            # 'typical_p': 1,
            # 'epsilon_cutoff': 0,  # In units of 1e-4
            # 'eta_cutoff': 0,  # In units of 1e-4
            # 'tfs': 1,
            # 'top_a': 0,
            # 'repetition_penalty': 1.18,
            # 'repetition_penalty_range': 0,
            # 'top_k': 40,
            # 'min_length': 0,
            # 'no_repeat_ngram_size': 0,
            # 'num_beams': 1,
            # 'penalty_alpha': 0,
            # 'length_penalty': 1,
            # 'early_stopping': False,
            # 'mirostat_mode': 0,
            # 'mirostat_tau': 5,
            # 'mirostat_eta': 0.1,
            # 'guidance_scale': 1,
            # 'negative_prompt': '',

            'seed': -1,
            'add_bos_token': True,
            'truncation_length': 2048,
            'ban_eos_token': False,
            'skip_special_tokens': True,
            'stopping_strings': []
        }

        return request

    def poll_api(self, request: Dict) -> Dict:
        response = requests.post(CHAT_ENDPOINT, json=request)

        if response.status_code != 200:
            log.warning(f"Status code came back as {response.status_code}")

            return {}

        result = response.json()

        log.info(f"result: {pformat('result')}")

        return result
