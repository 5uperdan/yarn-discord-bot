import os

import discord
from dotenv import load_dotenv
from discord.ext import commands
import asyncio
from multiprocessing import Lock
from suggestion import Suggestion
from random import choice


class YarnClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.BOT_COMMANDS = {
            "!start": self.on_message_start,
            "!help": self.on_message_help,
        }

        load_dotenv()

        self.GUILD_ID = int(os.getenv("GUILD_ID"))
        self.YARN_CHAN = int(os.getenv("YARN_CHAN"))
        self.OTHER_BROADCAST_CHAN = int(os.getenv("OTHER_BROADCAST_CHAN"))
        self.BOT_ID = int(os.getenv("BOT_ID"))
        self.MAX_ROUNDS = int(os.getenv("MAX_ROUNDS"))
        self.ROUND_TIMER = float(os.getenv("ROUND_TIMER"))
        self.MIN_UNIQUE_MSGS = int(os.getenv("MIN_UNIQUE_MSGS"))
        self.START_TEXT = "It was a dark and rainy night at lan when... "

        self.guild = None
        self.round_number = 0

        self.winning_suggestions = []  # a list GameRounds
        self.overall_scores = {}  # author -> number of round wins
        self.current_round = None  # a list of suggestions
        self.round_lock = Lock()

        self.bg_task = None

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
                # if we've reached cap, start timer
                if (
                    len(self.current_round) >= self.MIN_UNIQUE_MSGS
                    and self.bg_task is None
                ):
                    self.bg_task = self.loop.create_task(self.begin_round_end_timer())

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
        self.winning_suggestions = []
        self.round_number = 0
        await self.start_round()

    async def start_round(self):
        self.current_round = []
        self.round_number += 1

        await self.get_channel(self.YARN_CHAN).send(await self.get_story_text())

        await self.get_channel(self.OTHER_BROADCAST_CHAN).send(
            await self.get_story_text()
        )

        await self.get_channel(self.OTHER_BROADCAST_CHAN).send(
            f"-- DM me with !help or check out the #yarn-game channel for details --"
        )

        if self.round_number > self.MAX_ROUNDS:
            await self.end_game()
            return

    async def handle_suggestion(self, msg):
        """  """
        with self.round_lock:
            # check for duplicate text
            if msg.content in [sug.content for sug in self.current_round]:
                await msg.channel.send("Your suggestion has already been suggested!")
                return

            # check for duplicate author
            if msg.author in [sug.author for sug in self.current_round]:
                await msg.channel.send("You have already submitted a suggestion!")
                return

            bot_relay_msg = await self.get_channel(self.YARN_CHAN).send(
                f"--- \n {1 + len(self.current_round)}. {msg.content} \n ---"
            )

            self.current_round.append(
                Suggestion(
                    author=msg.author,
                    content=msg.content,
                    bot_msg_uid=bot_relay_msg.id,
                )
            )

    async def begin_round_end_timer(self):
        await self.wait_until_ready()
        counter = 0
        channel = self.get_channel(self.YARN_CHAN)  # channel ID goes here
        await channel.send(
            f"{self.MIN_UNIQUE_MSGS} or more suggestions to continue the story have been made. The round will end in {self.ROUND_TIMER} minutes, get voting!"
        )
        await asyncio.sleep(60 * self.ROUND_TIMER)

        await self.process_votes()
        await self.start_round()

        self.bg_task = None

    async def process_votes(self):
        # GET VOTES AND CHECK DECLARE ROUND WINNER
        # in the event of tie, award points to both, but randomly choose one continuation
        votes = {}  # suggestion -> vote count
        highest_count = 0

        for suggestion in self.current_round:
            bot_msg = await self.get_channel(self.YARN_CHAN).fetch_message(
                suggestion.bot_msg_uid
            )
            for reaction in bot_msg.reactions:
                if reaction.emoji == "👍":
                    count = reaction.count
                    # discard a vote if user voted for their own suggestion
                    users = await reaction.users().flatten()
                    if suggestion.author in users:
                        count -= 1
                    # only store the votes for the suggestion if above 0
                    if count > 0:
                        votes[suggestion] = count
                        if highest_count < count:
                            highest_count = count

        round_winning_suggestions = []

        for suggestion, count in votes.items():
            if count == highest_count:
                # add 1 to all overall scores for each winning author
                self.overall_scores[suggestion.author] = (
                    self.overall_scores.get(suggestion.author, 0) + 1
                )
                # keep track of the round winning suggestions
                round_winning_suggestions.append(suggestion)

        # if nobody voted for anything, we just pick a suggestion at random
        if len(round_winning_suggestions) == 0:
            await self.get_channel(self.YARN_CHAN).send(
                f"It looks like you guys didn't vote for anything, so i've picked a suggestion at random."
            )
            round_winning_suggestions.append(choice(self.current_round))
        else:
            await self.get_channel(self.YARN_CHAN).send(
                f"The round winners were {[str(suggestion.author) for suggestion in round_winning_suggestions]}"
            )

        # append one of the winning suggestions from the round
        self.winning_suggestions.append(choice(round_winning_suggestions))

    async def end_game(self):
        # count up and declare overall winner
        final_scores = []
        for author, score in self.overall_scores.items():
            final_scores.append(f"{str(author)}: {score}, ")

        await self.get_channel(self.YARN_CHAN).send(
            f"The final scores for that game were {final_scores}."
        )

    async def get_story_text(self):
        story_text = "--- \n"
        story_text += self.START_TEXT
        for suggestion in self.winning_suggestions:
            story_text += f"{suggestion.content} "
        story_text += "\n ---"

        return story_text


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
client = YarnClient()
client.run(TOKEN)
