import unittest

from app.utils.time_utils import clamp_time, seconds_to_timestamp
from app.utils.validation_utils import UploadValidationError, validate_video_filename


class TimeUtilsTest(unittest.TestCase):
    def test_seconds_to_timestamp(self) -> None:
        self.assertEqual(seconds_to_timestamp(0), "00:00:00")
        self.assertEqual(seconds_to_timestamp(65), "00:01:05")
        self.assertEqual(seconds_to_timestamp(3661), "01:01:01")

    def test_clamp_time(self) -> None:
        self.assertEqual(clamp_time(-1, 0, 10), 0)
        self.assertEqual(clamp_time(11, 0, 10), 10)
        self.assertEqual(clamp_time(5, 0, 10), 5)


class UploadValidationTest(unittest.TestCase):
    def test_accepts_supported_video_extension(self) -> None:
        validate_video_filename("live.mp4")
        validate_video_filename("live.MOV")

    def test_rejects_unsupported_extension(self) -> None:
        with self.assertRaises(UploadValidationError):
            validate_video_filename("live.exe")


if __name__ == "__main__":
    unittest.main()

