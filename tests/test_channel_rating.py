from types import SimpleNamespace

from modules.telegram_parser.channel_rating import build_channel_stats


def prediction(status, odds, market="match_winner", needs_review=False):
    return SimpleNamespace(
        status=status,
        odds_value=odds,
        market_type=market,
        needs_review=needs_review,
    )


def test_channel_rating_flat_roi_ignores_pending():
    channel = SimpleNamespace(id=1, username="test", title="Test", last_sync_at=None)
    stats = build_channel_stats(
        channel,
        [
            prediction("win", 2.5),
            prediction("loss", 1.8),
            prediction("pending", 2.0, needs_review=True),
        ],
    )

    assert stats.total_predictions == 3
    assert stats.resolved_predictions == 2
    assert stats.pending_predictions == 1
    assert stats.profit_flat == 0.5
    assert stats.roi_flat == 25.0
