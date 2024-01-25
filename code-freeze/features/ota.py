from esp32 import Partition           # type: ignore
from urllib.urequest import urlopen   # type: ignore

from features.wifi import wifi
from app import event_bus
from ota32 import OTA


async def progress_cb(**kw):
    await event_bus.post(type="ota_status", **kw)


async def _handle_ota_event(event):
    t = event.get('type')
    if t == 'ota_flash':
        async with wifi:
            url = event.get('url')
            sha = event.get('sha')
            if url and sha:
                ota = OTA(progress_cb, dry_run=False)
                await ota.ota(url, sha)


event_bus.subscribe(_handle_ota_event)
