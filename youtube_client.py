from pathlib import Path
from typing import List
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
BASE_DIR = Path(__file__).parent
CLIENT_SECRETS_FILE = BASE_DIR / "client_secrets.json"
TOKEN_FILE = BASE_DIR / "token.json"


def get_authenticated_service(
    client_secrets_path: Path = CLIENT_SECRETS_FILE,
    token_path: Path = TOKEN_FILE,
):
    """
    Authenticate with Google OAuth2 using `client_secrets.json`, cache credentials
    in `token.json`, and return a YouTube Data API v3 service client.
    """
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not client_secrets_path.exists():
                raise FileNotFoundError(
                    f"Missing OAuth2 client secrets file at {client_secrets_path}. "
                    "Download client_secrets.json from Google Cloud Console and place it in the project root."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secrets_path), SCOPES
            )
            creds = flow.run_local_server(port=0)

        token_path.write_text(creds.to_json(), encoding="utf-8")

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
