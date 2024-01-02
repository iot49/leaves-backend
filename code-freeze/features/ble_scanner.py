# !cp -a $IOT_PROJECTS/micropython-lib/micropython/bluetooth/aioble/aioble/ $IOT_PROJECTS/code/lib/aioble

import asyncio
import aioble
import logging
from struct import unpack
from ucryptolib import aes   # type: ignore

from app import config, event_bus
update = event_bus.post_state_update

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Victron models
_VICTRON_MODEL = {
    0x01: 'Solar_Charger',
    0x02: 'Battery_Monitor',
    0x03: 'Inverter',
    0x04: 'DC/DC_converter',
    0x0c: 'VE_Bus',
}

# Victron device state codes
_VICTRON_STATE = {
    0: 'off',
    1: 'low power',
    3: 'fault',
    3: 'bulk',
    4: 'absorption',
    5: 'float'
}


async def parse_victron(data, dev, mac, device):

    def pad(data):
        n = 16-len(data)
        return data + bytes([n])*n
    
    if data[0] != 0x10: return
    prefix, model_id, model, iv, key0 = unpack('<HHBHB', data)

    if device == None:
        m = _VICTRON_MODEL.get(model)
        if m == None: return
        # config.set?  
        print(f'discover/{mac}', {
            'alias': m,
            'key': '0123456789abcdef0123456789abcdef',
        })
        return
    
    try:
        key = bytes.fromhex(device.get('key'))
        did = device.get('alias', mac)
        if key[0] != key0:
            logger.error(f"Victron wrong key for {did}")
            return
        cipher = aes(key, 6, iv.to_bytes(16, 'little'))
    except TypeError as e:
        logger.exception(f"Victron type error, model = {model:02x}", e)
        return

    try:
        decrypted = cipher.decrypt(pad(data[8:]))
    except ValueError as e:
        logger.exception(f"Victron type error, model = {model:02x}", e)
        return

    if model == 0x1:
        # Solar charger
        state, error, v, i, y, p, ext = unpack('<BBhhHHH', decrypted)
        await update(did, 'rssi', dev.rssi)
        await update(did, 'state', _VICTRON_STATE.get(state, str(state)))
        await update(did, 'voltage', v/100)
        await update(did, 'current', i/10)
        await update(did, 'energy', y*10.0)
        await update(did, 'power', p)

    elif model == 0x2:
        # Battery SOC monitor
        ttg, v, alarm, aux, i2, i0, consumed, soc = unpack('<HHHHHbHH', decrypted)
        ttg = float('inf') if ttg == 0xffff else ttg/60
        c = i0 << 16 | i2
        i = (c>>2)/1000
        T = aux/100 - 273.15 if c & 0b11 == 2 else float('nan')
        soc = ((soc & 0x3fff) >>4) / 10

        await update(did, 'rssi', dev.rssi)
        await update(did, 'time_to_go', ttg)
        await update(did, 'voltage', v/100)
        await update(did, 'current', i)
        await update(did, 'energy', consumed/10)
        await update(did, 'soc', soc)
        await update(did, 'temperature', T)


async def parse_govee(data: bytes, dev, mac, device):
    if len(data) != 7: return
    _, temp, humi, batt = unpack('<BhHB', data)
    if device:
        did = device.get('alias', mac)
        logger.info(f"Govee {did} ({mac}) update T={temp/100}C H={humi/100}% batt={batt}% {dev.rssi}dBm")
        await update(did, 'temperature', temp/100)
        await update(did, 'humidity', humi/100)
        await update(did, 'battery', batt)
        await update(did, 'rssi', dev.rssi)
    else:
        config.set(f'discover/{mac}', {
            'alias': f'Govee_{mac}',
            'description': f'Govee T/H {temp/100}C {dev.rssi}dBm'
        })
        logger.info(f"discovered Govee {mac}, T={temp/100}C RSSI={dev.rssi}dBm")


_PARSER = {
    0xEC88: parse_govee,
    0x02E1: parse_victron,
}

async def _main():
    while True:
        async with aioble.scan(duration_ms=5000, active=True) as scanner:
            async for dev in scanner:
                for manufacturer, data in dev.manufacturer():
                    logger.debug(f"Scan {dev.name()} manuf={manufacturer:04x} {dev.device.addr_hex()}")
                    parser = _PARSER.get(manufacturer)
                    if parser:
                        # check if device is registered
                        mac = dev.device.addr_hex().lower()
                        device = config.get(f'devices/{mac}')
                        await parser(data, dev, mac, device)


asyncio.create_task(_main())