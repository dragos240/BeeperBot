import asyncio
import logging as log
from pprint import pformat
from typing import Dict, List
import os


from discord.app_commands import CommandTree
from gradio.external_utils import yaml

import requests
import discord

from .settings import Settings, Params

DEFAULT_BASE_URL = "http://localhost:5000"
CHAT_ENDPOINT = f"{DEFAULT_BASE_URL}/api/v1/chat"


class DiscordBot(discord.Client):
    """Discord bot the UI uses"""

    character: str
    channel_whitelist: str
    channel_blacklist: str
    history: Dict
    do_greeting: bool
    active_channels: List[discord.TextChannel]
    params: Params
    tree: CommandTree

    def __init__(self, settings: Settings):
        self.character = settings.character
        self.starting_channel = settings.starting_channel
        self.channel_whitelist = settings.channel_whitelist
        self.channel_blacklist = settings.channel_blacklist
        self.history = {"internal": [], "visible": []}
        self.do_greeting = True
        self.active_channels = []
        self.params = settings.params
        self.mode = "instruct"

        super().__init__(intents=self.get_intents())
        self.tree = CommandTree(self)

    def is_channel_allowed(self, channel_name: str) -> bool:
        if channel_name in self.channel_blacklist:
            return False
        elif channel_name not in self.channel_whitelist:
            return False

        return True

    async def setup_hook(self):
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)

    async def set_up_commands(self):
        command_funcs = [
            {"name": "repeat",
             "func": self.repeat,
             "description": "Repeat a string"},
            {"name": "reset",
             "func": self.reset,
             "description": "Make me forget everything"}
        ]

        for command_func in command_funcs:
            command = discord.app_commands.Command(
                name=command_func.get("name", command_func["func"].__name__),
                callback=command_func["func"],
                description=command_func["description"])

            self.tree.add_command(command)
        await self.tree.sync()

    @staticmethod
    def get_intents() -> discord.Intents:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        return intents

    async def close(self):
        await self.bid_farewell()
        await super().close()

    async def bid_farewell(self):
        for channel in self.active_channels:
            await channel.send("Signing off...")

    @discord.app_commands.describe(
        message="Message to repeat"
    )
    async def repeat(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message(message)

    async def reset(self, interaction: discord.Interaction):
        self.history = {"internal": [], "visible": []}
        request = self.create_request("Say hi~", "Chat")
        bot_reply = self.get_bot_reply(self.poll_api(request))

        await interaction.response.send_message(bot_reply)

    async def on_ready(self):
        log.info("Connected to discord!")

        await self.set_up_commands()

        if self.do_greeting:
            await self.greet()
            self.do_greeting = False

    async def greet(self):
        if not self.starting_channel:
            return
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
            if not self.is_channel_allowed(channel.name):
                continue
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
                and self.is_name_in_message(message) \
                and self.is_channel_allowed(message.channel.name):
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
        starting_channel = self.starting_channel
        for guild in self.guilds:
            channel: discord.TextChannel
            for channel in guild.channels:
                if channel.name == starting_channel:
                    return channel

    def create_request(self,
                       message: str,
                       display_name: str):
        base_request = self.params.to_dict()
        base_request["user_input"] \
            = "{}: {}".format(display_name, message)
        log.info("Params: %s", yaml.dump(self.params.to_dict(), indent=2))
        if self.mode == "chat":
            return self.create_chat_request(base_request)
        elif self.mode == "instruct":
            return self.create_instruct_request(base_request)

    def create_instruct_request(self, base_request: Dict):
        request = base_request

        instruct_data = {}
        os.makedirs("instruct-contexts", exist_ok=True)
        with open(f"instruct-contexts/{self.character}.yaml", "r") as f:
            instruct_data = yaml.full_load(f.read())
        user_string = instruct_data["user_string"]
        bot_string = instruct_data["bot_string"]
        persona = instruct_data["context"] \
            .replace("USER ", user_string) \
            .replace("BOT ", bot_string)
        turn_template = instruct_data["turn_template"]

        # Prevent None values from going into the request
        for name, value in request.items():
            if value is None:
                request[name] = Params.defaults[name]

        request.update({
            'history': self.history,
            'mode': 'instruct',
            'your_name': "",
            'name1_instruct': user_string,  # Optional
            'name2_instruct': bot_string,  # Optional
            'context_instruct': persona,
            'turn_template': turn_template,
            'regenerate': False,
            '_continue': False,
            'do_sample': True,

            'seed': -1,
            'add_bos_token': True,
            'truncation_length': 2048,
            'ban_eos_token': False,
            'skip_special_tokens': True,
            'stopping_strings': []
        })

        return request

    def create_chat_request(self, base_request: Dict = {}):
        request = base_request

        # Prevent None values from going into the request
        for name, value in request.items():
            if value is None:
                request[name] = Params.defaults[name]

        request.update({
            'history': self.history,
            'mode': 'chat',
            'your_name': "",
            'name2': self.character,
            'regenerate': False,
            '_continue': False,
            'do_sample': True,

            'seed': -1,
            'add_bos_token': True,
            'truncation_length': 2048,
            'ban_eos_token': False,
            'skip_special_tokens': True,
            'stopping_strings': []
        })

        try:
            with open(f"characters/{self.character}.yaml") as f:
                character_context = yaml.full_load(f.read())["context"]
            request["context"] = character_context
        except OSError:
            log.error("Cannot find character %s! Going with defaults",
                      self.character)
            pass

        return request

    def poll_api(self, request: Dict) -> Dict:
        response = requests.post(CHAT_ENDPOINT, json=request)

        if response.status_code != 200:
            log.warning(f"Status code came back as {response.status_code}")

            return {}

        result: Dict = \
            response.json()['results'][0]['history']

        return result
