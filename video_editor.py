from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps


@dataclass(frozen=True)
class VideoInfo:
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool


@dataclass(frozen=True)
class RenderSettings:
    start: float = 0.0
    end: float | None = None
    width: int = 1920
    height: int = 1080
    fps: int = 30
    intro_duration: float = 8.0
    outro_duration: float = 4.0
    transition: float = 0.6
    music_volume: float = 0.08
    crf: int = 20
    preset: str = "medium"
    denoise: bool = True
    normalize_audio: bool = True
    enhance: bool = False
    fit_mode: str = "contain"
    background_color: str = "0x07131f"


ProgressCallback = Callable[[float, str], None]


def find_ffmpeg() -> str:
    configured = os.environ.get("FFMPEG_BINARY")
    if configured and Path(configured).exists():
        return configured
    binary = shutil.which("ffmpeg")
    if binary:
        return binary
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError(
            "FFmpeg was not found. Install dependencies with: pip install -r requirements.txt"
        ) from exc


def _run_capture(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    return completed.stdout


def probe_video(path: Path) -> VideoInfo:
    output = _run_capture([find_ffmpeg(), "-hide_banner", "-i", str(path)])
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
    video_match = re.search(
        r"Video:.*?,\s*(?:[^,]+,\s*)?(\d{2,5})x(\d{2,5})(?:[^\n]*?)(\d+(?:\.\d+)?)\s*fps",
        output,
    )
    if not duration_match or not video_match:
        raise ValueError("Could not read this video's duration or dimensions.")
    hours, minutes, seconds = duration_match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return VideoInfo(
        duration=duration,
        width=int(video_match.group(1)),
        height=int(video_match.group(2)),
        fps=float(video_match.group(3)),
        has_audio="Audio:" in output,
    )


def format_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def extract_frame(video: Path, output: Path, at_seconds: float) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        find_ffmpeg(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        str(max(0.0, at_seconds)),
        "-i",
        str(video),
        "-frames:v",
        "1",
        "-update",
        "1",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Could not extract a video frame.")
    return output


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / ("arialbd.ttf" if bold else "arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def create_thumbnail(
    background: Path,
    output: Path,
    title: str,
    subtitle: str,
    author: str,
) -> Path:
    with Image.open(background) as source:
        image = ImageOps.fit(source.convert("RGB"), (1280, 720), method=Image.Resampling.LANCZOS)
    image = ImageEnhance.Contrast(image).enhance(1.06)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for x in range(700):
        alpha = int(205 * (1 - x / 700))
        draw.line((x, 0, x, 720), fill=(7, 18, 31, alpha))
    draw.rectangle((0, 0, 18, 720), fill=(244, 166, 35, 255))
    image = Image.alpha_composite(image.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(image)
    title_font = _font(70, bold=True)
    subtitle_font = _font(38, bold=True)
    author_font = _font(27, bold=False)
    wrapped = textwrap.wrap(title.strip() or "YOUR VIDEO TITLE", width=20)[:4]
    y = 120
    for line in wrapped:
        draw.text((68, y), line, font=title_font, fill="white", stroke_width=2, stroke_fill=(0, 0, 0, 120))
        y += 82
    if subtitle.strip():
        draw.rounded_rectangle((64, y + 12, 650, y + 72), radius=10, fill=(244, 166, 35, 235))
        draw.text((84, y + 21), subtitle.strip()[:32], font=subtitle_font, fill=(10, 31, 52))
    draw.text((68, 655), f"By {author.strip() or 'Creator'}", font=author_font, fill=(230, 237, 242))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output, "JPEG", quality=94, optimize=True)
    return output


def create_vertical_cover(
    background: Path,
    output: Path,
    title: str,
    subtitle: str,
    author: str,
) -> Path:
    """Create a 1080×1920 cover suitable for Facebook Reels and Stories."""
    with Image.open(background) as source:
        image = ImageOps.fit(source.convert("RGB"), (1080, 1920), method=Image.Resampling.LANCZOS)
    image = ImageEnhance.Contrast(image).enhance(1.05)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(1920):
        start = 650
        alpha = 0 if y < start else int(220 * min(1, (y - start) / 900))
        draw.line((0, y, 1080, y), fill=(4, 15, 26, alpha))
    draw.rounded_rectangle((68, 92, 370, 150), radius=22, fill=(244, 166, 35, 245))
    image = Image.alpha_composite(image.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(image)
    draw.text((104, 105), "ENERGY HUB", font=_font(27, bold=True), fill=(8, 29, 46))
    title_font = _font(88, bold=True)
    subtitle_font = _font(42, bold=True)
    author_font = _font(32, bold=False)
    wrapped = textwrap.wrap(title.strip() or "YOUR VIDEO TITLE", width=18)[:5]
    y = 1120
    for line in wrapped:
        draw.text((72, y), line, font=title_font, fill="white", stroke_width=3, stroke_fill=(0, 0, 0, 150))
        y += 104
    if subtitle.strip():
        box_top = min(y + 20, 1740)
        draw.rounded_rectangle((70, box_top, 790, box_top + 72), radius=12, fill=(244, 166, 35, 240))
        draw.text((94, box_top + 13), subtitle.strip()[:38], font=subtitle_font, fill=(8, 29, 46))
        y = box_top + 92
    draw.text((74, min(y + 20, 1845)), f"By {author.strip() or 'Creator'}", font=author_font, fill=(225, 234, 241))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output, "JPEG", quality=94, optimize=True)
    return output


def _visual_filter(label: str, settings: RenderSettings, duration: float, fade_out: bool = True) -> str:
    if settings.fit_mode == "fill":
        chain = [
            f"scale={settings.width}:{settings.height}:force_original_aspect_ratio=increase",
            f"crop={settings.width}:{settings.height}",
        ]
    else:
        chain = [
            f"scale={settings.width}:{settings.height}:force_original_aspect_ratio=decrease",
            f"pad={settings.width}:{settings.height}:(ow-iw)/2:(oh-ih)/2:color={settings.background_color}",
        ]
    chain += [f"fps={settings.fps}", "setsar=1", "format=yuv420p"]
    if settings.denoise:
        chain.append("hqdn3d=1.2:1.2:4:4")
    if settings.enhance:
        chain.append("eq=contrast=1.03:saturation=1.04:brightness=0.005")
    if settings.transition > 0:
        chain.append(f"fade=t=in:st=0:d={settings.transition:.3f}")
        if fade_out and duration > settings.transition:
            chain.append(
                f"fade=t=out:st={max(0, duration - settings.transition):.3f}:d={settings.transition:.3f}"
            )
    return f"[{label}]" + ",".join(chain)


def build_render_command(
    raw_video: Path,
    output: Path,
    settings: RenderSettings,
    info: VideoInfo,
    cover: Path | None = None,
    music: Path | None = None,
    outro: Path | None = None,
    preview_seconds: float | None = None,
) -> tuple[list[str], float]:
    start = min(max(0.0, settings.start), max(0.0, info.duration - 0.1))
    end = settings.end if settings.end is not None else info.duration
    end = min(info.duration, max(start + 0.1, end))
    main_duration = end - start
    if preview_seconds:
        main_duration = min(main_duration, preview_seconds)

    command = [find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw_video)]
    input_index = 1
    cover_index = None
    music_index = None
    outro_index = None
    if cover and settings.intro_duration > 0:
        cover_index = input_index
        input_index += 1
        command += ["-loop", "1", "-t", str(settings.intro_duration), "-i", str(cover)]
    if music:
        music_index = input_index
        input_index += 1
        command += ["-stream_loop", "-1", "-i", str(music)]
    if outro and settings.outro_duration > 0:
        outro_index = input_index
        command += ["-loop", "1", "-t", str(settings.outro_duration), "-i", str(outro)]

    filters: list[str] = []
    filters.append(
        f"[0:v]trim=start={start:.3f}:duration={main_duration:.3f},setpts=PTS-STARTPTS[vtrim]"
    )
    filters.append(_visual_filter("vtrim", settings, main_duration) + "[vmain]")
    if info.has_audio:
        audio_chain = [
            f"[0:a]atrim=start={start:.3f}:duration={main_duration:.3f}",
            "asetpts=PTS-STARTPTS",
            "aresample=48000",
            "aformat=sample_fmts=fltp:channel_layouts=stereo",
            "highpass=f=70",
            "lowpass=f=15000",
        ]
        if settings.normalize_audio:
            audio_chain.append("loudnorm=I=-16:TP=-1.5:LRA=11")
        if settings.transition > 0:
            audio_chain.append(f"afade=t=in:st=0:d={settings.transition:.3f}")
            if main_duration > settings.transition:
                audio_chain.append(
                    f"afade=t=out:st={max(0, main_duration - settings.transition):.3f}:d={settings.transition:.3f}"
                )
        filters.append(",".join(audio_chain) + "[amain]")
    else:
        filters.append(
            f"anullsrc=channel_layout=stereo:sample_rate=48000,atrim=duration={main_duration:.3f},"
            "aformat=sample_fmts=fltp:channel_layouts=stereo[amain]"
        )

    video_segments: list[str] = []
    audio_segments: list[str] = []
    if cover_index is not None:
        filters.append(
            _visual_filter(f"{cover_index}:v", settings, settings.intro_duration) + "[vintro]"
        )
        filters.append(
            f"anullsrc=channel_layout=stereo:sample_rate=48000,atrim=duration={settings.intro_duration:.3f},"
            "aformat=sample_fmts=fltp:channel_layouts=stereo[aintro]"
        )
        video_segments.append("[vintro]")
        audio_segments.append("[aintro]")
    video_segments.append("[vmain]")
    audio_segments.append("[amain]")
    if outro_index is not None:
        filters.append(
            _visual_filter(f"{outro_index}:v", settings, settings.outro_duration) + "[voutro]"
        )
        filters.append(
            f"anullsrc=channel_layout=stereo:sample_rate=48000,atrim=duration={settings.outro_duration:.3f},"
            "aformat=sample_fmts=fltp:channel_layouts=stereo[aoutro]"
        )
        video_segments.append("[voutro]")
        audio_segments.append("[aoutro]")

    segment_pairs = "".join(v + a for v, a in zip(video_segments, audio_segments))
    filters.append(f"{segment_pairs}concat=n={len(video_segments)}:v=1:a=1[vbase][abase]")
    total_duration = main_duration
    if cover_index is not None:
        total_duration += settings.intro_duration
    if outro_index is not None:
        total_duration += settings.outro_duration

    audio_output = "[abase]"
    if music_index is not None and settings.music_volume > 0:
        filters.append(
            f"[{music_index}:a]atrim=duration={total_duration:.3f},asetpts=PTS-STARTPTS,"
            f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"volume={settings.music_volume:.3f},afade=t=in:st=0:d=1,"
            f"afade=t=out:st={max(0, total_duration - 2):.3f}:d=2[bgm]"
        )
        filters.append("[abase][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]")
        audio_output = "[aout]"

    output.parent.mkdir(parents=True, exist_ok=True)
    command += [
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[vbase]",
        "-map",
        audio_output,
        "-c:v",
        "libx264",
        "-preset",
        settings.preset,
        "-crf",
        str(settings.crf),
        "-profile:v",
        "high",
        "-level",
        "4.2",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        "-t",
        f"{total_duration:.3f}",
        "-shortest",
        "-progress",
        "pipe:1",
        "-nostats",
        str(output),
    ]
    return command, total_duration


def render_video(command: list[str], total_duration: float, callback: ProgressCallback | None = None) -> None:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    assert process.stdout is not None
    for line in process.stdout:
        line = line.strip()
        if line.startswith("out_time_ms="):
            try:
                current = int(line.split("=", 1)[1]) / 1_000_000
                ratio = min(0.99, current / max(total_duration, 0.1))
                if callback:
                    callback(ratio, f"Rendering {format_duration(current)} / {format_duration(total_duration)}")
            except ValueError:
                pass
    stderr = process.stderr.read() if process.stderr else ""
    code = process.wait()
    if code != 0:
        tail = "\n".join(stderr.strip().splitlines()[-18:])
        raise RuntimeError(tail or f"FFmpeg exited with code {code}.")
    if callback:
        callback(1.0, "Render complete")
