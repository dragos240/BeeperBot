from time import sleep
from typing import Optional
import asyncio
from threading import Thread

from ..bot import DiscordBot
from ..settings import Settings
from ..log import log

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
