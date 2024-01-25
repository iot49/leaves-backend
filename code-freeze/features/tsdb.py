import json
import io
import logging
import math
import struct
from array import array
from micropython import const  # type: ignore

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


VERSION = "1.0"
MAGIC   = const(0x07fdabbc)

# type, block_addr, nblocks, key
DIR_RECORD_SIZE = const(64)           # size of directory records in bytes   
DIR_RECORD_FMT  = f"3I{DIR_RECORD_SIZE-12}s"    # 12 accounts for 3I header
DIR_TYPE_BLANK  = const(0xffffffff)   # available 
DIR_TYPE_CBUF   = const(0x01a2b3c4)   # allocated (for circular buffer)
DIR_TYPE_DEL    = const(0x00000000)   # deleted

ITEM_FMT        = "If"                # timestamp (uint), value (float)
ITEM_SIZE       = const(8)            # bytes


class TSDBException(Exception):
    pass


class TSDB:

    @classmethod
    def make_db(cls, block_dev, capacity: int, config={}):
        """Erase create empty db (erases existing data)
        @param capacity: Maximum number of records the db can hold
        @param config: optional configuration data"""
        BLOCK_SIZE = block_dev.ioctl(5, None)
        assert is_power_of_2(ITEM_SIZE), f"ITEM_SIZE ({ITEM_SIZE}) must be a power of two"
        assert is_power_of_2(BLOCK_SIZE), f"block size ({BLOCK_SIZE}) must be a power of two"
        assert BLOCK_SIZE >= DIR_RECORD_SIZE, f"block size must be equal or greater than {DIR_RECORD_SIZE}"

        # write configuration to block[0]
        _erase_block(block_dev, 0)
        config['description'] = "Time Series DataBase"
        config['version'] = VERSION
        config['magic'] = MAGIC
        config['block_size'] = BLOCK_SIZE
        config['num_dir_blocks'] = int(math.ceil(capacity*DIR_RECORD_SIZE/BLOCK_SIZE))
        j = json.dumps(config).encode()
        assert len(j) <= BLOCK_SIZE, f"configuration data ({len(j)}) exceeds BLOCK_SIZE ({BLOCK_SIZE})"
        block_dev.writeblocks(0, j, 0)
        # erase directory blocks
        for i in range(1, config['num_dir_blocks']+1):
            _erase_block(block_dev, i)
      
    def __init__(self, block_dev):
        """Open a database previously created with TSDB.make_db.
        @exception TSDBException for corrupted database
        
        Example:
            bdev = Partition.find(type=Partition.TYPE_DATA, label='data_1')[0]
            TSDB.make_db(bdev, 256)
            db = TSDB(bdev)
            db.create_record('temperature_data', 1023)
            db.append('temperature_data', timestamp, 22.5)
            db.values('temperature_data') -> { 'timestamp': Array('I', [...]), 'value': ... }
            print(db)
        """
        self.NBLOCKS = block_dev.ioctl(4, None)      # number of blocks in block_dev
        self.BLOCK_SIZE = block_dev.ioctl(5, None)   # block size in bytes
        self._bdev = block_dev
        self._read_header()
        self._read_records()

    @property
    def config(self):
        return self._config

    @property
    def capacity(self):
        """Number of records the database can hold."""
        return self._config['num_dir_blocks'] * self.BLOCK_SIZE // DIR_RECORD_SIZE

    def record_capacity(self, key: str):
        """Minimum number of items record can hold.
        The actual size may be greater depending on the state of the circular buffer."""
        try:
            rec = next(x for x in self._records if x['key'] == key)
            return (rec['nblocks']-1)*self.BLOCK_SIZE // ITEM_SIZE - 1
        except StopIteration:
            raise TSDBException(f"Record '{key}' not in database")

    @property
    def free_blocks(self):
        """Number of free blocks to hold records.
        The smallest record has two blocks and holds BLOCK_SIZE/ITEM_SIZE-1 items.
        Each additional block adds BLOCK_SIZE/ITEM_SIZE items.
        A record with N blocks holds (N-1)*BLOCK_SIZE/ITEM_SIZE-1 items."""
        if len(self._records) < 1:
            return self.NBLOCKS - self._config['num_dir_blocks'] - 1
        else:
            r = self._records[-1]
            return self.NBLOCKS - r['block_addr'] - r['nblocks']

    @property
    def keys(self) -> list:
        """Keys to all records stored in the database."""
        return [ r['key'] for r in self._records if r['type'] == DIR_TYPE_CBUF ]

    def values(self, key: str, ignore_deleted=True) -> dict:
        """Dict with timestamps and values as arrays.
        @param ignore_deleted: set to False to return values records marked "deleted"
        """
        rec = self._find_record(key, ignore_deleted)
        BLOCK_SIZE = self.BLOCK_SIZE
        nblocks = rec['nblocks']
        buf = bytearray(BLOCK_SIZE)
        bdev = self._bdev
        blank = b'\xff\xff\xff\xff\xff\xff\xff\xff'
        val = array('f')
        ts  = array('I')
        start  = rec['start']
        block  = start // BLOCK_SIZE
        mv = memoryview(buf)
        while True:
            assert block < nblocks
            bdev.readblocks(rec['block_addr'] + block, buf)
            for offset in range(0, BLOCK_SIZE, ITEM_SIZE):
                item = mv[offset:offset+ITEM_SIZE]
                if item == blank: 
                    return { 'timestamps': ts, 'values': val }
                t, v = struct.unpack(ITEM_FMT, item)
                val.append(v)
                ts.append(t)
            block = (block+1) % nblocks

    def create_record(self, key: str, capacity=1023):
        """Create new time-series record with given key (if it does not exist already).
        @param key: arbitrary but unique identifier
        @param capacity (items): will be rounded to next block boundary. E.g. for BLOCK_SIZE=4096
               capacity   blocks
                 <512        2
                <1024        3
                <1536        4
                <2048        5
        """
        # already in database?
        if key in self.keys:
            return
        # check available space in dir structure
        if len(self._records) >= self.capacity:
            raise TSDBException('Directory structure full')
        if len(self._records) < 1:
            block_addr = self._config['num_dir_blocks'] + 1
        else:
            r = self._records[-1]
            block_addr = r['block_addr'] + r['nblocks']
        nblocks = int(math.ceil((capacity+1)*ITEM_SIZE/self.BLOCK_SIZE+1))
        # check available space for cbuf's
        if self.free_blocks < nblocks:
            raise TSDBException(f'Insufficient space: need {nblocks} blocks, {self.free_blocks} free')
        # erase space for new record
        for i in range(block_addr, block_addr+nblocks):
            _erase_block(self._bdev, i)
        # write new record
        rec = struct.pack(DIR_RECORD_FMT, DIR_TYPE_CBUF, block_addr, nblocks, key)
        byte_addr = len(self._records)*DIR_RECORD_SIZE
        block_num = byte_addr // self.BLOCK_SIZE
        offset    = byte_addr %  self.BLOCK_SIZE
        self._bdev.writeblocks(block_num+1, rec, offset)
        self._records.append({ 'key': key, 'block_addr': block_addr, 'nblocks': nblocks, 'type': DIR_TYPE_CBUF, 'start': 0, 'next': 0 }) 

    def append(self, key: str, timestamp: int, value: float):
        """Add new (timestamp, value) tuple to record, overwriting oldest entries as needed"""
        rec = self._find_record(key)
        BLOCK_SIZE = self.BLOCK_SIZE
        nblocks = rec['nblocks']
        # sufficient space in current block?
        nxt = rec['next']
        block  = nxt // BLOCK_SIZE
        offset = nxt %  BLOCK_SIZE
        if BLOCK_SIZE-offset <= ITEM_SIZE:
            nxt_block = (block+1) % nblocks
            _erase_block(self._bdev, rec['block_addr']+nxt_block)
            rec['start'] = ((nxt_block+1) % nblocks) * BLOCK_SIZE
        # write
        self._bdev.writeblocks(rec['block_addr']+block, struct.pack(ITEM_FMT, timestamp, value), offset)
        # compute new p
        rec['next'] = (nxt + ITEM_SIZE) % (nblocks * BLOCK_SIZE)

    def delete_record(self, key: str):
        """Mark record "deleted".
        Note: the data is not actually removed from the database and can still be accessed by setting 
        'ignore_deleted' to False in keys and values.
        Backup, delete, and restore the database to actually delete the data from the block_device.
        It's not possible to "undelete" records.
        """
        try:
            index, rec = next((i, x) for i, x in enumerate(self._records) if x['key'] == key and x['type'] == DIR_TYPE_CBUF)
        except StopIteration:
            raise TSDBException(f"Record '{key}' not in database")
        # write new record
        new_rec = struct.pack(DIR_RECORD_FMT, DIR_TYPE_DEL, rec['block_addr'], rec['nblocks'], key)
        byte_addr = index*DIR_RECORD_SIZE
        block_num = byte_addr // self.BLOCK_SIZE
        offset    = byte_addr %  self.BLOCK_SIZE
        self._bdev.writeblocks(block_num+1, new_rec, offset)
        rec['type'] = DIR_TYPE_DEL

    def __str__(self):
        BLOCK_SIZE = self.BLOCK_SIZE
        config = self._config
        records = self._records
        s = io.StringIO()
        s.write(f"{config['description']} Version {config['version']}\n")
        s.write(f"Blocks:  {self.NBLOCKS:4} total, {self.free_blocks:4} free\n")
        s.write(f"Records: {self.capacity:4} total, {self.capacity-len(records):4} free\n")
        s.write(f"{len(records)} Record(s)\n")
        for r in records:
            s.write(f"  {r['key']:30} capacity: {self.record_capacity(r['key'])} @ block address {r['block_addr']:4}\n")
        return s.getvalue()
    
    def _find_record(self, key: str, ignore_deleted=True):
        try:
            rec = next(x for x in self._records if (x['key'] == key) and (x['type'] == DIR_TYPE_CBUF or not ignore_deleted))
        except StopIteration:
            raise TSDBException(f"Record '{key}' not in database")
        return rec
        
    def _read_header(self):
        buf = bytearray(self.BLOCK_SIZE)
        self._bdev.readblocks(0, buf)
        if buf[0] == 0xff:
            raise TSDBException("No valid database found on block device. Run TDDB.make_db.")
        try:
            buf = buf[:buf.index(b'\xff')]
        except ValueError:
            pass
        self._config = json.loads(buf)
        assert self._config['version'] == VERSION, f"version {self._config['version']} not supported"
        assert self._config['magic'] == MAGIC, f"wrong magic number, {self._config['magic']:08x}"
        assert self._config['block_size'] == self.BLOCK_SIZE

    def _read_records(self):
        BLOCK_SIZE = self.BLOCK_SIZE
        buf = bytearray(BLOCK_SIZE) 
        self._records = records = []
        for dir_block_index in range(1, self._config['num_dir_blocks']+1):
            self._bdev.readblocks(dir_block_index, buf)
            mv = memoryview(buf)
            for i in range(BLOCK_SIZE // DIR_RECORD_SIZE):
                offset = i*DIR_RECORD_SIZE
                tp, addr, n, key = struct.unpack(DIR_RECORD_FMT, mv[offset:offset+DIR_RECORD_SIZE])
                try:
                    key = key[:key.index(b'\x00')].decode()
                except ValueError:
                    pass
                if tp == DIR_TYPE_BLANK: return
                rec = { 'key': key, 'block_addr': addr, 'nblocks': n, 'type': tp }
                self._records.append(rec) 
                self._find_start_next(rec)

    def _find_start_next(self, rec):
        """Determine addresses (addr) for first item (start) and insert point (next) in circular buffer."""
        BLOCK_SIZE = self.BLOCK_SIZE
        buf = bytearray(BLOCK_SIZE)
        nblocks = rec['nblocks']
        block_addr = rec['block_addr']
        bdev = self._bdev

        nxt = -1
        for block in range(nblocks):
            a, b = self._block_fill(block_addr+block, buf)
            if not a and not b:
                # full block, check if next one is empty
                nxt_block = (block+1) % nblocks
                aa, bb = self._block_fill(block_addr+nxt_block, buf)
                if aa and bb:
                    nxt = nxt_block * BLOCK_SIZE
                    break
            if not a and b:
                # partially full block
                mv = memoryview(buf)
                blank = b'\xff\xff\xff\xff\xff\xff\xff\xff'
                for offset in range(0, BLOCK_SIZE, ITEM_SIZE):
                    if mv[offset:offset+ITEM_SIZE] == blank:                      
                        nxt = block*BLOCK_SIZE + offset
                        break
                assert mv[offset:offset+ITEM_SIZE] == blank
                break
                
        if nxt == -1:
            # empty database
            rec['start'] = rec['next'] = 0
            return
        # start is beginning of first non-empty block after next
        block = nxt // BLOCK_SIZE
        while True:
            block = (block+1) % nblocks
            a, b = self._block_fill(block_addr+block, buf)
            if not a:
                start = block * BLOCK_SIZE
                break
        rec['start'] = start
        rec['next']  = nxt

    def _block_fill(self, block_num, buf):
        """Check block status
           @return (start empty, tail empty)"""
        blank = b'\xff\xff\xff\xff\xff\xff\xff\xff'
        self._bdev.readblocks(block_num, buf)
        return (buf[:8]  == blank, buf[-8:] == blank)
    

def _erase_block(bdev, block_num):
    assert block_num < bdev.ioctl(4, None)
    bdev.ioctl(6, block_num)

def is_power_of_2(n):
    return (n & (n-1) == 0) and n != 0




from esp32 import Partition    # type: ignore

def init(partition='data_1'):
    global db, bdev
    bdev = Partition.find(type=Partition.TYPE_DATA, label=partition)[0]
    try:
        db = TSDB(bdev)
    except TSDBException as e:
        logger.exception("Failed initializing tsdb - creating new one", e)
        bdev = Partition.find(type=Partition.TYPE_DATA, label='data_1')[0]
        TSDB.make_db(bdev, 4096)
        db = TSDB(bdev)
