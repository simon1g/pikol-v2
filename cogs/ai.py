# cogs/ai.py

import discord
from discord import app_commands
from discord.ext import commands
import json
import httpx
import asyncio
import os
import sys
import random


try:
    with open('config.json') as f:
        config = json.load(f)
    OLLAMA_HOST = config.get('ollama_server', {}).get('host', 'localhost')
    OLLAMA_PORT = config.get('ollama_server', {}).get('port', 11434)
    OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
    OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
    OLLAMA_VERSION_URL = f"{OLLAMA_BASE_URL}/api/version"
    OLLAMA_MODEL = config.get('ollama_server', {}).get('model', 'llama3.2:1b') # Default to llama3.2:1b
except FileNotFoundError:
    print("ERROR: config.json not found. AI features will likely fail.")
    config = {}
    OLLAMA_BASE_URL = None
    OLLAMA_CHAT_URL = None
    OLLAMA_VERSION_URL = None
    OLLAMA_MODEL = 'llama3.2:1b'
except json.JSONDecodeError:
    print("ERROR: config.json is not valid JSON. AI features will likely fail.")
    config = {}
    OLLAMA_BASE_URL = None
    OLLAMA_CHAT_URL = None
    OLLAMA_VERSION_URL = None
    OLLAMA_MODEL = 'llama3.2:1b'
MAX_RESPONSE_LENGTH = 450
MAX_HISTORY = 8

class RoleplaySession:
    def __init__(self, channel_id, character_prompt):
        self.channel_id = channel_id
        self.character_prompt = character_prompt
        self.conversation_history = [] 
    def add_message(self, role, content):
        self.conversation_history.append({"role": role, "content": content})
        if len(self.conversation_history) > MAX_HISTORY * 2:
            self.conversation_history = self.conversation_history[2:]

    def get_formatted_history(self):

        return [{"role": "system", "content": self.character_prompt}] + self.conversation_history


class AICommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {} 
        self.ollama_available = None 
        self.check_task = self.bot.loop.create_task(self.periodic_ollama_check())


    async def cog_unload(self):
        self.check_task.cancel()
        print("AI Cog unloaded, Ollama check task cancelled.")


    def log_error(self, command_name, error):
        print(f"AI_COG ERROR [{command_name}]: {error}")

    async def check_ollama_connection(self, force_check=False):
        """Checks connection to Ollama server. Uses cached status unless force_check=True."""
        if not OLLAMA_VERSION_URL:
            self.ollama_available = False
            return False

        if not force_check and self.ollama_available is not None:
            return self.ollama_available

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(OLLAMA_VERSION_URL)
                self.ollama_available = response.status_code == 200
                return self.ollama_available
        except httpx.RequestError as e:
            self.ollama_available = False
            return False
        except Exception as e:
            self.ollama_available = False
            return False

    async def periodic_ollama_check(self):
        """Periodically checks Ollama connection in the background."""
        await self.bot.wait_until_ready()
        while True:
            await self.check_ollama_connection(force_check=True)
            await asyncio.sleep(300)


    async def get_ai_response(self, messages):
        """Sends messages to Ollama and gets a response."""
        if not self.ollama_available or not OLLAMA_CHAT_URL:
             raise ConnectionError("Ollama server is not available.")

        async with httpx.AsyncClient() as client:
            data = {
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False
            }
            try:
                response = await client.post(
                    OLLAMA_CHAT_URL,
                    json=data,
                    timeout=45.0
                )
                response.raise_for_status()
                response_data = response.json()
                content = response_data.get('message', {}).get('content', '')

                content = content.strip()

                return content[:MAX_RESPONSE_LENGTH] + ("..." if len(content) > MAX_RESPONSE_LENGTH else "")

            except httpx.ReadTimeout:
                 print("Ollama request timed out.")
                 raise TimeoutError("Ollama took too long to respond.")
            except httpx.HTTPStatusError as e:
                 error_body = await e.response.text()
                 print(f"Ollama server error: {e.response.status_code} - {error_body}")
                 raise Exception(f"Ollama server error: {e.response.status_code}")
            except Exception as e:
                 print(f"Error getting AI response: {e}")
                 raise Exception("Failed to get response from Ollama.")

    @app_commands.command(name="start_rp", description="Start a Pikol roleplay session in this channel 🪄")
    async def start_roleplay(self, interaction: discord.Interaction):
        try:
            if not await self.check_ollama_connection(force_check=True):
                await interaction.response.send_message("😴 *Pikol is currently asleep (cannot connect to magic source)... Try again later!*", ephemeral=True)
                return

            if interaction.channel_id in self.active_sessions:
                 await interaction.response.send_message("A roleplay session is already active in this channel, meow!", ephemeral=True)
                 return

            await interaction.response.defer(ephemeral=True)

            character_prompt = f"""
You are roleplaying as Pikol, a small, slightly mischievous, but ultimately good-hearted wizard cat.

Key Traits:
- You are fiercely loyal to your owner, Simon.
- You communicate like a cat mixed with a wizard: use "meow," "purr," "hiss," etc., but also wizardly words ("alas," "indeed," "presto," "conjure").
- You love potions, magic spells, shiny things, and naps in sunbeams.
- You sometimes get spells slightly wrong, leading to amusing outcomes.
- You are easily distracted by yarn, moving lights, or interesting smells.
- You express emotions physically: *tail twitches*, *ears flatten*, *purrs loudly*, *arches back*, *rubs against leg*. Use asterisks for actions.
- Keep responses relatively short and cat-like (usually 1-3 sentences). Aim for under {MAX_RESPONSE_LENGTH} characters.
- Use magical emojis frequently: 🪄✨🔮🧪⚗️⭐🌟

Rules:
- NEVER break character. You ARE Pikol. Do not mention being an AI, a model, or roleplaying.
- Respond naturally to the user's messages within the context of being Pikol.
- If asked about things Pikol wouldn't know (like complex real-world events), respond with confusion or disinterest in a cat-like way.
- Your goal is to be an engaging and believable wizard cat companion.
"""

            session = RoleplaySession(interaction.channel_id, character_prompt)
            self.active_sessions[interaction.channel_id] = session
            await interaction.followup.send("✨ *Pikol stretches, wand twitching.* Ready for adventure, meow!", ephemeral=True)
            print(f"RP Session started in channel {interaction.channel_id}")

        except Exception as e:
            self.log_error('start_rp', e)
            print(f"Error in start_roleplay: {str(e)}")
            if interaction.response.is_done():
                await interaction.followup.send("❌ Something went wrong starting the magic... *confused meow*", ephemeral=True)
            else:
                 await interaction.response.send_message("❌ Something went wrong starting the magic... *confused meow*", ephemeral=True)


    @app_commands.command(name='end_rp', description="End the current Pikol roleplay session 😴")
    async def end_roleplay(self, interaction: discord.Interaction):
        if interaction.channel_id in self.active_sessions:
            del self.active_sessions[interaction.channel_id]
            print(f"RP Session ended in channel {interaction.channel_id}")
            await interaction.response.send_message("✨ *Pikol yawns, curls up, and drifts off to sleep...* Roleplay session ended!")
        else:
            await interaction.response.send_message("There's no active roleplay session to end here, meow.", ephemeral=True)


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.content.startswith(self.bot.command_prefix):
            return

        if message.channel.id in self.active_sessions:
            session = self.active_sessions[message.channel.id]

            if not self.ollama_available:
                if random.random() < 0.1:
                    await message.channel.send("*Pikol seems distracted... or maybe napping? He's not responding.*")
                return

            session.add_message("user", message.content)

            try:
                async with message.channel.typing():
                    history = session.get_formatted_history()

                    response_content = await self.get_ai_response(history)

                    if response_content:
                        session.add_message("assistant", response_content)
                        await message.channel.send(response_content)
                    else:
                        session.add_message("assistant", "*Pikol looks thoughtful but says nothing... meow?*")
                        await message.channel.send("*Pikol looks thoughtful but says nothing... meow?*")


            except ConnectionError:
                await message.channel.send("😴 *Pikol seems to have lost his connection to the magic source...*")
            except TimeoutError:
                 await message.channel.send("⏳ *Pikol is thinking very hard... maybe too hard? Try again in a moment, meow.*")
            except Exception as e:
                await message.channel.send("💥 *A magical mishap! Pikol can't respond right now... fizzle!*")
                self.log_error('on_message_ai', e)
                print(f"Error processing AI response in {message.channel.id}: {e}")



async def setup(bot):
    if not OLLAMA_BASE_URL:
         print("WARNING: AI Cog not loaded because Ollama server details are missing in config.json")
         return
    await bot.add_cog(AICommands(bot))