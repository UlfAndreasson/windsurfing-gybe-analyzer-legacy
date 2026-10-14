import unittest
from app.fitlite import FitDecodeError, decode_activity


class FitLiteTests(unittest.TestCase):
    def test_rejects_non_fit(self):
        with self.assertRaises(FitDecodeError):
            decode_activity(b"not a fit file", "bad.fit")


if __name__ == "__main__":
    unittest.main()
