from __future__ import annotations

import hashlib
import time
from pathlib import Path

import streamlit as st

from video_editor import (
    RenderSettings,
    build_render_command,
    create_vertical_cover,
    extract_frame,
    format_duration,
    probe_video,
    render_video,
)


ROOT = Path(__file__).resolve().parents[1]
JOBS = ROOT / "renders"

st.set_page_config(page_title="Facebook Reels Studio", page_icon="📱", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background:linear-gradient(145deg,#06131f 0%,#102b3f 100%); }
    [data-testid="stHeader"] { background:transparent; }
    .fbhero { padding:1.35rem 1.55rem; border-radius:20px; margin-bottom:1rem;
      border:1px solid rgba(255,255,255,.1); background:linear-gradient(115deg,rgba(24,119,242,.2),rgba(244,166,35,.08)); }
    .fbhero small { color:#55a1ff; font-weight:800; letter-spacing:.12em; }
    .fbhero h1 { margin:.25rem 0;color:white; } .fbhero p { color:#bdcbd7;margin:0; }
    .step { color:#79b8ff !important;font-size:.76rem;font-weight:800;letter-spacing:.11em;margin-top:.65rem; }
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
    [data-testid="stRadio"] > label,
    [data-testid="stRadio"] > label p,
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
    [data-testid="stFileUploaderDropzone"] p,
    [data-testid="stFileUploaderDropzone"] span,
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input {
        color:#132638 !important;
    }
    div[data-testid="stMetric"] { background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);padding:12px;border-radius:14px; }
    .stButton > button[kind="primary"] { background:#1877f2;color:white;border:0;font-weight:800; }
    </style>
    <div class="fbhero"><small>FACEBOOK · VERTICAL VIDEO</small><h1>Facebook Reels Studio</h1>
    <p>Turn a landscape or portrait recording into a polished 9:16 video with a vertical cover, clear speech, music, fades, and an optional end card.</p></div>
    """,
    unsafe_allow_html=True,
)


def save_upload(upload, folder: Path, role: str) -> Path | None:
    if upload is None:
        return None
    suffix = Path(upload.name).suffix.lower()
    digest = hashlib.sha1(f"{upload.name}:{upload.size}".encode()).hexdigest()[:10]
    path = folder / f"{role}_{digest}{suffix}"
    if not path.exists() or path.stat().st_size != upload.size:
        folder.mkdir(parents=True, exist_ok=True)
        upload.seek(0)
        with path.open("wb") as target:
            while chunk := upload.read(8 * 1024 * 1024):
                target.write(chunk)
        upload.seek(0)
    return path


job_folder = JOBS / st.session_state.setdefault("facebook_job_id", f"facebook_{int(time.time())}")

with st.sidebar:
    st.markdown("### Facebook output")
    st.metric("Canvas", "1080 × 1920")
    st.caption("9:16 portrait · 30 fps · H.264 video · AAC stereo")
    quality = st.select_slider("Quality", ["Smaller file", "Balanced", "High quality"], value="Balanced")
    quality_map = {
        "Smaller file": (25, "veryfast"),
        "Balanced": (21, "medium"),
        "High quality": (18, "slow"),
    }
    crf, encoder_preset = quality_map[quality]
    st.info("Start with a short preview. Landscape screen recordings usually look best with **Keep full frame**.")

st.markdown('<div class="step">01 · RECORDING</div>', unsafe_allow_html=True)
raw_upload = st.file_uploader("Raw video", type=["mp4", "mov", "mkv", "m4v", "webm"])
raw_path = None
info = None
if raw_upload:
    try:
        raw_path = save_upload(raw_upload, job_folder, "raw")
        info = probe_video(raw_path)
        c1, c2, c3 = st.columns(3)
        c1.metric("Duration", format_duration(info.duration))
        c2.metric("Source", f"{info.width}×{info.height}")
        c3.metric("Orientation", "Landscape" if info.width > info.height else "Portrait")
    except Exception as exc:
        st.error(f"Could not inspect the recording: {exc}")

layout_label = st.radio(
    "How should the recording fit the vertical screen?",
    ["Keep full frame · branded background", "Fill screen · crop the sides"],
    horizontal=True,
    help="Keep full frame preserves slides and screen shares. Fill screen works well for centered talking-head videos.",
)
background_choice = st.selectbox(
    "Background color",
    ["Energy Hub navy", "Black", "Facebook blue", "Warm charcoal"],
    disabled=layout_label.startswith("Fill"),
)
colors = {
    "Energy Hub navy": "0x07131f",
    "Black": "black",
    "Facebook blue": "0x102a56",
    "Warm charcoal": "0x211f1c",
}

st.markdown('<div class="step">02 · VERTICAL COVER</div>', unsafe_allow_html=True)
cover_left, cover_right = st.columns([1.15, 1])
with cover_left:
    cover_background = st.file_uploader(
        "Cover background photo (optional)", type=["jpg", "jpeg", "png", "webp"]
    )
    title = st.text_input("Title", "Solar PV Basic Training")
    subtitle = st.text_input("Topic", "DAY 1 · BATCH 19")
    presenter = st.text_input("Presenter", "Ye Min")
with cover_right:
    capture_time = st.number_input("Use a raw-video frame at (seconds)", 0.0, value=10.0, step=1.0)
    intro_duration = st.slider("Opening cover duration", 0.0, 10.0, 3.0, 0.5)
    use_cover = st.toggle("Insert generated cover into video", value=True)

st.markdown('<div class="step">03 · SOUND & FINISH</div>', unsafe_allow_html=True)
s1, s2, s3 = st.columns(3)
with s1:
    music_upload = st.file_uploader("Background song", type=["mp3", "wav", "m4a", "aac", "ogg"])
    music_volume = st.slider("Song volume", 0, 25, 7, 1)
with s2:
    outro_upload = st.file_uploader("End card", type=["jpg", "jpeg", "png", "webp"])
    outro_duration = st.slider("End card duration", 0.0, 8.0, 3.0, 0.5)
with s3:
    fade = st.slider("Smooth fade", 0.0, 1.5, 0.5, 0.1)
    normalize = st.toggle("Normalize voice", value=True)
    denoise = st.toggle("Light video denoise", value=True)

with st.expander("Trim and advanced controls"):
    t1, t2, t3 = st.columns(3)
    with t1:
        trim_start = st.number_input("Start at (seconds)", min_value=0.0, value=0.0, step=1.0)
    with t2:
        trim_end = st.number_input("End at (0 = video end)", min_value=0.0, value=0.0, step=1.0)
    with t3:
        enhance = st.toggle("Gentle color enhancement", value=True)

st.markdown('<div class="step">04 · CREATE</div>', unsafe_allow_html=True)
preview = st.toggle("Create a 20-second preview first", value=True)
clicked = st.button("Create Facebook-ready package", type="primary", use_container_width=True)

if clicked:
    if not raw_path or not info:
        st.error("Upload a valid raw recording first.")
        st.stop()
    try:
        supplied_background = save_upload(cover_background, job_folder, "cover_background")
        if supplied_background is None:
            supplied_background = extract_frame(
                raw_path, job_folder / "cover_frame.jpg", min(capture_time, info.duration - 0.1)
            )
        vertical_cover = create_vertical_cover(
            supplied_background,
            job_folder / "facebook_cover.jpg",
            title,
            subtitle,
            presenter,
        )
        music_path = save_upload(music_upload, job_folder, "music")
        outro_path = save_upload(outro_upload, job_folder, "outro")
        settings = RenderSettings(
            start=trim_start,
            end=trim_end if trim_end > 0 else None,
            width=1080,
            height=1920,
            fps=30,
            intro_duration=intro_duration if use_cover else 0,
            outro_duration=outro_duration,
            transition=fade,
            music_volume=music_volume / 100,
            crf=crf,
            preset=encoder_preset,
            denoise=denoise,
            normalize_audio=normalize,
            enhance=enhance,
            fit_mode="fill" if layout_label.startswith("Fill") else "contain",
            background_color=colors[background_choice],
        )
        output = job_folder / ("facebook_preview.mp4" if preview else "facebook_ready_9x16.mp4")
        command, duration = build_render_command(
            raw_path,
            output,
            settings,
            info,
            cover=vertical_cover if use_cover else None,
            music=music_path,
            outro=outro_path,
            preview_seconds=20 if preview else None,
        )
        bar = st.progress(0.0, text="Starting vertical render…")
        render_video(command, duration, lambda value, message: bar.progress(value, text=message))
        st.session_state["facebook_video"] = str(output)
        st.session_state["facebook_cover"] = str(vertical_cover)
        st.success("Your Facebook-ready package is complete.")
    except Exception as exc:
        st.error(f"Render failed: {exc}")

video_result = Path(st.session_state.get("facebook_video", ""))
cover_result = Path(st.session_state.get("facebook_cover", ""))
if video_result.is_file() and cover_result.is_file():
    st.markdown("### Finished Facebook package")
    result_left, result_right = st.columns([0.75, 1.25])
    with result_left:
        st.video(str(video_result))
    with result_right:
        st.image(str(cover_result), caption="1080×1920 Facebook cover", width=300)
        st.caption(f"Video saved to: {video_result}")
        if video_result.stat().st_size <= 500 * 1024 * 1024:
            with video_result.open("rb") as handle:
                st.download_button(
                    "Download 9:16 MP4", handle, video_result.name, "video/mp4", use_container_width=True
                )
        else:
            st.info("The video is over 500 MB. Use the saved path instead of loading it into browser memory.")
        with cover_result.open("rb") as handle:
            st.download_button(
                "Download Facebook cover", handle, "facebook_cover.jpg", "image/jpeg", use_container_width=True
            )
