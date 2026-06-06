"""
Configuration management for the submission bot.
"""
import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import json
from utils import safe_load_json, parse_role_ids, ensure_directory

# Load environment variables
load_dotenv()


class Config:
    """Centralized configuration management."""
    
    def __init__(self):
        self._load_env()
        self._load_submission_types()
    
    def _load_env(self):
        """Load configuration from environment variables."""
        # Discord
        self.discord_token = os.getenv("DISCORD_TOKEN", "")
        self.guild_id = int(os.getenv("GUILD_ID", "0")) if os.getenv("GUILD_ID") else None
        
        # Channels
        review_channel_id = os.getenv("REVIEW_CHANNEL_ID", "")
        self.review_channel_id = int(review_channel_id) if review_channel_id else None
        
        self.use_threads = os.getenv("USE_THREADS", "true").lower() == "true"
        
        notify_channel_id = os.getenv("NOTIFY_CHANNEL_ID", "")
        self.notify_channel_id = int(notify_channel_id) if notify_channel_id else None
        
        # Roles
        self.reviewer_role_ids = parse_role_ids(os.getenv("REVIEWER_ROLE_IDS", ""))
        self.admin_role_ids = parse_role_ids(os.getenv("ADMIN_ROLE_IDS", ""))
        
        # Rate limiting
        self.cooldown_seconds = int(os.getenv("COOLDOWN_SECONDS", "300"))
        self.max_submissions_per_day = int(os.getenv("MAX_SUBMISSIONS_PER_DAY", "10"))
        
        # Features
        self.allow_attachments = os.getenv("ALLOW_ATTACHMENTS", "true").lower() == "true"
        
        # Paths
        self.data_dir = os.getenv("DATA_DIR", "./data")
        self.log_dir = os.getenv("LOG_DIR", "./logs")
        
        # Ensure directories exist
        ensure_directory(self.data_dir)
        ensure_directory(self.log_dir)
    
    def _load_submission_types(self):
        """Load submission type definitions from JSON file."""
        config_path = "config/submission_types.json"
        self.submission_types = safe_load_json(config_path, {})
    
    def reload_submission_types(self):
        """Reload submission types from file."""
        self._load_submission_types()
        return len(self.submission_types)
    
    def get_submission_type(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a submission type definition by key."""
        return self.submission_types.get(key)
    
    def get_all_submission_types(self) -> Dict[str, Any]:
        """Get all submission type definitions."""
        return self.submission_types
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate that required configuration is present."""
        if not self.discord_token:
            return False, "DISCORD_TOKEN is required"
        
        if not self.guild_id:
            return False, "GUILD_ID is required"
        
        if not self.review_channel_id:
            return False, "REVIEW_CHANNEL_ID is required"
        
        if not self.reviewer_role_ids and not self.admin_role_ids:
            return False, "At least one of REVIEWER_ROLE_IDS or ADMIN_ROLE_IDS must be set"
        
        return True, None
    
    def get_allowlisted_role_ids(self) -> list[int]:
        """Get all allowlisted role IDs from submission type configs."""
        role_ids = set()
        for stype in self.submission_types.values():
            if stype.get("default_approval_role_id"):
                role_ids.add(stype["default_approval_role_id"])
        return list(role_ids)


