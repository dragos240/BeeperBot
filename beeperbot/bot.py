import asyncio
import logging as log
from pprint import pformat, pprint
from typing import Any, Dict, List

import requests
import discord

DEFAULT_BASE_URL = "http://localhost:5000"
CHAT_ENDPOINT = f"{DEFAULT_BASE_URL}/api/v1/chat"


class DiscordBot(discord.Client):
    """Discord bot the UI uses"""

    character: str
    history: Dict
    do_greeting: bool
    active_channels: List[discord.TextChannel]
    params: Dict[str, Any]

    def __init__(self, config: Dict):
        self.character = config["character"]
        self.history = {"internal": [], "visible": []}
        self.do_greeting = True
        self.active_channels = []
        self.params = config["params"]

        super().__init__(intents=self.get_intents())

    @staticmethod
    def get_intents() -> discord.Intents:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        return intents

    async def on_ready(self):
        log.info("Connected to discord!")

        if self.do_greeting:
            await self.greet()
            self.do_greeting = False

    async def greet(self):
        channel = self.get_greeting_channel()
        self.active_channels.append(channel)
        request = self.create_request("Say hi~", "Chat")
        bot_greeting = self.get_bot_reply(self.poll_api(request))

        await channel.send(bot_greeting)

    def get_bot_names(self, channel: discord.TextChannel):
        names = [self.character.lower()]
        if self.user is not None:
            names.append(self.user.display_name.lower())
            for channel in self.active_channels:
                for member in channel.members:
                    if member.id == self.get_id():
                        names.append(member.nick)
                        break

        return names

    def get_name_with_message(self, message: discord.Message):
        names = self.get_bot_names(message)
        result = self.character

        for name in names:
            if name in message.clean_content.lower():
                result = name

        return result

    def is_name_in_message(self, message: discord.Message) -> bool:
        names = self.get_bot_names(message)

        for name in names:
            if name in message.clean_content.lower():
                return True

        return False

    def get_id(self) -> int:
        if self.user is not None:
            return self.user.id

        return -1

    async def update_character_async(self, name: str):
        self.character = name
        if self.character == "None":
            return
        for channel in self.active_channels:
            members = channel.guild.members
            for member in members:
                if member.id == self.get_id():
                    if member.nick != name:
                        await member.edit(nick=name)

    def update_character(self, name: str):
        asyncio.run_coroutine_threadsafe(
            self.update_character_async(name),
            self.loop)

    async def on_message(self, message: discord.Message):
        # if message.channel.name != "bot-testing":
        #     return
        if message.channel not in self.active_channels \
                and self.is_name_in_message(message):
            self.active_channels.append(message.channel)
            log.info("I was pinged in %s. I can now talk there!",
                     message.channel.name)
        if (self.user is not None
                and message.author.id == self.user.id) \
                or message.clean_content.startswith("//") \
                or message.channel not in self.active_channels:
            return

        # Update nicks
        await self.update_character_async(self.character)

        try:
            async with message.channel.typing():
                await self.handle_response(message)
        except discord.DiscordException as e:
            log.error("Exception while processing message: %s",
                      message.clean_content,
                      exc_info=e)

    def get_bot_reply(self, response: Dict) -> str:
        bot_reply = ""
        if "internal" in response:
            bot_reply = response["internal"][-1][-1]

        return bot_reply

    async def handle_response(self, message: discord.Message):
        request = self.create_request(message.clean_content,
                                      message.author.display_name)
        response = self.poll_api(request)

        log.info("Params: %s", pformat(self.params))

        bot_reply = self.get_bot_reply(response)
        await message.reply(bot_reply, mention_author=False)
        self.history = response

    def get_greeting_channel(self) -> discord.TextChannel:
        # TODO: Make this a setting
        for guild in self.guilds:
            channel: discord.TextChannel
            for channel in guild.channels:
                if channel.name == "serial-experiments-nat":
                    return channel

    def create_request(self,
                       message: str,
                       display_name: str):
        user_input = "{} says \"{}\"".format(
            display_name, message)
        bot_name = self.character

        request = self.params.copy()

        # It's possible some values accidentally resolve to None
        for k, v in request.items():
            if v is None:
                request[k] = 0.0

        request.update({
            'user_input': user_input,
            # 'max_new_tokens': 250,
            # 'auto_max_new_tokens': False,
            'history': self.history,
            'mode': 'chat',
            'character': self.character,
            'your_name': "You",
            # 'name1': message.author.display_name,
            'name2': bot_name,
            # 'context': 'character context', # Optional
            # 'greeting': 'greeting', # Optional
            # 'name1_instruct': 'You', # Optional
            # 'name2_instruct': 'Assistant', # Optional
            # 'context_instruct': 'context_instruct', # Optional
            # 'turn_template': 'turn_template', # Optional
            'regenerate': False,
            '_continue': False,
            # 'preset': 'None',
            'do_sample': True,
            # 'temperature': self.params["temperature"],
            # 'top_p': self.params["top_p"],
            # 'typical_p': 1,
            # 'epsilon_cutoff': 0,  # In units of 1e-4
            # 'eta_cutoff': 0,  # In units of 1e-4
            # 'tfs': 1,
            # 'top_a': 0,
            # 'repetition_penalty': self.params["repetition_penalty"],
            # 'repetition_penalty_range': 0,
            # 'top_k': self.params["top_k"],
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
        })

        return request

    def poll_api(self, request: Dict) -> Dict:
        response = requests.post(CHAT_ENDPOINT, json=request)

        if response.status_code != 200:
            log.warning(f"Status code came back as {response.status_code}")

            return {}

        result: Dict = \
            response.json()['results'][0]['history']

        return result
