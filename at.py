import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()



TIMEOUT_MINUTES = 10
NG_FILE = "ng_words.json"
MOD_FILE = "bot_mods.json"
LOG_FILE = "log_channel.json"

# =================
# JSON util
# =================
def load_json(file, default):
    if not os.path.exists(file):
        with open(file, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

NG_WORDS = set(load_json(NG_FILE, []))
BOT_MODS = set(load_json(MOD_FILE, []))
LOG_CHANNEL = load_json(LOG_FILE, {"channel_id": None})

# =================
# Bot設定
# =================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =================
# 権限
# =================
def is_bot_admin(member: discord.Member):
    return member.guild_permissions.administrator or member.id in BOT_MODS

# =================
# View（ボタン）
# =================
class ModActionView(discord.ui.View):
    def __init__(self, target: discord.Member):
        super().__init__(timeout=None)
        self.target = target
        self.handled = False

    async def disable_all(self, interaction: discord.Interaction, action: str):
        for item in self.children:
            item.disabled = True

        embed = interaction.message.embeds[0]
        embed.add_field(
            name="対応",
            value=f"{action}\n実行者: {interaction.user.mention}",
            inline=False
        )
        embed.color = discord.Color.green()

        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="🔨 対象をBAN", style=discord.ButtonStyle.danger)
    async def ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.handled:
            return

        if not is_bot_admin(interaction.user):
            await interaction.response.send_message(
                "❌ 権限がありません！", ephemeral=True
            )
            return

        self.handled = True
        await self.target.ban(reason="ログからBAN")
        await self.disable_all(interaction, "🔨 BAN")

        await interaction.response.send_message(
            f"{self.target.mention} をBANしました", ephemeral=True
        )

    @discord.ui.button(label="⏱️ TO解除", style=discord.ButtonStyle.success)
    async def untimeout(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.handled:
            return

        if not is_bot_admin(interaction.user):
            await interaction.response.send_message(
                "❌ 権限がありません!", ephemeral=True
            )
            return

        self.handled = True
        await self.target.timeout(None)
        await self.disable_all(interaction, "⏱️ タイムアウト解除")

        await interaction.response.send_message(
            f"{self.target.mention} のタイムアウトを解除しました",
            ephemeral=True
        )


# =================
# 起動
# =================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot is Ready!: {bot.user}")

# =================
# ログチャンネル設定
# =================
@bot.tree.command(name="set_log_ch", description="ログの送信先を設定")
async def set_log_channel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("管理者専用", ephemeral=True)
        return

    LOG_CHANNEL["channel_id"] = interaction.channel.id
    save_json(LOG_FILE, LOG_CHANNEL)

    await interaction.response.send_message(
        f"✅ このチャンネルをログ送信先に設定しました",
        ephemeral=True
    )

# =================
# メッセージ監視
# =================
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if message.author.guild_permissions.administrator:
        return

    content = message.content.lower()

    for word in NG_WORDS:
        if word in content:
            await message.delete()

            await message.author.timeout(
                timedelta(minutes=TIMEOUT_MINUTES),
                reason=f"NGワード: {word}"
            )

            # ログ送信
            channel_id = LOG_CHANNEL.get("channel_id")
            if channel_id:
                log_ch = message.guild.get_channel(channel_id)
                if log_ch:
                    embed = discord.Embed(
                        title="🚨 NGワードを検出",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="ユーザー", value=message.author.mention)
                    embed.add_field(name="ワード", value=word)
                    embed.add_field(name="チャンネル", value=message.channel.mention)
                    embed.add_field(name="内容", value=message.content, inline=False)

                    await log_ch.send(
                        embed=embed,
                        view=ModActionView(message.author)
                    )
            break

    await bot.process_commands(message)
    
token = os.getenv("DIS_TOKEN")
if not token:
    raise RuntimeError("DIS_TOKEN is not set")

bot.run(token)



