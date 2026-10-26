"""Google Drive sync. Three modes:
- 'oauth': real Google Drive via OAuth 2.0 InstalledApp flow.
- 'local': writes payloads to ./drive_staging/ (no network). For testing.
- 'off'  : no-op. Sync loop returns immediately.
"""

import json
import os
import time

from . import paths
from .models import Measurement, iter_all_measurements


def _mode():
    return os.environ.get("ERTERFACE_DRIVE_MODE", "oauth").strip().lower()


def _is_test_mode():
    return _mode() == "local"


def _is_off():
    return _mode() == "off"


class DriveClient:
    def __init__(self):
        self._service = None

    def _ensure_service(self):
        if self._is_off() or self._is_test_mode() or self._service is not None:
            return
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as e:
            raise RuntimeError(
                "google-api-python-client not installed. "
                "Run: pip install -r requirements.txt"
            ) from e

        creds = None
        if os.path.exists(paths.DRIVE_CREDENTIALS_FILE):
            creds = Credentials.from_authorized_user_file(
                paths.DRIVE_CREDENTIALS_FILE, paths.DRIVE_SCOPES
            )
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(paths.DRIVE_CLIENT_SECRET_FILE):
                    raise FileNotFoundError(
                        f"Missing {paths.DRIVE_CLIENT_SECRET_FILE}. "
                        "Place your OAuth Desktop client JSON there, then retry."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    paths.DRIVE_CLIENT_SECRET_FILE, paths.DRIVE_SCOPES
                )
                creds = flow.run_local_server(port=0)
            os.makedirs(os.path.dirname(paths.DRIVE_CREDENTIALS_FILE), exist_ok=True)
            with open(paths.DRIVE_CREDENTIALS_FILE, "w") as f:
                f.write(creds.to_json())

        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)

    def _folder_id(self):
        if os.path.exists(paths.DRIVE_CONFIG_FILE):
            with open(paths.DRIVE_CONFIG_FILE, "r") as f:
                return (json.load(f) or {}).get("folder_id")
        return None

    @staticmethod
    def _is_off():
        return _is_off()

    @staticmethod
    def _is_test_mode():
        return _is_test_mode()

    def upload_measurement(self, plantation, tree, measurement):
        """Upload one measurement. Returns True on success."""
        if self._is_off():
            return False
        if self._is_test_mode():
            return self._upload_local(plantation, tree, measurement)
        return self._upload_drive(plantation, tree, measurement)

    def _upload_local(self, p, t, m):
        prefix = f"{p.plant_id}/{t.tree_id}"
        out_dir = os.path.join(paths.DRIVE_STAGING_DIR, prefix)
        os.makedirs(out_dir, exist_ok=True)
        ts_str = m.timestamp.toString("yyyyMMdd_HHmmss")
        meta = {
            "imp_ratio": m.imp_ratio,
            "classification": m.classification,
            "timestamp": m.timestamp.toString("yyyy-MM-dd HH:mm:ss"),
        }
        with open(os.path.join(out_dir, f"measurement_{ts_str}.json"), "w") as f:
            json.dump(meta, f, indent=2)
        if m.data_path and os.path.exists(m.data_path):
            self._copy_local(m.data_path, os.path.join(out_dir, f"measurement_{ts_str}.npy"))
        if m.image_path and os.path.exists(m.image_path):
            self._copy_local(m.image_path, os.path.join(out_dir, f"measurement_{ts_str}.png"))
        return True

    @staticmethod
    def _copy_local(src, dst):
        with open(src, "rb") as fin, open(dst, "wb") as fout:
            fout.write(fin.read())

    def _upload_drive(self, p, t, m):
        try:
            from googleapiclient.http import MediaFileUpload
        except ImportError:
            return False
        self._ensure_service()
        if self._service is None:
            return False
        prefix = f"{p.plant_id}/{t.tree_id}"
        parent_id = self._folder_id() or "root"
        folder_id = self._ensure_folder(prefix, parent_id)
        ts_str = m.timestamp.toString("yyyyMMdd_HHmmss")
        meta = {
            "imp_ratio": m.imp_ratio,
            "classification": m.classification,
            "timestamp": m.timestamp.toString("yyyy-MM-dd HH:mm:ss"),
        }
        self._upload_string(
            json.dumps(meta, indent=2),
            os.path.join(prefix, f"measurement_{ts_str}.json"),
            folder_id,
            mime="application/json",
        )
        if m.data_path and os.path.exists(m.data_path):
            self._upload_file(m.data_path, os.path.join(prefix, f"measurement_{ts_str}.npy"), folder_id)
        if m.image_path and os.path.exists(m.image_path):
            self._upload_file(m.image_path, os.path.join(prefix, f"measurement_{ts_str}.png"), folder_id)
        return True

    def _ensure_folder(self, path, parent_id):
        parts = path.split("/")
        current = parent_id
        for part in parts:
            existing = self._find_child_folder(part, current)
            if existing:
                current = existing
            else:
                current = self._create_folder(part, current)
        return current

    def _find_child_folder(self, name, parent_id):
        q = (
            f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' "
            f"and '{parent_id}' in parents and trashed = false"
        )
        res = self._service.files().list(q=q, fields="files(id)").execute()
        files = res.get("files", [])
        return files[0]["id"] if files else None

    def _create_folder(self, name, parent_id):
        meta = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = self._service.files().create(body=meta, fields="id").execute()
        return folder["id"]

    def _upload_file(self, src_path, name, parent_id):
        from googleapiclient.http import MediaFileUpload
        meta = {"name": os.path.basename(name), "parents": [parent_id]}
        media = MediaFileUpload(src_path, resumable=True)
        self._service.files().create(body=meta, media_body=media, fields="id").execute()

    def _upload_string(self, content, name, parent_id, mime="text/plain"):
        from googleapiclient.http import MediaInMemoryUpload
        meta = {"name": os.path.basename(name), "parents": [parent_id]}
        media = MediaInMemoryUpload(content.encode("utf-8"), mimetype=mime)
        self._service.files().create(body=meta, media_body=media, fields="id").execute()


def sync_unsynced(database, client=None, progress_cb=None, cancel_check=None):
    """Walk the tree, find unsynced measurements, upload each.
    Returns (uploaded, failed, skipped) counts.
    """
    if _is_off():
        return 0, 0, 0
    if client is None:
        client = DriveClient()

    uploaded = 0
    failed = 0
    skipped = 0

    for p, t, m in iter_all_measurements(database):
        if cancel_check is not None and cancel_check():
            break
        if getattr(m, "synced", False):
            skipped += 1
            continue
        try:
            ok = client.upload_measurement(p, t, m)
            if ok:
                m.synced = True
                uploaded += 1
            else:
                failed += 1
        except Exception:
            failed += 1
        if progress_cb is not None:
            progress_cb(uploaded, failed, skipped)

    return uploaded, failed, skipped
