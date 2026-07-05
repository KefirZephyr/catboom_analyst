import asyncio

from modules.dota_data.match_sync import sync_matches


async def run() -> None:
    result = await sync_matches()
    if result.error:
        print(f"Match sync failed: {result.error}")
        return
    print(
        "Match sync completed: "
        f"upcoming={result.upcoming}, live={result.live}, past={result.past}, "
        f"teams={result.teams}, tournaments={result.tournaments}, matches={result.matches}"
    )


if __name__ == "__main__":
    asyncio.run(run())
