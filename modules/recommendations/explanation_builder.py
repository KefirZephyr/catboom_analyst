def build_explanation(edge_percent: float, confidence_percent: float) -> str:
    return (
        f"Edge {edge_percent}% и confidence {confidence_percent}% проходят заданные лимиты. "
        "Рекомендация требует ручного подтверждения пользователя."
    )
