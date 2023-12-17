import asyncio
import logging

from app import event_io
from .wifi import wifi

from microdot_asyncio import Microdot, Request
from microdot_asyncio_websocket import with_websocket
    
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


Request.max_content_length = 1024 * 1024
Request.max_body_length    =   64 * 1024
Request.max_readline       =    8 * 1024

webapp = Microdot()

@webapp.get('/')
async def hello(request):
    return "RV webapp"

@webapp.get('/ping')
async def test(request):
    return "pong"

@webapp.get('/test')
async def test(request):
    from tests import testing
    return testing.run_all()

@webapp.get('/ws')
@with_websocket
async def websocket(request, ws):
    await event_io.serve(ws)

def init(host='0.0.0.0', port=80, debug=False):

    # config returns strings!
    port=int(port)
    if isinstance(debug, str):
        debug = debug == 'true' or debug == 'True'

    async def _main(host=host, port=port, debug=debug):
        async with wifi:
            logger.info(f"serving @ http://{wifi.hostname} (http://{wifi.ip})")
            await webapp.start_server(host=host, port=port, debug=debug)

    asyncio.create_task(_main())

