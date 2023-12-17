from micropython import const 
import asyncio
import logging
import network   # type: ignore

from app import config, event_bus
from uping import ping

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

VERBOSE = False

class WifiException(Exception): pass

class _Wifi:

    def __init__(self):
        self._enabled_count = 0
        self._sta = network.WLAN(network.STA_IF)
        self._sta.active(True)
        nets = ", ".join([ f"{r[0].decode()} {r[2]}{r[3]}dbM" for r in self._sta.scan() if r[0] ])
        logger.debug(f"Visible Wifi Nets: {nets}")
        self._sta.active(False)
        network.hostname(config.get('secrets/wifi/hostname', default='leaf'))

    @property
    def enabled(self):
        return self._enabled_count > 0

    @property
    def isconnected(self):
        return self._sta.isconnected()
    
    @property
    def channel(self):
        return self._sta.config('channel')

    @property
    def ip(self):
        return self._sta.ifconfig()[0]

    @property
    def ip_bytes(self):
        return bytes([ int(x) for x in self.ip.split('.') ])

    @property
    def netmask(self):
        return self._sta.ifconfig()[1]

    @property
    def gateway_ip(self):
        return self._sta.ifconfig()[2]

    @property
    def dns_ip(self):
        return self._sta.ifconfig()[3]
    
    @property
    def hostname(self):
        return network.hostname()

    def ping(self, url=None, quiet=True):
        if not url: 
            # ping lan
            url = self.gateway_ip
        try:
            res = ping(url, quiet)
            return res[0] == res[1]
        except OSError:
            return False
        
    def ping_lan(self, quiet=True):
        return self.ping(quiet)
    
    def ping_internet(self, quiet=True):
        return ping('google.com', quiet)

    async def __aenter__(self):
        if self._enabled_count < 1:
            ssid = config.get('secrets/wifi/ssid')
            pwd  = config.get('secrets/wifi/pwd')
            sta = self._sta
            sta.active(True)
            for _ in range(50):
                if sta.active(): break
                await asyncio.sleep_ms(100)
            else:
                raise WifiException("Failed to acivate wifi network")
            await event_bus.post_state_update('wifi', 'channel', self.channel)
            logger.info(f"Connect to {ssid} ...")
            sta.connect(ssid, pwd)
            for n in range(200):
                if sta.isconnected(): break
                await asyncio.sleep_ms(100)
                if VERBOSE: print('.', end='')
            else:
                if VERBOSE: print()
                raise WifiException(f"Failed connecting to {ssid}")
            if VERBOSE: print()
            logger.info(f"connected @ {self.ip} in {n/100}s")
        self._enabled_count += 1

    async def __aexit__(self, *args):
        self._enabled_count -= 1
        if self._enabled_count < 1:
            self._sta.disconnect()
            self._sta.active(False)
            logger.info("disconnected from Wifi")


def init(verbose=False):
    global VERBOSE
    VERBOSE = verbose

wifi = _Wifi()
