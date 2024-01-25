import asyncio
import logging
import ssl
import time  # type: ignore

from app import event_io
from user_features.wifi import wifi

from microdot import Microdot, Request
from microdot.websocket import with_websocket
    
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


Request.max_content_length = 1024 * 1024
Request.max_body_length    =   64 * 1024
Request.max_readline       =    8 * 1024

webapp = Microdot()

@webapp.get('/')
async def hello(request):
    return f"RV webapp\nserved with secure Let's Encrypt Certificate!\n{time.time()}\n"

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
    print("websocket ...")
    await event_io.serve(ws)

def init(host='0.0.0.0', port=80, debug=False):
    # config returns strings!
    port=int(port)
    if isinstance(debug, str):
        debug = debug == 'true' or debug == 'True'

    async def _main(host=host, port=port, debug=debug):
        async with wifi:
            logger.info(f"serving @ https://{wifi.hostname} ({wifi.ip})")
            if debug: print(f"serving @ https://{wifi.hostname} ({wifi.ip})")
            sslctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            sslctx.load_cert_chain('/certs/le-cert.der', '/certs/le-key.der')
            # Does this even make sense? Veryfy the client's certificate?
            # Chrome: dev.backend.leaf49.org didn’t accept your login certificate, or one may not have been provided.
            # sslctx.verify_mode = ssl.CERT_REQUIRED
            # sslctx.load_verify_locations(cafile="/certs/le-ca-chain.der")
            port=443
            try:
                await webapp.start_server(host=host, port=port, debug=debug, ssl=sslctx)
            except Exception as e:
                logger.exception("***** Webserver", e)

    asyncio.create_task(_main())
