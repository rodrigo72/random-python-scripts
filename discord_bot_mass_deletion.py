import os
import aiofiles
import discord
import asyncio
from discord.ext import commands
from discord.errors import RateLimited
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

DATA_DIR = 'archived_messages'
EXCEPTIONS_PATH = 'exceptions.txt'
CUTOFF_DAYS = 1000
FALLBACK_DELAY = 2 
FALLBACK_DELAY_2 = 0.3
FIVE_DELETE_PAUSE = 4 
TARGET_USER_ID = 348800725272363009
TARGET_CHANNEL_ID = 771898269101850624
LISBON_TZ = ZoneInfo("Europe/Lisbon")
DECEMBER_2020 = datetime(2020, 12, 1, tzinfo=ZoneInfo('UTC'))
AFTER_DATE = datetime(2020, 11, 28, tzinfo=ZoneInfo('UTC'))
GIF_DOMAINS = {'tenor.com', 'giphy.com', 'media.giphy.com', 'i.giphy.com', 'media.tenor.com'}

os.makedirs(DATA_DIR, exist_ok=True)

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
    """Determine if message should be skipped based on content rules."""
    if not content:
        return False
    if content in exception_set:
        return True
    if content.startswith('$'):
        return True
    if content.startswith('!') and len(content) < 15:
        return True
    if count_alpha(content) < 4:
        return True
    if len(set(content)) <= 2:
        return True
    return False


async def safe_delete(msg: discord.Message, channel_name: str):
    while True:
        try:
            await msg.delete()
            now = datetime.now(LISBON_TZ).isoformat()
            print(f"[{now}] Deleted {msg.id} in #{channel_name}")
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


async def archive_and_delete(channel: discord.TextChannel):
    exception_set = set()
    try:
        with open(EXCEPTIONS_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                exception_set.add(line.rstrip('\n\r'))
    except FileNotFoundError:
        print(f"{EXCEPTIONS_PATH} not found. Continuing without exceptions.")

    now_lisbon = datetime.now(LISBON_TZ)
    cutoff = now_lisbon - timedelta(days=CUTOFF_DAYS)
    ts = now_lisbon.strftime('%Y%m%d_%H%M%S')
    guild_safe = channel.guild.name.replace(' ', '_')
    chan_safe = channel.name.replace(' ', '_')
    filepath = os.path.join(DATA_DIR, f"{guild_safe}_{chan_safe}_{ts}.txt")

    async with aiofiles.open(filepath, mode='w', encoding='utf-8') as afp:
        await afp.write(f"# Guild: {channel.guild.name} (ID: {channel.guild.id})\n")
        await afp.write(f"# Channel: {channel.name} (ID: {channel.id})\n")
        await afp.write(f"# Archived at: {now_lisbon.isoformat()}\n")
        await afp.write(f"# Cutoff: {cutoff.isoformat()}\n")
        await afp.write("# Delete rules:\n")
        await afp.write("# - Target user messages\n")
        await afp.write("# - Other users' messages mentioning target (pre-Dec 2020)\n")
        await afp.write("# - Skip GIFs, exceptions.txt matches, $ prefix, short !commands\n\n")

        deleted, errors, total = 0, 0, 0

        async for msg in channel.history(limit=None, before=cutoff, after=AFTER_DATE,oldest_first=True):
            total += 1
            content = msg.content.replace('\n', '\\n') if msg.content else ""
            if msg.attachments:
                content += f" [ATTACHMENTS: {' '.join(a.url for a in msg.attachments)}]"
            if msg.embeds:
                content += f" [EMBEDS: {len(msg.embeds)}]"
            line = f"[{msg.created_at.isoformat()}] {msg.author.display_name} ({msg.author.id}): {content}\n"
            await afp.write(line)

            to_delete = False
            content = msg.content or ""

            # target user messages
            if msg.author.id == TARGET_USER_ID:
                to_delete = True

            # other users mentioning target (pre-Dec 2020)
            elif (TARGET_USER_ID in [user.id for user in msg.mentions] and
                  msg.created_at < DECEMBER_2020):
                to_delete = True

            # apply deletion exceptions
            if to_delete:
                if is_gif_message(msg):
                    to_delete = False
                elif should_skip_deletion(content, exception_set):
                    to_delete = False

            # delete if eligible
            if to_delete:
                success = await safe_delete(msg, channel.name)
                if success:
                    deleted += 1
                    print(f"[CONTENT] Deleted message from {msg.author.display_name}: {content}")
                    if deleted % 5 == 0:
                        print(f"[PACING] Pausing {FIVE_DELETE_PAUSE}s after {deleted} deletes")
                        await asyncio.sleep(FIVE_DELETE_PAUSE)
                else:
                    errors += 1
                await asyncio.sleep(FALLBACK_DELAY)
            else:
                await asyncio.sleep(FALLBACK_DELAY_2)

    print(f"[DONE] #{channel.name} — Deleted: {deleted}, Errors: {errors}, Archived: {filepath}")


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
        await archive_and_delete(target_channel)
    print("Channel processed. Shutting down.")
    await bot.close()


if __name__ == '__main__':
    bot.run(TOKEN)
