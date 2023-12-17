import asyncio  

from struct import unpack
from machine import UART, RTC   # type: ignore
import time                     # type: ignore
import logging
import timestamp
from app import event_bus


logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

update = event_bus.post_state_update
    
class GPS:
    
    def __init__(self):
        uart = UART(1, baudrate=38400, rx=GPS_RX, tx=GPS_TX)
        self._reader = asyncio.StreamReader(uart)
        self.valid = False
    
    async def run(self):
        """Read satellite continually"""
        while True:
            try:
                line = await self._reader.readline()
                if line.startswith(b'$') and line.endswith(b'\r\n'):
                    tag, *fields = line.decode().split(',')
                    id = tag[3:]
                    if id == 'GGA':
                        await self._parse_gga(fields)
                    elif id == 'RMC':
                        await self._parse_rmc(fields)
            except (ValueError, IndexError) as e:
                logger.warning(f"***** GPS: {type(e)} {e}, {line}")
            
    async def _parse_gga(self, fields):
        self.valid = int(fields[5]) > 0
        if not self.valid: return
        d, s = unpack('2s8s', fields[1])
        lat = int(d) + float(s)/60
        lat = -lat if fields[2] == 'S' else lat
        await update('gps', 'latitude', lat)
        d, s = unpack('3s8s', fields[3])
        lon = int(d) + float(s)/60
        lon = -lon if fields[4] == 'W' else lon
        await update('gps', 'longitude', lon)
        await update('gps', 'altitude', float(fields[8]))
        await update('gps', 'nsat', int(fields[6]))
        
    async def _parse_rmc(self, fields):
        if not self.valid: return
        day, month, year = [ int(x) for x in unpack('2s2s2s', fields[8]) ]
        h, m, s = [ int(x) for x in unpack('2s2s2s', fields[0]) ]
        epoch = time.mktime((2000+year, month, day, h, m, s, 0, 0))
        # c-python epoch starts in 1970, micropython 2000: on client, add
        #       timestamp.EPOCH_OFFSET 
        # to get c-python epoch
        await update('gps', 'epoch', epoch)
        await update('gps', 'iso', timestamp.to_isodate(epoch))
        if abs(time.time() - epoch) > 2:
            self.set_time(epoch)

    def set_time(self, epoch):
        tm = time.gmtime(epoch)
        RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))



async def _main():
    gps = GPS()
    await gps.run()

try:
    from bsp import GPS_RX, GPS_TX
except ImportError:
    logger.error("gps not available")
    
    async def _main():
        pass

asyncio.create_task(_main())