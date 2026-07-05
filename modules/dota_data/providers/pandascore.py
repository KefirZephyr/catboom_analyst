import httpx

from config.settings import settings


class PandaScoreProvider:
    base_url = "https://api.pandascore.co"

    async def get_upcoming_dota_matches(self) -> list[dict]:
        token = settings.pandascore_token.get_secret_value()
        if not token:
            return []

        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=20) as client:
            response = await client.get("/dota2/matches/upcoming")
            response.raise_for_status()
            return response.json()
