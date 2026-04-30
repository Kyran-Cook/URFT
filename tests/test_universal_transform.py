import unittest
from .. import universal_transform

class TestUniversalTransform(unittest.TestCase):

    def test_mga_parse(self):
        self.assertIs(universal_transform.mga_parse("MGA94"), "GDA94")
        self.assertIs(universal_transform.mga_parse("ITRF2008"), "ITRF2008")

    def test_resolve_path(self):
        self.assertIs(universal_transform.resolve_path("GDA94", "WGS84 (Transit)"), )
    
if __name__ == '__main__':
    unittest.main()