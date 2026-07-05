from modules.analytics.value_detector import calculate_bookmaker_probability, detect_value


def test_bookmaker_probability_from_decimal_odds():
    assert calculate_bookmaker_probability(2.0) == 50.0


def test_detects_value_when_edge_above_threshold():
    result = detect_value(model_probability_percent=58.0, decimal_odds=2.0)

    assert result.bookmaker_probability_percent == 50.0
    assert result.edge_percent == 8.0
    assert result.is_value is True
