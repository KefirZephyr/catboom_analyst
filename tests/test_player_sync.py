import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.routers.players import PLAYERS_EMPTY_TEXT, format_player_card
from db.base import Base
from db.models import Player, Team
from modules.dota_data.match_sync import empty_counters, upsert_team_players


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

        await engine.dispose()

        assert counters["players_processed"] == 1
        assert counters["players_created"] == 1
        assert player.nickname == "Yatoro"
        assert player.first_name == "Illya"
        assert player.last_name == "Mulyarchuk"
        assert player.role == "carry"
        assert player.nationality == "UA"
        assert player.team_id == team.id
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
    assert "🔄 Обновить данные" in PLAYERS_EMPTY_TEXT
    assert "PandaScore" in PLAYERS_EMPTY_TEXT
