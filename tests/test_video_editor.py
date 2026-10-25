import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from video_editor import (
    RenderSettings,
    VideoInfo,
    build_render_command,
    format_duration,
    plan_topic_segments,
    probe_video,
)


class VideoEditorTests(unittest.TestCase):
    @patch("video_editor.find_ffmpeg", return_value="ffmpeg")
    @patch("video_editor._run_capture")
    def test_probe_video_returns_metadata(self, run_capture, _find_ffmpeg):
        run_capture.return_value = """
          Duration: 02:17:09.25, start: 0.000000, bitrate: 4200 kb/s
          Stream #0:0: Video: h264, yuv420p, 1920x1080, 29.97 fps
          Stream #0:1: Audio: aac, 48000 Hz, stereo
        """

        info = probe_video(Path("lecture.mp4"))

        self.assertEqual(info.duration, 8229.25)
        self.assertEqual((info.width, info.height), (1920, 1080))
        self.assertEqual(info.fps, 29.97)
        self.assertTrue(info.has_audio)

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
