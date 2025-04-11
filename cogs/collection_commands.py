import discord
from discord import app_commands
from discord.ext import commands
import json
import os

def get_rarity_emoji(rarity):
    if rarity == 1: return "🌟"
    elif rarity == 2: return "⭐"
    elif rarity == 3: return "✨"
    else: return "⚪"

class PaginationView(discord.ui.View):
    def __init__(self, pages, total_potions_possible, unique_count, original_interaction: discord.Interaction):
        super().__init__(timeout=120)
        self.pages = pages
        self.total_potions_possible = total_potions_possible
        self.unique_count = unique_count
        self.current_page = 0
        self.original_interaction = original_interaction
        self.message = None
        self.update_button_states()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.original_interaction.user.id:
            await interaction.response.send_message("this isn't your collection!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.NotFound:
                pass

    def update_button_states(self):
        previous_button = discord.utils.get(self.children, custom_id="previous_page")
        next_button = discord.utils.get(self.children, custom_id="next_page")

        if previous_button:
            previous_button.disabled = self.current_page == 0
        if next_button:
            next_button.disabled = self.current_page >= len(self.pages) - 1


    def create_embed(self):
        page_num = self.current_page
        collection_percentage = (self.unique_count / self.total_potions_possible) * 100 if self.total_potions_possible > 0 else 0

        segments = 10
        filled = int((self.unique_count / self.total_potions_possible) * segments) if self.total_potions_possible > 0 else 0
        progress_bar = '█' * filled + '░' * (segments - filled)

        embed = discord.Embed(
            title="🧪 your Potion Collection 🪄",
            description=f"collection progress: {self.unique_count}/{self.total_potions_possible} unique potions discovered.\n({collection_percentage:.2f}%) {progress_bar}",
            color=discord.Color.purple()
        )

        if not self.pages:
             embed.description += "\n\nyour collection is empty! go buy some potions, meow!"
        elif page_num >= len(self.pages):
             embed.description += "\n\nsomething went wrong with pagination!!!"
             page_num = 0
             self.current_page = 0
        else:
             for potion in self.pages[page_num]:
                 rarity_emoji = get_rarity_emoji(potion.get("rarity", 0))
                 quantity = potion.get('quantity', 1)
                 quantity_text = f" (×{quantity})" if quantity > 1 else ""
                 embed.add_field(
                     name=f"{rarity_emoji} {potion.get('name', 'Unknown Potion')}{quantity_text}",
                     value=f"Rarity: {potion.get('rarity', 'N/A')}",
                     inline=False
                 )

        embed.set_footer(text=f"page {page_num + 1}/{len(self.pages)}" if self.pages else "page 1/1")
        return embed

    @discord.ui.button(label="previous", style=discord.ButtonStyle.secondary, custom_id="previous_page", disabled=True)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_button_states()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()


    @discord.ui.button(label="next ~meow", style=discord.ButtonStyle.secondary, custom_id="next_page")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_button_states()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()


class CollectionCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        try:
            with open('json/potions.json') as f:
                self.ALL_POTIONS_DATA = json.load(f)
                self.TOTAL_POTIONS_POSSIBLE = len(self.ALL_POTIONS_DATA)
        except FileNotFoundError:
            print("ERROR: json/potions.json not found for collection count!")
            self.ALL_POTIONS_DATA = []
            self.TOTAL_POTIONS_POSSIBLE = 0
        except json.JSONDecodeError:
            print("ERROR: json/potions.json is not valid JSON for collection count!")
            self.ALL_POTIONS_DATA = []
            self.TOTAL_POTIONS_POSSIBLE = 0

    def load_server_data(self, server_id):
        return self.bot.load_server_data(server_id)

    def log_error(self, command_name, error):
        self.bot.log_error(command_name, error)

    @app_commands.command(name="collection", description="View your collected potions MEOW!!!")
    async def collection(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

            server_id = interaction.guild.id
            user_id = str(interaction.user.id)
            data = self.load_server_data(server_id)

            if user_id not in data.get("inventory", {}) or not data["inventory"][user_id]:
                await interaction.followup.send("you have not collected any potions yet... meow.....")
                return

            inventory_dict = data["inventory"][user_id]
            
            inventory_items = []
            for potion_name, quantity in inventory_dict.items():
                potion_data = next((p for p in self.ALL_POTIONS_DATA if p["name"] == potion_name), None)
                if potion_data:
                    potion_item = potion_data.copy()
                    potion_item["quantity"] = quantity
                    inventory_items.append(potion_item)

            sorted_inventory = sorted(inventory_items, key=lambda p: (p.get("rarity", 99), p.get("name", "")))
            unique_count = len(sorted_inventory)

            per_page = 5
            pages = [sorted_inventory[i:i + per_page] for i in range(0, len(sorted_inventory), per_page)]

            if not pages:
                await interaction.followup.send("your collection seems empty after sorting! MEOW!")
                return

            view = PaginationView(pages, self.TOTAL_POTIONS_POSSIBLE, unique_count, interaction)
            view.update_button_states()
            initial_embed = view.create_embed()

            view.message = await interaction.followup.send(embed=initial_embed, view=view)

        except Exception as e:
            self.log_error('collection', e)
            print(f"Error in collection command: {e}")
            if interaction.response.is_done():
                await interaction.followup.send("couldn't show your collection... *sad kitty noises*")
            else:
                await interaction.response.send_message("couldn't show your collection... *sad kitty noises*")


async def setup(bot):
    await bot.add_cog(CollectionCommands(bot))