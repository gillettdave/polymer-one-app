"""
File-based storage for submissions and decisions.
"""
import os
import json
import csv
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
from utils import atomic_write_json, safe_load_json, FileLock, ensure_directory


class Storage:
    """Manages file-based storage for submissions and decisions."""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        ensure_directory(data_dir)
        
        self.submissions_file = os.path.join(data_dir, "submissions.json")
        self.decisions_file = os.path.join(data_dir, "decisions.csv")
        
        self._submissions_lock = FileLock(os.path.join(data_dir, ".submissions.lock"))
        self._decisions_lock = FileLock(os.path.join(data_dir, ".decisions.lock"))
        
        # Initialize files if they don't exist
        self._init_files()
    
    def _init_files(self):
        """Initialize storage files if they don't exist."""
        if not os.path.exists(self.submissions_file):
            with self._submissions_lock:
                atomic_write_json(self.submissions_file, {})
        
        if not os.path.exists(self.decisions_file):
            with self._decisions_lock:
                with open(self.decisions_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "submission_id", "action", "reviewer_id", "reviewer_name",
                        "note", "timestamp"
                    ])
    
    def save_submission(self, submission: Dict[str, Any]) -> None:
        """Save a submission to storage."""
        with self._submissions_lock:
            submissions = safe_load_json(self.submissions_file, {})
            submissions[submission["submission_id"]] = submission
            atomic_write_json(self.submissions_file, submissions)
    
    def get_submission(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """Get a submission by ID."""
        submissions = safe_load_json(self.submissions_file, {})
        return submissions.get(submission_id)
    
    def get_user_submissions(
        self,
        user_id: int,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get recent submissions by a user, sorted by creation time."""
        submissions = safe_load_json(self.submissions_file, {})
        user_subs = [
            sub for sub in submissions.values()
            if sub.get("user_id") == user_id
        ]
        
        # Sort by created_at (newest first)
        user_subs.sort(
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )
        
        return user_subs[:limit]
    
    def get_pending_submissions(self) -> List[Dict[str, Any]]:
        """Get all pending submissions."""
        submissions = safe_load_json(self.submissions_file, {})
        return [
            sub for sub in submissions.values()
            if sub.get("status") == "pending"
        ]
    
    def update_submission_status(
        self,
        submission_id: str,
        status: str,
        review_message_id: Optional[int] = None,
        review_thread_id: Optional[int] = None
    ) -> bool:
        """Update a submission's status. Returns True if updated, False if not found."""
        with self._submissions_lock:
            submissions = safe_load_json(self.submissions_file, {})
            
            if submission_id not in submissions:
                return False
            
            submissions[submission_id]["status"] = status
            if review_message_id is not None:
                submissions[submission_id]["review_message_id"] = review_message_id
            if review_thread_id is not None:
                submissions[submission_id]["review_thread_id"] = review_thread_id
            
            atomic_write_json(self.submissions_file, submissions)
            return True
    
    def log_decision(
        self,
        submission_id: str,
        action: str,
        reviewer_id: int,
        reviewer_name: str,
        note: Optional[str] = None
    ) -> None:
        """Log a review decision to the CSV file."""
        with self._decisions_lock:
            with open(self.decisions_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    submission_id,
                    action,
                    reviewer_id,
                    reviewer_name,
                    note or "",
                    datetime.utcnow().isoformat()
                ])
    
    def get_user_submission_count_today(
        self,
        user_id: int,
        submission_type: Optional[str] = None
    ) -> int:
        """Count how many submissions a user has made today."""
        submissions = safe_load_json(self.submissions_file, {})
        today = datetime.utcnow().date().isoformat()
        
        count = 0
        for sub in submissions.values():
            if sub.get("user_id") != user_id:
                continue
            
            if submission_type and sub.get("submission_type_key") != submission_type:
                continue
            
            # Check if created today
            created_at = sub.get("created_at", "")
            if created_at.startswith(today):
                count += 1
        
        return count
    
    def get_last_submission_time(
        self,
        user_id: int,
        submission_type: str
    ) -> Optional[datetime]:
        """Get the timestamp of the user's last submission of this type."""
        submissions = safe_load_json(self.submissions_file, {})
        
        matching_subs = [
            sub for sub in submissions.values()
            if sub.get("user_id") == user_id
            and sub.get("submission_type_key") == submission_type
        ]
        
        if not matching_subs:
            return None
        
        # Sort by created_at and get the most recent
        matching_subs.sort(
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )
        
        try:
            created_at_str = matching_subs[0].get("created_at", "")
            # Parse ISO format datetime
            return datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get basic statistics about stored submissions."""
        submissions = safe_load_json(self.submissions_file, {})
        
        total = len(submissions)
        pending = sum(1 for s in submissions.values() if s.get("status") == "pending")
        approved = sum(1 for s in submissions.values() if s.get("status") == "approved")
        rejected = sum(1 for s in submissions.values() if s.get("status") == "rejected")
        changes_requested = sum(
            1 for s in submissions.values()
            if s.get("status") == "changes_requested"
        )
        
        return {
            "total_submissions": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "changes_requested": changes_requested,
            "submissions_file": self.submissions_file,
            "decisions_file": self.decisions_file
        }


