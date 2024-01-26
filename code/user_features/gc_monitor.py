import asyncio
import gc   # type: ignore
from app import event_bus


async def _main():
    gc.threshold(10_000)
    while True:
        await event_bus.post_state_update('ram', 'free',  gc.mem_free())
        await event_bus.post_state_update('ram', 'alloc', gc.mem_alloc())
        gc.collect()
        await asyncio.sleep_ms(100)


asyncio.create_task(_main())