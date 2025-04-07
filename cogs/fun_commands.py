import discord
from discord import app_commands
from discord.ext import commands
import json
import random
import asyncio
from datetime import timedelta

class FunCommands(commands.Cog):
    def __init__(self, bot):

        try:
            with open('json/pikol_gif.json') as f:
                self.PIKOL_GIFS = json.load(f)
        except FileNotFoundError:
            print("ERROR: json/pikol_gif.json not found!")
            self.PIKOL_GIFS = ["*Pikol tries to find a gif but the box is empty... meow?*"]
        except json.JSONDecodeError:
             print("ERROR: json/pikol_gif.json is invalid!")
             self.PIKOL_GIFS = ["*Pikol fumbles the gif box... it's broken!*"]

        try:
            with open('json/fates.json', encoding='utf-8') as f:
                self.FATES = json.load(f)
        except FileNotFoundError:
             print("ERROR: json/fates.json not found!")
             self.FATES = ["The crystal ball is cloudy... try again later, meow."]
        except json.JSONDecodeError:
             print("ERROR: json/fates.json is invalid!")
             self.FATES = ["The fates are scrambled... too much magic!"]

        try:
            with open('json/fates_together.json', encoding='utf-8') as f:
                self.FATES_TOGETHER = json.load(f)
        except FileNotFoundError:
             print("ERROR: json/fates_together.json not found!")
             self.FATES_TOGETHER = ["Your combined fate is... friendship? Maybe? Meow."]
        except json.JSONDecodeError:
             print("ERROR: json/fates_together.json is invalid!")
             self.FATES_TOGETHER = ["The threads of your fate are tangled!"]


    def log_error(self, command_name, error):
        self.bot.log_error(command_name, error)

    @app_commands.command(name="fmk", description="Fuck, Marry, Kill!!... Meow~")
    async def fmk(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            if not interaction.guild:
                await interaction.followup.send("This command can only be used in a server *meow*.", ephemeral=True)
                return

            members = [m for m in interaction.guild.members if not m.bot]

            if len(members) < 3:
                await interaction.followup.send(f"Not enough non-bot members ({len(members)} found) in the server to assign. Need at least 3, meow!", ephemeral=True)
                return


            protected_id = 385106645052686339 # Simon's ID 
            triggering_user_id = 1010211178716332183 # Brie's ID
            user_to_exclude_id = 841838035855212585 # Brain's ID

            eligible_members = list(members)

            if interaction.user.id == triggering_user_id:
                eligible_members = [m for m in eligible_members if m.id != user_to_exclude_id]
                if len(eligible_members) < 3:
                     await interaction.followup.send(f"After special exclusions, not enough members ({len(eligible_members)} left) for F.M.K., meow!", ephemeral=True)
                     return


            selected_members = random.sample(eligible_members, 3)

            kill_candidate = selected_members[2]
            if kill_candidate.id == protected_id:
                possible_replacements = [m for m in eligible_members if m.id not in (selected_members[0].id, selected_members[1].id, protected_id)]
                if not possible_replacements:
                    selected_members[1], selected_members[2] = selected_members[2], selected_members[1]
                else:
                    selected_members[2] = random.choice(possible_replacements)


            # Create embed
            embed = discord.Embed(
                title="🪄 F.M.K Fate Meow~🪄",
                color=discord.Color.pink()
            )

            embed.add_field(name="Fuck 🏩", value=f"{selected_members[0].mention}", inline=True)
            embed.add_field(name="Marry 👰‍♀️", value=f"{selected_members[1].mention}", inline=True)
            embed.add_field(name="Kill 😵", value=f"{selected_members[2].mention}", inline=True)
            embed.set_footer(text=f"Fate sealed by {interaction.user.display_name}")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            self.log_error('fmk', e)
            print(f"FMK command error: {e}")
            if interaction.response.is_done():
                await interaction.followup.send("The F.M.K ritual failed...*", ephemeral=True)
            else:
                await interaction.response.send_message("The F.M.K ritual failed...", ephemeral=True)

    @app_commands.command(name='pikol', description='Sends a random pikol gif ~meow')
    async def pikol(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

            if not self.PIKOL_GIFS:
                await interaction.followup.send("*sad meow* no gifs available...", ephemeral=True)
                return

            msg = random.choice(self.PIKOL_GIFS)
            await interaction.followup.send(msg)

        except Exception as e:
            self.log_error('pikol', e)
            print(f"Error loading pikol gif: {e}")
            if interaction.response.is_done():
                await interaction.followup.send("Couldn't find a gif... *drops yarn ball*", ephemeral=True)
            else:
                await interaction.response.send_message("Couldn't find a gif... *drops yarn ball*", ephemeral=True)


    @app_commands.command(name="crystal_ball", description="Ask a question and see your fate! 🪄")
    async def crystal_ball(self, interaction: discord.Interaction):
        try:
            if not interaction.guild:
                await interaction.response.send_message("This command can only be used in a server *meow*.", ephemeral=True)
                return

            embed = discord.Embed(
                title="🔮 Crystal Ball 🪄",
                description="Gaze into the swirling mists... What question burns in your heart, meow? Tell Pikol!",
                color=discord.Color.purple()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

            def check(m):
                return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

            try:
                message = await self.bot.wait_for('message', check=check, timeout=60.0)

                # delete the user's question for cleaner chat
                # try:
                #     await message.delete()
                # except discord.Forbidden:
                #     pass # Ignore if we don't have delete perms

                fate = random.choice(self.FATES)
                responses = [
                    f"*Pikol squints...* The swirling mists reveal:\n\n> {fate}",
                    f"*Meow!* The crystal ball shimmers and shows:\n\n> {fate}",
                    f"*Wizardy meow...* Your destiny is written thusly:\n\n> {fate}",
                    f"*Mystic meow~* The stars align to whisper:\n\n> {fate}",
                    f"*An enchanted purr resonates...* Your future holds:\n\n> {fate}"
                ]
                response = random.choice(responses)
                await interaction.channel.send(f"{interaction.user.mention}, you asked the crystal ball... {response}")


            except asyncio.TimeoutError:
                await interaction.edit_original_response(content="You took too long to ask! The mists have faded... *sad meow*", embed=None, view=None)
            except Exception as e:
                self.log_error('crystal_ball_wait', e)
                print(f"Error during crystal_ball wait/reply: {e}")
                await interaction.edit_original_response(content="Something interfered with the magic! *hisses*", embed=None, view=None)


        except Exception as e:
            self.log_error('crystal_ball', e)
            print(f"Error in crystal_ball command: {e}")
            if not interaction.response.is_done():
                 await interaction.response.send_message("The crystal ball is cracked! *panicked meow*", ephemeral=True)

    @app_commands.command(name="crystal_ball_together", description="See your fate with another user! 🔮🪄")
    @app_commands.describe(user="The user you want to see your fate with meow")
    async def crystal_ball_together(self, interaction: discord.Interaction, user: discord.User):
        try:
            await interaction.response.defer()
            if not interaction.guild:
                await interaction.followup.send("This command can only be used in a server *meow*.", ephemeral=True)
                return

            if interaction.user.id == user.id:
                await interaction.followup.send("You can't check your fate with yourself, silly meow!", ephemeral=True)
                return

            fate = random.choice(self.FATES_TOGETHER)

            embed = discord.Embed(
                title="🔮 Crystal Ball - Two Fates Entwined 🪄",
                description=f"{interaction.user.mention} and {user.mention}, the crystal ball reveals your combined path *meeeow*:\n\n> {fate}",
                color=discord.Color.teal()
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            self.log_error('crystal_ball_together', e)
            print(f"Error in crystal_ball_together command: {e}")
            if interaction.response.is_done():
                 await interaction.followup.send("The combined fate reading failed! Too much interference!", ephemeral=True)
            else:
                 await interaction.response.send_message("The combined fate reading failed! Too much interference!", ephemeral=True)


    @app_commands.command(name="magic_beam", description="Cast a magic beam on a user! 🪄")
    @app_commands.describe(user="The user you want to cast a magic beam on meow")
    async def magic_beam(self, interaction: discord.Interaction, user: discord.User):
        try:
            await interaction.response.defer()
            if not interaction.guild:
                await interaction.followup.send("This command can only be used in a server *meow*.", ephemeral=True)
                return

            if user == self.bot.user:
                 await interaction.followup.send("I can't beam myself, meow! Try someone else.", ephemeral=True)
                 return
            if user == interaction.user:
                 await interaction.followup.send("Beaming yourself? That's a bit silly, meow!", ephemeral=True)
                 return


            wizard_pikol = '<:wizardpikol:1328137703044415488>'
            beam_emote = '<:beam:1330639513650855956>'
            empty_space = '<:empty:1330639906199961621>'

            if not wizard_pikol or not beam_emote or not empty_space:
                 await interaction.followup.send("Missing the special emojis for this spell, meow!", ephemeral=True)
                 return


            beam_length = random.randint(4, 9)
            beam_speed = 0.4

            message_content = f"{wizard_pikol}🪄{empty_space*beam_length}{user.mention}"
            message = await interaction.followup.send(message_content, wait=True) 

            for i in range(beam_length):
                await asyncio.sleep(beam_speed)
                current_beam = str(beam_emote) * (i + 1)
                remaining_space = str(empty_space) * (beam_length - 1 - i)
                await message.edit(content=f"{wizard_pikol}🪄{current_beam}{remaining_space}{user.mention}")

            await asyncio.sleep(beam_speed)
            final_beam = str(beam_emote) * beam_length
            await message.edit(content=f"{wizard_pikol}🪄{final_beam}💥 {user.mention}")

            # timeout functionality requires manage roles permission
            # try:
            #     target_member = interaction.guild.get_member(user.id)
            #     if target_member and target_member.top_role < interaction.guild.me.top_role: # Basic check
            #         await target_member.timeout(timedelta(seconds=random.randint(3,7)), reason=f"Hit by a magic beam from {interaction.user.display_name}!")
            # except discord.Forbidden:
            #     await message.edit(content=f"{wizard_pikol}🪄{final_beam}💥 {user.mention}\n*(Pikol tried to zap them, but lacked the power! Meow!)*")
            # except Exception as timeout_error:
            #      print(f"Timeout error: {timeout_error}") # Log other timeout errors
            #      await message.edit(content=f"{wizard_pikol}🪄{final_beam}💥 {user.mention}\n*(The magic fizzled slightly...)*")


            await asyncio.sleep(5)
            try:
                 await message.delete()
            except discord.NotFound:
                 pass
            except discord.Forbidden:
                 pass


        except discord.errors.NotFound:
             self.log_error('magic_beam', "Interaction or channel not found")
             print(f"Error in magic_beam command: Interaction/Channel not found")
        except Exception as e:
            self.log_error('magic_beam', e)
            print(f"Error in magic_beam command: {e}")
            if not interaction.response.is_done():
                 try:
                     await interaction.response.send_message("The magic beam misfired! *poof*", ephemeral=True)
                 except discord.errors.InteractionResponded:
                      pass


async def setup(bot):
    await bot.add_cog(FunCommands(bot))