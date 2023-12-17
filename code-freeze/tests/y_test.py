import unittest
import os
from collections import OrderedDict

from app import CONFIG_DIR
import y

class TestConfig(unittest.TestCase):

    def test_config_files(self):
        # breaks webserver ???
        try:
            dir = os.getcwd()
            os.chdir(CONFIG_DIR)
            for file in os.listdir():
                with self.subTest(f"Test {file}"):
                    with open(file) as stream:
                        obj = y.load(stream, file)
                        yml = y.dumps(obj)
                        self.assertEqual(str(obj), str(y.loads(yml, file)).replace("'None'", "None"))
        finally:
            os.chdir(dir)

    def test_patterns(self):
        tests = [ 
(
"""
a: aaa
b: bbb # comment

c:
dd:00:11:
dd:33: value_1: value_2
""",
OrderedDict({'a': 'aaa', 'b': 'bbb', 'c': None, 'dd:00:11': None, 'dd:33': 'value_1: value_2'})),

(
"""
- 1: a
- 2: b
- 3
- 4 # comment

-5
- 6:
- 7

""",
[OrderedDict({'1': 'a'}), OrderedDict({'2': 'b'}), '3', '4', '5', OrderedDict({'6': None}), '7']),

(
"""
a:
    b:
        c: ccc
        d: ddd
    e:
f:
""",
OrderedDict({'a': OrderedDict({'b': OrderedDict({'c': 'ccc', 'd': 'ddd'}), 'e': None}), 'f': None})),

(
"""
- 1
- 2:
- 3: 333
  4: 444
  5:
      - 555
      - 666:
          - 777:
            888:
            999:
                - a
                - b:
            000:
          - aaa
- 6
""",
['1', OrderedDict({'2': None}), OrderedDict({'3': '333', '4': '444', '5': ['555', OrderedDict({'666': [OrderedDict({'777': OrderedDict({'888': None, '999': ['a', OrderedDict({'b': None})], '000': None})}), 'aaa']})]}), '6']),

(
"""
    - k1:k2: v1: 4 v2 # comment
    - "1 k2:k3:k4 ":abc: def #comment
    - "k": "v" # c
    - 'k': 'v' # c
    - 'k': "v'" # c
    - "a: b':
      x:
    - y
""",
[OrderedDict({'k1:k2': 'v1: 4 v2'}), OrderedDict({'1 k2:k3:k4 ': 'abc: def'}), OrderedDict({'k': 'v'}), OrderedDict({'k': 'v'}), OrderedDict({'k': "v'"}), OrderedDict({'"a': "b':", 'x': None}), 'y']),

]
        for i, (test, expec) in enumerate(tests):
            with self.subTest(f"Test {i}"):
                obj = y.loads(test)
                yml = y.dumps(obj)
                self.assertEqual(str(obj), str(expec))
                self.assertEqual(str(obj), str(y.loads(yml)).replace("'None'", "None"))


# if __name__ == '__main__': unittest.main()