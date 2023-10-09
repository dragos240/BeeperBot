import asyncio
from pprint import pformat
from typing import Dict, Optional
import os

import discord
from discord.app_commands import CommandTree
from discord.errors import HTTPException
from gradio.external_utils import yaml
import requests

from .settings import Settings, Params
from .log import log

DEFAULT_BASE_URL = "http://localhost:5000"
CHAT_ENDPOINT = f"{DEFAULT_BASE_URL}/api/v1/chat"


class ChannelContainer:
    """A channel and its connected history for a bot

    Attributes:
        channel: The actual channel
        history: History for that channel
    """
    channel: discord.TextChannel
    history: Dict

    def __init__(self, channel):
        self.channel = channel
        self.history = self.new_history()

    def new_history(self):
        return {"internal": [], "visible": []}


class DiscordBot(discord.Client):
    """Discord bot the UI uses"""

    character: str
    character_path: str
    instruction_template: str
    channel_whitelist: str
    channel_blacklist: str
    do_greeting: bool
    active_channels: Dict[str, ChannelContainer]
    params: Params
    mode: str
    tree: CommandTree

    def __init__(self, settings: Settings):
        self.character = settings.character
        self.character_path = settings.character_path
        self.instruction_template = settings.instruction_template
        self.starting_channel = settings.starting_channel
        self.channel_whitelist = settings.channel_whitelist
        self.channel_blacklist = settings.channel_blacklist
        self.do_greeting = True
        self.active_channels = {}
        self.params = settings.params
        self.mode = settings.mode

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
        for channel_container in self.active_channels.values():
            await channel_container.channel.send("Signing off...")

    # Commands

    @discord.app_commands.describe(
        message="Message to repeat"
    )
    async def repeat(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message(message)

    async def reset(self, interaction: discord.Interaction):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return
        channel_container = ChannelContainer(channel)
        request = self.create_request("Say hi~",
                                      "Chat",
                                      channel_container.history)
        if channel.name is None:
            return
        self.active_channels[channel.name] = channel_container
        bot_reply = self.get_bot_reply(self.poll_api(request))

        await interaction.response.send_message(bot_reply)

    # Discord.py events

    async def on_ready(self):
        log.info("Connected to discord!")

        await self.set_up_commands()

        if self.do_greeting:
            await self.greet()
            self.do_greeting = False

    async def on_message(self, message: discord.Message):
        # Make sure message is in a TextChannel
        if not isinstance(message.channel, discord.TextChannel):
            return
        # Add channel to active_channels if we're mentioned and the channel
        # is not already in active_channels and not in the blacklist
        if (not self.is_active_channel(message.channel)
            and self.is_name_in_message(message)
                and self.is_channel_allowed(message.channel.name)):
            self.active_channels[message.channel.name] \
                = ChannelContainer(message.channel)
            log.info("I was pinged in %s. I can now talk there!",
                     message.channel.name)
        # Return if message starts with ignore string, or it's something
        # we already posted, or if it's not in active_channels
        if (message.author.id == self.id
            or message.clean_content.startswith("//")
                or not self.is_active_channel(message.channel)):
            return

        # Update nicks if necessary
        if self.character_path \
                and self.current_name != self.character:
            await self.update_character_async(self.character_path)

        # Send a response
        try:
            async with message.channel.typing():
                await self.handle_response(message)
        except discord.DiscordException as e:
            log.error(
                f"Exception while processing message: {message.clean_content}",
                exc=e)

    # Other methods

    async def greet(self):
        """Send a greeting message to the starting channel if it exists"""
        if not self.starting_channel:
            return
        channel = self.get_greeting_channel()
        channel_container = ChannelContainer(channel)
        request = self.create_request("Say hi~",
                                      "Chat",
                                      channel_container.history)
        self.active_channels[channel.name] = channel_container
        bot_greeting = self.get_bot_reply(self.poll_api(request))

        await channel.send(bot_greeting)

    @property
    def id(self) -> int:
        if self.user is not None:
            return self.user.id

        return -1

    @property
    def current_name(self) -> str:
        if self.user is not None:
            return self.user.name

        return ""

    def is_name_in_message(self, message: discord.Message) -> bool:
        if not isinstance(message.channel, discord.TextChannel):
            return False

        if self.character in message.clean_content.lower():
            return True

        return False

    def get_character_picture(self) -> Optional[bytes]:
        """Get the picture for the bot's name

        Returns:
            Optional[bytes]: The picture data if it exists
        """
        base_filename = self.character_path\
            .split("/")[-1] \
            .split(".")[0]
        for _, _, filenames in os.walk("characters"):
            for filename in filenames:
                fname_base, fname_ext = filename.split(".")
                if fname_base == base_filename \
                        and fname_ext in ["webp", "jpg", "jpeg", "png"]:
                    pic_path = f"characters/{filename}"
                    with open(pic_path, "rb") as f:
                        return f.read()

    async def update_character_async(self, char_path: str):
        """Update the bot's name and picture (if a match exists)

        Args:
            char_path (str): The path to the character file
        """
        self.character_path = char_path
        with open(self.character_path) as f:
            character = yaml.full_load(f.read())
        name = character["name"]
        # Don't set the character name if it's already set correctly
        if self.character != name:
            self.character = name

        if self.user is not None:
            if self.current_name != self.character:
                # Try to change username if it doesn't match character name
                log.info(f"Changing username to {self.character}")
                try:
                    await self.user.edit(username=self.character)
                except HTTPException:
                    log.error("Couldn't change username, too many requests")

            pic = self.get_character_picture()
            if pic is None:
                return
            log.info("Changing avatar")
            try:
                await self.user.edit(avatar=pic)
            except HTTPException:
                log.error("Couldn't change avatar, too many requests")

    def update_character(self, name: str):
        """Calls update_character_async in the event loop

        Args:
            name (str): The new name
        """
        asyncio.run_coroutine_threadsafe(
            self.update_character_async(name),
            self.loop)

    def is_active_channel(self,
                          channel: discord.TextChannel):
        for active_channel_name in self.active_channels.keys():
            if channel.name == active_channel_name:
                return True

        return False

    def get_bot_reply(self, response: Dict) -> str:
        bot_reply = ""
        if "internal" in response:
            bot_reply = response["internal"][-1][-1]

        return bot_reply

    def get_greeting_channel(self) -> discord.TextChannel:
        starting_channel = self.starting_channel
        for guild in self.guilds:
            for channel in guild.channels:
                if not isinstance(channel, discord.TextChannel):
                    continue
                if channel.name == starting_channel:
                    return channel

        raise Exception("Could not get greeting channel")

    def sanitize_context(self,
                         name: str,
                         context: str) -> str:
        # Remove any unicode characters that may mess with parsing
        context = context.encode("ascii", "ignore").decode()
        # Replace placeholders and newlines
        context = (context
            .replace("{{user}}'s", "your")
            .replace("{{user}}", "you")
            .replace("{{char}}", name)
            .replace("\\n", " ")
            )

        return context


    def sanitize_turn_template(self,
                               name: str,
                               turn_template: str):
        return turn_template.replace("<|bot-message|>",
                                     f"{name}: <|bot-message|>")

    # Ooba API related methods

    async def handle_response(self, message: discord.Message):
        if not isinstance(message.channel, discord.TextChannel):
            return
        channel_container = self.active_channels[message.channel.name]
        request = self.create_request(
            message.clean_content,
            message.author.display_name,
            channel_container.history)
        response = self.poll_api(request)

        log.info("Params: %s", pformat(self.params.to_dict()))

        bot_reply = self.get_bot_reply(response)
        await message.reply(bot_reply, mention_author=False)
        channel_container.history.update(response)

    def create_request(self,
                       message: str,
                       display_name: str,
                       history: Dict) -> Dict:
        base_request = self.params.to_dict()
        base_request.update({"user_input": "{}: {}"
                             .format(display_name, message),
                             "history": history})
        log.info("Params: %s", yaml.dump(self.params.to_dict(), indent=2))
        if self.mode == "chat":
            return self.create_chat_request(base_request)
        else:
            return self.create_instruct_request(base_request)

    def create_instruct_request(self,
                                base_request: Dict):
        request = base_request

        character = {}
        with open(self.character_path, "r") as f:
            character = yaml.full_load(f.read())
        name = character.get("name", self.character)
        instruction_template = {}
        with open(f"instruction-templates/{self.instruction_template}.yaml",
                  "r") as f:
            instruction_template = yaml.full_load(f.read())
        user_string = instruction_template["user"]
        bot_string = instruction_template["bot"]
        turn_template = self.sanitize_turn_template(
            name,
            instruction_template["turn_template"])
        persona = self.sanitize_context(name, character["context"])

        # Prevent None values from going into the request
        for name, value in request.items():
            if value is None:
                request[name] = Params.defaults[name]

        request.update({
            'mode': 'instruct',
            'name1_instruct': user_string,  # Optional
            'name2_instruct': bot_string,  # Optional
            'context_instruct': persona,
            'turn_template': turn_template,
        })

        return request

    def create_chat_request(self,
                            base_request: Dict):
        request = base_request

        # Prevent None values from going into the request
        for name, value in request.items():
            if value is None:
                request[name] = Params.defaults[name]

        request.update({
            'mode': 'chat',
            'your_name': "",
            'name2': self.character,
        })

        try:
            with open(self.character_path) as f:
                character_context = yaml.full_load(f.read())["context"]
            request["context"] = character_context
        except OSError:
            log.error(
                f"Cannot find character {self.character}! Going with defaults")
            pass

        return request

    def poll_api(self, request: Dict) -> Dict:
        response = requests.post(CHAT_ENDPOINT, json=request)

        if response.status_code != 200:
            log.warn(f"Status code came back as {response.status_code}")

            return {}

        result: Dict = response.json()['results'][0]['history']

        return result
