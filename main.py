import os
import json
import asyncio
from datetime import datetime
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
from dotenv import load_dotenv
import discord

# --- Load environment ---
load_dotenv()
TOKEN = os.getenv("TOKEN")
GUILD_ID = 1389641561578541196

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Flask Keep-alive ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run).start()

# --- Data ---
valor_points = {}
try:
    with open('valor_points.json', 'r') as f:
        valor_points = json.load(f)
    print("✅ Loaded existing valor points data")
except (FileNotFoundError, json.JSONDecodeError):
    print("⚠️ No existing data found, starting fresh")

rank_thresholds = {
    "Chief Warrant Officer": 200,
    "Warrant Officer": 140,
    "Petty Officer 1st Class": 75,
    "Petty Officer 2nd Class": 50,
    "Petty Officer 3rd Class": 25,
    "Leading Seaman": 15,
    "Able Seaman": 5,
}

valid_ranks = [
    "Admiral", "Vice Admiral", "Rear Admiral", "Commodore",
    "Captain", "Commander", "Lieutenant Commander", "Lieutenant", "Ensign",
    "Midshipman", "Chief Warrant Officer", "Petty Officer 1st Class",
    "Petty Officer 2nd Class", "Petty Officer 3rd Class", "Leading Seaman",
    "Able Seaman", "Ordinary Seaman", "Warrant Officer",
    "Senior Chief Petty Officer", "Chief Petty Officer"
]

# --- Backup System ---
def save_backup():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"valor_backup_{timestamp}.json"
    with open(filename, 'w') as f:
        json.dump(valor_points, f, indent=4)
    return filename

@tasks.loop(minutes=1)
async def backup_leaderboard():
    try:
        backup_channel = discord.utils.get(bot.get_all_channels(), name="backup")
        if backup_channel is None:
            print("⚠️ Backup channel not found")
            return
        filename = save_backup()
        with open(filename, 'rb') as f:
            await backup_channel.send(
                f"⏱️ Minute Leaderboard Backup ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
                file=discord.File(f, filename)
            )
        print(f"✅ Successfully backed up leaderboard to {filename}")
    except Exception as e:
        print(f"❌ Backup failed: {e}")

# --- Valor Logic ---
def get_valor(member_id):
    return valor_points.get(str(member_id), 0)

def set_valor(member_id, amount):
    valor_points[str(member_id)] = amount

async def auto_promote(guild, member):
    valor = get_valor(member.id)
    for rank, threshold in sorted(rank_thresholds.items(), key=lambda x: x[1]):
        role = discord.utils.get(guild.roles, name=rank)
        if role and valor >= threshold and role not in member.roles:
            for r_name in rank_thresholds:
                r = discord.utils.get(guild.roles, name=r_name)
                if r in member.roles and r != role:
                    await member.remove_roles(r)
            await member.add_roles(role)
            try:
                await member.send(f"You've been promoted to **{rank}** with {valor} Valor!")
            except:
                pass

# --- Permission Check ---
def is_high_command():
    async def predicate(ctx):
        high_ranks = ["Admiral", "Vice Admiral"]
        user_roles = [role.name for role in ctx.author.roles]
        return any(rank in user_roles for rank in high_ranks)
    return commands.check(predicate)

# --- Events ---
@bot.event
async def on_ready():
    print(f"🤖 {bot.user} is online!")
    try:
        await bot.sync_commands()
        print("✅ Slash commands synced!")
    except Exception as e:
        print(f"❌ Sync failed: {e}")
    backup_leaderboard.start()

# --- Slash Commands ---
@bot.slash_command(name="test", description="Ping test")
async def test(ctx):
    await ctx.respond("✅ Bot is responding!", ephemeral=True)

@bot.slash_command(name="addvalor", description="Add Valor points")
@is_high_command()
async def addvalor(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        await ctx.respond("Valor must be > 0.", ephemeral=True)
        return
    current = get_valor(member.id)
    set_valor(member.id, current + amount)
    await ctx.respond(f"Added {amount} Valor to {member.display_name}. Total: {current + amount}")
    await auto_promote(ctx.guild, member)

@bot.slash_command(name="removevalor", description="Remove Valor points")
@is_high_command()
async def removevalor(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        await ctx.respond("Amount must be > 0.", ephemeral=True)
        return
    current = get_valor(member.id)
    new_valor = max(0, current - amount)
    set_valor(member.id, new_valor)
    await ctx.respond(f"Removed {amount} Valor from {member.display_name}. Total: {new_valor}")

@bot.slash_command(name="rank", description="Assign a rank")
@is_high_command()
async def rank(ctx, member: discord.Member, rank: str):
    if rank not in valid_ranks:
        await ctx.respond(f"❌ Invalid rank. Valid: {', '.join(valid_ranks)}", ephemeral=True)
        return
    role = discord.utils.get(ctx.guild.roles, name=rank)
    if not role:
        await ctx.respond(f"Role `{rank}` not found on server.", ephemeral=True)
        return
    for r_name in valid_ranks:
        r = discord.utils.get(ctx.guild.roles, name=r_name)
        if r in member.roles and r != role:
            await member.remove_roles(r)
    await member.add_roles(role)
    await ctx.respond(f"{member.display_name} assigned to **{rank}**.")

@bot.slash_command(name="leaderboard", description="Show Valor leaderboard")
async def leaderboard(ctx):
    if not valor_points:
        await ctx.respond("No Valor records yet.")
        return
    lines = []
    for user_id, valor in valor_points.items():
        member = ctx.guild.get_member(int(user_id))
        if member:
            lines.append(f"**{member.display_name}** — {valor} V")
        else:
            lines.append(f"Unknown User ({user_id}) — {valor} V")
    chunks = [lines[i:i+25] for i in range(0, len(lines), 25)]
    for chunk in chunks:
        await ctx.respond("🏆 **Valor Leaderboard:**\n" + "\n".join(chunk))

# --- Start Bot ---
keep_alive()
bot.run(TOKEN)
