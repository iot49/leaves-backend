from app import event_bus

# dict enity_id -> value
# OK to inspect, don't alter
state = {}

async def _handle_update_event(event):
    global state
    et = event.get('type')
    if et == 'state_update':
        state[event['entity_id']] = event['value']
    elif et == 'get_state':
        await event_bus.post(type='get_state_', data=state, dst=event.get('src', '*'))


event_bus.subscribe(_handle_update_event)
