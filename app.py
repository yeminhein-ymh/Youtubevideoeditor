from __future__ import annotations

import hashlib
import time
from pathlib import Path

import streamlit as st

from video_editor import (
    RenderSettings,
    build_render_command,
    create_thumbnail,
    extract_frame,
    find_ffmpeg,
    format_duration,
    probe_video,
    render_video,
)


APP_ROOT = Path(__file__).resolve().parent
JOBS_ROOT = APP_ROOT / "renders"

st.set_page_config(page_title="Energy Hub Video Studio", page_icon="☀️", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(145deg, #07131f 0%, #0d2133 52%, #102a3f 100%); }
    [data-testid="stHeader"] { background: transparent; }
    .hero { padding: 1.4rem 1.6rem; border: 1px solid rgba(255,255,255,.10); border-radius: 20px;
            background: linear-gradient(110deg, rgba(244,166,35,.14), rgba(255,255,255,.035)); margin-bottom: 1rem; }
    .eyebrow { color:#f4a623; font-weight:700; letter-spacing:.13em; font-size:.78rem; }
    .hero h1 { color:#fff; margin:.25rem 0 .35rem; font-size:2.35rem; }
    .hero p { color:#b9c9d6; margin:0; max-width:780px; }
    .step { color:#ffb52e !important; font-size:.76rem; font-weight:800; letter-spacing:.11em; margin-bottom:.15rem; }
    /* High-contrast labels on the dark studio canvas. */
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] span,
    [data-testid="stFileUploader"] > label,
    [data-testid="stFileUploader"] > label p,
    [data-testid="stSlider"] > label,
    [data-testid="stSlider"] > label p,
    [data-testid="stTextInput"] > label,
    [data-testid="stTextInput"] > label p,
    [data-testid="stNumberInput"] > label,
    [data-testid="stNumberInput"] > label p,
    [data-testid="stSelectbox"] > label,
    [data-testid="stSelectbox"] > label p,
    [data-testid="stToggle"] label p {
        color:#eef6fb !important;
        opacity:1 !important;
        font-weight:600 !important;
    }
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
        color:#bed0dc !important;
    }
    [data-testid="stExpander"] {
        border-color:rgba(255,255,255,.16) !important;
        background:rgba(255,255,255,.035) !important;
    }
    [data-testid="stExpander"] details summary,
    [data-testid="stExpander"] details summary p,
    [data-testid="stExpander"] details summary span {
        color:#eef6fb !important;
        background:#142b3d !important;
        font-weight:700 !important;
    }
    /* Preserve dark text inside light form controls and upload panels. */
    [data-testid="stFileUploaderDropzone"] p,
    [data-testid="stFileUploaderDropzone"] span,
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input {
        color:#132638 !important;
    }
    div[data-testid="stMetric"] { background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08); padding:12px; border-radius:14px; }
    .stButton > button[kind="primary"] { background:#f4a623; color:#102235; border:0; font-weight:800; }
    .stDownloadButton > button { border-color:#f4a623; color:#f4a623; }
    </style>
    <div class="hero"><div class="eyebrow">ENERGY HUB · CREATOR WORKFLOW</div>
    <h1>Raw recording → YouTube-ready video</h1>
    <p>Add a polished cover, clean lecture audio, optional background music, smooth fades, an end card, and a 1280×720 thumbnail—without leaving this page.</p></div>
    """,
    unsafe_allow_html=True,
)


def save_upload(upload, folder: Path, role: str) -> Path | None:
    if upload is None:
        return None
    safe_name = Path(upload.name).name
    suffix = Path(safe_name).suffix.lower()
    digest = hashlib.sha1(f"{safe_name}:{upload.size}".encode()).hexdigest()[:10]
    path = folder / f"{role}_{digest}{suffix}"
    if not path.exists() or path.stat().st_size != upload.size:
        folder.mkdir(parents=True, exist_ok=True)
        upload.seek(0)
        with path.open("wb") as target:
            while chunk := upload.read(8 * 1024 * 1024):
                target.write(chunk)
        upload.seek(0)
    return path


with st.sidebar:
    st.markdown("### Output preset")
    preset_name = st.selectbox(
        "Preset",
        ["Reference style · 1080p", "Fast preview · 720p", "YouTube high quality · 1080p"],
        help="The reference preset follows the attached sample: 16:9, 30 fps, title card and clean lecture audio.",
    )
    if preset_name.startswith("Fast"):
        output_width, output_height, fps, crf, encoder_preset = 1280, 720, 24, 27, "veryfast"
    elif preset_name.startswith("YouTube"):
        output_width, output_height, fps, crf, encoder_preset = 1920, 1080, 30, 18, "slow"
    else:
        output_width, output_height, fps, crf, encoder_preset = 1920, 1080, 30, 20, "medium"
    st.caption(f"{output_width}×{output_height} · {fps} fps · H.264/AAC")
    st.markdown("---")
    st.markdown("**Reference analyzed**")
    st.caption("10:58 · 1920×1080 · 30 fps · 8 s cover · lecture layout · subscribe end card")

st.markdown('<div class="step">01 · SOURCE</div>', unsafe_allow_html=True)
source_col, reference_col = st.columns([1.45, 1])
with source_col:
    raw_upload = st.file_uploader(
        "Raw recording (required)",
        type=["mp4", "mov", "mkv", "m4v", "webm"],
        help="Large files are supported. For the supplied two-hour recording, rendering may take significant time.",
    )
with reference_col:
    reference_upload = st.file_uploader(
        "Sample/reference video (optional)",
        type=["mp4", "mov", "mkv", "m4v", "webm"],
        help="Kept as a visual reference; it is not inserted into the final video.",
    )

info = None
session_folder = JOBS_ROOT / st.session_state.setdefault("job_id", str(int(time.time())))
raw_path = None
if raw_upload:
    try:
        raw_path = save_upload(raw_upload, session_folder, "raw")
        info = probe_video(raw_path)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Duration", format_duration(info.duration))
        m2.metric("Source", f"{info.width}×{info.height}")
        m3.metric("Frame rate", f"{info.fps:g} fps")
        m4.metric("Audio", "Detected" if info.has_audio else "Silent")
    except Exception as exc:
        st.error(f"Could not inspect the raw video: {exc}")

if reference_upload:
    try:
        reference_path = save_upload(reference_upload, session_folder, "reference")
        reference_info = probe_video(reference_path)
        st.info(
            "Reference loaded · "
            f"{format_duration(reference_info.duration)} · "
            f"{reference_info.width}×{reference_info.height} · {reference_info.fps:g} fps. "
            "It is used for visual comparison and is not inserted into the output."
        )
    except Exception as exc:
        st.warning(f"The reference video could not be inspected: {exc}")

st.markdown('<div class="step">02 · BRANDING & AUDIO</div>', unsafe_allow_html=True)
a, b, c = st.columns(3)
with a:
    cover_upload = st.file_uploader("Opening cover photo", type=["jpg", "jpeg", "png", "webp"])
    intro_duration = st.slider("Cover duration (seconds)", 0.0, 15.0, 8.0, 0.5)
with b:
    music_upload = st.file_uploader("Background song", type=["mp3", "wav", "m4a", "aac", "ogg"])
    music_percent = st.slider("Song volume", 0, 30, 8, 1, help="Keep this low so speech stays clear.")
with c:
    outro_upload = st.file_uploader("End card / subscribe image", type=["jpg", "jpeg", "png", "webp"])
    outro_duration = st.slider("End card duration (seconds)", 0.0, 10.0, 4.0, 0.5)

with st.expander("Thumbnail designer", expanded=True):
    tc1, tc2, tc3 = st.columns([1.3, 1, 1])
    with tc1:
        title = st.text_input("Video title", "Solar PV Basic Training Course")
    with tc2:
        subtitle = st.text_input("Topic / episode", "DAY 1 · BATCH 19")
    with tc3:
        author = st.text_input("Presenter", "Ye Min")
    thumbnail_upload = st.file_uploader(
        "Custom thumbnail background (optional)", type=["jpg", "jpeg", "png", "webp"]
    )
    frame_time = st.number_input("Or capture raw video at (seconds)", min_value=0.0, value=10.0, step=1.0)

st.markdown('<div class="step">03 · EDIT</div>', unsafe_allow_html=True)
e1, e2, e3 = st.columns(3)
with e1:
    trim_start = st.number_input("Trim start (seconds)", min_value=0.0, value=0.0, step=1.0)
with e2:
    default_end = float(info.duration) if info else 0.0
    trim_end = st.number_input("Trim end (0 = video end)", min_value=0.0, value=0.0, step=1.0)
with e3:
    transition = st.slider("Fade duration", 0.0, 2.0, 0.6, 0.1)

o1, o2, o3 = st.columns(3)
with o1:
    normalize_audio = st.toggle("Normalize voice audio", value=True)
with o2:
    denoise = st.toggle("Light video denoise", value=True)
with o3:
    enhance = st.toggle("Gentle contrast & color", value=False)

with st.expander("What the smooth edit does"):
    st.markdown(
        "- Fits every source into a clean 16:9 canvas without stretching\n"
        "- Adds short visual and audio fades at section boundaries\n"
        "- Removes low rumble and harsh high-frequency noise\n"
        "- Targets YouTube-friendly voice loudness (−16 LUFS)\n"
        "- Mixes the optional song quietly beneath speech\n"
        "- Exports H.264 video, AAC stereo audio, and fast-start MP4"
    )

st.markdown('<div class="step">04 · CREATE</div>', unsafe_allow_html=True)
preview_only = st.toggle("Render a 30-second preview first", value=True)
render_clicked = st.button("Create YouTube-ready package", type="primary", use_container_width=True)

if render_clicked:
    if not raw_path or not info:
        st.error("Upload a valid raw recording first.")
        st.stop()
    try:
        find_ffmpeg()
        cover_path = save_upload(cover_upload, session_folder, "cover")
        music_path = save_upload(music_upload, session_folder, "music")
        outro_path = save_upload(outro_upload, session_folder, "outro")
        thumb_background = save_upload(thumbnail_upload, session_folder, "thumbnail_bg")
        if thumb_background is None:
            if cover_path:
                thumb_background = cover_path
            else:
                thumb_background = extract_frame(
                    raw_path, session_folder / "thumbnail_frame.jpg", min(frame_time, info.duration - 0.1)
                )
        thumbnail_path = create_thumbnail(
            thumb_background, session_folder / "youtube_thumbnail.jpg", title, subtitle, author
        )
        settings = RenderSettings(
            start=trim_start,
            end=trim_end if trim_end > 0 else None,
            width=output_width,
            height=output_height,
            fps=fps,
            intro_duration=intro_duration,
            outro_duration=outro_duration,
            transition=transition,
            music_volume=music_percent / 100,
            crf=crf,
            preset=encoder_preset,
            denoise=denoise,
            normalize_audio=normalize_audio,
            enhance=enhance,
        )
        filename = "youtube_preview.mp4" if preview_only else "youtube_ready.mp4"
        output_path = session_folder / filename
        command, total_duration = build_render_command(
            raw_path,
            output_path,
            settings,
            info,
            cover=cover_path,
            music=music_path,
            outro=outro_path,
            preview_seconds=30 if preview_only else None,
        )
        progress = st.progress(0.0, text="Starting FFmpeg…")

        def update(value: float, message: str) -> None:
            progress.progress(value, text=message)

        render_video(command, total_duration, update)
        st.session_state["latest_video"] = str(output_path)
        st.session_state["latest_thumbnail"] = str(thumbnail_path)
        st.success("Your YouTube package is ready.")
    except Exception as exc:
        st.error(f"Render failed: {exc}")

video_result = Path(st.session_state.get("latest_video", ""))
thumbnail_result = Path(st.session_state.get("latest_thumbnail", ""))
if video_result.is_file() and thumbnail_result.is_file():
    st.markdown("### Finished package")
    left, right = st.columns([1.5, 1])
    with left:
        st.video(str(video_result))
        st.caption(f"Saved to: {video_result}")
        if video_result.stat().st_size <= 500 * 1024 * 1024:
            with video_result.open("rb") as video_file:
                st.download_button(
                    "Download MP4", video_file, file_name=video_result.name, mime="video/mp4", use_container_width=True
                )
        else:
            st.info("The MP4 is over 500 MB. Use the saved file path above instead of loading it into the browser.")
    with right:
        st.image(str(thumbnail_result), caption="1280×720 YouTube thumbnail", use_container_width=True)
        with thumbnail_result.open("rb") as thumbnail_file:
            st.download_button(
                "Download thumbnail",
                thumbnail_file,
                file_name="youtube_thumbnail.jpg",
                mime="image/jpeg",
                use_container_width=True,
            )
