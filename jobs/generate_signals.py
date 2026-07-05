import asyncio

from modules.recommendations.signal_generator import generate_signals_for_ready_predictions


async def run() -> None:
    results = await generate_signals_for_ready_predictions()
    created = len([item for item in results if item.signal])
    skipped = len(results) - created
    print(f"Signal generation completed: created={created}, skipped={skipped}")


if __name__ == "__main__":
    asyncio.run(run())
