import unittest
from backend.code.user_features.tsdb import *

BIG = False

if BIG:
    BLOCK_SIZE  = 4096      # >=128
    NBLOCKS     =  150
    DIR_RECORDS =   64
else:
    BLOCK_SIZE  =  128      # >=128
    NBLOCKS     =   30
    DIR_RECORDS =    8
  

class TestTSDB(unittest.TestCase):

    # @unittest.skip("skip test_make_db")
    def test_make_db(self):
        # create bdev and initialize db
        bdev = RAMBlockDev(BLOCK_SIZE, NBLOCKS) 
        key = 'e'
        extra = {key: 'X'}
        TSDB.make_db(bdev, DIR_RECORDS, extra)
        db = TSDB(bdev)
        self.assertEqual(db.free_blocks, NBLOCKS - db.capacity * DIR_RECORD_SIZE // BLOCK_SIZE - 1)
        self.assertTrue(db.capacity >= DIR_RECORDS)
        self.assertEqual(len(db.keys), 0)
        self.assertEqual(db.config[key], extra[key])
        for i in range(db.capacity):
            db.create_record(f"rec_{i}", 1)
        with self.assertRaises(TSDBException):
            db.create_record('no space')

    # @unittest.skip("skip test_create_record")
    def test_create_record(self):
        # create bdev and initialize db
        bdev = RAMBlockDev(BLOCK_SIZE, NBLOCKS) 
        TSDB.make_db(bdev, DIR_RECORDS)
        
        # fill db
        db = TSDB(bdev)
        self.assertEqual(db.keys, [])
        free = db.free_blocks
        db.create_record('a', capacity=1)
        self.assertEqual(db.free_blocks, free-2)
        free = db.free_blocks
        cap = (free-1)*BLOCK_SIZE/ITEM_SIZE-1
        db.create_record('b', capacity=cap)
        self.assertEqual(db.free_blocks, 0)
        self.assertEqual(db.record_capacity('b'), cap)
        self.assertEqual(db.keys, ['a', 'b'])
        
        # reload db from bdev
        db = TSDB(bdev)
        self.assertEqual(db.free_blocks, 0)
        self.assertEqual(db.keys, ['a', 'b'])
        with self.assertRaises(TSDBException):
            db.create_record('c')
        TSDB.make_db(bdev, 2)

    # @unittest.skip("skip test_append")
    def test_append(self):
        # create bdev and initialize db
        bdev = RAMBlockDev(BLOCK_SIZE, NBLOCKS) 
        TSDB.make_db(bdev, DIR_RECORDS)

        db = TSDB(bdev)
        db.create_record('a', 1)
        cap = db.record_capacity('a')
        val = array('f')
        ts  = array('I')
        for t in range(cap+BLOCK_SIZE//ITEM_SIZE):
            val.append(t**4+0.1)
            ts.append(t)
            db.append('a', t, t**4+0.1)
        self.assertEqual(ts,  db.values('a')['timestamps'])
        self.assertTrue(eq_af(val, db.values('a')['values']))

        # timestamp is increasing ints
        db.create_record('b', 1)
        cap = db.record_capacity('b')
        N = 2*cap+20
        for i in range(N):
            db.append('b', i, i)
            # verify that ts is increasing series of ints
            if i in [ 1, N//2, N-1]:
                ts = db.values('b')['timestamps']
                self.assertTrue(len(ts) >= min(i, cap))
                for j in range(len(ts)-1):
                    self.assertEqual(ts[j]+1, ts[j+1])

    # @unittest.skip("skip test_load")
    def test_load(self):
        # create bdev and initialize db
        bdev = RAMBlockDev(BLOCK_SIZE, NBLOCKS) 

        # create db and add some data
        TSDB.make_db(bdev, DIR_RECORDS)
        db = TSDB(bdev)
        db.create_record('a', 1)
        db.create_record('b', 3*db.record_capacity('a'))
        db.create_record('c', 1)
        for key in ['a', 'b']:
            for i in range(2*db.record_capacity(key)):
                db.append(key, i, i**4+0.1)
        ts_a = db.values('a')['timestamps']
        ts_b = db.values('b')['timestamps']
        ts_c = db.values('c')['timestamps']
        val_b = db.values('b')['values']

        # reload db
        db = TSDB(bdev)
        ts_a_reload = db.values('a')['timestamps']
        ts_b_reload = db.values('b')['timestamps']
        ts_c_reload = db.values('c')['timestamps']
        val_b_reload = db.values('b')['values']
        self.assertEqual(ts_a, ts_a_reload)
        self.assertEqual(ts_b, ts_b_reload)
        self.assertEqual(ts_c, ts_c_reload)
        self.assertTrue(eq_af(val_b, val_b_reload))

    # @unittest.skip("skip test_delete")
    def test_delete(self):
        # create bdev and initialize db
        bdev = RAMBlockDev(BLOCK_SIZE, NBLOCKS) 

        # create db and add some data
        TSDB.make_db(bdev, DIR_RECORDS)
        db = TSDB(bdev)
        keys = [ 'a', 'b', 'c', 'd' ]
        for key in keys:
            db.create_record(key, 1)
        self.assertEqual(db.keys, keys)
        db.append('c', 1, 1)
        db.delete_record('c')
        keys.remove('c')
        self.assertEqual(db.keys, keys)
        db.create_record('x', 1)
        keys.append('x')
        self.assertEqual(db.keys, keys)
        db.create_record('c', 1)
        keys.append('c')
        self.assertEqual(db.keys, keys)
        db.append('c', 2, 2)
        # by default, value returns new record
        self.assertEqual(db.values('c')['timestamps'], array('I', (2,)))
        # deleted record
        self.assertEqual(db.values('c', False)['timestamps'], array('I', (1,)))

        

def eq_af(a, b):
    # check equality of array('f')
    if len(a) != len(b): return False
    for x, y in zip(a, b):
        if x != y: return False
    return True


class RAMBlockDev:
    """Helper for testing.
    Example:
        bdev = RAMBlockDev(512, 64)
        TSDB.make_db(bdev, 16)
    """
    
    def __init__(self, block_size, num_blocks):
        self.block_size = block_size
        self.data = bytearray(block_size * num_blocks)

    def readblocks(self, block_num, buf):
        for i in range(len(buf)):
            buf[i] = self.data[block_num * self.block_size + i]

    def writeblocks(self, block_num, buf, offset=0):
        for i in range(len(buf)):
            self.data[offset + block_num * self.block_size + i] = buf[i]

    def ioctl(self, op, arg):
        if op == 4: # get number of blocks
            return len(self.data) // self.block_size
        if op == 5: # get block size
            return self.block_size
        if op == 6: # erase block
            buf = bytearray(self.block_size)
            for i in range(len(buf)): buf[i] = 0xff
            self.writeblocks(arg, buf)
