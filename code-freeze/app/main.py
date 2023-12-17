import asyncio
import sys
import logging
import machine   # type: ignore
import esp32     # type: ignore

from .config import config
from .event_bus import event_bus


def config_logging():
    class LogHandler(logging.Handler):
        def emit(self, r):
            # print(f"{timestamp.to_isodate(r.ct)} {r.levelname} {r.name}: {r.message}")

            # EventBus.post is async!
            async def log_event():
                await event_bus.post(
                    type='log', 
                    ct=r.ct,
                    levelno=r.levelno, 
                    levelname=r.levelname, 
                    name=r.name, 
                    message=r.message.strip())
            asyncio.create_task(log_event())

    root_logger = logging.getLogger() 
    # remove default handler
    root_logger.handlers = []
    root_logger.addHandler(LogHandler())

config_logging()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def load_feature(feature, params):
    module = None
    for mod in [ 'user_features', 'features' ]:
        path = f"{mod}.{feature}"
        if path in sys.modules.keys():
            logger.error(f"feature {feature} already imported!")
            return
        try:
            m = __import__(path)
            module = getattr(m, feature)
            logger.debug(f"loading feature {feature} with params {params}: {mod} -> {m} -> {module}")
            break
        except ImportError as e:
            pass
    
    if module:        
        try:
            module.init(**params)
        except TypeError as e:
            logger.error(f"feature {feature}: {e}")
        except AttributeError as e:
            if params: logger.error(f"feature {feature}: {e}")
    else:
        logger.error(f"no such feature: {feature}")


async def main():

    def exception_handler(_, context):
        logger.exception("global asyncio exception:", context["exception"])

    # set exception handler
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(exception_handler)

    try:
        from features.led import led
        led.pattern = led.GREEN_BLINK_SLOW

        # load features
        for feature, params in config.get(f"nodes/dev/features").items():
            load_feature(feature, params or {})

        # since we got here, we assume the app is working
        esp32.Partition.mark_app_valid_cancel_rollback()

        # start the wdt
        SLEEP_MS = 1000
        wdt = machine.WDT(id=0, timeout=2*SLEEP_MS)

        # and keep feeding it
        while True:
            wdt.feed()
            await asyncio.sleep_ms(SLEEP_MS)

    except KeyboardInterrupt as e:
        logger.exception("KeyboardInterrupt", e)
        # BAIL!
    except Exception as e:
        logger.exception("Exception in app.main", e)
    finally:
        logger.info("app.main EXITS")
