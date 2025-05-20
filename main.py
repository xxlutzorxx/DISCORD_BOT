import discord
from discord.ext import commands
from discord import ui
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

CREATED_CATEGORY_ID = 1365361855069159530
CLAIMED_CATEGORY_ID = 1365361855069159531
CLOSED_CATEGORY_ID = 1365361855069159532

SUPPORT_ROLE_NAME = "Support"
TICKET_HANDLER_ROLE_NAME = "Ticket-Handler"
MEMBER_ROLE_NAME = "Member"
LOG_CHANNEL_NAME = "transkripte"

regel_nachricht_id = None

def get_ticket_buttons(disable_claim=False):
    view = ui.View(timeout=None)
    view.add_item(ui.Button(label="🔒 Ticket schließen", style=discord.ButtonStyle.red, custom_id="close_ticket"))
    view.add_item(
        ui.Button(
            label="👨‍💻 Ticket claimen",
            style=discord.ButtonStyle.blurple,
            custom_id="claim_ticket",
            disabled=disable_claim
        )
    )
    return view

@bot.command()
@commands.has_permissions(administrator=True)
async def regeln(ctx):
    global regel_nachricht_id
    regeln_text = (
        "**📖 Server-Regeln – Bitte aufmerksam lesen!**\n\n"
        " **1. Allgemeiner Respekt und Umgang**\n"
        "• Jeder wird respektvoll behandelt – keine Beleidigungen, Diskriminierung oder Mobbing.\n"
        "• Freundliche Sprache ist Pflicht.\n\n"
        " **2. Kein Spam oder Werbung**\n"
        "• Keine Wiederholungen oder Flooding.\n"
        "• Werbung nur mit Erlaubnis im richtigen Channel.\n"
        "• Eigenwerbung nur in erlaubten Bereichen.\n\n"
        " **3. Themenbezogene Kommunikation**\n"
        "• Nutzt Channels themengerecht (z. B. Gaming, Support).\n"
        "• Bleibt beim Thema und respektiert andere.\n\n"
        " **4. Inhalte und Medien**\n"
        "• Keine NSFW-Inhalte außerhalb freigegebener Bereiche.\n"
        "• Achtet auf Urheberrechte bei Medien.\n\n"
        " **5. Voice & Video**\n"
        "• Vermeidet störende Geräusche.\n"
        "• Mikrofon stummschalten, wenn es sein muss.\n\n"
        " **6. Datenschutz**\n"
        "• Keine persönlichen Daten ohne Einwilligung veröffentlichen.\n"
        "• Respektiert die Privatsphäre anderer.\n\n"
        " **7. Moderation**\n"
        "• Mods haben das letzte Wort.\n"
        "• Regelverstöße führen zu Konsequenzen.\n\n"
        " **8. Feedback**\n"
        "• Vorschläge sind willkommen. Nutzt den Feedback-Channel.\n\n"
        " **Reagiere mit ✅, um die Regeln zu akzeptieren und die 'Member'-Rolle zu erhalten.**"
    )
    nachricht = await ctx.send(regeln_text)
    regel_nachricht_id = nachricht.id
    await nachricht.add_reaction("✅")

@bot.event
async def on_raw_reaction_add(payload):
    if payload.message_id != regel_nachricht_id:
        return
    if str(payload.emoji) == "✅":
        guild = bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return
        rolle = discord.utils.get(guild.roles, name=MEMBER_ROLE_NAME)
        if rolle:
            await member.add_roles(rolle)

class TicketView(ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=None)
        self.author_id = author_id

    @ui.button(label="🎟️ Support", style=discord.ButtonStyle.green, custom_id="ticket_support")
    async def support(self, interaction: discord.Interaction, button: ui.Button):
        await self.create_ticket(interaction, "Support")

    @ui.button(label="🛠️ Developer", style=discord.ButtonStyle.blurple, custom_id="ticket_developer")
    async def developer(self, interaction: discord.Interaction, button: ui.Button):
        await self.create_ticket(interaction, "Developer")

    @ui.button(label="📄 Bewerbung", style=discord.ButtonStyle.gray, custom_id="ticket_bewerbung")
    async def bewerbung(self, interaction: discord.Interaction, button: ui.Button):
        await self.create_ticket(interaction, "Bewerbung")

    async def create_ticket(self, interaction: discord.Interaction, typ: str):
        guild = interaction.guild
        member = interaction.user
        support_role = discord.utils.get(guild.roles, name=SUPPORT_ROLE_NAME)
        category = discord.utils.get(guild.categories, id=CREATED_CATEGORY_ID)

        channel_name = f"ticket-{typ.lower()}-{member.name}".replace(" ", "-").lower()
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            support_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        ticket_channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites, topic=f"{typ} Ticket von {member}")

        await ticket_channel.send(
            embed=discord.Embed(
                title=f"{typ}-Ticket",
                description=f"{member.mention}, ein {typ}-Ticket wurde erstellt. Ein Teammitglied wird sich bald melden.",
                color=discord.Color.green()
            ),
            view=get_ticket_buttons()
        )
        await interaction.response.send_message(f"✅ Dein {typ}-Ticket wurde erstellt: {ticket_channel.mention}", ephemeral=True)
        await asyncio.sleep(10)
        await interaction.delete_original_response()

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return

    custom_id = interaction.data.get("custom_id")
    guild = interaction.guild
    member = interaction.user
    channel = interaction.channel

    if not channel.name.startswith("ticket-"):
        return

    ticket_handler_role = discord.utils.get(guild.roles, name=TICKET_HANDLER_ROLE_NAME)
    support_role = discord.utils.get(guild.roles, name=SUPPORT_ROLE_NAME)
    log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)

    messages = [msg async for msg in channel.history(limit=50)]
    starter_message = next((msg for msg in messages if msg.author == bot.user and msg.components), None)

    if custom_id == "close_ticket":
        closed_category = discord.utils.get(guild.categories, id=CLOSED_CATEGORY_ID)
        if ticket_handler_role and ticket_handler_role in member.roles:
            await member.remove_roles(ticket_handler_role)
        await channel.edit(category=closed_category, topic=f"Geschlossen von {member}")
        if log_channel:
            await log_channel.send(f"📌 Ticket {channel.name} wurde geschlossen von {member.mention}")
        await interaction.response.send_message("✅ Ticket wurde geschlossen und verschoben.", ephemeral=True)

    elif custom_id == "claim_ticket":
        claimed_category = discord.utils.get(guild.categories, id=CLAIMED_CATEGORY_ID)
        if ticket_handler_role and ticket_handler_role not in member.roles:
            await member.add_roles(ticket_handler_role)
        await channel.edit(category=claimed_category, topic=f"Beansprucht von {member}")
        await interaction.response.send_message(f"✅ Ticket wurde von {member.mention} beansprucht.", ephemeral=True)

        if starter_message:
            await starter_message.edit(view=get_ticket_buttons(disable_claim=True))

@bot.command()
@commands.has_permissions(administrator=True)
async def ticketpanel(ctx):
    view = TicketView(ctx.author.id)
    embed = discord.Embed(
        title="📩 Ticket System",
        description="Klicke auf einen der unten angezeigten Buttons. Ein Teammitglied wird sich gleich um dich kümmern:",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed, view=view)

bot.run(os.getenv("DISCORD_TOKEN"))
