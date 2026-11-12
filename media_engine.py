import asyncio
import os
import tempfile
from pathlib import Path
from typing import List, Tuple
import dotenv
import edge_tts
import requests

_orig_load_dotenv = dotenv.load_dotenv


def _safe_load_dotenv(*args, **kwargs):
    try:
        return _orig_load_dotenv(*args, **kwargs)
    except PermissionError:
        fallback = Path(__file__).parent / "config.env"
        if fallback.exists():
            return _orig_load_dotenv(dotenv_path=str(fallback))
        return False


dotenv.load_dotenv = _safe_load_dotenv
dotenv.main.load_dotenv = _safe_load_dotenv
_safe_load_dotenv()
if (Path(__file__).parent / "config.env").exists():
    _orig_load_dotenv(dotenv_path=str(Path(__file__).parent / "config.env"))

try:
    from moviepy.editor import (
        AudioFileClip,
        ColorClip,
        VideoFileClip,
        concatenate_videoclips,
    )
    MOVIEPY_V2 = False
except ImportError:
    from moviepy import (
        AudioFileClip,
        ColorClip,
        VideoFileClip,
        concatenate_videoclips,
    )
    MOVIEPY_V2 = True

VOICE_NAME = "en-US-ChristopherNeural"
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
OUTPUT_DIR = Path(__file__).parent / "output"
PEXELS_VIDEO_SEARCH_URL = "https://api.pexels.com/videos/search"
PIXABAY_VIDEO_SEARCH_URL = "https://pixabay.com/api/videos/"


async def _synthesize_voiceover_async(script: str, output_audio_path: Path) -> None:
    communicate = edge_tts.Communicate(text=script, voice=VOICE_NAME)
    await communicate.save(str(output_audio_path))


def generate_voiceover(script: str, output_audio_path: Path) -> Path:
    """Generate MP3 voiceover from script text using edge-tts (`en-US-ChristopherNeural`)."""
    output_audio_path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_synthesize_voiceover_async(script, output_audio_path))
    return output_audio_path


def fetch_pexels_videos(
    queries: List[str], download_dir: Path, clips_needed: int = 6
) -> List[Path]:
    """Fetch stock video clips from Pixabay or Pexels API for the given search queries."""
    pixabay_key = os.getenv("PIXABAY_API_KEY", "").strip()
    pexels_key = os.getenv("PEXELS_API_KEY", "").strip()

    # Detect Pixabay key format (e.g., "58574983-659fdee7e919db3ae27323f33")
    active_pixabay_key = pixabay_key or (
        pexels_key if "-" in pexels_key and pexels_key.split("-", 1)[0].isdigit() else ""
    )

    if active_pixabay_key:
        return _fetch_pixabay_videos(
            active_pixabay_key, queries, download_dir, clips_needed
        )

    if not pexels_key or pexels_key == "your_pexels_api_key_here":
        raise ValueError(
            "Neither PIXABAY_API_KEY nor PEXELS_API_KEY is configured in .env"
        )

    download_dir.mkdir(parents=True, exist_ok=True)
    headers = {"Authorization": pexels_key}
    downloaded_paths: List[Path] = []
    seen_video_ids = set()

    for query in queries:
        if len(downloaded_paths) >= clips_needed:
            break
        params = {
            "query": query,
            "orientation": "portrait",
            "size": "medium",
            "per_page": 4,
        }
        response = requests.get(
            PEXELS_VIDEO_SEARCH_URL, headers=headers, params=params, timeout=30
        )
        response.raise_for_status()
        data = response.json()

        for video in data.get("videos", []):
            vid_id = video.get("id")
            if vid_id in seen_video_ids:
                continue
            video_files = video.get("video_files", [])
            chosen_url = _select_best_video_file(video_files)
            if not chosen_url:
                continue

            dest_path = download_dir / f"pexels_{vid_id}.mp4"
            if not dest_path.exists():
                with requests.get(chosen_url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(dest_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

            seen_video_ids.add(vid_id)
            downloaded_paths.append(dest_path)
            if len(downloaded_paths) >= clips_needed:
                break

    return downloaded_paths


def _fetch_pixabay_videos(
    api_key: str, queries: List[str], download_dir: Path, clips_needed: int = 6
) -> List[Path]:
    """Fetch stock video clips from Pixabay Video API."""
    download_dir.mkdir(parents=True, exist_ok=True)
    downloaded_paths: List[Path] = []
    seen_video_ids = set()

    for query in queries:
        if len(downloaded_paths) >= clips_needed:
            break
        params = {
            "key": api_key,
            "q": query[:100],
            "per_page": 5,
            "safesearch": "true",
        }
        response = requests.get(PIXABAY_VIDEO_SEARCH_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        for hit in data.get("hits", []):
            vid_id = hit.get("id")
            if vid_id in seen_video_ids:
                continue
            videos_dict = hit.get("videos", {})
            chosen_url = (
                videos_dict.get("medium", {}).get("url")
                or videos_dict.get("small", {}).get("url")
                or videos_dict.get("large", {}).get("url")
            )
            if not chosen_url:
                continue

            dest_path = download_dir / f"pixabay_{vid_id}.mp4"
            if not dest_path.exists():
                with requests.get(chosen_url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(dest_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

            seen_video_ids.add(vid_id)
            downloaded_paths.append(dest_path)
            if len(downloaded_paths) >= clips_needed:
                break

    return downloaded_paths


def _select_best_video_file(video_files: List[dict]) -> str | None:
    mp4_files = [
        vf for vf in video_files if vf.get("file_type") == "video/mp4" and vf.get("link")
    ]
    if not mp4_files:
        return None
    # Prefer portrait files close to 1080x1920
    mp4_files.sort(
        key=lambda vf: (
            1 if (vf.get("height", 0) > vf.get("width", 0)) else 0,
            -abs(vf.get("height", 0) - TARGET_HEIGHT),
        ),
        reverse=True,
    )
    return mp4_files[0]["link"]


def _format_clip_vertical(clip, duration: float):
    """Resize and center-crop a clip to 1080x1920 and trim/loop to `duration`."""
    if MOVIEPY_V2:
        if clip.duration > duration:
            clip = clip.subclipped(0, duration)
        w, h = clip.size
        scale = max(TARGET_WIDTH / w, TARGET_HEIGHT / h)
        clip = clip.resized(scale)
        w_new, h_new = clip.size
        x1 = max(0, int((w_new - TARGET_WIDTH) / 2))
        y1 = max(0, int((h_new - TARGET_HEIGHT) / 2))
        clip = clip.cropped(
            x1=x1, y1=y1, x2=x1 + TARGET_WIDTH, y2=y1 + TARGET_HEIGHT
        )
        return clip.without_audio()
    else:
        if clip.duration > duration:
            clip = clip.subclip(0, duration)
        w, h = clip.size
        scale = max(TARGET_WIDTH / w, TARGET_HEIGHT / h)
        clip = clip.resize(scale)
        w_new, h_new = clip.size
        x1 = max(0, int((w_new - TARGET_WIDTH) / 2))
        y1 = max(0, int((h_new - TARGET_HEIGHT) / 2))
        clip = clip.crop(
            x1=x1, y1=y1, x2=x1 + TARGET_WIDTH, y2=y1 + TARGET_HEIGHT
        )
        return clip.without_audio()


def assemble_video(
    script: str,
    pexels_queries: List[str],
    output_filename: str,
    output_dir: Path = OUTPUT_DIR,
) -> Tuple[str, float]:
    """
    Generate voiceover, download Pexels b-roll clips, and assemble a 1080x1920 MP4
    matching the voiceover duration. Returns (video_path, duration_seconds).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_video_path = output_dir / output_filename

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        audio_path = tmp_path / "voiceover.mp3"
        generate_voiceover(script, audio_path)

        audio_clip = AudioFileClip(str(audio_path))
        total_duration = float(audio_clip.duration)

        raw_clip_paths = fetch_pexels_videos(
            pexels_queries, download_dir=tmp_path / "clips", clips_needed=max(4, len(pexels_queries))
        )

        loaded_clips = []
        processed_clips = []
        try:
            if not raw_clip_paths:
                fallback = ColorClip(
                    size=(TARGET_WIDTH, TARGET_HEIGHT),
                    color=(15, 20, 35),
                    duration=total_duration,
                )
                processed_clips.append(fallback)
            else:
                segment_duration = total_duration / len(raw_clip_paths)
                accumulated = 0.0
                idx = 0
                while accumulated < total_duration - 0.05:
                    clip_path = raw_clip_paths[idx % len(raw_clip_paths)]
                    raw_clip = VideoFileClip(str(clip_path))
                    loaded_clips.append(raw_clip)
                    needed = min(segment_duration, total_duration - accumulated)
                    clip_seg_dur = min(raw_clip.duration, needed)
                    if clip_seg_dur <= 0.1:
                        break
                    formatted = _format_clip_vertical(raw_clip, clip_seg_dur)
                    processed_clips.append(formatted)
                    accumulated += formatted.duration
                    idx += 1

            final_video = concatenate_videoclips(processed_clips, method="compose")
            if MOVIEPY_V2:
                final_video = final_video.with_audio(audio_clip)
            else:
                final_video = final_video.set_audio(audio_clip)

            final_video.write_videofile(
                str(output_video_path),
                fps=24,
                codec="libx264",
                audio_codec="aac",
                threads=2,
                logger=None,
            )
            final_video.close()
        finally:
            audio_clip.close()
            for c in processed_clips:
                try:
                    c.close()
                except Exception:
                    pass
            for c in loaded_clips:
                try:
                    c.close()
                except Exception:
                    pass

    return str(output_video_path.resolve()), round(total_duration, 2)
