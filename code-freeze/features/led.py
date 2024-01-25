import asyncio
from machine import Pin         # type: ignore
from neopixel import NeoPixel   # type: ignore

from bsp import LED

"""
On-board LED

Example:
    from features import led
    led.pattern = led.RGB_FAST
    # ...
    led.pattern = led.BLUE_BLINK_SLOW
"""


class _LED:

    # few colors ...
    OFF   = (0, 0, 0)
    WHITE = (255, 255, 255)
    RED   = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLUE  = (0, 0, 255)
    
    # few patterns
    # format: list/tuple of (color, duration_ms)
    LED_OFF = ((OFF, 1000))
    
    RED_BLINK_SLOW = ((RED, 150), (OFF, 1500))
    RED_BLINK_FAST = ((RED, 150), (OFF, 150))
    
    GREEN_BLINK_SLOW = ((GREEN, 150), (OFF, 1500))
    GREEN_BLINK_FAST = ((GREEN, 150), (OFF, 150))
    
    BLUE_BLINK_SLOW = ((BLUE, 150), (OFF, 1500))
    BLUE_BLINK_FAST = ((BLUE, 150), (OFF, 150))
    
    RGB_SLOW = ((RED, 1000), (GREEN, 1000), (BLUE, 1000))
    RGB_FAST = ((RED, 150), (GREEN, 150), (BLUE, 150))

    def __init__(self):
        self._np = NeoPixel(Pin(LED), 1)
        self.pattern = self.GREEN_BLINK_SLOW

    async def run(self):
        print("led.run")
        n = -1
        while True:
            n = (n+1) % len(self.pattern)
            color, ms = self.pattern[n]
            self._np[0] = color
            self._np.write()
            await asyncio.sleep_ms(ms)



# create led singleton
led = _LED()

print("LED!")
# start blink task
asyncio.create_task(led.run())

