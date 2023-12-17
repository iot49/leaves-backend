from micropython import const
import asyncio
import json
import logging

from app import event_bus
from app import config

from features.current_state import state

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ping client at this interval to test connection [sec]
_PING_INTERVAL = const(1)


class EventIO:

    def __init__(self, ws):
        self._ws = ws
        self.client_addr = ws.request.client_addr[0]
        logger.info(f"{'-'*20} new connection from {self.client_addr}")
        # save bound method for later unsubscribe
        # Note: self._send produces different object each time it is called!
        self._susbscriber = self._send
        event_bus.subscribe(self._susbscriber)

    async def receiver(self):
        while True:
            try:
                event = await asyncio.wait_for(self._ws.receive(), timeout=_PING_INTERVAL+1)
                event = json.loads(event)
                if event.get('type') == 'ping': 
                    await event_bus.post(type='pong')
                else:
                    logger.debug(f"event.io {self.client_addr} received {event}")
                    await event_bus.post(src=self.client_addr, **event)
            except asyncio.TimeoutError:
                logger.warning("EventIO.receiver.TimeoutError - disconnecting")
                await self._close()
            if self._ws.closed:
                break

    async def _send(self, event):
        try:
            dst = event.get('dst', '*')
            if dst == self.client_addr or dst == '*':
                await self._ws.send(json.dumps(event))
        except OSError as e:
            if e.errno == 9:
                # socket closed
                await self._close()
            else:
                # unidentified error - this should not happen???
                logger.exception("***** EventIO._sender: OSError", e.errno)

    async def _close(self):
        try:
            await self._ws.close()
        except OSError as e:
            if e.errno == 9:
                pass
            else:
                # unidentified error - this should not happen???
                logger.exception("***** EventIO._close: OSError", e.errno)
        event_bus.unsubscribe(self._susbscriber)
        logger.info(f"{'-'*20} connection CLOSED")


async def serve(ws):
    io = EventIO(ws)
    await io.receiver()