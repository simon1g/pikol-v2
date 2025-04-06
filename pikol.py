import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import random
from datetime import datetime, timedelta
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv('TOKEN')
TOKEN_TEST = os.getenv('TOKEN_TEST')

# Keep paths or basic config if needed by main file/tasks
LOG_DIR = 'logs'
SERVER_DATA_DIR = 'servers'
JSON_DIR = 'json'

# Ensure directories exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SERVER_DATA_DIR, exist_ok=True)
os.makedirs(JSON_DIR, exist_ok=True) # Ensure json dir exists if files are missing


# Load data needed by tasks or shared utilities if not loaded by cogs
try:
    with open(os.path.join(JSON_DIR,'potions.json')) as f:
        POTIONS_DATA = json.load(f)
except FileNotFoundError:
    print(f"Warning: {os.path.join(JSON_DIR,'potions.json')} not found. Shop restock might fail.")
    POTIONS_DATA = []
except json.JSONDecodeError:
     print(f"Warning: {os.path.join(JSON_DIR,'potions.json')} is invalid. Shop restock might fail.")
     POTIONS_DATA = []

# --- Bot Setup ---
intents = discord.Intents.default()
intents.messages = True       # Needed for on_message
intents.message_content = True  # REQUIRED for reading message content
intents.guilds = True         # Needed for guild operations, members list
intents.members = True        # Needed for fetching members, user data

# Prefix can be empty if only using slash commands, but keep for potential future text commands
bot = commands.Bot(command_prefix='!', intents=intents)
# tree = bot.tree # Tree is accessible via bot.tree directly

# --- Global Helper Functions (Accessible via bot instance in cogs or directly here) ---

def load_server_data(server_id):
    filepath = os.path.join(SERVER_DATA_DIR, f'{server_id}.json')
    try:
        with open(filepath) as f:
            return json.load(f)
    except FileNotFoundError:
        # Return a default structure if file doesn't exist
        return {"balance": {}, "inventory": {}, "shop": [], "next_restock": None}
    except json.JSONDecodeError:
        print(f"Error decoding JSON for server {server_id}. Returning default.")
        # Handle corrupted JSON file - maybe backup and return default?
        return {"balance": {}, "inventory": {}, "shop": [], "next_restock": None}


def save_server_data(server_id, data):
    filepath = os.path.join(SERVER_DATA_DIR, f'{server_id}.json')
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
    except IOError as e:
         print(f"Error saving data for server {server_id}: {e}")
    except TypeError as e:
         print(f"Error serializing data for server {server_id} (likely non-serializable object): {e}")


def log_error(command_name, error):
    """Logs an error to a command-specific file."""
    timestamp = datetime.now().isoformat()
    log_message = f"{timestamp} - Error: {error}\n"
    # Add traceback logging for more detail (optional)
    # import traceback
    # log_message += traceback.format_exc() + "\n"

    filepath = os.path.join(LOG_DIR, f'{command_name}_errors.txt')
    try:
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(log_message)
    except IOError as e:
        print(f"CRITICAL: Could not write to log file {filepath}: {e}")


# Attach helpers to bot instance so cogs can access them via self.bot
bot.load_server_data = load_server_data
bot.save_server_data = save_server_data
bot.log_error = log_error

# --- Restock Logic (Used by Task) ---
def restock_shop():
    """Generates a new list of potions for the shop."""
    if not POTIONS_DATA: # Handle case where potion data failed to load
        return []

    shop = []
    # Ensure weights are positive and match the number of potions
    weights = [p.get('rarity', 1) for p in POTIONS_DATA] # Default rarity 1 if missing
    valid_potions = [p for i, p in enumerate(POTIONS_DATA) if weights[i] > 0]
    valid_weights = [w for w in weights if w > 0]

    if not valid_potions or not valid_weights or len(valid_potions) != len(valid_weights):
         print("Warning: Invalid potion data or weights for restocking.")
         # Fallback: select randomly without weights? or return empty?
         if POTIONS_DATA:
             for _ in range(min(4, len(POTIONS_DATA))): # Select up to 4 random if weights fail
                  shop.append(random.choice(POTIONS_DATA).copy())
         return shop


    try:
        for _ in range(4): # Generate 4 potions for the shop
            # Use random.choices (plural) which handles weights
            chosen_potion_list = random.choices(valid_potions, weights=valid_weights, k=1)
            if chosen_potion_list:
                 # IMPORTANT: Use .copy() to avoid modifying the original POTIONS_DATA dict
                 potion = chosen_potion_list[0].copy()
                 # Add default price/quantity if missing? Or assume they exist in JSON
                 potion['price'] = potion.get('price', random.randint(10, 50)) # Example default price
                 shop.append(potion)
    except Exception as e:
         print(f"Error during shop restocking logic: {e}")
         # Fallback or return partially filled shop?
         return shop # Return whatever was generated so far

    return shop


# --- Background Tasks ---

@tasks.loop(minutes=10)
async def restock_shops_task():
    print(f"Task: Running restock_shops at {datetime.now()}")
    for guild in bot.guilds:
        try:
            data = load_server_data(guild.id)
            data['shop'] = restock_shop() # Call the restock logic
            data['next_restock'] = (datetime.now() + timedelta(minutes=10)).isoformat()
            save_server_data(guild.id, data)
            # print(f"Shop restocked for guild {guild.id}") # Optional: Verbose logging
        except Exception as e:
            log_error(f'restock_task_guild_{guild.id}', e)
            print(f"Error in restock task for guild {guild.id}: {e}")

@tasks.loop(minutes=5) # Rotate more often?
async def rotate_activity_task():
    # Constants moved from original file
    ACTIVITIES = [
        (discord.ActivityType.playing, "with potions 🧪"),
        (discord.ActivityType.listening, "to purrs"),
        (discord.ActivityType.playing, "in the cauldron ⚗️"),
        (discord.ActivityType.watching, "magic bubbles ✨"),
        (discord.ActivityType.listening, "wizard spells 🪄"),
        (discord.ActivityType.playing, "with magic yarn 🧶"),
        (discord.ActivityType.watching, "the orb 🔮"),
        (discord.ActivityType.competing, "in a spell-off ⭐"),
    ]
    try:
        activity_type, name = random.choice(ACTIVITIES)
        await bot.change_presence(activity=discord.Activity(type=activity_type, name=name))
        # print(f"Activity updated to: {activity_type.name} {name}") # Optional logging
    except Exception as e:
        log_error('rotate_activity_task', e)
        print(f"Error changing activity: {e}")


@tasks.loop(minutes=15) # Increase interval?
async def reward_random_user_task():
    print(f"Task: Running reward_random_user at {datetime.now()}")
    coins_to_reward = 20
    for guild in bot.guilds:
        try:
            data = load_server_data(guild.id)

            # Fetch members if needed or use cached members if available and intent is on
            # Be mindful of large servers, fetching might be slow/costly.
            # Using guild.members might be sufficient if member intent is enabled and cache is populated.
            eligible_members = [
                member for member in guild.members
                if not member.bot and member.status != discord.Status.offline # Optional: only online/idle users?
            ]

            if not eligible_members:
                # print(f"No eligible members found in {guild.name} for reward.")
                continue

            lucky_member = random.choice(eligible_members)
            user_id = str(lucky_member.id)

            # Initialize if user not present
            if user_id not in data['balance']:
                data['balance'][user_id] = random.randint(80, 120) # Initial balance if new
            if user_id not in data['inventory']:
                 data['inventory'][user_id] = {}


            # Grant the reward
            # original_balance = data['balance'][user_id] # Not used currently
            data['balance'][user_id] += coins_to_reward
            save_server_data(guild.id, data)
            print(f"Rewarded {coins_to_reward} coins to {lucky_member.display_name} in {guild.name}")

            # Optional: Send a message to a specific channel? Needs channel ID config.
            # log_channel_id = 123456789012345678 # Replace with actual ID
            # log_channel = guild.get_channel(log_channel_id)
            # if log_channel:
            #     await log_channel.send(f"✨ {lucky_member.mention} found {coins_to_reward} shiny coins! ✨")

        except Exception as e:
            log_error(f'reward_task_guild_{guild.id}', e)
            print(f"Error in reward_random_user task for guild {guild.id}: {e}")

# --- Core Bot Events ---

@bot.event
async def on_ready():
    """Called when the bot is ready and connected."""
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    print(f'Discord.py Version: {discord.__version__}')
    print('------')

    # Load Cogs
    print("Loading cogs...")
    loaded_cogs = 0
    cog_dir = 'cogs'
    for filename in os.listdir(cog_dir):
        # Load .py files, exclude __init__.py and non-python files
        if filename.endswith('.py') and filename != '__init__.py':
            extension_name = f'{cog_dir}.{filename[:-3]}'
            try:
                await bot.load_extension(extension_name)
                print(f'Successfully loaded extension: {extension_name}')
                loaded_cogs += 1
            except commands.ExtensionNotFound:
                print(f'Error: Extension {extension_name} not found.')
            except commands.ExtensionAlreadyLoaded:
                print(f'Warning: Extension {extension_name} already loaded.')
            except commands.NoEntryPointError:
                print(f'Error: Extension {extension_name} has no setup() function.')
            except commands.ExtensionFailed as e:
                # Log the full traceback for detailed debugging
                log_error(f'cog_load_{filename[:-3]}', e.original)
                print(f'Error loading extension {extension_name}:\n {e.original}')
                # Optionally print traceback:
                # import traceback
                # traceback.print_exception(type(e.original), e.original, e.original.__traceback__)

    print(f"--- Loaded {loaded_cogs} cogs ---")


    # Sync slash commands (important!)
    # Sync globally or per guild? Global is simpler but takes time to propagate.
    # Guild sync is instant but needs to be done for each guild (e.g., in a command).
    print("Syncing slash commands...")
    try:
        # Sync globally
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} global application command(s).")
        # # To sync for a specific guild (faster updates during testing):
        # test_guild_id = 123456789012345678 # Replace with your test server ID
        # guild_obj = discord.Object(id=test_guild_id)
        # await bot.tree.sync(guild=guild_obj)
        # print(f"Synced commands for guild {test_guild_id}")
    except Exception as e:
        log_error('command_sync', e)
        print(f"Error syncing application commands: {e}")

    # Start background tasks
    print("Starting background tasks...")
    if not restock_shops_task.is_running():
        restock_shops_task.start()
    if not reward_random_user_task.is_running():
         reward_random_user_task.start()
    if not rotate_activity_task.is_running():
         rotate_activity_task.start()
    print("--- Bot is Ready! ---")


@bot.event
async def on_message(message: discord.Message):
    """Handles messages NOT processed by cogs or commands."""
    try:
        # Ignore bots (including self)
        if message.author.bot:
            return

        # Safely get message content
        content = str(message.content) if message.content else ""

        # Check if AI cog is handling this message
        ai_cog = bot.get_cog('AICommands')
        if ai_cog and hasattr(ai_cog, 'active_sessions') and message.channel.id in ai_cog.active_sessions:
            return  # Let AI cog handle it

        # Safely handle emojis
        try:
            pikol_emoji = discord.utils.get(message.guild.emojis, name='pikol') if message.guild else None
            wizard_pikol_emoji = discord.utils.get(message.guild.emojis, name='wizardpikol') if message.guild else None

            pikol_str = str(pikol_emoji) if pikol_emoji else "<:wizardpikol:1328137703044415488>"
            wizard_pikol_str = str(wizard_pikol_emoji) if wizard_pikol_emoji else "<:wizardpikol:1328137703044415488>"
        except:
            # Fallback if emoji fetch fails
            pikol_str = "<:wizardpikol:1328137703044415488>"
            wizard_pikol_str = "<:wizardpikol:1328137703044415488>"

        # Check mentions safely
        is_direct_mention = bot.user.id in [u.id for u in message.mentions] if message.mentions else False
        content_lower = content.lower()

        # Define responses
        meow_responses = ['Meow', 'MEOW', '~meow~🪄', f'meow {pikol_str}', f'{wizard_pikol_str}🪄', '*purrrr*', '...?']
        mention_responses = ['Meow?', 'Yes, meow?', '*tilts head*', f'{pikol_str}?', f'{wizard_pikol_str}!', 'You called, meow?']

        # Handle responses with proper error checking
        if not message.channel:
            return

        try:
            if 'meow' in content_lower and is_direct_mention:
                await message.channel.send(str(random.choice(meow_responses)))
            elif 'meow' in content_lower and random.random() < 0.2:
                await message.channel.send(str(random.choice(meow_responses)))
            elif is_direct_mention:
                await message.channel.send(str(random.choice(mention_responses)))
        except discord.errors.Forbidden:
            pass  # Can't send messages in this channel
        except Exception as response_error:
            print(f"Error sending response: {response_error}")

    except Exception as e:
        error_info = f"Error Type: {type(e)}\nError Message: {str(e)}\nError Args: {getattr(e, 'args', [])}"
        log_error('on_message_basic', error_info)
        print(f"Error in on_message handler: {error_info}")

    # Let other event handlers and cogs process the message

# --- Run the Bot ---
if __name__ == "__main__":
    if not TOKEN:
        print("CRITICAL: Bot token is missing! Please set your Discord bot token in the TOKEN variable.")
    else:
        try:
            bot.run(TOKEN)
        except discord.LoginFailure:
            print("CRITICAL: Failed to log in. Please check that your Discord bot token is correct.")
        except Exception as e:
            print(f"CRITICAL: An error occurred while running the bot: {e}")
            log_error('bot_run', e)