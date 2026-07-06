import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.routers.data_update import data_update_run, format_data_update_report
from bot.routers.players import PLAYERS_EMPTY_TEXT, format_player_card
from db.base import Base
from db.models import Player, Team
from modules.dota_data.match_sync import MatchSyncResult, empty_counters, upsert_team_players
from modules.dota_data.providers.pandascore import (
    PandaScoreNotFound,
    PandaScoreProvider,
    TEAM_DETAIL_NOT_FOUND_CACHE,
)


def test_upsert_player_from_pandascore_payload_and_team_link() -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as session:
            team = Team(external_id="10", name="Team Spirit")
            session.add(team)
            await session.flush()

            counters = empty_counters()
            await upsert_team_players(
                session,
                team,
                {
                    "players": [
                        {
                            "id": 123,
                            "name": "Yatoro",
                            "first_name": "Illya",
                            "last_name": "Mulyarchuk",
                            "role": "carry",
                            "nationality": "UA",
                            "active": True,
                        }
                    ]
                },
                counters,
            )
            await session.commit()

            result = await session.execute(select(Player).where(Player.external_id == "123"))
            player = result.scalar_one()
            team_id = team.id

        await engine.dispose()

        assert counters["players_processed"] == 1
        assert counters["players_created"] == 1
        assert player.nickname == "Yatoro"
        assert player.first_name == "Illya"
        assert player.last_name == "Mulyarchuk"
        assert player.role == "carry"
        assert player.nationality == "UA"
        assert player.team_id == team_id
        assert player.is_active is True

    asyncio.run(run())


def test_format_player_card_contains_real_fields() -> None:
    team = Team(id=10, name="Team Spirit")
    player = Player(
        id=1,
        external_id="123",
        team_id=10,
        nickname="Yatoro",
        first_name="Illya",
        last_name="Mulyarchuk",
        role="carry",
        nationality="UA",
        is_active=True,
        updated_at=datetime(2026, 7, 6, 12, 30),
    )

    text = format_player_card(player, team)

    assert "Yatoro" in text
    assert "Illya Mulyarchuk" in text
    assert "Team Spirit" in text
    assert "carry" in text
    assert "активен" in text
    assert "06.07.2026 12:30" in text


def test_players_empty_state_explains_next_action() -> None:
    assert "Игроки пока не загружены" in PLAYERS_EMPTY_TEXT
    assert "PandaScore не вернул составы/игроков" in PLAYERS_EMPTY_TEXT
    assert "🔄 Обновить данные" in PLAYERS_EMPTY_TEXT


def test_provider_caches_team_detail_404(monkeypatch) -> None:
    async def run() -> None:
        TEAM_DETAIL_NOT_FOUND_CACHE.clear()
        provider = PandaScoreProvider()
        calls = []

        async def fake_get(path: str, expect_list: bool = True):
            calls.append(path)
            raise PandaScoreNotFound("not found")

        monkeypatch.setattr(provider, "_get", fake_get)

        for _ in range(2):
            try:
                await provider.get_team("126591")
            except PandaScoreNotFound:
                pass

        assert calls == ["/teams/126591"]
        assert "126591" in TEAM_DETAIL_NOT_FOUND_CACHE
        TEAM_DETAIL_NOT_FOUND_CACHE.clear()

    asyncio.run(run())


def test_data_update_callback_is_answered_before_sync(monkeypatch) -> None:
    async def run() -> None:
        events = []

        async def fake_sync_matches() -> MatchSyncResult:
            events.append("sync")
            return MatchSyncResult(matches_processed=1)

        class FakeMessage:
            async def edit_text(self, *args, **kwargs):
                events.append("edit")

        class FakeCallback:
            message = FakeMessage()

            async def answer(self, *args, **kwargs):
                events.append("answer")

        monkeypatch.setattr("bot.routers.data_update.sync_matches", fake_sync_matches)

        await data_update_run(FakeCallback())

        assert events[0] == "answer"
        assert events.index("answer") < events.index("sync")

    asyncio.run(run())


def test_data_update_report_shows_player_sync_skipped_reason() -> None:
    text = format_data_update_report(
        MatchSyncResult(
            matches_processed=5,
            matches_created=1,
            matches_updated=4,
            teams_created=2,
            teams_updated=3,
            tournaments_created=1,
            tournaments_updated=1,
            players_skipped=3,
            players_reason="PandaScore team details endpoint вернул несколько 404 подряд.",
        )
    )

    assert "Матчи обработано: 5" in text
    assert "Player sync skipped: 3" in text
    assert "PandaScore team details endpoint" in text
