from config.settings import settings


def is_signal_allowed(edge_percent: float, confidence_percent: float) -> bool:
    return (
        edge_percent >= settings.min_edge_percent
        and confidence_percent >= settings.min_confidence_percent
    )
