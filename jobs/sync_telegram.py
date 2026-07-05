from modules.telegram_parser.channel_sync import sync_channels


async def run() -> None:
    await sync_channels()
