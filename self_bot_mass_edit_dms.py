import discord
import asyncio
from datetime import datetime, timedelta, timezone
import string

EXCEPTIONS_PATH = 'exceptions.txt'


def count_alpha(s: str) -> int:
    return sum(c.isalpha() for c in s)


def should_skip_deletion(content: str, exception_set: set) -> bool:
    if not content:
        return False
    if content.lower() == '[redacted]':
        return True
    if content in exception_set:
        return True
    if content.startswith('$') and len(content) < 15:
        return True
    if content.lower().startswith('pls') and len(content) < 35:
        return True
    if content.startswith('!') and len(content) < 35:
        return True
    if count_alpha(content) < 4:
        return True
    if len(set(content)) <= 2:
        return True
    if content.startswith('<') and content.endswith('>'):
        return True
    return False


class DMCleanupBot(discord.Client):
    def __init__(self, **options):
        super().__init__(**options)
        self.exception_set = set()
        try:
            with open(EXCEPTIONS_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    self.exception_set.add(line.strip())
        except FileNotFoundError:
            print(f"{EXCEPTIONS_PATH} not found; continuing without exceptions")

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')

    async def on_message(self, message):
        if message.author.id != self.user.id:
            return

        parts = message.content.strip().split()

        if parts[0] == '!start_cleanup_dm':
            if len(parts) != 4:
                return await message.channel.send(
                    "Usage: !start_cleanup_dm DM_CHANNEL_ID DAYS SECONDS"
                )

            try:
                dm_channel_id = int(parts[1])
                days          = int(parts[2])
                delay         = float(parts[3])
            except ValueError:
                return await message.channel.send("Invalid numeric arguments.")

            dm_channel = self.get_channel(dm_channel_id)
            if dm_channel is None:
                try:
                    dm_channel = await self.fetch_channel(dm_channel_id)
                    print("Finished fetching channel.")
                except Exception:
                    return await message.channel.send("Could not find a DM with that ID.")

            if not isinstance(dm_channel, discord.DMChannel):
                return await message.channel.send("Channel ID is not a DM channel.")

            await message.channel.send(
                f"Starting redaction in your DM (ID {dm_channel_id}):\n"
                f"— messages older than {days} days, {delay}s delay"
            )
            asyncio.create_task(
                self.redact_streaming(dm_channel, message.channel, days, delay)
            )

    async def redact_streaming(self, target_channel, feedback_channel, days, delay):
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        edited_count = 0
        deleted_count = 0
        skipped_count = 0

        async for msg in target_channel.history(limit=None, before=cutoff, oldest_first=False):
            if msg.author.id != self.user.id:
                continue

            content = msg.content or ""
            has_attachments = bool(msg.attachments)

            if not content and has_attachments:
                try:
                    await msg.delete()
                    deleted_count += 1
                    print("Deleted attachment message.")
                except discord.NotFound:
                    skipped_count += 1
                except Exception as e:
                    print(f"Error deleting message {msg.id}: {e!r}")
                await asyncio.sleep(delay)
                continue

            print(f"Message content: {content[:100]}")

            if should_skip_deletion(content, self.exception_set):
                skipped_count += 1
                print("Skiped message.")
                continue

            try:
                await msg.edit(content="[REDACTED]")
                print("Redacted message.")
                edited_count += 1
            except discord.NotFound:
                skipped_count += 1
            except Exception as e:
                print(f"Error editing message {msg.id}: {e!r}")

            await asyncio.sleep(delay)

        await feedback_channel.send(
            f"Redaction completed in your DM with {target_channel.recipient}:\n"
            f"- Edited: {edited_count} messages\n"
            f"- Deleted attachments-only: {deleted_count} messages\n"
            f"- Skipped: {skipped_count} messages"
        )


if __name__ == '__main__':
    client = DMCleanupBot()
    client.run('TOKEN')
