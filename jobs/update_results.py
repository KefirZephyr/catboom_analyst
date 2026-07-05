from modules.telegram_parser.result_matcher import match_prediction_results


async def run() -> None:
    await match_prediction_results()
