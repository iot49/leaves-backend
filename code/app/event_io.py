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
_PING_INTERVAL = float(config.get('app/timeouts/ping_ms', 5000))/1000
_MAX_EVENT_SIZE = int(config.get('app/max_event_size', 100000))


class EventIO:

    _next_client_id = 0

    def __init__(self, ws):
        self._ws = ws
        EventIO._next_client_id += 1
        self._client_id = f'event-io-{EventIO._next_client_id}'
        print(f"{'-'*20} new connection from {self._client_id}")
        logger.info(f"{'-'*20} new connection from {self._client_id}")
        # save bound method for later unsubscribe
        # Note: self._send produces different object each time it is called!
        self._susbscriber = self._send
        event_bus.subscribe(self._susbscriber)

    async def receiver(self):
        while True:
            try:
                msg = await asyncio.wait_for(self._ws.receive(), _PING_INTERVAL)
                if len(msg) > _MAX_EVENT_SIZE:
                    logger.error(f"event exceeds maximum permitted message size ({len(msg)} > {_MAX_EVENT_SIZE} Bytes), rejected")
                event = json.loads(msg)
                if event.get('type') == 'ping': 
                    # await event_bus.post(type='pong')
                    event['type'] = 'pong'
                    await self._send(event)
                else:
                    logger.debug(f"event.io {self._client_id} received {event}")
                    await event_bus.post(src=self._client_id, **event)
            except asyncio.TimeoutError:
                print("EventIO.receiver.TimeoutError - disconnecting")
                logger.warning("EventIO.receiver.TimeoutError - disconnecting")
                await self._close()
            except Exception as e:
                logger.exception("event_io.receiver", e)
            if self._ws.closed:
                break

    async def _send(self, event):
        try:
            # don't send to self ...
            if event.get('src') == self._client_id: return
            # filter out what's not for us
            dst = event.get('dst', '*')
            j = json.dumps(event)
            if dst == self._client_id or dst == '*':
                if len(j) > _MAX_EVENT_SIZE:
                    logger.error(f"event ({event.get('type')}) exceeds maximum permitted message size ({len(j)} > {_MAX_EVENT_SIZE} Bytes), rejected")
                else:
                    await self._ws.send(j)
        except OSError as e:
            if e.errno == 9:
                # socket closed
                await self._close()
            else:
                # unidentified error - this should not happen???
                logger.exception("***** EventIO._sender: OSError", e.errno)
        except Exception as e:
            logger.exception("event_io._send", e)

    async def _close(self):
        print("event_io.close", self._client_id)
        try:
            await self._ws.close()
        except OSError as e:
            if e.errno == 9:
                pass
            else:
                # unidentified error - this should not happen???
                logger.exception("***** EventIO._close: OSError", e.errno)
        except Exception as e:
            logger.exception("_close", e)
        try:
            event_bus.unsubscribe(self._susbscriber)
        except Exception as e:
            logger.exception("unsubscribe", e)
        print(f"{'-'*20} connection with {self._client_id} CLOSED")
        logger.info(f"{'-'*20} connection with {self._client_id} CLOSED")


async def serve(ws):
    io = EventIO(ws)
    await io.receiver()
