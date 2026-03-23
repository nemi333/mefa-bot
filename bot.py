import discord
import os
import aiohttp
import json
import asyncio
import random
from discord.ext import tasks
from dotenv import load_dotenv

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

if not DISCORD_TOKEN or DISCORD_TOKEN == "twoj_token_bota_tutaj":
    print("BŁĄD: Musisz podać DISCORD_TOKEN w pliku .env!")
    exit(1)

GUILD_ID            = None
WELCOME_CHANNEL_ID  = 1485641038566653993
ANNOUNCE_CHANNEL_ID = 1485620102845173822
ARMA_BOARDS = [
    {"bm_server_id": "35744919", "channel_id": 1485628780629196832},
    {"bm_server_id": "35747535", "channel_id": 1485628780629196832},
]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

WELCOME_TEMPLATES = [
    "Czołem {mention}! Witaj w naszej ekipie dowodzenia.\n\nSerwery na których gramy to **PLG #1** i **PLG #2** (częściej spotkasz nas na #2).\n\nJeśli masz pytania lub jesteś totalnie świeży w Arma Reforger to dobrze trafiłeś/aś! Z naszą ekipą bez problemu nauczysz się podstaw lub rozwiniesz swoje umiejętności.\n\nDo zobaczenia w bitce! 🫡",
    "Melduj się, {mention}! Dobrze Cię widzieć w naszych szeregach.\n\nNaszym głównym rejonem działań są serwery **PLG #1** oraz **PLG #2** (najczęściej stacjonujemy na dwójce).\n\nNie przejmuj się, jeśli Arma to dla Ciebie nowość - od tego jesteśmy, żeby pomóc Ci ogarnąć sterowanie i szlifować skilla.\n\nGotów do wymarszu? Widzimy się na froncie! 🫡",
    "Witamy w wirtualnej bazie, {mention}! Cieszymy się, że dołączasz do oddziału.\n\nNajwięcej wojujemy na serwerach **PLG #1** i **PLG #2** (z naciskiem na ten drugi).\n\nNiezależnie od tego, czy zjadłeś zęby na serii Arma, czy to Twoja pierwsza strzelanina, chętnie pomożemy Ci wdrożyć się w walkę.\n\nKoniec odprawy. Do zobaczenia na polu bitwy! 🫡",
    "Salut {mention}! Twoje akta właśnie powędrowały na biurko sztabu.\n\nRozkazy są proste: wbijamy na **PLG #1** i **PLG #2** (głównym celem jest zazwyczaj #2).\n\nZawsze służymy pomocą dowódczą dla nowych rekrutów, więc nie krępuj się pytać, jeśli gra stawia przed Tobą wyzwania.\n\nŁaduj magazynek i widzimy się z bronią w ręku! 🫡",
    "Oto nowy rekrut! Siema {mention}, rozgość się w kantynie.\n\nSzybki meldunek na radio: nasze operacje toczą się głównie na serwerach **PLG #1** i **PLG #2** (chętniej atakujemy #2).\n\nMasz problemy z ogarnięciem Army? Żaden problem. Z naszą brygadą szybko złapiesz taktykę i podstawy przetrwania.\n\nPowodzenia, odpalaj grę i ruszaj do pomocy paczce! 🫡"
]

async def get_welcome_message(mention: str) -> str:
    if GEMINI_API_KEY:
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
                prompt = (
                    "Jesteś botem na serwerze Discord graczy Arma Reforger. Przywitaj nowego gracza militarnie, krótko i wyluzowanie. "
                    "3 kluczowe zasady: 1) Wspomnij, że gracie na serwerach PLG #1 i PLG #2 (głównie na #2). "
                    "2) Podkreśl, że jesteście gotowi uczyć graczy, którzy są nowi w Arma Reforger. "
                    "3) Pisz naturalnie, najwyżej w 2-4 zdaniach, rzucaj emotkami wojskowymi (np. 🫡, 🔫). "
                    f"Wygeneruj powitanie, a na samym początku wiadomości KONIECZNIE umieść dosłownie: {mention} (żeby pingnęło gracza)."
                )
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.85}
                }
                async with session.post(url, json=payload, timeout=8) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        if mention not in text:
                            text = f"{mention} " + text
                        return text
        except Exception as e:
            print(f"Błąd Gemini API: {e}")
            pass
            
    return random.choice(WELCOME_TEMPLATES).replace("{mention}", mention)

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True

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

DB_FILE = "database.json"
db_lock = asyncio.Lock()

async def load_db():
    async with db_lock:
        if not os.path.exists(DB_FILE):
            return {"user_stats": {}, "arma_boards": []}
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"user_stats": {}, "arma_boards": []}

async def save_db(data):
    async with db_lock:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

async def init_db():
    async with db_lock:
        if not os.path.exists(DB_FILE):
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump({"user_stats": {}, "arma_boards": []}, f, indent=4, ensure_ascii=False)


@tasks.loop(minutes=1.0)
async def voice_time_tracker():
    data = await load_db()
    changed = False

    for guild in bot.guilds:
        for vc in guild.voice_channels:
            if guild.afk_channel and vc.id == guild.afk_channel.id:
                continue
            for member in vc.members:
                if member.bot:
                    continue

                user_id_str = str(member.id)
                if user_id_str not in data["user_stats"]:
                    data["user_stats"][user_id_str] = {"total_minutes": 0, "rank_index": -1}

                data["user_stats"][user_id_str]["total_minutes"] += 1
                changed = True
                
                total_minutes = data["user_stats"][user_id_str]["total_minutes"]
                db_rank_index = data["user_stats"][user_id_str]["rank_index"]

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
                    data["user_stats"][user_id_str]["rank_index"] = new_rank_index
                    changed = True
                    
                    ann_ch = guild.get_channel(ANNOUNCE_CHANNEL_ID)
                    if ann_ch:
                        try:
                            embed = discord.Embed(
                                title="🎉 Nowa ranga!",
                                description=(
                                    f"Gratulacje {member.mention}! Osiągnąłeś/aś nową rangę: "
                                    f"**{target_name}** po **{total_minutes}** minutach na kanałach głosowych! 🎙️"
                                ),
                                color=discord.Color.gold()
                            )
                            await ann_ch.send(content=member.mention, embed=embed)
                        except discord.Forbidden:
                            pass

    if changed:
        await save_db(data)


@voice_time_tracker.before_loop
async def before_voice():
    await bot.wait_until_ready()


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
    data = await load_db()
    
    for board in data.get("arma_boards", []):
        guild_id = board["guild_id"]
        channel_id = board["channel_id"]
        message_id = board["message_id"]
        bm_server_id = board["bm_server_id"]
        
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


@bot.slash_command(name="top", description="Ranking 10 osób z największym czasem na kanałach")
async def cmd_top(ctx: discord.ApplicationContext):
    await ctx.defer()
    data = await load_db()
    
    users = data.get("user_stats", {})
    if not users:
        return await ctx.followup.send("Brak danych o czasie spędzonym na kanałach.")
    
    sorted_users = sorted(users.items(), key=lambda x: x[1].get("total_minutes", 0), reverse=True)
    
    top_10 = sorted_users[:10]
    
    embed = discord.Embed(
        title="🏆 Ranking Aktywności Głosowej",
        color=discord.Color.gold(),
        description="Top 10 graczy, którzy spędzili najwięcej czasu na naszych kanałach:\n\n"
    )
    
    for i, (user_id_str, stats) in enumerate(top_10, 1):
        minutes = stats.get("total_minutes", 0)
        hours = minutes // 60
        mins = minutes % 60
        time_str = f"{hours}h {mins}m" if hours > 0 else f"{minutes} min"
        
        embed.description += f"**{i}.** <@{user_id_str}> — ⏱️ {time_str}\n"
        
    await ctx.followup.send(embed=embed)


@bot.slash_command(name="dodaj_czas", description="Dodaje minuty wybranemu użytkownikowi (Admin)")
@discord.default_permissions(administrator=True)
async def cmd_dodaj_czas(ctx: discord.ApplicationContext, user: discord.Member, minuty: int):
    if not ctx.author.guild_permissions.administrator:
        return await ctx.respond("❌ Brak uprawnień.", ephemeral=True)
    
    if minuty <= 0:
        return await ctx.respond("❌ Ilość minut musi być większa niż zero.", ephemeral=True)
        
    await ctx.defer()
    data = await load_db()
    
    user_id_str = str(user.id)
    if user_id_str not in data["user_stats"]:
        data["user_stats"][user_id_str] = {"total_minutes": 0, "rank_index": -1}
        
    data["user_stats"][user_id_str]["total_minutes"] += minuty
    await save_db(data)
    
    embed = discord.Embed(
        title="✅ Dodano czas!",
        description=f"Pomyślnie dodano **{minuty}** min. użytkownikowi {user.mention}.\n*(Zmiana ról serwerwych zostanie zaaplikowana automatycznie w ciągu kliku minut po wejściu gracza na kanał głosowy)*.",
        color=discord.Color.green()
    )
    await ctx.followup.send(embed=embed)


@bot.slash_command(name="zabierz_czas", description="Odejmuje minuty wybranemu użytkownikowi (Admin)")
@discord.default_permissions(administrator=True)
async def cmd_zabierz_czas(ctx: discord.ApplicationContext, user: discord.Member, minuty: int):
    if not ctx.author.guild_permissions.administrator:
        return await ctx.respond("❌ Brak uprawnień.", ephemeral=True)
    
    if minuty <= 0:
        return await ctx.respond("❌ Ilość minut musi być większa niż zero.", ephemeral=True)
        
    await ctx.defer()
    data = await load_db()
    
    user_id_str = str(user.id)
    current_minutes = data.get("user_stats", {}).get(user_id_str, {}).get("total_minutes", 0)
    
    if current_minutes == 0:
        return await ctx.followup.send(f"❌ Użytkownik {user.mention} ma 0 minut, nie można mu już nic odebrać.")
        
    nowe_minuty = max(0, current_minutes - minuty)
    if user_id_str not in data["user_stats"]:
        data["user_stats"][user_id_str] = {"total_minutes": nowe_minuty, "rank_index": -1}
    else:
        data["user_stats"][user_id_str]["total_minutes"] = nowe_minuty
        
    new_rank_index = -1
    for i, rank in enumerate(RANKS):
        if nowe_minuty >= rank["required_minutes"]:
            new_rank_index = i
        else:
            break
            
    data["user_stats"][user_id_str]["rank_index"] = new_rank_index
    await save_db(data)
    
    embed = discord.Embed(
        title="➖ Odebrano czas",
        description=f"Zabrano **{minuty}** minut użytkownikowi {user.mention}. Pozostał(a) z **{nowe_minuty}** min.\n*(Zabrane role serwerowe zostaną zasygnalizowane przez bota po następnym wejściu użytkownika na kanał)*.",
        color=discord.Color.red()
    )
    await ctx.followup.send(embed=embed)


@bot.slash_command(name="ranga", description="Twój czas na głosowych i postęp do nowej rangi")
async def cmd_ranga(ctx: discord.ApplicationContext):
    await ctx.defer()
    
    data = await load_db()
    user_id_str = str(ctx.author.id)
    user_stat = data.get("user_stats", {}).get(user_id_str, {"total_minutes": 0})
    total_minutes = user_stat.get("total_minutes", 0)

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

    data = await load_db()
    boards = data.setdefault("arma_boards", [])
    
    found = False
    for b in boards:
        if b["guild_id"] == ctx.guild.id and b["bm_server_id"] == battlemetrics_server_id:
            b["channel_id"] = msg.channel.id
            b["message_id"] = msg.id
            found = True
            break
            
    if not found:
        boards.append({
            "guild_id": ctx.guild.id,
            "channel_id": msg.channel.id,
            "message_id": msg.id,
            "bm_server_id": battlemetrics_server_id
        })
        
    await save_db(data)

    if not arma_board_updater.is_running():
        arma_board_updater.start()


@bot.event
async def on_member_join(member: discord.Member):
    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if not channel:
        return
    
    text = await get_welcome_message(member.mention)
    
    embed = discord.Embed(
        title="Witaj w ekipie! 🫡",
        description=text,
        color=discord.Color.from_rgb(139, 0, 0)
    )
    embed.set_image(url="https://media.tenor.com/pYtOt3XQMsYAAAAC/ar-ataka.gif")
    try:
        await channel.send(content=member.mention, embed=embed)
    except discord.Forbidden:
        pass


@bot.event
async def on_ready():
    await init_db()
    print("=" * 30)
    print(f"✅ Bot gotowy! Zalogowano jako {bot.user}")
    print("=" * 30)

    for guild in bot.guilds:
        for rank in RANKS:
            if not discord.utils.get(guild.roles, name=rank["name"]):
                try:
                    await guild.create_role(name=rank["name"], reason="Auto-tworzenie rangi przez bota")
                    print(f"  + Stworzono rolę: {rank['name']}")
                except discord.Forbidden:
                    print(f"  - Brak uprawnień do tworzenia ról na {guild.name}")

    data = await load_db()
    changed = False
    
    for guild in bot.guilds:
        for board_cfg in ARMA_BOARDS:
            channel = guild.get_channel(board_cfg["channel_id"])
            if not channel:
                continue
                
            boards = data.setdefault("arma_boards", [])
            existing = next((b for b in boards if b["guild_id"] == guild.id and b["bm_server_id"] == board_cfg["bm_server_id"]), None)
            if existing:
                continue
                
            info = await fetch_arma_data(board_cfg["bm_server_id"])
            if not info:
                continue
            embed = build_arma_embed(info, board_cfg["bm_server_id"], [])
            try:
                msg = await channel.send(embed=embed)
                boards.append({
                    "guild_id": guild.id,
                    "channel_id": channel.id,
                    "message_id": msg.id,
                    "bm_server_id": board_cfg["bm_server_id"]
                })
                changed = True
                print(f"  + Wysłano tablicę Arma (serwer BM: {board_cfg['bm_server_id']})")
            except discord.Forbidden:
                print(f"  - Brak uprawnień do wysyłania na kanale {channel.id}")
                
    if changed:
        await save_db(data)

    print("=" * 30)
    if not voice_time_tracker.is_running():
        voice_time_tracker.start()
        print("▶️ Uruchomiono śledzenie czasu głosowego!")
    if not arma_board_updater.is_running():
        arma_board_updater.start()
        print("▶️ Uruchomiono aktualizację tablic Arma!")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
