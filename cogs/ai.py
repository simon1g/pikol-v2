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
import time


with open('config.json') as f:
    config = json.load(f)
OLLAMA_HOST = config.get('ollama_server', {}).get('host', 'localhost')
OLLAMA_PORT = config.get('ollama_server', {}).get('port', 11434)
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_VERSION_URL = f"{OLLAMA_BASE_URL}/api/version"
OLLAMA_MODEL = config.get('ollama_server', {}).get('model', 'llama3.2:1b')
MAX_RESPONSE_LENGTH = 450
MAX_HISTORY = 8
SESSION_TIMEOUT = 1800

class RoleplaySession:
    def __init__(self, channel_id, character_prompt):
        self.channel_id = channel_id
        self.character_prompt = character_prompt
        self.conversation_history = [] # will store dicts: {"role": role, "content": content, "user_name": name}
        self.last_activity = time.time()

    def update_activity(self):
        """Update the last activity timestamp"""
        self.last_activity = time.time()

    def is_expired(self):
        """Check if the session has expired"""
        return (time.time() - self.last_activity) > SESSION_TIMEOUT

    def add_message(self, role, content, user_name=None):
        """Adds a message to the history, including user_name if role is 'user'."""
        self.update_activity()
        message_data = {"role": role, "content": content}
        if role == "user" and user_name:
            message_data["user_name"] = user_name

        self.conversation_history.append(message_data)
        if len(self.conversation_history) > MAX_HISTORY * 2:
            self.conversation_history = self.conversation_history[2:]

    def get_formatted_history(self):
        """Formats history for the Ollama API, prepending user names."""
        formatted = [{"role": "system", "content": self.character_prompt}]
        for msg in self.conversation_history:
            if msg["role"] == "user":
                user_name = msg.get("user_name", "User") # fallback if name is missing
                formatted.append({
                    "role": "user",
                    "content": f"{user_name}: {msg['content']}"
                })
            else:
                formatted.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        return formatted


class AICommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {}
        self.ollama_available = None
        self.check_task = self.bot.loop.create_task(self.periodic_ollama_check())
        self.cleanup_task = self.bot.loop.create_task(self.cleanup_expired_sessions())

    async def cog_unload(self):
        self.check_task.cancel()
        self.cleanup_task.cancel()
        print("AI Cog unloaded, background tasks cancelled.")

    async def cleanup_expired_sessions(self):
        """Periodically clean up expired sessions"""
        await self.bot.wait_until_ready()
        while True:
            expired_channels = []
            for channel_id, session in self.active_sessions.items():
                if session.is_expired():
                    expired_channels.append(channel_id)
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        await channel.send("*Pikol yawns and curls up for a nap.* The roleplay session has expired due to inactivity. ✨")
            
            for channel_id in expired_channels:
                del self.active_sessions[channel_id]
            
            await asyncio.sleep(300)

    async def check_ollama_connection(self, force_check=False):
        if not OLLAMA_VERSION_URL:
            self.ollama_available = False
            return False

        if not force_check and self.ollama_available is not None:
            return self.ollama_available

        if OLLAMA_BASE_URL is None:
            self.ollama_available = False
            return False

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(OLLAMA_VERSION_URL)
                self.ollama_available = response.status_code == 200
                if self.ollama_available:
                    pass
                else:
                    print(f"Ollama connection check failed (Status: {response.status_code}) Target: {OLLAMA_VERSION_URL}")
                return self.ollama_available
        except httpx.RequestError as e:
            if self.ollama_available is not False:
                 print(f"Ollama connection check failed: {e}")
            self.ollama_available = False
            return False
        except Exception as e:
            print(f"Unexpected error during Ollama connection check: {e}")
            self.ollama_available = False
            return False

    async def periodic_ollama_check(self):
        await self.bot.wait_until_ready()
        while True:
            old_status = self.ollama_available
            await self.check_ollama_connection(force_check=True)
            if old_status is False and self.ollama_available is True:
                print("Ollama connection re-established.")
            await asyncio.sleep(300)

    async def get_ai_response(self, messages):
        if not self.ollama_available or not OLLAMA_CHAT_URL:
             raise ConnectionError("Ollama server is not available.")

        async with httpx.AsyncClient() as client:
            data = {
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {
                     "temperature": 0.7,
                     "num_predict": MAX_RESPONSE_LENGTH
                }
            }
            try:
                response = await client.post(
                    OLLAMA_CHAT_URL,
                    json=data,
                    timeout=60.0
                )
                response.raise_for_status()
                response_data = response.json()
                content = response_data.get('message', {}).get('content', '')
                content = content.strip()

                return content[:MAX_RESPONSE_LENGTH] + ("..." if len(content) > MAX_RESPONSE_LENGTH else "")

            except httpx.ReadTimeout:
                 print(f"Ollama request timed out after 60 seconds for model {OLLAMA_MODEL}.")
                 raise TimeoutError("Ollama took too long to respond.")
            except httpx.ConnectError:
                 print(f"Could not connect to Ollama server at {OLLAMA_CHAT_URL}.")
                 self.ollama_available = False
                 raise ConnectionError("Failed to connect to Ollama server.")
            except httpx.HTTPStatusError as e:
                 error_body = "<Could not decode error body>"
                 try:
                     error_body = await e.response.text()
                 except Exception:
                     pass
                 print(f"Ollama server error: {e.response.status_code} - {error_body}. Model: {OLLAMA_MODEL}")
                 if e.response.status_code == 404 and "model" in error_body.lower() and ("not found" in error_body.lower() or "doesn't exist" in error_body.lower()):
                     raise ValueError(f"Model '{OLLAMA_MODEL}' not found on the Ollama server.")
                 raise Exception(f"Ollama server error: {e.response.status_code}")
            except Exception as e:
                 print(f"Unexpected error getting AI response: {type(e).__name__} - {e}")
                 raise Exception("An unexpected error occurred while communicating with Ollama.")


    @app_commands.command(name="start_rp", description="Start a pikol roleplay session in this channel 🪄")
    async def start_roleplay(self, interaction: discord.Interaction):
        """Starts a Pikol roleplay session."""
        try:
            if not await self.check_ollama_connection(force_check=True):
                await interaction.response.send_message(f"*Pikol seems to be napping deeply...* (Ollama server at {OLLAMA_BASE_URL} is not responding).", ephemeral=True)
                return

            if interaction.channel_id in self.active_sessions:
                 await interaction.response.send_message("A roleplay session is already active in this channel, meow!", ephemeral=True)
                 return

            await interaction.response.defer(ephemeral=True)
            starter_user = interaction.user 
            starter_user_name = starter_user.display_name
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
- The user's name will appear before their message (e.g., 'Simon: Hello!'). Try to sometimes use their name in your replies naturally, like 'Hmm, Simon, that sounds interesting!' or 'Watch this spell, {{{{user_name}}}}!' (Replace {{{{user_name}}}} with the actual name).

Rules:
- NEVER break character. You ARE Pikol. Do not mention being an AI, a model, or roleplaying.
- Respond naturally to the user's messages within the context of being Pikol.
- If asked about things Pikol wouldn't know (like complex real-world events), respond with confusion or disinterest in a cat-like way.
- Your goal is to be an engaging and believable wizard cat companion.
"""

            session = RoleplaySession(interaction.channel_id, character_prompt)
            self.active_sessions[interaction.channel_id] = session
            await interaction.followup.send("*Pikol stretches, wand twitching.* Hi there! What magic shall we conjure today?")
            print(f"RP Session started in channel {interaction.channel_id} by {starter_user_name} (ID: {starter_user.id})")

        except ValueError as e:
             self.log_error('start_rp', e)
             print(f"Configuration error in start_roleplay: {str(e)}")
             msg = f"Failed to start roleplay. {str(e)}. Please check the `model` in `config.json`."
             if not interaction.response.is_done():
                  await interaction.response.send_message(msg, ephemeral=True)
             else:
                  try:
                      await interaction.edit_original_response(content=msg)
                  except discord.NotFound:
                      await interaction.followup.send(msg, ephemeral=True)

        except Exception as e:
            self.log_error('start_rp', e)
            print(f"Error in start_roleplay: {type(e).__name__} - {str(e)}")
            msg = "Something went wrong starting the magic... *confused meow*"
            if not interaction.response.is_done():
                 await interaction.response.send_message(msg, ephemeral=True)
            else:
                  try:
                      await interaction.edit_original_response(content=msg)
                  except discord.NotFound:
                      await interaction.followup.send(msg, ephemeral=True)


    @app_commands.command(name='end_rp', description="End the current pikol roleplay session")
    async def end_roleplay(self, interaction: discord.Interaction):
        if interaction.channel_id in self.active_sessions:
            del self.active_sessions[interaction.channel_id]
            ender_user_name = interaction.user.display_name
            print(f"RP Session ended in channel {interaction.channel_id} by {ender_user_name}")
            await interaction.response.send_message("*Pikol yawns, waves his tiny wand fizzling out sparks, and curls up for a nap.* Until next time! Roleplay ended. ✨")
        else:
            await interaction.response.send_message("There's no active roleplay session to end here...", ephemeral=True)


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        prefix = await self.bot.get_prefix(message) if callable(getattr(self.bot, "get_prefix", None)) else getattr(self.bot, "command_prefix", None)
        is_command = False
        if prefix:
            if isinstance(prefix, str) and message.content.startswith(prefix):
                is_command = True
            elif isinstance(prefix, (list, tuple)) and any(message.content.startswith(p) for p in prefix):
                is_command = True

        if message.author.bot or is_command or message.channel.id not in self.active_sessions:
            return

        session = self.active_sessions[message.channel.id]

        if session.is_expired():
            del self.active_sessions[message.channel.id]
            await message.channel.send("*Pikol yawns, waves his tiny wand fizzling out sparks, and curls up for a nap.* The roleplay session has expired due to inactivity. ✨")
            return

        if not self.ollama_available:
            if random.random() < 0.2:
                await message.channel.send("*Pikol seems lost in thought* The magical connection is weak? (Ollama unavailable)")
            return

        user_name = message.author.display_name
        session.add_message("user", message.content, user_name=user_name)

        try:
            async with message.channel.typing():
                history = session.get_formatted_history()
                response_content = await self.get_ai_response(history)

                if response_content:
                    session.add_message("assistant", response_content)
                    await message.channel.send(response_content)
                else:
                    empty_responses = [
                        "*Pikol just blinks slowly...*",
                        "*Pikol chases his tail for a moment, forgetting the question.*",
                        "*Pikol sniffs the air curiously but says nothing.*",
                        "Meow? *tilts head*",
                    ]
                    fallback_response = random.choice(empty_responses)
                    session.add_message("assistant", fallback_response)
                    await message.channel.send(fallback_response)

        except ConnectionError as e:
            await message.channel.send(f"*Pikol's magic fizzles. Seems the connection is lost...* ({e})")
            self.ollama_available = False
        except TimeoutError:
             await message.channel.send("*Pikol is concentrating very hard... maybe too hard?* The magic words are slow today, meow. Try again?")
        except ValueError as e:
            await message.channel.send(f"*Pikol paws at his wand, but nothing happens!* There's a problem with the magic source: {e}")
            self.log_error('on_message_ai', e)
        except Exception as e:
            await message.channel.send("*Poof! A magical mishap!* Something went wrong with Pikol's spellcasting...")
            self.log_error('on_message_ai', e)
            print(f"Error processing AI response in {message.channel.id}: {type(e).__name__} - {e}")


async def setup(bot):
    if not OLLAMA_BASE_URL or not OLLAMA_CHAT_URL:
         print("WARNING: AI Cog not loaded because 'ollama_server' details (host, port) are missing or incomplete in config.json")
         return

    cog = AICommands(bot)
    await bot.add_cog(cog)

    print("AICommands Cog loaded. Performing initial Ollama connection check...")
    await cog.check_ollama_connection(force_check=True)
    if not cog.ollama_available:
        print(f"WARNING: Initial connection to Ollama server ({OLLAMA_BASE_URL}) failed. AI features may not work.")
    else:
        print(f"Initial connection to Ollama server ({OLLAMA_BASE_URL}) successful. Model set to: {OLLAMA_MODEL}")