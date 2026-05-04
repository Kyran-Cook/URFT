import unittest
import sys
import os
from importlib.resources import files
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import point_in_polygon

eez_path = files("other_files") / "EEZ_australia_approx.dig"
EEZ_PLATE = point_in_polygon.build_plate_index(eez_path)

dig_path = files("other_files") / "MORVEL56_plates.dig"
PLATES = point_in_polygon.build_plate_index(dig_path)

class TestUniversalTransform(unittest.TestCase):
    
    def test_plate_from_ll_all(self):
        self.assertEqual(point_in_polygon.plate_from_ll(36.9, -102.5, PLATES), "NA")
        self.assertEqual(point_in_polygon.plate_from_ll(15.8, 13.9, PLATES), "AF")
        self.assertEqual(point_in_polygon.plate_from_ll(52.2, 68.5, PLATES), "EU")
        self.assertEqual(point_in_polygon.plate_from_ll(12.3, 94.0, PLATES), "BU")
        self.assertEqual(point_in_polygon.plate_from_ll(-3.23, 138.18, PLATES), "MO")
        self.assertEqual(point_in_polygon.plate_from_ll(88.3, 54.2, PLATES), "NA")
        self.assertEqual(point_in_polygon.plate_from_ll(-62.1, 56.5, PLATES), "AN")
        self.assertEqual(point_in_polygon.plate_from_ll(-19.8, 67.3, PLATES), "CP")
        self.assertEqual(point_in_polygon.plate_from_ll(-24.7, -114, PLATES), "EA")
        self.assertEqual(point_in_polygon.plate_from_ll(1.9, -101.5, PLATES), "GP")
    
    def test_plate_from_ll_eez(self):
        self.assertEqual(point_in_polygon.plate_from_ll(-27.31, 170.48, EEZ_PLATE), "MA")
        self.assertEqual(point_in_polygon.plate_from_ll(-59.28,159.71, EEZ_PLATE), "MQ")
        self.assertEqual(point_in_polygon.plate_from_ll(-12.09,107.35, EEZ_PLATE), "CH")
        self.assertEqual(point_in_polygon.plate_from_ll(-10.5,95.7, EEZ_PLATE), "CO")
        self.assertEqual(point_in_polygon.plate_from_ll(-43.66,170.63, EEZ_PLATE), None)
    
    def test_plate_from_xyz(self):
        self.assertEqual(point_in_polygon.plate_from_xyz(-4130636.762, 2894953.144, -3890530.253, PLATES), "AU")

    def test_universal_plate_motion_transformation(self):
        result = point_in_polygon.universal_plate_motion_transformation(-4130636.759,2894953.142,-3890530.249, date(2005,1,1), date(2020,1,1))

        expected = (-4130637.3480, 2894953.2048, -3890529.5769, None)

        for i in range(3):
            self.assertAlmostEqual(result[i], expected[i], places=3)

        self.assertIsNone(result[3])

    
if __name__ == '__main__':
    unittest.main()