def calculate_channel_rating(win_rate: float, sample_size: int) -> float:
    if sample_size <= 0:
        return 0
    return round(win_rate * min(sample_size / 100, 1), 2)
