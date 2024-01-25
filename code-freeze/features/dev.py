import asyncio
import io, os, sys, logging
from app import event_bus

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class _DUP(io.IOBase):

    def __init__(self):
        self._buffer = io.BytesIO()
        self._id = 0

    def write(self, data):
        if self._buffer.tell() < 100_000:
            self._buffer.write(data)

    def readinto(self, data):
        return None
    
    async def run(self):
        os.dupterm(self)
        while True:
            buffer = self._buffer
            if buffer.tell() > 0:
                # allocate new buffer
                self._buffer = io.BytesIO()
                # post contents from prior buffer to event_bus
                buffer.seek(0)
                while True:
                    data = buffer.read(1024)
                    if data:
                        await event_bus.post(type='print', data=data, id=self._id)
                    else:
                        break

            await asyncio.sleep_ms(100)


async def _main():
    global _DUPTERM
    await _DUPTERM.run()

_DUPTERM = _DUP()
asyncio.create_task(_main())



async def _handle_dev_event(event):
    global _DUPTERM
    t = event.get('type')
    if t == 'exec':
        try:
            _DUPTERM._id = event.get('id', 0)
            g = __import__("__main__").__dict__
            exec(event.get('code'), g, g)
        except Exception as e:
            s = io.StringIO()
            sys.print_exception(e, s)
            t = s.getvalue().split('\n', 3)
            t.pop(1)
            t = '\n'.join(t)
            print(f'\n<div class="exception">***** {e.value}\n{t}</div>')

event_bus.subscribe(_handle_dev_event)

