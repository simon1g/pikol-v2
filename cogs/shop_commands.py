import discord
from discord import app_commands
from discord.ext import commands
import json
import random
from datetime import datetime, timedelta
import os

def get_rarity_emoji(rarity):
    if rarity == 1: return "🌟"
    elif rarity == 2: return "⭐"
    elif rarity == 3: return "✨"
    else: return "⚪"

PURCHASE_RESPONSES = [
    "*~meow!~* {user} just bought {potion}{quantity} for {price} coins!",
    "**MEOW!!** 🧪 {user} snagged {potion} ⚗️ {quantity} for {price} 🪙",
    "~meow 🪄 {user} purchased {potion} ⚗️ {quantity} for {price} 🪙🪙🪙!",
    "{user} dropped {price} coins for {potion} 🧪 {quantity}! *cat took the coins and runs away!*",
    "MEOWEST PURCHASE! ⚗️{user} got {potion}{quantity} for {price} coins!",
    "*purrs* 🧪 {user} now owns {potion} 🪄 {quantity}! paid {price} 🪙 ~meow~",
    "⚗️ *happy meow* ⚗️ {user} took {potion}{quantity} home for {price} coins!",
    "the meowest choice! 🧪 {user} bought {potion}{quantity} for {price} coins 🪙!",
    "PIKOL APPROVED! 🪄 {user} got {potion}{quantity} for {price} coins!"
]

EMPTY_SHOP_MESSAGES = [
    "pikol is taking a cat nap! come back in {minutes} minutes!\nYour balance: {balance} 🪙",
    "the shop is empty! pikol went to cast some spells! return in {minutes} minutes!\nYour balance: {balance} 🪙",
    "pikol spilled all the potions... clean up will take {minutes} minutes!\nYour balance: {balance} 🪙",
    "pikol is out gathering rare ingredients! check back in {minutes} minutes!\nYour balance: {balance} 🪙",
    "*meow?* shop's closed for restocking! try again in {minutes} minutes!\nYour balance: {balance} 🪙",
    "pikol is brewing new potions! come back in {minutes} minutes!\nYour balance: {balance} 🪙",
    "the cauldron needs {minutes} minutes to heat up! *happy cat noises*\nYour balance: {balance} 🪙",
    "pikol got tangled in magic yarn! return in {minutes} minutes!\nYour balance: {balance} 🪙",
    "pikol is chasing potion bubbles! dumb dumb! come again in {minutes} minutes!\nYour balance: {balance} 🪙"
]

NO_COINS_MESSAGES = [
    "you don't have enough coins! **MEOW!** 🪄",
    "*sad cat noises* your coin purse is too light! 🪙",
    "not enough in your pocket! *meoww* ⭐",
    "**MEOW MEOW!** come back with more coins!"
]

class ShopCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        try:
            with open('json/potions.json') as f:
                self.POTIONS = json.load(f)
        except FileNotFoundError:
            print("ERROR: json/potions.json not found!")
            self.POTIONS = []
        except json.JSONDecodeError:
            print("ERROR: json/potions.json is not valid JSON!")
            self.POTIONS = []

    def load_server_data(self, server_id):
        return self.bot.load_server_data(server_id)

    def save_server_data(self, server_id, data):
        self.bot.save_server_data(server_id, data)

    def log_error(self, command_name, error):
        self.bot.log_error(command_name, error)

    @app_commands.command(name="shop", description="View the potion shop and your balance.🪄")
    async def shop(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

            server_id = interaction.guild.id
            user_id = str(interaction.user.id)
            original_user = interaction.user
            data = self.load_server_data(server_id)

            if user_id not in data['balance']:
                data['balance'][user_id] = random.randint(80, 120)
            if user_id not in data['inventory']:
                 data['inventory'][user_id] = {}
            if user_id not in data['balance'] or user_id not in data['inventory']:
                self.save_server_data(server_id, data)

            current_balance = data['balance'][user_id]

            if 'shop' not in data or not data['shop']:
                next_restock_iso = data.get('next_restock')
                if next_restock_iso:
                    try:
                        next_restock = datetime.fromisoformat(next_restock_iso)
                    except ValueError:
                        next_restock = datetime.now()
                else:
                    next_restock = datetime.now()

                current_time = datetime.now()
                time_left = next_restock - current_time
                minutes = max(1, int(time_left.total_seconds() / 60)) if time_left.total_seconds() > 0 else 10

                empty_message = random.choice(EMPTY_SHOP_MESSAGES).format(
                    minutes=minutes,
                    balance=current_balance
                )
                empty_embed = discord.Embed(
                    title="🔮 Pikol's Potion Shop 🪄",
                    description=empty_message,
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=empty_embed)
                return

            shop_items = data['shop']

            next_restock_iso = data.get('next_restock', datetime.now().isoformat())
            try:
                next_restock = datetime.fromisoformat(next_restock_iso)
            except ValueError:
                 next_restock = datetime.now() + timedelta(minutes=10)

            time_until_restock = next_restock - datetime.now()
            minutes_until_restock = min(10, max(1, int(time_until_restock.total_seconds() / 60) + 1)) if time_until_restock.total_seconds() > 0 else 10

            embed = discord.Embed(
                title="🔮 Pikol's Potion Shop 🪄",
                description=f"welcome *~meow~*! your balance: {current_balance} 🪙\nnext restock in: {minutes_until_restock} minutes",
                color=discord.Color.blurple()
            )

            if not shop_items:
                 embed.description = f"pikol is restocking! Check back in {minutes_until_restock} minutes!\nyour balance: {current_balance} 🪙"
                 embed.color = discord.Color.red()
                 await interaction.followup.send(embed=embed)
                 return

            for i, potion in enumerate(shop_items):
                 if i >= 4: break
                 rarity_emoji = get_rarity_emoji(potion["rarity"])
                 embed.add_field(
                     name=f"{i+1}. {rarity_emoji} {potion['name']}",
                     value=f"price: {potion['price']} 🪙",
                     inline=False
                 )

            view = discord.ui.View(timeout=120)

            for i, potion_data in enumerate(shop_items):
                if i >= 4: break
                rarity_emoji = get_rarity_emoji(potion_data["rarity"])
                
                class ButtonHandler:
                    def __init__(self, index, shop_commands):
                        self.index = index
                        self.shop_commands = shop_commands

                    async def callback(self, interaction: discord.Interaction):
                        try:
                            await interaction.response.defer(ephemeral=True)
                            
                            guild_data = self.shop_commands.load_server_data(interaction.guild_id)
                            shop = guild_data.get('shop', [])
                            
                            if self.index >= len(shop):
                                await interaction.followup.send("this item is no longer available! *sad meow*", ephemeral=True)
                                return
                                
                            item = shop[self.index]
                            user_id = str(interaction.user.id)
                            
                            if user_id not in guild_data['balance']:
                                guild_data['balance'][user_id] = random.randint(80, 120)
                            if user_id not in guild_data['inventory']:
                                guild_data['inventory'][user_id] = {}
                                
                            if guild_data['balance'][user_id] < item['price']:
                                await interaction.followup.send("you don't have enough coins! *sad meow*", ephemeral=True)
                                return
                                
                            guild_data['balance'][user_id] -= item['price']
                            guild_data['inventory'][user_id][item['name']] = guild_data['inventory'][user_id].get(item['name'], 0) + 1
                            guild_data['shop'].pop(self.index)
                            
                            self.shop_commands.save_server_data(interaction.guild_id, guild_data)
                            
                            purchase_message = f"you bought a {item['name']} for {item['price']} coins! *happy meow*"
                            try:
                                await interaction.followup.send(purchase_message, ephemeral=True)
                            except discord.NotFound:
                                try:
                                    await interaction.response.send_message(purchase_message, ephemeral=True)
                                except discord.NotFound:
                                    print(f"Failed to respond to interaction - both followup and response failed")
                                    return
                                    
                        except Exception as e:
                            self.shop_commands.log_error('shop_button_callback', e)
                            try:
                                await interaction.followup.send("an error occurred while processing your purchase! *sad meow*", ephemeral=True)
                            except:
                                print(f"Failed to send error message for shop purchase: {str(e)}")

                button = discord.ui.Button(
                    label=f"buy {i+1} {rarity_emoji}",
                    custom_id=f"buy_{i}",
                    style=discord.ButtonStyle.secondary
                )
                
                handler = ButtonHandler(i, self)
                button.callback = handler.callback
                view.add_item(button)

            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            self.log_error('shop', e)
            print(f"Error in shop command: {e}")
            if interaction.response.is_done():
                await interaction.followup.send("something went wrong displaying the shop! *confused meow*", ephemeral=True)
            else:
                 await interaction.response.send_message("something went wrong displaying the shop! *confused meow*", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ShopCommands(bot))