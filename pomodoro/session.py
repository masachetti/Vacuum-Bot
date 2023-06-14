import math
import os
from datetime import datetime, timedelta

import discord
from discord import Interaction
from discord.ext import commands, tasks

from pomodoro.models import PomodoroState, PomodoroSettings, AlarmOptions


def plural(quantity: int):
    return 's' if quantity > 1 else ''


def create_alarm_sound_path(alarm: AlarmOptions):
    return os.path.join(os.path.dirname(__file__), f"../assets/{alarm.name}.mp3")


def create_voice_sound_path(state: PomodoroState):
    return os.path.join(os.path.dirname(__file__), f"../assets/{state.name}.mp3")


class PomodoroSession:
    def __init__(self, bot: commands.Bot, interaction: Interaction, settings: PomodoroSettings):
        self.interaction = interaction
        self.bot = bot
        self.user = interaction.user
        self.channel = interaction.user.voice.channel
        self.state: PomodoroState = PomodoroState.Working
        self.paused = False
        self.settings: PomodoroSettings = settings
        self.cycles = 0
        self.remaining_time = None
        self.started_at = None
        self.created_at = None
        self.finish_session_callback = None
        self._next_state_timestamp = None

    async def play_alarm(self):
        vc = await self.channel.connect()

        async def after_play():
            await vc.disconnect()

        def disconnect(error):
            self.bot.loop.create_task(after_play())

        def play_voice(error):
            if not self.settings.use_voices:
                return disconnect(error)
            vc.play(
                discord.FFmpegPCMAudio(create_voice_sound_path(self.state)),
                after=disconnect)

        vc.play(
            discord.FFmpegPCMAudio(create_alarm_sound_path(self.settings.alarm_sound)),
            after=play_voice)

    async def notify_channel(self):
        await self.play_alarm()
        if self.state == PomodoroState.Working:
            await self.channel.send(
                content=f":tomato: Iniciando estudos! ({self.settings.work_time} minuto{plural(self.settings.work_time)}!)")
        elif self.state == PomodoroState.Break:
            await self.channel.send(
                content=f":tomato: Intervalo ... ({self.settings.break_time} minuto{plural(self.settings.break_time)}!)")
        elif self.state == PomodoroState.LongBreak:
            await self.channel.send(
                content=f":tomato: Intervalo longo ... ({self.settings.long_break_time} minuto{plural(self.settings.long_break_time)}!)")

    async def start(self):
        self.state = PomodoroState.Working
        self._next_state_timestamp = datetime.now() + timedelta(minutes=self.settings.work_time)
        self.update.start()
        await self.notify_channel()

    async def skip(self, interaction: Interaction):
        await interaction.response.send_message(content=f":tomato: {interaction.user.mention} avançou a sessão.")
        self.advance_state()
        self.update_timestamp()
        await self.notify_channel()

    def pause(self):
        if not self.paused:
            self.paused = True
            self.remaining_time = self._next_state_timestamp - datetime.now()

    def resume(self):
        if self.paused:
            self.paused = False
            self._next_state_timestamp = datetime.now() + self.remaining_time

    def get_remaining_time(self):
        remaining_time = (self._next_state_timestamp - datetime.now()).total_seconds()
        minutes = math.floor(remaining_time / 60)
        seconds = math.floor(remaining_time % 60)
        return minutes, seconds

    def advance_state(self):
        if self.paused:
            return
        if self.state == PomodoroState.Working:
            if ((self.cycles + 1) % (self.settings.n_breaks + 1)) == 0:
                self.state = PomodoroState.LongBreak
                return
            self.state = PomodoroState.Break
            return
        self.cycles += 1
        self.state = PomodoroState.Working
        return

    def update_timestamp(self):
        if self.state == PomodoroState.Working:
            self._next_state_timestamp = datetime.now() + timedelta(minutes=self.settings.work_time)
        elif self.state == PomodoroState.Break:
            self._next_state_timestamp = datetime.now() + timedelta(minutes=self.settings.break_time)
        elif self.state == PomodoroState.LongBreak:
            self._next_state_timestamp = datetime.now() + timedelta(minutes=self.settings.long_break_time)

    @tasks.loop(seconds=1)
    async def update(self):
        await self.check_channel()
        if self.paused:
            return
        now = datetime.now()
        if now >= self._next_state_timestamp:
            self.advance_state()
            self.update_timestamp()
            await self.notify_channel()

    async def check_channel(self):
        if not self.channel.members:
            self.update.stop()
            if callable(self.finish_session_callback):
                await self.finish_session_callback(self.channel)
