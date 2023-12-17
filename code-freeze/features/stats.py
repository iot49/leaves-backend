import asyncio
import logging
from time import ticks_ms, ticks_add, ticks_diff   # type: ignore

from app import event_bus
update = event_bus.post_state_update

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


_BREAKS = [ 5, 10, 50, 100, 500, 1000 ]
_COUNTS = [0] * (len(_BREAKS)+1)


def histogram(value):
    global _BREAKS, _COUNTS
    for i, b in enumerate(_BREAKS):
        if value < b:
            _COUNTS[i] += 1
            return
    _COUNTS[-1] += 1


async def send_stats(period):
    # send statistics ... number of updates processed / second
    global _BREAKS, _COUNTS

    last_call_ms = ticks_ms()
    last_event_total = 0
    while True:
        await asyncio.sleep(period)

        # number of events processed
        t = ticks_ms()
        dt = 0.001 * ticks_diff(t, last_call_ms)
        last_call_ms = t
        events = event_bus.total_events
        await update('stats', 'events', (events-last_event_total)/dt)
        last_event_total = events

        # latency statistics
        N = 0.01*sum(_COUNTS)
        for i, b in enumerate(_BREAKS):
            await update('stats', f'latency < {b:4.0f} ms', _COUNTS[i]/N)
        await update('stats', f'latency > {_BREAKS[-1]:4.0f} ms', _COUNTS[-1]/N)


async def latency(period_ms):
    # measure asyncio scheduler "latency" (delay from ideal time task should run)
    t = ticks_ms()
    await asyncio.sleep_ms(period_ms)
    while True:
        last_call_ms = t
        t = ticks_ms()
        dt = ticks_diff(t, last_call_ms)
        histogram(dt-period_ms)
        await asyncio.sleep_ms(ticks_diff(ticks_add(t, period_ms), ticks_ms()))


async def counter():
    count = 0
    while True:
        await update('stats', 'count', count)
        # logger.info(f"features.stats.counter {count}")
        count += 1
        await asyncio.sleep_ms(1_000)


async def _main():
    if False:
        config.set('devices', 'stats', 'entities', 'updates-total', 'unit', '/sec')
        config.set('devices', 'stats', 'entities', 'updates-sent',  'unit', '/sec')
        config.set('devices', 'stats', 'entities', f'latency > {_BREAKS[-1]:4.0f} ms', 'unit', '%')
        for b in _BREAKS:
            config.set('devices', 'stats', 'entities', f'latency < {b:4.0f} ms', 'unit', '%')

    # average throughput over 60 seconds
    asyncio.create_task(send_stats(60))

    # "pulse"
    asyncio.create_task(counter())

    # measure latency once a second
    await latency(1000)


asyncio.create_task(_main())