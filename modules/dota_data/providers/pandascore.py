import logging
from typing import Any

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


class PandaScoreError(RuntimeError):
    pass


class PandaScoreTokenMissing(PandaScoreError):
    pass


class PandaScoreProvider:
    def __init__(self) -> None:
        self.base_url = settings.pandascore_base_url.rstrip("/")
        self.token = settings.pandascore_token.get_secret_value().strip()

    @property
    def is_configured(self) -> bool:
        return bool(self.token)

    async def get_upcoming_matches(self) -> list[dict[str, Any]]:
        return await self._get("/dota2/matches/upcoming")

    async def get_live_matches(self) -> list[dict[str, Any]]:
        return await self._get("/dota2/matches/running")

    async def get_past_matches(self) -> list[dict[str, Any]]:
        return await self._get("/dota2/matches/past")

    async def get_team(self, team_id: str) -> dict[str, Any]:
        data = await self._get(f"/dota2/teams/{team_id}", expect_list=False)
        if not isinstance(data, dict):
            raise PandaScoreError("PandaScore API вернул неожиданный формат данных команды")
        return data

    async def _get(self, path: str, expect_list: bool = True) -> list[dict[str, Any]] | dict[str, Any]:
        if not self.token:
            raise PandaScoreTokenMissing("PANDASCORE_TOKEN не задан")

        headers = {"Authorization": f"Bearer {self.token}"}
        params = {"per_page": 50}

        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30,
            ) as client:
                response = await client.get(path, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            logger.warning("PandaScore API returned HTTP %s for %s", status, path)
            raise PandaScoreError(f"PandaScore API вернул HTTP {status}") from exc
        except httpx.HTTPError as exc:
            logger.warning("PandaScore API request failed for %s: %s", path, type(exc).__name__)
            raise PandaScoreError("Не удалось подключиться к PandaScore API") from exc

        if expect_list and not isinstance(data, list):
            logger.warning("PandaScore API returned unexpected payload for %s", path)
            raise PandaScoreError("PandaScore API вернул неожиданный формат данных")

        return data
