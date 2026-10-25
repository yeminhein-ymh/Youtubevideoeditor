import tempfile
import unittest
from pathlib import Path

from video_editor import RenderSettings, VideoInfo, build_render_command, format_duration


class VideoEditorTests(unittest.TestCase):
    def test_format_duration(self):
        self.assertEqual(format_duration(8229.25), "02:17:09")

    def test_build_command_has_youtube_codecs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw = root / "raw.mp4"
            output = root / "out.mp4"
            info = VideoInfo(120, 1280, 720, 24, True)
            command, duration = build_render_command(raw, output, RenderSettings(), info)
            joined = " ".join(command)
            self.assertIn("libx264", command)
            self.assertIn("aac", command)
            self.assertIn("+faststart", command)
            self.assertIn("scale=1920:1080", joined)
            self.assertEqual(duration, 120)

    def test_vertical_fill_command(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            settings = RenderSettings(width=1080, height=1920, fit_mode="fill")
            command, _ = build_render_command(
                root / "raw.mp4",
                root / "facebook.mp4",
                settings,
                VideoInfo(30, 1920, 1080, 30, True),
            )
            joined = " ".join(command)
            self.assertIn("scale=1080:1920:force_original_aspect_ratio=increase", joined)
            self.assertIn("crop=1080:1920", joined)


if __name__ == "__main__":
    unittest.main()
