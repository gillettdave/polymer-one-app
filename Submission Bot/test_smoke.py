"""
Smoke test script for the Discord Submissions Bot.
Tests basic functionality without requiring Discord connection.
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import (
    generate_submission_id,
    safe_load_json,
    atomic_write_json,
    parse_role_ids,
    format_timestamp,
    validate_url,
    ensure_directory
)
from storage import Storage
from config import Config


def test_utils():
    """Test utility functions."""
    print("Testing utilities...")
    
    # Test submission ID generation
    sub_id = generate_submission_id()
    assert sub_id.startswith("SUB-"), "Submission ID should start with SUB-"
    # Format: SUB-YYYYMMDD-XXXXXXXX (3 + 8 + 1 + 8 = 20 chars minimum)
    parts = sub_id.split("-")
    assert len(parts) == 3, "Submission ID should have format SUB-YYYYMMDD-XXXXXXXX"
    assert len(parts[1]) == 8, "Date segment should be 8 digits (YYYYMMDD)"
    assert len(parts[2]) == 8, "Suffix should be 8 characters (4 microsecond + 4 hex)"
    assert parts[2].isalnum(), "Suffix should be alphanumeric"
    print(f"  ✓ Submission ID generation: {sub_id}")
    
    # Test role ID parsing
    role_ids = parse_role_ids("123,456,789")
    assert role_ids == [123, 456, 789], "Role IDs should be parsed correctly"
    print("  ✓ Role ID parsing")
    
    # Test URL validation
    assert validate_url("https://example.com") == True
    assert validate_url("http://example.com") == True
    assert validate_url("not-a-url") == False
    print("  ✓ URL validation")
    
    # Test directory creation
    test_dir = "./test_temp_dir"
    ensure_directory(test_dir)
    assert os.path.exists(test_dir), "Directory should be created"
    os.rmdir(test_dir)
    print("  ✓ Directory creation")
    
    print("  ✓ All utility tests passed\n")


def test_storage():
    """Test storage functionality."""
    print("Testing storage...")
    
    # Use a test data directory
    test_data_dir = "./test_data"
    ensure_directory(test_data_dir)
    
    try:
        storage = Storage(test_data_dir)
        
        # Test submission save/load
        test_submission = {
            "submission_id": "SUB-TEST-0001",
            "user_id": 123456789,
            "title": "Test Submission",
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        
        storage.save_submission(test_submission)
        loaded = storage.get_submission("SUB-TEST-0001")
        assert loaded is not None, "Submission should be saved and loadable"
        assert loaded["title"] == "Test Submission", "Submission data should match"
        print("  ✓ Submission save/load")
        
        # Test user submissions
        user_subs = storage.get_user_submissions(123456789, limit=5)
        assert len(user_subs) > 0, "Should find user submissions"
        print("  ✓ User submission retrieval")
        
        # Test stats
        stats = storage.get_stats()
        assert "total_submissions" in stats, "Stats should include total_submissions"
        print("  ✓ Statistics generation")
        
    finally:
        # Cleanup
        import shutil
        if os.path.exists(test_data_dir):
            shutil.rmtree(test_data_dir)
    
    print("  ✓ All storage tests passed\n")


def test_config():
    """Test configuration loading."""
    print("Testing configuration...")
    
    # Test that config files exist
    assert os.path.exists("config/submission_types.json"), "submission_types.json should exist"
    print("  ✓ Config files exist")
    
    # Test JSON loading
    types = safe_load_json("config/submission_types.json", {})
    assert isinstance(types, dict), "Should load as dictionary"
    assert len(types) > 0, "Should have at least one submission type"
    print(f"  ✓ Loaded {len(types)} submission type(s)")
    
    # Test config schema exists
    assert os.path.exists("config/config.schema.json"), "config.schema.json should exist"
    print("  ✓ Config schema exists")
    
    print("  ✓ All configuration tests passed\n")


def test_file_structure():
    """Test that all required files exist."""
    print("Testing file structure...")
    
    required_files = [
        "bot.py",
        "config.py",
        "storage.py",
        "review.py",
        "ui_components.py",
        "permissions.py",
        "utils.py",
        "requirements.txt",
        "README.md",
        "INSTALL.md",
        "COMMANDS.md",
        "CONFIG.md",
        "TROUBLESHOOTING.md",
        "SECURITY.md",
        "LICENSE.md",
        "RELEASE_CHECKLIST.md"
    ]
    
    required_dirs = [
        "config"
    ]
    
    for file in required_files:
        assert os.path.exists(file), f"Required file missing: {file}"
        print(f"  ✓ {file}")
    
    for dir in required_dirs:
        assert os.path.isdir(dir), f"Required directory missing: {dir}"
        print(f"  ✓ {dir}/")
    
    print("  ✓ All required files present\n")


def test_json_syntax():
    """Test that JSON files are valid."""
    print("Testing JSON syntax...")
    
    json_files = [
        "config/submission_types.json",
        "config/config.schema.json"
    ]
    
    for json_file in json_files:
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    json.load(f)
                print(f"  ✓ {json_file} is valid JSON")
            except json.JSONDecodeError as e:
                print(f"  ✗ {json_file} has JSON syntax error: {e}")
                raise
    
    print("  ✓ All JSON files are valid\n")


def main():
    """Run all smoke tests."""
    print("=" * 60)
    print("Discord Submissions Bot - Smoke Tests")
    print("=" * 60)
    print()
    
    try:
        test_file_structure()
        test_json_syntax()
        test_utils()
        test_config()
        test_storage()
        
        print("=" * 60)
        print("✓ All smoke tests passed!")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

