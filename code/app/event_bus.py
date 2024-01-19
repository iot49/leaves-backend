import asyncio
import timestamp
import logging
from . import event_filter

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class _EventBus():

    def __init__(self):
        self._subscribers = set()
        self._total_events = 0
        self._event_filters = {}

    async def post(self, **event):
        if not 'type' in event: print("event_bus.post", event)
        assert 'type' in event
        for sub in self._subscribers:
            await sub(event)
        self._total_events += 1
        # dev.run (and maybe other tasks) "crash silently" without this delay
        await asyncio.sleep_ms(10)
 
    async def post_response(self, event, response):
        event = event.copy()
        event['response'] = response
        for sub in self._subscribers:
            await sub(event)
        self._total_events += 1

    async def post_state_update(self, device_id, attr_id, value, timestamp=timestamp.now()):
        # recursive import
        from .config import config
        from . import eid
        entity_id = f"{eid.NODE_ID}.{device_id}.{attr_id}"
        if not entity_id in self._event_filters:
            # all defined filters
            filters = { k[:-6].lower(): v for k,v in event_filter.__dict__.items() if k.endswith('Filter') }
            # filters for this entity
            spec = eid.attr(entity_id, 'filter', ['duplicate'])
            spec = [ next(iter(f.items())) if isinstance(f, dict) else (f, None) for f in spec ]
             # create filters
            self._event_filters[entity_id] = ([ filters[f[0]](f[1]) for f in spec ])
        # filter
        try:
            for f in self._event_filters[entity_id]:
                value = f.filter(value)
        except event_filter.NoUpdate:
            return
        await self.post(type='state_update', entity_id=entity_id, value=value, timestamp=timestamp)

    def subscribe(self, subscriber):
        self._subscribers.add(subscriber)

    def unsubscribe(self, subscriber):
        try:
            self._subscribers.remove(subscriber)
        except KeyError:
            pass

    def is_subscribed(self, subscriber):
        return subscriber in self._subscribers
    
    @property
    def total_events(self):
        return self._total_events


# singleton
event_bus = _EventBus()

