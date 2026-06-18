def seconds_to_timestamp(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def clamp_time(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)

