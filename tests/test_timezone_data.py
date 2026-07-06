from zoneinfo import ZoneInfo


def test_required_timezones_are_available() -> None:
    assert ZoneInfo("UTC").key == "UTC"
    assert ZoneInfo("Europe/Moscow").key == "Europe/Moscow"
