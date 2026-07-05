from modules.telegram_parser.prediction_extractor import extract_prediction


def test_extracts_match_winner_prediction_with_odds():
    prediction = extract_prediction("Dota 2 прогноз: победа Team Spirit кф 1.85")

    assert prediction is not None
    assert prediction.market_type == "match_winner"
    assert prediction.odds == 1.85
    assert prediction.needs_review is False


def test_extracts_maps_total_prediction():
    prediction = extract_prediction("Dota2 тотал карт ТБ 2.5 odds 1.92")

    assert prediction is not None
    assert prediction.market_type == "maps_total"
    assert prediction.market_side == "over"
    assert prediction.market_line == 2.5
    assert prediction.odds == 1.92


def test_extracts_maps_total_over_without_treating_line_as_odds():
    prediction = extract_prediction("Dota 2 ТБ 2.5 карт")

    assert prediction is not None
    assert prediction.market_type == "maps_total"
    assert prediction.market_side == "over"
    assert prediction.market_line == 2.5
    assert prediction.odds is None


def test_extracts_maps_total_under():
    prediction = extract_prediction("under 2.5 maps @1.88")

    assert prediction is not None
    assert prediction.market_type == "maps_total"
    assert prediction.market_side == "under"
    assert prediction.market_line == 2.5
    assert prediction.odds == 1.88


def test_ignores_short_noise():
    assert extract_prediction("hello") is None
