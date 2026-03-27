"""
Загрузка скриншотов оплат на Google Drive.
Структура папок: ROOT / 2026 / Мар / файл.jpg
"""
import io
import json
import logging
import os

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from config import MONTH_SHEETS

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive",
]

DRIVE_ROOT_FOLDER_ID = os.getenv("DRIVE_RECEIPTS_FOLDER_ID", "")


def _get_drive_service():
    google_creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if google_creds_json:
        creds_dict = json.loads(google_creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _find_or_create_folder(service, name: str, parent_id: str) -> str:
    query = (
        f"name = '{name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents "
        f"and trashed = false"
    )
    results = service.files().list(
        q=query, spaces="drive", fields="files(id, name)",
        pageSize=1, supportsAllDrives=True
    ).execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    file_metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(
        body=file_metadata, fields="id", supportsAllDrives=True
    ).execute()
    logger.info(f"Created Drive folder: {name} ({folder['id']})")
    return folder["id"]


def _get_month_folder(service, year: int, month: int) -> str:
    root_id = DRIVE_ROOT_FOLDER_ID
    if not root_id:
        raise ValueError("DRIVE_RECEIPTS_FOLDER_ID не задан в env!")
    year_folder_id = _find_or_create_folder(service, str(year), root_id)
    month_name = MONTH_SHEETS.get(month, f"Месяц_{month}")
    month_folder_id = _find_or_create_folder(service, month_name, year_folder_id)
    return month_folder_id


async def upload_receipt(
    file_bytes: bytes,
    filename: str,
    year: int,
    month: int,
    mime_type: str = "image/jpeg",
) -> str:
    service = _get_drive_service()
    folder_id = _get_month_folder(service, year, month)

    file_metadata = {
        "name": filename,
        "parents": [folder_id],
    }
    media = MediaIoBaseUpload(
        io.BytesIO(file_bytes), mimetype=mime_type, resumable=False
    )
    uploaded = (
        service.files()
        .create(
            body=file_metadata, media_body=media,
            fields="id,webViewLink", supportsAllDrives=True
        )
        .execute()
    )

    service.permissions().create(
        fileId=uploaded["id"],
        body={"type": "anyone", "role": "reader"},
        supportsAllDrives=True
    ).execute()

    link = uploaded.get(
        "webViewLink",
        f"https://drive.google.com/file/d/{uploaded['id']}/view"
    )
    logger.info(f"Uploaded receipt: {filename} -> {link}")
    return link
