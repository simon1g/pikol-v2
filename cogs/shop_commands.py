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
    "The meowest choice! 🧪 {user} bought {potion}{quantity} for {price} coins 🪙!",
    "PIKOL APPROVED! 🪄 {user} got {potion}{quantity} for {price} coins!"
]

EMPTY_SHOP_MESSAGES = [
    "Pikol is taking a cat nap! Come back in {minutes} minutes! *purrs*\nYour balance: {balance} 🪙",
    "The shop is empty! Pikol went to cast some spells! Return in {minutes} minutes!\nYour balance: {balance} 🪙",
    "Pikol spilled all the potions... Clean up will take {minutes} minutes!\nYour balance: {balance} 🪙",
    "Pikol is out gathering rare ingredients! Check back in {minutes} minutes!\nYour balance: {balance} 🪙",
    "*meow?* Shop's closed for restocking! Try again in {minutes} minutes!\nYour balance: {balance} 🪙",
    "Pikol is brewing new potions! Come back in {minutes} minutes!\nYour balance: {balance} 🪙",
    "The cauldron needs {minutes} minutes to heat up! *happy cat noises*\nYour balance: {balance} 🪙",
    "Pikol got tangled in magic yarn! Return in {minutes} minutes!\nYour balance: {balance} 🪙",
    "Pikol is chasing potion bubbles! dumb dumb! Come again in {minutes} minutes!\nYour balance: {balance} 🪙"
]

NO_COINS_MESSAGES = [
    "You don't have enough coins! **MEOW!** 🪄",
    "*sad cat noises* Your coin purse is too light! 🪙",
    "Not enough in your pocket! *meoww* ⭐",
    "**MEOW MEOW!** Come back with more coins!"
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
                description=f"Welcome *~meow~*! Your balance: {current_balance} 🪙\nNext restock in: {minutes_until_restock} minutes",
                color=discord.Color.blurple()
            )

            if not shop_items:
                 embed.description = f"Pikol is restocking! Check back in {minutes_until_restock} minutes!\nYour balance: {current_balance} 🪙"
                 embed.color = discord.Color.red()
                 await interaction.followup.send(embed=embed)
                 return

            for i, potion in enumerate(shop_items):
                 if i >= 4: break
                 rarity_emoji = get_rarity_emoji(potion["rarity"])
                 embed.add_field(
                     name=f"{i+1}. {rarity_emoji} {potion['name']}",
                     value=f"Price: {potion['price']} 🪙",
                     inline=False
                 )

            view = discord.ui.View(timeout=120)

            for i, potion_data in enumerate(shop_items):
                if i >= 4: break
                rarity_emoji = get_rarity_emoji(potion_data["rarity"])
                button = discord.ui.Button(
                    label=f"Buy {i+1} {rarity_emoji}",
                    custom_id=f"buy_{server_id}_{i}",
                    style=discord.ButtonStyle.secondary
                )

                async def button_callback(interaction: discord.Interaction, current_index=i):
                    callback_data = self.load_server_data(interaction.guild.id)
                    callback_user_id = str(interaction.user.id)

                    if interaction.user.id != original_user.id:
                        await interaction.response.send_message("This is not your shop session! Use `/shop` yourself, meow!", ephemeral=True)
                        return

                    if 'shop' not in callback_data or not callback_data['shop'] or current_index >= len(callback_data['shop']):
                        await interaction.response.edit_message(content="*Meow?* The shop changed or this item is gone!", embed=None, view=None)
                        return

                    potion_to_buy = callback_data['shop'][current_index]
                    user_balance = callback_data['balance'].get(callback_user_id, 0)

                    if user_balance < potion_to_buy['price']:
                        await interaction.response.send_message(random.choice(NO_COINS_MESSAGES), ephemeral=True)
                        return

                    try:
                        callback_data['balance'][callback_user_id] -= potion_to_buy['price']

                        potion_key = f"{potion_to_buy['name']}_{potion_to_buy['rarity']}"
                        if callback_user_id not in callback_data['inventory']:
                             callback_data['inventory'][callback_user_id] = {}

                        if potion_key not in callback_data['inventory'][callback_user_id]:
                            potion_copy = {
                                "name": potion_to_buy["name"],
                                "rarity": potion_to_buy["rarity"],
                                "quantity": 1
                            }
                            callback_data['inventory'][callback_user_id][potion_key] = potion_copy
                            new_quantity_text = ""
                        else:
                            callback_data['inventory'][callback_user_id][potion_key]['quantity'] += 1
                            new_quantity = callback_data['inventory'][callback_user_id][potion_key]['quantity']
                            new_quantity_text = f" (Now you have {new_quantity}!)"

                        removed_potion = callback_data['shop'].pop(current_index)
                        self.save_server_data(interaction.guild.id, callback_data)

                        for item in view.children:
                            if isinstance(item, discord.ui.Button):
                                item.disabled = True
                        await interaction.message.edit(view=view)

                        purchase_message = random.choice(PURCHASE_RESPONSES).format(
                            user=interaction.user.mention,
                            potion=removed_potion['name'],
                            price=removed_potion['price'],
                            quantity=new_quantity_text
                        )
                        await interaction.followup.send(purchase_message)
                        await interaction.response.defer()

                    except Exception as e:
                        self.log_error('shop_button_callback', e)
                        print(f"Button callback error: {e}")
                        try:
                            await interaction.response.send_message("Error processing purchase! *sad meow*", ephemeral=True)
                        except discord.InteractionResponded:
                             await interaction.followup.send("Error processing purchase! *sad meow*", ephemeral=True)

                button.callback = button_callback
                view.add_item(button)

            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            self.log_error('shop', e)
            print(f"Error in shop command: {e}")
            if interaction.response.is_done():
                await interaction.followup.send("Something went wrong displaying the shop! *confused meow*", ephemeral=True)
            else:
                 await interaction.response.send_message("Something went wrong displaying the shop! *confused meow*", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ShopCommands(bot))