import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import universal_transform

class TestUniversalTransform(unittest.TestCase):

    def test_mga_parse(self):
        self.assertIs(universal_transform.mga_parse("MGA94"), "GDA94")
        self.assertIs(universal_transform.mga_parse("ITRF2008"), "ITRF2008")

    def test_resolve_path(self):
        self.assertListEqual(universal_transform.resolve_path("GDA94", "WGS84 (Transit)"), ['GDA94', 'ITRF2008', 'ITRF90', 'WGS84 (Transit)'])
    
if __name__ == '__main__':
    unittest.main()