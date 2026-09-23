import math
import unittest
from types import SimpleNamespace

from fred_hri.control import Axis, closest_eyes


class ControlTests(unittest.TestCase):
    def test_limits_and_acceleration(self):
        axis = Axis(limit=0.4)
        previous = 0
        for _ in range(1000):
            axis.update(1, 0.02)
            self.assertLessEqual(abs(axis.angle), 0.4)
            self.assertLessEqual(abs(axis.velocity), axis.max_speed)
            if abs(axis.angle) < axis.limit:
                self.assertLessEqual(abs(axis.velocity - previous), axis.max_acceleration * .02 + 1e-9)
            previous = axis.velocity
        self.assertLess(abs(axis.integral), .5)
        axis.stop()
        self.assertEqual(axis.velocity, 0)
        self.assertEqual(axis.angle, .4)

    def test_closed_loop_converges(self):
        axis = Axis(limit=1.0)
        for _ in range(600):
            axis.update(0.3 - axis.angle, .02)
        self.assertLess(abs(.3 - axis.angle), .04)

    def test_largest_face_and_eye_normalization(self):
        def face(size, x):
            points = [SimpleNamespace(x=x, y=.25) for _ in range(478)]
            points[0] = SimpleNamespace(x=x-size, y=.25-size)
            points[1] = SimpleNamespace(x=x+size, y=.25+size)
            return points
        result = closest_eyes([face(.05, .1), face(.2, .75)])
        self.assertAlmostEqual(result[1], .5)
        self.assertAlmostEqual(result[2], -.5)
        self.assertIsNone(closest_eyes([]))
        broken = face(.1, .5); broken[0].x = math.nan
        self.assertIsNone(closest_eyes([broken]))


if __name__ == '__main__':
    unittest.main()
