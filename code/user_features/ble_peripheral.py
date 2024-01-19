from micropython import const
import bluetooth   # type: ignore
import asyncio
import aioble
import struct
import logging
from io import BytesIO
from collections import deque

from app import config, event_io
from features.wifi import wifi


_DESIRED_MTU      = const(512)   # maximum permitted
_MTU_OVERHEAD     = const(3)     # send overhead in bytes

_ADV_APPEARANCE_GENERIC_COMPUTER = const(128)
_ADV_MANUFACTURER = const(0x1234)
_ADV_TIMEOUT_MS   = const(1000)
_ADV_INTERVAL_US  = const(250_000)

# message type for incoming messages
_MSG_PART         = const(0x1)
_MSG_COMPLETE     = const(0x2)

_SERVICE_UUID     = bluetooth.UUID("4d8b9851-05af-4ea0-99a5-cdbf9fd4104b")
_SERVICE_RX       = bluetooth.UUID("4d8b9852-05af-4ea0-99a5-cdbf9fd4104b")
_SERVICE_TX       = bluetooth.UUID("4d8b9853-05af-4ea0-99a5-cdbf9fd4104b")

_RX_QUEUE_SZ      = const(10)
_TX_QUEUE_SZ      = const(10)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class BLEPeripheral:

    def __init__(self):
        # initialize BLE
        aioble.core.log_level = 1
        aioble.config(gap_name=config.get('app/name'))
        aioble.config(mtu=_DESIRED_MTU)
        service = aioble.Service(_SERVICE_UUID)
        self._connection = None
        # is there a use for max_len > mtu?
        self._rx_characteristic = aioble.BufferedCharacteristic(service, _SERVICE_RX, max_len=2*_DESIRED_MTU, indicate=True, write=True, capture=True)
        self._tx_characteristic = aioble.BufferedCharacteristic(service, _SERVICE_TX, max_len=2*_DESIRED_MTU, indicate=True, read=True)
        aioble.register_services(service)

    async def run(self):
        logger.info(f"Advertising BLE peripheral '{aioble.config('gap_name').decode()}'")
        while True:
            # manufacturer data: wifi ip, channel
            manuf_data = struct.pack('!4sB', wifi.ip_bytes, wifi.channel)
            try:
                connection = await aioble.advertise(
                    connectable=not self.connected,
                    timeout_ms=_ADV_TIMEOUT_MS,
                    interval_us=_ADV_INTERVAL_US,
                    services=[_SERVICE_UUID],
                    appearance=_ADV_APPEARANCE_GENERIC_COMPUTER,
                    manufacturer=[_ADV_MANUFACTURER, manuf_data]
                )
                self._connection = connection
                self._rx_buffer = deque((), _RX_QUEUE_SZ, 1)
                self._tx_buffer = deque((), _TX_QUEUE_SZ, 1)

                asyncio.create_task(self._handle_connection())
            except asyncio.TimeoutError:
                # timeout regularly to update the wifi channel (in case it has changed)
                pass
            except Exception as e:
                logger.exception("run", e)

    async def send(self, data: bytes) -> None:
        # we use a queue to ensure that parts of messages exceeding mtu size are sent successively
        while self.connected:
            try:
                self._tx_buffer.append(data)
                break
            except IndexError:
                # buffer full
                await asyncio.sleep_ms(100)

    async def receive(self) -> bytes:
        while self.connected:
            try:
                return self._rx_buffer.popleft()
            except IndexError:
                pass
            await asyncio.sleep_ms(10)
        return b''

    async def close(self):
        # Compatibility with websocket
        print(f"BlePeripheral disconnected from {self._connection.device}")
        self._connection = None

    @property
    def connected(self):
        return self._connection != None
    
    @property
    def closed(self):
        # Compatibility with websocket
        return not self.connected

    async def _recv_task(self):
        rx = self._rx_characteristic
        buf = BytesIO()
        while self.connected:
            connection, msg = await rx.written()
            # assert connection == self._connection
            buf.write(msg[1:])
            if msg[0] == _MSG_COMPLETE:
                try:
                    self._rx_buffer.append(buf.getvalue())
                except Exception as e:
                    logger.exception("_recv_task", e)
                finally:
                    # clear the buffer
                    buf = BytesIO()
                
    async def _send_task(self):
        while self.connected:
            # fetch next message
            while self.connected:
                try:
                    data = self._tx_buffer.popleft()
                    break
                except IndexError:
                    pass
                await asyncio.sleep_ms(10)
            else:
                return
            # send message
            mv = memoryview(data)
            mtu = self._mtu - _MTU_OVERHEAD - 1
            for index in range(0, len(data), mtu):
                # detect last iteration
                if index+mtu >= len(data):
                    msg = _MSG_COMPLETE.to_bytes(1, 'little') + mv[index:]
                else:
                    msg = _MSG_PART.to_bytes(1, 'little') + mv[index:index+mtu]
                try:
                    await self._tx_characteristic.indicate(self._connection, timeout_ms=1000, data=msg)
                except ValueError:
                    # "in progress", thrown by aioble/server.py
                    # raised (only?) on abrupt client disconnect
                    # investigate if random disconnects occur
                    self.close()
                    return
                except Exception as e:
                    logger.exception("_send_task", e)

    async def _handle_connection(self):
        print("BlePeripheral connected from", self._connection, self._connection.device)
        try:
            self._mtu = await self._connection.exchange_mtu(_DESIRED_MTU)
            asyncio.create_task(self._send_task())
            asyncio.create_task(self._recv_task())

            asyncio.create_task(event_io.serve(self))
            # await event_io.serve(self)

            # STRANGE things happen on Mac when pairing ...
            # print(f"pair (no bonding), encrypted={connection.encrypted}, key_size={connection.key_size}")
            # await connection.pair(bond=False)
            # print(f"pairing complete, encrypted={connection.encrypted}, key_size={connection.key_size}")

            # wait for disconnect
            await self._connection.disconnected(timeout_ms=None)
        except Exception as e:
            logger.exception("_handle_connection", e)
        finally:
            self.close()


ble_peripheral = BLEPeripheral()


def init():
    async def _main():
        global ble_peripheral
        logger.info(f"starting {config.get('app/name')}")
        print(f"starting {config.get('app/name')}")
        await ble_peripheral.run()

    asyncio.create_task(_main())

