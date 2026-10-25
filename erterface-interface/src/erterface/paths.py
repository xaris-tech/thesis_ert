"""Filesystem paths for runtime data and config."""

import os
from pathlib import Path

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The thesis repo this app lives inside; the capture session is imported
# from here and records its runs under THESIS_ROOT / "scans".
THESIS_ROOT = Path(ROOT_DIR).parent

DATA_FILE = os.path.join(ROOT_DIR, "plantation_data.json")
DATA_DIRECTORY = os.path.join(ROOT_DIR, "data")
DRIVE_STAGING_DIR = os.path.join(ROOT_DIR, "drive_staging")
EXPORTS_DIR = os.path.join(ROOT_DIR, "exports")
FONTS_DIR = os.path.join(ROOT_DIR, "assets", "fonts")

USER_CONFIG_DIR = os.path.expanduser("~/.config/erterface")
DRIVE_CREDENTIALS_FILE = os.path.join(USER_CONFIG_DIR, "drive_credentials.json")
DRIVE_CLIENT_SECRET_FILE = os.path.join(USER_CONFIG_DIR, "drive_client_secret.json")
DRIVE_CONFIG_FILE = os.path.join(USER_CONFIG_DIR, "drive_config.json")

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]

CLASSIFICATION_HEALTHY = "HEALTHY"
CLASSIFICATION_AT_RISK = "AT_RISK"
CLASSIFICATION_UNHEALTHY = "UNHEALTHY"
# A run recorded by the capture session: images only, no health verdict.
CLASSIFICATION_UNCLASSIFIED = "UNCLASSIFIED"

ALL_CLASSIFICATIONS = (
    CLASSIFICATION_HEALTHY,
    CLASSIFICATION_AT_RISK,
    CLASSIFICATION_UNHEALTHY,
    CLASSIFICATION_UNCLASSIFIED,
)


def resolve_data_file(stored_path):
    """Find a measurement artifact whose stored path came from another
    machine (e.g. a Windows ``D:\\...`` path in plantation_data.json):
    use it if it exists, else look for the same file name in DATA_DIRECTORY.
    Returns "" when neither exists.
    """
    if not stored_path:
        return ""
    if os.path.exists(stored_path):
        return stored_path
    local = os.path.join(DATA_DIRECTORY, stored_path.replace("\\", "/").rsplit("/", 1)[-1])
    return local if os.path.exists(local) else ""


def ensure_directories():
    for d in (DATA_DIRECTORY, DRIVE_STAGING_DIR, EXPORTS_DIR, USER_CONFIG_DIR, FONTS_DIR):
        os.makedirs(d, exist_ok=True)
