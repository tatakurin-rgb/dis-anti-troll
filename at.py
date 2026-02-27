import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime
import threading

# =====================
# 設定
# =====================
LOG_CHANNEL_ID = 1381633140623151300
TIMEOUT_MINUTES = 1

NG_FILE = "ng_words.json"
ALLOW_FILE = "allowed_users.json"

# =====================
# JSON ユーティリティー
# =====================
def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# =====================
# インテント関係
# =====================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =====================
# 権限判定
# =====================
def is_allowed(user: discord.Member):
    if user.guild_permissions.administrator:
        return True
    allowed = load_json(ALLOW_FILE, [])
    return user.id in allowed

# =====================
# UIボタン
# =====================
import datetime
import discord

class PunishView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def get_target(self, interaction: discord.Interaction):
        try:
            user_id = int(interaction.message.embeds[0].footer.text)
        except (IndexError, ValueError, AttributeError):
            return None

        member = interaction.guild.get_member(user_id)
        if member is None:
            try:
                member = await interaction.guild.fetch_member(user_id)
            except discord.NotFound:
                return None

        return member

    # ---------------- BAN ----------------
    @discord.ui.button(
        label="🔨 BAN",
        style=discord.ButtonStyle.danger,
        custom_id="ban_button"
    )
    async def ban(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer(ephemeral=True)

        member = await self.get_target(interaction)
        if member is None:
            return await interaction.followup.send("ユーザーが見つかりません", ephemeral=True)

        await member.ban(reason="Botによるオートモデレーション")
        await interaction.followup.send("対象をBANしました", ephemeral=True)

    # ---------------- TIMEOUT ----------------
    @discord.ui.button(
        label="⏳ TO",
        style=discord.ButtonStyle.gray,
        custom_id="timeout_button"
    )
    async def timeout(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer(ephemeral=True)

        member = await self.get_target(interaction)
        if member is None:
            return await interaction.followup.send("ユーザーが見つかりません", ephemeral=True)

        until = discord.utils.utcnow() + datetime.timedelta(minutes=TIMEOUT_MINUTES)
        await member.timeout(until)

        await interaction.followup.send("対象をTOしました", ephemeral=True)

    # ---------------- UNTIMEOUT ----------------
    @discord.ui.button(
        label="✅ TO解除",
        style=discord.ButtonStyle.green,
        custom_id="untimeout_button"
    )
    async def untimeout(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer(ephemeral=True)

        member = await self.get_target(interaction)
        if member is None:
            return await interaction.followup.send("ユーザーが見つかりません", ephemeral=True)

        await member.timeout(None)

        await interaction.followup.send("タイムアウトを解除しました", ephemeral=True)
# =====================
# 禁止ワード検知
# =====================
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    ng_words = load_json(NG_FILE, [])
    if any(word.lower() in message.content.lower() for word in ng_words):
        member = message.author
        until = discord.utils.utcnow() + datetime.timedelta(minutes=TIMEOUT_MINUTES)
        await member.timeout(until)

        log_channel = await bot.fetch_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="🚨 NGワードを検知",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="ユーザー", value=member.mention)
            embed.add_field(name="内容", value=message.content, inline=False)
            embed.set_footer(text=str(member.id))
                             
            await log_channel.send(embed=embed, view=PunishView())

    await bot.process_commands(message)

# =====================
# コマンド
# =====================
@bot.tree.command(name="add_ng", description="禁止ワードを追加します")
async def add_ng(interaction: discord.Interaction, word: str):
    if not is_allowed(interaction.user):
        return await interaction.response.send_message("権限がありません", ephemeral=True)

    ng = load_json(NG_FILE, [])
    if word not in ng:
        ng.append(word)
        save_json(NG_FILE, ng)

    await interaction.response.send_message(f"禁止ワードを追加しました: `{word}`", ephemeral=True)

@bot.tree.command(name="remove_ng", description="禁止ワードを削除します")
async def remove_ng(interaction: discord.Interaction, word: str):
    if not is_allowed(interaction.user):
        return await interaction.response.send_message("権限がありません", ephemeral=True)

    ng = load_json(NG_FILE, [])
    if word in ng:
        ng.remove(word)
        save_json(NG_FILE, ng)

    await interaction.response.send_message(f"禁止ワードを削除しました: `{word}`", ephemeral=True)

@bot.tree.command(name="list_ng", description="禁止ワードを確認します")
async def list_ng(interaction: discord.Interaction):
    ng = load_json(NG_FILE, [])
    await interaction.response.send_message(", ".join(ng) or "なし", ephemeral=True)

@bot.tree.command(name="allow_mod", description="指定ユーザーにBot操作を許可します")
async def allow_mod(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("これは管理者専用です", ephemeral=True)

    allowed = load_json(ALLOW_FILE, [])
    if user.id not in allowed:
        allowed.append(user.id)
        save_json(ALLOW_FILE, allowed)

    await interaction.response.send_message(f"{user.mention} のBOT操作を許可しました", ephemeral=True)

# =====================
# Bot Standby!
# =====================
@bot.event
async def on_ready():
    if not hasattr(bot, "startup_time"):
        bot.startup_time = True
        print(f"Logged in as {bot.user}")
# =====================
# intents確認用
# =====================

# =====================
# 起動
# =====================
token = os.getenv("DISCORD_TOKEN") or os.getenv("DIS_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN not set")

bot.run(token)
