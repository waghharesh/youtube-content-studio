import json
import os
from pathlib import Path
from typing import List, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
BASE_DIR = Path(__file__).parent
CLIENT_SECRETS_FILE = BASE_DIR / "client_secrets.json"
TOKEN_FILE = BASE_DIR / "token.json"


def _get_secret(key: str) -> Optional[str]:
    """Read a secret from environment variables or Streamlit st.secrets."""
    val = os.getenv(key, "").strip()
    if val:
        return val
    try:
        import streamlit as st

        if key in st.secrets:
            secret_val = st.secrets[key]
            if isinstance(secret_val, str):
                return secret_val.strip()
            return json.dumps(dict(secret_val))
    except Exception:
        pass
    return None


def get_authenticated_service(
    client_secrets_path: Path = CLIENT_SECRETS_FILE,
    token_path: Path = TOKEN_FILE,
):
    """
    Authenticate with Google OAuth2 using `token.json` / `client_secrets.json`
    (from disk, environment variables, or Streamlit Cloud `st.secrets`) and
    return a YouTube Data API v3 service client.
    """
    creds = None

    token_json_str = _get_secret("YOUTUBE_TOKEN_JSON")
    client_secrets_str = _get_secret("YOUTUBE_CLIENT_SECRETS_JSON")

    if token_json_str:
        token_info = json.loads(token_json_str)
        creds = Credentials.from_authorized_user_info(token_info, SCOPES)
    elif token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if client_secrets_str and not client_secrets_path.exists():
                try:
                    client_secrets_path.write_text(client_secrets_str, encoding="utf-8")
                except Exception:
                    pass
            if not client_secrets_path.exists():
                raise FileNotFoundError(
                    f"Missing OAuth2 client secrets file at {client_secrets_path}. "
                    "Add YOUTUBE_TOKEN_JSON and YOUTUBE_CLIENT_SECRETS_JSON in Streamlit Secrets "
                    "or place client_secrets.json and token.json in the project root."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secrets_path), SCOPES
            )
            creds = flow.run_local_server(port=0)

        try:
            token_path.write_text(creds.to_json(), encoding="utf-8")
        except Exception:
            pass

    return build("youtube", "v3", credentials=creds)


def upload_video_to_youtube(
    video_path: str,
    title: str,
    description: str,
    tags: List[str],
    category_id: str = "28",
    privacy_status: str = "public",
) -> str:
    """
    Perform a resumable upload to YouTube via `youtube.videos.insert` and return
    the uploaded YouTube video ID.
    """
    file_path = Path(video_path)
    if not file_path.exists():
        candidate = BASE_DIR / "output" / file_path.name
        if candidate.exists():
            file_path = candidate
        else:
            raise FileNotFoundError(f"Video file not found: {video_path}")

    youtube = get_authenticated_service()

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(file_path),
        mimetype="video/mp4",
        chunksize=1024 * 1024 * 4,
        resumable=True,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        _, response = request.next_chunk()

    return str(response["id"])
