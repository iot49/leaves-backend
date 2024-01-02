import asyncio
import sys, io, os
import unittest

if not "tests" in sys.path:
    sys.path.append("tests")

# TODO: async.sleep between individual test tasks to avoid timeout!

def run_all():
    class DUP(io.IOBase):
        def __init__(self, s):
            self.s = s
        def write(self, data):
            self.s += data
            return len(data)
        def readinto(self, data):
            return None
    
    try:
        s = bytearray()
        dup_stream = os.dupterm(DUP(s))
        for test in os.listdir('/tests'):
            if test == "testing.py": continue
            if not test.endswith('.py'): continue
            unittest.main(module=test[:-3])
    finally:
        os.dupterm(dup_stream)
    return s.decode()


async def run_all():
    # run all tests
    class DUP(io.IOBase):
        def __init__(self, s):
            self.s = s
        def write(self, data):
            self.s += data
            return len(data)
        def readinto(self, data):
            return None
        
    async def run(test):
        print(f'>>>>> Testing {test} ...')
        unittest.main(module=test)
    
    try:
        s = bytearray()
        dup_stream = os.dupterm(DUP(s))
        # run tests sequentially, yielding after each test
        for test in os.listdir('/tests'):
            if test.endswith('_test.py'):
                await asyncio.create_task(run(test[:-3]))
            await asyncio.sleep_ms(0)
    finally:
        os.dupterm(dup_stream)
    return s.decode()
