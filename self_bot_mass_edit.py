import discord
import asyncio
from datetime import datetime, timedelta, timezone

class CleanupBot(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')

    async def on_message(self, message):
        if message.author.id != self.user.id:
            return

        if message.content.startswith('!start_cleanup'):
            parts = message.content.split()
            if len(parts) != 5:
                return await message.channel.send(
                    "Usage: !start_cleanup SERVER_ID CHANNEL_ID DAYS SECONDS"
                )

            try:
                guild_id, channel_id = map(int, parts[1:3])
                days = int(parts[3])
                delay = float(parts[4])
            except ValueError:
                return await message.channel.send("Invalid numeric arguments.")

            guild = self.get_guild(guild_id)
            if not guild:
                return await message.channel.send("Server not found")

            channel = guild.get_channel(channel_id)
            if not channel:
                return await message.channel.send("Channel not found")

            await message.channel.send(
                f"Starting redaction in {channel.name}: "
                f"messages older than {days} days, {delay} seconds delay"
            )
            asyncio.create_task(
                self.redact_streaming(channel, message.channel, days, delay)
            )

    async def redact_streaming(self, target_channel, feedback_channel, days, delay):
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        edited_count = 0
        skipped_count = 0

        async for msg in target_channel.history(limit=None, before=cutoff):
            if msg.author.id != self.user.id:
                continue
            if "[REDACTED]" in msg.content:
                skipped_count += 1
                continue

            try:
                await msg.edit(content="[REDACTED]")
                edited_count += 1

                timestamp = datetime.now(timezone.utc).isoformat()
                print(f"[{timestamp}] Edited message #{edited_count} (ID {msg.id})")

            except discord.NotFound:
                skipped_count += 1
            except Exception as e:
                print(f"Error editing message {msg.id}: {e!r}")

            await asyncio.sleep(delay)

        await feedback_channel.send(
            f"Redaction completed in {target_channel.mention}:\n"
            f"- Edited: {edited_count} messages\n"
            f"- Skipped (already redacted or missing): {skipped_count} messages"
        )


if __name__ == '__main__':
    client = CleanupBot()
    client.run('TOKEN')
