import unittest
import sys
import os
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import universal_transform

class TestUniversalTransform(unittest.TestCase):

    def test_mga_parse(self):
        self.assertEqual(universal_transform.mga_parse("MGA94"), "GDA94")
        self.assertEqual(universal_transform.mga_parse("ITRF2008"), "ITRF2008")

    def test_resolve_path(self):
        self.assertListEqual(universal_transform.resolve_path("GDA94", "WGS84 (Transit)"), ['GDA94', 'ITRF2008', 'ITRF90', 'WGS84 (Transit)'])
        self.assertListEqual(universal_transform.resolve_path("AGD66", "ITRF2020"), ['AGD66', 'GDA94', 'GDA2020', 'ITRF2014', 'ITRF2020'])

    def test_ref_name_parser(self):
        self.assertEqual(universal_transform.ref_frame_parser("WGS84 Ensemble"), "wgs84ensemble")
        self.assertEqual(universal_transform.ref_frame_parser("GDA2020"), "gda2020")

    def test_transformation_type(self):
        self.assertEqual(universal_transform.transformation_type(['AGD66', 'GDA94', 'GDA2020', 'ITRF2014', 'ITRF2020']), "static_to_dynamic")
        self.assertEqual(universal_transform.transformation_type(['ITRF2020', 'ITRF90', 'WGS84 (Transit)']), "dynamic_to_dynamic")

    def test_universal_transform(self):
        results1 = universal_transform.universal_transform(-4130636.759,2894953.142,-3890530.249, "GDA94", "MGA2020", return_type="enu")
        results2 = universal_transform.universal_transform(-4130636.759,2894953.142,-3890530.249, "ITRF90", "GDA2020", date(2000,1,1), return_type="llh")
        results3 = universal_transform.universal_transform(-4130636.759,2894953.142,-3890530.249, "GDA2020", "ITRF2008", to_epoch=date(2008,1,1))
        results4 = universal_transform.universal_transform(-4130636.759,2894953.142,-3890530.249, "ATRF2014", "ITRF97", date(2020,1,1), date(2000,1,1))

        expected1 = [55, 321820.5725, 5811182.98, 40.4909]
        expected2 = [-37.8294, 144.9753, 40.5248]
        expected3 = [-4130636.286, 2894953.0932, -3890530.7837]
        expected4 = [-4130635.9789, 2894953.069, -3890531.185]

        self.assertEqual(results1["coords"]["zone"], expected1[0])
        self.assertAlmostEqual(results1["coords"]["east"], expected1[1],3)
        self.assertAlmostEqual(results1["coords"]["north"], expected1[2],3)
        self.assertAlmostEqual(results1["coords"]["el_height"], expected1[3],3)

        self.assertAlmostEqual(results2["coords"]["lat"], expected2[0],3)
        self.assertAlmostEqual(results2["coords"]["lon"], expected2[1],3)
        self.assertAlmostEqual(results2["coords"]["el_height"], expected2[2],3)

        self.assertAlmostEqual(results3["coords"]["x"], expected3[0],3)
        self.assertAlmostEqual(results3["coords"]["y"], expected3[1],3)
        self.assertAlmostEqual(results3["coords"]["z"], expected3[2],3)

        self.assertAlmostEqual(results4["coords"]["x"], expected4[0],3)
        self.assertAlmostEqual(results4["coords"]["y"], expected4[1],3)
        self.assertAlmostEqual(results4["coords"]["z"], expected4[2],3)

    def test_universal_transform_llh(self):
        results1 = universal_transform.universal_transform_llh(-37.829403199, 144.975341111, 40.579712832, "GDA94", "MGA2020", return_type="enu")
        results2 = universal_transform.universal_transform_llh(-37.829403199, 144.975341111, 40.579712832, "ITRF90", "GDA2020", date(2000,1,1), return_type="llh")
        results4 = universal_transform.universal_transform_llh(-37.829403199, 144.975341111, 40.579712832, "ATRF2014", "ITRF97", date(2020,1,1), date(2000,1,1), return_type="xyz")

        expected1 = [55, 321820.5725, 5811182.98, 40.4909]
        expected2 = [-37.8294, 144.9753, 40.5248]
        expected4 = [-4130635.9789, 2894953.069, -3890531.185]

        self.assertEqual(results1["coords"]["zone"], expected1[0])
        self.assertAlmostEqual(results1["coords"]["east"], expected1[1],3)
        self.assertAlmostEqual(results1["coords"]["north"], expected1[2],3)
        self.assertAlmostEqual(results1["coords"]["el_height"], expected1[3],3)

        self.assertAlmostEqual(results2["coords"]["lat"], expected2[0],3)
        self.assertAlmostEqual(results2["coords"]["lon"], expected2[1],3)
        self.assertAlmostEqual(results2["coords"]["el_height"], expected2[2],3)

        self.assertAlmostEqual(results4["coords"]["x"], expected4[0],3)
        self.assertAlmostEqual(results4["coords"]["y"], expected4[1],3)
        self.assertAlmostEqual(results4["coords"]["z"], expected4[2],3) 

    def test_universal_transform_enu(self): 
        results1 = universal_transform.universal_transform_enu(321820.0821, 5811181.5082, 40.5797, 55, "MGA94", "MGA2020", return_type="enu")
        results3 = universal_transform.universal_transform_enu(321820.0821, 5811181.5082, 40.5797, 55, "MGA2020", "ITRF2008", to_epoch=date(2008,1,1), return_type="xyz")
        
        expected1 = [55, 321820.5725, 5811182.98, 40.4909]
        expected3 = [-4130636.286, 2894953.0932, -3890530.7837]

        self.assertEqual(results1["coords"]["zone"], expected1[0])
        self.assertAlmostEqual(results1["coords"]["east"], expected1[1],3)
        self.assertAlmostEqual(results1["coords"]["north"], expected1[2],3)
        self.assertAlmostEqual(results1["coords"]["el_height"], expected1[3],3)

        self.assertAlmostEqual(results3["coords"]["x"], expected3[0],3)
        self.assertAlmostEqual(results3["coords"]["y"], expected3[1],3)
        self.assertAlmostEqual(results3["coords"]["z"], expected3[2],3)

if __name__ == '__main__':
    unittest.main()