import asyncio
import sys
import logging
import machine   # type: ignore
import esp32     # type: ignore
import micropython

from .config import config
from .eid import IS_GATEWAY, NODE_ID
from .event_bus import event_bus

RESET_CAUSE = {
    machine.PWRON_RESET: 'power-on',
    machine.HARD_RESET: 'hard reset',
    machine.WDT_RESET: 'watchdog timer',
    machine.DEEPSLEEP_RESET: 'deepsleep reset',
    machine.SOFT_RESET: 'soft reset'
}

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


micropython.alloc_emergency_exception_buf(200)

config_logging()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def load_feature(feature, params):
    module = None
    for mod in [ 'user_features', 'features' ]:
        path = f"{mod}.{feature}"
        if path in sys.modules.keys():
            logger.warning(f"feature {feature} already imported!")
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
        except AttributeError as e:
            if params: logger.error(f"feature {feature}: {e}")
        except (TypeError, Exception) as e:
            logger.exception(f"feature {feature}: {e}")
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
        tp = 'gateway' if IS_GATEWAY else 'leaf'
        for feature, params in config.get(f"app/default_features/{tp}", {}).items():
            load_feature(feature, params or {})
        for feature, params in config.get(f"app/nodes/{NODE_ID}/features", {}).items():
            load_feature(feature, params or {})

        # reset cause
        logger.info(f"reset cause: {RESET_CAUSE.get(machine.reset_cause(), 'unknown')}")
        print(f"reset cause: {RESET_CAUSE.get(machine.reset_cause(), 'unknown')}")

        # since we got here, we assume the app is working
        esp32.Partition.mark_app_valid_cancel_rollback()

        # start the wdt
        SLEEP_MS = int(config.get('app/timeout/wdt_ms', 5000))
        wdt = machine.WDT(id=0, timeout=SLEEP_MS)

        # and keep feeding it
        while True:
            wdt.feed()
            await asyncio.sleep_ms(SLEEP_MS // 2)

    except KeyboardInterrupt as e:
        print("\n***** KeyboardInterrupt")
        logger.exception("KeyboardInterrupt", e)
        # BAIL!
    except Exception as e:
        logger.exception("Exception in app.main", e)
        raise
    finally:
        logger.info("app.main EXITS")
