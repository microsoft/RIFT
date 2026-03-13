import unittest
import sys
sys.path.append("../")
from librift.utils import parse_crate_string
class TestUtils(unittest.TestCase):

    def test_parse_crate_string(self):
        """Tests helper function parse_crate_string in utils.py"""
        s = "reqwest@2.2.2"
        c = parse_crate_string(s)
        self.assertEqual(c.name, "reqwest")
        self.assertEqual(c.version, "2.2.2")

        s2 = "hashbrown"
        c  =parse_crate_string(s2)
        self.assertEqual(c.name, s2)
        self.assertEqual(c.version, "")
        print("test_parse_crate_string success!")

if __name__ == "__main__":
    unittest.main()

