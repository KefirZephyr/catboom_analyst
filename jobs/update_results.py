import asyncio

from modules.telegram_parser.result_settlement import settle_predictions


async def run() -> None:
    summary = await settle_predictions()
    print(
        "Settlement summary: "
        f"checked={summary.checked}, "
        f"wins={summary.wins}, "
        f"losses={summary.losses}, "
        f"voids={summary.voids}, "
        f"skipped={summary.skipped}, "
        f"errors={summary.errors}"
    )


if __name__ == "__main__":
    asyncio.run(run())
