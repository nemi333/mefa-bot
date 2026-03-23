import discord
import os
import aiosqlite
import aiohttp
from discord.ext import tasks
from dotenv import load_dotenv

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

if not DISCORD_TOKEN or DISCORD_TOKEN == "twoj_token_bota_tutaj":
    print("BŁĄD: Musisz podać DISCORD_TOKEN w pliku .env!")
    exit(1)

# ─────────────────────────────────────────────
# Hardcoded config (channel/server IDs)
# ─────────────────────────────────────────────
GUILD_ID            = None           # None = działa na wszystkich serwerach
WELCOME_CHANNEL_ID  = 1485641038566653993
ANNOUNCE_CHANNEL_ID = 1485620102845173822
ARMA_BOARDS = [
    {"bm_server_id": "35744919", "channel_id": 1485628780629196832},
    {"bm_server_id": "35747535", "channel_id": 1485628780629196832},
]

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True  # Wymagane do on_member_join

bot = discord.Bot(intents=intents)

RANKS = [
    {"name": "Szeregowy",                  "required_minutes": 25},
    {"name": "Starszy szeregowy",           "required_minutes": 55},
    {"name": "Starszy szeregowy specjalista","required_minutes": 90},
    {"name": "Kapral",                      "required_minutes": 130},
    {"name": "Starszy kapral",              "required_minutes": 175},
    {"name": "Plutonowy",                   "required_minutes": 225},
    {"name": "Sierżant",                    "required_minutes": 280},
    {"name": "Starszy sierżant",            "required_minutes": 340},
    {"name": "Młodszy chorąży",             "required_minutes": 405},
    {"name": "Chorąży",                     "required_minutes": 475},
    {"name": "Starszy chorąży",             "required_minutes": 550},
    {"name": "Starszy chorąży sztabowy",    "required_minutes": 630},
    {"name": "Podporucznik",                "required_minutes": 715},
    {"name": "Porucznik",                   "required_minutes": 805},
    {"name": "Kapitan",                     "required_minutes": 900},
    {"name": "Major",                       "required_minutes": 1000},
    {"name": "Podpułkownik",                "required_minutes": 1105},
    {"name": "Pułkownik",                   "required_minutes": 1215},
    {"name": "Generał brygady",             "required_minutes": 1330},
    {"name": "Generał dywizji",             "required_minutes": 1450},
    {"name": "Generał broni",               "required_minutes": 1575},
    {"name": "Generał",                     "required_minutes": 1705},
]

RANK_NAMES = {r["name"] for r in RANKS}


async def init_db():
    async with aiosqlite.connect("database.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id     INTEGER PRIMARY KEY,
                total_minutes INTEGER DEFAULT 0,
                rank_index  INTEGER DEFAULT -1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS arma_boards (
                rowid       INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER,
                channel_id  INTEGER,
                message_id  INTEGER,
                bm_server_id TEXT,
                UNIQUE(guild_id, bm_server_id)
            )
        """)
        await db.commit()


# ─────────────────────────────────────────────
# Voice time tracker (co 1 min)
# ─────────────────────────────────────────────

@tasks.loop(minutes=1.0)
async def voice_time_tracker():
    async with aiosqlite.connect("database.db") as db:
        for guild in bot.guilds:
            for vc in guild.voice_channels:
                if guild.afk_channel and vc.id == guild.afk_channel.id:
                    continue
                for member in vc.members:
                    if member.bot:
                        continue

                    await db.execute("""
                        INSERT INTO user_stats (user_id, total_minutes, rank_index)
                        VALUES (?, 1, -1)
                        ON CONFLICT(user_id)
                        DO UPDATE SET total_minutes = total_minutes + 1
                    """, (member.id,))

                    async with db.execute(
                        "SELECT total_minutes, rank_index FROM user_stats WHERE user_id = ?",
                        (member.id,)
                    ) as cur:
                        row = await cur.fetchone()

                    if not row:
                        continue
                    total_minutes, db_rank_index = row

                    new_rank_index = -1
                    for i, rank in enumerate(RANKS):
                        if total_minutes >= rank["required_minutes"]:
                            new_rank_index = i
                        else:
                            break

                    if new_rank_index == -1:
                        continue

                    target_name = RANKS[new_rank_index]["name"]
                    target_role = discord.utils.get(guild.roles, name=target_name)
                    if not target_role:
                        continue

                    user_rank_roles = [r for r in member.roles if r.name in RANK_NAMES]
                    to_remove = [r for r in user_rank_roles if r.name != target_name]
                    has_role  = any(r.name == target_name for r in user_rank_roles)

                    if not has_role or to_remove:
                        try:
                            if not has_role:
                                await member.add_roles(target_role)
                            if to_remove:
                                await member.remove_roles(*to_remove)
                        except discord.Forbidden:
                            pass

                    if new_rank_index > db_rank_index:
                        await db.execute(
                            "UPDATE user_stats SET rank_index = ? WHERE user_id = ?",
                            (new_rank_index, member.id)
                        )
                        ann_ch = guild.get_channel(ANNOUNCE_CHANNEL_ID)
                        if ann_ch:
                            try:
                                await ann_ch.send(
                                    f"🎉 Gratulacje {member.mention}! Osiągnąłeś/aś nową rangę: "
                                    f"**{target_name}** po **{total_minutes}** minutach na kanałach głosowych! 🎙️"
                                )
                            except discord.Forbidden:
                                pass

        await db.commit()


@voice_time_tracker.before_loop
async def before_voice():
    await bot.wait_until_ready()


# ─────────────────────────────────────────────
# Arma Reforger board (co 5 min)
# ─────────────────────────────────────────────

async def fetch_arma_data(bm_server_id: str) -> dict | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.battlemetrics.com/servers/{bm_server_id}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        attrs = data["data"]["attributes"]
        return {
            "name":        attrs.get("name", "N/A"),
            "map":         attrs.get("details", {}).get("reforger", {}).get("scenarioName", "N/A"),
            "players":     attrs.get("players", 0),
            "max_players": attrs.get("maxPlayers", 0),
        }
    except Exception as e:
        print(f"Błąd Battlemetrics ({bm_server_id}): {e}")
        return None


def build_arma_embed(info: dict, bm_server_id: str, playing_members: list) -> discord.Embed:
    embed = discord.Embed(
        title="🎮 Arma Reforger",
        description=f"**{info['name']}**",
        color=discord.Color.from_rgb(139, 0, 0)
    )
    embed.add_field(name="🗺️ Mapa",           value=info["map"], inline=True)
    embed.add_field(name="👥 Gracze",          value=f"**{info['players']}** / **{info['max_players']}**", inline=True)
    if playing_members:
        embed.add_field(name="🛡️ Nasi Online", value="\n".join(playing_members), inline=False)
    else:
        embed.add_field(name="🛡️ Nasi Online", value="Nikt z naszego Discorda nie gra teraz.", inline=False)
    embed.set_footer(text=f"ID: {bm_server_id} • Aktualizacja co 5 min")
    return embed


@tasks.loop(minutes=5.0)
async def arma_board_updater():
    async with aiosqlite.connect("database.db") as db:
        async with db.execute(
            "SELECT guild_id, channel_id, message_id, bm_server_id FROM arma_boards"
        ) as cur:
            rows = await cur.fetchall()

    for guild_id, channel_id, message_id, bm_server_id in rows:
        guild = bot.get_guild(guild_id)
        if not guild:
            continue
        channel = guild.get_channel(channel_id)
        if not channel:
            continue
        try:
            msg = await channel.fetch_message(message_id)
        except discord.NotFound:
            continue

        info = await fetch_arma_data(bm_server_id)
        if not info:
            continue

        playing = [
            f"• {m.mention}" for m in guild.members
            if not m.bot and any(
                getattr(a, "name", "") == "Arma Reforger"
                for a in m.activities
            )
        ]
        embed = build_arma_embed(info, bm_server_id, playing)
        try:
            await msg.edit(embed=embed)
        except discord.HTTPException:
            pass


@arma_board_updater.before_loop
async def before_arma():
    await bot.wait_until_ready()


# ─────────────────────────────────────────────
# Slash commands
# ─────────────────────────────────────────────

@bot.slash_command(name="ranga", description="Twój czas na głosowych i postęp do nowej rangi")
async def cmd_ranga(ctx: discord.ApplicationContext):
    await ctx.defer()
    async with aiosqlite.connect("database.db") as db:
        async with db.execute(
            "SELECT total_minutes FROM user_stats WHERE user_id = ?", (ctx.author.id,)
        ) as cur:
            row = await cur.fetchone()
    total_minutes = row[0] if row else 0

    current_rank = None
    next_rank = RANKS[0]
    for i, rank in enumerate(RANKS):
        if total_minutes >= rank["required_minutes"]:
            current_rank = rank
            next_rank = RANKS[i + 1] if i + 1 < len(RANKS) else None
        else:
            break

    if next_rank:
        base = current_rank["required_minutes"] if current_rank else 0
        progress = total_minutes - base
        span = next_rank["required_minutes"] - base
        pct = min(100, int(progress / span * 100))
        bar = "🟩" * (pct // 10) + "⬛" * (10 - pct // 10)
        brakuje = next_rank["required_minutes"] - total_minutes

        embed = discord.Embed(title="Twoja Ranga 🎖️", color=discord.Color.blue())
        embed.description = (
            f"⏱️ **Czas na kanałach:** {total_minutes} min\n"
            f"🎖️ **Aktualna ranga:** {current_rank['name'] if current_rank else 'Brak'}\n"
            f"⬆️ **Następna ranga:** {next_rank['name']} (brakuje {brakuje} min)\n\n"
            f"**Postęp:** {bar} {pct}%"
        )
    else:
        embed = discord.Embed(title="Twoja Ranga 🎖️", color=discord.Color.gold())
        embed.description = (
            f"⏱️ **Czas na kanałach:** {total_minutes} min\n"
            f"🎖️ **Aktualna ranga:** {current_rank['name']}\n\n"
            f"🎉 Osiągnąłeś/aś najwyższą rangę!"
        )
    await ctx.followup.send(embed=embed)


@bot.slash_command(name="ustaw_arma_tablice", description="Stawia tablicę statystyk Arma (Admin)")
async def cmd_ustaw_arma(ctx: discord.ApplicationContext, battlemetrics_server_id: str):
    if not ctx.author.guild_permissions.administrator:
        return await ctx.respond("❌ Wymagane uprawnienia Administratora.", ephemeral=True)
    await ctx.defer()

    info = await fetch_arma_data(battlemetrics_server_id)
    if not info:
        return await ctx.followup.send("❌ Nie udało się pobrać danych z Battlemetrics. Sprawdź ID serwera.")

    embed = build_arma_embed(info, battlemetrics_server_id, [])
    msg = await ctx.followup.send(embed=embed)

    async with aiosqlite.connect("database.db") as db:
        await db.execute("""
            INSERT INTO arma_boards (guild_id, channel_id, message_id, bm_server_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, bm_server_id)
            DO UPDATE SET channel_id=excluded.channel_id, message_id=excluded.message_id
        """, (ctx.guild.id, msg.channel.id, msg.id, battlemetrics_server_id))
        await db.commit()

    if not arma_board_updater.is_running():
        arma_board_updater.start()


# ─────────────────────────────────────────────
# Events
# ─────────────────────────────────────────────

@bot.event
async def on_member_join(member: discord.Member):
    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if not channel:
        return
    text = (
        f"Czołem {member.mention}! Witaj w naszej ekipie.\n\n"
        f"Serwery na których gramy to PLG #1 i PLG#2 (częściej na #2)\n\n"
        f"Jeśli masz pytania lub jesteś totalnie świeży w Arma Reforger to dobrze trafiłeś/aś! "
        f"Z naszą ekipą bez problemu nauczysz się podstaw lub rozwiniesz swoje umiejętności 🫡\n\n"
        f"Do zobaczenia w bitce!"
    )
    gif_embed = discord.Embed(color=discord.Color.from_rgb(139, 0, 0))
    gif_embed.set_image(url="https://media.tenor.com/pYtOt3XQMsYAAAAC/ar-ataka.gif")
    try:
        await channel.send(content=text, embed=gif_embed)
    except discord.Forbidden:
        pass


@bot.event
async def on_ready():
    await init_db()
    print("=" * 30)
    print(f"✅ Bot gotowy! Zalogowano jako {bot.user}")
    print("=" * 30)

    # Tworzenie brakujących ról rang
    for guild in bot.guilds:
        for rank in RANKS:
            if not discord.utils.get(guild.roles, name=rank["name"]):
                try:
                    await guild.create_role(name=rank["name"], reason="Auto-tworzenie rangi przez bota")
                    print(f"  + Stworzono rolę: {rank['name']}")
                except discord.Forbidden:
                    print(f"  - Brak uprawnień do tworzenia ról na {guild.name}")

    # Inicjalizacja tablic Arma z konfiguracji
    async with aiosqlite.connect("database.db") as db:
        for guild in bot.guilds:
            for board in ARMA_BOARDS:
                channel = guild.get_channel(board["channel_id"])
                if not channel:
                    continue
                async with db.execute(
                    "SELECT message_id FROM arma_boards WHERE guild_id=? AND bm_server_id=?",
                    (guild.id, board["bm_server_id"])
                ) as cur:
                    existing = await cur.fetchone()
                if existing:
                    continue  # Tablica już istnieje, nie twórzmy duplikatu
                info = await fetch_arma_data(board["bm_server_id"])
                if not info:
                    continue
                embed = build_arma_embed(info, board["bm_server_id"], [])
                try:
                    msg = await channel.send(embed=embed)
                    await db.execute("""
                        INSERT INTO arma_boards (guild_id, channel_id, message_id, bm_server_id)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(guild_id, bm_server_id)
                        DO UPDATE SET channel_id=excluded.channel_id, message_id=excluded.message_id
                    """, (guild.id, channel.id, msg.id, board["bm_server_id"]))
                    print(f"  + Wysłano tablicę Arma (serwer BM: {board['bm_server_id']})")
                except discord.Forbidden:
                    print(f"  - Brak uprawnień do wysyłania na kanale {channel.id}")
        await db.commit()

    print("=" * 30)
    if not voice_time_tracker.is_running():
        voice_time_tracker.start()
        print("▶️ Uruchomiono śledzenie czasu głosowego!")
    if not arma_board_updater.is_running():
        arma_board_updater.start()
        print("▶️ Uruchomiono aktualizację tablic Arma!")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
