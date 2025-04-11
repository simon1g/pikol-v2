import discord
from discord import app_commands
from discord.ext import commands
import json
import random
import asyncio
from datetime import timedelta

class FunCommands(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

        try:
            with open('json/pikol_gif.json') as f:
                self.PIKOL_GIFS = json.load(f)
        except FileNotFoundError:
            print("ERROR: json/pikol_gif.json not found!")
            self.PIKOL_GIFS = ["*pikol tries to find a gif but the box is empty...* meow?"]
        except json.JSONDecodeError:
             print("ERROR: json/pikol_gif.json is invalid!")
             self.PIKOL_GIFS = ["*pikol fumbles the gif box...* it's broken!"]

        try:
            with open('json/fates.json', encoding='utf-8') as f:
                self.FATES = json.load(f)
        except FileNotFoundError:
             print("ERROR: json/fates.json not found!")
             self.FATES = ["the crystal ball is cloudy..."]
        except json.JSONDecodeError:
             print("ERROR: json/fates.json is invalid!")
             self.FATES = ["the fates are scrambled..."]

        try:
            with open('json/fates_together.json', encoding='utf-8') as f:
                self.FATES_TOGETHER = json.load(f)
        except FileNotFoundError:
             print("ERROR: json/fates_together.json not found!")
             self.FATES_TOGETHER = ["your combined fate is... friendship? maybe? idk meow."]
        except json.JSONDecodeError:
             print("ERROR: json/fates_together.json is invalid!")
             self.FATES_TOGETHER = ["the threads of your fate are tangled in a confusing way..."]


    def log_error(self, command_name, error):
        self.bot.log_error(command_name, error)

    @app_commands.command(name="fmk", description="Fuck, Marry, Kill!!... Meow~")
    async def fmk(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            if not interaction.guild:
                await interaction.followup.send("this command can only be used in a server *meow*.")
                return

            members = [m for m in interaction.guild.members if not m.bot]

            if len(members) < 3:
                await interaction.followup.send(f"not enough non-bot members ({len(members)} found) in the server to assign. need at least 3, meow!")
                return


            protected_id = 385106645052686339 # Simon's ID 
            triggering_user_id = 1010211178716332183 # Brie's ID
            user_to_exclude_id = 841838035855212585 # Brain's ID

            eligible_members = list(members)

            if interaction.user.id == triggering_user_id:
                eligible_members = [m for m in eligible_members if m.id != user_to_exclude_id]
                if len(eligible_members) < 3:
                     await interaction.followup.send(f"after special exclusions, not enough members ({len(eligible_members)} left) for F.M.K., meow!")
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
                await interaction.followup.send("The F.M.K ritual failed...*")
            else:
                await interaction.response.send_message("The F.M.K ritual failed...")

    @app_commands.command(name='pikol', description='Sends a random pikol gif ~meow')
    async def pikol(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()

            if not self.PIKOL_GIFS:
                await interaction.followup.send("*sad meow* no gifs available...")
                return

            msg = random.choice(self.PIKOL_GIFS)
            await interaction.followup.send(msg)

        except Exception as e:
            self.log_error('pikol', e)
            print(f"Error loading pikol gif: {e}")
            if interaction.response.is_done():
                await interaction.followup.send("couldn't find a gif... *drops magic ball*")
            else:
                await interaction.response.send_message("couldn't find a gif... *drops magic ball*")


    @app_commands.command(name="crystal_ball", description="Ask a question and see your fate! 🪄")
    async def crystal_ball(self, interaction: discord.Interaction):
        try:
            if not interaction.guild:
                await interaction.response.send_message("this command can only be used in a server *meow*")
                return

            embed = discord.Embed(
                title="🔮 Crystal Ball 🪄",
                description="gaze into the future... what question burns in your heart, meow? tell pikol!",
                color=discord.Color.purple()
            )
            initial_message = await interaction.response.send_message(embed=embed)

            def check(m):
                return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

            try:
                message = await self.bot.wait_for('message', check=check, timeout=60.0)
                await interaction.delete_original_response()
                
                fate = random.choice(self.FATES)
                responses = [
                    "*Pikol squints...* The magic mists reveal:",
                    "*Meow!* The crystal ball shimmers and shows:",
                    "*Wizardy meow...* Your destiny is written thusly:",
                    "*Mystic meow~* The stars align to whisper:",
                    "*An enchanted meow resonates...* Your future holds:"
                ]
                response = random.choice(responses)
                
                response_embed = discord.Embed(
                    title="🔮 Your Fate Has Been Revealed 🪄",
                    description=f"{response}\n\n> {fate}",
                    color=discord.Color.purple()
                )
                await message.reply(embed=response_embed)

            except asyncio.TimeoutError:
                await interaction.edit_original_response(content="you took too long to ask! the magic have faded... *sad meow*", embed=None)
            except Exception as e:
                self.log_error('crystal_ball_wait', e)
                print(f"Error during crystal_ball wait/reply: {e}")
                await interaction.edit_original_response(content="something interfered with the magic! *angry meow*", embed=None)

        except Exception as e:
            self.log_error('crystal_ball', e)
            print(f"Error in crystal_ball command: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("the crystal ball is cracked!!! *panicked meow*")

    @app_commands.command(name="crystal_ball_together", description="See your fate with another user! 🔮🪄")
    @app_commands.describe(user="the user you want to see your fate with meow")
    async def crystal_ball_together(self, interaction: discord.Interaction, user: discord.User):
        try:
            await interaction.response.defer()
            if not interaction.guild:
                await interaction.followup.send("this command can only be used in a server *meow*")
                return

            if interaction.user.id == user.id:
                await interaction.followup.send("you can't check your fate with yourself silly... silly meow!")
                return

            fate = random.choice(self.FATES_TOGETHER)

            embed = discord.Embed(
                title="🔮 Crystal Ball - Two Fates Entwined 🪄",
                description=f"{interaction.user.mention} and {user.mention}, the crystal ball reveals your combined path *meeeeeeow*:\n\n> {fate}",
                color=discord.Color.teal()
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            self.log_error('crystal_ball_together', e)
            print(f"Error in crystal_ball_together command: {e}")
            if interaction.response.is_done():
                 await interaction.followup.send("the combined fate reading failed! too much magic interference!")
                 await interaction.response.send_message("the combined fate reading failed! too much *MEOW*!")


    @app_commands.command(name="magic_beam", description="Cast a magic beam on a user! 🪄")
    @app_commands.describe(user="the user you want to cast a magic beam on meow")
    async def magic_beam(self, interaction: discord.Interaction, user: discord.User):
        try:
            await interaction.response.defer()
            if not interaction.guild:
                await interaction.followup.send("this command can only be used in a server *meow*.")
                return

            if user == self.bot.user:
                 await interaction.followup.send("i can't beam myself, meow! try someone else...")
                 return
            if user == interaction.user:
                 await interaction.followup.send("beaming yourself??? that's a bit silly, meow!")
                 return


            wizard_pikol = '<:wizardpikol:1328137703044415488>'
            beam_emote = '<:beam:1330639513650855956>'
            empty_space = '<:empty:1330639906199961621>'

            if not wizard_pikol or not beam_emote or not empty_space:
                 await interaction.followup.send("missing the special emojis for this spell, meow!")
                 return


            beam_length = random.randint(4, 9)
            beam_speed = 0.4

            message_content = f"{wizard_pikol}.🪄{empty_space*beam_length}{user.mention}"
            message = await interaction.followup.send(message_content, wait=True) 

            for i in range(beam_length):
                await asyncio.sleep(beam_speed)
                current_beam = str(beam_emote) * (i + 1)
                remaining_space = str(empty_space) * (beam_length - 1 - i)
                await message.edit(content=f"{wizard_pikol}.🪄{current_beam}{remaining_space}{user.mention}")

            await asyncio.sleep(beam_speed)
            final_beam = str(beam_emote) * beam_length
            await message.edit(content=f"{wizard_pikol}.🪄{final_beam}💥")

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
                     await interaction.response.send_message("the magic beam misfired!!! *poof*")
                 except discord.errors.InteractionResponded:
                      pass


async def setup(bot):
    await bot.add_cog(FunCommands(bot))