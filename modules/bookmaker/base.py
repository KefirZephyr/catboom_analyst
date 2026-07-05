from typing import Protocol


class OddsProvider(Protocol):
    async def get_odds(self) -> list[dict]:
        ...
