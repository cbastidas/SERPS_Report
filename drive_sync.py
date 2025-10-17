# drive_sync.py
import os
import calendar
from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

UTC = timezone.utc

# ====== CONFIGURATION ======
REPORTS_ROOT_ID = "1IuUNGrI3yyVw67t5D9T418mDlG_A-6ch"     
SCREENSHOTS_ROOT_ID = "103gC0AL0chUzZjLY0YPo84ARGX-PuUhc"   
DRIVE_ROOT_FOLDER_ID = "1IuUNGrI3yyVw67t5D9T418mDlG_A-6ch"
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON_PATH", r"C:\Users\Christian\Desktop\Leap Square\Leap Square\Scripts\SERP ScreenShots\service_account.json")
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _service():
    """Creates a Google Drive client using the Service Account."""
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(
            f"Service Account JSON not found at: {SERVICE_ACCOUNT_FILE}\n"
            "Set the environment variable GOOGLE_APPLICATION_CREDENTIALS_JSON_PATH or place service_account.json in the working directory."
        )
    
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    # supportsAllDrives=True requires that the Service Account is a member of the folder or Shared Drive
    return build("drive", "v3", credentials=creds)


def _find_or_create_folder(service, name: str, parent_id: str) -> str:
    """
    Finds a folder by name under the given parent_id.
    If it does not exist, creates it.
    Returns the folder_id.
    """
    q = (
        f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents and trashed = false"
    )
    res = service.files().list(
        q=q,
        fields="files(id,name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(
        body=metadata,
        fields="id",
        supportsAllDrives=True
    ).execute()
    return folder["id"]


def _ensure_y_m_d_tree(service, root_id: str, now_dt=None) -> str:
    """
    Ensures the folder hierarchy exists:
    root / YYYY / MM-MonthName / DDMonthName
    Returns the folder_id for the current day.
    """
    now_dt = now_dt or datetime.now(UTC)
    year_name = now_dt.strftime("%Y")                 # 2025
    month_num = now_dt.strftime("%m")                 # 10
    month_name = calendar.month_name[int(month_num)]  # October
    month_folder = f"{month_num}-{month_name}"        # 10-October
    day_folder = now_dt.strftime("%d") + month_name   # 16October

    year_id  = _find_or_create_folder(service, year_name, root_id)
    month_id = _find_or_create_folder(service, month_folder, year_id)
    day_id   = _find_or_create_folder(service, day_folder, month_id)
    return day_id


# --- NEW 1: Upload directly to a specific folder (no date hierarchy)
def upload_file_to_folder(local_path: str, parent_folder_id: str):
    """
    Uploads local_path directly into the folder with ID parent_folder_id (no subfolders).
    Returns (file_id, webViewLink).
    """
    if not os.path.isfile(local_path):
        raise FileNotFoundError(f"Local file not found: {local_path}")
    if not parent_folder_id:
        raise RuntimeError("Missing parent_folder_id for upload_file_to_folder().")

    service = _service()
    media = MediaFileUpload(local_path, resumable=True)
    metadata = {"name": os.path.basename(local_path), "parents": [parent_folder_id]}
    file = service.files().create(
        body=metadata,
        media_body=media,
        fields="id, name, webViewLink",
        supportsAllDrives=True
    ).execute()
    return file["id"], file["webViewLink"]


# --- NEW 2: Upload with optional 'root_id' (uses date hierarchy)
def upload_file_preserving_tree(local_path: str, root_id: str | None = None):
    """
    Uploads local_path to (root_id or DRIVE_ROOT_FOLDER_ID) / YYYY / MM-Month / DDMonth.
    If 'root_id' is None, uses the default DRIVE_ROOT_FOLDER_ID.
    Returns (file_id, webViewLink).
    """
    target_root = root_id or DRIVE_ROOT_FOLDER_ID
    if not target_root:
        raise RuntimeError("Missing root_id or DRIVE_ROOT_FOLDER_ID.")
    if not os.path.isfile(local_path):
        raise FileNotFoundError(f"Local file not found: {local_path}")

    service = _service()
    parent_day_id = _ensure_y_m_d_tree(service, target_root)

    media = MediaFileUpload(local_path, resumable=True)
    metadata = {"name": os.path.basename(local_path), "parents": [parent_day_id]}
    file = service.files().create(
        body=metadata,
        media_body=media,
        fields="id, name, webViewLink",
        supportsAllDrives=True
    ).execute()
    return file["id"], file["webViewLink"]
