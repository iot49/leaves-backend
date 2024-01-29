import asyncio
import logging
import ssl
import gc
import time  # type: ignore
import timestamp

from app import event_io
from features.wifi import wifi

from microdot import Microdot, Request
from microdot.websocket import with_websocket

print("FIX mac /private/etc/hosts REMOVE entry for 'dev.backend.leaf49.org' (webserver.py)")

    
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


Request.max_content_length = 1024 * 1024
Request.max_body_length    =   64 * 1024
Request.max_readline       =    8 * 1024

webapp = Microdot()


# FIX gc before and after each request to fix (?) ssl memory issue
@webapp.before_request
async def collect1(request):
    gc.collect()

@webapp.after_request
async def collect2(request, response):
    gc.collect()

@webapp.get('/')
async def hello(request):
    return f"""RV webapp
served with secure Let's Encrypt Certificate!
{timestamp.to_isodate(time.time())}
timestamp = {time.time()}
"""

@webapp.get('/ping')
async def test(request):
    return "pong"

@webapp.get('/test')
async def test(request):
    # warning: wdt timeout if a single test runs long!
    from tests import run_all
    return await run_all()

@webapp.get('/ws')
@with_websocket
async def websocket(request, ws):
    await event_io.serve(ws)

def init(host='0.0.0.0', port=443, debug=False):
    # config returns strings!
    port=int(port)
    if isinstance(debug, str):
        debug = debug == 'true' or debug == 'True'

    async def _main(host=host, port=port, debug=debug):
        async with wifi:
            logger.info(f"serving @ https://{wifi.hostname} ({wifi.ip})")
            if debug: print(f"serving @ https://{wifi.hostname} ({wifi.ip})")
            try:
                sslctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                sslctx.load_cert_chain('/certs/le-cert.der', '/certs/le-key.der')
                await webapp.start_server(host=host, port=port, debug=debug, ssl=sslctx)
            except Exception as e:
                logger.exception("***** Webserver", e)

    asyncio.create_task(_main())
