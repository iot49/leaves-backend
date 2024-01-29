import asyncio
import ntptime                        # type: ignore
import time                           # type: ignore
from features.wifi import wifi   # type: ignore

async def _main():
    async with wifi:
        ntptime.settime()

def init(host="pool.ntp.org", timeout=10):
    # time shifts crash something
    # FIX: features.ntp - time shift issue
    if time.time() > 700000000: return
    ntptime.host = host
    ntptime.timeout = timeout
    asyncio.create_task(_main())