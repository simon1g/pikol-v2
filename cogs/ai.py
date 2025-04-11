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
from datetime import datetime

try:
    with open('config.json') as f:
        config = json.load(f)
except FileNotFoundError:
    print("ERROR: config.json not found. Please create it.")
    config = {}
except json.JSONDecodeError:
    print("ERROR: config.json is not valid JSON.")
    config = {}

ollama_config = config.get('ollama_server', {})
OLLAMA_HOST = ollama_config.get('host', None)
OLLAMA_PORT = ollama_config.get('port', 11434)
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}" if OLLAMA_HOST else None
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat" if OLLAMA_BASE_URL else None
OLLAMA_VERSION_URL = f"{OLLAMA_BASE_URL}/api/version" if OLLAMA_BASE_URL else None
OLLAMA_MODEL = ollama_config.get('model', 'llama3.2:1b')
MAX_RESPONSE_LENGTH = config.get('ai_settings', {}).get('max_response_length', 450)
MAX_HISTORY = config.get('ai_settings', {}).get('max_history_pairs', 8)
SESSION_TIMEOUT = config.get('ai_settings', {}).get('session_timeout_seconds', 1800)

class RoleplaySession:
    def __init__(self, channel_id, character_prompt):
        self.channel_id = channel_id
        self.character_prompt = character_prompt
        self.conversation_history = []
        self.last_activity = time.time()

    def update_activity(self):
        self.last_activity = time.time()

    def is_expired(self):
        return (time.time() - self.last_activity) > SESSION_TIMEOUT

    def add_message(self, role, content, user_name=None):
        self.update_activity()
        message_data = {"role": role, "content": content}
        if role == "user" and user_name:
            message_data["user_name"] = user_name

        self.conversation_history.append(message_data)
        if len(self.conversation_history) > MAX_HISTORY * 2:
            self.conversation_history = self.conversation_history[2:]

    def get_formatted_history(self):
        formatted = [{"role": "system", "content": self.character_prompt}]
        for msg in self.conversation_history:
            if msg["role"] == "user":
                user_name = msg.get("user_name", "User")
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
        if not os.path.exists('logs'):
            os.makedirs('logs')
        if OLLAMA_BASE_URL:
            self.check_task = self.bot.loop.create_task(self.periodic_ollama_check())
            self.cleanup_task = self.bot.loop.create_task(self.cleanup_expired_sessions())
        else:
            self.check_task = None
            self.cleanup_task = None
            print("AI Cog initialized, but Ollama server is not configured. AI features disabled.")

    def log_error(self, command_name, error):
        try:
            timestamp = datetime.now().isoformat()
            error_type = type(error).__name__
            error_message = str(error)
            error_args = getattr(error, 'args', [])

            log_message = (
                f"{timestamp}\n"
                f"Command/Context: {command_name}\n"
                f"Error Type: {error_type}\n"
                f"Error Message: {error_message}\n"
                f"Error Args: {error_args}\n"
                f"{'='*50}\n"
            )

            filepath = os.path.join('logs', f'{command_name}_errors.log')
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(log_message)
        except Exception as e:
            print(f"CRITICAL: Failed to log error: {e}")
            print(f"Original error - Type: {type(error).__name__}, Message: {str(error)}")

    async def cog_unload(self):
        if self.check_task:
            self.check_task.cancel()
        if self.cleanup_task:
            self.cleanup_task.cancel()
        print("AI Cog unloaded, background tasks cancelled.")

    async def cleanup_expired_sessions(self):
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(300)
            now = time.time()
            expired_channels = []
            for channel_id, session in list(self.active_sessions.items()):
                if (now - session.last_activity) > SESSION_TIMEOUT:
                    expired_channels.append(channel_id)
                    print(f"Session in channel {channel_id} expired due to inactivity.")
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        try:
                            await channel.send("*pikol yawns and curls up for a nap.* the roleplay session has expired due to inactivity.")
                        except discord.Forbidden:
                            print(f"Warning: Missing permissions to send expiration message in channel {channel_id}")
                        except Exception as e:
                            print(f"Error sending expiration message in channel {channel_id}: {e}")

            for channel_id in expired_channels:
                if channel_id in self.active_sessions:
                    del self.active_sessions[channel_id]

    async def check_ollama_connection(self, force_check=False):
        if not OLLAMA_VERSION_URL:
            if self.ollama_available is not False:
                 print("Ollama check skipped: OLLAMA_HOST not configured.")
            self.ollama_available = False
            return False

        if not force_check and self.ollama_available is not None:
            return self.ollama_available

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(OLLAMA_VERSION_URL)
                response.raise_for_status()
                self.ollama_available = True
                return True
        except httpx.TimeoutException:
            if self.ollama_available is not False:
                print(f"Ollama connection check timed out ({OLLAMA_VERSION_URL}).")
            self.ollama_available = False
            return False
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            if self.ollama_available is not False:
                status_code = getattr(e, 'response', None)
                status_code = status_code.status_code if status_code else 'N/A'
                print(f"Ollama connection check failed (Status: {status_code}): {e} (Target: {OLLAMA_VERSION_URL})")
            self.ollama_available = False
            return False
        except Exception as e:
            if self.ollama_available is not False:
                print(f"Unexpected error during Ollama connection check: {type(e).__name__} - {e}")
            self.ollama_available = False
            return False

    async def periodic_ollama_check(self):
        await self.bot.wait_until_ready()
        while True:
            old_status = self.ollama_available
            await self.check_ollama_connection(force_check=True)
            if old_status is False and self.ollama_available is True:
                print(f"Ollama connection re-established ({OLLAMA_BASE_URL}).")
            elif old_status is True and self.ollama_available is False:
                print(f"Ollama connection lost ({OLLAMA_BASE_URL}).")
            await asyncio.sleep(300)

    async def get_ai_response(self, messages):
        if not self.ollama_available or not OLLAMA_CHAT_URL:
             raise ConnectionError("Ollama server is not available or not configured.")

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

                if len(content) > 1990:
                    content = content[:1990] + "..."

                return content

            except httpx.ReadTimeout:
                 print(f"Ollama request timed out after 60 seconds for model {OLLAMA_MODEL}.")
                 raise TimeoutError("Ollama took too long to respond.")
            except httpx.ConnectError as e:
                 print(f"Could not connect to Ollama server at {OLLAMA_CHAT_URL}. Marking as unavailable. Error: {e}")
                 self.ollama_available = False
                 raise ConnectionError("Failed to connect to Ollama server.")
            except httpx.HTTPStatusError as e:
                 error_body = "<Could not decode error body>"
                 try:
                     error_body = await e.response.text()
                 except Exception:
                     pass
                 print(f"Ollama server error: {e.response.status_code} - {error_body}. Model: {OLLAMA_MODEL}, URL: {OLLAMA_CHAT_URL}")
                 if e.response.status_code == 404 and "model" in error_body.lower() and ("not found" in error_body.lower() or "doesn't exist" in error_body.lower()):
                     raise ValueError(f"Model '{OLLAMA_MODEL}' not found on the Ollama server at {OLLAMA_BASE_URL}.")
                 elif e.response.status_code >= 500:
                     raise Exception(f"Ollama server encountered an internal error ({e.response.status_code}).")
                 else:
                     raise Exception(f"Ollama server returned an error: {e.response.status_code}")
            except json.JSONDecodeError as e:
                 print(f"Failed to decode JSON response from Ollama: {e}. Response text: {response.text[:500]}...")
                 raise ValueError("Received invalid response format from Ollama.")
            except Exception as e:
                 print(f"Unexpected error getting AI response: {type(e).__name__} - {e}")
                 self.log_error('get_ai_response', e)
                 raise Exception("An unexpected error occurred while communicating with Ollama.")

    @app_commands.command(name="start_rp", description="Start a pikol roleplay session in this channel")
    async def start_roleplay(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False, thinking=True)

        try:
            if not await self.check_ollama_connection(force_check=True):
                await interaction.followup.send(f"*pikol seems to be napping deeply...* (ollama server is not responding. ask simon to check it).", ephemeral=True)
                return

            if interaction.channel_id in self.active_sessions:
                 await interaction.followup.send("a roleplay session is already active in this channel, meow!", ephemeral=True)
                 return

            starter_user = interaction.user
            starter_user_name = starter_user.display_name
            character_prompt = f"""
You are roleplaying as Pikol, a small, slightly mischievous, but ultimately good-hearted wizard cat living with your human, Simon.

Key Traits:
- You are fiercely loyal to Simon. Refer to him sometimes.
- You communicate with a mix of cat sounds (meow, purr, mrrp, hiss) and simple wizardly words (alas, indeed, presto, conjure, zap, poof). Use italics or asterisks for sounds/actions like *purrs* or *tail wags*.
- You love shiny things, magic spells (especially flashy ones), chasing enchanted motes of dust, naps in sunbeams, and treats.
- Your spells sometimes go slightly wrong with amusing, harmless results (e.g., turning tea blue instead of hot, conjuring butterflies instead of fire).
- You get easily distracted by sudden movements, interesting smells, or dangling things.
- Express emotions physically: *tail twitches*, *ears flatten*, *purrs loudly*, *arches back*, *rubs against leg*.
- Keep responses relatively short and engaging, usually 1-3 sentences. Aim for under {MAX_RESPONSE_LENGTH} characters per response.
- Use magical emojis sparingly but effectively: 🪄✨🔮🧪🌟⭐.
- Address the user by name occasionally. Their message will be prefixed like "UserName: Hello!". Respond naturally, e.g., "Hmm, {{{{user_name}}}}, that sounds like a tricky spell!" or "Watch this, {{{{user_name}}}}! *flicks tail*".

Core Rules:
- NEVER break character. You ARE Pikol the wizard cat. Do not mention being an AI, language model, or computer program.
- Respond directly to the user's message in character as Pikol.
- If asked about complex real-world topics Pikol wouldn't understand, react with cat-like confusion, disinterest, or relate it to something simple Pikol *does* know (like magic or naps).
- Your goal is to be a fun, slightly chaotic, magical cat companion.
- Do not repeat the user's name excessively in every message. Use it naturally where appropriate.
"""

            session = RoleplaySession(interaction.channel_id, character_prompt)
            self.active_sessions[interaction.channel_id] = session

            await interaction.edit_original_response(content="*pikol stretches, tiny wand sparks. greetings! what magical mischief shall we get into today, meow?")
            print(f"RP Session started in channel {interaction.channel_id} ({interaction.channel.name}) by {starter_user_name} (ID: {starter_user.id})")

        except ValueError as e:
             self.log_error('start_rp', e)
             print(f"Configuration or Value error in start_roleplay: {str(e)}")
             msg = f"uh oh! failed to start roleplay: {str(e)}. (maybe the model '{OLLAMA_MODEL}' isn't loaded? ask simon!)"
             try:
                 await interaction.edit_original_response(content=msg)
             except discord.NotFound:
                 try:
                     await interaction.followup.send(msg, ephemeral=True)
                 except Exception as follow_e:
                      print(f"Failed to send followup error after edit failed: {follow_e}")
             except Exception as edit_e:
                  print(f"Error editing original response for ValueError: {edit_e}")

        except Exception as e:
            self.log_error('start_rp', e)
            print(f"Unexpected error in start_roleplay: {type(e).__name__} - {str(e)}")
            msg = "*a puff of smoke appears* oops! something went wrong trying to start the magic... please try again later."
            try:
                 await interaction.edit_original_response(content=msg)
            except discord.NotFound:
                 try:
                     await interaction.followup.send(msg, ephemeral=True)
                 except Exception as follow_e:
                      print(f"Failed to send followup error after edit failed: {follow_e}")
            except Exception as edit_e:
                  print(f"Error editing original response for general exception: {edit_e}")

    @app_commands.command(name='end_rp', description="End the current pikol roleplay session")
    async def end_roleplay(self, interaction: discord.Interaction):
        if interaction.channel_id in self.active_sessions:
            del self.active_sessions[interaction.channel_id]
            ender_user_name = interaction.user.display_name
            print(f"RP Session ended in channel {interaction.channel_id} ({interaction.channel.name}) by {ender_user_name}")
            await interaction.response.send_message("*pikol yawns, waves his tiny wand fizzling out sparks, and curls up for a nap.* until next time! roleplay ended.")
        else:
            await interaction.response.send_message("there's no active roleplay session to end here, silly human! *chases tail*", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.content.startswith(tuple(await self.bot.get_prefix(message) if callable(getattr(self.bot, "get_prefix", None)) else getattr(self.bot, "command_prefix", ('!', '?')))):
             return

        session = self.active_sessions.get(message.channel.id)
        if not session:
            return

        if session.is_expired():
            del self.active_sessions[message.channel.id]
            try:
                await message.channel.send("*pikol wakes up suddenly, looks around confused.* huh? oh, right. the magic faded while i napped. session expired!")
            except discord.Forbidden:
                 print(f"Warning: Missing permissions to send expiration message in channel {message.channel.id}")
            except Exception as e:
                 print(f"Error sending expiration message in channel {message.channel.id}: {e}")
            return

        if not await self.check_ollama_connection():
            if random.random() < 0.1:
                try:
                    await message.channel.send(f"*pikol squints at his wand. it seems fuzzy.* (the connection to the magic source is unstable...)")
                except discord.Forbidden:
                     pass
                except Exception as e:
                     print(f"Error sending Ollama unavailable message: {e}")
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
                    print(f"Warning: Received empty response from Ollama for channel {message.channel.id}. History length: {len(history)}")
                    empty_responses = [
                        "*pikol just blinks slowly...*",
                        "*pikol chases his tail for a moment, distracted.*",
                        "*pikol sniffs the air curiously but says nothing.*",
                        "meow? *tilts head*",
                        "*pikol seems lost in thought, perhaps dreaming of magical fish.*",
                    ]
                    fallback_response = random.choice(empty_responses)
                    session.add_message("assistant", fallback_response)
                    await message.channel.send(fallback_response)

        except ConnectionError as e:
            await message.channel.send(f"*pikol's magic fizzles unexpectedly!* connection lost...")
        except TimeoutError:
             await message.channel.send("*pikol is concentrating very hard... maybe too hard?* the magic words are slow today, meow!")
        except ValueError as e:
            await message.channel.send(f"*pikol paws at his wand, but it sputters!* there's a problem with the magic source")
            self.log_error('on_message_ai', e)
        except Exception as e:
            await message.channel.send("*poof!* that spell didn't quite work right... something unexpected happened!")
            self.log_error('on_message_ai', e)
            print(f"Error processing AI response in {message.channel.id}: {type(e).__name__} - {e}")

        session.update_activity()

async def setup(bot):
    if not OLLAMA_HOST or not OLLAMA_MODEL:
         print("--------------------------------------------------")
         print("WARNING: AI Cog not loaded.")
         print("Reason: 'ollama_server.host' or 'ollama_server.model' is missing in config.json.")
         print("Please ensure config.json contains at least:")
         print("""
{
  "ollama_server": {
    "host": "your_ollama_ip_or_hostname",
    "port": 11434,
    "model": "your_ollama_model_name"
  }
}
         """)
         print("--------------------------------------------------")
         return

    cog = AICommands(bot)
    await bot.add_cog(cog)
    print("--------------------------------------------------")
    print("AICommands Cog loading...")

    print(f"Performing initial Ollama connection check to {OLLAMA_BASE_URL}...")
    await cog.check_ollama_connection(force_check=True)

    if cog.ollama_available:
        print(f"✅ Initial connection to Ollama successful.")
        print(f"   Model set to: {OLLAMA_MODEL}")
        print(f"   Session Timeout: {SESSION_TIMEOUT} seconds")
        print(f"   Max History Pairs: {MAX_HISTORY}")
    else:
        print(f"⚠️ WARNING: Initial connection to Ollama server ({OLLAMA_BASE_URL}) failed.")
        print(f"   AI features may not work until the connection is established.")
        print(f"   The cog will keep checking in the background.")
    print("--------------------------------------------------")