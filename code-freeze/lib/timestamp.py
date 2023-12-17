import time

EPOCH_OFFSET = 946684800

def now():
    """Timestamp in ESP32-Micropython seconds (starting at 2000-01-01)."""
    return time.time()

def to_unix_epoch(timestamp):
    """Convert timestamp to Unix Epoch (starting at 1970-01-01)."""
    return timestamp + EPOCH_OFFSET

def to_isodate(timestamp):
    year, month, day, hour, min, sec, _, _ = time.gmtime(timestamp)
    return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{min:02d}:{sec:02d}"

