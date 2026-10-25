import tempfile
import unittest
from pathlib import Path

from video_editor import RenderSettings, VideoInfo, build_render_command, format_duration, plan_topic_segments


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

    def test_topic_plan_prefers_natural_pauses(self):
        pauses = [(620, 1.4), (760, 2.8), (910, 4.0), (1490, 2.2)]
        segments = plan_topic_segments(0, 1800, pauses, 10, 15, ["Overview", "Components"])
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].end, 760)
        self.assertEqual(segments[0].title, "Overview")
        self.assertEqual(segments[1].title, "Components")


if __name__ == "__main__":
    unittest.main()
