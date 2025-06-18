import os
import discord
import asyncio
from discord.ext import commands
from discord.errors import RateLimited
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

CUTOFF_DAYS = 365
FALLBACK_DELAY = 1.8
FALLBACK_DELAY_2 = 0.1
FIVE_DELETE_PAUSE = 2.8 
TARGET_USER_ID = 123123123123123123
TARGET_CHANNEL_ID = 12312312312312123
LISBON_TZ = ZoneInfo("Europe/Lisbon")
DECEMBER_2020 = datetime(2020, 12, 1, tzinfo=ZoneInfo('UTC'))
AFTER_DATE = datetime(2021, 1, 23, tzinfo=ZoneInfo('UTC'))
GIF_DOMAINS = {'tenor.com', 'giphy.com', 'media.giphy.com', 'i.giphy.com', 'media.tenor.com'}
EXCEPTIONS_PATH = 'exceptions.txt'

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
bot = commands.Bot(command_prefix='!', intents=intents)


def is_gif_message(msg: discord.Message) -> bool:
    for att in msg.attachments:
        if att.filename.lower().endswith('.gif'):
            return True
    if msg.content:
        for domain in GIF_DOMAINS:
            if domain in msg.content:
                return True
    return False


def count_alpha(s):
    return sum(c.isalpha() for c in s)


def should_skip_deletion(content: str, exception_set: set) -> bool:
    if not content:
        return False
    if content in exception_set:
        return True
    if content.startswith('$') and len(content) < 15:
        return True
    if content.startswith('pls') and len(content) < 15:
        return True
    if content.startswith('!') and len(content) < 15:
        return True
    if count_alpha(content) < 4:
        return True
    if len(set(content)) <= 2:
        return True
    if content.startswith('<') and content.endswith('>'):
        return True
    return False


async def safe_delete(msg: discord.Message, channel_name: str):
    while True:
        try:
            await msg.delete()
            now = datetime.now(LISBON_TZ).isoformat()
            max_len = 100
            content = msg.content or ''
            short = (content[:max_len] + '...') if len(content) > max_len else content
            print(f"[{now}] Deleted {msg.id} in #{channel_name} from {msg.author}: {short}")
            return True
        except RateLimited as rl:
            wait = getattr(rl, 'retry_after', FALLBACK_DELAY)
            print(f"[RateLimited] Waiting {wait:.2f}s before retry")
            await asyncio.sleep(wait)
        except discord.Forbidden:
            print(f"[Forbidden] Cannot delete {msg.id} in #{channel_name}")
            return False
        except discord.NotFound:
            return False
        except discord.HTTPException as e:
            headers = getattr(e.response, 'headers', {})
            if headers.get('x-ratelimit-remaining') == '0':
                wait = float(headers.get('x-ratelimit-reset-after', FALLBACK_DELAY))
                print(f"[Bucket Rate Limit] Pausing {wait}s")
                await asyncio.sleep(wait)
            elif 'retry-after' in headers:
                wait = float(headers['retry-after'])
                print(f"[Global Rate Limit] Pausing {wait}s")
                await asyncio.sleep(wait)
            else:
                print(f"[HTTPException] Failed to delete {msg.id}: {e}")
                return False


async def delete_messages(channel: discord.TextChannel):
    exception_set = set()
    try:
        with open(EXCEPTIONS_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                exception_set.add(line.strip())
    except FileNotFoundError:
        print(f"{EXCEPTIONS_PATH} not found; continuing without exceptions")

    now_lisbon = datetime.now(LISBON_TZ)
    cutoff = now_lisbon - timedelta(days=CUTOFF_DAYS)

    deleted = 0
    errors = 0

    async for msg in channel.history(limit=None, before=cutoff, after=AFTER_DATE, oldest_first=True):
        to_delete = False
        content = msg.content or ""

        if msg.author.id == TARGET_USER_ID:
            to_delete = True
        elif (TARGET_USER_ID in [user.id for user in msg.mentions]
              and msg.created_at < DECEMBER_2020):
            to_delete = True

        if to_delete:
            if is_gif_message(msg) or should_skip_deletion(content, exception_set):
                to_delete = False

        if to_delete:
            success = await safe_delete(msg, channel.name)
            if success:
                deleted += 1
                if deleted % 5 == 0:
                    await asyncio.sleep(FIVE_DELETE_PAUSE)
            else:
                errors += 1
            await asyncio.sleep(FALLBACK_DELAY)
        else:
            print(f"Skipping {msg.author}: {content[:30]}...")
            await asyncio.sleep(FALLBACK_DELAY_2)

    print(f"[DONE] #{channel.name} — Deleted: {deleted}, Errors: {errors}")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    target_channel = bot.get_channel(TARGET_CHANNEL_ID)
    if not target_channel:
        print(f"[ERROR] Channel with ID {TARGET_CHANNEL_ID} not found.")
    elif not isinstance(target_channel, discord.TextChannel):
        print(f"[ERROR] Channel ID {TARGET_CHANNEL_ID} is not a text channel.")
    elif not target_channel.permissions_for(target_channel.guild.me).manage_messages:
        print(f"[Skip] No permission to delete messages in #{target_channel.name}")
    else:
        await delete_messages(target_channel)
    print("Channel processed. Shutting down.")
    await bot.close()


if __name__ == '__main__':
    bot.run(TOKEN)
