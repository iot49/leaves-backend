from micropython import const 
import asyncio
import logging
import network   # type: ignore
import uping

from app import config, event_bus

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

VERBOSE = False
SLEEP_MS = 100


class WifiException(Exception): pass

class _Radio:

    def __init__(self):
        self._enabled_count = 0
        self._sta = network.WLAN(network.STA_IF)

    def __enter__(self):
        if self._enabled_count < 1:
            self._sta.active(True)
            logger.debug("radio ON")
        self._enabled_count += 1

    def __exit__(self, *args):
        self._enabled_count -= 1
        if self._enabled_count < 1:
            self._sta.active(False)
            logger.debug("radio OFF")

    def scan(self):
        return "\n".join([ f"{r[0].decode():40} ch={r[2]:2} rssi={r[3]:3}dbM" for r in self._sta.scan() if r[0] ])


class _Wifi:

    def __init__(self):
        self._enabled_count = 0
        network.hostname(config.get('secrets/wifi/hostname', default='leaf'))

    @property
    def channel(self):
        return radio._sta.config('channel')

    @property
    def ip(self):
        return radio._sta.ifconfig()[0]

    @property
    def ip_bytes(self):
        return bytes([ int(x) for x in self.ip.split('.') ])

    @property
    def netmask(self):
        return radio._sta.ifconfig()[1]

    @property
    def gateway_ip(self):
        return radio._sta.ifconfig()[2]

    @property
    def dns_ip(self):
        return radio._sta.ifconfig()[3]
    
    @property
    def hostname(self):
        return network.hostname()

    def _find_ap(self):
        """Scan to find best available access point.
        Return (ssid, pwd)."""
        return (config.get('secrets/wifi/ssid'), config.get('secrets/wifi/pwd'))
    
    def ping(self, url=None, quiet=True):
        if not url: 
            # ping lan
            url = self.gateway_ip
        try:
            res = uping.ping(url, quiet=quiet)
            return res[0] == res[1]
        except OSError as e:
            return False
        
    def ping_lan(self, quiet=True):
        return self.ping(quiet=quiet)
    
    def ping_wan(self, quiet=True):
        return self.ping("google.com", quiet=quiet)

    def scan(self):
        return radio.scan()

    async def __aenter__(self):
        if self._enabled_count < 1:
            radio.__enter__()
            ssid, pwd = self._find_ap()
            await event_bus.post_state_update('wifi', 'channel', self.channel)
            logger.info(f"Connect to {ssid} ...")
            radio._sta.connect(ssid, pwd)
            for n in range(20_000//SLEEP_MS):
                if radio._sta.isconnected(): break
                await asyncio.sleep_ms(SLEEP_MS)
                if VERBOSE: print('.', end='')
            else:
                if VERBOSE: print()
                from features.led import led   # type: ignore
                led.pattern = led.RED_BLINK_FAST
                logger.error(f"Failed connecting to {ssid}")
                raise WifiException(f"Failed connecting to {ssid}")
            if VERBOSE: print(f' ip={self.ip}')
            logger.info(f"connected @ {self.ip} in {n*SLEEP_MS/1000}s")
        self._enabled_count += 1

    async def __aexit__(self, *args):
        self._enabled_count -= 1
        if self._enabled_count < 1:
            radio._sta.disconnect()
            radio.__exit__()
            logger.info("disconnected from Wifi")

def init(verbose=False, sleep_ms=100):
    global VERBOSE, SLEEP_MS
    VERBOSE = verbose
    SLEEP_MS = sleep_ms

radio = _Radio()
wifi  = _Wifi()

VERBOSE = True
