"""
Utility functions for the submission bot.
"""
import os
import json
import threading
import secrets
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path


class FileLock:
    """Simple file-based lock for thread-safe file operations."""
    
    def __init__(self, lock_file: str):
        self.lock_file = lock_file
        self.lock = threading.Lock()
    
    def __enter__(self):
        self.lock.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lock.release()


def generate_submission_id() -> str:
    """Generate a collision-resistant submission ID in format SUB-YYYYMMDD-XXXXXXXX."""
    now = datetime.utcnow()
    date_str = now.strftime("%Y%m%d")
    # Use microseconds (last 4 digits) + random hex (4 chars) for collision resistance
    microsecond_suffix = str(now.microsecond)[-4:].zfill(4)
    random_suffix = secrets.token_hex(2).upper()  # 4 hex characters
    return f"SUB-{date_str}-{microsecond_suffix}{random_suffix}"


def ensure_directory(path: str) -> None:
    """Ensure a directory exists, creating it if necessary."""
    Path(path).mkdir(parents=True, exist_ok=True)


def atomic_write_json(file_path: str, data: Any) -> None:
    """
    Atomically write JSON data to a file.
    Writes to a temp file first, then replaces the original.
    """
    temp_path = f"{file_path}.tmp"
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # On Windows, we need to remove the old file first
    if os.path.exists(file_path):
        os.remove(file_path)
    
    os.rename(temp_path, file_path)


def safe_load_json(file_path: str, default: Any = None) -> Any:
    """Safely load JSON from a file, returning default if file doesn't exist."""
    if default is None:
        default = {}
    
    if not os.path.exists(file_path):
        return default
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def parse_role_ids(role_ids_str: Optional[str]) -> list[int]:
    """Parse comma-separated role IDs string into a list of integers."""
    if not role_ids_str:
        return []
    
    try:
        return [int(rid.strip()) for rid in role_ids_str.split(',') if rid.strip()]
    except ValueError:
        return []


def format_timestamp(dt: Optional[datetime] = None) -> str:
    """Format a datetime as a readable string."""
    if dt is None:
        dt = datetime.utcnow()
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def truncate_string(s: str, max_length: int = 1000) -> str:
    """Truncate a string to max_length, adding ellipsis if truncated."""
    if len(s) <= max_length:
        return s
    return s[:max_length - 3] + "..."


def validate_url(url: str) -> bool:
    """Basic URL validation."""
    return url.startswith(('http://', 'https://'))


def get_attachment_info(attachment) -> Optional[Dict[str, str]]:
    """Extract attachment metadata from a Discord attachment object."""
    if not attachment:
        return None
    
    return {
        "url": attachment.url,
        "filename": attachment.filename,
        "content_type": attachment.content_type or "unknown",
        "size": attachment.size
    }

