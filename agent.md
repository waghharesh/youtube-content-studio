# Project: 100% Free Automated YouTube Content Studio

## Goal
Build a Python application that generates 1.5–2 minute vertical videos (1080x1920) on trending topics, places them in a SQLite database with status 'PENDING_REVIEW', allows peer review via a Streamlit dashboard, and uploads approved videos to YouTube via the YouTube Data API v3.

## Tech Stack (Zero-Cost / 100% Free)
- LLM / SEO & Script: Google Gemini 1.5 Flash (via `google-generativeai`)
- Voiceover (TTS): `edge-tts` (Microsoft Edge neural voice, `en-US-ChristopherNeural`, no API key needed)
- Stock Video: Pexels API (free tier)
- Video Assembly: `moviepy`
- Database: SQLite (`studio.db`)
- UI / Peer Review: Streamlit (`app.py`)
- Video Publisher: Google API Client (`youtube.videos.insert` via OAuth2 `client_secrets.json`)

## Architecture Files
- `database.py`: SQLite schema (id, topic, title, description, tags, script, video_path, duration, status, youtube_video_id).
- `seo_engine.py`: Calls Gemini 1.5 Flash in JSON mode to output titles, 3-tier tags (long-tail, mid-tier, broad), script (~230 words), and Pexels queries.
- `media_engine.py`: Generates voiceover via `edge-tts`, fetches b-roll clips from Pexels, and concatenates them with audio in MoviePy.
- `youtube_client.py`: Handles Google OAuth2, caches token in `token.json`, and performs resumable video upload.
- `worker.py`: Orchestrates the daily pipeline and inserts drafts as `PENDING_REVIEW`.
- `app.py`: Streamlit dashboard with tabs for Review Queue, Manual Generation, and Published Archive.
