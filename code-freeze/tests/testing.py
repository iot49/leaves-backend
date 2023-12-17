import sys, io, os
import unittest

if not "tests" in sys.path:
    sys.path.append("tests")

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
