from collections import deque
from app import event_bus
import logging

_log = None
_levelno = logging.WARNING

def get_log():
    # Note: micropython.deque is not iterable!
    global _log
    res = [None]*len(_log)
    for i in range(len(_log)):
        res[i] = x = _log.popleft()
        _log.append(x)
    return res

async def _handle_log_event(event):
    global _log, _levelno
    type = event.get('type')
    if type == 'log' and event.get('levelno', logging.WARNING) >= _levelno:
        _log.append(event)
    elif type == 'get_log':
        await event_bus.post(type='get_log_', data=get_log(), dst=event.get('src', '*'))

def init(size=10, level='WARNING'):
    global _log, _levelno
    try:
        _levelno = next(key for key, value in logging._level_dict.items() if value == level.upper())
    except StopIteration:
        _levelno = logging.WARNING
    _log = deque((), int(size))
    event_bus.subscribe(_handle_log_event)
