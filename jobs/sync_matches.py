from modules.dota_data.match_sync import sync_matches


async def run() -> None:
    await sync_matches()
