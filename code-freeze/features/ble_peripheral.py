from micropython import const
import bluetooth   # type: ignore
import asyncio
import aioble
import struct
import json
import logging
from io import BytesIO

from app import config
from .wifi import wifi


_MAX_CONNECTIONS  = const(3)     # maxium number of concurrent connections accepted
_DESIRED_MTU      = const(512)   # maximum permitted
_MTU_OVERHEAD     = const(3)     # send overhead in bytes

_ADV_APPEARANCE_GENERIC_COMPUTER = const(128)
_ADV_MANUFACTURER = const(0x1234)
_ADV_TIMEOUT_MS   = const(1000)
_ADV_INTERVAL_US  = const(250_000)

# message type for incoming messages
_MSG_PART         = const(0x1)
_MSG_COMPLETE     = const(0x2)

# magic for outgoing messages
_MAGIC            = const(0x82a1)

_SERVICE_UUID   = bluetooth.UUID("4d8b9851-05af-4ea0-99a5-cdbf9fd4104b")
_SERVICE_RX     = bluetooth.UUID("4d8b9852-05af-4ea0-99a5-cdbf9fd4104b")
_SERVICE_TX     = bluetooth.UUID("4d8b9853-05af-4ea0-99a5-cdbf9fd4104b")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class BLEPeripheral:

    def __init__(self):
        # initialize BLE
        aioble.core.log_level = 1
        aioble.config(gap_name=config.get('app/name'))
        aioble.config(mtu=_DESIRED_MTU)
        service = aioble.Service(_SERVICE_UUID)
        
        self._active_connections = {}
        self._rx_characteristic = aioble.Characteristic(service, _SERVICE_RX, indicate=True, write=True)
        self._tx_characteristic = aioble.BufferedCharacteristic(service, _SERVICE_TX, max_len=512, indicate=True, read=True)
        aioble.register_services(service)

    async def run(self):
        logger.info(f"advertising BLE peripheral '{aioble.config('gap_name').decode()}'")
        # run never returns (shutdown not implemented)
        asyncio.create_task(self._recv_task())
        while True:
            # manufacturer data: wifi ip, channel
            manuf_data = struct.pack('!4sB', wifi.ip_bytes, wifi.channel)
            try:
                connection = await aioble.advertise(
                    connectable=len(self._active_connections) <= _MAX_CONNECTIONS,
                    timeout_ms=_ADV_TIMEOUT_MS,
                    interval_us=_ADV_INTERVAL_US,
                    services=[_SERVICE_UUID],
                    appearance=_ADV_APPEARANCE_GENERIC_COMPUTER,
                    manufacturer=[_ADV_MANUFACTURER, manuf_data]
                )
                asyncio.create_task(self._handle_connection(connection))
            except asyncio.TimeoutError:
                # timeout regularly to update the wifi channel (in case it has changed)
                pass

    async def send(self, data: dict):
        if not self._active_connections:
            # nobody listening
            return
        # reserve one byte for message type
        mtu = _DESIRED_MTU - _MTU_OVERHEAD - 1

        data = json.dumps(data)
        assert 'type' in data, 'No type attribute'
        mv = memoryview(data)
        for index in range(0, len(data), mtu):
            # detect last iteration
            if index+mtu >= len(data):
                msg = _MSG_COMPLETE.to_bytes(1, 'little') + mv[index:]
            else:
                msg = _MSG_PART.to_bytes(1, 'little') + mv[index:index+mtu]
            self._tx_characteristic.write(msg, send_update=True)
            # delay needed for central to get all messages
            await asyncio.sleep_ms(100)
            # await self._tx_characteristic.indicate(list(self._active_connections.keys())[0], timeout_ms=1000)

    async def recv(self) -> dict:
        while True:
            try:
                return self._rx_buffer.popleft()
            except IndexError:
                pass
            await asyncio.sleep_ms(10)

    @property
    def connected(self):
        return len(self._active_connections) > 0

    async def _recv_task(self):
        rx = self._rx_characteristic
        while True:
            sender = await rx.written()
            buf = self._active_connections[sender]
            msg = rx.read()
            buf.write(msg[1:])
            if msg[0] == _MSG_COMPLETE:
                try:
                    data = json.loads(buf.getvalue())
                    data['src'] = sender.device.addr_hex()
                    self._rx_buffer.append(data)
                except ValueError:
                    print(f"***** BLEConnector: bogus json - discarded [{len(buf.getvalue())}] {buf.getvalue()}")
                finally:
                    # clear the buffer
                    self._active_connections[sender] = BytesIO()

                
    async def _handle_connection(self, connection):
        assert not (connection in self._active_connections)
        self._active_connections[connection] = BytesIO()
        print(f"> [{len(self._active_connections)}] connected to {connection.device}")
        try:
            self.mtu = await connection.exchange_mtu(_DESIRED_MTU)

            # STRANGE things happen on Mac when pairing ...
            # print(f"pair (no bonding), encrypted={connection.encrypted}, key_size={connection.key_size}")
            # await connection.pair(bond=False)
            # print(f"pairing complete, encrypted={connection.encrypted}, key_size={connection.key_size}")

            # wait for disconnect
            await connection.disconnected(timeout_ms=None)           
        finally:
            del self._active_connections[connection]
            print(f"< [{len(self._active_connections)}] disconnected from {connection.device}")


ble_peripheral = BLEPeripheral()


def init():
    async def _main():
        global ble_peripheral
        logger.info(f"starting ble_peripheral {config.get('app/name')}")
        await ble_peripheral.run()

    asyncio.create_task(_main())

