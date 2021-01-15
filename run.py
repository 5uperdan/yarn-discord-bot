import os

import discord
from dotenv import load_dotenv
from discord.ext import commands
import asyncio
from multiprocessing import Lock
from suggestion import Suggestion


class YarnClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        load_dotenv()

        self.BOT_COMMANDS = {
            "!start": self.on_message_start,
            "!help": self.on_message_help,
        }

        self.GUILD_ID = int(os.getenv("GUILD_ID"))
        self.YARN_CHAN = int(os.getenv("YARN_CHAN"))
        self.BOT_ID = int(os.getenv("BOT_ID"))
        self.MAX_ROUNDS = int(os.getenv("MAX_ROUNDS"))

        self.guild = None
        self.round_number = 0
        self.all_rounds = []  # a list GameRounds

        self.current_round = None  # a list of suggestions
        self.round_lock = Lock()

        # self.bg_task = self.loop.create_task(self.my_background_task())

    async def on_message(self, msg):
        """ handles all messages read by the bot and diverts to correct subs """
        # ignore messages except in yarn channel or DMs
        if (
            msg.channel.id != self.YARN_CHAN
            and msg.channel.type != discord.enums.ChannelType.private
        ):
            return

        # ignore bot's own messages
        if msg.author.id == self.BOT_ID:
            return

        # if message is a bot command, send to correct handler
        if msg.content in self.BOT_COMMANDS:
            on_message_func = self.BOT_COMMANDS[msg.content]
            await on_message_func(msg)
            return

        # if message is in yarn chan, chastise user
        if msg.channel.id == self.YARN_CHAN:
            await msg.channel.send(
                "Don't type here, you need to DM me your suggestions."
            )

        # handle DMs as a suggestion if the round has begun
        if msg.channel.type == discord.enums.ChannelType.private:
            if self.current_round is None:
                await msg.channel.send("Game has not started yet.")
            else:
                await self.handle_suggestion(msg)

    async def on_ready(self):
        """ handles ready event fired when bot is connected and listening """
        self.guild = discord.utils.get(self.guilds, id=self.GUILD_ID)
        print(f"{self.user} has connected to {self.guild.name}")

    async def on_message_help(self, msg):
        with open("help.md", "r") as reader:
            await msg.channel.send(reader.read())

    async def on_message_start(self, msg):
        """ starts a game """
        if msg.author.display_name != "Superdan":
            await msg.channel.send("Fuck you, you ain't no Superdan!")
        else:
            if msg.author.id != 97032397584859136:
                await msg.channel.send("Fuck you, you ain't the real Superdan!")
            else:
                await self.start_game(msg)

    async def start_game(self, msg):
        await msg.channel.send("New game will be started")
        self.all_rounds = []
        self.current_round = []
        await self.get_channel(self.YARN_CHAN).send(
            "It was a dark and rainy night at stratlan when... "
        )

    async def handle_suggestion(self, msg):
        """  """
        with self.round_lock:
            # check for duplicate text
            if msg.content in [sug.content for sug in self.current_round]:
                await msg.channel.send("Your suggestion has already been suggested!")
                return

            # check for duplicate author
            if msg.author.id in [sug.author_id for sug in self.current_round]:
                await msg.channel.send("You have already submitted a suggestion!")
                return

            bot_relay_msg = await self.get_channel(self.YARN_CHAN).send(
                f"{1 + len(self.current_round)}. {msg.content}"
            )

            self.current_round.append(
                Suggestion(
                    author_id=msg.author.id,
                    author_name=msg.author.display_name,
                    content=msg.content,
                    bot_msg_uid=bot_relay_msg.id,
                )
            )

    async def my_background_task(self):
        await self.wait_until_ready()
        counter = 0
        channel = self.get_channel(1234567)  # channel ID goes here
        while not self.is_closed():
            counter += 1
            await channel.send(counter)
            await asyncio.sleep(60)  # task runs every 60 seconds


TOKEN = os.getenv("DISCORD_TOKEN")
client = YarnClient()
client.run(TOKEN)
