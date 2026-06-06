import os
import math
import json
import datetime
import asyncio
import random
import logging
import logging.handlers
import traceback
import sys
import time
from typing import Optional, List, Dict, Any, Tuple, Callable, Union
from urllib.parse import urlparse
import csv
from collections import defaultdict, deque
from functools import wraps
from zoneinfo import ZoneInfo

import discord
from discord.ext import tasks, commands
from discord import app_commands
import aiohttp
from openai import OpenAI
from dotenv import load_dotenv

import gspread
from google.oauth2.service_account import Credentials

# Load environment variables
load_dotenv()

# -------------------------------
# Config
# -------------------------------

TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_DISCORD_BOT_TOKEN")

# Main metrics announcements channel (text channel)
CHANNEL_ID = int(os.getenv("METRICS_CHANNEL_ID", "123456789012345678"))

# Voice channel used as volume counter (0 to disable)
VOLUME_CHANNEL_ID = int(os.getenv("VOLUME_CHANNEL_ID", "0"))

LEADERBOARD_URL = os.getenv(
    "LEADERBOARD_URL",
    "https://analytics.polymer.zone/api/metrics/leaderboard/top-transactions?environment=mainnet",
)
ANALYTICS_URL = os.getenv(
    "ANALYTICS_URL",
    "https://analytics.polymer.zone/api/analytics?environment=mainnet",
)

STATE_FILE = "state.json"
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "600"))  # seconds
MAX_TX_AGE = datetime.timedelta(days=1)  # 24h freshness window

# Google Sheets config
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
GOOGLE_SPREADSHEET_NAME = os.getenv("GOOGLE_SPREADSHEET_NAME", "Polymer University Dashboard")

# XP sheets
XP_EVENTS_SHEET_NAME = os.getenv("XP_EVENTS_SHEET_NAME", "xp_events")
XP_TOTALS_SHEET_NAME = os.getenv("XP_TOTALS_SHEET_NAME", "xp_totals")

# Tweet sheets
TWEETS_SHEET_NAME = os.getenv("TWEETS_SHEET_NAME", "tweets")
OLD_TWEETS_SHEET_NAME = os.getenv("OLD_TWEETS_SHEET_NAME", "")  # Optional: old tweets sheet for migration

# Predictions sheet
PREDICTIONS_SHEET_NAME = os.getenv("PREDICTIONS_SHEET_NAME", "predictions")

# Local CSV for Discord <-> Twitter handle mapping
TWITTER_HANDLES_CSV = os.getenv("TWITTER_HANDLES_CSV", "twitter_handles.csv")

# API keys
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# OpenAI (for tweet grading)
openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Quiz config
QUIZ_DATA_FILE = os.getenv("QUIZ_DATA_FILE", "questions.csv")
QUIZ_RESULTS_FILE = os.getenv("QUIZ_RESULTS_FILE", "results.csv")
MAX_QUIZ_PARTICIPANTS = int(os.getenv("MAX_QUIZ_PARTICIPANTS", "50"))
QUIZ_COOLDOWN_SECONDS = int(os.getenv("QUIZ_COOLDOWN_SECONDS", "600"))
ADMIN_ROLE_NAME = os.getenv("ADMIN_ROLE_NAME", "manager perms")
METRICS_QUIZ_CSV = os.getenv("METRICS_QUIZ_CSV", "metrics_quiz_custom.csv")

# Daily XP caps (tiered system for catch-up mechanics)
# Format: (min_xp_threshold, daily_cap)
# Increments of 25 XP between tiers
XP_TIER_CAPS = [
    (0, 400),      # 0-499 XP: 400 XP/day (new users - catch up faster)
    (500, 375),    # 500-999 XP: 375 XP/day (400 - 25)
    (1000, 350),   # 1000-1999 XP: 350 XP/day (375 - 25)
    (2000, 325),   # 2000+ XP: 325 XP/day (350 - 25, top users - maintain lead but slower)
]
DEFAULT_DAILY_CAP = 325  # Fallback cap

# Grandfather bonus config (for existing contributors)
GRANDFATHER_BONUS_ENABLED = os.getenv("GRANDFATHER_BONUS_ENABLED", "true").lower() == "true"
GRANDFATHER_BONUS_PER_TWEET = 2  # Bonus XP per historical tweet (on top of old 5 XP)

# Prediction game config
PREDICTION_DEADLINE_HOURS = 1  # Predictions must be submitted at least 1 hour before resolution
PREDICTION_RESOLUTION_HOUR = 23  # Resolve predictions at 23:00 UTC (11 PM)
PREDICTION_MAX_VOLUME_PREDICTIONS_PER_DAY = 1  # Max volume predictions per user per day
PREDICTION_MAX_TOP10_PREDICTIONS_PER_DAY = 1  # Max top10 predictions per user per day
PREDICTION_VOLUME_XP_BASE = 50  # Base XP for volume predictions
PREDICTION_TOP10_XP_BASE = 75  # Base XP for top10 predictions

# Rate limiting for DMs
dm_timestamps = deque()
DM_RATE_LIMIT = 250 / 60  # ~4.16 DMs/sec
DM_WINDOW = 1  # 1 second window

# Rate limiting for user commands
user_command_timestamps: Dict[int, deque] = {}  # discord_id -> deque of timestamps
USER_COMMAND_COOLDOWN = 30  # seconds between tweet submissions per user
USER_COMMAND_WINDOW = 60  # window for tracking

# Google Sheets API rate limiting
# Google Sheets API: 60 requests per minute per user = 1 req/sec
sheets_api_queue = asyncio.Queue()
sheets_api_last_call = 0.0
SHEETS_API_MIN_INTERVAL = 1.1  # seconds between calls (slightly more than 1/sec for safety)
sheets_api_lock = asyncio.Lock()

# OpenAI API rate limiting
# OpenAI API: Rate limits vary by tier, but typically 500 requests/minute for gpt-4o-mini
# We'll be conservative: 8 requests per second max = ~480 requests/minute
openai_api_last_call = 0.0
OPENAI_API_MIN_INTERVAL = 0.125  # seconds between calls (8 req/sec = 480/min, well under 500/min limit)
openai_api_lock = asyncio.Lock()

# Twitter API rate limiting
# Twitter API v2 batch endpoint: 300 requests per 15 minutes, up to 100 tweets per request
# Single tweet endpoint: 300 requests per 15 minutes (1 tweet per request)
# We use batch fetching for efficiency (100 tweets per API call vs 1 tweet per call)
# Minimum interval: 6 seconds between calls (10 req/min = 150 per 15 min, well under 300 limit)
twitter_api_last_call = 0.0
TWITTER_API_MIN_INTERVAL = 6.0  # seconds between calls (10 req/min = 150 per 15 min, well under 300 limit)
twitter_api_lock = asyncio.Lock()
twitter_api_rate_limit_reset = None  # Timestamp when rate limit resets
twitter_api_remaining = None  # Remaining requests in current window

# Stop event for process_ungraded_tweets command
process_tweets_stop_event = asyncio.Event()

# Tweet submission queue for batch processing (Phase 2)
tweet_submission_queue: asyncio.Queue = asyncio.Queue()
tweet_queue_processor_running = False
TWEET_QUEUE_BATCH_SIZE = 100  # Max tweets per batch (Twitter API limit)
TWEET_QUEUE_PROCESS_INTERVAL = 30.0  # Process queue every 30 seconds
TWEET_QUEUE_MIN_BATCH_SIZE = 5  # Process if queue has at least this many items

# Exclusions cache
_exclusions_cache: Optional[List[str]] = None
_exclusions_cache_time: Optional[float] = None
EXCLUSIONS_CACHE_TTL = 300  # 5 minutes cache TTL

# Priority channel message count cache (persistent, daily refresh)
PRIORITY_CACHE_FILE = "priority_channel_cache.json"
PRIORITY_CACHE_TTL = 86400  # 24 hours (1 day)

# DeFiLlama chain metadata config
DEFI_LLAMA_API_KEY = os.getenv("DEFI_LLAMA_API_KEY", "")
DEFI_LLAMA_CHAINS_URL = "https://pro-api.llama.fi/api/v2/chains"
CHAIN_ICON_BASE_URL = os.getenv("CHAIN_ICON_BASE_URL", "https://icons.llama.fi")
CHAIN_CACHE: Dict[int, Dict[str, str]] = {}
CHAIN_CACHE_FILE = "chain_cache.json"

# Manual chain ID to name mapping (fallback when API is unavailable)
# Common Polymer-related chains and major chains
MANUAL_CHAIN_MAPPING: Dict[int, str] = {
    1: "Ethereum",
    10: "Optimism",
    56: "BSC",
    137: "Polygon",
    250: "Fantom",
    42161: "Arbitrum",
    43114: "Avalanche",
    8453: "Base",
    59144: "Linea",
    534352: "Scroll",
    # Polymer-related chains
    223: "B2",
    60808: "BOB",
    # Add more as needed
}

# Logging config
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_FILE_MAX_BYTES = int(os.getenv("LOG_FILE_MAX_BYTES", "10485760"))  # 10MB
LOG_FILE_BACKUP_COUNT = int(os.getenv("LOG_FILE_BACKUP_COUNT", "5"))

# Error notification config
ERROR_NOTIFICATION_ENABLED = os.getenv("ERROR_NOTIFICATION_ENABLED", "true").lower() == "true"
ADMIN_DM_USER_IDS = os.getenv("ADMIN_DM_USER_IDS", "").split(",")  # Comma-separated Discord user IDs
ADMIN_DM_USER_IDS = [int(uid.strip()) for uid in ADMIN_DM_USER_IDS if uid.strip()]

# -------------------------------
# Logging Setup
# -------------------------------

def setup_logging() -> logging.Logger:
    """Configure structured logging with file rotation.
    
    Sets up console and file handlers with rotation, configures log levels,
    and suppresses noisy third-party loggers.
    
    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger("PolyOne")
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Format for log messages
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    log_file = os.path.join(LOG_DIR, "polyone.log")
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=LOG_FILE_MAX_BYTES,
        backupCount=LOG_FILE_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Error log file (errors and above only)
    error_log_file = os.path.join(LOG_DIR, "polyone_errors.log")
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=LOG_FILE_MAX_BYTES,
        backupCount=LOG_FILE_BACKUP_COUNT,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("gspread").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    return logger

# Initialize logger (will be set after bot is created)
logger = None

# -------------------------------
# Error Notification System
# -------------------------------

_error_notification_queue = deque(maxlen=100)  # Keep last 100 errors
_error_notification_cooldown = {}  # Track last notification time per error type
ERROR_NOTIFICATION_COOLDOWN_SECONDS = 300  # 5 minutes between same error type

async def notify_admins_of_error(error_type: str, error_message: str, error_traceback: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
    """Send error notifications to admin users via DM."""
    if not ERROR_NOTIFICATION_ENABLED or not ADMIN_DM_USER_IDS:
        return
    
    # Check if bot is available
    try:
        bot_instance = bot
        if not bot_instance or not bot_instance.is_ready():
            if logger:
                logger.warning(f"Bot not ready, skipping error notification: {error_type}")
            return
    except (NameError, AttributeError):
        if logger:
            logger.warning(f"Bot not initialized, skipping error notification: {error_type}")
        return
    
    # Check cooldown
    now = datetime.datetime.now(datetime.timezone.utc)
    last_notification = _error_notification_cooldown.get(error_type)
    if last_notification:
        time_since = (now - last_notification).total_seconds()
        if time_since < ERROR_NOTIFICATION_COOLDOWN_SECONDS:
            return  # Still in cooldown
    
    _error_notification_cooldown[error_type] = now
    
    # Build error message
    error_lines = [
        f"🚨 **Critical Error Alert**",
        f"",
        f"**Error Type:** `{error_type}`",
        f"**Time:** {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"**Message:** {error_message}",
    ]
    
    if context:
        error_lines.append("")
        error_lines.append("**Context:**")
        for key, value in context.items():
            error_lines.append(f"- {key}: {value}")
    
    if error_traceback:
        # Truncate traceback if too long
        tb_lines = error_traceback.split('\n')
        if len(tb_lines) > 20:
            tb_lines = tb_lines[:20] + ["... (truncated)"]
        error_lines.append("")
        error_lines.append("**Traceback:**")
        error_lines.append("```")
        error_lines.extend(tb_lines)
        error_lines.append("```")
    
    error_content = "\n".join(error_lines)
    
    # Send to all admin users
    notified_count = 0
    for user_id in ADMIN_DM_USER_IDS:
        try:
            user = await bot_instance.fetch_user(user_id)
            if user:
                try:
                    dm_channel = await user.create_dm()
                    await dm_channel.send(error_content)
                    notified_count += 1
                    if logger:
                        logger.info(f"Sent error notification to admin {user_id}")
                except discord.Forbidden:
                    if logger:
                        logger.warning(f"Cannot send DM to admin {user_id} (DMs disabled)")
                except Exception as e:
                    if logger:
                        logger.error(f"Failed to send error notification to admin {user_id}: {e}")
        except discord.NotFound:
            if logger:
                logger.warning(f"Admin user {user_id} not found")
        except Exception as e:
            if logger:
                logger.error(f"Error fetching admin user {user_id}: {e}")
    
    if logger and notified_count > 0:
        logger.info(f"Error notification sent to {notified_count} admin(s)")
    
    # Store in queue for tracking
    _error_notification_queue.append({
        "timestamp": now.isoformat(),
        "error_type": error_type,
        "error_message": error_message,
    })


def log_error_with_notification(error_type: str, error: Exception, context: Optional[Dict[str, Any]] = None):
    """Log an error and notify admins if it's critical."""
    error_message = str(error)
    error_traceback = traceback.format_exc()
    
    if logger:
        logger.error(f"[{error_type}] {error_message}", exc_info=error)
        if error_traceback:
            logger.error(error_traceback)
    else:
        # Fallback if logger not initialized yet
        print(f"[ERROR] [{error_type}] {error_message}")
        if error_traceback:
            print(error_traceback)
    
    # Notify admins for critical errors
    if ERROR_NOTIFICATION_ENABLED:
        # Schedule notification (bot might not be ready yet)
        try:
            bot_instance = bot
            if bot_instance and bot_instance.is_ready():
                asyncio.create_task(notify_admins_of_error(error_type, error_message, error_traceback, context))
        except (NameError, AttributeError):
            pass  # Bot not initialized yet
        except Exception:
            pass  # Bot not ready yet


# -------------------------------
# Google Sheets client
# -------------------------------

_GSCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_GCREDS = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=_GSCOPE)
_GCLIENT = gspread.authorize(_GCREDS)
_GSHEET = _GCLIENT.open(GOOGLE_SPREADSHEET_NAME)


def get_ws(name: str) -> gspread.Worksheet:
    """Get a worksheet by name from the Google Spreadsheet.
    
    Args:
        name: Name of the worksheet to retrieve
        
    Returns:
        The requested worksheet
        
    Raises:
        gspread.WorksheetNotFound: If the worksheet doesn't exist
    """
    return _GSHEET.worksheet(name)


def get_tweets_ws() -> gspread.Worksheet:
    """Get the tweets worksheet.
    
    Returns:
        The tweets worksheet
        
    Raises:
        gspread.WorksheetNotFound: If the tweets worksheet doesn't exist
    """
    return get_ws(TWEETS_SHEET_NAME)

def get_old_tweets_ws() -> Optional[gspread.Worksheet]:
    """Get old tweets worksheet if configured.
    
    Returns:
        The old tweets worksheet if configured and exists, None otherwise
    """
    if not OLD_TWEETS_SHEET_NAME:
        return None
    try:
        return get_ws(OLD_TWEETS_SHEET_NAME)
    except Exception:
        return None


def _refresh_exclusions_cache() -> None:
    """Refresh the exclusions cache from the Google Sheet.
    
    Reads the Exclusions worksheet and caches the list of excluded Twitter handles.
    If the sheet doesn't exist or an error occurs, an empty list is cached.
    """
    global _exclusions_cache, _exclusions_cache_time
    
    try:
        exclusions_ws = get_ws("Exclusions")
        rows = exclusions_ws.get_all_values()
        
        if not rows:
            _exclusions_cache = []
            _exclusions_cache_time = time.time()
            return
        
        # Column A is index 0
        excluded_col = 0
        
        # Check if first row is a header (looks for "Excluded Members")
        header = rows[0] if rows else []
        has_header = header and len(header) > 0 and (
            header[0].strip().lower() == "excluded members" or
            header[0].strip().lower() == "excluded member"
        )
        
        # Extract all excluded handles
        excluded_handles = []
        start_row = 1 if has_header else 0
        for row in rows[start_row:]:
            if len(row) > excluded_col and row[excluded_col]:
                handle = row[excluded_col].lstrip("@").lower().strip()
                if handle:
                    excluded_handles.append(handle)
        
        _exclusions_cache = excluded_handles
        _exclusions_cache_time = time.time()
        
    except gspread.WorksheetNotFound:
        # Exclusions sheet doesn't exist - no exclusions
        _exclusions_cache = []
        _exclusions_cache_time = time.time()
    except Exception as e:
        # Log error but don't block submission if we can't check
        if logger:
            logger.warning(f"[Exclusions] Error refreshing exclusions cache: {e}")
        else:
            log_or_print("warning", f"[Exclusions] Error refreshing exclusions cache: {e}")
        # Keep old cache if refresh fails
        if _exclusions_cache is None:
            _exclusions_cache = []
            _exclusions_cache_time = time.time()


def is_handle_excluded(twitter_handle: str) -> bool:
    """Check if a Twitter handle is in the Exclusions sheet.
    
    Uses cached data to avoid reading the sheet on every check.
    Cache is refreshed every EXCLUSIONS_CACHE_TTL seconds.
    
    Args:
        twitter_handle: The Twitter handle to check (with or without @)
        
    Returns:
        True if the handle is excluded, False otherwise
    """
    if not twitter_handle:
        return False
    
    # Check if cache needs refresh
    now = time.time()
    if _exclusions_cache is None or _exclusions_cache_time is None:
        _refresh_exclusions_cache()
    elif (now - _exclusions_cache_time) > EXCLUSIONS_CACHE_TTL:
        _refresh_exclusions_cache()
    
    # Normalize the handle for comparison
    normalized_handle = twitter_handle.lstrip("@").lower().strip()
    
    # Check against cached list
    return normalized_handle in (_exclusions_cache or [])


def get_xp_events_ws() -> gspread.Worksheet:
    """Get the XP events worksheet.
    
    Returns:
        The XP events worksheet
        
    Raises:
        gspread.WorksheetNotFound: If the XP events worksheet doesn't exist
    """
    return get_ws(XP_EVENTS_SHEET_NAME)


def get_xp_totals_ws() -> gspread.Worksheet:
    """Get the XP totals worksheet.
    
    Returns:
        The XP totals worksheet
        
    Raises:
        gspread.WorksheetNotFound: If the XP totals worksheet doesn't exist
    """
    return get_ws(XP_TOTALS_SHEET_NAME)


async def ensure_xp_totals_sheet_size(min_rows: int = 10000) -> None:
    """Ensure the xp_totals sheet has enough rows for formulas to expand.
    
    Args:
        min_rows: Minimum number of rows the sheet should have (default: 10000)
    """
    try:
        ws = get_xp_totals_ws()
        current_rows = await asyncio.to_thread(lambda: ws.row_count)
        
        if current_rows < min_rows:
            rows_to_add = min_rows - current_rows
            log_or_print("info", f"[XPAdmin] Expanding xp_totals sheet: adding {rows_to_add} rows (current: {current_rows}, target: {min_rows})")
            
            await throttle_sheets_api()
            await retry_with_backoff(
                lambda: asyncio.to_thread(ws.add_rows, rows_to_add),
                max_retries=3,
                initial_delay=1.0,
            )
            log_or_print("info", f"[XPAdmin] Successfully expanded xp_totals sheet to {min_rows} rows")
    except Exception as e:
        log_or_print("warning", f"[XPAdmin] Error expanding xp_totals sheet: {e}")
        # Don't fail the whole operation if expansion fails - formulas might still work


async def get_members_with_messages(
    guild: discord.Guild, 
    max_messages_per_channel: int = 10000,
    progress_callback: Optional[Callable[[str], Any]] = None
) -> set[int]:
    """Get a set of member IDs who have posted at least one message in the server.
    
    This scans all text channels to build a cache of active members.
    Much more efficient than checking each member individually.
    
    Args:
        guild: The Discord guild/server
        max_messages_per_channel: Maximum messages to check per channel (default: 10000)
        progress_callback: Optional async callback function to report progress (takes message string)
    
    Returns:
        Set of member IDs who have posted at least once
    """
    active_member_ids = set()
    text_channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel)]
    
    if progress_callback:
        await progress_callback(f"🔍 Scanning {len(text_channels)} channels for active members...")
    else:
        log_or_print("info", f"[XPAdmin] Scanning {len(text_channels)} channels for active members...")
    
    for channel_idx, channel in enumerate(text_channels, 1):
        try:
            # Check if we can read message history
            if not channel.permissions_for(guild.me).read_message_history:
                continue
            
            # Scan messages in this channel
            message_count = 0
            async for message in channel.history(limit=max_messages_per_channel):
                if message.author and not message.author.bot:
                    active_member_ids.add(message.author.id)
                message_count += 1
            
            # Report progress every 10 channels or on last channel
            if (channel_idx % 10 == 0) or channel_idx == len(text_channels):
                progress_msg = f"Scanned {channel_idx}/{len(text_channels)} channels, found {len(active_member_ids)} active members..."
                if progress_callback:
                    await progress_callback(progress_msg)
                else:
                    log_or_print("info", f"[XPAdmin] {progress_msg}")
                
        except discord.Forbidden:
            if progress_callback:
                await progress_callback(f"⚠️ No permission to read {channel.name}")
            else:
                log_or_print("warning", f"[XPAdmin] No permission to read {channel.name}")
            continue
        except Exception as e:
            if progress_callback:
                await progress_callback(f"⚠️ Error scanning {channel.name}: {str(e)[:50]}")
            else:
                log_or_print("warning", f"[XPAdmin] Error scanning {channel.name}: {e}")
            continue
    
    final_msg = f"✅ Found {len(active_member_ids)} unique active members across all channels"
    if progress_callback:
        await progress_callback(final_msg)
    else:
        log_or_print("info", f"[XPAdmin] {final_msg}")
    
    return active_member_ids


def load_priority_cache() -> Tuple[Dict[int, Dict[int, int]], Optional[float]]:
    """Load priority channel cache from file.
    
    Returns:
        Tuple of (cache dict, timestamp) where cache is {channel_id: {user_id: count}}
    """
    if not os.path.exists(PRIORITY_CACHE_FILE):
        return {}, None
    
    try:
        with open(PRIORITY_CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            cache = {int(k): {int(uk): uv for uk, uv in v.items()} 
                    for k, v in data.get('cache', {}).items()}
            timestamp = data.get('timestamp')
            return cache, timestamp
    except Exception as e:
        log_or_print("error", f"[PriorityCache] Error loading cache: {e}")
        return {}, None


def save_priority_cache(cache: Dict[int, Dict[int, int]]) -> None:
    """Save priority channel cache to file."""
    try:
        data = {
            'cache': {str(k): {str(uk): uv for uk, uv in v.items()} 
                     for k, v in cache.items()},
            'timestamp': time.time()
        }
        with open(PRIORITY_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        log_or_print("info", f"[PriorityCache] Saved cache to {PRIORITY_CACHE_FILE}")
    except Exception as e:
        log_or_print("error", f"[PriorityCache] Error saving cache: {e}")


async def refresh_priority_channel_cache(guild: discord.Guild) -> Dict[int, Dict[int, int]]:
    """Fetch and cache message counts from priority and regional channels.
    
    Returns:
        Dictionary mapping channel_id -> {user_id: message_count}
    """
    PRIORITY_CHANNEL_IDS = [839904201244803102, 1270724937295859743]
    
    # Regional channels to cache
    REGIONAL_CHANNEL_IDS = [
        1199451508538871868,  # Arabic
        963526432259186718,   # Chinese
        1212449334894006312,  # Dutch
        1199389794149601384,  # French
        1201905842300133436,  # Hindi
        1199376946543476850,  # Indonesian
        1199109660087681044,  # Japanese
        1199374800813035671,  # Korean
        1199451660691439786,  # Persian
        1200511688378683603,  # Polish
        1199380046868131901,  # Portuguese
        1199742795800391782,  # Spanish
        1199375456567312474,  # Russian
        1200106047130570782,  # Thai
        1192726724933337138,  # Turkish
        1199429345735876810,  # Ukrainian
        1199375110184902766,  # Vietnamese
    ]
    
    # Combine all channels to cache
    ALL_CHANNEL_IDS = PRIORITY_CHANNEL_IDS + REGIONAL_CHANNEL_IDS
    
    excluded_channel_ids = get_excluded_channel_ids()
    
    cache = {}
    
    for channel_id in ALL_CHANNEL_IDS:
        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            continue
        
        if channel.id in excluded_channel_ids:
            continue
        
        if not channel.permissions_for(guild.me).read_message_history:
            continue
        
        # Count messages per user (only from last 270 days)
        user_counts: Dict[int, int] = {}
        try:
            lookback_days = 270
            cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=lookback_days)
            log_or_print("info", f"[PriorityCache] Fetching messages from channel {channel_id} (last {lookback_days} days, cutoff: {cutoff_date.date()})...")
            message_count = 0
            max_limit = 100000  # High limit to ensure we get all messages from the lookback period
            # Discord.py will handle pagination automatically. The limit caps the total fetched.
            # If a channel has more than 100k messages in the lookback period, we'll need to increase this.
            async for message in channel.history(limit=max_limit, after=cutoff_date):
                # Safety check: if message is older than cutoff, stop (shouldn't happen with after param, but safety)
                if message.created_at < cutoff_date:
                    break
                message_count += 1
                if message.author and not message.author.bot:
                    user_id = message.author.id
                    user_counts[user_id] = user_counts.get(user_id, 0) + 1
            
            # Warn if we're approaching the limit (might have missed messages)
            if message_count >= max_limit * 0.95:
                log_or_print("warning", f"[PriorityCache] Channel {channel_id} reached {message_count} messages (near limit {max_limit}). Some messages may have been missed!")
            
            log_or_print("info", f"[PriorityCache] Processed {message_count} messages from channel {channel_id}, found {len(user_counts)} unique users")
        except Exception as e:
            log_or_print("error", f"[PriorityCache] Error caching channel {channel_id}: {e}", exc_info=True)
            continue
        
        cache[channel_id] = user_counts
        log_or_print("info", f"[PriorityCache] Cached {len(user_counts)} users from channel {channel_id} (total messages counted: {sum(user_counts.values())})")
    
    # Save to file for persistence
    save_priority_cache(cache)
    log_or_print("info", f"[PriorityCache] Cache refresh complete. Total channels: {len(cache)}")
    return cache


async def get_cached_channel_message_count(guild: discord.Guild, user_id: int, channel_ids: List[int]) -> int:
    """Get message count from specified channels (uses persistent cache with daily refresh).
    
    Args:
        guild: Discord guild/server
        user_id: Discord user ID to get count for
        channel_ids: List of channel IDs to check
    
    Returns:
        Total message count from all specified channels for this user
    """
    # Load cache from file
    cache, timestamp = load_priority_cache()
    current_time = time.time()
    
    # Refresh if cache is stale (older than 24 hours) or missing
    if (not cache or timestamp is None or 
        current_time - timestamp > PRIORITY_CACHE_TTL):
        log_or_print("info", "[PriorityCache] Cache stale or missing, refreshing...")
        cache = await refresh_priority_channel_cache(guild)
    else:
        age_hours = (current_time - timestamp) / 3600
        log_or_print("debug", f"[PriorityCache] Using cached data (age: {age_hours:.1f} hours)")
    
    # Sum counts from all specified channels
    total_count = 0
    for channel_id in channel_ids:
        if channel_id in cache:
            channel_count = cache[channel_id].get(user_id, 0)
            total_count += channel_count
            if channel_count > 0:
                log_or_print("debug", f"[PriorityCache] User {user_id} has {channel_count} posts in channel {channel_id}")
        else:
            log_or_print("debug", f"[PriorityCache] Channel {channel_id} not found in cache")
    
    return total_count


async def get_priority_channel_message_count(guild: discord.Guild, user_id: int) -> int:
    """Get message count from priority channels (uses persistent cache with daily refresh).
    
    Args:
        guild: Discord guild/server
        user_id: Discord user ID to get count for
    
    Returns:
        Total message count from all priority channels for this user
    """
    PRIORITY_CHANNEL_IDS = [839904201244803102, 1270724937295859743]
    total_count = await get_cached_channel_message_count(guild, user_id, PRIORITY_CHANNEL_IDS)
    log_or_print("debug", f"[PriorityCache] User {user_id} total priority channel count: {total_count}")
    return total_count


async def count_discord_messages_for_user(
    guild: discord.Guild,
    user_id: int,
    max_messages_per_channel: int = 10000
) -> int:
    """Count the total number of messages posted by a user in the Discord server.
    
    Args:
        guild: The Discord guild/server
        user_id: The Discord user ID to count messages for
        max_messages_per_channel: Maximum messages to check per channel (default: 10000)
    
    Returns:
        Total count of messages posted by the user (excluding bot messages and excluded channels)
    """
    excluded_channel_ids = get_excluded_channel_ids()
    
    message_count = 0
    min_posts_required = get_min_discord_posts()
    channels_checked = 0
    
    # Priority channels to check first (most active channels)
    PRIORITY_CHANNEL_IDS = [839904201244803102, 1270724937295859743]
    
    # Regional role name to channel ID mapping
    REGIONAL_ROLE_TO_CHANNEL = {
        "Arabic": 1199451508538871868,
        "Chinese": 963526432259186718,
        "Dutch": 1212449334894006312,
        "French": 1199389794149601384,
        "Hindi": 1201905842300133436,
        "Indonesian": 1199376946543476850,
        "Japanese": 1199109660087681044,
        "Korean": 1199374800813035671,
        "Persian": 1199451660691439786,
        "Polish": 1200511688378683603,
        "Portuguese": 1199380046868131901,
        "Spanish": 1199742795800391782,
        "Russian": 1199375456567312474,
        "Thai": 1200106047130570782,
        "Turkish": 1192726724933337138,
        "Ukrainian": 1199429345735876810,
        "Vietnamese": 1199375110184902766,
    }
    
    # Get the member to check their roles
    member = None
    try:
        member = await guild.fetch_member(user_id)
    except discord.NotFound:
        log_or_print("debug", f"[DiscordMessageCount] User {user_id} not found in guild")
        return 0
    except Exception as e:
        log_or_print("debug", f"[DiscordMessageCount] Error fetching member {user_id}: {e}")
        return 0
    
    if not member:
        return 0
    
    # Get user's role names (case-insensitive comparison)
    user_role_names = {role.name.lower() for role in member.roles}
    
    # Find regional channels based on user's roles
    regional_channel_ids = []
    for role_name, channel_id in REGIONAL_ROLE_TO_CHANNEL.items():
        if role_name.lower() in user_role_names:
            regional_channel_ids.append(channel_id)
    
    # Check priority channels first (using persistent cache)
    try:
        priority_count = await get_priority_channel_message_count(guild, user_id)
        message_count += priority_count
        log_or_print("debug", f"[DiscordMessageCount] User {user_id} priority channel count: {priority_count}, total so far: {message_count}")
    except Exception as e:
        log_or_print("error", f"[DiscordMessageCount] Error getting priority channel count for user {user_id}: {e}", exc_info=True)
        # Continue without priority count - will check regional channels
    
    if message_count >= min_posts_required:
        log_or_print("debug", f"[DiscordMessageCount] User {user_id} has {message_count} posts (need {min_posts_required}+), stopping early after checking priority channels cache")
        return message_count
    
    # If user has no regional roles, only check priority channels (already done above)
    if not regional_channel_ids:
        log_or_print("debug", f"[DiscordMessageCount] User {user_id} has no regional roles, only checked priority channels. Found {message_count} posts")
        return message_count
    
    # Check regional channels based on user's roles (using cache)
    if regional_channel_ids:
        # Filter out priority channels (already checked) and excluded channels
        regional_channels_to_check = [
            cid for cid in regional_channel_ids 
            if cid not in PRIORITY_CHANNEL_IDS and cid not in excluded_channel_ids
        ]
        
        if regional_channels_to_check:
            try:
                regional_count = await get_cached_channel_message_count(guild, user_id, regional_channels_to_check)
                message_count += regional_count
                log_or_print("debug", f"[DiscordMessageCount] User {user_id} regional channel count: {regional_count}, total: {message_count}")
                
                if message_count >= min_posts_required:
                    log_or_print("debug", f"[DiscordMessageCount] User {user_id} has {message_count} posts (need {min_posts_required}+), stopping early after checking cached channels")
                    return message_count
            except Exception as e:
                log_or_print("error", f"[DiscordMessageCount] Error getting regional channel count from cache for user {user_id}: {e}", exc_info=True)
                # Fallback: check channels directly if cache fails
                for channel_id in regional_channels_to_check:
                    channel = guild.get_channel(channel_id)
                    if not channel or not isinstance(channel, discord.TextChannel):
                        continue
                    
                    try:
                        if not channel.permissions_for(guild.me).read_message_history:
                            continue
                        
                        channels_checked += 1
                        async for message in channel.history(limit=max_messages_per_channel):
                            if message.author and message.author.id == user_id and not message.author.bot:
                                message_count += 1
                                if message_count >= min_posts_required:
                                    log_or_print("debug", f"[DiscordMessageCount] User {user_id} has {message_count} posts (need {min_posts_required}+), stopping early after {channels_checked} channels")
                                    return message_count
                    except Exception as e2:
                        log_or_print("debug", f"[DiscordMessageCount] Error counting messages in regional channel {channel_id}: {e2}")
                        continue
    
    log_or_print("debug", f"[DiscordMessageCount] User {user_id} has {message_count} posts after checking {channels_checked} channels (priority + {len(regional_channel_ids)} regional)")
    return message_count


def get_predictions_ws() -> gspread.Worksheet:
    """Get or create the predictions worksheet.
    
    If the worksheet doesn't exist, it will be created with the required headers.
    
    Returns:
        The predictions worksheet
    """
    try:
        return get_ws(PREDICTIONS_SHEET_NAME)
    except gspread.WorksheetNotFound:
        # Create the worksheet with headers
        ws = _GSHEET.add_worksheet(
            title=PREDICTIONS_SHEET_NAME,
            rows=1000,
            cols=12
        )
        # Set headers
        headers = [
            "Timestamp",
            "Discord ID",
            "Discord Name",
            "Prediction Type",
            "Target Date",
            "Prediction Value",
            "Actual Value",
            "Resolved",
            "Accuracy",
            "XP Awarded",
            "Notes",
            "Resolution Timestamp"
        ]
        ws.append_row(headers)
        return ws


# -------------------------------
# XP helpers
# -------------------------------

def get_daily_cap_for_user(total_xp: int) -> int:
    """Get the daily XP cap for a user based on their total XP (tiered system)."""
    for min_xp, cap in sorted(XP_TIER_CAPS, reverse=True):
        if total_xp >= min_xp:
            return cap
    return DEFAULT_DAILY_CAP


def has_passed_quiz_today(discord_id: int | str, quiz_type: Optional[str] = None) -> bool:
    """Check if user has passed a quiz today (earned XP from quiz completion).
    
    Args:
        discord_id: User's Discord ID
        quiz_type: Type of quiz to check for:
            - "metrics": Check only for daily metrics quiz (reference_id="quiz_metrics")
            - "university": Check only for Polymer University quizzes (reference_id starts with "quiz_" but not "quiz_metrics")
            - None: Check for any quiz (backward compatibility)
    
    Users can attempt quizzes multiple times, but can only earn XP from the first
    passed quiz of each type each day. Day resets at 11:59pm UTC.
    """
    try:
        ws = get_xp_events_ws()
        rows = ws.get_all_values()
    except gspread.WorksheetNotFound:
        return False
    
    discord_id_str = str(discord_id)
    # Day resets at 11:59pm UTC, so we check if any quiz XP was earned today
    now = datetime.datetime.now(datetime.timezone.utc)
    today = now.date()
    
    if not rows:
        return False
    
    header = rows[0]
    timestamp_col = 0
    discord_id_col = 1
    source_col = 4
    amount_col = 5
    reference_id_col = 7
    
    # Find columns
    for idx, col_name in enumerate(header):
        col_lower = col_name.lower()
        if "timestamp" in col_lower or "date" in col_lower or "time" in col_lower:
            timestamp_col = idx
        elif "discord_id" in col_lower or "id" == col_lower:
            discord_id_col = idx
        elif "source" in col_lower:
            source_col = idx
        elif "amount" in col_lower or "xp" in col_lower:
            amount_col = idx
        elif "reference_id" in col_lower:
            reference_id_col = idx
    
    for row in rows[1:]:
        if len(row) <= max(discord_id_col, timestamp_col, source_col, amount_col):
            continue
        
        if row[discord_id_col] != discord_id_str:
            continue
        
        # Check if it's a quiz completion with positive XP (meaning they passed)
        if len(row) > source_col and row[source_col].lower() == "quiz_completion":
            # Check reference_id if quiz_type is specified
            if quiz_type is not None:
                ref_id = row[reference_id_col] if len(row) > reference_id_col else ""
                if quiz_type == "metrics":
                    # Only check for daily metrics quiz
                    if ref_id != "quiz_metrics":
                        continue
                elif quiz_type == "university":
                    # Only check for Polymer University quizzes (quiz_* but not quiz_metrics)
                    if not ref_id.startswith("quiz_") or ref_id == "quiz_metrics":
                        continue
            
            # Check if they earned XP (positive amount means they passed)
            try:
                amount = int(float(row[amount_col])) if len(row) > amount_col else 0
                if amount > 0:  # Only count if they earned XP (passed)
                    # Check if today (before 11:59pm UTC reset)
                    ts_str = row[timestamp_col]
                    if ts_str:
                        if "T" in ts_str:
                            ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        else:
                            ts = datetime.datetime.fromisoformat(ts_str)
                        
                        # Check if same day (day resets at 11:59pm UTC)
                        if ts.date() == today:
                            return True
            except (ValueError, IndexError, TypeError):
                continue
    
    return False


def get_daily_xp_earned(discord_id: int | str, source_filter: Optional[str] = None) -> int:
    """Get total XP earned today by a user, optionally filtered by source."""
    try:
        ws = get_xp_events_ws()
        rows = ws.get_all_values()
    except gspread.WorksheetNotFound:
        return 0
    
    discord_id_str = str(discord_id)
    today = datetime.datetime.now(datetime.timezone.utc).date()
    total = 0
    
    # Find timestamp column (usually first column)
    if not rows:
        return 0
    
    header = rows[0]
    timestamp_col = 0  # Default to first column
    discord_id_col = 1  # Default to second column
    source_col = 4  # Default to 5th column (after timestamp, discord_id, discord_name, twitter_handle)
    amount_col = 5  # Default to 6th column
    
    # Try to find columns by header
    for idx, col_name in enumerate(header):
        col_lower = col_name.lower()
        if "timestamp" in col_lower or "date" in col_lower or "time" in col_lower:
            timestamp_col = idx
        elif "discord_id" in col_lower or "id" == col_lower:
            discord_id_col = idx
        elif "source" in col_lower:
            source_col = idx
        elif "amount" in col_lower or "xp" in col_lower:
            amount_col = idx
    
    for row in rows[1:]:
        if len(row) <= max(discord_id_col, amount_col, timestamp_col, source_col):
            continue
        
        if row[discord_id_col] != discord_id_str:
            continue
        
        # Check source filter
        if source_filter and len(row) > source_col:
            if row[source_col].lower() != source_filter.lower():
                continue
        
        # Parse timestamp and check if today
        try:
            ts_str = row[timestamp_col]
            if ts_str:
                # Handle ISO format timestamps
                if "T" in ts_str:
                    ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                else:
                    ts = datetime.datetime.fromisoformat(ts_str)
                
                if ts.date() == today:
                    # Get amount (positive only - ignore negative admin removals for cap calculation)
                    amount = int(float(row[amount_col])) if len(row) > amount_col else 0
                    if amount > 0:
                        total += amount
        except (ValueError, IndexError, TypeError):
            continue
    
    return total


def get_tweets_with_xp_today(discord_id: int | str, discord_name: str, tweets_ws: Optional[gspread.Worksheet] = None, tweets_rows: Optional[List[List[str]]] = None) -> int:
    """Count how many tweets a user has submitted today that received XP (> 0).
    
    Args:
        discord_id: User's Discord ID
        discord_name: User's Discord name (e.g., "username#1234")
        tweets_ws: Optional cached tweets worksheet (to avoid repeated metadata fetches)
        tweets_rows: Optional cached tweets rows data (to avoid repeated read requests)
    
    Returns:
        Number of tweets submitted today that have XP > 0
    """
    try:
        if tweets_rows is not None:
            # Use cached rows data to avoid read request
            rows = tweets_rows
        elif tweets_ws is not None:
            # Use cached worksheet to avoid metadata fetch, but still need to read values
            rows = tweets_ws.get_all_values()
        else:
            # Fallback: fetch worksheet and rows (slower, but backward compatible)
            ws = get_tweets_ws()
            rows = ws.get_all_values()
    except gspread.WorksheetNotFound:
        return 0
    
    if not rows:
        return 0
    
    header = rows[0]
    date_col = None
    member_col = None
    xp_col = None
    
    # Find columns
    for idx, name in enumerate(header):
        if name == "Date":
            date_col = idx
        elif name == "Member":
            member_col = idx
        elif name == "XP Awarded":
            xp_col = idx
    
    # If required columns don't exist, return 0
    if date_col is None or member_col is None or xp_col is None:
        return 0
    
    today = datetime.datetime.now(datetime.timezone.utc).date()
    count = 0
    
    for row in rows[1:]:
        if len(row) <= max(date_col, member_col, xp_col):
            continue
        
        # Check if member matches
        if row[member_col] != discord_name:
            continue
        
        # Check if date is today
        try:
            date_str = row[date_col]
            if date_str:
                # Handle ISO format timestamps
                if "T" in date_str:
                    ts = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                else:
                    ts = datetime.datetime.fromisoformat(date_str)
                
                if ts.date() == today:
                    # Check if XP > 0
                    try:
                        xp_value = row[xp_col] if len(row) > xp_col else "0"
                        xp_amount = float(xp_value) if xp_value else 0
                        if xp_amount > 0:
                            count += 1
                    except (ValueError, TypeError):
                        continue
        except (ValueError, IndexError, TypeError):
            continue
    
    return count


def get_last_submitted_tweet(discord_id: int | str, discord_name: str) -> Optional[Dict[str, Any]]:
    """Get the last submitted tweet for a user.
    
    Args:
        discord_id: User's Discord ID
        discord_name: User's Discord name (e.g., "username#1234")
    
    Returns:
        Dictionary with keys: 'url', 'graded', 'xp_awarded', 'date', or None if no tweets found
    """
    try:
        ws = get_tweets_ws()
        rows = ws.get_all_values()
    except (gspread.WorksheetNotFound, Exception):
        return None
    
    if not rows:
        return None
    
    header = rows[0]
    date_col = None
    member_col = None
    url_col = None
    graded_col = None
    xp_col = None
    
    # Find columns
    for idx, name in enumerate(header):
        if name == "Date":
            date_col = idx
        elif name == "Member":
            member_col = idx
        elif name == "URL":
            url_col = idx
        elif name == "Graded":
            graded_col = idx
        elif name == "XP Awarded":
            xp_col = idx
    
    # If required columns don't exist, return None
    if date_col is None or member_col is None or url_col is None:
        return None
    
    # Find all tweets by this user
    user_tweets = []
    for row in rows[1:]:
        if len(row) <= max(date_col, member_col, url_col):
            continue
        
        # Check if member matches
        if row[member_col] != discord_name:
            continue
        
        # Get date
        date_str = row[date_col] if len(row) > date_col else ""
        if not date_str:
            continue
        
        # Parse date
        try:
            if "T" in date_str:
                date_obj = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                date_obj = datetime.datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            continue
        
        # Get URL
        url = row[url_col] if len(row) > url_col else ""
        if not url:
            continue
        
        # Get graded status
        graded = False
        if graded_col is not None and len(row) > graded_col:
            graded_val = row[graded_col]
            graded = graded_val and str(graded_val).lower() in ("true", "yes", "1", "graded")
        
        # Get XP awarded
        xp_awarded = 0
        if xp_col is not None and len(row) > xp_col:
            try:
                xp_val = row[xp_col]
                if xp_val:
                    xp_awarded = float(xp_val)
            except (ValueError, TypeError):
                pass
        
        user_tweets.append({
            'date': date_obj,
            'url': url,
            'graded': graded,
            'xp_awarded': xp_awarded
        })
    
    # Sort by date (most recent first) and return the first one
    if user_tweets:
        user_tweets.sort(key=lambda x: x['date'], reverse=True)
        return user_tweets[0]
    
    return None


def check_daily_cap(discord_id: int | str, amount: int, source: str) -> Tuple[bool, int, int]:
    """Check if adding XP would exceed daily cap.
    
    Returns:
        (allowed, current_daily_xp, daily_cap)
        - allowed: True if can add XP, False if would exceed cap
        - current_daily_xp: Current XP earned today from this source
        - daily_cap: The daily cap for this user
    """
    # Admin actions bypass caps
    if source in ["admin_grant", "admin_removal", "historical_migration"]:
        return True, 0, 0
    
    # Quiz completion bypasses caps (admin-controlled, limited availability)
    if source == "quiz_completion":
        return True, 0, 0
    
    # Only apply caps to tweet_grade
    if source != "tweet_grade":
        return True, 0, 0
    
    total_xp = get_total_xp(discord_id)
    daily_cap = get_daily_cap_for_user(total_xp)
    current_daily_xp = get_daily_xp_earned(discord_id, source_filter="tweet_grade")
    
    if current_daily_xp + amount > daily_cap:
        return False, current_daily_xp, daily_cap
    
    return True, current_daily_xp, daily_cap


def add_xp(
    discord_id: int | str,
    discord_name: str,
    amount: int,
    source: str,
    twitter_handle: Optional[str] = None,
    reference_type: str = "",
    reference_id: str = "",
    notes: str = "",
    bypass_cap: bool = False,
) -> Tuple[bool, Optional[str]]:
    """Append a single XP event row into xp_events.
    
    Returns:
        (success, error_message)
        - success: True if XP was added, False if blocked by cap
        - error_message: None if success, error message if failed
    """
    # Check daily cap (unless bypassed)
    if not bypass_cap and amount > 0:
        allowed, current_daily, daily_cap = check_daily_cap(discord_id, amount, source)
        if not allowed:
            remaining = daily_cap - current_daily
            return False, f"Daily cap reached ({current_daily}/{daily_cap} XP today). You can earn {remaining} more XP today."
    
    ws = get_xp_events_ws()
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    row = [
        ts,
        str(discord_id),
        discord_name,
        twitter_handle or "",
        source,
        int(amount),
        reference_type,
        reference_id,
        notes,
    ]

    ws.append_row(row, value_input_option="RAW")
    return True, None


async def batch_add_xp(
    xp_entries: List[Dict[str, Any]],
    batch_size: int = 500,
    progress_callback: Optional[Callable[[int, int, int], None]] = None,
) -> Tuple[int, int, List[str]]:
    """Batch append multiple XP events to xp_events sheet.
    
    Args:
        xp_entries: List of dicts with keys: discord_id, discord_name, amount, source,
                    twitter_handle (optional), reference_type, reference_id, notes
        batch_size: Number of rows to append per API call (default: 500)
        progress_callback: Optional callback function(current, total, batch_num) called after each batch
    
    Returns:
        (success_count, error_count, error_messages)
    """
    if not xp_entries:
        return 0, 0, []
    
    ws = get_xp_events_ws()
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # Prepare all rows
    rows = []
    for entry in xp_entries:
        row = [
            ts,
            str(entry.get("discord_id", "")),
            entry.get("discord_name", ""),
            entry.get("twitter_handle", "") or "",
            entry.get("source", ""),
            int(entry.get("amount", 0)),
            entry.get("reference_type", ""),
            entry.get("reference_id", ""),
            entry.get("notes", ""),
        ]
        rows.append(row)
    
    success_count = 0
    error_count = 0
    error_messages = []
    total_rows = len(rows)
    num_batches = (total_rows + batch_size - 1) // batch_size
    
    # Process in batches
    # Use the Google Sheets API values_append endpoint which automatically appends to the end
    # This handles sheet expansion automatically and allows batch appending
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        batch_num = i // batch_size + 1
        
        try:
            # Throttle API calls
            await throttle_sheets_api()
            
            # Use the spreadsheet's values_append method via the client
            # This automatically appends to the end of the sheet and handles expansion
            def _append_batch():
                body = {
                    "values": batch
                }
                return ws.spreadsheet.values_append(
                    f"'{ws.title}'!A:I",
                    params={"valueInputOption": "RAW"},
                    body=body
                )
            
            await retry_with_backoff(
                lambda: asyncio.to_thread(_append_batch),
                max_retries=3,
                initial_delay=1.0,
            )
            
            success_count += len(batch)
            
            # Call progress callback if provided
            if progress_callback:
                try:
                    progress_callback(success_count, total_rows, batch_num)
                except Exception as e:
                    # Don't let progress callback errors break the main process
                    if logger:
                        logger.debug(f"[XPAdmin] Progress callback error: {e}")
            
            # Small delay between batches to be extra safe with rate limits
            if i + batch_size < len(rows):
                await asyncio.sleep(0.2)
                
        except Exception as e:
            error_count += len(batch)
            error_msg = f"Batch {batch_num} failed: {str(e)}"
            error_messages.append(error_msg)
            if logger:
                logger.error(f"[XPAdmin] Error in batch_add_xp batch {batch_num}: {e}", exc_info=True)
            
            # Still call progress callback even on error
            if progress_callback:
                try:
                    progress_callback(success_count, total_rows, batch_num)
                except Exception:
                    pass
    
    # After adding XP events, ensure xp_totals sheet has enough rows for formulas
    # Estimate: if we added many new users, we might need more rows in xp_totals
    # Use a conservative estimate: ensure at least 10,000 rows (can handle ~10k unique users)
    if success_count > 0:
        try:
            # Estimate unique users: assume at most all entries are new users (worst case)
            # Add buffer: ensure sheet can handle at least 2x the number of entries added
            estimated_unique_users = min(success_count * 2, 50000)  # Cap at 50k
            await ensure_xp_totals_sheet_size(min_rows=max(10000, estimated_unique_users + 1000))
        except Exception as e:
            # Log but don't fail - this is a best-effort optimization
            if logger:
                logger.warning(f"[XPAdmin] Could not expand xp_totals sheet: {e}")
    
    return success_count, error_count, error_messages


def get_total_xp(discord_id: int | str) -> int:
    """Read the user's total XP from xp_totals (discord_id, discord_name, total_xp)."""
    try:
        ws = get_xp_totals_ws()
    except gspread.WorksheetNotFound:
        return 0

    discord_id_str = str(discord_id)
    rows = ws.get_all_values()
    for row in rows[1:]:
        if len(row) >= 3 and row[0] == discord_id_str:
            try:
                return int(float(row[2]))
            except ValueError:
                return 0
    return 0


def get_xp_history(discord_id: int | str, limit: int = 30) -> List[Dict[str, Any]]:
    """Get XP history for a user from xp_events sheet.
    
    Returns list of events sorted by most recent first.
    Each event is a dict with: timestamp, source, amount, notes, reference_type, reference_id
    """
    try:
        ws = get_xp_events_ws()
        rows = ws.get_all_values()
    except gspread.WorksheetNotFound:
        return []
    
    discord_id_str = str(discord_id)
    
    if not rows:
        return []
    
    header = rows[0]
    # Expected columns: timestamp, discord_id, discord_name, twitter_handle, source, amount, reference_type, reference_id, notes
    timestamp_col = 0
    discord_id_col = 1
    source_col = 4
    amount_col = 5
    reference_type_col = 6
    reference_id_col = 7
    notes_col = 8
    
    # Find columns by header
    for idx, col_name in enumerate(header):
        col_lower = col_name.lower()
        if "timestamp" in col_lower or "date" in col_lower or "time" in col_lower:
            timestamp_col = idx
        elif "discord_id" in col_lower or "id" == col_lower:
            discord_id_col = idx
        elif "source" in col_lower:
            source_col = idx
        elif "amount" in col_lower or "xp" in col_lower:
            amount_col = idx
        elif "reference_type" in col_lower or "type" in col_lower:
            reference_type_col = idx
        elif "reference_id" in col_lower:
            reference_id_col = idx
        elif "notes" in col_lower:
            notes_col = idx
    
    events = []
    for row in rows[1:]:
        if len(row) <= max(discord_id_col, timestamp_col, source_col, amount_col):
            continue
        
        if row[discord_id_col] != discord_id_str:
            continue
        
        try:
            # Parse timestamp
            ts_str = row[timestamp_col] if len(row) > timestamp_col else ""
            timestamp = None
            if ts_str:
                try:
                    if "T" in ts_str:
                        timestamp = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    else:
                        timestamp = datetime.datetime.fromisoformat(ts_str)
                except (ValueError, TypeError):
                    pass
            
            # Get other fields
            source = row[source_col] if len(row) > source_col else ""
            amount = 0
            try:
                amount = int(float(row[amount_col])) if len(row) > amount_col else 0
            except (ValueError, TypeError):
                pass
            
            reference_type = row[reference_type_col] if len(row) > reference_type_col else ""
            reference_id = row[reference_id_col] if len(row) > reference_id_col else ""
            notes = row[notes_col] if len(row) > notes_col else ""
            
            events.append({
                "timestamp": timestamp,
                "source": source,
                "amount": amount,
                "reference_type": reference_type,
                "reference_id": reference_id,
                "notes": notes,
            })
        except Exception as e:
            log_or_print("debug", f"[XPHistory] Error parsing row: {e}")
            continue
    
    # Sort by timestamp (most recent first)
    events.sort(key=lambda x: x["timestamp"] if x["timestamp"] else datetime.datetime.min.replace(tzinfo=datetime.timezone.utc), reverse=True)
    
    return events[:limit]


# -------------------------------
# Prediction game helpers
# -------------------------------

def has_prediction_today(discord_id: int | str, prediction_type: str, target_date: Optional[datetime.date] = None) -> bool:
    """Check if user has already submitted a prediction of this type for the target date (or today if not specified)."""
    try:
        ws = get_predictions_ws()
        rows = ws.get_all_values()
    except gspread.WorksheetNotFound:
        return False
    
    if not rows or len(rows) < 2:
        return False
    
    discord_id_str = str(discord_id)
    if target_date is None:
        target_date = datetime.datetime.now(datetime.timezone.utc).date()
    
    target_date_str = target_date.isoformat()
    
    # Find column indices
    header = rows[0]
    discord_id_col = 1
    prediction_type_col = 3
    target_date_col = 4
    resolved_col = 7
    
    for idx, col_name in enumerate(header):
        col_lower = col_name.lower()
        if "discord_id" in col_lower or "id" == col_lower:
            discord_id_col = idx
        elif "prediction_type" in col_lower or "type" in col_lower:
            prediction_type_col = idx
        elif "target_date" in col_lower or "target" in col_lower:
            target_date_col = idx
        elif "resolved" in col_lower:
            resolved_col = idx
    
    for row in rows[1:]:
        if len(row) <= max(discord_id_col, prediction_type_col, target_date_col):
            continue
        
        if (row[discord_id_col] == discord_id_str and
            row[prediction_type_col].lower() == prediction_type.lower() and
            row[target_date_col] == target_date_str):
            # Check if already resolved (if resolved, allow new prediction)
            if len(row) > resolved_col and row[resolved_col].lower() in ["true", "yes", "1"]:
                continue
            return True
    
    return False


def can_submit_prediction(target_date: datetime.date) -> Tuple[bool, Optional[str]]:
    """Check if predictions can still be submitted for the target date.
    
    Returns (allowed, error_message)
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    target_datetime = datetime.datetime.combine(target_date, datetime.time(PREDICTION_RESOLUTION_HOUR, 0), tzinfo=datetime.timezone.utc)
    deadline = target_datetime - datetime.timedelta(hours=PREDICTION_DEADLINE_HOURS)
    
    if now >= deadline:
        return False, f"Predictions for {target_date.isoformat()} closed at {deadline.strftime('%H:%M UTC')} (1 hour before resolution)."
    
    if target_date < now.date():
        return False, "Cannot submit predictions for past dates."
    
    return True, None


def calculate_volume_accuracy(predicted: float, actual: float) -> float:
    """Calculate accuracy percentage for volume predictions.
    
    Accuracy is based on how close the prediction is to actual value.
    Returns a value between 0.0 and 1.0 (100% accuracy).
    """
    if actual == 0:
        return 0.0 if predicted != 0 else 1.0
    
    error = abs(predicted - actual) / actual
    # Convert error to accuracy: 0% error = 100% accuracy, 100% error = 0% accuracy
    # Use exponential decay for better scoring
    accuracy = max(0.0, 1.0 - error)
    return accuracy


def calculate_top10_accuracy(predicted_data: Dict[str, Any], actual_top10: List[Dict[str, Any]], previous_top10_tokens: List[str]) -> float:
    """Calculate accuracy for top10 predictions.
    
    predicted_data should contain:
    - "new_entries": List of token symbols expected to enter top 10
    - "removed_entries": List of token symbols expected to leave top 10
    
    actual_top10: Current top 10 transactions
    previous_top10_tokens: List of token symbols from previous day's top 10
    
    Returns accuracy between 0.0 and 1.0.
    """
    if not predicted_data or not actual_top10:
        return 0.0
    
    # Extract current top 10 tokens
    current_tokens = set()
    for tx in actual_top10[:10]:
        token = tx.get("TokenSymbol", "").strip().upper()
        if token:
            current_tokens.add(token)
    
    previous_tokens = set(t.upper() for t in previous_top10_tokens)
    
    # Calculate what actually changed
    actual_new = current_tokens - previous_tokens  # Tokens in current but not in previous
    actual_removed = previous_tokens - current_tokens  # Tokens in previous but not in current
    
    # Get predicted changes
    predicted_new = set(t.upper() for t in predicted_data.get("new_entries", []))
    predicted_removed = set(t.upper() for t in predicted_data.get("removed_entries", []))
    
    # Calculate correct predictions
    correct_new = len(predicted_new & actual_new)
    correct_removed = len(predicted_removed & actual_removed)
    
    total_predicted = len(predicted_new) + len(predicted_removed)
    total_actual = len(actual_new) + len(actual_removed)
    
    if total_predicted == 0:
        return 0.0
    
    # Accuracy: (correct predictions / total predicted) weighted by how many changes actually happened
    if total_actual == 0:
        # No changes happened - if user predicted no changes, give full credit
        if total_predicted == 0:
            return 1.0
        # User predicted changes but none happened
        return 0.0
    
    # Calculate accuracy: correct / predicted, but also consider precision
    accuracy = (correct_new + correct_removed) / total_predicted if total_predicted > 0 else 0.0
    
    # Bonus for precision: if user predicted fewer changes and got them all right, boost score
    if total_predicted <= total_actual and (correct_new + correct_removed) == total_predicted:
        accuracy = min(1.0, accuracy * 1.2)  # 20% bonus for perfect precision
    
    return min(1.0, max(0.0, accuracy))


def calculate_prediction_xp(accuracy: float, base_xp: int) -> int:
    """Calculate XP awarded based on prediction accuracy.
    
    accuracy: 0.0 to 1.0
    base_xp: Base XP for this prediction type
    
    Returns XP amount (0 to base_xp * 2 for perfect predictions)
    """
    if accuracy <= 0:
        return 0
    
    # Linear scaling: 50% accuracy = 50% of base XP, 100% accuracy = 200% of base XP
    xp = int(base_xp * (0.5 + 1.5 * accuracy))
    return max(0, xp)


def get_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Return top N users by total XP based on xp_totals."""
    try:
        ws = get_xp_totals_ws()
    except gspread.WorksheetNotFound:
        return []

    rows = ws.get_all_values()
    entries: List[Dict[str, Any]] = []
    for row in rows[1:]:
        if len(row) < 3:
            continue
        discord_id, discord_name, total_xp_str = row[0], row[1], row[2]
        if not discord_id:
            continue
        try:
            total_xp = int(float(total_xp_str))
        except ValueError:
            continue
        entries.append(
            {
                "discord_id": discord_id,
                "discord_name": discord_name,
                "total_xp": total_xp,
            }
        )

    entries.sort(key=lambda e: e["total_xp"], reverse=True)
    return entries[:limit]


def get_user_rank(discord_id: int | str) -> Optional[Dict[str, Any]]:
    """Return the rank information for a user based on xp_totals."""
    try:
        ws = get_xp_totals_ws()
    except gspread.WorksheetNotFound:
        return None

    rows = ws.get_all_values()
    entries: List[Tuple[str, str, int]] = []
    for row in rows[1:]:
        if len(row) < 3:
            continue
        row_discord_id = row[0]
        if not row_discord_id:
            continue
        try:
            total_xp = int(float(row[2]))
        except ValueError:
            continue
        entries.append((row_discord_id, row[1], total_xp))

    if not entries:
        return None

    # Sort descending by XP
    entries.sort(key=lambda item: item[2], reverse=True)
    total_users = len(entries)

    discord_id_str = str(discord_id)
    for idx, (row_id, row_name, total_xp) in enumerate(entries, start=1):
        if row_id == discord_id_str:
            return {
                "rank": idx,
                "total_users": total_users,
                "discord_name": row_name,
                "total_xp": total_xp,
            }

    return None


def get_xp_breakdown(discord_id: int | str) -> Dict[str, int]:
    """Return XP breakdown for a user by category."""
    categories = {
        "polymer_university": 0,
        "twitter_submissions": 0,
        "daily_quiz": 0,
        "other": 0,
    }

    try:
        ws = get_xp_events_ws()
        rows = ws.get_all_values()
    except gspread.WorksheetNotFound:
        return categories

    if not rows or len(rows) < 2:
        return categories

    header = rows[0]
    discord_id_col = 1
    source_col = 4
    amount_col = 5
    reference_id_col = 7

    for idx, col_name in enumerate(header):
        col_lower = col_name.lower()
        if "discord_id" in col_lower or "user" in col_lower:
            discord_id_col = idx
        elif "source" in col_lower:
            source_col = idx
        elif "amount" in col_lower or "xp" in col_lower:
            amount_col = idx
        elif "reference_id" in col_lower or "reference" in col_lower:
            reference_id_col = idx

    discord_id_str = str(discord_id)

    for row in rows[1:]:
        if len(row) <= max(discord_id_col, source_col, amount_col):
            continue

        if row[discord_id_col] != discord_id_str:
            continue

        try:
            amount = int(float(row[amount_col]))
        except (ValueError, TypeError):
            continue

        if amount == 0:
            continue

        source = row[source_col].lower().strip() if len(row) > source_col else ""
        reference_id = row[reference_id_col].lower().strip() if len(row) > reference_id_col else ""

        if source == "tweet_grade":
            categories["twitter_submissions"] += amount
        elif source == "historical_migration":
            # Historical migration XP should be categorized as twitter submissions
            categories["twitter_submissions"] += amount
        elif source == "quiz_completion":
            if reference_id == "quiz_metrics":
                categories["daily_quiz"] += amount
            else:
                categories["polymer_university"] += amount
        elif source in {"grandfather_bonus", "admin_grant"}:
            categories["polymer_university"] += amount
        else:
            categories["other"] += amount

    return categories


# -------------------------------
# Historical XP Migration helpers
# -------------------------------

def load_old_leaderboard_csv(csv_path: str) -> List[Dict[str, Any]]:
    """Load old leaderboard CSV and return list of entries."""
    entries = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip empty rows
                if not row.get("Total XP") or not row.get("Total XP").strip():
                    continue
                
                try:
                    xp = float(row["Total XP"])
                    if xp <= 0:
                        continue
                    
                    entries.append({
                        "discord_username": row.get("Discord Username", "").strip(),
                        "twitter_handle": row.get("Twitter Handle", "").strip().lstrip("@"),
                        "total_xp": int(round(xp)),  # Round to int
                    })
                except (ValueError, KeyError) as e:
                    log_or_print("debug", f"[Migration] Skipping invalid row: {row} - {e}")
                    continue
    except FileNotFoundError:
        log_or_print("warning", f"[Migration] CSV file not found: {csv_path}")
    except Exception as e:
        log_or_print("error", f"[Migration] Error loading CSV: {e}")
    
    return entries


async def find_user_by_username_or_twitter(
    guild: discord.Guild, 
    username: str, 
    twitter_handle: str
) -> Optional[discord.Member]:
    """Try to find a user by Discord username or Twitter handle.
    
    Priority order:
    1. Twitter handle in twitter_handles.csv (most reliable - users who registered)
    2. Discord username matching
    3. Twitter handle fallback (if not in CSV but in old leaderboard)
    """
    # PRIORITY 1: Check twitter_handles.csv first (users who have registered via /set_twitter)
    # This is most reliable since these users actively set their handles
    if twitter_handle:
        try:
            with open(TWITTER_HANDLES_CSV, "r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 3:
                        csv_handle = row[2].lstrip("@").lower().strip()
                        if csv_handle == twitter_handle.lower().strip():
                            discord_id = row[0]
                            try:
                                member = guild.get_member(int(discord_id))
                                if member:
                                    return member
                            except (ValueError, TypeError):
                                continue
        except FileNotFoundError:
            pass
    
    # PRIORITY 2: Try by Discord username
    if username:
        # Clean username (remove #discriminator if present, handle new format)
        username_clean = username.split("#")[0].strip().lower()
        
        # Try exact match with get_member_named (handles old format with #)
        if "#" in username:
            member = guild.get_member_named(username)
            if member:
                return member
        
        # Try partial match (username without discriminator)
        for member in guild.members:
            # Match by display name or username
            if (member.name.lower() == username_clean or 
                (member.display_name and member.display_name.lower() == username_clean) or
                str(member).lower() == username.lower()):
                return member
    
    return None


def cross_reference_leaderboard_with_handles(old_leaderboard_path: str) -> Dict[str, Any]:
    """Cross-reference old leaderboard entries with twitter_handles.csv.
    
    Returns stats about how many entries can be matched.
    """
    old_entries = load_old_leaderboard_csv(old_leaderboard_path)
    
    # Load twitter_handles.csv
    registered_handles = {}
    try:
        with open(TWITTER_HANDLES_CSV, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 3:
                    handle = row[2].lstrip("@").lower().strip()
                    discord_id = row[0]
                    registered_handles[handle] = {
                        'discord_id': discord_id,
                        'discord_name': row[1] if len(row) > 1 else ""
                    }
    except FileNotFoundError:
        pass
    
    stats = {
        'total_old_entries': len(old_entries),
        'matched_by_twitter': 0,
        'matched_by_username': 0,
        'not_in_handles_csv': [],
        'in_handles_csv': []
    }
    
    for entry in old_entries:
        twitter_handle = entry['twitter_handle'].lower().strip() if entry['twitter_handle'] else ""
        username = entry['discord_username']
        
        # Check if Twitter handle exists in registered handles
        if twitter_handle and twitter_handle in registered_handles:
            stats['matched_by_twitter'] += 1
            stats['in_handles_csv'].append({
                'username': username or "N/A",
                'twitter': entry['twitter_handle'],
                'xp': entry['total_xp'],
                'discord_id': registered_handles[twitter_handle]['discord_id']
            })
        else:
            stats['not_in_handles_csv'].append({
                'username': username or "N/A",
                'twitter': entry['twitter_handle'] or "N/A",
                'xp': entry['total_xp']
            })
    
    return stats


async def migrate_historical_xp(
    guild: discord.Guild,
    csv_path: str,
    dry_run: bool = True
) -> Dict[str, Any]:
    """Migrate historical XP from old leaderboard CSV.
    
    Returns:
        dict with stats: {
            'total_entries': int,
            'found_users': int,
            'not_found': List[dict],
            'migrated': int,
            'errors': List[str]
        }
    """
    entries = load_old_leaderboard_csv(csv_path)
    stats = {
        'total_entries': len(entries),
        'found_users': 0,
        'not_found': [],
        'migrated': 0,
        'errors': []
    }
    
    if not entries:
        stats['errors'].append("No valid entries found in CSV")
        return stats
    
    # OPTIMIZATION: Load xp_events sheet ONCE and cache migration entries
    # This avoids reading the sheet for every user (which causes rate limits)
    existing_migrations = set()  # Set of (user_id, reference_id) tuples
    if not dry_run:
        try:
            await throttle_sheets_api()
            ws_events = await retry_with_backoff(
                lambda: asyncio.to_thread(get_xp_events_ws),
                max_retries=3,
                initial_delay=1.0,
            )
            await throttle_sheets_api()
            rows = await retry_with_backoff(
                lambda: asyncio.to_thread(ws_events.get_all_values),
                max_retries=3,
                initial_delay=1.0,
            )
            
            # Cache all existing migration entries
            if len(rows) > 1:  # Has header + data
                for row in rows[1:]:
                    if len(row) >= 8:
                        row_user_id = row[1]  # Discord ID column
                        row_source = row[4]  # Source column
                        row_ref_id = row[7]  # Reference ID column
                        if row_source == "historical_migration" and row_ref_id:
                            existing_migrations.add((row_user_id, row_ref_id))
        except Exception as cache_error:
            # If we can't load the cache, proceed anyway (will check individually)
            if logger:
                logger.warning(f"[Migration] Could not cache existing migrations: {cache_error}")
    
    # Process each entry
    for idx, entry in enumerate(entries, 1):
        username = entry['discord_username']
        twitter_handle = entry['twitter_handle']
        xp_amount = entry['total_xp']
        
        # Try to find user
        member = await find_user_by_username_or_twitter(guild, username, twitter_handle)
        
        if not member:
            stats['not_found'].append({
                'username': username or "N/A",
                'twitter': twitter_handle or "N/A",
                'xp': xp_amount
            })
            continue
        
        stats['found_users'] += 1
        
        if not dry_run:
            try:
                # Check if this specific migration entry already exists (avoid duplicates)
                reference_id = f"old_leaderboard_{username or twitter_handle}"
                user_id_str = str(member.id)
                
                # Check cached migrations
                if (user_id_str, reference_id) in existing_migrations:
                    stats['errors'].append(
                        f"User {member} already has migration entry for {reference_id}, skipping"
                    )
                    continue
                
                # Add historical XP (bypass cap for migration)
                # This will add to existing XP if user already has some
                # Use retry logic and throttling for API calls
                def _add_xp_sync():
                    return add_xp(
                        discord_id=member.id,
                        discord_name=str(member),
                        amount=xp_amount,
                        source="historical_migration",
                        twitter_handle=twitter_handle if twitter_handle else None,
                        reference_type="migration",
                        reference_id=reference_id,
                        notes=f"Migrated from old leaderboard - Original: {username or 'N/A'}",
                        bypass_cap=True,
                    )
                
                await throttle_sheets_api()
                success, error_msg = await retry_with_backoff(
                    lambda: asyncio.to_thread(_add_xp_sync),
                    max_retries=3,
                    initial_delay=2.0,  # Longer initial delay for migrations
                    max_delay=60.0,
                )
                
                if not success:
                    stats['errors'].append(f"Failed to add XP for {member}: {error_msg}")
                    continue
                
                # Add to cache to avoid duplicate checks
                existing_migrations.add((user_id_str, reference_id))
                stats['migrated'] += 1
                
                # Rate limiting: Add delay between users to avoid hitting API limits
                # Process in batches with delays
                if idx % 10 == 0:  # Every 10 users, add extra delay
                    await asyncio.sleep(2.0)
                else:
                    await asyncio.sleep(0.5)  # Small delay between each user
                    
            except Exception as e:
                error_str = str(e)
                # Check if it's a rate limit error
                if "429" in error_str or "Quota exceeded" in error_str:
                    stats['errors'].append(f"Error migrating {member}: Rate limit hit - {error_str[:100]}")
                    # Add longer delay before continuing
                    await asyncio.sleep(5.0)
                else:
                    stats['errors'].append(f"Error migrating {member}: {error_str[:200]}")
        else:
            # Dry run - just count
            stats['migrated'] += 1
    
    return stats


# -------------------------------
# Quiz helpers
# -------------------------------

def load_questions() -> List[Dict[str, str]]:
    """Load questions from CSV file."""
    if not os.path.exists(QUIZ_DATA_FILE):
        log_or_print("warning", f"[Quiz] Questions file not found: {QUIZ_DATA_FILE}")
        return []
    
    try:
        with open(QUIZ_DATA_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception as e:
        log_or_print("error", f"[Quiz] Error loading questions: {e}")
        return []


def log_quiz_result(user: discord.User, score: int, total: int, passed: bool, required_score: int, discord_post_check: Optional[str] = None) -> None:
    """Log quiz result to CSV file.
    
    Args:
        user: Discord user who took the quiz
        score: User's score
        total: Total number of questions
        passed: Whether user passed the quiz
        required_score: Score needed to pass
        discord_post_check: Status of Discord post check (e.g., "passed", "failed", "not_checked")
    """
    try:
        file_exists = os.path.exists(QUIZ_RESULTS_FILE)
        
        # Check if file exists and has header to determine if we need to add the new column
        needs_header = not file_exists
        if file_exists:
            # Read first line to check if header has the new column
            with open(QUIZ_RESULTS_FILE, "r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                try:
                    header = next(reader)
                    needs_header = "discord_post_check" not in header
                except StopIteration:
                    needs_header = True
        
        with open(QUIZ_RESULTS_FILE, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if needs_header:
                writer.writerow(["username", "user_id", "score", "total", "required_score", "result", "discord_post_check"])
            writer.writerow([user.name, user.id, score, total, required_score, "passed" if passed else "failed", discord_post_check or "not_checked"])
    except Exception as e:
        log_or_print("error", f"[Quiz] Error logging result: {e}")


async def force_stop_quiz(user_id: int) -> None:
    """Force-stop a quiz for a user and clean up their messages."""
    session = bot.quiz_sessions.get(user_id)
    if session:
        # Cancel pending wait tasks
        if 'wait_task' in session and not session['wait_task'].done():
            session['wait_task'].cancel()
            try:
                await session['wait_task']
            except asyncio.CancelledError:
                pass

        # Mark as stopped
        session['stopped'] = True
        bot.quiz_sessions.pop(user_id, None)


# -------------------------------
# Twitter handle helpers
# -------------------------------

def ensure_handles_file_exists() -> None:
    """Ensure the Twitter handles CSV file exists with proper headers.
    
    Creates the file with headers if it doesn't exist.
    """
    if not os.path.exists(TWITTER_HANDLES_CSV):
        with open(TWITTER_HANDLES_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["discord_id", "discord_name", "twitter_handle"])


def upsert_twitter_handle(discord_id: int, discord_name: str, handle: str) -> None:
    """Add or update the mapping in twitter_handles.csv"""
    ensure_handles_file_exists()
    with open(TWITTER_HANDLES_CSV, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        rows = [["discord_id", "discord_name", "twitter_handle"]]

    updated = False
    for i in range(1, len(rows)):
        row = rows[i]
        if not row:
            continue
        if row[0] == str(discord_id):
            rows[i] = [str(discord_id), discord_name, handle]
            updated = True
            break

    if not updated:
        rows.append([str(discord_id), discord_name, handle])

    with open(TWITTER_HANDLES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def get_twitter_handle_for_user(discord_id: int) -> Optional[str]:
    ensure_handles_file_exists()
    with open(TWITTER_HANDLES_CSV, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return None

    for i in range(1, len(rows)):
        row = rows[i]
        if not row:
            continue
        if row[0] == str(discord_id) and len(row) >= 3:
            handle = row[2].lstrip("@").strip()
            return handle or None
    return None


def get_twitter_handle_for_username(discord_username: str) -> Optional[str]:
    """Get Twitter handle by Discord username (from discord_name column in CSV).
    
    Args:
        discord_username: Discord username (e.g., "username#1234" or "username")
        
    Returns:
        Twitter handle (without @) or None if not found
    """
    ensure_handles_file_exists()
    with open(TWITTER_HANDLES_CSV, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return None

    # Normalize username for comparison (remove discriminator if present)
    normalized_username = discord_username.split("#")[0].strip().lower()

    for i in range(1, len(rows)):
        row = rows[i]
        if not row or len(row) < 3:
            continue
        # Compare normalized usernames
        csv_username = row[1].split("#")[0].strip().lower() if row[1] else ""
        if csv_username == normalized_username:
            handle = row[2].lstrip("@").strip()
            return handle or None
    return None


# -------------------------------
# State handling
# -------------------------------

def load_state() -> Dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return {
            "last_top10_ids": [],
            "announced_top10_ids": [],
            "last_milestone": 0.0,
            "initialized_milestone": False,
            "initialized_leaderboard": False,
            "volume_history": [],
            "transaction_count_history": [],  # Track total transaction count over time
            "biggest_transaction_history": [],  # Track biggest transaction per snapshot
            "previous_top10_tokens": [],  # Store previous day's top 10 tokens for prediction resolution
            "components_enabled": {  # Component toggle states
                "leaderboard_checking": True,
                "volume_checking": True,
                "daily_summary": True,
                "prediction_resolution": True,
                "metrics_quiz": True,
                "thread_cleanup": True,
                "auto_process_tweets": True,  # Auto-process ungraded tweets at 2am UTC
            },
            "metrics_quiz_message_id": None,  # Store the current quiz message ID for replacement
            "metrics_quiz_channel_id": None,  # Store the channel ID for quiz posting
            "main_metrics_channel_id": None,  # Main channel for metrics announcements (daily summary, top 10 TX)
            "volume_channel_id": None,  # Voice channel for volume counter
            "leaderboard_channel_id": None,  # Channel for daily XP leaderboard posts
            "admin_role_name": None,  # Admin role name (falls back to env var)
            "tweet_xp_daily_limit": 3,  # Maximum number of tweets per day that can earn XP
        }
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    data.setdefault("last_top10_ids", [])
    data.setdefault("announced_top10_ids", [])
    data.setdefault("last_milestone", 0.0)
    data.setdefault("initialized_milestone", False)
    data.setdefault("initialized_leaderboard", False)
    data.setdefault("volume_history", [])
    data.setdefault("transaction_count_history", [])
    data.setdefault("biggest_transaction_history", [])
    data.setdefault("previous_top10_tokens", [])
    data.setdefault("components_enabled", {
        "leaderboard_checking": True,
        "volume_checking": True,
        "daily_summary": True,
        "prediction_resolution": True,
        "metrics_quiz": True,
        "thread_cleanup": True,
    })
    data.setdefault("metrics_quiz_message_id", None)
    data.setdefault("metrics_quiz_channel_id", None)
    data.setdefault("main_metrics_channel_id", None)
    data.setdefault("volume_channel_id", None)
    data.setdefault("leaderboard_channel_id", None)
    data.setdefault("admin_role_name", None)
    data.setdefault("tweet_xp_daily_limit", 3)  # Default to 3 tweets per day
    data.setdefault("min_discord_posts", 3)  # Default to 3 posts required for XP-earning activities (shared config)
    data.setdefault("excluded_channel_ids", [933812975297527818])  # Channels excluded from message counting
    # Backward compatibility: if quiz_min_discord_posts exists but min_discord_posts doesn't, migrate it
    if "quiz_min_discord_posts" in data and "min_discord_posts" not in data:
        data["min_discord_posts"] = data["quiz_min_discord_posts"]
    return data


def save_state(state: Dict[str, Any]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)


state: Dict[str, Any] = load_state()

# Initialize logger
logger = setup_logging()

def log_or_print(level: str, message: str, *args, **kwargs) -> None:
    """Helper function to log or print if logger is not available.
    
    This function provides a fallback mechanism for logging when the logger
    might not be initialized yet (e.g., during early startup).
    
    Args:
        level: Log level ('debug', 'info', 'warning', 'error', 'critical')
        message: Message to log
        *args: Additional positional arguments for logger methods
        **kwargs: Additional keyword arguments for logger methods (e.g., exc_info)
    """
    if logger:
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(message, *args, **kwargs)
    else:
        print(f"[{level.upper()}] {message}")

# -------------------------------
# Custom metrics quiz questions
# -------------------------------

def load_custom_metrics_quiz_questions() -> List[Dict[str, str]]:
    """Load custom metrics quiz questions from CSV."""
    questions: List[Dict[str, str]] = []
    if not os.path.exists(METRICS_QUIZ_CSV):
        return questions
    try:
        with open(METRICS_QUIZ_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row:
                    continue
                if all(
                    key in row and row[key].strip()
                    for key in ["question", "option_a", "option_b", "option_c", "option_d", "correct"]
                ):
                    correct = row["correct"].strip().lower()
                    if correct in ["a", "b", "c", "d"]:
                        questions.append(
                            {
                                "question": row["question"].strip(),
                                "option_a": row["option_a"].strip(),
                                "option_b": row["option_b"].strip(),
                                "option_c": row["option_c"].strip(),
                                "option_d": row["option_d"].strip(),
                                "correct": correct,
                            }
                        )
    except Exception as e:
        if logger:
            logger.error(f"[MetricsQuiz] Error reading custom CSV: {e}", exc_info=True)
    return questions

# -------------------------------
# Discord bot setup
# -------------------------------

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
allowed_mentions = discord.AllowedMentions(everyone=True)
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    allowed_mentions=allowed_mentions,
)

# Quiz session tracking
bot.quiz_sessions = {}
active_threads = {}
thread_semaphore = asyncio.Semaphore(1)  # only 1 thread-create call at a time


# -------------------------------
# Rate limiting helpers
# -------------------------------

def check_user_rate_limit(user_id: int, cooldown_seconds: int = USER_COMMAND_COOLDOWN) -> bool:
    """Check if a user can perform an action based on rate limiting.
    
    Args:
        user_id: Discord user ID
        cooldown_seconds: Minimum seconds between actions
        
    Returns:
        True if user can proceed, False if rate limited
    """
    now = datetime.datetime.utcnow().timestamp()
    
    if user_id not in user_command_timestamps:
        user_command_timestamps[user_id] = deque()
    
    timestamps = user_command_timestamps[user_id]
    
    # Remove old timestamps outside the window
    while timestamps and (now - timestamps[0]) > USER_COMMAND_WINDOW:
        timestamps.popleft()
    
    # Check if user has made a request recently
    if timestamps and (now - timestamps[-1]) < cooldown_seconds:
        return False
    
    # Record this request
    timestamps.append(now)
    return True


def get_user_rate_limit_remaining(user_id: int, cooldown_seconds: int = USER_COMMAND_COOLDOWN) -> float:
    """Get remaining seconds until user can perform action again.
    
    Returns:
        Seconds remaining (0 if can proceed now)
    """
    if user_id not in user_command_timestamps:
        return 0.0
    
    timestamps = user_command_timestamps[user_id]
    if not timestamps:
        return 0.0
    
    now = datetime.datetime.utcnow().timestamp()
    last_request = timestamps[-1]
    elapsed = now - last_request
    remaining = max(0.0, cooldown_seconds - elapsed)
    return remaining


async def throttle_sheets_api() -> None:
    """Throttle Google Sheets API calls to respect rate limits.
    
    Ensures minimum interval between API calls to avoid hitting rate limits.
    Sleeps if necessary to maintain the required interval (SHEETS_API_MIN_INTERVAL).
    Uses a global lock to ensure thread-safe rate limiting.
    """
    global sheets_api_last_call
    
    async with sheets_api_lock:
        now = time.time()
        time_since_last = now - sheets_api_last_call
        
        if time_since_last < SHEETS_API_MIN_INTERVAL:
            wait_time = SHEETS_API_MIN_INTERVAL - time_since_last
            await asyncio.sleep(wait_time)
        
        sheets_api_last_call = time.time()


async def throttle_openai_api() -> None:
    """Throttle OpenAI API calls to respect rate limits.
    
    Ensures minimum interval between API calls to avoid hitting rate limits.
    Sleeps if necessary to maintain the required interval (OPENAI_API_MIN_INTERVAL).
    Uses a global lock to ensure thread-safe rate limiting.
    """
    global openai_api_last_call
    
    async with openai_api_lock:
        now = time.time()
        time_since_last = now - openai_api_last_call
        
        if time_since_last < OPENAI_API_MIN_INTERVAL:
            wait_time = OPENAI_API_MIN_INTERVAL - time_since_last
            await asyncio.sleep(wait_time)
        
        openai_api_last_call = time.time()


async def throttle_twitter_api() -> None:
    """Throttle Twitter API calls to respect rate limits.
    
    Ensures minimum interval between API calls to avoid hitting rate limits.
    Also checks if we're near the rate limit based on headers from previous responses.
    Sleeps if necessary to maintain the required interval or wait for rate limit reset.
    Uses a global lock to ensure thread-safe rate limiting.
    
    More aggressive rate limiting:
    - Blocks requests when remaining < 5 (unless waiting for reset)
    - Increases delays exponentially as remaining decreases
    - Minimum 6 seconds between calls (150 requests per 15 minutes max)
    """
    global twitter_api_last_call, twitter_api_rate_limit_reset, twitter_api_remaining
    
    async with twitter_api_lock:
        now = time.time()
        
        # Check if we need to wait for rate limit reset
        # Only wait if we're actually out of quota (remaining = 0 or very low)
        # The x-rate-limit-reset header tells us when the window resets, but we should
        # only wait for it if we've exhausted our quota, not on every call
        if twitter_api_rate_limit_reset and now < twitter_api_rate_limit_reset:
            # Only wait for reset if we're out of quota or have very few requests left
            if twitter_api_remaining is not None and twitter_api_remaining <= 0:
                wait_time = twitter_api_rate_limit_reset - now
                if wait_time > 0:
                    if logger:
                        logger.info(f"[TwitterAPI] Rate limit exhausted (remaining: 0). Window resets in {wait_time:.0f}s, waiting...")
                    await asyncio.sleep(wait_time)
                    now = time.time()
        
        # More aggressive rate limiting: block requests when remaining is very low
        if twitter_api_remaining is not None and twitter_api_remaining < 5:
            # If we have less than 5 requests remaining, wait longer
            # Calculate wait time based on remaining requests and time until reset
            if twitter_api_rate_limit_reset and now < twitter_api_rate_limit_reset:
                # Wait proportionally until reset
                time_until_reset = twitter_api_rate_limit_reset - now
                # If we have very few requests left, wait longer
                if twitter_api_remaining <= 2:
                    # For 0-2 remaining, wait at least 30 seconds or until reset (whichever is shorter)
                    wait_time = min(time_until_reset, 30.0)
                else:
                    # For 3-4 remaining, wait at least 15 seconds or until reset (whichever is shorter)
                    wait_time = min(time_until_reset, 15.0)
                
                if wait_time > 0:
                    if logger:
                        logger.warning(f"[TwitterAPI] Very low rate limit remaining ({twitter_api_remaining}), waiting {wait_time:.1f}s before request")
                    await asyncio.sleep(wait_time)
                    now = time.time()
            else:
                # No reset time known, add significant delay
                extra_delay = (5 - twitter_api_remaining) * 3.0  # 3s per request under 5
                if logger:
                    logger.warning(f"[TwitterAPI] Low rate limit remaining ({twitter_api_remaining}), adding {extra_delay:.1f}s delay")
                await asyncio.sleep(extra_delay)
        
        # Check remaining quota - if we're getting low, add extra delay
        elif twitter_api_remaining is not None and twitter_api_remaining < 15:
            # If we have less than 15 requests remaining, add extra delay
            # More aggressive: 1.5s per request under 15 (was 0.5s per request under 10)
            extra_delay = (15 - twitter_api_remaining) * 1.5
            if logger:
                logger.warning(f"[TwitterAPI] Low rate limit remaining ({twitter_api_remaining}), adding {extra_delay:.1f}s delay")
            await asyncio.sleep(extra_delay)
        
        # Ensure minimum interval between calls
        time_since_last = now - twitter_api_last_call
        if time_since_last < TWITTER_API_MIN_INTERVAL:
            wait_time = TWITTER_API_MIN_INTERVAL - time_since_last
            await asyncio.sleep(wait_time)
        
        twitter_api_last_call = time.time()


async def retry_with_backoff(
    func: Callable[[], Any],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    retry_on: Tuple[int, ...] = (429, 500, 502, 503, 504),
) -> Any:
    """Retry a function with exponential backoff.
    
    Args:
        func: Async function to retry
        max_retries: Maximum number of retries
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        backoff_factor: Multiplier for delay on each retry
        retry_on: Tuple of status codes to retry on
        
    Returns:
        Result of func() or raises last exception
    """
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            
            # Check if this is a retryable error
            should_retry = False
            retry_delay = None
            
            # Check for TwitterUsageCapExceededError first - don't retry these
            if isinstance(e, TwitterUsageCapExceededError):
                should_retry = False
                log_or_print("error", f"[Retry] Twitter API usage cap exceeded - not retrying. {e}")
            # Check for TwitterRateLimitError
            elif isinstance(e, TwitterRateLimitError):
                should_retry = True
                if e.retry_after:
                    retry_delay = min(e.retry_after, max_delay)
            elif hasattr(e, 'status'):
                should_retry = e.status in retry_on
            elif hasattr(e, 'response') and hasattr(e.response, 'status'):
                should_retry = e.response.status in retry_on
            elif isinstance(e, gspread.exceptions.APIError):
                # Google Sheets API errors
                if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                    if e.response.status_code in retry_on:
                        should_retry = True
                # Also check for rate limit errors in the error message
                error_msg = str(e)
                if '429' in error_msg or 'Quota exceeded' in error_msg or 'rate limit' in error_msg.lower():
                    should_retry = True
                    # Extract retry-after if available
                    if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                        retry_after_header = e.response.headers.get('Retry-After')
                        if retry_after_header:
                            try:
                                retry_delay = float(retry_after_header)
                            except (ValueError, TypeError):
                                pass
            
            if not should_retry or attempt >= max_retries:
                raise
            
            # Use retry_after if available, otherwise use exponential backoff
            if retry_delay is not None:
                wait_time = retry_delay
            else:
                wait_time = min(delay, max_delay)
                delay *= backoff_factor
            
            # Wait before retrying
            if logger:
                logger.info(f"[Retry] Waiting {wait_time:.1f}s before retry (attempt {attempt + 1}/{max_retries + 1})")
            await asyncio.sleep(wait_time)
    
    raise last_exception


def can_send_dm() -> bool:
    """Check if we can send a DM without hitting rate limits."""
    now = datetime.datetime.utcnow()
    while dm_timestamps and (now - dm_timestamps[0]).total_seconds() > DM_WINDOW:
        dm_timestamps.popleft()
    return len(dm_timestamps) < DM_RATE_LIMIT


def register_dm_send() -> None:
    """Register that we sent a DM."""
    dm_timestamps.append(datetime.datetime.utcnow())


async def safe_delete_message(message: discord.Message, delay: float = 0.5) -> bool:
    """Safely delete a message with rate limit handling."""
    try:
        await asyncio.sleep(delay)  # Add delay to avoid rate limits
        await message.delete()
        return True
    except discord.NotFound:
        return False  # Already deleted
    except discord.HTTPException as e:
        if e.status == 429:
            # Rate limited - wait and retry once
            retry_after = e.retry_after if hasattr(e, 'retry_after') else 1.0
            await asyncio.sleep(retry_after)
            try:
                await message.delete()
                return True
            except Exception:
                return False
        return False
    except Exception as e:
        log_or_print("warning", f"[SafeDelete] Failed to delete message: {e}")
        return False


async def batch_delete_messages(messages: List[discord.Message], batch_size: int = 5, delay: float = 1.0) -> int:
    """Delete messages in batches to avoid rate limits. Returns number deleted."""
    deleted = 0
    for i, msg in enumerate(messages):
        if await safe_delete_message(msg, delay=delay if i > 0 else 0):
            deleted += 1
        # Add extra delay every batch_size messages
        if (i + 1) % batch_size == 0:
            await asyncio.sleep(2.0)
    return deleted


# -------------------------------
# Permission helpers
# -------------------------------

def get_admin_role_name() -> str:
    """Get admin role name from state or fallback to env var/default."""
    return state.get("admin_role_name") or ADMIN_ROLE_NAME

def get_admin_role_list() -> List[str]:
    """Get admin role name as a list for use in decorators."""
    return [get_admin_role_name()]

def get_min_discord_posts() -> int:
    """Get minimum Discord posts required for XP-earning activities from state or default.
    
    This is a shared configuration used across multiple features (quizzes, etc.)
    to prevent bots from gaming the XP system.
    
    Returns:
        Minimum number of Discord posts required (default: 3)
    """
    # Check for new shared key first, then legacy quiz-specific key for backward compatibility
    if "min_discord_posts" in state:
        return state.get("min_discord_posts", 3)
    # Backward compatibility: check legacy key
    if "quiz_min_discord_posts" in state:
        return state.get("quiz_min_discord_posts", 3)
    return 3

def get_excluded_channel_ids() -> List[int]:
    """Get list of channel IDs to exclude from Discord message counting.
    
    These channels are excluded when counting messages for bot detection.
    Can be configured via state.json in the future.
    
    Returns:
        List of channel IDs to exclude (default: [933812975297527818])
    """
    # Get from state if configured, otherwise use default
    excluded = state.get("excluded_channel_ids", [933812975297527818])
    # Ensure it's a list
    if not isinstance(excluded, list):
        return [933812975297527818]
    return excluded

def get_quiz_min_discord_posts() -> int:
    """Get minimum Discord posts required for quiz XP (alias for get_min_discord_posts for backward compatibility)."""
    return get_min_discord_posts()

def admin_or_role_only(role_names_or_callable: Union[List[str], Callable[[], List[str]]]) -> Callable:
    """Decorator to restrict commands to admins or users with specific roles.
    
    Users with Discord administrator permissions always have access.
    Otherwise, users must have at least one of the specified roles.
    
    Args:
        role_names_or_callable: Either a list of role names, or a callable that returns
                                a list of role names. If a callable, it will be called
                                at runtime to get the role names (useful for dynamic roles).
                                
    Returns:
        Decorator function that wraps the command handler
        
    Example:
        @admin_or_role_only(["manager perms"])
        async def my_command(interaction: discord.Interaction):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            # Get role names (either from list or by calling the callable)
            if callable(role_names_or_callable):
                role_names = role_names_or_callable()
                # If callable returns a string, wrap it in a list
                if isinstance(role_names, str):
                    role_names = [role_names]
            else:
                role_names = role_names_or_callable
            
            if interaction.user.guild_permissions.administrator:
                return await func(interaction, *args, **kwargs)
            
            user_roles = [role.name for role in interaction.user.roles]
            if any(role_name in user_roles for role_name in role_names):
                return await func(interaction, *args, **kwargs)
            
            await interaction.response.send_message(
                f"❌ You don't have permission to use this command. Required roles: {', '.join(role_names)}",
                ephemeral=True
            )
        return wrapper
    return decorator


# -------------------------------
# HTTP helpers
# -------------------------------

async def fetch_json(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=20) as resp:
            resp.raise_for_status()
            return await resp.json()


def extract_total_value(analytics_data: dict) -> float:
    """Extract total volume value from analytics data.
    
    Attempts to find the total volume in various possible field names
    and formats. Returns 0.0 if no valid value is found.
    
    Args:
        analytics_data: Dictionary containing analytics data, expected to have
                       an "analytics" key with volume information
                       
    Returns:
        Total volume as a float, or 0.0 if not found
    """
    analytics = analytics_data.get("analytics", {})
    candidates = [
        analytics.get("totalValue"),
        analytics.get("total_value"),
        analytics.get("totalValueUsd"),
        analytics.get("total_volume"),
        analytics_data.get("totalValue"),
        analytics_data.get("totalValueUsd"),
    ]

    for v in candidates:
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue

    log_or_print("warning", f"[Analytics] Could not find numeric total volume field. Keys: {list(analytics_data.keys())}")
    if isinstance(analytics, dict):
        log_or_print("debug", f"[Analytics] analytics subkeys: {list(analytics.keys())}")
    return 0.0


def extract_transaction_count(analytics_data: dict) -> Optional[int]:
    """Extract total transaction count from analytics data.
    
    Attempts to find the transaction count in various possible field names.
    Returns None if not found.
    
    Args:
        analytics_data: Dictionary containing analytics data
        
    Returns:
        Transaction count as an int, or None if not found
    """
    analytics = analytics_data.get("analytics", {})
    candidates = [
        analytics.get("transactionCount"),
        analytics.get("transaction_count"),
        analytics.get("totalTransactions"),
        analytics.get("total_transactions"),
        analytics.get("txCount"),
        analytics.get("tx_count"),
        analytics_data.get("transactionCount"),
        analytics_data.get("totalTransactions"),
        analytics_data.get("txCount"),
    ]
    
    for v in candidates:
        if v is None:
            continue
        try:
            return int(v)
        except (TypeError, ValueError):
            continue
    
    return None


def extract_biggest_transaction(leaderboard_data: dict) -> Optional[dict]:
    """Extract the biggest transaction from leaderboard data.
    
    Args:
        leaderboard_data: Dictionary containing leaderboard data with transactions list
        
    Returns:
        Transaction dict with highest AmountUSD, or None if no transactions
    """
    txs = leaderboard_data.get("transactions", [])
    if not txs:
        return None
    
    biggest = None
    biggest_amount = 0.0
    
    for tx in txs:
        try:
            amount = float(tx.get("AmountUSD", 0) or tx.get("amount_usd", 0) or 0)
            if amount > biggest_amount:
                biggest_amount = amount
                biggest = tx
        except (ValueError, TypeError):
            continue
    
    return biggest


def parse_ts(ts_str: Optional[str]) -> Optional[datetime.datetime]:
    if not ts_str:
        return None
    try:
        return datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return None


# -------------------------------
# Chain metadata lookup (DeFiLlama)
# -------------------------------

def load_chain_cache() -> Dict[int, Dict[str, str]]:
    """Load chain cache from file if it exists."""
    cache = {}
    if os.path.exists(CHAIN_CACHE_FILE):
        try:
            with open(CHAIN_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Convert string keys to int keys
                cache = {int(k): v for k, v in data.items()}
            if logger:
                logger.info(f"[ChainLookup] Loaded {len(cache)} chains from cache file")
        except Exception as e:
            if logger:
                logger.warning(f"[ChainLookup] Error loading chain cache: {e}")
    
    # Always populate manual mappings (they override file cache to ensure correct names)
    manual_count = 0
    for chain_id, name in MANUAL_CHAIN_MAPPING.items():
        slug = name.lower().replace(" ", "-")
        logo = f"{CHAIN_ICON_BASE_URL}/{slug}.png"
        # Override cache entry if it exists (manual mapping takes precedence)
        cache[chain_id] = {"name": name, "logo": logo, "slug": slug}
        manual_count += 1
    
    if logger:
        logger.info(f"[ChainLookup] Populated {manual_count} manual chain mappings (overriding cache if needed)")
    
    return cache


def save_chain_cache() -> None:
    """Save chain cache to file.
    
    Persists the current chain cache (including manual mappings) to disk
    for faster loading on next startup.
    """
    global CHAIN_CACHE
    try:
        with open(CHAIN_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(CHAIN_CACHE, f, indent=2)
    except Exception as e:
        if logger:
            logger.warning(f"[ChainLookup] Error saving chain cache: {e}")


async def fetch_chain_list() -> List[Dict[str, Any]]:
    """Fetch chain list from DeFiLlama API."""
    headers = {}
    if DEFI_LLAMA_API_KEY:
        headers["X-API-Key"] = DEFI_LLAMA_API_KEY
    
    # Try multiple possible endpoints
    endpoints = [
        DEFI_LLAMA_CHAINS_URL,  # Original endpoint
        "https://api.llama.fi/v2/chains",  # Alternative endpoint
        "https://api.llama.fi/chains",  # Fallback endpoint
    ]
    
    for endpoint in endpoints:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, headers=headers, timeout=20) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list):
                            if logger:
                                logger.info(f"[ChainLookup] Successfully fetched chain list from {endpoint}")
                            return data
                        elif isinstance(data, dict) and "chains" in data:
                            # Some APIs return wrapped in a dict
                            chains = data.get("chains", [])
                            if isinstance(chains, list):
                                if logger:
                                    logger.info(f"[ChainLookup] Successfully fetched chain list from {endpoint}")
                                return chains
                    elif resp.status == 404:
                        # Try next endpoint
                        continue
                    else:
                        if logger:
                            logger.debug(f"[ChainLookup] DeFiLlama API returned status {resp.status} for {endpoint}")
        except Exception as e:
            if logger:
                logger.debug(f"[ChainLookup] Error fetching from {endpoint}: {e}")
            continue
    
    # All endpoints failed
    if logger:
        logger.warning(f"[ChainLookup] All DeFiLlama API endpoints failed. Chain names will use IDs.")
    return []


async def get_chain_info(chain_id: int) -> Dict[str, str]:
    """Get chain name and logo URL for a given chain ID.
    
    Returns dict with 'name' and 'logo' keys.
    """
    global CHAIN_CACHE
    
    if logger:
        logger.debug(f"[ChainLookup] get_chain_info called for chain_id: {chain_id} (type: {type(chain_id)})")
        logger.debug(f"[ChainLookup] Manual mapping has {len(MANUAL_CHAIN_MAPPING)} entries: {list(MANUAL_CHAIN_MAPPING.keys())}")
        logger.debug(f"[ChainLookup] Cache has {len(CHAIN_CACHE)} entries: {list(CHAIN_CACHE.keys())[:10]}...")
    
    # Check cache first
    if chain_id in CHAIN_CACHE:
        if logger:
            logger.debug(f"[ChainLookup] Found chain {chain_id} in cache: {CHAIN_CACHE[chain_id]}")
        return CHAIN_CACHE[chain_id]
    
    # Check manual mapping first (fastest, no API call needed)
    if chain_id in MANUAL_CHAIN_MAPPING:
        name = MANUAL_CHAIN_MAPPING[chain_id]
        slug = name.lower().replace(" ", "-")
        logo = f"{CHAIN_ICON_BASE_URL}/{slug}.png"
        CHAIN_CACHE[chain_id] = {"name": name, "logo": logo, "slug": slug}
        if logger:
            logger.info(f"[ChainLookup] Found chain {chain_id} in manual mapping: {name}")
        save_chain_cache()
        return CHAIN_CACHE[chain_id]
    else:
        if logger:
            logger.debug(f"[ChainLookup] Chain {chain_id} NOT in manual mapping")
    
    # Try to fetch from API
    chains = await fetch_chain_list()
    
    for chain in chains:
        # Try multiple possible field names for chain ID
        chain_id_from_api = chain.get("chainId") or chain.get("chain_id") or chain.get("id")
        if chain_id_from_api == chain_id:
            name = chain.get("name", f"Chain {chain_id}")
            # Try to get slug from various fields
            slug = chain.get("gecko_id") or chain.get("slug") or name.lower().replace(" ", "-")
            # Clean up slug for URL
            slug = slug.replace(" ", "-").lower()
            logo = f"{CHAIN_ICON_BASE_URL}/{slug}.png"
            
            CHAIN_CACHE[chain_id] = {"name": name, "logo": logo, "slug": slug}
            if logger:
                logger.info(f"[ChainLookup] Found chain {chain_id} in API: {name}")
            save_chain_cache()
            return CHAIN_CACHE[chain_id]
    
    # Fallback: chain not found - check if we have a manual mapping (double-check)
    if chain_id in MANUAL_CHAIN_MAPPING:
        name = MANUAL_CHAIN_MAPPING[chain_id]
        slug = name.lower().replace(" ", "-")
        logo = f"{CHAIN_ICON_BASE_URL}/{slug}.png"
        CHAIN_CACHE[chain_id] = {"name": name, "logo": logo, "slug": slug}
        if logger:
            logger.warning(f"[ChainLookup] Found chain {chain_id} in manual mapping on second check: {name}")
        save_chain_cache()
        return CHAIN_CACHE[chain_id]
    
    # Final fallback: chain not found
    if logger:
        logger.warning(f"[ChainLookup] Chain {chain_id} not found in manual mapping or API. Using fallback.")
    CHAIN_CACHE[chain_id] = {"name": f"Chain {chain_id}", "logo": None, "slug": None}
    save_chain_cache()
    return CHAIN_CACHE[chain_id]


def format_chain_display(chain_id: int, chain_info: Optional[Dict[str, str]] = None, include_icon: bool = True) -> str:
    """Format chain for display with optional icon.
    
    If chain_info is provided, uses it. Otherwise returns just the chain ID.
    """
    if chain_info:
        name = chain_info.get("name", f"Chain {chain_id}")
        logo = chain_info.get("logo")
        
        if include_icon and logo:
            # Discord supports emoji-style icons, but we can also use the name with a note
            # For now, just return the name (Discord will auto-embed images in some contexts)
            return name
        else:
            return name
    else:
        return f"Chain {chain_id}"


async def get_chain_display(chain_id_str: str, include_icon: bool = True) -> str:
    """Get formatted chain display string from chain ID string.
    
    Handles conversion from string to int and async lookup.
    """
    try:
        chain_id = int(chain_id_str)
        if logger:
            logger.debug(f"[ChainLookup] Looking up chain ID: {chain_id} (from string: {chain_id_str})")
        chain_info = await get_chain_info(chain_id)
        result = format_chain_display(chain_id, chain_info, include_icon)
        if logger:
            logger.debug(f"[ChainLookup] Chain {chain_id} resolved to: {result}")
        return result
    except (ValueError, TypeError) as e:
        # If it's not a number, return as-is (might already be a name)
        if logger:
            logger.debug(f"[ChainLookup] Could not convert '{chain_id_str}' to int: {e}")
        return chain_id_str


# Chain cache will be initialized after logger is set up


# -------------------------------
# Twitter API helpers
# -------------------------------

class TwitterRateLimitError(Exception):
    """Exception raised when Twitter API rate limit is hit."""
    def __init__(self, message: str, retry_after: Optional[float] = None, status: int = 429):
        super().__init__(message)
        self.retry_after = retry_after
        self.status = status


class TwitterUsageCapExceededError(Exception):
    """Exception raised when Twitter API monthly usage cap is exceeded."""
    def __init__(self, message: str, period: Optional[str] = None, status: int = 429):
        super().__init__(message)
        self.period = period  # e.g., "Monthly"
        self.status = status

async def fetch_tweet_text_from_api(tweet_id: str) -> Optional[str]:
    """Fetch tweet text using Twitter/X API v2 (single tweet).

    Requires:
      - TWITTER_BEARER_TOKEN env var set
      - Tweet ID (not URL)
    
    Raises:
      TwitterRateLimitError: When rate limit (429) is hit
      Exception: For other API errors
    """
    # Use batch fetch for single tweet (more efficient)
    results = await fetch_tweets_batch_from_api([tweet_id])
    return results.get(tweet_id)


async def fetch_tweet_data_for_thread_detection(tweet_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Fetch tweet data including conversation_id for thread detection.
    
    Args:
        tweet_ids: List of tweet IDs to fetch
    
    Returns:
        Dictionary mapping tweet_id -> {text, conversation_id, author_id, in_reply_to_user_id}
    """
    global twitter_api_rate_limit_reset, twitter_api_remaining
    
    if not TWITTER_BEARER_TOKEN:
        log_or_print("warning", "[TweetFetch] TWITTER_BEARER_TOKEN not set; cannot fetch tweet data.")
        return {tid: {} for tid in tweet_ids}
    
    if not tweet_ids:
        return {}
    
    # Throttle API calls
    await throttle_twitter_api()
    
    # Fetch up to 100 IDs at a time
    all_results = {}
    for i in range(0, len(tweet_ids), 100):
        batch = tweet_ids[i:i+100]
        ids_str = ",".join(batch)
        url = f"https://api.x.com/2/tweets?ids={ids_str}&tweet.fields=text,conversation_id,author_id,in_reply_to_user_id"
        headers = {
            "Authorization": f"Bearer {TWITTER_BEARER_TOKEN}",
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=20) as resp:
                    # Debug: Log all rate limit related headers to diagnose the issue
                    all_headers = dict(resp.headers)
                    rate_limit_headers = {k: v for k, v in all_headers.items() if 'rate' in k.lower() or 'limit' in k.lower()}
                    if rate_limit_headers:
                        log_or_print("debug", f"[TweetFetch] Rate limit headers received: {rate_limit_headers}")
                    
                    # Update rate limit tracking from response headers
                    # Try multiple possible header name variations
                    rate_limit_reset = (
                        resp.headers.get("x-rate-limit-reset") or
                        resp.headers.get("X-Rate-Limit-Reset") or
                        resp.headers.get("x-ratelimit-reset") or
                        resp.headers.get("X-RateLimit-Reset")
                    )
                    rate_limit_limit = (
                        resp.headers.get("x-rate-limit-limit") or
                        resp.headers.get("X-Rate-Limit-Limit") or
                        resp.headers.get("x-ratelimit-limit") or
                        resp.headers.get("X-RateLimit-Limit")
                    )
                    rate_limit_remaining = (
                        resp.headers.get("x-rate-limit-remaining") or
                        resp.headers.get("X-Rate-Limit-Remaining") or
                        resp.headers.get("x-ratelimit-remaining") or
                        resp.headers.get("X-RateLimit-Remaining")
                    )
                    
                    # Debug: Log raw header values
                    if rate_limit_remaining:
                        log_or_print("debug", f"[TweetFetch] Raw x-rate-limit-remaining header value: '{rate_limit_remaining}' (type: {type(rate_limit_remaining).__name__}, length: {len(str(rate_limit_remaining))})")
                    
                    if rate_limit_reset:
                        try:
                            reset_timestamp = float(rate_limit_reset)
                            async with twitter_api_lock:
                                twitter_api_rate_limit_reset = reset_timestamp
                        except (ValueError, TypeError):
                            pass
                    
                    if rate_limit_remaining:
                        try:
                            # Strip whitespace and try to parse
                            remaining_str = str(rate_limit_remaining).strip()
                            remaining = int(remaining_str)
                            
                            # Get the limit to validate against (if available)
                            max_limit = None
                            if rate_limit_limit:
                                try:
                                    max_limit = int(str(rate_limit_limit).strip())
                                except (ValueError, TypeError):
                                    pass
                            
                            # Validate: must be non-negative and not a timestamp
                            # Timestamps are typically 10+ digits and > 1000000000 (year 2001+)
                            is_valid = remaining >= 0
                            if remaining > 1000000000:
                                # Likely a timestamp, not a rate limit value
                                if logger:
                                    logger.warning(f"[TweetFetch] Rate limit remaining value '{remaining_str}' looks like a timestamp (>{remaining}). Ignoring.")
                                is_valid = False
                            
                            if is_valid:
                                # If we have a limit header, validate remaining <= limit
                                if max_limit is not None and remaining > max_limit:
                                    if logger:
                                        logger.warning(f"[TweetFetch] Rate limit remaining ({remaining}) exceeds limit ({max_limit}). Ignoring.")
                                else:
                                    async with twitter_api_lock:
                                        twitter_api_remaining = remaining
                                    if logger and max_limit and remaining < max_limit * 0.05:  # Warn if less than 5% remaining
                                        logger.warning(f"[TweetFetch] Twitter API rate limit remaining: {remaining}/{max_limit if max_limit else '?'} requests")
                            else:
                                if logger:
                                    logger.warning(f"[TweetFetch] Invalid rate limit remaining value from API: {remaining} (raw: '{remaining_str}'). Ignoring.")
                        except (ValueError, TypeError) as e:
                            if logger:
                                logger.warning(f"[TweetFetch] Error parsing rate limit remaining '{rate_limit_remaining}': {e}")
                            pass
                    
                    if resp.status == 429:
                        # Read response body first to understand the actual error
                        error_body = ""
                        error_data = None
                        try:
                            error_body = await resp.text()
                            if error_body:
                                log_or_print("warning", f"[TweetFetch] 429 response body: {error_body}")
                                try:
                                    error_data = json.loads(error_body)
                                except (json.JSONDecodeError, ValueError):
                                    pass
                        except Exception:
                            pass
                        
                        # Check if this is a usage cap error (not a rate limit)
                        is_usage_cap = False
                        usage_cap_period = None
                        if error_data:
                            title = error_data.get("title", "").lower()
                            detail = error_data.get("detail", "").lower()
                            error_type = error_data.get("type", "").lower()
                            if ("usagecap" in title or "usage-cap" in title or 
                                "usage cap" in detail or "usage-capped" in error_type or
                                "usagecapped" in error_type):
                                is_usage_cap = True
                                usage_cap_period = error_data.get("period", "Monthly")
                                log_or_print("error", f"[TweetFetch] Twitter API monthly usage cap exceeded ({usage_cap_period}). Cannot fetch tweets until the cap resets. Error: {error_body}")
                                raise TwitterUsageCapExceededError(
                                    f"Twitter API monthly usage cap exceeded ({usage_cap_period}). "
                                    f"The account has hit its monthly limit and cannot make more requests until the billing period resets. "
                                    f"Please upgrade the plan or wait for the next billing cycle.",
                                    period=usage_cap_period,
                                    status=429
                                )
                        
                        # Rate limit hit - read remaining count from response headers first
                        # This is more accurate than the stale global variable
                        remaining_from_header = None
                        # Try both lowercase and case-sensitive versions
                        rate_limit_remaining_429 = resp.headers.get("x-rate-limit-remaining") or resp.headers.get("X-Rate-Limit-Remaining")
                        rate_limit_limit_429 = resp.headers.get("x-rate-limit-limit") or resp.headers.get("X-Rate-Limit-Limit")
                        
                        # Debug: Log all headers when we get 429
                        if logger:
                            all_headers_429 = dict(resp.headers)
                            logger.debug(f"[TweetFetch] 429 response - All headers: {all_headers_429}")
                            if rate_limit_remaining_429:
                                logger.debug(f"[TweetFetch] 429 response - Raw x-rate-limit-remaining: '{rate_limit_remaining_429}' (type: {type(rate_limit_remaining_429).__name__})")
                        
                        if rate_limit_remaining_429:
                            try:
                                # Strip whitespace
                                remaining_str_429 = str(rate_limit_remaining_429).strip()
                                remaining_from_header = int(remaining_str_429)
                                
                                # Get the limit to validate against (if available)
                                max_limit_429 = None
                                if rate_limit_limit_429:
                                    try:
                                        max_limit_429 = int(str(rate_limit_limit_429).strip())
                                    except (ValueError, TypeError):
                                        pass
                                
                                # Validate: must be non-negative and not a timestamp
                                is_valid = remaining_from_header >= 0
                                if remaining_from_header > 1000000000:
                                    # Likely a timestamp, not a rate limit value
                                    if logger:
                                        logger.warning(f"[TweetFetch] Rate limit remaining in 429 response '{remaining_str_429}' looks like a timestamp. Clearing tracking.")
                                    is_valid = False
                                
                                if is_valid:
                                    # If we have a limit header, validate remaining <= limit
                                    if max_limit_429 is not None and remaining_from_header > max_limit_429:
                                        if logger:
                                            logger.warning(f"[TweetFetch] Rate limit remaining in 429 ({remaining_from_header}) exceeds limit ({max_limit_429}). Clearing tracking.")
                                        async with twitter_api_lock:
                                            twitter_api_remaining = None
                                    else:
                                        # Update global tracking with the actual value from the 429 response
                                        async with twitter_api_lock:
                                            twitter_api_remaining = remaining_from_header
                                else:
                                    # Invalid value - clear the tracking
                                    async with twitter_api_lock:
                                        twitter_api_remaining = None
                            except (ValueError, TypeError) as e:
                                if logger:
                                    logger.warning(f"[TweetFetch] Error parsing rate limit remaining from 429 response '{rate_limit_remaining_429}': {e}")
                                pass
                        
                        # Check if this is actually a rate limit issue
                        # If remaining is very high (> 90% of limit), it's likely a different error
                        is_actual_rate_limit = True
                        if remaining_from_header is not None and max_limit_429 is not None:
                            remaining_percent = (remaining_from_header / max_limit_429) * 100
                            if remaining_percent > 90:  # More than 90% remaining
                                is_actual_rate_limit = False
                                log_or_print("warning", f"[TweetFetch] 429 received but {remaining_percent:.1f}% of rate limit remaining ({remaining_from_header}/{max_limit_429}). This is likely a different error, not a rate limit. Response body: {error_body}")
                        elif remaining_from_header is not None and remaining_from_header > 1000:
                            # If we don't have the limit but remaining is very high, it's probably not a rate limit
                            is_actual_rate_limit = False
                            log_or_print("warning", f"[TweetFetch] 429 received but remaining count is very high ({remaining_from_header}). This is likely a different error, not a rate limit. Response body: {error_body}")
                        
                        retry_after = None
                        retry_after_header = resp.headers.get("retry-after") or resp.headers.get("x-rate-limit-reset")
                        if retry_after_header:
                            try:
                                retry_after_value = float(retry_after_header)
                                if retry_after_value > 1000000000:
                                    retry_after = max(0, retry_after_value - time.time())
                                else:
                                    retry_after = retry_after_value
                            except (ValueError, TypeError):
                                pass
                        
                        # If it's not an actual rate limit, use a short retry delay instead of the full wait
                        if not is_actual_rate_limit:
                            # Use a short retry delay (5-10 seconds) instead of waiting for the full reset
                            retry_after = min(retry_after if retry_after else 10, 10)  # Cap at 10 seconds
                            log_or_print("info", f"[TweetFetch] 429 with high remaining count - using short retry delay ({retry_after:.0f}s) instead of full rate limit wait")
                        
                        error_msg = f"Twitter API rate limit exceeded (429)"
                        if retry_after:
                            error_msg += f" - retry after {retry_after:.0f} seconds"
                        # Show remaining count if it's valid
                        if remaining_from_header is not None and remaining_from_header >= 0 and remaining_from_header <= 1000000000:
                            error_msg += f" (remaining: {remaining_from_header})"
                        elif twitter_api_remaining is not None and twitter_api_remaining >= 0 and twitter_api_remaining <= 1000000000:
                            error_msg += f" (remaining: {twitter_api_remaining})"
                        log_or_print("warning", f"[TweetFetch] {error_msg}")
                        raise TwitterRateLimitError(error_msg, retry_after=retry_after, status=429)
                    
                    if resp.status != 200:
                        log_or_print("warning", f"[TweetFetch] Twitter API returned status {resp.status} for batch request")
                        continue
                    
                    data = await resp.json()
                    
                    if "data" in data and isinstance(data["data"], list):
                        for tweet in data["data"]:
                            tweet_id = str(tweet.get("id", ""))
                            all_results[tweet_id] = {
                                "text": tweet.get("text", ""),
                                "conversation_id": tweet.get("conversation_id", ""),
                                "author_id": tweet.get("author_id", ""),
                                "in_reply_to_user_id": tweet.get("in_reply_to_user_id", ""),
                            }
        except (TwitterUsageCapExceededError, TwitterRateLimitError):
            # Re-raise these errors so caller can handle them
            raise
        except Exception as e:
            log_or_print("error", f"[TweetFetch] Error fetching tweet data: {e}")
            continue
    
    return all_results


def detect_thread_tweets(tweet_ids: List[str], tweet_data: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    """Detect which tweet IDs belong to the same thread.
    
    Args:
        tweet_ids: List of tweet IDs to check
        tweet_data: Dictionary from fetch_tweet_data_for_thread_detection
    
    Returns:
        Dictionary mapping conversation_id -> list of tweet_ids in that thread
    """
    threads = {}
    
    for tweet_id in tweet_ids:
        if tweet_id not in tweet_data:
            # If we don't have data for this tweet, treat it as its own thread
            threads.setdefault(tweet_id, []).append(tweet_id)
            continue
        
        data = tweet_data[tweet_id]
        conversation_id = data.get("conversation_id", "")
        
        if conversation_id:
            threads.setdefault(conversation_id, []).append(tweet_id)
        else:
            # No conversation_id, treat as standalone
            threads.setdefault(tweet_id, []).append(tweet_id)
    
    return threads


def combine_thread_text(tweet_ids: List[str], tweet_data: Dict[str, Dict[str, Any]]) -> str:
    """Combine text from multiple tweets in a thread into a single text.
    
    Args:
        tweet_ids: List of tweet IDs in the thread (should be in order)
        tweet_data: Dictionary from fetch_tweet_data_for_thread_detection
    
    Returns:
        Combined text from all tweets
    """
    texts = []
    for tweet_id in tweet_ids:
        if tweet_id in tweet_data:
            text = tweet_data[tweet_id].get("text", "")
            if text:
                texts.append(text)
    
    # Join with double newline to separate tweets
    return "\n\n".join(texts)


async def fetch_tweets_batch_from_api(tweet_ids: List[str]) -> Dict[str, Optional[str]]:
    """Fetch multiple tweet texts using Twitter/X API v2 batch endpoint.
    
    This is much more efficient than fetching tweets one at a time.
    Rate limit: 300 requests per 15 minutes, up to 100 IDs per request.
    
    Args:
        tweet_ids: List of tweet IDs to fetch (max 100 per request)
    
    Returns:
        Dictionary mapping tweet_id -> tweet_text (or None if not found/error)
    
    Raises:
        TwitterRateLimitError: When rate limit (429) is hit
        Exception: For other API errors
    """
    global twitter_api_rate_limit_reset, twitter_api_remaining
    
    if not TWITTER_BEARER_TOKEN:
        log_or_print("warning", "[TweetFetch] TWITTER_BEARER_TOKEN not set; cannot fetch tweet text.")
        return {tid: None for tid in tweet_ids}
    
    if not tweet_ids:
        return {}
    
    # Throttle API calls to respect rate limits
    await throttle_twitter_api()
    
    # Twitter API v2 batch endpoint allows up to 100 IDs per request
    # Join IDs with comma
    # Include conversation_id to detect threads
    ids_str = ",".join(tweet_ids[:100])  # Limit to 100 IDs
    url = f"https://api.x.com/2/tweets?ids={ids_str}&tweet.fields=text,conversation_id,author_id,in_reply_to_user_id"
    headers = {
        "Authorization": f"Bearer {TWITTER_BEARER_TOKEN}",
    }
    
    results = {}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=20) as resp:
                # Debug: Log all rate limit related headers to diagnose the issue
                if logger:
                    all_headers = dict(resp.headers)
                    rate_limit_headers = {k: v for k, v in all_headers.items() if 'rate' in k.lower() or 'limit' in k.lower()}
                    if rate_limit_headers:
                        logger.debug(f"[TweetFetch] Rate limit headers received: {rate_limit_headers}")
                
                # Update rate limit tracking from response headers
                # Try both lowercase and case-sensitive versions
                rate_limit_reset = resp.headers.get("x-rate-limit-reset") or resp.headers.get("X-Rate-Limit-Reset")
                rate_limit_limit = resp.headers.get("x-rate-limit-limit") or resp.headers.get("X-Rate-Limit-Limit")
                rate_limit_remaining = resp.headers.get("x-rate-limit-remaining") or resp.headers.get("X-Rate-Limit-Remaining")
                
                # Debug: Log raw header values
                if logger and rate_limit_remaining:
                    logger.debug(f"[TweetFetch] Raw x-rate-limit-remaining header value: '{rate_limit_remaining}' (type: {type(rate_limit_remaining).__name__})")
                
                if rate_limit_reset:
                    try:
                        reset_timestamp = float(rate_limit_reset)
                        async with twitter_api_lock:
                            twitter_api_rate_limit_reset = reset_timestamp
                    except (ValueError, TypeError):
                        pass
                
                if rate_limit_remaining:
                    try:
                        # Strip whitespace and try to parse
                        remaining_str = str(rate_limit_remaining).strip()
                        remaining = int(remaining_str)
                        
                        # Get the limit to validate against (if available)
                        max_limit = None
                        if rate_limit_limit:
                            try:
                                max_limit = int(str(rate_limit_limit).strip())
                            except (ValueError, TypeError):
                                pass
                        
                        # Validate: must be non-negative and not a timestamp
                        # Timestamps are typically 10+ digits and > 1000000000 (year 2001+)
                        is_valid = remaining >= 0
                        if remaining > 1000000000:
                            # Likely a timestamp, not a rate limit value
                            if logger:
                                logger.warning(f"[TweetFetch] Rate limit remaining value '{remaining_str}' looks like a timestamp (>{remaining}). Ignoring.")
                            is_valid = False
                        
                        if is_valid:
                            # If we have a limit header, validate remaining <= limit
                            if max_limit is not None and remaining > max_limit:
                                if logger:
                                    logger.warning(f"[TweetFetch] Rate limit remaining ({remaining}) exceeds limit ({max_limit}). Ignoring.")
                            else:
                                async with twitter_api_lock:
                                    twitter_api_remaining = remaining
                                # Log rate limit status more frequently to help track usage
                                if logger and max_limit:
                                    if remaining < max_limit * 0.1:  # Warn if less than 10% remaining
                                        logger.warning(f"[TweetFetch] Twitter API rate limit remaining: {remaining}/{max_limit} requests ({remaining/max_limit*100:.1f}%)")
                                    elif remaining < max_limit * 0.2:  # Info if less than 20% remaining
                                        logger.info(f"[TweetFetch] Twitter API rate limit remaining: {remaining}/{max_limit} requests ({remaining/max_limit*100:.1f}%)")
                        else:
                            if logger:
                                logger.warning(f"[TweetFetch] Invalid rate limit remaining value from API: {remaining} (raw: '{remaining_str}'). Ignoring.")
                    except (ValueError, TypeError) as e:
                        if logger:
                            logger.warning(f"[TweetFetch] Error parsing rate limit remaining '{rate_limit_remaining}': {e}")
                        pass
                
                if resp.status == 429:
                    # Read response body first to understand the actual error
                    error_body = ""
                    error_data = None
                    try:
                        error_body = await resp.text()
                        if error_body:
                            log_or_print("warning", f"[TweetFetch] 429 response body: {error_body}")
                            try:
                                error_data = json.loads(error_body)
                            except (json.JSONDecodeError, ValueError):
                                pass
                    except Exception:
                        pass
                    
                    # Check if this is a usage cap error (not a rate limit)
                    is_usage_cap = False
                    usage_cap_period = None
                    if error_data:
                        title = error_data.get("title", "").lower()
                        detail = error_data.get("detail", "").lower()
                        error_type = error_data.get("type", "").lower()
                        if ("usagecap" in title or "usage-cap" in title or 
                            "usage cap" in detail or "usage-capped" in error_type or
                            "usagecapped" in error_type):
                            is_usage_cap = True
                            usage_cap_period = error_data.get("period", "Monthly")
                            log_or_print("error", f"[TweetFetch] Twitter API monthly usage cap exceeded ({usage_cap_period}). Cannot fetch tweets until the cap resets. Error: {error_body}")
                            raise TwitterUsageCapExceededError(
                                f"Twitter API monthly usage cap exceeded ({usage_cap_period}). "
                                f"The account has hit its monthly limit and cannot make more requests until the billing period resets. "
                                f"Please upgrade the plan or wait for the next billing cycle.",
                                period=usage_cap_period,
                                status=429
                            )
                    
                    # Rate limit hit - read remaining count from response headers first
                    # This is more accurate than the stale global variable
                    remaining_from_header = None
                    
                    # Debug: Log ALL headers when we get 429 to diagnose the issue
                    all_headers_429 = dict(resp.headers)
                    log_or_print("warning", f"[TweetFetch] 429 response received. All response headers: {all_headers_429}")
                    
                    # Try multiple possible header name variations
                    rate_limit_remaining_429 = (
                        resp.headers.get("x-rate-limit-remaining") or
                        resp.headers.get("X-Rate-Limit-Remaining") or
                        resp.headers.get("x-ratelimit-remaining") or
                        resp.headers.get("X-RateLimit-Remaining")
                    )
                    rate_limit_limit_429 = (
                        resp.headers.get("x-rate-limit-limit") or
                        resp.headers.get("X-Rate-Limit-Limit") or
                        resp.headers.get("x-ratelimit-limit") or
                        resp.headers.get("X-RateLimit-Limit")
                    )
                    
                    # Also check for any header containing "remaining" or "rate"
                    if not rate_limit_remaining_429:
                        for header_name, header_value in all_headers_429.items():
                            if 'remaining' in header_name.lower() or 'rate' in header_name.lower():
                                log_or_print("warning", f"[TweetFetch] Found potential rate limit header: '{header_name}' = '{header_value}'")
                    
                    if rate_limit_remaining_429:
                        log_or_print("warning", f"[TweetFetch] 429 response - Raw x-rate-limit-remaining: '{rate_limit_remaining_429}' (type: {type(rate_limit_remaining_429).__name__}, length: {len(str(rate_limit_remaining_429))})")
                    
                    if rate_limit_remaining_429:
                        try:
                            # Strip whitespace
                            remaining_str_429 = str(rate_limit_remaining_429).strip()
                            remaining_from_header = int(remaining_str_429)
                            
                            # Get the limit to validate against (if available)
                            max_limit_429 = None
                            if rate_limit_limit_429:
                                try:
                                    max_limit_429 = int(str(rate_limit_limit_429).strip())
                                except (ValueError, TypeError):
                                    pass
                            
                            # Validate: must be non-negative and not a timestamp
                            is_valid = remaining_from_header >= 0
                            if remaining_from_header > 1000000000:
                                # Likely a timestamp, not a rate limit value
                                if logger:
                                    logger.warning(f"[TweetFetch] Rate limit remaining in 429 response '{remaining_str_429}' looks like a timestamp. Clearing tracking.")
                                is_valid = False
                            
                            if is_valid:
                                # If we have a limit header, validate remaining <= limit
                                if max_limit_429 is not None and remaining_from_header > max_limit_429:
                                    if logger:
                                        logger.warning(f"[TweetFetch] Rate limit remaining in 429 ({remaining_from_header}) exceeds limit ({max_limit_429}). Clearing tracking.")
                                    async with twitter_api_lock:
                                        twitter_api_remaining = None
                                else:
                                    # Update global tracking with the actual value from the 429 response
                                    async with twitter_api_lock:
                                        twitter_api_remaining = remaining_from_header
                            else:
                                # Invalid value - clear the tracking
                                async with twitter_api_lock:
                                    twitter_api_remaining = None
                        except (ValueError, TypeError) as e:
                            if logger:
                                logger.warning(f"[TweetFetch] Error parsing rate limit remaining from 429 response '{rate_limit_remaining_429}': {e}")
                            pass
                    
                    # Check if this is actually a rate limit issue
                    # If remaining is very high (> 90% of limit), it's likely a different error
                    is_actual_rate_limit = True
                    if remaining_from_header is not None and max_limit_429 is not None:
                        remaining_percent = (remaining_from_header / max_limit_429) * 100
                        if remaining_percent > 90:  # More than 90% remaining
                            is_actual_rate_limit = False
                            log_or_print("warning", f"[TweetFetch] 429 received but {remaining_percent:.1f}% of rate limit remaining ({remaining_from_header}/{max_limit_429}). This is likely a different error, not a rate limit. Response body: {error_body}")
                    elif remaining_from_header is not None and remaining_from_header > 1000:
                        # If we don't have the limit but remaining is very high, it's probably not a rate limit
                        is_actual_rate_limit = False
                        log_or_print("warning", f"[TweetFetch] 429 received but remaining count is very high ({remaining_from_header}). This is likely a different error, not a rate limit. Response body: {error_body}")
                    
                    # Check for retry-after header
                    retry_after = None
                    retry_after_header = resp.headers.get("retry-after") or resp.headers.get("x-rate-limit-reset")
                    if retry_after_header:
                        try:
                            # retry-after can be seconds (int) or a timestamp
                            retry_after_value = float(retry_after_header)
                            # If it's a timestamp (large number), calculate seconds until then
                            if retry_after_value > 1000000000:  # Likely a Unix timestamp
                                retry_after = max(0, retry_after_value - time.time())
                            else:
                                retry_after = retry_after_value
                        except (ValueError, TypeError):
                            pass
                    
                    # If it's not an actual rate limit, use a short retry delay instead of the full wait
                    if not is_actual_rate_limit:
                        # Use a short retry delay (5-10 seconds) instead of waiting for the full reset
                        retry_after = min(retry_after if retry_after else 10, 10)  # Cap at 10 seconds
                        log_or_print("info", f"[TweetFetch] 429 with high remaining count - using short retry delay ({retry_after:.0f}s) instead of full rate limit wait")
                    
                    error_msg = f"Twitter API rate limit exceeded (429)"
                    if retry_after:
                        error_msg += f" - retry after {retry_after:.0f} seconds"
                    # Show remaining count if it's valid
                    if remaining_from_header is not None and remaining_from_header >= 0 and remaining_from_header <= 1000000000:
                        error_msg += f" (remaining: {remaining_from_header})"
                    elif twitter_api_remaining is not None and twitter_api_remaining >= 0 and twitter_api_remaining <= 1000000000:
                        error_msg += f" (remaining: {twitter_api_remaining})"
                    log_or_print("warning", f"[TweetFetch] {error_msg}")
                    raise TwitterRateLimitError(error_msg, retry_after=retry_after, status=429)
                
                if resp.status != 200:
                    error_body = ""
                    try:
                        error_body = await resp.text()
                        log_or_print("debug", f"[TweetFetch] Response body: {error_body}")
                    except Exception:
                        pass
                    
                    # For batch requests, 404/403 might be in the response data, not status
                    # But if the whole request fails, we'll mark all as None
                    log_or_print("warning", f"[TweetFetch] Twitter API returned status {resp.status} for batch request")
                    # Return None for all IDs
                    return {tid: None for tid in tweet_ids}
                
                data = await resp.json()
                
                # Initialize all results as None
                results = {tid: None for tid in tweet_ids}
                
                # Process successful responses
                if "data" in data and isinstance(data["data"], list):
                    for tweet in data["data"]:
                        tweet_id = str(tweet.get("id", ""))
                        text = tweet.get("text", "")
                        if tweet_id and text:
                            results[tweet_id] = text
                
                # Handle errors array (for individual tweet errors like 404/403)
                if "errors" in data and isinstance(data["errors"], list):
                    for error in data["errors"]:
                        error_id = str(error.get("resource_id", ""))
                        error_title = error.get("title", "").lower()
                        if error_id in results:
                            # 404 = not found, 403 = forbidden/private
                            if "not found" in error_title or "404" in str(error):
                                results[error_id] = None  # Already None, but log it
                                log_or_print("debug", f"[TweetFetch] Tweet {error_id} not found (404)")
                            elif "forbidden" in error_title or "403" in str(error):
                                results[error_id] = None
                                log_or_print("debug", f"[TweetFetch] Tweet {error_id} forbidden/private (403)")
                
                return results
                
    except (TwitterUsageCapExceededError, TwitterRateLimitError):
        # Re-raise these errors so caller can handle them
        raise
    except Exception as e:
        log_or_print("error", f"[TweetFetch] Error fetching tweet batch: {e}")
        raise


def detect_thread_tweets(tweet_ids: List[str], tweet_data: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    """Detect which tweet IDs belong to the same thread.
    
    Args:
        tweet_ids: List of tweet IDs to check
        tweet_data: Dictionary from fetch_tweet_data_for_thread_detection
    
    Returns:
        Dictionary mapping conversation_id -> list of tweet_ids in that thread
    """
    threads = {}
    
    for tweet_id in tweet_ids:
        if tweet_id not in tweet_data:
            # If we don't have data for this tweet, treat it as its own thread
            threads.setdefault(tweet_id, []).append(tweet_id)
            continue
        
        data = tweet_data[tweet_id]
        conversation_id = data.get("conversation_id", "")
        
        if conversation_id:
            threads.setdefault(conversation_id, []).append(tweet_id)
        else:
            # No conversation_id, treat as standalone
            threads.setdefault(tweet_id, []).append(tweet_id)
    
    return threads


def combine_thread_text(tweet_ids: List[str], tweet_data: Dict[str, Dict[str, Any]]) -> str:
    """Combine text from multiple tweets in a thread into a single text.
    
    Args:
        tweet_ids: List of tweet IDs in the thread (should be in order)
        tweet_data: Dictionary from fetch_tweet_data_for_thread_detection
    
    Returns:
        Combined text from all tweets
    """
    texts = []
    for tweet_id in tweet_ids:
        if tweet_id in tweet_data:
            text = tweet_data[tweet_id].get("text", "")
            if text:
                texts.append(text)
    
    # Join with double newline to separate tweets
    return "\n\n".join(texts)


# -------------------------------
# OpenAI grading helpers
# -------------------------------

async def grade_tweet(tweet_text: str) -> tuple[float, str]:
    """Grade a tweet using OpenAI and return (score, rationale).

    Score is expected to be between -1 and 5 in 0.5 increments, following your rubric.
    """
    if not OPENAI_API_KEY:
        log_or_print("warning", "[TweetGrade] OPENAI_API_KEY not set; cannot grade.")
        return 0.0, "Grading disabled (no OpenAI API key configured)."

    # Throttle OpenAI API calls to respect rate limits
    await throttle_openai_api()
    
    return await asyncio.to_thread(_grade_tweet_sync, tweet_text)


def _grade_tweet_sync(tweet_text: str) -> tuple[float, str]:
    """Blocking OpenAI call, run in a thread via asyncio.to_thread()."""
    if not openai_client:
        return 0.0, "OpenAI client not initialized."

    try:
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an evaluator scoring tweets about Polymer Labs and its Prove API.\n"
                        "Score only the tweet CONTENT (ignore emojis, minor formatting), from -1 to 5 in 0.5 steps.\n"
                        "-1 = disqualifying (mentions IBC/Polymer Hub/testnet campaign, or factually wrong / spam).\n"
                        "0–1.5 = irrelevant, low quality, or generic crypto noise.\n"
                        "2–3.5 = somewhat relevant, partially correct, but missing key pieces.\n"
                        "4–5 = clearly explains Polymer/Prove API/value prop with correct details and a clear CTA.\n"
                        "Return STRICT JSON: {\"score\": float, \"rationale\": \"short explanation\"}."
                    ),
                },
                {
                    "role": "user",
                    "content": tweet_text,
                },
            ],
        )

        raw = completion.choices[0].message.content
        data = json.loads(raw)
        score = float(data.get("score", 0.0))
        rationale = str(data.get("rationale", "")).strip()

        # clamp score to [-1, 5]
        if score < -1:
            score = -1.0
        if score > 5:
            score = 5.0

        return score, rationale
    except Exception as e:
        error_str = str(e)
        if logger:
            logger.error(f"[TweetGrade] Error grading tweet: {e}", exc_info=True)
        else:
            log_or_print("error", f"[TweetGrade] Error grading tweet: {e}")
        
        # Check for specific error types
        if "insufficient_quota" in error_str or "429" in error_str:
            # Quota exceeded - raise a special exception so caller knows not to mark as graded
            raise RuntimeError(
                "OpenAI API quota exceeded. Tweet grading temporarily unavailable. "
                "Please try again later or contact an admin."
            )
        elif "rate_limit" in error_str.lower():
            raise RuntimeError(
                "OpenAI API rate limit exceeded. Tweet grading temporarily unavailable. "
                "Please try again in a few moments."
            )
        else:
            # Other errors - return 0 but caller should handle appropriately
            return 0.0, f"Grading failed: {error_str[:200]}"


# -------------------------------
# Volume history & 24h change
# -------------------------------

def update_transaction_stats_history(total_value: float, transaction_count: Optional[int], biggest_tx: Optional[dict]) -> None:
    """Update transaction count and biggest transaction history.
    
    Similar to volume_history, tracks transaction count and biggest transaction over time
    to enable calculation of daily metrics.
    
    Args:
        total_value: Current total volume in USD
        transaction_count: Current total transaction count (if available from API)
        biggest_tx: Current biggest transaction dict (if available from leaderboard)
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # Track transaction count history
    count_history: List[dict] = state.get("transaction_count_history", [])
    if transaction_count is not None:
        count_history.append({
            "ts": now.isoformat(),
            "count": int(transaction_count),
            "total_value": float(total_value),
        })
    
    # Prune entries older than 2 days
    cutoff = now - datetime.timedelta(days=2)
    count_history = [e for e in count_history if parse_ts(e.get("ts")) and parse_ts(e.get("ts")) >= cutoff]
    state["transaction_count_history"] = count_history
    
    # Track biggest transaction history
    biggest_history: List[dict] = state.get("biggest_transaction_history", [])
    if biggest_tx:
        try:
            amount = float(biggest_tx.get("AmountUSD", 0) or biggest_tx.get("amount_usd", 0) or 0)
            if amount > 0:
                biggest_history.append({
                    "ts": now.isoformat(),
                    "amount": amount,
                    "token_symbol": biggest_tx.get("TokenSymbol") or biggest_tx.get("token_symbol") or "N/A",
                    "application": biggest_tx.get("Application") or biggest_tx.get("application") or "N/A",
                    "source_chain": biggest_tx.get("SourceChain") or biggest_tx.get("source_chain") or "N/A",
                    "destination_chain": biggest_tx.get("DestinationChain") or biggest_tx.get("destination_chain") or "N/A",
                })
        except (ValueError, TypeError):
            pass
    
    # Prune entries older than 2 days
    biggest_history = [e for e in biggest_history if parse_ts(e.get("ts")) and parse_ts(e.get("ts")) >= cutoff]
    state["biggest_transaction_history"] = biggest_history


def update_volume_history_and_get_change(total_value: float) -> float:
    """Update volume history and calculate 24-hour change.
    
    Adds the current total volume to the history, prunes entries older than 2 days,
    and calculates the percentage change from 24 hours ago.
    
    Args:
        total_value: Current total volume in USD
        
    Returns:
        Percentage change from 24 hours ago (as a float, e.g., 5.2 for 5.2% increase)
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    history: List[dict] = state.get("volume_history", [])

    history.append(
        {
            "ts": now.isoformat(),
            "total": float(total_value),
        }
    )

    cutoff = now - datetime.timedelta(days=2)
    pruned: List[dict] = []
    for entry in history:
        ts = parse_ts(entry.get("ts"))
        if ts is None or ts < cutoff:
            continue
        pruned.append(entry)
    history = pruned
    state["volume_history"] = history

    if len(history) < 2:
        return 0.0

    target = now - datetime.timedelta(days=1)
    closest_entry = None
    closest_delta = None

    for entry in history:
        ts = parse_ts(entry.get("ts"))
        if ts is None:
            continue
        delta = abs((ts - target).total_seconds())
        if closest_delta is None or delta < closest_delta:
            closest_delta = delta
            closest_entry = entry

    if not closest_entry:
        return 0.0

    baseline_total = float(closest_entry.get("total", 0.0))
    if baseline_total <= 0:
        return 0.0

    pct_change = (total_value - baseline_total) / baseline_total * 100.0
    return pct_change


async def update_volume_channel(total_value: float, pct_change: float) -> None:
    # Get volume channel from state, fallback to env var
    volume_channel_id = state.get("volume_channel_id") or VOLUME_CHANNEL_ID
    if not volume_channel_id:
        return
    channel = bot.get_channel(volume_channel_id)
    if channel is None:
        log_or_print("warning", "[VolumeChannel] Volume channel not found")
        return

    billions = total_value / 1_000_000_000
    sign = "+" if pct_change >= 0 else "-"
    pct_abs = abs(pct_change)

    new_name = f"Polymer Volume: ${billions:.3f}B ({sign}{pct_abs:.1f}%)"

    try:
        await channel.edit(name=new_name)
        log_or_print("info", f"[VolumeChannel] Updated channel name to: {new_name}")
    except discord.Forbidden as e:
        log_or_print("warning", f"[VolumeChannel] Missing permissions to edit channel name: {e}")
    except Exception as e:
        log_or_print("error", f"[VolumeChannel] Error updating volume channel name: {e}")


# -------------------------------
# Leaderboard task (top 10 tx)
# -------------------------------

@tasks.loop(seconds=POLL_INTERVAL)
async def check_leaderboard():
    await bot.wait_until_ready()
    
    # Check if component is enabled
    if not state.get("components_enabled", {}).get("leaderboard_checking", True):
        return
    
    # Get main metrics channel from state, fallback to env var
    channel_id = state.get("main_metrics_channel_id") or CHANNEL_ID
    channel = bot.get_channel(channel_id)
    if channel is None:
        log_or_print("warning", f"[Leaderboard] Channel not found (ID: {channel_id})")
        return

    try:
        data = await fetch_json(LEADERBOARD_URL)
    except Exception as e:
        log_or_print("error", f"[Leaderboard] Error fetching data: {e}")
        return

    txs = data.get("transactions", [])
    top10 = txs[:10]

    new_top10_ids = [tx.get("TransactionID") for tx in top10 if tx.get("TransactionID")]
    initialized_leaderboard = bool(state.get("initialized_leaderboard", False))
    announced_ids = set(state.get("announced_top10_ids", []))

    if not initialized_leaderboard:
        state["last_top10_ids"] = new_top10_ids
        baseline_ids = [tx_id for tx_id in new_top10_ids if tx_id is not None]
        state["announced_top10_ids"] = list(
            set(state.get("announced_top10_ids", [])) | set(baseline_ids)
        )
        state["initialized_leaderboard"] = True
        save_state(state)
        log_or_print("info", "[Leaderboard] Initialized baseline top10 without alerts.")
        return

    now = datetime.datetime.now(datetime.timezone.utc)
    new_entries: List[dict] = []

    for tx in top10:
        tx_id = tx.get("TransactionID")
        if not tx_id or tx_id in announced_ids:
            continue

        ts_str = tx.get("Timestamp")
        ts = parse_ts(ts_str)
        if ts is not None:
            age = now - ts
            if age > MAX_TX_AGE:
                log_or_print("debug", f"[Leaderboard] Skipping old TX {tx_id} (age {age}).")
                continue

        new_entries.append(tx)

    if not new_entries:
        log_or_print("debug", "[Leaderboard] No new (fresh) top10 entries.")
        state["last_top10_ids"] = new_top10_ids
        save_state(state)
        return

    for tx in new_entries:
        tx_id = tx.get("TransactionID")
        try:
            amount = float(tx.get("AmountUSD", 0))
        except (TypeError, ValueError):
            amount = 0.0

        # Get chain names
        src_chain_id = tx.get('SourceChain', 'N/A')
        dst_chain_id = tx.get('DestinationChain', 'N/A')
        src_chain_name = await get_chain_display(src_chain_id)
        dst_chain_name = await get_chain_display(dst_chain_id)

        msg_lines = [
            "@everyone 🚀 New Transaction Entered the Top 10!",
            f"Amount: ${amount:,.2f}",
            f"User: `{tx.get('UserAddress', 'N/A')}`",
            f"Token: {tx.get('TokenSymbol', 'N/A')} ({tx.get('TokenName', 'N/A')})",
            f"From: {src_chain_name}",
            f"To: {dst_chain_name}",
            f"Application: {tx.get('Application', 'N/A')}",
            f"Time: {tx.get('Timestamp', 'N/A')}",
            f"Transaction ID: {tx_id or 'N/A'}",
        ]
        await channel.send("\n".join(msg_lines))

        if tx_id:
            state["announced_top10_ids"].append(tx_id)

    state["last_top10_ids"] = new_top10_ids
    save_state(state)


# -------------------------------
# Volume task (milestones + channel)
# -------------------------------

@tasks.loop(seconds=POLL_INTERVAL)
async def check_volume():
    await bot.wait_until_ready()
    
    # Check if component is enabled
    if not state.get("components_enabled", {}).get("volume_checking", True):
        return
    # Get main metrics channel from state, fallback to env var
    channel_id = state.get("main_metrics_channel_id") or CHANNEL_ID
    channel = bot.get_channel(channel_id)
    if channel is None:
        log_or_print("warning", f"[Analytics] Channel not found (ID: {channel_id})")
        return

    try:
        analytics_data = await fetch_json(ANALYTICS_URL)
        leaderboard_data = await fetch_json(LEADERBOARD_URL)
    except Exception as e:
        log_or_print("error", f"[Analytics] Error fetching data: {e}")
        return

    total_value = extract_total_value(analytics_data)
    current_billions = total_value / 1_000_000_000
    
    # Extract transaction count and biggest transaction for tracking
    transaction_count = extract_transaction_count(analytics_data)
    biggest_tx = extract_biggest_transaction(leaderboard_data)
    
    # Update transaction stats history
    update_transaction_stats_history(total_value, transaction_count, biggest_tx)

    last_milestone = float(state.get("last_milestone", 0.0))
    initialized_milestone = bool(state.get("initialized_milestone", False))

    pct_change = update_volume_history_and_get_change(total_value)
    save_state(state)

    await update_volume_channel(total_value, pct_change)

    if not initialized_milestone:
        initial_milestone = math.floor(current_billions * 10) / 10.0
        state["last_milestone"] = initial_milestone
        state["initialized_milestone"] = True
        save_state(state)
        log_or_print("info", f"[Analytics] Initialized last_milestone to {initial_milestone:.1f} B based on current volume.")
        return

    if current_billions < last_milestone + 0.1:
        log_or_print("debug", "[Analytics] No new milestone reached.")
        return

    new_milestone = round(last_milestone + 0.1, 1)

    msg_lines = [
        "@everyone 🎉 Polymer Volume Milestone!",
        f"New Total Volume: ${total_value:,.0f}",
        f"We just crossed {new_milestone:.1f} Billion USD!",
    ]
    await channel.send("\n".join(msg_lines))

    state["last_milestone"] = new_milestone
    save_state(state)


# -------------------------------
# Metrics-based quiz generation
# -------------------------------

async def generate_metrics_quiz_questions(num_questions: int = 3) -> List[Dict[str, str]]:
    """Generate quiz questions based on current Polymer metrics.
    
    Returns list of question dicts with: question, option_a, option_b, option_c, option_d, correct
    """
    custom_questions = load_custom_metrics_quiz_questions()
    custom_sample: List[Dict[str, str]] = []
    if custom_questions:
        max_custom = min(len(custom_questions), num_questions)
        if max_custom > 0:
            custom_count = random.randint(1, max_custom)
            custom_sample = random.sample(custom_questions, custom_count)

    remaining = max(0, num_questions - len(custom_sample))
    if remaining == 0:
        random.shuffle(custom_sample)
        return custom_sample[:num_questions]
    ai_questions: List[Dict[str, str]] = []

    if not openai_client:
        log_or_print("warning", "[MetricsQuiz] OpenAI client not initialized")
        if custom_sample:
            random.shuffle(custom_sample)
            return custom_sample[:num_questions]
        return []
    
    try:
        # Fetch current metrics
        try:
            analytics_data, leaderboard_data = await fetch_metrics_for_quiz()
        except Exception as fetch_error:
            if logger:
                logger.warning(f"[MetricsQuiz] Error fetching metrics for quiz generation: {fetch_error}")
            else:
                log_or_print("warning", f"[MetricsQuiz] Error fetching metrics for quiz generation: {fetch_error}")
            # Continue with empty data - will use fallback questions
            analytics_data = {}
            leaderboard_data = {"transactions": []}
        
        total_value = extract_total_value(analytics_data) if analytics_data else 0
        current_billions = total_value / 1_000_000_000 if total_value > 0 else 0
        txs = leaderboard_data.get("transactions", []) if leaderboard_data else []
        top3 = txs[:10] if len(txs) >= 10 else txs
        
        # Prepare context for OpenAI
        metrics_context = {
            "total_volume_usd": total_value,
            "total_volume_billions": round(current_billions, 3),
            "top_transactions": []
        }
        
        for tx in top3:
            try:
                amount = float(tx.get("AmountUSD", 0))
                src_chain_id = tx.get("SourceChain", "N/A")
                dst_chain_id = tx.get("DestinationChain", "N/A")
                src_chain_name = await get_chain_display(src_chain_id)
                dst_chain_name = await get_chain_display(dst_chain_id)
                metrics_context["top_transactions"].append({
                    "amount_usd": amount,
                    "token": tx.get("TokenSymbol", "N/A"),
                    "application": tx.get("Application", "N/A"),
                    "source_chain": src_chain_name,
                    "destination_chain": dst_chain_name,
                })
            except (TypeError, ValueError):
                continue
        
        # Generate questions using OpenAI
        prompt = f"""You are creating quiz questions about Polymer blockchain metrics based on real-time data.

Current Metrics Data:
- Total Volume: ${metrics_context['total_volume_usd']:,.0f} (${metrics_context['total_volume_billions']:.3f} billion)
- Top Transactions: {json.dumps(metrics_context['top_transactions'], indent=2)}

Generate {num_questions} multiple-choice questions about these metrics. Questions should:
1. Test knowledge of current Polymer network statistics
2. Be answerable from the provided metrics data
3. Have exactly 4 options (a, b, c, d)
4. Have one clearly correct answer
5. Be educational and engaging

Return ONLY valid JSON in this exact format:
{{
  "questions": [
    {{
      "question": "What is the current total volume of Polymer?",
      "option_a": "$1.5 billion",
      "option_b": "$2.0 billion",
      "option_c": "$2.5 billion",
      "option_d": "$3.0 billion",
      "correct": "a"
    }}
  ]
}}

Make sure:
- Questions are based on the actual metrics provided
- Correct answers match the data
- Options are plausible but only one is correct
- Questions are clear and test understanding of Polymer metrics"""

        completion = await asyncio.to_thread(
            openai_client.chat.completions.create,
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You are a quiz question generator for blockchain metrics. Always return valid JSON with questions array."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
        )
        
        raw = completion.choices[0].message.content
        data = json.loads(raw)
        
        for q in data.get("questions", []):
            if all(key in q for key in ["question", "option_a", "option_b", "option_c", "option_d", "correct"]):
                q["correct"] = q["correct"].strip().lower()
                if q["correct"] in ["a", "b", "c", "d"]:
                    ai_questions.append(q)
        log_or_print("info", f"[MetricsQuiz] Generated {len(ai_questions)} valid AI questions")
        
    except json.JSONDecodeError as e:
        log_or_print("warning", f"[MetricsQuiz] Failed to parse JSON response: {e}")
        ai_questions = []
    except Exception as e:
        log_or_print("warning", f"[MetricsQuiz] Error generating questions: {e}", exc_info=True)
        ai_questions = []

    combined = custom_sample + ai_questions
    
    # If we don't have enough questions, add fallback questions
    if len(combined) < num_questions:
        fallback_questions = [
            {
                "question": "What core problem does Polymer aim to solve?",
                "option_a": "Decentralized storage",
                "option_b": "Cross-chain interoperability",
                "option_c": "Stablecoin issuance",
                "option_d": "Gaming guild infrastructure",
                "correct": "b",
            },
            {
                "question": "What is Polymer's Prove API used for?",
                "option_a": "Token minting",
                "option_b": "Cross-chain message verification",
                "option_c": "NFT marketplace",
                "option_d": "DeFi lending",
                "correct": "b",
            },
            {
                "question": "Which blockchain infrastructure does Polymer focus on?",
                "option_a": "Layer 1 consensus",
                "option_b": "IBC (Inter-Blockchain Communication)",
                "option_c": "Smart contract execution",
                "option_d": "Mining pools",
                "correct": "b",
            },
        ]
        # Add fallback questions until we have enough
        needed = num_questions - len(combined)
        combined.extend(fallback_questions[:needed])
    
    if not combined:
        # Ultimate fallback - should never happen
        combined = [fallback_questions[0]]

    random.shuffle(combined)
    return combined[:num_questions]


# -------------------------------
# Status builder
# -------------------------------

async def aiohttp_gather_status():
    async with aiohttp.ClientSession() as session:
        async def fetch(url):
            async with session.get(url, timeout=20) as resp:
                resp.raise_for_status()
                return await resp.json()

        analytics_task = fetch(ANALYTICS_URL)
        leaderboard_task = fetch(LEADERBOARD_URL)
        return await asyncio.gather(analytics_task, leaderboard_task)


async def fetch_metrics_for_quiz() -> Tuple[dict, dict]:
    """Fetch analytics and leaderboard data for quiz generation."""
    return await aiohttp_gather_status()


async def build_status_text() -> Optional[str]:
    try:
        analytics_data, leaderboard_data = await aiohttp_gather_status()
    except Exception as e:
        if logger:
            logger.error(f"[Status] Error fetching data: {e}", exc_info=True)
        else:
            log_or_print("error", f"[Status] Error fetching data: {e}")
        return None

    total_value = extract_total_value(analytics_data)
    current_billions = total_value / 1_000_000_000
    last_milestone = float(state.get("last_milestone", 0.0))

    txs = leaderboard_data.get("transactions", [])
    top3 = txs[:10]
    
    # Update transaction stats history with current data
    transaction_count = extract_transaction_count(analytics_data)
    biggest_tx = extract_biggest_transaction(leaderboard_data)
    update_transaction_stats_history(total_value, transaction_count, biggest_tx)
    save_state(state)

    lines: List[str] = [
        "📊 **Polymer Daily Summary**",
        "",
    ]

    # Calculate daily volume (past 24 hours)
    now = datetime.datetime.now(datetime.timezone.utc)
    volume_24h_ago = None
    volume_history = state.get("volume_history", [])
    if volume_history:
        target_time = now - datetime.timedelta(hours=24)
        closest_entry = None
        closest_delta = None
        for entry in volume_history:
            try:
                ts_str = entry.get("ts", "")
                if ts_str:
                    ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    delta = abs((ts - target_time).total_seconds())
                    if closest_delta is None or delta < closest_delta:
                        closest_delta = delta
                        closest_entry = entry
            except (ValueError, TypeError):
                continue
        if closest_entry:
            volume_24h_ago = float(closest_entry.get("total", 0.0))
    
    daily_volume = total_value - volume_24h_ago if volume_24h_ago else None
    if daily_volume is not None and daily_volume > 0:
        lines.append(f"📈 **Total Daily Volume (24h):** ${daily_volume:,.0f}")
    elif volume_history:
        # We have history but couldn't find a 24h ago entry
        lines.append(f"📈 **Total Daily Volume (24h):** Insufficient history (need 24h of data)")
    else:
        # No history at all - bot just started
        lines.append(f"📈 **Total Daily Volume (24h):** Data will be available after 24 hours of tracking")

    # Calculate transaction count change (24h) - similar to volume calculation
    target_time = now - datetime.timedelta(hours=24)
    count_history = state.get("transaction_count_history", [])
    count_24h_ago = None
    
    if count_history:
        closest_entry = None
        closest_delta = None
        for entry in count_history:
            try:
                ts_str = entry.get("ts", "")
                if ts_str:
                    ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    delta = abs((ts - target_time).total_seconds())
                    if closest_delta is None or delta < closest_delta:
                        closest_delta = delta
                        closest_entry = entry
            except (ValueError, TypeError):
                continue
        if closest_entry:
            count_24h_ago = int(closest_entry.get("count", 0))
    
    # Get current transaction count (try from current analytics data first, then from history)
    current_count = extract_transaction_count(analytics_data)
    if current_count is None and count_history:
        # Fallback to most recent history entry
        most_recent = max(count_history, key=lambda e: parse_ts(e.get("ts")) or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc))
        current_count = int(most_recent.get("count", 0))
    
    daily_count = current_count - count_24h_ago if (current_count is not None and count_24h_ago is not None) else None
    
    # Get biggest transaction from past 24 hours using biggest_transaction_history
    cutoff_time = now - datetime.timedelta(hours=24)
    biggest_history = state.get("biggest_transaction_history", [])
    
    biggest_tx_entry = None
    biggest_amount = 0.0
    
    for entry in biggest_history:
        try:
            tx_time = parse_ts(entry.get("ts"))
            if not tx_time or tx_time < cutoff_time:
                continue
            
            amount = float(entry.get("amount", 0))
            if amount > biggest_amount:
                biggest_amount = amount
                biggest_tx_entry = entry
        except (ValueError, TypeError):
            continue
    
    # Display biggest transfer from past 24 hours
    if biggest_tx_entry:
        sym = biggest_tx_entry.get("token_symbol", "N/A")
        app = biggest_tx_entry.get("application", "N/A")
        src_chain_id = biggest_tx_entry.get("source_chain", "N/A")
        dst_chain_id = biggest_tx_entry.get("destination_chain", "N/A")
        try:
            src_chain_name = await get_chain_display(src_chain_id)
            dst_chain_name = await get_chain_display(dst_chain_id)
        except Exception:
            src_chain_name = str(src_chain_id)
            dst_chain_name = str(dst_chain_id)
        lines.append(f"🏆 **Biggest Transfer Today:** ${biggest_amount:,.2f} - {sym} via {app} ({src_chain_name} → {dst_chain_name})")
    else:
        if len(biggest_history) == 0:
            lines.append(f"🏆 **Biggest Transfer Today:** No transaction history available yet")
        else:
            lines.append(f"🏆 **Biggest Transfer Today:** No transactions found in past 24 hours")

    # Calculate average transaction size for past 24 hours using daily_volume / daily_count
    if daily_volume is not None and daily_volume > 0 and daily_count is not None and daily_count > 0:
        avg_tx_size = daily_volume / daily_count
        lines.append(f"📊 **Average Transaction Size (24h):** ${avg_tx_size:,.2f} ({daily_count:,} transactions)")
    elif daily_volume is not None and daily_volume > 0:
        # We have volume but not count - show volume only
        lines.append(f"📊 **Average Transaction Size (24h):** Calculating (transaction count not available)")
    else:
        if len(count_history) == 0:
            lines.append(f"📊 **Average Transaction Size (24h):** No transaction history available yet")
        else:
            lines.append(f"📊 **Average Transaction Size (24h):** No transactions found in past 24 hours")

    lines.append("")
    lines.append("**Overall Network Stats:**")
    lines.append(f"Total Volume: ${total_value:,.0f} ({current_billions:.3f} B)")
    lines.append(f"Last Milestone: {last_milestone:.1f} B")
    lines.append("")

    if top3:
        lines.append("Top 10 Transactions (All Time):")
        for i, tx in enumerate(top3, start=1):
            try:
                amount = float(tx.get("AmountUSD", 0))
            except (TypeError, ValueError):
                amount = 0.0
            app = tx.get("Application", "N/A")
            sym = tx.get("TokenSymbol", "N/A")
            src_chain_id = tx.get("SourceChain", "N/A")
            dst_chain_id = tx.get("DestinationChain", "N/A")
            src_chain_name = await get_chain_display(src_chain_id)
            dst_chain_name = await get_chain_display(dst_chain_id)
            lines.append(f"{i}. ${amount:,.2f} - {sym} via {app} ({src_chain_name} → {dst_chain_name})")
    else:
        lines.append("No leaderboard data available.")

    analytics_top = analytics_data.get("analytics")
    last_updated = analytics_data.get("lastUpdated")
    if isinstance(analytics_top, dict):
        last_updated = last_updated or analytics_top.get("lastUpdated")
    if last_updated:
        lines.append(f"\nDashboard last updated: {last_updated}")

    return "\n".join(lines)


# -------------------------------
# Metrics quiz auto-announcement
# -------------------------------

async def post_metrics_quiz_announcement(num_questions: int = 3) -> None:
    """Post or replace the daily metrics quiz announcement with questions visible in-channel."""
    # Use configured channel or fallback to CHANNEL_ID
    channel_id = state.get("metrics_quiz_channel_id") or CHANNEL_ID
    channel = bot.get_channel(channel_id)
    if channel is None:
        log_or_print("warning", f"[MetricsQuiz] Metrics quiz channel not found (ID: {channel_id})")
        return
    
    # Check if bot has necessary permissions
    if not isinstance(channel, discord.TextChannel):
        log_or_print("warning", f"[MetricsQuiz] Channel {channel_id} is not a text channel")
        return
    
    bot_member = channel.guild.get_member(bot.user.id)
    if bot_member:
        permissions = channel.permissions_for(bot_member)
        if not permissions.send_messages:
            log_or_print("warning", f"[MetricsQuiz] Bot missing 'Send Messages' permission in channel {channel.name} (ID: {channel_id})")
            return
        if not permissions.embed_links:
            log_or_print("warning", f"[MetricsQuiz] Bot missing 'Embed Links' permission in channel {channel.name} (ID: {channel_id})")
            return

    try:
        # Generate questions
        questions = await generate_metrics_quiz_questions(num_questions)
        if not questions:
            log_or_print("error", "[MetricsQuiz] Failed to generate questions")
            return
        
        # Delete old quiz messages if they exist
        old_message_ids = state.get("metrics_quiz_all_message_ids", [])
        if not old_message_ids:
            # Fallback to single message ID for backwards compatibility
            old_message_id = state.get("metrics_quiz_message_id")
            if old_message_id:
                old_message_ids = [old_message_id]
        
        for old_msg_id in old_message_ids:
            try:
                old_message = await channel.fetch_message(old_msg_id)
                await old_message.delete()
                log_or_print("debug", f"[MetricsQuiz] Deleted old quiz message {old_msg_id}")
            except discord.NotFound:
                pass  # Message already deleted
            except Exception as e:
                log_or_print("warning", f"[MetricsQuiz] Error deleting old message {old_msg_id}: {e}")
        
        # Header message is included in old_message_ids list

        # Create shared state for all questions
        shared_state = QuizSharedState(questions=questions, message_ids=[])
        shared_state.channel = channel
        
        # Post header message
        header_embed = discord.Embed(
            title="📊 Daily Metrics Quiz",
            description="Test your knowledge of the latest Polymer stats! Answer all questions below to complete the quiz.\n\n"
                       "💡 **How to play:**\n"
                       "• Read each question below\n"
                       "• Research the answers (check current metrics!)\n"
                       "• Click the answer buttons directly below each question\n"
                       "• You can change your answers before completing\n"
                       "• Once you answer all 3 questions, your score is calculated\n\n"
                       "*(This quiz will be available for 24 hours)*",
            color=discord.Color.blue()
        )
        header_message = await channel.send(embed=header_embed)
        header_message_id = header_message.id
        
        # Post separate message for each question with its own buttons
        message_ids = []
        for i, q in enumerate(questions):
            question_text = q.get("question", "")
            options = [
                f"**A:** {q.get('option_a', '')}",
                f"**B:** {q.get('option_b', '')}",
                f"**C:** {q.get('option_c', '')}",
                f"**D:** {q.get('option_d', '')}",
            ]
            
            # Create embed for this question
            question_embed = discord.Embed(
                title=f"Question {i+1}",
                description=f"{question_text}\n\n" + "\n".join(options),
                color=discord.Color.blue()
            )
            question_embed.set_footer(text="0 user(s) completed today • Click buttons below to answer")
            
            # Create view with buttons for this question only
            view = InChannelMetricsQuizView(shared_state=shared_state, question_id=i, question=q)
            
            # Post question message
            question_message = await channel.send(embed=question_embed, view=view)
            message_ids.append(question_message.id)
            
            # Add spacing between questions (Discord messages naturally have spacing)
            # No need to send empty messages - they're not allowed anyway
        
        # Update shared state with message IDs
        shared_state.message_ids = message_ids
        
        # Store message IDs for deletion
        state["metrics_quiz_message_id"] = header_message_id  # Store header for backwards compatibility
        state["metrics_quiz_channel_id"] = channel_id
        state["metrics_quiz_all_message_ids"] = [header_message_id] + message_ids  # Store header + all question message IDs
        save_state(state)
        
        log_or_print("info", f"[MetricsQuiz] Posted daily metrics quiz with {len(questions)} questions ({len(message_ids)} question messages)")
    except discord.Forbidden as e:
        error_msg = (
            f"[MetricsQuiz] Permission denied when posting quiz to channel {channel.name} (ID: {channel_id}).\n"
            f"Required permissions: Send Messages, Embed Links, Read Message History, Manage Messages (for deleting old quiz)\n"
            f"Error: {e}"
        )
        log_or_print("error", error_msg, exc_info=True)
    except Exception as e:
        error_msg = f"[MetricsQuiz] Error posting announcement to channel {channel.name} (ID: {channel_id}): {e}"
        log_or_print("error", error_msg, exc_info=True)


@tasks.loop(time=datetime.time(hour=23, minute=59, tzinfo=datetime.timezone.utc))
async def schedule_metrics_quiz_announcements():
    """Post daily metrics quiz at 11:59 PM UTC (after daily summary)."""
    await bot.wait_until_ready()
    
    # Check if metrics quiz is enabled
    if not state.get("components_enabled", {}).get("metrics_quiz", True):
        log_or_print("debug", "[MetricsQuiz] Metrics quiz is disabled, skipping announcement")
        return
    
    # Wait a few seconds to ensure daily summary posts first
    # This ensures the quiz is the newest message
    await asyncio.sleep(3)
    
    try:
        await post_metrics_quiz_announcement(num_questions=3)
    except Exception as e:
        log_or_print("error", f"[MetricsQuiz] Error running scheduled announcement: {e}")

# -------------------------------
# Daily summary
# -------------------------------

@tasks.loop(time=datetime.time(hour=PREDICTION_RESOLUTION_HOUR, minute=0, tzinfo=datetime.timezone.utc))
async def resolve_predictions():
    """Resolve predictions daily at the configured hour."""
    await bot.wait_until_ready()
    
    # Check if component is enabled
    if not state.get("components_enabled", {}).get("prediction_resolution", True):
        log_or_print("debug", "[Predictions] Prediction resolution is disabled, skipping")
        return
    
    log_or_print("info", f"[Predictions] Starting daily prediction resolution at {PREDICTION_RESOLUTION_HOUR}:00 UTC")
    
    try:
        ws = get_predictions_ws()
        rows = ws.get_all_values()
    except Exception as e:
        log_or_print("error", f"[Predictions] Error accessing predictions sheet: {e}")
        return
    
    if not rows or len(rows) < 2:
        log_or_print("info", "[Predictions] No predictions to resolve.")
        return
    
    # Find column indices
    header = rows[0]
    row_idx_col = None  # We'll track row index manually
    discord_id_col = 1
    discord_name_col = 2
    prediction_type_col = 3
    target_date_col = 4
    prediction_value_col = 5
    actual_value_col = 6
    resolved_col = 7
    accuracy_col = 8
    xp_awarded_col = 9
    notes_col = 10
    resolution_timestamp_col = 11
    
    for idx, col_name in enumerate(header):
        col_lower = col_name.lower()
        if "discord_id" in col_lower:
            discord_id_col = idx
        elif "discord_name" in col_lower:
            discord_name_col = idx
        elif "prediction_type" in col_lower:
            prediction_type_col = idx
        elif "target_date" in col_lower:
            target_date_col = idx
        elif "prediction_value" in col_lower:
            prediction_value_col = idx
        elif "actual_value" in col_lower:
            actual_value_col = idx
        elif "resolved" in col_lower:
            resolved_col = idx
        elif "accuracy" in col_lower:
            accuracy_col = idx
        elif "xp_awarded" in col_lower:
            xp_awarded_col = idx
        elif "notes" in col_lower:
            notes_col = idx
        elif "resolution_timestamp" in col_lower:
            resolution_timestamp_col = idx
    
    today = datetime.datetime.now(datetime.timezone.utc).date()
    resolved_count = 0
    
    # Fetch current metrics
    try:
        analytics_data, leaderboard_data = await aiohttp_gather_status()
        current_volume = extract_total_value(analytics_data) / 1_000_000_000  # Convert to billions
        current_top10 = leaderboard_data.get("transactions", [])[:10]
        current_top10_tokens = [tx.get("TokenSymbol", "").strip().upper() for tx in current_top10 if tx.get("TokenSymbol", "").strip()]
    except Exception as e:
        log_or_print("error", f"[Predictions] Error fetching current metrics: {e}")
        return
    
    # Get previous top 10 tokens from state
    previous_top10_tokens = state.get("previous_top10_tokens", [])
    
    # Process each prediction
    for row_idx, row in enumerate(rows[1:], start=2):  # Start at 2 (row 1 is header, row 2 is first data)
        if len(row) <= max(discord_id_col, target_date_col, resolved_col):
            continue
        
        # Skip if already resolved
        if len(row) > resolved_col and row[resolved_col].lower() in ["true", "yes", "1"]:
            continue
        
        # Check if this prediction is for today
        target_date_str = row[target_date_col] if len(row) > target_date_col else ""
        try:
            target_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        
        if target_date != today:
            continue
        
        # Resolve this prediction
        pred_type = row[prediction_type_col].lower() if len(row) > prediction_type_col else ""
        pred_value = row[prediction_value_col] if len(row) > prediction_value_col else ""
        discord_id = row[discord_id_col] if len(row) > discord_id_col else ""
        discord_name = row[discord_name_col] if len(row) > discord_name_col else "Unknown"
        
        accuracy = 0.0
        xp_awarded = 0
        actual_value_str = ""
        
        try:
            if pred_type == "volume":
                # Resolve volume prediction
                try:
                    predicted_volume = float(pred_value)
                except (ValueError, TypeError):
                    log_or_print("warning", f"[Predictions] Invalid volume prediction value: {pred_value}")
                    continue
                
                actual_value_str = str(current_volume)
                accuracy = calculate_volume_accuracy(predicted_volume, current_volume)
                xp_awarded = calculate_prediction_xp(accuracy, PREDICTION_VOLUME_XP_BASE)
                
            elif pred_type == "top10":
                # Resolve top10 prediction
                try:
                    predicted_data = json.loads(pred_value)
                except (json.JSONDecodeError, TypeError):
                    log_or_print("warning", f"[Predictions] Invalid top10 prediction value: {pred_value}")
                    continue
                
                actual_value_str = json.dumps([tx.get("TokenSymbol", "N/A") for tx in current_top10])
                accuracy = calculate_top10_accuracy(predicted_data, current_top10, previous_top10_tokens)
                xp_awarded = calculate_prediction_xp(accuracy, PREDICTION_TOP10_XP_BASE)
            
            else:
                log_or_print("warning", f"[Predictions] Unknown prediction type: {pred_type}")
                continue
            
            # Update the row
            resolution_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            # Update cells
            ws.update_cell(row_idx, actual_value_col + 1, actual_value_str)
            ws.update_cell(row_idx, resolved_col + 1, "TRUE")
            ws.update_cell(row_idx, accuracy_col + 1, f"{accuracy:.2%}")
            ws.update_cell(row_idx, xp_awarded_col + 1, str(xp_awarded))
            ws.update_cell(row_idx, resolution_timestamp_col + 1, resolution_ts)
            
            # Award XP if any
            if xp_awarded > 0:
                add_xp(
                    discord_id=discord_id,
                    discord_name=discord_name,
                    amount=xp_awarded,
                    source="prediction_volume" if pred_type == "volume" else "prediction_top10",
                    reference_type="prediction",
                    reference_id=f"{pred_type}_{target_date_str}",
                    notes=f"Prediction accuracy: {accuracy:.2%}",
                    bypass_cap=True,  # Predictions bypass daily caps
                )
            
            resolved_count += 1
            log_or_print("info", f"[Predictions] Resolved {pred_type} prediction for {discord_name}: {accuracy:.2%} accuracy, {xp_awarded} XP")
            
        except Exception as e:
            log_or_print("error", f"[Predictions] Error resolving prediction at row {row_idx}: {e}")
            continue
    
    log_or_print("info", f"[Predictions] Resolved {resolved_count} predictions for {today.isoformat()}")
    
    # Update state with current top 10 tokens for next day's predictions
    state["previous_top10_tokens"] = current_top10_tokens
    save_state(state)
    
    # Post announcement if there were resolved predictions
    if resolved_count > 0:
        try:
            # Get main metrics channel from state, fallback to env var
            channel_id = state.get("main_metrics_channel_id") or CHANNEL_ID
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(
                    f"🎯 **Prediction Resolution Complete!**\n\n"
                    f"Resolved **{resolved_count}** predictions for {today.isoformat()}.\n"
                    f"Check `/prediction_leaderboard` to see the results!"
                )
        except Exception as e:
            log_or_print("error", f"[Predictions] Error posting resolution announcement: {e}")


@tasks.loop(time=datetime.time(hour=23, minute=59, tzinfo=datetime.timezone.utc))
async def post_daily_leaderboard():
    """Post daily XP leaderboard to the configured channel."""
    await bot.wait_until_ready()
    
    # Check if component is enabled
    if not state.get("components_enabled", {}).get("leaderboard_checking", True):
        return
    
    # Get leaderboard channel from state, fallback to hardcoded ID if not set
    leaderboard_channel_id = state.get("leaderboard_channel_id") or 1445475021890785383
    channel = bot.get_channel(leaderboard_channel_id)
    if channel is None:
        log_or_print("warning", f"[DailyLeaderboard] Channel {leaderboard_channel_id} not found")
        return
    
    try:
        # Delete previous leaderboard post if it exists
        previous_message_id = state.get("daily_leaderboard_message_id")
        if previous_message_id:
            try:
                previous_message = await channel.fetch_message(previous_message_id)
                await previous_message.delete()
                if logger:
                    logger.info(f"[DailyLeaderboard] Deleted previous leaderboard message {previous_message_id}")
            except discord.NotFound:
                # Message already deleted or doesn't exist
                pass
            except Exception as e:
                if logger:
                    logger.warning(f"[DailyLeaderboard] Error deleting previous leaderboard message: {e}")
                else:
                    log_or_print("warning", f"[DailyLeaderboard] Error deleting previous leaderboard message: {e}")
        
        lb = get_leaderboard(limit=25)
        if not lb:
            log_or_print("warning", "[DailyLeaderboard] No XP data available")
            return
        
        lines = ["🏅 **Polymer XP Leaderboard (Top 25)**", ""]
        for i, entry in enumerate(lb, start=1):
            name = entry["discord_name"] or f"<@{entry['discord_id']}>"
            xp = entry["total_xp"]
            lines.append(f"{i}. {name} — **{xp} XP**")
        
        message = await channel.send("\n".join(lines))
        
        # Save the new message ID to state
        state["daily_leaderboard_message_id"] = message.id
        save_state(state)
        
        log_or_print("info", f"[DailyLeaderboard] Posted daily leaderboard with {len(lb)} entries")
    except Exception as e:
        if logger:
            logger.error(f"[DailyLeaderboard] Error posting daily leaderboard: {e}", exc_info=True)
        else:
            log_or_print("error", f"[DailyLeaderboard] Error posting daily leaderboard: {e}")


@tasks.loop(time=datetime.time(hour=23, minute=59, tzinfo=datetime.timezone.utc))
async def daily_summary():
    await bot.wait_until_ready()
    
    # Check if component is enabled
    if not state.get("components_enabled", {}).get("daily_summary", True):
        return
    
    # Get main metrics channel from state, fallback to env var
    channel_id = state.get("main_metrics_channel_id") or CHANNEL_ID
    channel = bot.get_channel(channel_id)
    if channel is None:
        log_or_print("warning", f"[Daily Summary] Channel not found (ID: {channel_id})")
        return

    status_text = await build_status_text()
    if status_text is None:
        log_or_print("error", "[Daily Summary] Failed to build status text")
        return

    try:
        await channel.send(content=status_text)
        log_or_print("info", "[Daily Summary] Posted daily status.")
    except discord.Forbidden as e:
        log_or_print("warning", f"[Daily Summary] Missing permissions: {e}")
    except Exception as e:
        log_or_print("error", f"[Daily Summary] Error sending daily summary: {e}")


@tasks.loop(time=datetime.time(hour=2, minute=0, tzinfo=datetime.timezone.utc))
async def auto_process_ungraded_tweets():
    """Automatically process ungraded tweets at 2am UTC daily."""
    await bot.wait_until_ready()
    
    # Check if component is enabled
    if not state.get("components_enabled", {}).get("auto_process_tweets", True):
        return
    
    log_or_print("info", "[AutoProcessTweets] Starting automatic processing of ungraded tweets...")
    
    try:
        stats = await _process_ungraded_tweets_core(check_stop_event=False, send_updates=None)
        
        log_or_print(
            "info",
            f"[AutoProcessTweets] Processing complete. "
            f"Processed: {stats['processed']}, Failed: {stats['failed']}, "
            f"Skipped: {stats['skipped']}, Total: {stats['total']}"
        )
    except Exception as e:
        log_or_print("error", f"[AutoProcessTweets] Error during automatic processing: {e}", exc_info=True)


# -------------------------------
# Quiz UI Classes
# -------------------------------

class QuizButton(discord.ui.Button):
    def __init__(self, label: str, full_label: str, button_letter: str, correct_letter: str, 
                 user_id: int, question_id: int, message: discord.Message, done_event: asyncio.Event, 
                 stop_event: Optional[asyncio.Event] = None, row: Optional[int] = None):
        safe_label = label if len(label) <= 80 else label[:77] + "..."
        super().__init__(label=safe_label, style=discord.ButtonStyle.primary, row=row)
        self.full_label = full_label
        self.button_letter = button_letter
        self.correct_letter = correct_letter
        self.user_id = user_id
        self.question_id = question_id
        self.message = message
        self.done_event = done_event
        self.stop_event = stop_event or asyncio.Event()

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ You're not in this quiz session.", ephemeral=True)
            return

        if self.stop_event.is_set():
            await interaction.response.send_message("🛑 This quiz has been stopped.", ephemeral=True)
            return

        session = bot.quiz_sessions.get(self.user_id)
        if not session:
            await interaction.response.send_message("🛑 This quiz session has ended.", ephemeral=True)
            return

        if self.question_id in session['answered']:
            await interaction.response.send_message("⏳ You've already answered this question.", ephemeral=True)
            return

        is_correct = self.button_letter == self.correct_letter

        if is_correct:
            session['score'] += 1

        session['answered'].add(self.question_id)

        response_text = "✅ Correct!" if is_correct else "❌ Incorrect."
        await interaction.response.send_message(response_text, ephemeral=True)

        # Don't delete message immediately - let it timeout naturally to reduce rate limits
        self.done_event.set()


class QuizView(discord.ui.View):
    def __init__(self, question_text: str, choices: List[str], correct_letter: str, user_id: int, 
                 question_id: int, message: discord.Message, done_event: asyncio.Event, 
                 stop_event: Optional[asyncio.Event] = None):
        super().__init__(timeout=30)
        self.question_text = question_text
        self.choices = choices
        self.correct_letter = correct_letter.strip().lower()
        self.user_id = user_id
        self.question_id = question_id
        self.message = message
        self.done_event = done_event
        self.stop_event = stop_event or asyncio.Event()

        for idx, choice in enumerate(choices):
            button_letter = ["a", "b", "c", "d"][idx]
            button = QuizButton(
                label=choice,
                full_label=choice,
                button_letter=button_letter,
                correct_letter=self.correct_letter,
                user_id=user_id,
                question_id=question_id,
                message=message,
                done_event=done_event,
                stop_event=self.stop_event,
                row=idx
            )
            self.add_item(button)

    async def on_timeout(self):
        if not self.done_event.is_set() and not self.stop_event.is_set():
            # Don't delete immediately - reduces rate limits
            self.done_event.set()
        self.stop()


class ClearBotMessagesView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="🗑️ Clear Bot Messages", style=discord.ButtonStyle.secondary)
    async def clear_dm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This button is not for you.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        messages_to_delete = []
        async for msg in interaction.channel.history(limit=200):
            if msg.author == bot.user:
                messages_to_delete.append(msg)

        deleted_count = await batch_delete_messages(messages_to_delete, batch_size=5, delay=0.7)
        await interaction.followup.send(f"🗑️ Deleted {deleted_count} bot messages in this DM.", ephemeral=True)


class StartQuizButton(discord.ui.View):
    def __init__(self, user_id: int, questions: List[Dict[str, str]], required_score: int, 
                 role_to_assign: discord.Role, qualifying_roles: List[discord.Role], 
                 stop_event: Optional[asyncio.Event] = None):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.questions = questions
        self.required_score = required_score
        self.role_to_assign = role_to_assign
        self.qualifying_roles = qualifying_roles
        self.stop_event = stop_event or asyncio.Event()

    @discord.ui.button(label="Start Quiz", style=discord.ButtonStyle.success, row=0)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This button is not for you.", ephemeral=True)
            return

        # Check if this is a Polymer University quiz (has a role to assign that's not the default role)
        # Even if interaction.guild is None (in DMs), we can check the role's guild attribute
        is_polymer_university_quiz = False
        if self.role_to_assign is not None:
            # Get guild from role or interaction
            guild = self.role_to_assign.guild if hasattr(self.role_to_assign, 'guild') else (interaction.guild if interaction.guild else None)
            if guild:
                # Check if role is not the default role (@everyone)
                is_polymer_university_quiz = self.role_to_assign != guild.default_role
            else:
                # If we can't determine the guild, assume it's a Polymer University quiz if role exists
                # (default role wouldn't typically be assigned through quizzes)
                is_polymer_university_quiz = True
        
        if is_polymer_university_quiz:
            # For Polymer University quizzes: check if user already has the role
            # Get guild from role_to_assign (roles always have a guild attribute)
            if self.role_to_assign and self.role_to_assign.guild:
                guild = self.role_to_assign.guild
            elif interaction.guild:
                guild = interaction.guild
            else:
                guild = None
            member = guild.get_member(self.user_id) if guild else None
            if not member and guild:
                # If get_member returns None, try fetching the member (might not be cached)
                try:
                    member = await guild.fetch_member(self.user_id)
                except (discord.NotFound, discord.HTTPException):
                    member = None
            
            if member and self.role_to_assign in member.roles:
                await interaction.response.send_message(
                    f"❌ **Quiz Already Completed**\n\n"
                    f"You already have the **{self.role_to_assign.name}** role, which means you've already completed this quiz.\n"
                    f"💡 Each Polymer University quiz can only be completed once.",
                    ephemeral=True
                )
                return
            
            # Check if user has already completed a Polymer University quiz today
            if has_passed_quiz_today(interaction.user.id, quiz_type="university"):
                await interaction.response.send_message(
                    "⚠️ **Quiz Limit Reached**\n\n"
                    "You've already completed a Polymer University quiz today and earned XP.\n"
                    "💡 You can only earn XP from one Polymer University quiz per day.\n"
                    "🕐 Daily limit resets at 11:59 PM UTC.\n\n"
                    "You can attempt another Polymer University quiz tomorrow!",
                    ephemeral=True
                )
                return
        else:
            # For daily metrics quizzes: check if user has already passed a metrics quiz today
            if has_passed_quiz_today(interaction.user.id, quiz_type="metrics"):
                await interaction.response.send_message(
                    "⚠️ **Quiz Limit Reached**\n\n"
                    "You've already passed a quiz today and earned XP.\n"
                    "💡 You can only earn XP from the first quiz you pass each day.\n"
                    "🕐 Daily limit resets at 11:59 PM UTC.\n\n"
                    "You can attempt quizzes again tomorrow!",
                    ephemeral=True
                )
                return

        await interaction.response.defer(ephemeral=True)
        bot.quiz_sessions[self.user_id] = {'score': 0, 'answered': set(), 'stopped': False}

        dm_channel = interaction.channel
        sent_messages = []

        for i, q in enumerate(self.questions):
            if self.stop_event.is_set() or bot.quiz_sessions.get(self.user_id, {}).get('stopped', False):
                async with thread_semaphore:
                    msg = await dm_channel.send("🛑 Quiz has been stopped.")
                sent_messages.append(msg)
                break

            # Countdown
            try:
                async with thread_semaphore:
                    countdown_msg = await dm_channel.send(f"⏳ Question {i+1} begins in 3...")
                sent_messages.append(countdown_msg)
                await asyncio.sleep(1)
                await countdown_msg.edit(content="2...")
                await asyncio.sleep(1)
                await countdown_msg.edit(content="1...")
                await asyncio.sleep(1)
                await safe_delete_message(countdown_msg, delay=0)
            except Exception as e:
                log_or_print("warning", f"[Quiz] Error in countdown: {e}")
                continue

            # Send Question
            embed = discord.Embed(title=q["question"], color=discord.Color.purple())
            choices = [q["option_a"], q["option_b"], q["option_c"], q["option_d"]]
            correct_letter = q["correct"].strip().lower()
            done_event = asyncio.Event()

            try:
                async with thread_semaphore:
                    msg = await dm_channel.send(embed=embed)
                sent_messages.append(msg)
                view = QuizView(
                    q["question"],
                    choices,
                    correct_letter,
                    self.user_id,
                    i,
                    msg,
                    done_event,
                    stop_event=self.stop_event
                )
                await msg.edit(view=view)
            except Exception as e:
                log_or_print("error", f"[Quiz] Error sending question: {e}")
                continue

            # Wait for answer with timeout
            wait_task = asyncio.create_task(done_event.wait())
            try:
                await asyncio.wait_for(wait_task, timeout=20)
            except asyncio.TimeoutError:
                # Send warning
                try:
                    async with thread_semaphore:
                        warning_msg = await dm_channel.send("⚠️ 10 seconds left to answer...")
                    sent_messages.append(warning_msg)
                    try:
                        await asyncio.wait_for(done_event.wait(), timeout=10)
                    except asyncio.TimeoutError:
                        async with thread_semaphore:
                            timeout_msg = await dm_channel.send("⏱️ You ran out of time!")
                        sent_messages.append(timeout_msg)
                        # Don't delete question message - reduces rate limits
                except Exception as e:
                    log_or_print("warning", f"[Quiz] Error in timeout handling: {e}")

        # Clean up messages in batches to avoid rate limits
        await batch_delete_messages(sent_messages, batch_size=3, delay=1.0)

        # Post results
        session = bot.quiz_sessions.pop(self.user_id, {"score": 0, "answered": set()})
        score = session["score"]
        passed = score >= self.required_score

        # Determine if this is a Polymer University quiz (has a role to assign that's not the default role)
        # Even if interaction.guild is None (in DMs), we can check the role's guild attribute
        is_polymer_university_quiz = False
        if self.role_to_assign is not None:
            # Get guild from role or interaction
            guild = self.role_to_assign.guild if hasattr(self.role_to_assign, 'guild') else (interaction.guild if interaction.guild else None)
            if guild:
                # Check if role is not the default role (@everyone)
                is_polymer_university_quiz = self.role_to_assign != guild.default_role
            else:
                # If we can't determine the guild, assume it's a Polymer University quiz if role exists
                # (default role wouldn't typically be assigned through quizzes)
                is_polymer_university_quiz = True
        perfect_score = score == len(self.questions)

        # Check Discord post count before awarding XP (anti-bot measure)
        # Users must have at least 3 posts in Discord to earn XP from quizzes
        discord_post_count = 0
        can_earn_xp = False
        try:
            # Get guild from role_to_assign or interaction
            if self.role_to_assign and self.role_to_assign.guild:
                guild = self.role_to_assign.guild
            elif interaction.guild:
                guild = interaction.guild
            else:
                guild = None
            
            if guild:
                discord_post_count = await count_discord_messages_for_user(guild, interaction.user.id)
                min_posts_required = get_min_discord_posts()
                can_earn_xp = discord_post_count >= min_posts_required
            else:
                # If we can't determine the guild, log a warning but allow XP (fallback)
                log_or_print("warning", f"[Quiz] Could not determine guild for user {interaction.user.id}, allowing XP as fallback")
                can_earn_xp = True
        except Exception as e:
            log_or_print("error", f"[Quiz] Error checking Discord post count for user {interaction.user.id}: {e}")
            # On error, allow XP (fail open to avoid blocking legitimate users)
            can_earn_xp = True
        
        # Determine Discord post check status for logging
        discord_post_check_status = "not_checked"
        if guild:
            if can_earn_xp:
                discord_post_check_status = "passed"
            else:
                discord_post_check_status = "failed"
        
        log_quiz_result(interaction.user, score, len(self.questions), passed, self.required_score, discord_post_check_status)

        # Award XP for quiz completion
        xp_amount = 0
        if is_polymer_university_quiz:
            # Polymer University quizzes: Only award XP on 100% perfect score
            if perfect_score:
                # Double-check daily limit (shouldn't happen since we block at start, but safety check)
                if has_passed_quiz_today(interaction.user.id, quiz_type="university"):
                    # This shouldn't happen since we block at start, but handle gracefully
                    xp_amount = 0
                elif not can_earn_xp:
                    # User doesn't have enough Discord posts
                    xp_amount = 0
                    min_posts_required = get_min_discord_posts()
                    log_or_print("info", f"[Quiz] User {interaction.user.id} ({interaction.user}) completed quiz but has only {discord_post_count} Discord posts (need {min_posts_required}+)")
                else:
                    xp_amount = 50  # Fixed 50 XP for Polymer University quizzes
                    try:
                        role_ref = f"quiz_{self.role_to_assign.id}"
                        success, error_msg = add_xp(
                            discord_id=interaction.user.id,
                            discord_name=str(interaction.user),
                            amount=xp_amount,
                            source="quiz_completion",
                            reference_type="quiz",
                            reference_id=role_ref,
                            notes=f"Polymer University quiz completed: {score}/{len(self.questions)}",
                            bypass_cap=True,  # Polymer University quizzes bypass daily caps
                        )
                        if not success:
                            log_or_print("error", f"[Quiz] Error awarding XP: {error_msg}")
                    except Exception as e:
                        log_or_print("error", f"[Quiz] Error awarding XP: {e}")
        else:
            # Daily metrics quizzes: Award XP based on score (existing system)
            if passed:
                # Double-check (shouldn't happen since we block at start, but safety check)
                if has_passed_quiz_today(interaction.user.id, quiz_type="metrics"):
                    # This shouldn't happen since we block at start, but handle gracefully
                    xp_amount = 0
                elif not can_earn_xp:
                    # User doesn't have enough Discord posts
                    xp_amount = 0
                    min_posts_required = get_min_discord_posts()
                    log_or_print("info", f"[Quiz] User {interaction.user.id} ({interaction.user}) passed quiz but has only {discord_post_count} Discord posts (need {min_posts_required}+)")
                else:
                    # Award XP based on score: 5 XP base + 5 XP per correct answer
                    # 0/3 = 5 XP, 1/3 = 10 XP, 2/3 = 15 XP, 3/3 = 25 XP
                    if score == 0:
                        xp_amount = 5
                    elif score == 1:
                        xp_amount = 10
                    elif score == 2:
                        xp_amount = 15
                    elif score == 3:
                        xp_amount = 25
                    else:
                        # Fallback for quizzes with different number of questions
                        xp_amount = 5 + (score * 5)

                    try:
                        # Use "metrics" as reference for daily quizzes
                        success, error_msg = add_xp(
                            discord_id=interaction.user.id,
                            discord_name=str(interaction.user),
                            amount=xp_amount,
                            source="quiz_completion",
                            reference_type="quiz",
                            reference_id="quiz_metrics",
                            notes=f"Quiz passed: {score}/{len(self.questions)}",
                        )
                        if not success:
                            log_or_print("error", f"[Quiz] Error awarding XP: {error_msg}")
                    except Exception as e:
                        log_or_print("error", f"[Quiz] Error awarding XP: {e}")

        try:
            # Get guild from role_to_assign (roles always have a guild attribute)
            # If no role, try interaction.guild as fallback
            if self.role_to_assign and self.role_to_assign.guild:
                guild = self.role_to_assign.guild
            elif interaction.guild:
                guild = interaction.guild
            else:
                guild = None
            
            member = guild.get_member(self.user_id) if guild else None
            if not member and guild:
                # If get_member returns None, try fetching the member (might not be cached)
                try:
                    member = await guild.fetch_member(self.user_id)
                except (discord.NotFound, discord.HTTPException) as e:
                    log_or_print("warning", f"[Quiz] Could not fetch member {self.user_id} from guild {guild.id}: {e}")
                    member = None
            
            if not member and guild:
                log_or_print("warning", f"[Quiz] Member {self.user_id} not found in guild {guild.id} (guild name: {guild.name})")
            
            missing_roles = [r.name for r in self.qualifying_roles if r not in (member.roles if member else [])]

            result_msg = ""
            if is_polymer_university_quiz:
                # Polymer University quiz: Only award role and XP on 100% perfect score
                if perfect_score:
                    if member:
                        if missing_roles:
                            result_msg = f"✅ You got a perfect score ({score}/{len(self.questions)})! However, you still need to complete: **{', '.join(missing_roles)}** to earn **{self.role_to_assign.name}**."
                            # Shadow ban: only mention XP if they actually earned it
                            if xp_amount > 0:
                                result_msg += f"\n🎁 You earned **{xp_amount} XP**!"
                        else:
                            try:
                                # Check bot permissions before assigning role
                                bot_member = guild.get_member(bot.user.id)
                                if not bot_member:
                                    raise RuntimeError(
                                        f"Bot member not found in guild '{guild.name}' (ID: {guild.id}). "
                                        "This may indicate a synchronization issue with Discord."
                                    )
                                
                                bot_permissions = guild.me.guild_permissions
                                if not bot_permissions.manage_roles:
                                    raise PermissionError(
                                        f"Bot is missing 'Manage Roles' permission in guild '{guild.name}'. "
                                        "Please grant this permission in server settings."
                                    )
                                
                                # Check if bot's highest role is above the role being assigned
                                bot_top_role = bot_member.top_role
                                if self.role_to_assign >= bot_top_role:
                                    raise ValueError(
                                        f"Bot's highest role '{bot_top_role.name}' must be higher than "
                                        f"the role being assigned '{self.role_to_assign.name}' in the Discord role hierarchy. "
                                        "Please adjust the role hierarchy in server settings."
                                    )
                                
                                await member.add_roles(self.role_to_assign)
                                result_msg = f"🎉 Perfect score! You earned the **{self.role_to_assign.name}** role!"
                                # Shadow ban: only mention XP if they actually earned it
                                if xp_amount > 0:
                                    result_msg += f"\n🎁 You also earned **{xp_amount} XP**!"
                            except discord.Forbidden as e:
                                error_msg = str(e)
                                log_or_print("error", f"[Quiz] Permission error assigning role {self.role_to_assign.name} (ID: {self.role_to_assign.id}) to user {self.user_id}: {error_msg}")
                                
                                # Provide helpful error message
                                if "50001" in error_msg or "Missing Access" in error_msg:
                                    result_msg = f"✅ Perfect score ({score}/{len(self.questions)})!\n⚠️ Could not assign role: Bot lacks permission or role hierarchy issue. Please contact an admin."
                                else:
                                    result_msg = f"✅ Perfect score ({score}/{len(self.questions)})!\n⚠️ Could not assign role: {error_msg}"
                                # Shadow ban: only mention XP if they actually earned it
                                if xp_amount > 0:
                                    result_msg += f"\n🎁 You earned **{xp_amount} XP**!"
                            except Exception as e:
                                error_msg = str(e)
                                log_or_print("error", f"[Quiz] Error assigning role {self.role_to_assign.name} (ID: {self.role_to_assign.id}) to user {self.user_id}: {error_msg}", exc_info=True)
                                result_msg = f"✅ Perfect score ({score}/{len(self.questions)})!\n⚠️ Could not assign role: {error_msg}"
                                # Shadow ban: only mention XP if they actually earned it
                                if xp_amount > 0:
                                    result_msg += f"\n🎁 You earned **{xp_amount} XP**!"
                    else:
                        result_msg = "⚠️ Could not assign role because you are not currently in the server."
                        # Shadow ban: only mention XP if they actually earned it
                        if xp_amount > 0:
                            result_msg += f"\n🎁 You earned **{xp_amount} XP**!"
                elif passed:
                    # Passed but not perfect - no role or XP
                    result_msg = f"✅ You passed with {score}/{len(self.questions)}, but you need a perfect score (100%) to earn the role and XP.\n💡 Try again to get all questions correct!"
                else:
                    result_msg = f"❌ You did not pass ({score}/{len(self.questions)}). You need {self.required_score} correct answers to pass. Please review and try again."
            else:
                # Daily metrics quiz: Award XP based on passing (existing system)
                if passed:
                    # XP should have been awarded (or blocked at start), so just show results
                    if member:
                        # Only try to assign role if it's not @everyone (default_role)
                        if self.role_to_assign and self.role_to_assign != member.guild.default_role:
                            if missing_roles:
                                result_msg = f"✅ You passed with {score}/{len(self.questions)}! However, you still need to complete: **{', '.join(missing_roles)}** to earn **{self.role_to_assign.name}**."
                                # Shadow ban: only mention XP if they actually earned it
                                if xp_amount > 0:
                                    result_msg += f"\n🎁 You earned **{xp_amount} XP**!"
                            else:
                                try:
                                    # Check bot permissions before assigning role
                                    bot_member = guild.get_member(bot.user.id)
                                    if not bot_member:
                                        raise RuntimeError(
                                            f"Bot member not found in guild '{guild.name}' (ID: {guild.id}). "
                                            "This may indicate a synchronization issue with Discord."
                                        )
                                    
                                    bot_permissions = guild.me.guild_permissions
                                    if not bot_permissions.manage_roles:
                                        raise PermissionError(
                                            f"Bot is missing 'Manage Roles' permission in guild '{guild.name}'. "
                                            "Please grant this permission in server settings."
                                        )
                                    
                                    # Check if bot's highest role is above the role being assigned
                                    bot_top_role = bot_member.top_role
                                    if self.role_to_assign >= bot_top_role:
                                        raise ValueError(
                                            f"Bot's highest role '{bot_top_role.name}' must be higher than "
                                            f"the role being assigned '{self.role_to_assign.name}' in the Discord role hierarchy. "
                                            "Please adjust the role hierarchy in server settings."
                                        )
                                    
                                    await member.add_roles(self.role_to_assign)
                                    result_msg = f"🎉 Congrats, you earned the **{self.role_to_assign.name}** role!"
                                    # Shadow ban: only mention XP if they actually earned it
                                    if xp_amount > 0:
                                        result_msg += f"\n🎁 You also earned **{xp_amount} XP**!"
                                except discord.Forbidden as e:
                                    error_msg = str(e)
                                    if logger:
                                        logger.error(f"[Quiz] Permission error assigning role {self.role_to_assign.name} (ID: {self.role_to_assign.id}) to user {self.user_id}: {error_msg}")
                                    else:
                                        log_or_print("error", f"[Quiz] Permission error assigning role {self.role_to_assign.name} (ID: {self.role_to_assign.id}) to user {self.user_id}: {error_msg}")
                                    
                                    # Provide helpful error message
                                    if "50001" in error_msg or "Missing Access" in error_msg:
                                        result_msg = f"✅ You passed with {score}/{len(self.questions)}!\n⚠️ Could not assign role: Bot lacks permission or role hierarchy issue. Please contact an admin."
                                    else:
                                        result_msg = f"✅ You passed with {score}/{len(self.questions)}!\n⚠️ Could not assign role: {error_msg}"
                                    # Shadow ban: only mention XP if they actually earned it
                                    if xp_amount > 0:
                                        result_msg += f"\n🎁 You earned **{xp_amount} XP**!"
                                except Exception as e:
                                    error_msg = str(e)
                                    log_or_print("error", f"[Quiz] Error assigning role {self.role_to_assign.name} (ID: {self.role_to_assign.id}) to user {self.user_id}: {error_msg}", exc_info=True)
                                    result_msg = f"✅ You passed with {score}/{len(self.questions)}!\n⚠️ Could not assign role: {error_msg}"
                                    # Shadow ban: only mention XP if they actually earned it
                                    if xp_amount > 0:
                                        result_msg += f"\n🎁 You earned **{xp_amount} XP**!"
                        else:
                            # No specific role to assign (metrics quiz without role)
                            result_msg = f"✅ You passed with {score}/{len(self.questions)}!"
                            # Shadow ban: only mention XP if they actually earned it
                            if xp_amount > 0:
                                result_msg += f"\n🎁 You earned **{xp_amount} XP**!"
                    else:
                        result_msg = "⚠️ Could not assign role because you are not currently in the server."
                        # Shadow ban: only mention XP if they actually earned it
                        if xp_amount > 0:
                            result_msg += f"\n🎁 You earned **{xp_amount} XP**!"
                else:
                    result_msg = f"❌ You did not pass ({score}/{len(self.questions)}). Please review and try again."

            async with thread_semaphore:
                msg = await dm_channel.send(result_msg)
            sent_messages.append(msg)

            # Post Clear Messages Button
            clear_view = ClearBotMessagesView(self.user_id)
            async with thread_semaphore:
                msg = await dm_channel.send(
                    "✅ Quiz complete. Use the button below to clear these quiz messages if you wish:",
                    view=clear_view
                )
            sent_messages.append(msg)
        except Exception as e:
            log_or_print("error", f"[Quiz] Error posting results: {e}")

    @discord.ui.button(label="Stop Quiz", style=discord.ButtonStyle.danger, row=1)
    async def stop_quiz_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This button is not for you.", ephemeral=True)
            return

        self.stop_event.set()
        await force_stop_quiz(self.user_id)
        await interaction.response.send_message("🛑 Your quiz has been stopped and cleaned up.", ephemeral=True)


class QuizTriggerButtonFull(discord.ui.View):
    def __init__(self, quiz_file: str, num_questions: int, required_score: int, role_id: int, qualifying_roles: List[discord.Role]):
        super().__init__(timeout=None)
        self.quiz_file = quiz_file
        self.num_questions = num_questions
        self.required_score = required_score
        self.role_id = role_id
        self.qualifying_roles = qualifying_roles

    @discord.ui.button(label="Take Quiz", style=discord.ButtonStyle.primary)
    async def start_quiz(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        role_to_assign = discord.utils.get(interaction.guild.roles, id=self.role_id)

        await interaction.response.defer(ephemeral=True)

        # Check if this is a Polymer University quiz (has a role to assign that's not the default role)
        # Even if interaction.guild is None (in DMs), we can check the role's guild attribute
        is_polymer_university_quiz = False
        if role_to_assign is not None:
            # Get guild from role or interaction
            guild = role_to_assign.guild if hasattr(role_to_assign, 'guild') else (interaction.guild if interaction.guild else None)
            if guild:
                # Check if role is not the default role (@everyone)
                is_polymer_university_quiz = role_to_assign != guild.default_role
            else:
                # If we can't determine the guild, assume it's a Polymer University quiz if role exists
                # (default role wouldn't typically be assigned through quizzes)
                is_polymer_university_quiz = True
        
        if is_polymer_university_quiz:
            # For Polymer University quizzes: check if user already has the role
            member = interaction.guild.get_member(user.id) if interaction.guild else None
            
            if member and role_to_assign in member.roles:
                await interaction.followup.send(
                    f"❌ **Quiz Already Completed**\n\n"
                    f"You already have the **{role_to_assign.name}** role, which means you've already completed this quiz.\n"
                    f"💡 Each Polymer University quiz can only be completed once.",
                    ephemeral=True
                )
                return
            
            # Check if user has already completed a Polymer University quiz today
            if has_passed_quiz_today(user.id, quiz_type="university"):
                await interaction.followup.send(
                    "⚠️ **Quiz Limit Reached**\n\n"
                    "You've already completed a Polymer University quiz today and earned XP.\n"
                    "💡 You can only earn XP from one Polymer University quiz per day.\n"
                    "🕐 Daily limit resets at 11:59 PM UTC.\n\n"
                    "You can attempt another Polymer University quiz tomorrow!",
                    ephemeral=True
                )
                return
        else:
            # For daily metrics quizzes: check if user has already passed a metrics quiz today
            if has_passed_quiz_today(user.id, quiz_type="metrics"):
                await interaction.followup.send(
                    "⚠️ **Quiz Limit Reached**\n\n"
                    "You've already completed the daily metrics quiz today and earned XP.\n"
                    "💡 You can only earn XP from the daily quiz once per day.\n"
                    "🕐 Daily limit resets at 11:59 PM UTC.\n\n"
                    "You can attempt the daily quiz again tomorrow!",
                    ephemeral=True
                )
                return

        if not can_send_dm():
            await interaction.followup.send(
                "🚦 The quiz bot is currently busy. Please try again in a few minutes.",
                ephemeral=True
            )
            return

        # Load questions
        try:
            with open(self.quiz_file, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                questions = list(reader)

            required_columns = {"question", "option_a", "option_b", "option_c", "option_d", "correct"}
            if not required_columns.issubset(reader.fieldnames):
                missing = required_columns - set(reader.fieldnames or [])
                raise ValueError(
                    f"Quiz CSV file '{self.quiz_file}' is missing required columns: {', '.join(sorted(missing))}. "
                    f"Found columns: {', '.join(reader.fieldnames or [])}. "
                    "Please check the CSV file format."
                )
        except Exception as e:
            await interaction.followup.send(f"⚠️ Could not start quiz: {e}", ephemeral=True)
            return

        selected = random.sample(questions, min(self.num_questions, len(questions)))

        try:
            dm_channel = await user.create_dm()
            register_dm_send()
            async with thread_semaphore:
                await dm_channel.send("✅ Your quiz is starting here in your DMs. Let's begin!")

            async with thread_semaphore:
                await dm_channel.send(
                    f"{user.mention} 🎯 Click below to begin your quiz:",
                    view=StartQuizButton(
                        user_id=user.id,
                        questions=selected,
                        required_score=self.required_score,
                        role_to_assign=role_to_assign,
                        qualifying_roles=self.qualifying_roles
                    )
                )

            await interaction.followup.send("📩 Quiz has been sent to your DMs!", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Cannot send you a DM. Please enable DMs from server members and try again.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"⚠️ Failed to send quiz: {e}", ephemeral=True)


class QuizSharedState:
    """Shared state for quiz across multiple messages."""
    def __init__(self, questions: List[Dict[str, str]], message_ids: List[int]):
        self.questions = questions
        self.message_ids = message_ids  # List of message IDs for all question messages
        self.user_answers: Dict[int, Dict[int, str]] = {}  # user_id -> {question_id: answer}
        self.completed_users: set = set()  # Track who has completed
        self.channel = None  # Will be set after messages are sent


#
# Metrics quiz rate limiting / caching
#

# Cooldown between button presses per user (seconds)
METRICS_QUIZ_INTERACTION_COOLDOWN_SECONDS = 3

# TTL for caching has_passed_quiz_today results per user/quiz type (seconds)
METRICS_QUIZ_PASS_CHECK_TTL_SECONDS = 60

# In-memory per-process caches (safe to lose on restart)
_metrics_quiz_last_interaction: Dict[int, float] = {}
_metrics_quiz_last_pass_check: Dict[tuple[int, str | None], tuple[float, bool]] = {}


def has_passed_quiz_today_cached(discord_id: int | str, quiz_type: Optional[str] = None) -> bool:
    """Cached wrapper around has_passed_quiz_today to reduce Google Sheets reads.

    Caches results per (user, quiz_type) for a short TTL so repeated button presses
    don't hammer the Sheets API.
    """
    key = (int(discord_id), quiz_type)
    now = time.time()

    cached = _metrics_quiz_last_pass_check.get(key)
    if cached is not None:
        ts, value = cached
        if now - ts < METRICS_QUIZ_PASS_CHECK_TTL_SECONDS:
            return value

    value = has_passed_quiz_today(discord_id, quiz_type=quiz_type)
    _metrics_quiz_last_pass_check[key] = (now, value)
    return value


class InChannelMetricsQuizView(discord.ui.View):
    """In-channel quiz view for a single question with its answer buttons."""
    def __init__(self, shared_state: QuizSharedState, question_id: int, question: Dict[str, str]):
        super().__init__(timeout=None)  # No timeout - quiz stays active
        self.shared_state = shared_state
        self.question_id = question_id
        self.question = question
        
        # Add 4 answer buttons for this question only
        for opt_letter in ['a', 'b', 'c', 'd']:
            label = f"{opt_letter.upper()}"
            button = InChannelQuizAnswerButton(
                shared_state=shared_state,
                question_id=question_id,
                answer_letter=opt_letter,
                correct_answer=question.get("correct", "").strip().lower(),
                label=label,
                row=0  # All buttons on same row for this question
            )
            self.add_item(button)
    
    def has_user_completed(self, user_id: int) -> bool:
        """Check if user has completed the quiz."""
        return user_id in self.shared_state.completed_users
    
    def get_user_answers(self, user_id: int) -> Dict[int, str]:
        """Get user's answers."""
        return self.shared_state.user_answers.get(user_id, {})
    
    def set_user_answer(self, user_id: int, question_id: int, answer: str):
        """Set user's answer for a question."""
        if user_id not in self.shared_state.user_answers:
            self.shared_state.user_answers[user_id] = {}
        self.shared_state.user_answers[user_id][question_id] = answer
    
    def mark_user_completed(self, user_id: int):
        """Mark user as having completed the quiz."""
        self.shared_state.completed_users.add(user_id)
    
    def calculate_score(self, user_id: int) -> int:
        """Calculate user's score."""
        answers = self.shared_state.user_answers.get(user_id, {})
        score = 0
        for q_idx, q in enumerate(self.shared_state.questions):
            user_answer = answers.get(q_idx, "").lower()
            correct_answer = q.get("correct", "").strip().lower()
            if user_answer == correct_answer:
                score += 1
        return score
    
    def get_completion_count(self) -> int:
        """Get number of users who completed the quiz."""
        return len(self.shared_state.completed_users)
    
    async def update_all_footers(self):
        """Update footers on all question messages."""
        if not self.shared_state.channel:
            return
        
        completion_count = self.get_completion_count()
        footer_text = f"{completion_count} user(s) completed today • Click buttons to answer"
        
        for msg_id in self.shared_state.message_ids:
            try:
                msg = await self.shared_state.channel.fetch_message(msg_id)
                if msg.embeds:
                    embed = msg.embeds[0]
                    embed.set_footer(text=footer_text)
                    await msg.edit(embed=embed, view=msg.view)
            except (discord.NotFound, discord.Forbidden, Exception) as e:
                # Message might be deleted or we don't have permission
                if logger:
                    logger.debug(f"[MetricsQuiz] Could not update footer for message {msg_id}: {e}")


class InChannelQuizAnswerButton(discord.ui.Button):
    """Button for answering a quiz question in-channel."""
    def __init__(self, shared_state: QuizSharedState, question_id: int, answer_letter: str, correct_answer: str, label: str, row: int):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, row=row)
        self.shared_state = shared_state
        self.question_id = question_id
        self.answer_letter = answer_letter
        self.correct_answer = correct_answer
    
    async def callback(self, interaction: discord.Interaction):
        try:
            # Basic per-user cooldown to avoid spam / bot hammering
            user_id = interaction.user.id
            now = time.time()
            last_ts = _metrics_quiz_last_interaction.get(user_id)
            if last_ts is not None and now - last_ts < METRICS_QUIZ_INTERACTION_COOLDOWN_SECONDS:
                # Silently ignore rapid repeat clicks – interaction will just noop
                return
            _metrics_quiz_last_interaction[user_id] = now

            # Defer response first to avoid timeout. If Discord says the interaction
            # is unknown (expired/already acknowledged), just stop quietly.
            try:
                await interaction.response.defer(ephemeral=True)
            except discord.NotFound:
                if logger:
                    logger.debug("[MetricsQuiz] Interaction already invalid when deferring (Unknown interaction)")
                return
            
            # Get the view from the message
            message = interaction.message
            if not message:
                await interaction.followup.send("❌ Could not find quiz message.", ephemeral=True)
                return
            
            view = self.view
            if not isinstance(view, InChannelMetricsQuizView):
                await interaction.followup.send("❌ Invalid quiz view.", ephemeral=True)
                return
            
            if not hasattr(view, 'shared_state') or view.shared_state is None:
                await interaction.followup.send("❌ Quiz state not initialized.", ephemeral=True)
                return
            
            # Check if user already completed
            if view.has_user_completed(user_id):
                await interaction.followup.send(
                    "✅ You've already completed today's quiz! Check back tomorrow for a new one.",
                    ephemeral=True
                )
                return
            
            # Check daily limit for metrics quiz (cached to reduce Sheets reads)
            if has_passed_quiz_today_cached(user_id, quiz_type="metrics"):
                await interaction.followup.send(
                    "⚠️ **Quiz Limit Reached**\n\n"
                    "You've already completed the daily metrics quiz today and earned XP.\n"
                    "💡 You can only earn XP from the daily quiz once per day.\n"
                    "🕐 Daily limit resets at 11:59 PM UTC.",
                    ephemeral=True
                )
                return
        
            # Check if user already answered this question (allow changing answer until completion)
            user_answers = view.get_user_answers(user_id)
            already_answered_this = self.question_id in user_answers
            
            # Set user's answer (overwrites if they change their mind)
            view.set_user_answer(user_id, self.question_id, self.answer_letter)
            
            # Check if user has answered all questions
            user_answers = view.get_user_answers(user_id)
            if len(user_answers) == len(view.shared_state.questions):
                # User has answered all questions - calculate score and award XP
                # Double-check daily limit right before completion (in case they passed another quiz while answering)
                if has_passed_quiz_today_cached(user_id, quiz_type="metrics"):
                    await interaction.followup.send(
                        "⚠️ **Quiz Limit Reached**\n\n"
                        "You've already passed a quiz today and earned XP.\n"
                        "💡 You can only earn XP from the first quiz you pass each day.\n"
                        "🕐 Daily limit resets at 11:59 PM UTC.",
                        ephemeral=True
                    )
                    # Clear their answers so they can try again tomorrow
                    if user_id in view.shared_state.user_answers:
                        del view.shared_state.user_answers[user_id]
                    return
                
                view.mark_user_completed(user_id)
                score = view.calculate_score(user_id)
                total_questions = len(view.shared_state.questions)
                passed = score >= max(1, int(math.ceil(total_questions * 0.6)))  # 60% to pass
                
                # Check Discord post count before awarding XP (anti-bot measure)
                # Users must have at least 3 posts in Discord to earn XP from quizzes
                discord_post_count = 0
                can_earn_xp = False
                try:
                    guild = interaction.guild
                    if guild:
                        discord_post_count = await count_discord_messages_for_user(guild, user_id)
                        min_posts_required = get_min_discord_posts()
                        can_earn_xp = discord_post_count >= min_posts_required
                    else:
                        # If we can't determine the guild, log a warning but allow XP (fallback)
                        log_or_print("warning", f"[MetricsQuiz] Could not determine guild for user {user_id}, allowing XP as fallback")
                        can_earn_xp = True
                except Exception as e:
                    log_or_print("error", f"[MetricsQuiz] Error checking Discord post count for user {user_id}: {e}")
                    # On error, allow XP (fail open to avoid blocking legitimate users)
                    can_earn_xp = True
                
                # Award XP based on score (always, regardless of pass status)
                # 0/3 = 5 XP, 1/3 = 10 XP, 2/3 = 15 XP, 3/3 = 25 XP
                if score == 0:
                    xp_amount = 5
                elif score == 1:
                    xp_amount = 10
                elif score == 2:
                    xp_amount = 15
                elif score == 3:
                    xp_amount = 25
                else:
                    # Fallback for quizzes with different number of questions
                    xp_amount = 5 + (score * 5)
                
                # Only award XP if user has enough Discord posts
                if not can_earn_xp:
                    xp_amount = 0
                    min_posts_required = get_min_discord_posts()
                    log_or_print("info", f"[MetricsQuiz] User {user_id} ({interaction.user}) completed quiz but has only {discord_post_count} Discord posts (need {min_posts_required}+)")
                
                try:
                    if xp_amount > 0:
                        success, error_msg = add_xp(
                            discord_id=user_id,
                            discord_name=str(interaction.user),
                            amount=xp_amount,
                            source="quiz_completion",
                            reference_type="quiz",
                            reference_id="quiz_metrics",
                            notes=f"Daily metrics quiz: {score}/{total_questions}",
                        )
                        if not success:
                            xp_message = f"\n⚠️ XP not awarded: {error_msg}"
                        else:
                            xp_message = f"\n⭐️ XP Earned: **{xp_amount} XP**"
                    else:
                        # Shadow ban: don't mention XP at all if they didn't earn any
                        xp_message = ""
                except Exception as e:
                    if logger:
                        logger.error(f"[MetricsQuiz] Error awarding XP: {e}")
                    xp_message = f"\n⚠️ Error awarding XP"
                
                # Log quiz result
                # Determine Discord post check status for logging
                discord_post_check_status = "not_checked"
                if guild:
                    if can_earn_xp:
                        discord_post_check_status = "passed"
                    else:
                        discord_post_check_status = "failed"
                
                log_quiz_result(interaction.user, score, total_questions, passed, max(1, int(math.ceil(total_questions * 0.6))), discord_post_check_status)
                
                # Send completion message (shadow ban: no mention of XP if they didn't earn any)
                completion_msg = f"📝 **Quiz Complete!**\n\n🎉 Score: **{score}/{total_questions}**"
                if xp_message:
                    completion_msg += f"\n{xp_message}"
                completion_msg += "\n🚀 Check back tomorrow for the next quiz!"
                
                await interaction.followup.send(completion_msg, ephemeral=True)
                
                # Update all quiz messages to show completion count
                try:
                    await view.update_all_footers()
                except Exception as e:
                    if logger:
                        logger.warning(f"[MetricsQuiz] Error updating completion count: {e}")
            else:
                # User hasn't answered all questions yet - just confirm their answer
                change_msg = " (changed)" if already_answered_this else ""
                await interaction.followup.send(
                    f"✅ Answer recorded{change_msg}! ({len(user_answers)}/{len(view.shared_state.questions)} questions answered)\n"
                    f"💡 You can change your answer by clicking a different option.",
                    ephemeral=True
                )
        except Exception as e:
            error_msg = f"[MetricsQuiz] Error in button callback: {e}"
            log_or_print("error", error_msg, exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ An error occurred processing your answer. Please try again.",
                    ephemeral=True
                )
            except Exception:
                pass  # If followup also fails, just log it


class MetricsQuizAnnouncementView(discord.ui.View):
    def __init__(self, num_questions: int = 3):
        super().__init__(timeout=3600)
        self.num_questions = num_questions

    @discord.ui.button(label="Take Metrics Quiz", style=discord.ButtonStyle.primary)
    async def take_quiz(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await handle_metrics_quiz_request(interaction, self.num_questions)


# -------------------------------
# Slash: /polymer_status
# -------------------------------

@bot.tree.command(name="polymer_status", description="Show current Polymer dashboard stats")
async def polymer_status(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    status_text = await build_status_text()
    if status_text is None:
        await interaction.followup.send(
            "❌ Error fetching Polymer status. Check bot logs.",
            ephemeral=True,
        )
        return
    await interaction.followup.send(content=status_text, ephemeral=False)


# -------------------------------
# XP commands
# -------------------------------

@bot.tree.command(name="xp_me", description="Show your total Polymer XP")
@app_commands.describe(
    user="View another user's XP (Admin only)"
)
async def xp_me(interaction: discord.Interaction, user: Optional[discord.User] = None):
    await interaction.response.defer(ephemeral=True)
    
    # Check if user is viewing someone else's XP
    target_user = user if user else interaction.user
    is_admin = False
    
    if user and user != interaction.user:
        # Check if requester is admin
        if interaction.user.guild_permissions.administrator:
            is_admin = True
        else:
            user_roles = [role.name for role in interaction.user.roles]
            if get_admin_role_name() in user_roles:
                is_admin = True
        
        if not is_admin:
            await interaction.followup.send(
                f"❌ You don't have permission to view other users' XP.",
                ephemeral=True
            )
            return
    
    total_xp = get_total_xp(target_user.id)
    breakdown = get_xp_breakdown(target_user.id)
    
    # Get user's rank
    rank_info = get_user_rank(target_user.id)

    pu_xp = breakdown["polymer_university"]
    twitter_xp = breakdown["twitter_submissions"]
    quiz_xp = breakdown["daily_quiz"]
    other_xp = breakdown["other"]

    lines = [
        f"🧬 {target_user.mention}, you have **{total_xp} XP** in the Polymer ecosystem.",
    ]
    
    # Add rank if available
    if rank_info:
        rank = rank_info["rank"]
        total_users = rank_info["total_users"]
        lines.append(f"🏅 **Rank: #{rank}** out of {total_users} users")
        lines.append("")
    
    lines.extend([
        "📊 **XP Breakdown:**",
        f"• 🎓 Polymer University: **{pu_xp} XP**",
        f"• 🐦 Twitter submissions: **{twitter_xp} XP**",
        f"• 📅 Daily quizzes: **{quiz_xp} XP**",
        f"• ✨ Other contributions: **{other_xp} XP**",
    ])
    
    # Check if user is shadow banned BEFORE showing last tweet info
    is_shadow_banned = False
    
    # Check if handle is excluded
    handle = get_twitter_handle_for_user(target_user.id)
    if handle and is_handle_excluded(handle):
        is_shadow_banned = True
    
    # Check Discord post count (if guild is available)
    if interaction.guild and not is_shadow_banned:
        try:
            discord_post_count = await count_discord_messages_for_user(interaction.guild, target_user.id)
            min_posts_required = get_min_discord_posts()
            if discord_post_count < min_posts_required:
                is_shadow_banned = True
        except Exception:
            # If we can't check, assume not shadow banned to avoid false positives
            pass
    
    # Only show last tweet information if user is NOT shadow banned
    if not is_shadow_banned:
        last_tweet = get_last_submitted_tweet(target_user.id, str(target_user))
        if last_tweet:
            lines.append("")
            lines.append("🐦 **Last Submitted Tweet:**")
            lines.append(f"Last submitted tweet: {last_tweet['url']}")
            
            # Determine XP status
            if last_tweet['graded']:
                # Tweet was graded - show XP (even if 0)
                lines.append(f"XP earned: **{int(last_tweet['xp_awarded'])} XP**")
            else:
                # Tweet not graded yet
                lines.append(f"XP has not yet been assigned, when the app is available XP will be awarded")

    await interaction.followup.send("\n".join(lines), ephemeral=True)


@bot.tree.command(name="xp_leaderboard", description="Show the top XP leaderboard")
async def xp_leaderboard_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    lb = get_leaderboard(limit=25)
    if not lb:
        await interaction.followup.send("No XP data yet.", ephemeral=True)
        return

    lines = ["🏅 **Polymer XP Leaderboard (Top 25)**", ""]
    for i, entry in enumerate(lb, start=1):
        name = entry["discord_name"] or f"<@{entry['discord_id']}>"
        xp = entry["total_xp"]
        lines.append(f"{i}. {name} — **{xp} XP**")

    await interaction.followup.send("\n".join(lines), ephemeral=True)


@bot.tree.command(name="xp_daily_status", description="Check your daily XP progress and cap")
async def xp_daily_status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    total_xp = get_total_xp(interaction.user.id)
    daily_cap = get_daily_cap_for_user(total_xp)
    current_daily = get_daily_xp_earned(interaction.user.id, source_filter="tweet_grade")
    remaining = max(0, daily_cap - current_daily)
    
    # Determine tier
    tier_name = "New User"
    for min_xp, cap in sorted(XP_TIER_CAPS, reverse=True):
        if total_xp >= min_xp:
            tier_name = f"{min_xp}+ XP Tier"
            break
    
    lines = [
        f"📊 **Daily XP Status**",
        f"Total XP: **{total_xp} XP**",
        f"Tier: **{tier_name}**",
        f"",
        f"📈 Today's Progress:",
        f"- Earned: **{current_daily}/{daily_cap} XP**",
        f"- Remaining: **{remaining} XP**",
    ]
    
    if current_daily >= daily_cap:
        lines.append(f"\n⚠️ You've reached your daily cap! Come back tomorrow.")
    elif remaining < 50:
        lines.append(f"\n💡 Almost there! {remaining} XP remaining today.")
    else:
        lines.append(f"\n💪 Keep going! You can earn {remaining} more XP today.")
    
    await interaction.followup.send("\n".join(lines), ephemeral=True)


@bot.tree.command(name="xp_history", description="View your XP history (recent events)")
@app_commands.describe(
    limit="Number of recent events to show (default: 20, max: 50)",
    user="View another user's history (Admin only)"
)
async def xp_history(interaction: discord.Interaction, limit: int = 20, user: Optional[discord.User] = None):
    await interaction.response.defer(ephemeral=True)
    
    # Check if user is viewing someone else's history
    target_user = user if user else interaction.user
    is_admin = False
    
    if user and user != interaction.user:
        # Check if requester is admin
        if interaction.user.guild_permissions.administrator:
            is_admin = True
        else:
            user_roles = [role.name for role in interaction.user.roles]
            if get_admin_role_name() in user_roles:
                is_admin = True
        
        if not is_admin:
            await interaction.followup.send(
                f"❌ You don't have permission to view other users' XP history.",
                ephemeral=True
            )
            return
    
    # Validate limit
    limit = max(1, min(50, limit))  # Clamp between 1 and 50
    
    # Get history
    history = get_xp_history(target_user.id, limit=limit)
    
    if not history:
        await interaction.followup.send(
            f"📜 No XP history found for {target_user.mention}.",
            ephemeral=True
        )
        return
    
    # Build response
    total_xp = get_total_xp(target_user.id)
    lines = [
        f"📜 **XP History for {target_user.display_name}**",
        f"Total XP: **{total_xp} XP**",
        f"Showing last **{len(history)}** events:",
        f"",
    ]
    
    # Format events
    for i, event in enumerate(history, 1):
        timestamp_str = "Unknown date"
        if event["timestamp"]:
            try:
                # Format as relative time or date
                now = datetime.datetime.now(datetime.timezone.utc)
                delta = now - event["timestamp"]
                
                if delta.days == 0:
                    if delta.seconds < 3600:
                        minutes = delta.seconds // 60
                        timestamp_str = f"{minutes}m ago" if minutes > 0 else "Just now"
                    else:
                        hours = delta.seconds // 3600
                        timestamp_str = f"{hours}h ago"
                elif delta.days == 1:
                    timestamp_str = "Yesterday"
                elif delta.days < 7:
                    timestamp_str = f"{delta.days}d ago"
                else:
                    timestamp_str = event["timestamp"].strftime("%Y-%m-%d")
            except Exception:
                timestamp_str = "Unknown"
        
        source = event["source"] or "unknown"
        amount = event["amount"]
        notes = event["notes"] or ""
        
        # Format amount with sign
        amount_str = f"+{amount}" if amount > 0 else str(amount)
        
        # Format source name nicely
        source_display = {
            "tweet_grade": "📱 Tweet",
            "quiz_completion": "📝 Quiz",
            "admin_grant": "👑 Admin Grant",
            "admin_removal": "👑 Admin Removal",
            "grandfather_bonus": "🎁 Grandfather Bonus",
            "historical_migration": "📦 Migration",
        }.get(source, source.replace("_", " ").title())
        
        line = f"**{i}.** {amount_str} XP — {source_display} ({timestamp_str})"
        if notes and len(notes) < 60:
            line += f"\n   └ {notes}"
        lines.append(line)
    
    # Discord message limit is 2000 characters
    response = "\n".join(lines)
    if len(response) > 2000:
        # Truncate if too long
        response = response[:1950] + "\n\n... (truncated)"
    
    await interaction.followup.send(response, ephemeral=True)


# -------------------------------
# Tweet submission commands
# -------------------------------

@bot.tree.command(name="set_twitter", description="Link your Twitter/X handle to your Discord account")
async def set_twitter(interaction: discord.Interaction, handle: str):
    await interaction.response.defer(ephemeral=True)

    normalized = handle.strip()
    if normalized.startswith("@"):
        normalized = normalized[1:]
    if not normalized:
        await interaction.followup.send("❌ Please provide a valid Twitter handle.", ephemeral=True)
        return

    upsert_twitter_handle(interaction.user.id, str(interaction.user), normalized)
    await interaction.followup.send(f"✅ Your Twitter handle has been set to `@{normalized}`.", ephemeral=True)


async def process_tweet_submission_queue():
    """Background task to process tweet submissions from the queue in batches.
    
    This function processes tweets in batches of up to TWEET_QUEUE_BATCH_SIZE (100)
    to maximize API efficiency and minimize rate limit issues.
    """
    global tweet_queue_processor_running
    
    tweet_queue_processor_running = True
    log_or_print("info", "[TweetQueue] Queue processor started")
    
    while True:
        try:
            # Wait for queue items or timeout
            queue_items = []
            timeout = TWEET_QUEUE_PROCESS_INTERVAL
            
            # Collect items from queue (up to batch size)
            start_time = asyncio.get_event_loop().time()
            while len(queue_items) < TWEET_QUEUE_BATCH_SIZE:
                try:
                    # Wait for item with timeout
                    remaining_time = timeout - (asyncio.get_event_loop().time() - start_time)
                    if remaining_time <= 0:
                        break
                    
                    item = await asyncio.wait_for(
                        tweet_submission_queue.get(),
                        timeout=min(remaining_time, 5.0)  # Check every 5 seconds
                    )
                    queue_items.append(item)
                except asyncio.TimeoutError:
                    # No items available, check if we should process what we have
                    if len(queue_items) >= TWEET_QUEUE_MIN_BATCH_SIZE:
                        break
                    # Otherwise continue waiting
                    continue
            
            # Process batch if we have items
            if queue_items:
                log_or_print("info", f"[TweetQueue] Processing batch of {len(queue_items)} tweet submission(s)")
                await _process_tweet_submission_batch(queue_items)
            else:
                # No items, sleep briefly before checking again
                await asyncio.sleep(5.0)
                
        except Exception as e:
            log_or_print("error", f"[TweetQueue] Error in queue processor: {e}", exc_info=True)
            await asyncio.sleep(10.0)  # Wait before retrying


async def _process_tweet_submission_batch(submission_items: List[Dict[str, Any]]):
    """Process a batch of tweet submissions.
    
    Args:
        submission_items: List of submission dicts with keys:
            - user_id: Discord user ID
            - user_name: Discord username
            - handle: Twitter handle
            - tweet_ids: List of tweet IDs
            - tweet_id_to_url: Dict mapping tweet_id to base_url
            - interaction: Optional Discord interaction for followup
    """
    # Group all tweet IDs from all submissions
    all_tweet_ids = []
    tweet_id_to_submission = {}  # Map tweet_id to submission item
    
    for item in submission_items:
        for tweet_id in item["tweet_ids"]:
            all_tweet_ids.append(tweet_id)
            if tweet_id not in tweet_id_to_submission:
                tweet_id_to_submission[tweet_id] = []
            tweet_id_to_submission[tweet_id].append(item)
    
    if not all_tweet_ids:
        return

    # Batch fetch all tweets in a single API call
    log_or_print("info", f"[TweetQueue] Batch fetching {len(all_tweet_ids)} tweet(s) from {len(submission_items)} submission(s) in single API call")
    all_tweet_data = {}
    try:
        all_tweet_data = await retry_with_backoff(
            lambda: fetch_tweet_data_for_thread_detection(all_tweet_ids),
            max_retries=2,
            initial_delay=2.0,
        )
    except Exception as e:
        log_or_print("error", f"[TweetQueue] Error batch fetching tweet data: {e}")
        # Mark all as failed
        for item in submission_items:
            if item.get("interaction"):
                try:
                    await item["interaction"].followup.send(
                        f"⚠️ Error fetching tweet data: {str(e)[:200]}. Tweets saved for later processing.",
            ephemeral=True,
        )
                except:
                    pass
        return

    # Process each submission
    for item in submission_items:
        try:
            await _process_single_submission(item, all_tweet_data)
        except Exception as e:
            log_or_print("error", f"[TweetQueue] Error processing submission for user {item['user_id']}: {e}", exc_info=True)
            if item.get("interaction"):
                try:
                    await item["interaction"].followup.send(
                        f"⚠️ Error processing your submission: {str(e)[:200]}",
            ephemeral=True,
        )
                except:
                    pass


async def _process_single_submission(item: Dict[str, Any], all_tweet_data: Dict[str, Dict[str, Any]]):
    """Process a single user's tweet submission.
    
    This is the core processing logic extracted from submit_tweet.
    """
    user_id = item["user_id"]
    user_name = item["user_name"]
    handle = item["handle"]
    tweet_ids = item["tweet_ids"]
    tweet_id_to_url = item["tweet_id_to_url"]
    interaction = item.get("interaction")
    
    # Open Google Sheet
    try:
        ws = get_tweets_ws()
    except Exception as e:
        log_or_print("error", f"[TweetQueue] Error opening tweets worksheet: {e}", exc_info=True)
        if interaction:
            await interaction.followup.send(
                f"⚠️ Error accessing tweets sheet: {str(e)[:200]}. Please contact an admin.",
                ephemeral=True,
            )
        return

    # Read all rows
    try:
        await throttle_sheets_api()
        rows = await retry_with_backoff(
            lambda: asyncio.to_thread(ws.get_all_values),
            max_retries=3,
            initial_delay=1.0,
        )
    except Exception as e:
        log_or_print("error", f"[TweetQueue] Error reading tweets sheet: {e}")
        if interaction:
            await interaction.followup.send(
                "⚠️ Error reading tweets sheet. Please try again in a moment.",
                ephemeral=True,
            )
        return
    
    header = rows[0] if rows else []

    # Find column indices
    tweet_id_col = None
    url_col = None
    date_col = None
    member_col = None
    graded_col = None
    score_col = None
    xp_col = None
    text_col = None
    notes_col = None

    for idx, name in enumerate(header):
        if name == "Tweet ID":
            tweet_id_col = idx
        elif name == "URL":
            url_col = idx
        elif name == "Date":
            date_col = idx
        elif name == "Member":
            member_col = idx
        elif name == "Graded":
            graded_col = idx
        elif name == "Score":
            score_col = idx
        elif name == "XP Awarded":
            xp_col = idx
        elif name == "Tweet Text":
            text_col = idx
        elif name == "Notes" or "notes" in name.lower():
            notes_col = idx

    # Check for duplicates
    existing_tweet_ids = set()
    if tweet_id_col is not None:
        for row in rows[1:]:
            if len(row) > tweet_id_col and row[tweet_id_col]:
                existing_tweet_ids.add(row[tweet_id_col])
    
    # Filter out duplicates
    new_tweet_ids = [tid for tid in tweet_ids if tid not in existing_tweet_ids]
    duplicate_tweet_ids = [tid for tid in tweet_ids if tid in existing_tweet_ids]
    
    if not new_tweet_ids:
        if interaction:
            dup_count = len(duplicate_tweet_ids)
            await interaction.followup.send(
                f"⚠️ All {dup_count} tweet(s) have already been submitted.",
                ephemeral=True,
            )
        return

    if duplicate_tweet_ids:
        dup_count = len(duplicate_tweet_ids)
        log_or_print("info", f"[TweetQueue] User {user_id} ({user_name}): Skipping {dup_count} duplicate tweet(s) out of {len(tweet_ids)} submitted")
    
    # Process each new tweet
    now_str = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    results = []
    
    for tweet_id in new_tweet_ids:
        try:
            base_url = tweet_id_to_url[tweet_id]
            tweet_data = all_tweet_data.get(tweet_id, {})
            tweet_text = tweet_data.get("text")
            
            if not tweet_text:
                log_or_print("warning", f"[TweetQueue] Could not fetch text for tweet {tweet_id} (user {user_id}), saving as ungraded")
                
                # Build row
                if header:
                    col_count = len(header)
                    new_row = ["" for _ in range(col_count)]
                    if date_col is not None:
                        new_row[date_col] = now_str
                    if tweet_id_col is not None:
                        new_row[tweet_id_col] = tweet_id
                    if url_col is not None:
                        new_row[url_col] = base_url
                    if member_col is not None:
                        new_row[member_col] = user_name
                else:
                    new_row = [now_str, tweet_id, user_name, base_url]
                
                # Append row
                await throttle_sheets_api()
                await retry_with_backoff(
                    lambda: asyncio.to_thread(ws.append_row, new_row, "RAW"),
                    max_retries=3,
                    initial_delay=1.0,
                )
                
                results.append((tweet_id, False, 0.0, 0, "Tweet text could not be fetched - will be graded later"))
                continue
            
            # Build row
            if header:
                col_count = len(header)
                new_row = ["" for _ in range(col_count)]
                if date_col is not None:
                    new_row[date_col] = now_str
                if tweet_id_col is not None:
                    new_row[tweet_id_col] = tweet_id
                if url_col is not None:
                    new_row[url_col] = base_url
                if member_col is not None:
                    new_row[member_col] = user_name
            else:
                new_row = [now_str, tweet_id, user_name, base_url]
            
            # Append row
            pre_row_count = len(rows)
            target_row_index = pre_row_count + 1
            
            await throttle_sheets_api()
            await retry_with_backoff(
                lambda: asyncio.to_thread(ws.append_row, new_row, "RAW"),
                max_retries=3,
                initial_delay=1.0,
            )
            
            rows.append(new_row)
            
            # Grade the tweet
            score = 0.0
            rationale = ""
            try:
                score, rationale = await grade_tweet(tweet_text)
            except Exception as e:
                error_msg = str(e)
                log_or_print("error", f"[TweetQueue] Error grading tweet {tweet_id}: {error_msg}")
                if "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                    results.append((tweet_id, False, 0.0, 0, f"Grading failed: {error_msg} - will be graded later"))
                    continue
                score = 0.0
                rationale = f"Grading error: {error_msg[:200]}"
            
            # XP calculation
            xp_amount = max(0, round(score)) if score > 0 else 0

            # Check daily tweet XP limit
            tweet_xp_daily_limit = state.get("tweet_xp_daily_limit", 3)
            tweets_with_xp_today = await retry_with_backoff(
                lambda: asyncio.to_thread(get_tweets_with_xp_today, user_id, user_name),
                max_retries=2,
                initial_delay=0.5,
            )
            
            xp_awarded_in_sheet = xp_amount
            if xp_amount > 0 and tweets_with_xp_today >= tweet_xp_daily_limit:
                xp_awarded_in_sheet = 0
            
            # Update sheet with grading results
            def _get_column_letter(col_index: int) -> str:
                result = ""
                col_index += 1
                while col_index > 0:
                    col_index -= 1
                    result = chr(65 + (col_index % 26)) + result
                    col_index //= 26
                return result
            
            batch_updates = []
            if "Grading error" not in rationale and "Grading failed" not in rationale:
                if graded_col is not None:
                    batch_updates.append({
                        "range": f"{_get_column_letter(graded_col)}{target_row_index}",
                        "values": [[True]]
                    })
            
            if score_col is not None:
                batch_updates.append({
                    "range": f"{_get_column_letter(score_col)}{target_row_index}",
                    "values": [[score]]
                })
            if xp_col is not None:
                batch_updates.append({
                    "range": f"{_get_column_letter(xp_col)}{target_row_index}",
                    "values": [[xp_awarded_in_sheet]]
                })
            if text_col is not None and tweet_text:
                truncated_text = tweet_text[:49000] if len(tweet_text) > 49000 else tweet_text
                batch_updates.append({
                    "range": f"{_get_column_letter(text_col)}{target_row_index}",
                    "values": [[truncated_text]]
                })
            if notes_col is not None and rationale:
                batch_updates.append({
                    "range": f"{_get_column_letter(notes_col)}{target_row_index}",
                    "values": [[rationale[:500]]]
                })
            
            if batch_updates:
                await throttle_sheets_api()
                await retry_with_backoff(
                    lambda: asyncio.to_thread(ws.batch_update, batch_updates, value_input_option="RAW"),
                    max_retries=3,
                    initial_delay=1.0,
                )
            
            # Award XP if applicable
            xp_awarded = False
            if xp_awarded_in_sheet > 0:
                try:
                    await throttle_sheets_api()
                    def _add_xp_sync():
                        return add_xp(
                            user_id,
                            user_name,
                            xp_awarded_in_sheet,
                            "tweet_grade",
                            handle,
                            "tweet",
                            tweet_id,
                            f"Score {score} – {rationale[:180]}",
                        )
                    success, error_msg = await retry_with_backoff(
                        lambda: asyncio.to_thread(_add_xp_sync),
                        max_retries=2,
                        initial_delay=1.0,
                    )
                    if success:
                        xp_awarded = True
                except Exception as e:
                    log_or_print("error", f"[TweetQueue] Error logging XP event for tweet {tweet_id}: {e}")
            
            results.append((tweet_id, True, score, xp_awarded_in_sheet if xp_awarded else 0, None))
            
        except Exception as e:
            log_or_print("error", f"[TweetQueue] Error processing tweet {tweet_id}: {e}", exc_info=True)
            results.append((tweet_id, False, 0.0, 0, f"Error: {str(e)[:100]}"))
    
    # Send response to user if interaction available
    if interaction:
        response_lines = []
        if len(results) == 1:
            tweet_id, success, score, xp, error = results[0]
            if success:
                response_lines.append(f"✅ Tweet submitted **and graded**!")
                response_lines.append(f"- Score: **{score}**")
                if xp > 0:
                    response_lines.append(f"- XP awarded: **{xp} XP**")
                elif score > 0:
                    response_lines.append(f"- XP would be: **{max(0, round(score))} XP** (blocked by daily limit)")
            else:
                response_lines.append(f"✅ Tweet submitted")
                if error:
                    response_lines.append(f"⚠️ {error}")
        else:
            successful = [r for r in results if r[1]]
            failed = [r for r in results if not r[1]]
            total_xp = sum(r[3] for r in results)
            
            response_lines.append(f"✅ **{len(results)} tweet(s) submitted**")
            if successful:
                avg_score = sum(r[2] for r in successful) / len(successful) if successful else 0
                response_lines.append(f"- **{len(successful)} graded** (avg score: {avg_score:.1f})")
            if failed:
                response_lines.append(f"- **{len(failed)} saved for later grading**")
            if total_xp > 0:
                response_lines.append(f"- **Total XP awarded: {total_xp} XP**")
            if duplicate_tweet_ids:
                response_lines.append(f"- **{len(duplicate_tweet_ids)} duplicate(s) skipped**")
        
        try:
            await interaction.followup.send("\n".join(response_lines), ephemeral=True)
        except:
            pass


def parse_tweet_urls(url_input: str) -> List[tuple]:
    """Parse multiple tweet URLs from input string.
    
    Supports comma-separated or newline-separated URLs.
    
    Args:
        url_input: String containing one or more tweet URLs
        
    Returns:
        List of tuples: (tweet_id, base_url, original_url)
        Returns empty list if no valid URLs found
    """
    # Split by comma or newline
    url_strings = []
    for separator in [',', '\n', '\r\n']:
        if separator in url_input:
            url_strings = [u.strip() for u in url_input.split(separator) if u.strip()]
            break
    
    # If no separator found, treat as single URL
    if not url_strings:
        url_strings = [url_input.strip()]
    
    parsed_urls = []
    for url_str in url_strings:
        if not url_str:
            continue
            
        try:
            parsed = urlparse(url_str)
            if "twitter.com" not in parsed.netloc and "x.com" not in parsed.netloc:
                continue
            
            parts = parsed.path.strip("/").split("/")
            if len(parts) < 3 or parts[-2] != "status":
                continue
            
            tweet_id = parts[-1]
            base_url = f"https://{parsed.netloc}/{parts[0]}/status/{tweet_id}"
            parsed_urls.append((tweet_id, base_url, url_str))
        except Exception as e:
            log_or_print("warning", f"[SubmitTweet] Error parsing URL '{url_str}': {e}")
            continue
    
    return parsed_urls


@bot.tree.command(name="submit_tweet", description="Submit tweet URL(s) for Polymer content campaign. Multiple URLs supported.")
@app_commands.describe(
    url="Tweet URL(s) - can submit multiple URLs separated by commas or newlines (max 20 per submission)"
)
async def submit_tweet(interaction: discord.Interaction, url: str):
    await interaction.response.defer(ephemeral=True)

    # Check rate limiting first
    if not check_user_rate_limit(interaction.user.id, USER_COMMAND_COOLDOWN):
        remaining = get_user_rate_limit_remaining(interaction.user.id, USER_COMMAND_COOLDOWN)
        await interaction.followup.send(
            f"⏳ Please wait {remaining:.0f} seconds before submitting another tweet.",
            ephemeral=True,
        )
        return

    handle = get_twitter_handle_for_user(interaction.user.id)
    if handle is None:
        await interaction.followup.send(
            "❌ You have not set your Twitter handle. Please use `/set_twitter` first.",
            ephemeral=True,
        )
        return

    # Check if user is shadow banned (excluded)
    if is_handle_excluded(handle):
        # Shadow ban: accept submission but don't process it
        # User sees success message but nothing is logged or graded
        await interaction.followup.send(
            "✅ Tweet submitted successfully.",
            ephemeral=True,
        )
        return

    # Check Discord post count before making API calls
    try:
        guild = interaction.guild
        if guild:
            discord_post_count = await count_discord_messages_for_user(guild, interaction.user.id)
            min_posts_required = get_min_discord_posts()
            if discord_post_count < min_posts_required:
                # Shadow ban: accept submission but don't process it
                # User sees success message but nothing is logged or graded
                log_or_print("info", f"[SubmitTweet] User {interaction.user.id} ({interaction.user}) submitted tweet but has only {discord_post_count} Discord posts (need {min_posts_required}+)")
                await interaction.followup.send(
                    "✅ Tweet submitted successfully.",
                    ephemeral=True,
                )
                return
    except Exception as e:
        log_or_print("warning", f"[SubmitTweet] Error checking Discord post count for user {interaction.user.id}: {e}")
        # On error, continue processing (fail open to avoid blocking legitimate users)

    # Parse multiple URLs from input
    parsed_urls = parse_tweet_urls(url)
    
    if not parsed_urls:
        await interaction.followup.send(
            "❌ No valid Twitter/X tweet URLs found. Please provide at least one valid tweet URL (format: https://twitter.com/username/status/123456 or https://x.com/username/status/123456).",
            ephemeral=True,
        )
        return
    
    # Limit to 20 URLs per submission to prevent abuse
    if len(parsed_urls) > 20:
        await interaction.followup.send(
            f"❌ Too many URLs provided ({len(parsed_urls)}). Maximum 20 URLs per submission.",
            ephemeral=True,
        )
        return
    
    # Extract tweet IDs for batch processing
    tweet_ids = [tweet_id for tweet_id, _, _ in parsed_urls]
    tweet_id_to_url = {tweet_id: base_url for tweet_id, base_url, _ in parsed_urls}
    
    # Log submission with user info and tweet IDs
    log_or_print("info", f"[SubmitTweet] User {interaction.user.id} ({interaction.user}) submitted {len(tweet_ids)} tweet(s): {', '.join(tweet_ids[:5])}{'...' if len(tweet_ids) > 5 else ''}")
    
    # Add submission to queue for batch processing (Phase 2: Queue-based batching)
    submission_item = {
        "user_id": interaction.user.id,
        "user_name": str(interaction.user),
        "handle": handle,
        "tweet_ids": tweet_ids,
        "tweet_id_to_url": tweet_id_to_url,
        "interaction": interaction,  # Store interaction for followup response
    }
    
    try:
        await tweet_submission_queue.put(submission_item)
        queue_size = tweet_submission_queue.qsize()
        log_or_print("info", f"[SubmitTweet] Added {len(tweet_ids)} tweet(s) to processing queue (queue size: {queue_size})")
        
        # Send immediate acknowledgment to user
        await interaction.followup.send(
            f"✅ **{len(tweet_ids)} tweet(s) queued for processing!**\n"
            f"Your submission is in the queue and will be processed shortly. You'll receive a follow-up message with the results.",
            ephemeral=True,
        )
    except Exception as e:
        log_or_print("error", f"[SubmitTweet] Error adding submission to queue: {e}", exc_info=True)
        await interaction.followup.send(
            f"⚠️ Error queuing your submission: {str(e)[:200]}. Please try again.",
            ephemeral=True,
        )


async def _process_ungraded_tweets_core(
    check_stop_event: bool = True,
    send_updates: Optional[Callable[[str], Any]] = None
) -> Dict[str, int]:
    """Core logic for processing ungraded tweets.
    
    Args:
        check_stop_event: Whether to check for stop event (for manual runs)
        send_updates: Optional callback function to send progress updates (for manual runs)
    
    Returns:
        Dictionary with keys: 'processed', 'failed', 'skipped', 'total'
    """
    global twitter_api_rate_limit_reset, twitter_api_remaining
    
    log_or_print("info", "[ProcessUngraded] Starting process_ungraded_tweets_core")
    stats = {"processed": 0, "failed": 0, "skipped": 0, "total": 0}
    
    if not TWITTER_BEARER_TOKEN:
        error_msg = "TWITTER_BEARER_TOKEN not set. Cannot fetch tweet text."
        log_or_print("error", f"[ProcessUngraded] {error_msg}")
        if send_updates:
            await send_updates(f"❌ {error_msg}")
        return stats
    
    if not OPENAI_API_KEY:
        error_msg = "OPENAI_API_KEY not set. Cannot grade tweets."
        log_or_print("error", f"[ProcessUngraded] {error_msg}")
        if send_updates:
            await send_updates(f"❌ {error_msg}")
        return stats
    
    try:
        ws = get_tweets_ws()
    except Exception as e:
        if logger:
            logger.error(f"[ProcessUngraded] Error opening tweets worksheet: {e}", exc_info=True)
        error_msg = f"Error accessing tweets sheet: {str(e)}"
        if send_updates:
            await send_updates(f"❌ {error_msg}")
        return stats
    
    # Read all rows once at the start (cache for daily limit checks)
    try:
        await throttle_sheets_api()
        cached_tweets_rows = await retry_with_backoff(
            lambda: asyncio.to_thread(ws.get_all_values),
            max_retries=3,
            initial_delay=1.0,
        )
    except Exception as e:
        if logger:
            logger.error(f"[ProcessUngraded] Error reading tweets sheet: {e}", exc_info=True)
        error_msg = f"Error reading tweets sheet: {str(e)}"
        if send_updates:
            await send_updates(f"❌ {error_msg}")
        return stats
    
    if not cached_tweets_rows or len(cached_tweets_rows) < 2:
        log_or_print("info", "[ProcessUngraded] No tweets found in the sheet")
        if send_updates:
            await send_updates("✅ No tweets found in the sheet.")
        return stats
    
    log_or_print("info", f"[ProcessUngraded] Read {len(cached_tweets_rows)} rows from sheet")
    rows = cached_tweets_rows
    header = rows[0]
    
    # Find column indices
    tweet_id_col = None
    member_col = None
    graded_col = None
    score_col = None
    xp_col = None
    text_col = None
    notes_col = None
    
    for idx, name in enumerate(header):
        name_lower = name.lower()
        if "tweet id" in name_lower or name == "Tweet ID":
            tweet_id_col = idx
        elif name == "Member" or "member" in name_lower:
            member_col = idx
        elif name == "Graded" or "graded" in name_lower:
            graded_col = idx
        elif name == "Score" or "score" in name_lower:
            score_col = idx
        elif "xp" in name_lower and "awarded" in name_lower:
            xp_col = idx
        elif "tweet text" in name_lower or name == "Tweet Text":
            text_col = idx
        elif name == "Notes" or "notes" in name_lower:
            notes_col = idx
    
    if tweet_id_col is None:
        error_msg = "Could not find 'Tweet ID' column in the sheet."
        if send_updates:
            await send_updates(f"❌ {error_msg}")
        return stats
    
    # Find ungraded tweets
    ungraded_rows = []
    for row_idx, row in enumerate(rows[1:], start=2):
        if len(row) <= max(tweet_id_col, graded_col if graded_col is not None else 0):
            continue
        
        is_graded = False
        if graded_col is not None and len(row) > graded_col:
            graded_value = row[graded_col].strip().lower()
            is_graded = graded_value in ["true", "yes", "1", "graded"]
        
        if not is_graded:
            tweet_id = row[tweet_id_col] if len(row) > tweet_id_col else ""
            if tweet_id:
                ungraded_rows.append((row_idx, row, tweet_id))
    
    stats["total"] = len(ungraded_rows)
    log_or_print("info", f"[ProcessUngraded] Found {len(ungraded_rows)} ungraded tweets")
    
    if not ungraded_rows:
        log_or_print("info", "[ProcessUngraded] No ungraded tweets found")
        if send_updates:
            await send_updates("✅ No ungraded tweets found.")
        return stats
    
    if send_updates:
        await send_updates(
            f"🔄 Found {len(ungraded_rows)} ungraded tweet(s). Processing in batches with rate limiting...\n"
            f"⏳ This may take a while. I'll update you when complete.\n"
            f"💡 Use `/stop_processing_tweets` to stop processing at any time."
        )
    
    # Clear stop event at start (in case it was set from a previous run)
    if check_stop_event:
        process_tweets_stop_event.clear()
    
    def _get_column_letter(col_index: int) -> str:
        """Convert 0-based column index to A1 notation letter."""
        result = ""
        col_index += 1
        while col_index > 0:
            col_index -= 1
            result = chr(65 + (col_index % 26)) + result
            col_index //= 26
        return result
    
    # First pass: Validate rows and collect tweet IDs for batch fetching
    log_or_print("info", "[ProcessUngraded] Starting validation pass")
    tweet_data_map: Dict[str, Dict] = {}
    tweets_to_fetch = []
    
    # Get guild for Discord post count checks (needed for eligibility)
    guild = None
    try:
        # Try to get guild from bot (assuming bot is available)
        if bot.guilds:
            guild = bot.guilds[0]  # Use first guild, or find the correct one
            log_or_print("debug", f"[ProcessUngraded] Using guild {guild.id} ({guild.name}) for eligibility checks")
    except Exception as e:
        log_or_print("warning", f"[ProcessUngraded] Could not get guild for eligibility checks: {e}")
    
    for row_idx, row, tweet_id in ungraded_rows:
        if check_stop_event and process_tweets_stop_event.is_set():
            if logger:
                logger.info(f"[ProcessUngraded] Stop requested by user during validation. Processed {stats['processed']}, failed {stats['failed']}")
            if send_updates:
                await send_updates(
                    f"⏹️ **Processing stopped by user request.**\n\n"
                    f"📊 **Progress:**\n"
                    f"• Validated: **{len(tweet_data_map)}** tweet(s)\n"
                    f"• Failed validation: **{stats['failed']}** tweet(s)\n\n"
                    f"💡 Run `/process_ungraded_tweets` again to continue processing remaining tweets."
                )
            if check_stop_event:
                process_tweets_stop_event.clear()
            return stats
        
        try:
            discord_username = ""
            if member_col is not None and len(row) > member_col:
                discord_username = row[member_col].strip()
            
            if not discord_username:
                batch_updates = [{
                    "range": f"{_get_column_letter(graded_col if graded_col is not None else len(header))}{row_idx}",
                    "values": [["FALSE"]]
                }]
                if notes_col is not None:
                    batch_updates.append({
                        "range": f"{_get_column_letter(notes_col)}{row_idx}",
                        "values": [["Failed: Member not found"]]
                    })
                await throttle_sheets_api()
                await retry_with_backoff(
                    lambda: asyncio.to_thread(ws.batch_update, batch_updates, value_input_option="RAW"),
                    max_retries=2,
                    initial_delay=1.0,
                )
                stats["failed"] += 1
                if logger:
                    logger.warning(f"[ProcessUngraded] Row {row_idx}: No member found")
                continue
            
            twitter_handle = get_twitter_handle_for_username(discord_username)
            if not twitter_handle:
                batch_updates = [{
                    "range": f"{_get_column_letter(graded_col if graded_col is not None else len(header))}{row_idx}",
                    "values": [["FALSE"]]
                }]
                if notes_col is not None:
                    batch_updates.append({
                        "range": f"{_get_column_letter(notes_col)}{row_idx}",
                        "values": [[f"Failed: Member '{discord_username}' not found in Twitter handle mapping"]]
                    })
                await throttle_sheets_api()
                await retry_with_backoff(
                    lambda: asyncio.to_thread(ws.batch_update, batch_updates, value_input_option="RAW"),
                    max_retries=2,
                    initial_delay=1.0,
                )
                stats["failed"] += 1
                if logger:
                    logger.warning(f"[ProcessUngraded] Row {row_idx}: Twitter handle not found for {discord_username}")
                continue
            
            # Check if handle is excluded BEFORE adding to fetch list
            if is_handle_excluded(twitter_handle):
                log_or_print("info", f"[ProcessUngraded] Row {row_idx}: Twitter handle {twitter_handle} is excluded, skipping API call")
                # Mark as failed but don't fetch
                batch_updates = [{
                    "range": f"{_get_column_letter(graded_col if graded_col is not None else len(header))}{row_idx}",
                    "values": [["FALSE"]]
                }]
                if notes_col is not None:
                    batch_updates.append({
                        "range": f"{_get_column_letter(notes_col)}{row_idx}",
                        "values": [["Failed: Account excluded"]]
                    })
                await throttle_sheets_api()
                await retry_with_backoff(
                    lambda: asyncio.to_thread(ws.batch_update, batch_updates, value_input_option="RAW"),
                    max_retries=2,
                    initial_delay=1.0,
                )
                stats["failed"] += 1
                continue
            
            discord_id = None
            try:
                ensure_handles_file_exists()
                with open(TWITTER_HANDLES_CSV, "r", newline="", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    csv_rows = list(reader)
                    for csv_row in csv_rows[1:]:
                        if len(csv_row) >= 2:
                            csv_username = csv_row[1].split("#")[0].strip().lower() if csv_row[1] else ""
                            if csv_username == discord_username.split("#")[0].strip().lower():
                                try:
                                    discord_id = int(csv_row[0])
                                    break
                                except (ValueError, TypeError):
                                    pass
            except Exception:
                pass
            
            # Check Discord post count BEFORE adding to fetch list
            if discord_id and guild:
                try:
                    discord_post_count = await count_discord_messages_for_user(guild, discord_id)
                    min_posts_required = get_min_discord_posts()
                    if discord_post_count < min_posts_required:
                        log_or_print("info", f"[ProcessUngraded] Row {row_idx}: User {discord_id} ({discord_username}) has only {discord_post_count} Discord posts (need {min_posts_required}+), skipping API call")
                        # Mark as failed but don't fetch
                        batch_updates = [{
                            "range": f"{_get_column_letter(graded_col if graded_col is not None else len(header))}{row_idx}",
                            "values": [["FALSE"]]
                        }]
                        if notes_col is not None:
                            batch_updates.append({
                                "range": f"{_get_column_letter(notes_col)}{row_idx}",
                                "values": [["Failed: Insufficient Discord posts"]]
                            })
                        await throttle_sheets_api()
                        await retry_with_backoff(
                            lambda: asyncio.to_thread(ws.batch_update, batch_updates, value_input_option="RAW"),
                            max_retries=2,
                            initial_delay=1.0,
                        )
                        stats["failed"] += 1
                        continue
                except Exception as e:
                    log_or_print("warning", f"[ProcessUngraded] Row {row_idx}: Error checking Discord post count for user {discord_id}: {e}")
                    # On error, continue processing (fail open to avoid blocking legitimate users)
            
            # Only add to fetch list if passed all eligibility checks
            tweet_data_map[tweet_id] = {
                "row_idx": row_idx,
                "row": row,
                "discord_username": discord_username,
                "twitter_handle": twitter_handle,
                "discord_id": discord_id,
            }
            tweets_to_fetch.append(tweet_id)
            
        except Exception as e:
            if logger:
                logger.error(f"[ProcessUngraded] Row {row_idx}: Error during validation: {e}", exc_info=True)
            stats["failed"] += 1
            continue
    
    if not tweets_to_fetch:
        log_or_print("info", f"[ProcessUngraded] Validation complete. No valid tweets to process. Failed: {stats['failed']}")
        if send_updates:
            await send_updates(
                f"✅ Validation complete. No valid tweets to process.\n"
                f"📊 Failed validation: **{stats['failed']}** tweet(s)"
            )
        if check_stop_event:
            process_tweets_stop_event.clear()
        return stats
    
    log_or_print("info", f"[ProcessUngraded] Validation complete. {len(tweets_to_fetch)} tweets to fetch, {stats['failed']} failed validation")
    
    # Batch fetch tweet texts (in chunks of 100)
    tweet_texts: Dict[str, Optional[str]] = {}
    
    def chunks(lst, n):
        """Split list into chunks of size n."""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]
    
    # Check rate limit BEFORE starting batch fetching
    # If we're already at the limit, wait for reset
    # Check reset time first (more reliable than remaining count which might be wrong)
    log_or_print("info", "[ProcessUngraded] Checking rate limit before starting batch fetch...")
    # Read values without lock (read-only operation is safe without lock)
    # We only need the lock when writing/updating these values
    now = time.time()
    reset_time = twitter_api_rate_limit_reset
    remaining_count = twitter_api_remaining
    log_or_print("info", f"[ProcessUngraded] Rate limit check: reset={reset_time}, remaining={remaining_count}, now={now}")
    
    wait_time_to_use = None
    if reset_time and now < reset_time:
        # If we have a reset time in the future, we should wait
        # The reset time is more reliable than the remaining count (which might be corrupted)
        wait_time = reset_time - now
        
        # Only wait if the wait time is reasonable (not more than 15 minutes)
        # If it's longer, something might be wrong with the reset time
        log_or_print("info", f"[ProcessUngraded] Rate limit reset time found: {wait_time:.0f} seconds from now")
        if 0 < wait_time <= 900:  # Max 15 minutes
            remaining_info = f" (remaining: {remaining_count})" if remaining_count is not None else ""
            log_or_print("warning", f"[ProcessUngraded] Rate limit exhausted (reset in {wait_time:.0f}s{remaining_info}). Waiting before starting batch fetch...")
            if send_updates:
                await send_updates(
                    f"⏳ **Rate limit exhausted.**\n"
                    f"Waiting {wait_time:.0f} seconds ({wait_time/60:.1f} minutes) for rate limit reset before starting...\n"
                    f"💡 You can use `/stop_processing_tweets` to cancel."
                )
            wait_time_to_use = wait_time
        elif wait_time > 900:
            # Reset time is more than 15 minutes away - this seems wrong, clear it
            log_or_print("warning", f"[ProcessUngraded] Reset time is {wait_time:.0f}s away (>15 min), which seems incorrect. Clearing reset time.")
            async with twitter_api_lock:
                twitter_api_rate_limit_reset = None
                twitter_api_remaining = None
            wait_time_to_use = None
    
    # If we need to wait, do it outside the lock to avoid blocking other operations
    if wait_time_to_use and 0 < wait_time_to_use <= 900:
        await asyncio.sleep(wait_time_to_use)
        log_or_print("info", "[ProcessUngraded] Finished waiting for rate limit reset. Continuing...")
        # Reset the remaining count after waiting (will be updated on next API call)
        async with twitter_api_lock:
            twitter_api_remaining = None
    
    log_or_print("info", "[ProcessUngraded] Rate limit check complete. Proceeding to batch fetch...")
    
    batch_size = 100
    total_batches = (len(tweets_to_fetch) + batch_size - 1) // batch_size
    log_or_print("info", f"[ProcessUngraded] Starting batch fetch: {total_batches} batches of up to {batch_size} tweets each")
    
    batch_list = list(chunks(tweets_to_fetch, batch_size))
    batch_num = 0
    
    while batch_num < len(batch_list):
        if check_stop_event and process_tweets_stop_event.is_set():
            if logger:
                logger.info(f"[ProcessUngraded] Stop requested during batch fetch. Processed {stats['processed']}, failed {stats['failed']}")
            if send_updates:
                await send_updates(
                    f"⏹️ **Processing stopped by user request.**\n\n"
                    f"📊 **Progress:**\n"
                    f"• Fetched: **{len(tweet_texts)}** tweet(s)\n"
                    f"• Processed: **{stats['processed']}** tweet(s)\n"
                    f"• Failed: **{stats['failed']}** tweet(s)\n"
                    f"• Remaining: **{len(tweets_to_fetch) - len(tweet_texts)}** tweet(s)\n\n"
                    f"💡 Run `/process_ungraded_tweets` again to continue processing remaining tweets."
                )
            if check_stop_event:
                process_tweets_stop_event.clear()
            return stats
        
        batch_num += 1
        tweet_id_batch = batch_list[batch_num - 1]
        
        try:
            if logger:
                logger.info(f"[ProcessUngraded] Fetching batch {batch_num}/{total_batches} ({len(tweet_id_batch)} tweets)")
            
            # Check rate limit before each batch
            # Use reset time as primary check (more reliable than remaining count)
            async with twitter_api_lock:
                now = time.time()
                if twitter_api_rate_limit_reset and now < twitter_api_rate_limit_reset:
                    # Check if we should wait based on remaining count or reset time
                    should_wait = False
                    if twitter_api_remaining is None:
                        should_wait = True  # Unknown - be safe
                    elif twitter_api_remaining <= 0:
                        should_wait = True  # Definitely at limit
                    elif twitter_api_remaining > 1000:
                        # Suspiciously high value - trust reset time
                        should_wait = True
                    
                    if should_wait:
                        wait_time = twitter_api_rate_limit_reset - now
                        if wait_time > 0:
                            if logger:
                                logger.warning(f"[ProcessUngraded] Rate limit exhausted before batch {batch_num}. Waiting {wait_time:.0f}s...")
                            if send_updates:
                                await send_updates(f"⏳ Rate limit exhausted. Waiting {wait_time:.0f}s ({wait_time/60:.1f} min) before batch {batch_num}...")
                            await asyncio.sleep(wait_time)
                            # Reset remaining count after waiting
                            async with twitter_api_lock:
                                twitter_api_remaining = None
            
            log_or_print("info", f"[ProcessUngraded] Calling Twitter API for batch {batch_num}/{total_batches}")
            batch_results = await retry_with_backoff(
                lambda: fetch_tweets_batch_from_api(tweet_id_batch),
                max_retries=3,
                initial_delay=2.0,
                max_delay=300.0,
            )
            
            fetched_count = sum(1 for v in batch_results.values() if v is not None)
            log_or_print("info", f"[ProcessUngraded] Batch {batch_num}/{total_batches} complete: fetched {fetched_count}/{len(tweet_id_batch)} tweets")
            tweet_texts.update(batch_results)
            
            # Add delay between batches to be conservative with rate limits
            # Use longer delay if we're getting low on remaining requests
            async with twitter_api_lock:
                delay = 1.0
                if twitter_api_remaining is not None:
                    if twitter_api_remaining < 10:
                        delay = 5.0  # Longer delay when low on requests
                    elif twitter_api_remaining < 50:
                        delay = 2.0  # Medium delay when getting low
                
            if batch_num < total_batches:
                await asyncio.sleep(delay)
                
        except TwitterUsageCapExceededError as e:
            # Usage cap exceeded - cannot continue processing
            error_msg = (
                f"❌ **Twitter API Monthly Usage Cap Exceeded**\n\n"
                f"The Twitter API account has hit its monthly usage limit ({e.period}).\n"
                f"Tweet fetching cannot continue until the billing period resets.\n\n"
                f"**Options:**\n"
                f"• Wait for the next billing cycle\n"
                f"• Upgrade the Twitter API plan to increase the monthly limit\n\n"
                f"**Progress so far:**\n"
                f"• Fetched: **{len(tweet_texts)}** tweet(s)\n"
                f"• Processed: **{stats['processed']}** tweet(s)\n"
                f"• Failed: **{stats['failed']}** tweet(s)\n"
                f"• Remaining: **{len(tweets_to_fetch) - len(tweet_texts)}** tweet(s)\n\n"
                f"Processing stopped. Run `/process_ungraded_tweets` again after the cap resets."
            )
            log_or_print("error", f"[ProcessUngraded] {error_msg}")
            if send_updates:
                await send_updates(error_msg)
            if check_stop_event:
                process_tweets_stop_event.clear()
            return stats
        except TwitterRateLimitError as e:
            retry_after = e.retry_after if e.retry_after else 60
            wait_time = min(retry_after + 5, 300)
            if logger:
                logger.warning(f"[ProcessUngraded] Rate limit hit during batch {batch_num}. Waiting {wait_time:.0f}s before retrying...")
            if send_updates:
                await send_updates(f"⏳ Rate limit hit on batch {batch_num}. Waiting {wait_time:.0f}s ({wait_time/60:.1f} min) before retrying...")
            await asyncio.sleep(wait_time)
            # Retry the same batch by not incrementing batch_num
            batch_num -= 1
            continue
        except Exception as e:
            if logger:
                logger.error(f"[ProcessUngraded] Error fetching batch {batch_num}: {e}", exc_info=True)
            for tid in tweet_id_batch:
                if tid in tweet_data_map:
                    tweet_data_map[tid]["fetch_error"] = str(e)[:100]
            continue
    
    # Second pass: Process each tweet with fetched text
    log_or_print("info", f"[ProcessUngraded] Starting processing phase: {len(tweet_data_map)} tweets to process")
    processed_count = 0
    for tweet_id, tweet_data in tweet_data_map.items():
        processed_count += 1
        if processed_count % 10 == 0:
            log_or_print("info", f"[ProcessUngraded] Processing progress: {processed_count}/{len(tweet_data_map)} tweets processed")
        if check_stop_event and process_tweets_stop_event.is_set():
            if logger:
                logger.info(f"[ProcessUngraded] Stop requested by user. Processed {stats['processed']}, failed {stats['failed']}, remaining: {len(tweet_data_map) - stats['processed'] - stats['failed']}")
            if send_updates:
                await send_updates(
                    f"⏹️ **Processing stopped by user request.**\n\n"
                    f"📊 **Progress:**\n"
                    f"• Processed: **{stats['processed']}** tweet(s)\n"
                    f"• Failed: **{stats['failed']}** tweet(s)\n"
                    f"• Remaining: **{len(tweet_data_map) - stats['processed'] - stats['failed']}** tweet(s)\n\n"
                    f"💡 Run `/process_ungraded_tweets` again to continue processing remaining tweets."
                )
            if check_stop_event:
                process_tweets_stop_event.clear()
            return stats
        
        try:
            row_idx = tweet_data["row_idx"]
            row = tweet_data["row"]
            discord_username = tweet_data["discord_username"]
            twitter_handle = tweet_data["twitter_handle"]
            discord_id = tweet_data["discord_id"]
            
            tweet_text = tweet_texts.get(tweet_id)
            
            if "fetch_error" in tweet_data:
                reason = f"Failed: {tweet_data['fetch_error']}"
                batch_updates = [{
                    "range": f"{_get_column_letter(graded_col if graded_col is not None else len(header))}{row_idx}",
                    "values": [["FALSE"]]
                }]
                if notes_col is not None:
                    batch_updates.append({
                        "range": f"{_get_column_letter(notes_col)}{row_idx}",
                        "values": [[reason]]
                    })
                await throttle_sheets_api()
                await retry_with_backoff(
                    lambda: asyncio.to_thread(ws.batch_update, batch_updates, value_input_option="RAW"),
                    max_retries=2,
                    initial_delay=1.0,
                )
                stats["failed"] += 1
                if logger:
                    logger.warning(f"[ProcessUngraded] Row {row_idx}: {reason}")
                continue
            
            if not tweet_text or not tweet_text.strip():
                batch_updates = [{
                    "range": f"{_get_column_letter(graded_col if graded_col is not None else len(header))}{row_idx}",
                    "values": [["FALSE"]]
                }]
                if notes_col is not None:
                    batch_updates.append({
                        "range": f"{_get_column_letter(notes_col)}{row_idx}",
                        "values": [["Failed: Tweet text is blank"]]
                    })
                await throttle_sheets_api()
                await retry_with_backoff(
                    lambda: asyncio.to_thread(ws.batch_update, batch_updates, value_input_option="RAW"),
                    max_retries=2,
                    initial_delay=1.0,
                )
                stats["failed"] += 1
                continue
            
            try:
                log_or_print("debug", f"[ProcessUngraded] Row {row_idx}: Grading tweet {tweet_id}")
                score, rationale = await grade_tweet(tweet_text)
                log_or_print("debug", f"[ProcessUngraded] Row {row_idx}: Graded tweet {tweet_id}, score: {score}")
            except Exception as e:
                if logger:
                    logger.error(f"[ProcessUngraded] Row {row_idx}: Error grading tweet: {e}", exc_info=True)
                batch_updates = [{
                    "range": f"{_get_column_letter(graded_col if graded_col is not None else len(header))}{row_idx}",
                    "values": [["FALSE"]]
                }]
                if notes_col is not None:
                    batch_updates.append({
                        "range": f"{_get_column_letter(notes_col)}{row_idx}",
                        "values": [[f"Failed: Grading error - {str(e)[:100]}"]]
                    })
                await throttle_sheets_api()
                await retry_with_backoff(
                    lambda: asyncio.to_thread(ws.batch_update, batch_updates, value_input_option="RAW"),
                    max_retries=2,
                    initial_delay=1.0,
                )
                stats["failed"] += 1
                continue
            
            xp_amount = max(0, round(score)) if score > 0 else 0
            
            xp_to_award_in_sheet = xp_amount
            if xp_amount > 0 and discord_id:
                tweet_xp_daily_limit = state.get("tweet_xp_daily_limit", 3)
                tweets_with_xp_today = await retry_with_backoff(
                    lambda: asyncio.to_thread(get_tweets_with_xp_today, discord_id, discord_username, tweets_ws=ws, tweets_rows=cached_tweets_rows),
                    max_retries=2,
                    initial_delay=0.5,
                )
                if tweets_with_xp_today >= tweet_xp_daily_limit:
                    xp_to_award_in_sheet = 0
                    if logger:
                        logger.info(f"[ProcessUngraded] Row {row_idx}: XP not awarded - daily limit reached ({tweets_with_xp_today}/{tweet_xp_daily_limit})")
            
            batch_updates = []
            if graded_col is not None:
                batch_updates.append({
                    "range": f"{_get_column_letter(graded_col)}{row_idx}",
                    "values": [["TRUE"]]
                })
            if score_col is not None:
                batch_updates.append({
                    "range": f"{_get_column_letter(score_col)}{row_idx}",
                    "values": [[score]]
                })
            if xp_col is not None:
                batch_updates.append({
                    "range": f"{_get_column_letter(xp_col)}{row_idx}",
                    "values": [[xp_to_award_in_sheet]]
                })
            if text_col is not None:
                truncated_text = tweet_text[:49000] if len(tweet_text) > 49000 else tweet_text
                batch_updates.append({
                    "range": f"{_get_column_letter(text_col)}{row_idx}",
                    "values": [[truncated_text]]
                })
            
            if batch_updates:
                await throttle_sheets_api()
                await retry_with_backoff(
                    lambda: asyncio.to_thread(ws.batch_update, batch_updates, value_input_option="RAW"),
                    max_retries=3,
                    initial_delay=1.0,
                )
            
            if xp_to_award_in_sheet > 0 and discord_id:
                try:
                    await throttle_sheets_api()
                    def _add_xp_sync():
                        return add_xp(
                            discord_id,
                            discord_username,
                            xp_to_award_in_sheet,
                            "tweet_grade",
                            twitter_handle,
                            "tweet",
                            tweet_id,
                            f"Score {score} – {rationale[:180]}",
                        )
                    success, error_msg = await retry_with_backoff(
                        lambda: asyncio.to_thread(_add_xp_sync),
                        max_retries=2,
                        initial_delay=1.0,
                    )
                    if not success and logger:
                        logger.warning(f"[ProcessUngraded] Row {row_idx}: XP not awarded: {error_msg}")
                except Exception as e:
                    if logger:
                        logger.warning(f"[ProcessUngraded] Row {row_idx}: Error awarding XP: {e}")
            elif xp_amount > 0 and not discord_id:
                if logger:
                    logger.warning(f"[ProcessUngraded] Row {row_idx}: Could not find Discord ID for {discord_username}, XP not awarded")
            
            stats["processed"] += 1
            log_or_print("info", f"[ProcessUngraded] Row {row_idx}: Processed tweet {tweet_id}, score: {score}, XP: {xp_amount}")
            
            await asyncio.sleep(0.5)
            
        except Exception as e:
            if logger:
                logger.error(f"[ProcessUngraded] Row {tweet_data.get('row_idx', 'unknown')}: Unexpected error: {e}", exc_info=True)
            stats["failed"] += 1
            continue
    
    if check_stop_event:
        process_tweets_stop_event.clear()
    
    log_or_print("info", f"[ProcessUngraded] Processing complete. Stats: processed={stats['processed']}, failed={stats['failed']}, skipped={stats['skipped']}, total={stats['total']}")
    return stats


@bot.tree.command(name="reset_twitter_rate_limit", description="Reset Twitter API rate limit tracking (Admin only)")
@admin_or_role_only(get_admin_role_list)
async def reset_twitter_rate_limit(interaction: discord.Interaction):
    """Reset the Twitter API rate limit tracking.
    
    This clears the cached rate limit information, which can help if the tracking
    gets out of sync or shows incorrect values. The next API call will fetch fresh
    rate limit information from Twitter.
    """
    await interaction.response.defer(ephemeral=True)
    
    global twitter_api_rate_limit_reset, twitter_api_remaining
    
    async with twitter_api_lock:
        old_reset = twitter_api_rate_limit_reset
        old_remaining = twitter_api_remaining
        twitter_api_rate_limit_reset = None
        twitter_api_remaining = None
    
    reset_info = []
    if old_reset:
        reset_info.append(f"Reset time: {old_reset}")
    if old_remaining is not None:
        reset_info.append(f"Remaining: {old_remaining}")
    
    if logger:
        logger.info(f"[ResetRateLimit] Rate limit tracking reset by {interaction.user}. Old values: {', '.join(reset_info) if reset_info else 'None'}")
    
    await interaction.followup.send(
        f"✅ **Twitter API rate limit tracking reset.**\n\n"
        f"The next API call will fetch fresh rate limit information from Twitter.\n"
        f"Old values cleared: {', '.join(reset_info) if reset_info else 'None'}",
        ephemeral=True
    )


@bot.tree.command(name="process_ungraded_tweets", description="Process all ungraded tweets in the sheet (Admin only)")
@admin_or_role_only(get_admin_role_list)
async def process_ungraded_tweets(interaction: discord.Interaction):
    """Process all ungraded tweets in the tweets sheet.
    
    This will:
    - Find all tweets where Graded is FALSE or empty
    - Look up Twitter handles by Discord username
    - Fetch tweet text and grade them
    - Update the sheet with scores and XP
    - Mark failed tweets with reasons
    """
    log_or_print("info", f"[ProcessUngraded] Command invoked by {interaction.user.name} ({interaction.user.id})")
    await interaction.response.defer(ephemeral=True)
    
    async def send_update(msg: str):
        await interaction.followup.send(msg, ephemeral=True)
    
    log_or_print("info", "[ProcessUngraded] Starting _process_ungraded_tweets_core")
    stats = await _process_ungraded_tweets_core(check_stop_event=True, send_updates=send_update)
    log_or_print("info", f"[ProcessUngraded] _process_ungraded_tweets_core returned. Stats: {stats}")
    
    # Send completion message if we got stats (function didn't return early)
    if stats.get("total", 0) > 0:
        result_msg = (
            f"✅ **Processing Complete!**\n\n"
            f"📊 **Results:**\n"
            f"• Processed: **{stats['processed']}** tweet(s)\n"
            f"• Failed: **{stats['failed']}** tweet(s)\n"
            f"• Skipped: **{stats['skipped']}** tweet(s)\n\n"
        )
        
        if stats['failed'] > 0:
            result_msg += "⚠️ Some tweets failed. Check the 'Notes' column for reasons."
        
        await interaction.followup.send(result_msg, ephemeral=True)


@bot.tree.command(name="stop_processing_tweets", description="Stop the currently running /process_ungraded_tweets command (Admin only)")
@admin_or_role_only(get_admin_role_list)
async def stop_processing_tweets(interaction: discord.Interaction):
    """Stop the currently running /process_ungraded_tweets command.
    
    This will gracefully stop processing at the next tweet, allowing the current
    tweet to finish processing before stopping.
    """
    await interaction.response.defer(ephemeral=True)
    
    # Check if processing is currently running
    if process_tweets_stop_event.is_set():
        await interaction.followup.send(
            "⚠️ Stop request already pending. Processing will stop at the next tweet.",
            ephemeral=True
        )
        return
    
    # Set the stop event
    process_tweets_stop_event.set()
    
    if logger:
        logger.info(f"[StopProcessing] Stop requested by {interaction.user.name} ({interaction.user.id})")
    
    await interaction.followup.send(
        "⏹️ **Stop request sent!**\n\n"
        "Processing will stop gracefully after the current tweet finishes. "
        "You'll receive a summary of progress when it stops.",
        ephemeral=True
    )


@bot.tree.command(name="check_tweets", description="Check how many tweets you have submitted")
@app_commands.describe(
    user="View another user's tweet count (Admin only)"
)
async def check_tweets(interaction: discord.Interaction, user: Optional[discord.User] = None):
    await interaction.response.defer(ephemeral=True)

    # Check if user is viewing someone else's tweets
    target_user = user if user else interaction.user
    is_admin = False
    
    if user and user != interaction.user:
        # Check if requester is admin
        if interaction.user.guild_permissions.administrator:
            is_admin = True
        else:
            user_roles = [role.name for role in interaction.user.roles]
            if get_admin_role_name() in user_roles:
                is_admin = True
        
        if not is_admin:
            await interaction.followup.send(
                f"❌ You don't have permission to view other users' tweet counts.",
                ephemeral=True
            )
            return

    handle = get_twitter_handle_for_user(target_user.id)
    if handle is None:
        await interaction.followup.send(
            f"❌ {target_user.mention} has not set their Twitter handle. Use `/set_twitter` first.",
            ephemeral=True,
        )
        return

    user_identifier = str(target_user)
    count_new = 0
    count_old = 0

    # Count tweets from current sheet
    try:
        ws = get_tweets_ws()
        rows = ws.get_all_values()
        header = rows[0] if rows else []
        member_col = None
        if header:
            for idx, name in enumerate(header):
                if name == "Member":
                    member_col = idx
                    break

        if member_col is not None:
            for row in rows[1:]:
                if len(row) > member_col and row[member_col] == user_identifier:
                    count_new += 1
    except Exception as e:
        log_or_print("warning", f"[CheckTweets] Error accessing current tweets worksheet: {e}")

    # Count tweets from old sheet (if configured)
    # Note: Old sheet has Twitter handles in Member column, not Discord usernames
    if OLD_TWEETS_SHEET_NAME and handle:
        try:
            old_ws = get_old_tweets_ws()
            if old_ws:
                old_rows = old_ws.get_all_values()
                old_header = old_rows[0] if old_rows else []
                old_member_col = None
                if old_header:
                    for idx, name in enumerate(old_header):
                        if name == "Member":
                            old_member_col = idx
                            break

                if old_member_col is not None:
                    # Normalize handle for comparison (remove @, lowercase)
                    normalized_handle = handle.lstrip("@").lower().strip()
                    for row in old_rows[1:]:
                        if len(row) > old_member_col:
                            # Normalize the value in the sheet for comparison
                            row_value = row[old_member_col].lstrip("@").lower().strip()
                            if row_value == normalized_handle:
                                count_old += 1
        except Exception as e:
            log_or_print("warning", f"[CheckTweets] Error accessing old tweets worksheet: {e}")

    total_count = count_new + count_old
    
    await interaction.followup.send(
        f"🧵 {target_user.mention} has submitted **{total_count}** tweet(s) so far.",
        ephemeral=True,
    )


@bot.tree.command(name="polyu_rank", description="Show your Polymer University leaderboard rank (sheet-based)")
async def polyu_rank(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    rank_info = get_user_rank(interaction.user.id)
    if not rank_info:
        await interaction.followup.send(
            "🔍 You have not earned any XP yet, so you're not ranked. Submit a tweet or pass a quiz to get started!",
            ephemeral=True,
        )
        return

    total_xp = rank_info["total_xp"]
    rank = rank_info["rank"]
    total_users = rank_info["total_users"]

    handle = get_twitter_handle_for_user(interaction.user.id)
    handle_text = f"@{handle.lower()}" if handle else interaction.user.mention

    lines = [
        f"🎓 Polymer University rank for {handle_text}:",
        f"- Rank: **#{rank}** out of {total_users} learners",
        f"- XP: **{total_xp}**",
    ]

    await interaction.followup.send("\n".join(lines), ephemeral=True)


# -------------------------------
# Quiz commands
# -------------------------------

async def handle_metrics_quiz_request(interaction: discord.Interaction, num_questions: int) -> None:
    """Shared handler for metrics quiz command and buttons."""
    num_questions = max(1, min(5, num_questions))

    if has_passed_quiz_today(interaction.user.id, quiz_type="metrics"):
        await interaction.followup.send(
            "⚠️ **Quiz Limit Reached**\n\n"
            "You've already completed the daily metrics quiz today and earned XP.\n"
            "💡 You can only earn XP from the daily quiz once per day.\n"
            "🕐 Daily limit resets at 11:59 PM UTC.\n\n"
            "You can attempt the daily quiz again tomorrow!",
            ephemeral=True,
        )
        return

    if not can_send_dm():
        await interaction.followup.send(
            "🚦 The quiz bot is currently busy. Please try again in a few minutes.",
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        "🔄 Generating quiz questions based on current Polymer metrics...",
        ephemeral=True,
    )

    questions = await generate_metrics_quiz_questions(num_questions)
    if not questions:
        await interaction.followup.send(
            "❌ Failed to generate quiz questions. Please try again later.",
            ephemeral=True,
        )
        return

    if not interaction.guild:
        await interaction.followup.send(
            "❌ This command must be used in a server.",
            ephemeral=True,
        )
        return

    metrics_role = None
    try:
        metrics_role = discord.utils.get(interaction.guild.roles, name="Metrics Quiz")
    except Exception:
        metrics_role = None

    role_to_assign = metrics_role if metrics_role else interaction.guild.default_role

    try:
        dm_channel = await interaction.user.create_dm()
        register_dm_send()

        async with thread_semaphore:
            await dm_channel.send(
                "✅ Your metrics quiz is ready! Questions are based on current Polymer network data."
            )

        required_score = max(1, int(math.ceil(len(questions) * 0.6)))

        async with thread_semaphore:
            await dm_channel.send(
                f"{interaction.user.mention} 🎯 Click below to begin your metrics quiz ({len(questions)} questions):",
                view=StartQuizButton(
                    user_id=interaction.user.id,
                    questions=questions,
                    required_score=required_score,
                    role_to_assign=role_to_assign,
                    qualifying_roles=[],
                ),
            )

        await interaction.followup.send(
            f"📩 Metrics quiz sent to your DMs! ({len(questions)} questions based on current Polymer data)",
            ephemeral=True,
        )

    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Cannot send you a DM. Please enable DMs from server members and try again.",
            ephemeral=True,
        )
    except Exception as e:
        log_or_print("error", f"[MetricsQuiz] Error: {e}", exc_info=True)
        await interaction.followup.send(
            f"⚠️ Failed to send quiz: {e}",
            ephemeral=True,
        )


@bot.tree.command(name="metrics_quiz", description="Start a quiz based on current Polymer metrics")
@app_commands.describe(
    num_questions="Number of questions (1-5, default: 3)"
)
async def metrics_quiz(interaction: discord.Interaction, num_questions: int = 3):
    await interaction.response.defer(ephemeral=True)
    await handle_metrics_quiz_request(interaction, num_questions)


@bot.tree.command(name="post_quiz_button", description="Post a quiz button for users to click.")
@app_commands.describe(
    quiz_message="The message that will appear above the button",
    num_questions="Number of questions to ask",
    required_score="Number of correct answers needed to pass",
    role_to_assign="Role to assign if user passes",
    qualifying_role="Optional role user must already have to receive reward"
)
@admin_or_role_only(get_admin_role_list)
async def post_quiz_button(interaction: discord.Interaction,
                           quiz_message: str,
                           num_questions: int,
                           required_score: int,
                           role_to_assign: discord.Role,
                           qualifying_role: Optional[discord.Role] = None):
    try:
        # Defer response immediately to prevent timeout
        await interaction.response.defer(ephemeral=True)
        
        qualifying_roles = [qualifying_role] if qualifying_role else []

        # Get quiz files with error handling
        try:
            quiz_files = [f for f in os.listdir() if f.endswith(".csv") and f != QUIZ_RESULTS_FILE and f != TWITTER_HANDLES_CSV]
        except Exception as e:
            log_or_print("error", f"[PostQuizButton] Error reading directory: {e}", exc_info=True)
            await interaction.followup.send(f"⚠️ Error reading quiz files: {e}", ephemeral=True)
            return

        if not quiz_files:
            await interaction.followup.send("⚠️ No quiz files found in the directory.", ephemeral=True)
            return

        # Discord Select menus are limited to 25 options
        MAX_SELECT_OPTIONS = 25
        if len(quiz_files) > MAX_SELECT_OPTIONS:
            # Sort and limit to first 25
            quiz_files_sorted = sorted(quiz_files)[:MAX_SELECT_OPTIONS]
            warning_msg = f"⚠️ Found {len(quiz_files)} quiz files, but Discord limits Select menus to {MAX_SELECT_OPTIONS} options. Showing first {MAX_SELECT_OPTIONS} alphabetically.\n\n"
        else:
            quiz_files_sorted = sorted(quiz_files)
            warning_msg = ""

        class FileSelect(discord.ui.Select):
            def __init__(self, files):
                options = [discord.SelectOption(label=f, value=f) for f in files]
                super().__init__(placeholder="Choose a quiz CSV...", options=options)

            async def callback(self, select_interaction: discord.Interaction):
                try:
                    await select_interaction.channel.send(
                        content=quiz_message,
                        view=QuizTriggerButtonFull(
                            quiz_file=self.values[0],
                            num_questions=num_questions,
                            required_score=required_score,
                            role_id=role_to_assign.id,
                            qualifying_roles=qualifying_roles
                        )
                    )
                    await select_interaction.response.defer()
                except Exception as e:
                    log_or_print("error", f"[PostQuizButton] Error in FileSelect callback: {e}", exc_info=True)
                    if select_interaction.response.is_done():
                        try:
                            await select_interaction.followup.send(f"⚠️ Could not post quiz button: {e}", ephemeral=True)
                        except Exception:
                            pass
                    else:
                        await select_interaction.response.send_message(f"⚠️ Could not post quiz button: {e}", ephemeral=True)

        class FileSelectView(discord.ui.View):
            def __init__(self, files):
                super().__init__(timeout=60)
                self.add_item(FileSelect(files))

        await interaction.followup.send(f"{warning_msg}📁 Select which quiz to post:", view=FileSelectView(quiz_files_sorted), ephemeral=True)
    except Exception as e:
        log_or_print("error", f"[PostQuizButton] Unexpected error: {e}", exc_info=True)
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"⚠️ An error occurred: {e}", ephemeral=True)
            else:
                await interaction.followup.send(f"⚠️ An error occurred: {e}", ephemeral=True)
        except Exception as send_error:
            log_or_print("error", f"[PostQuizButton] Failed to send error message: {send_error}", exc_info=True)


@bot.tree.command(name="clean_threads", description="Clean all threads in a channel created by this bot")
@app_commands.describe(
    target_channel="Channel to clean up threads in"
)
@admin_or_role_only(get_admin_role_list)
async def clean_threads(interaction: discord.Interaction, target_channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)

    try:
        # Fix: Use active_threads() method properly
        if hasattr(target_channel, 'threads'):
            threads = target_channel.threads
        else:
            # Fallback: get threads from guild
            threads = [t for t in target_channel.guild.threads if t.parent_id == target_channel.id]
        
        deleted = 0
        skipped = 0

        for thread in threads:
            if thread.owner_id == bot.user.id:
                try:
                    await thread.delete()
                    deleted += 1
                    await asyncio.sleep(0.5)  # Rate limit protection
                except Exception as e:
                    log_or_print("warning", f"❌ Failed to delete thread {thread.name}: {e}")
            else:
                skipped += 1

        await interaction.followup.send(
            f"🧹 Cleaned up threads in {target_channel.mention}.\n"
            f"✅ Deleted: `{deleted}`\n"
            f"🚫 Skipped (not bot-owned): `{skipped}`",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"⚠️ Failed to clean threads: {e}", ephemeral=True)


# -------------------------------
# Admin XP commands
# -------------------------------

@bot.tree.command(name="xp_admin_give", description="Give XP to a user (Admin only)")
@app_commands.describe(
    user="The user to give XP to",
    amount="Amount of XP to give"
)
@admin_or_role_only(get_admin_role_list)
async def xp_admin_give(interaction: discord.Interaction, user: discord.User, amount: int):
    await interaction.response.defer(ephemeral=True)
    
    if amount <= 0:
        await interaction.followup.send("❌ Amount must be positive.", ephemeral=True)
        return
    
    try:
        success, error_msg = add_xp(
            discord_id=user.id,
            discord_name=str(user),
            amount=amount,
            source="admin_grant",
            reference_type="admin_action",
            reference_id=str(interaction.user.id),
            notes=f"Granted by {interaction.user}",
            bypass_cap=True,
        )
        if success:
            await interaction.followup.send(
                f"✅ Granted **{amount} XP** to {user.mention}.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"⚠️ Error granting XP: {error_msg}",
                ephemeral=True
            )
    except Exception as e:
        log_or_print("error", f"[XPAdmin] Error granting XP: {e}", exc_info=True)
        await interaction.followup.send(
            f"⚠️ Error granting XP: {e}",
            ephemeral=True
        )


@bot.tree.command(name="xp_admin_give_role", description="Give XP to all members with a specific role (Admin only)")
@app_commands.describe(
    role="Role to grant XP to all members with",
    amount="Amount of XP to give to each member",
    notes="Optional notes for the XP grant",
    require_messages="Only award XP to members who have posted at least once (default: True)"
)
@admin_or_role_only(get_admin_role_list)
async def xp_admin_give_role(
    interaction: discord.Interaction, 
    role: discord.Role, 
    amount: int, 
    notes: Optional[str] = None,
    require_messages: bool = True
):
    """Give XP to all members who have a specific role."""
    await interaction.response.defer(ephemeral=True)
    
    if amount <= 0:
        await interaction.followup.send("❌ XP amount must be greater than 0.", ephemeral=True)
        return
    
    try:
        # Get all members with the role (excluding bots)
        all_members_with_role = [
            member for member in interaction.guild.members 
            if role in member.roles and not member.bot
        ]
        
        if not all_members_with_role:
            await interaction.followup.send(
                f"ℹ️ No members found with the role **{role.name}**.",
                ephemeral=True
            )
            return
        
        # Filter by activity if requested
        members_with_role = all_members_with_role
        filtered_count = 0
        
        if require_messages:
            # Create a progress message that we'll update
            progress_msg = await interaction.followup.send(
                f"🔍 **Scanning Server Activity**\n\n"
                f"Scanning channels to find members who have posted messages...\n"
                f"This may take 1-5 minutes for large servers.\n\n"
                f"⏳ Starting scan...",
                ephemeral=True
            )
            
            # Progress callback to update the message
            async def update_progress(message: str):
                try:
                    # Get current content and append new progress
                    current_content = progress_msg.content if hasattr(progress_msg, 'content') else ""
                    # Keep it concise - just show the latest status
                    new_content = f"🔍 **Scanning Server Activity**\n\n{message}"
                    await progress_msg.edit(content=new_content)
                except:
                    pass  # Ignore errors updating progress
            
            try:
                active_member_ids = await get_members_with_messages(
                    interaction.guild,
                    max_messages_per_channel=10000,
                    progress_callback=update_progress
                )
                
                # Filter members to only those who have posted
                members_with_role = [
                    member for member in all_members_with_role 
                    if member.id in active_member_ids
                ]
                
                filtered_count = len(all_members_with_role) - len(members_with_role)
                
                if filtered_count > 0:
                    log_or_print("info", f"[XPAdmin] Filtered out {filtered_count} inactive members (no messages found)")
                    
            except Exception as e:
                log_or_print("error", f"[XPAdmin] Error scanning for active members: {e}", exc_info=True)
                await progress_msg.edit(
                    content=f"⚠️ **Error scanning channels**\n\n"
                            f"Error: {str(e)}\n\n"
                            f"Proceeding with all {len(all_members_with_role)} members (no filtering applied)."
                )
                # Continue with all members if scanning fails
                members_with_role = all_members_with_role
                filtered_count = 0
        
        if not members_with_role:
            filter_note = f"\n\n(Filtered from {len(all_members_with_role)} total members - none had posted messages)" if require_messages else ""
            await interaction.followup.send(
                f"ℹ️ No active members found with the role **{role.name}**.{filter_note}",
                ephemeral=True
            )
            return
        
        total_members = len(members_with_role)
        default_notes = notes or f"Bulk XP grant for {role.name} role"
        
        # Determine batch size based on total members
        # For large operations (50k+), use larger batches to minimize API calls
        # For smaller operations, use smaller batches for faster feedback
        if total_members >= 10000:
            batch_size = 1000  # Large batches for very large operations
        elif total_members >= 1000:
            batch_size = 500   # Medium batches for large operations
        else:
            batch_size = 100   # Smaller batches for smaller operations
        
        # Calculate estimated time (conservative estimate: 1.3 seconds per batch)
        num_batches = (total_members + batch_size - 1) // batch_size
        estimated_seconds = int(num_batches * 1.3)
        estimated_time_str = f"{estimated_seconds // 60}m {estimated_seconds % 60}s" if estimated_seconds >= 60 else f"{estimated_seconds}s"
        
        # Build confirmation message
        confirmation_lines = [
            f"⚠️ **Confirm XP Grant**\n",
            f"Role: **{role.name}**",
            f"Members: **{total_members:,}**",
        ]
        
        if require_messages and filtered_count > 0:
            confirmation_lines.append(f"Filtered: **{filtered_count:,}** inactive members (no messages)")
            confirmation_lines.append(f"Total with role: **{len(all_members_with_role):,}**")
        
        confirmation_lines.extend([
            f"XP per member: **{amount} XP**",
            f"Total XP to grant: **{total_members * amount:,} XP**",
            f"Batch size: **{batch_size}** rows per API call",
            f"Estimated time: **~{estimated_time_str}**\n",
            f"⏳ Processing in batches to avoid rate limits...",
        ])
        
        # Send confirmation (or update progress message if we have one)
        if require_messages and 'progress_msg' in locals():
            try:
                await progress_msg.edit(content="\n".join(confirmation_lines))
            except:
                await interaction.followup.send("\n".join(confirmation_lines), ephemeral=True)
        else:
            await interaction.followup.send("\n".join(confirmation_lines), ephemeral=True)
        
        # Prepare all XP entries
        xp_entries = []
        for member in members_with_role:
            xp_entries.append({
                "discord_id": member.id,
                "discord_name": str(member),
                "amount": amount,
                "source": "admin_grant",
                "reference_type": "role_bulk_grant",
                "reference_id": f"role_{role.id}",
                "notes": default_notes,
            })
        
        # Send progress updates for large operations
        progress_message = None
        if total_members >= 1000:
            progress_message = await interaction.followup.send(
                f"📊 **Granting XP**\n\n"
                f"Role: **{role.name}**\n"
                f"Members: **{total_members:,}**\n"
                f"XP per member: **{amount} XP**\n"
                f"Batch size: **{batch_size}**\n\n"
                f"⏳ Starting... (0/{total_members:,})",
                ephemeral=True
            )
        
        # Ensure xp_totals sheet has enough rows BEFORE adding XP
        # This prevents "Result was not automatically expanded" errors
        # Estimate: ensure sheet can handle all potential unique users
        try:
            await ensure_xp_totals_sheet_size(min_rows=max(10000, total_members + 5000))
        except Exception as e:
            # Log but continue - expansion is best-effort
            if logger:
                logger.warning(f"[XPAdmin] Could not pre-expand xp_totals sheet: {e}")
        
        # Create progress callback for batch_add_xp
        def grant_progress_callback(current: int, total: int, batch_num: int):
            """Sync progress callback that schedules async message updates."""
            if progress_message and total_members >= 1000:
                try:
                    percentage = (current / total) * 100 if total > 0 else 0
                    num_batches = (total + batch_size - 1) // batch_size
                    content = (
                        f"📊 **Granting XP**\n\n"
                        f"Role: **{role.name}**\n"
                        f"Members: **{total:,}**\n"
                        f"XP per member: **{amount} XP**\n"
                        f"Batch size: **{batch_size}**\n\n"
                        f"⏳ Progress: {current:,}/{total:,} ({percentage:.1f}%)\n"
                        f"Batch: {batch_num}/{num_batches}"
                    )
                    # Schedule async update (fire and forget)
                    async def update_msg():
                        try:
                            await progress_message.edit(content=content)
                        except:
                            pass
                    asyncio.create_task(update_msg())
                except:
                    pass
        
        # Batch add XP with progress updates
        success_count, error_count, error_messages = await batch_add_xp(
            xp_entries,
            batch_size=batch_size,
            progress_callback=grant_progress_callback if total_members >= 1000 else None
        )
        
        # Update progress message if we sent one
        if progress_message:
            try:
                await progress_message.edit(
                    content=f"📊 **Granting XP**\n\n"
                            f"✅ Completed processing {total_members:,} entries!"
                )
            except:
                pass  # Message might have been deleted or edited
        
        # Send summary
        summary_lines = [
            f"✅ **XP Grant Complete**\n",
            f"Role: **{role.name}**",
            f"XP per member: **{amount} XP**\n",
            f"📊 **Results:**",
            f"• ✅ Successfully granted: **{success_count:,}** members",
        ]
        
        if require_messages and filtered_count > 0:
            summary_lines.append(f"• 🔍 Filtered out: **{filtered_count:,}** inactive members (no messages)")
        
        if error_count > 0:
            summary_lines.append(f"• ❌ Errors: **{error_count:,}** members")
            if error_messages and len(error_messages) <= 5:
                summary_lines.append(f"\n**Error details:**")
                for msg in error_messages:
                    summary_lines.append(f"• {msg}")
            elif error_messages:
                summary_lines.append(f"\n**First 5 errors:**")
                for msg in error_messages[:5]:
                    summary_lines.append(f"• {msg}")
                summary_lines.append(f"• ... and {len(error_messages) - 5} more errors")
        
        summary_text = "\n".join(summary_lines)
        # Discord message limit is 2000 characters
        if len(summary_text) > 2000:
            summary_text = summary_text[:1950] + "\n\n... (truncated)"
        
        await interaction.followup.send(summary_text, ephemeral=True)
        
    except Exception as e:
        if logger:
            logger.error(f"[XPAdmin] Error in bulk role XP grant: {e}", exc_info=True)
        await interaction.followup.send(
            f"❌ Error granting XP: {e}",
            ephemeral=True
        )


@bot.tree.command(name="xp_admin_verify_role", description="Verify and optionally repair XP grants for a role (Admin only)")
@app_commands.describe(
    role="Role to verify XP grants for",
    amount="Amount of XP that should have been granted",
    notes="Optional notes to match (leave empty to match any notes)",
    repair="If True, grant XP to members who are missing it (default: False)",
    require_messages="Only check members who have posted at least once (default: True)"
)
@admin_or_role_only(get_admin_role_list)
async def xp_admin_verify_role(
    interaction: discord.Interaction,
    role: discord.Role,
    amount: int,
    notes: Optional[str] = None,
    repair: bool = False,
    require_messages: bool = True
):
    """Verify that all members with a role received XP from a previous grant, and optionally repair missing grants."""
    await interaction.response.defer(ephemeral=True)
    
    # Helper function to safely send followup messages (fallback to channel if token expires)
    async def safe_followup_send(content: str, ephemeral: bool = True):
        """Send followup message, falling back to channel if token expired."""
        try:
            await interaction.followup.send(content, ephemeral=ephemeral)
        except discord.HTTPException as e:
            # Interaction token expired - send to channel instead
            if "Invalid Webhook Token" in str(e) or "50027" in str(e) or "Unauthorized" in str(e):
                try:
                    if ephemeral:
                        # For ephemeral messages, mention user and send to channel
                        await interaction.channel.send(f"{interaction.user.mention}\n\n{content}")
                    else:
                        await interaction.channel.send(content)
                except Exception as channel_error:
                    log_or_print("error", f"[XPAdminVerify] Could not send to channel: {channel_error}")
            else:
                raise
    
    if amount <= 0:
        await safe_followup_send("❌ XP amount must be greater than 0.", ephemeral=True)
        return
    
    try:
        # Get all members with the role (excluding bots)
        all_members_with_role = [
            member for member in interaction.guild.members 
            if role in member.roles and not member.bot
        ]
        
        if not all_members_with_role:
            await safe_followup_send(
                f"ℹ️ No members found with the role **{role.name}**.",
                ephemeral=True
            )
            return
        
        # Filter by activity if requested
        members_with_role = all_members_with_role
        filtered_count = 0
        
        if require_messages:
            log_or_print("info", f"[XPAdminVerify] Starting channel scan to find active members...")
            
            # Track last update time for console logging
            last_progress_update = [time.time()]
            progress_update_interval = 10.0  # Update every 10 seconds
            last_percentage = [0]
            
            async def update_progress(message: str):
                try:
                    current_time = time.time()
                    # Log to console every 10 seconds or on significant milestones
                    time_since_update = current_time - last_progress_update[0]
                    if time_since_update >= progress_update_interval:
                        log_or_print("info", f"[XPAdminVerify] Channel scan: {message}")
                        last_progress_update[0] = current_time
                    else:
                        # Still log important milestones (like completion)
                        if "✅" in message or "Found" in message:
                            log_or_print("info", f"[XPAdminVerify] Channel scan: {message}")
                except Exception as e:
                    log_or_print("error", f"[XPAdminVerify] Error in update_progress: {e}", exc_info=True)
            
            try:
                active_member_ids = await get_members_with_messages(
                    interaction.guild,
                    max_messages_per_channel=10000,
                    progress_callback=update_progress
                )
                
                members_with_role = [
                    member for member in all_members_with_role 
                    if member.id in active_member_ids
                ]
                
                filtered_count = len(all_members_with_role) - len(members_with_role)
                
                if filtered_count > 0:
                    log_or_print("info", f"[XPAdminVerify] Filtered out {filtered_count} inactive members (no messages found)")
                    
            except Exception as e:
                log_or_print("error", f"[XPAdminVerify] Error scanning for active members: {e}", exc_info=True)
                log_or_print("warning", f"[XPAdminVerify] Proceeding with all {len(all_members_with_role)} members (no filtering applied)")
                await safe_followup_send(
                    f"⚠️ Error scanning channels: {str(e)}\n\nProceeding with all {len(all_members_with_role)} members.",
                    ephemeral=True
                )
                members_with_role = all_members_with_role
                filtered_count = 0
        
        if not members_with_role:
            filter_note = f"\n\n(Filtered from {len(all_members_with_role)} total members - none had posted messages)" if require_messages else ""
            await safe_followup_send(
                f"ℹ️ No active members found with the role **{role.name}**.{filter_note}",
                ephemeral=True
            )
            return
        
        # Read XP events to find matching grants
        log_or_print("info", f"[XPAdminVerify] Starting verification - Role: {role.name}, Amount: {amount} XP, Members: {len(members_with_role):,}")
        
        # Track last update time for console logging
        last_verify_update = [time.time()]
        verify_update_interval = 10.0  # Update every 10 seconds
        last_percentage = [0]
        
        async def update_verify_progress(message: str):
            """Log progress to console."""
            try:
                current_time = time.time()
                # Log to console every 10 seconds or on significant milestones
                time_since_update = current_time - last_verify_update[0]
                if time_since_update >= verify_update_interval:
                    log_or_print("info", f"[XPAdminVerify] {message}")
                    last_verify_update[0] = current_time
                else:
                    # Still log important milestones
                    if "✅" in message or "Complete" in message or "Error" in message:
                        log_or_print("info", f"[XPAdminVerify] {message}")
            except Exception as e:
                log_or_print("error", f"[XPAdminVerify] Error in update_verify_progress: {e}", exc_info=True)
        
        try:
            log_or_print("info", f"[XPAdminVerify] Reading XP events from sheet...")
            await throttle_sheets_api()
            ws_events = await retry_with_backoff(
                lambda: asyncio.to_thread(get_xp_events_ws),
                max_retries=3,
                initial_delay=1.0,
            )
            
            await throttle_sheets_api()
            rows = await retry_with_backoff(
                lambda: asyncio.to_thread(ws_events.get_all_values),
                max_retries=3,
                initial_delay=1.0,
            )
            log_or_print("info", f"[XPAdminVerify] Read {len(rows)} rows from XP events sheet")
        except Exception as e:
            log_or_print("error", f"[XPAdminVerify] Error reading xp_events: {e}", exc_info=True)
            await safe_followup_send(
                f"❌ Error reading XP events: {str(e)}",
                ephemeral=True
            )
            return
        
        if not rows or len(rows) < 2:
            await safe_followup_send(
                "❌ No XP events found in the sheet.",
                ephemeral=True
            )
            return
        
        # Find column indices
        header = rows[0]
        discord_id_col = None
        source_col = None
        amount_col = None
        reference_type_col = None
        reference_id_col = None
        notes_col = None
        
        for idx, col_name in enumerate(header):
            col_lower = col_name.lower()
            if "discord_id" in col_lower or (col_name == "ID" and discord_id_col is None):
                discord_id_col = idx
            elif "source" in col_lower:
                source_col = idx
            elif "amount" in col_lower or "xp" in col_lower:
                amount_col = idx
            elif "reference_type" in col_lower:
                reference_type_col = idx
            elif "reference_id" in col_lower:
                reference_id_col = idx
            elif "notes" in col_lower:
                notes_col = idx
        
        if discord_id_col is None or source_col is None or amount_col is None:
            await interaction.followup.send(
                "❌ Could not find required columns in xp_events sheet.",
                ephemeral=True
            )
            return
        
        # Expected values for matching
        expected_source = "admin_grant"
        expected_reference_type = "role_bulk_grant"
        expected_reference_id = f"role_{role.id}"
        expected_amount = amount
        
        # Find members who received the XP grant
        members_with_xp = set()
        total_rows = len(rows) - 1  # Exclude header
        rows_processed = 0
        last_update_time = time.time()
        update_interval = 10.0  # Update every 10 seconds
        last_percentage = 0  # Track last logged percentage (every 10%)
        
        log_or_print("info", f"[XPAdminVerify] Processing {total_rows:,} XP event rows...")
        
        for row in rows[1:]:
            rows_processed += 1
            current_time = time.time()
            
            # Update progress every 10 seconds or every 10% of rows
            percentage = (rows_processed / total_rows) * 100
            current_percentage_10 = int(percentage // 10) * 10  # Round down to nearest 10%
            should_update = (
                (current_time - last_update_time >= update_interval) or 
                (current_percentage_10 > last_percentage) or
                (rows_processed == 1)  # Always update on first row
            )
            
            if should_update:
                log_or_print("info", f"[XPAdminVerify] Processing rows: {rows_processed:,}/{total_rows:,} ({percentage:.1f}%)")
                last_update_time = current_time
                last_percentage = current_percentage_10
            if len(row) <= max(discord_id_col, source_col, amount_col, 
                              reference_type_col if reference_type_col is not None else 0,
                              reference_id_col if reference_id_col is not None else 0):
                continue
            
            row_discord_id = row[discord_id_col].strip()
            row_source = row[source_col].strip() if len(row) > source_col else ""
            row_amount = row[amount_col].strip() if len(row) > amount_col else ""
            row_reference_type = row[reference_type_col].strip() if reference_type_col is not None and len(row) > reference_type_col else ""
            row_reference_id = row[reference_id_col].strip() if reference_id_col is not None and len(row) > reference_id_col else ""
            row_notes = row[notes_col].strip() if notes_col is not None and len(row) > notes_col else ""
            
            # Check if this row matches our criteria
            if (row_source == expected_source and
                row_reference_type == expected_reference_type and
                row_reference_id == expected_reference_id):
                
                try:
                    row_amount_int = int(row_amount)
                    if row_amount_int == expected_amount:
                        # If notes were specified, check if they match
                        if notes is None or notes.strip() == "" or row_notes == notes:
                            members_with_xp.add(row_discord_id)
                except (ValueError, TypeError):
                    continue
        
        # Find members missing XP
        members_missing_xp = []
        for member in members_with_role:
            if str(member.id) not in members_with_xp:
                members_missing_xp.append(member)
        
        # Build report
        report_lines = [
            f"📊 **XP Grant Verification Report**\n",
            f"Role: **{role.name}**",
            f"Expected amount: **{amount} XP**",
            f"Expected notes: **{notes or '(any notes)'}**\n",
            f"**Results:**",
            f"• Total members with role: **{len(all_members_with_role):,}**",
        ]
        
        if require_messages and filtered_count > 0:
            report_lines.append(f"• Filtered (inactive): **{filtered_count:,}**")
        
        report_lines.extend([
            f"• Members checked: **{len(members_with_role):,}**",
            f"• ✅ Members with XP: **{len(members_with_xp):,}**",
            f"• ❌ Members missing XP: **{len(members_missing_xp):,}**",
        ])
        
        if members_missing_xp:
            report_lines.append(f"\n**Missing XP Members:**")
            # Show first 20 missing members
            for i, member in enumerate(members_missing_xp[:20], 1):
                report_lines.append(f"{i}. {member.display_name} ({member.id})")
            
            if len(members_missing_xp) > 20:
                report_lines.append(f"... and {len(members_missing_xp) - 20} more members")
        
        if repair and members_missing_xp:
            report_lines.append(f"\n🔧 **Repairing...**")
            report_lines.append(f"Granting {amount} XP to {len(members_missing_xp):,} missing members...")
            
            # Prepare XP entries for missing members
            default_notes = notes or f"Bulk XP grant for {role.name} role (repair)"
            xp_entries = []
            for member in members_missing_xp:
                xp_entries.append({
                    "discord_id": member.id,
                    "discord_name": str(member),
                    "amount": amount,
                    "source": "admin_grant",
                    "reference_type": "role_bulk_grant",
                    "reference_id": f"role_{role.id}",
                    "notes": default_notes,
                })
            
            # Determine batch size
            total_members = len(members_missing_xp)
            if total_members >= 10000:
                batch_size = 1000
            elif total_members >= 1000:
                batch_size = 500
            else:
                batch_size = 100
            
            # Ensure xp_totals sheet has enough rows
            try:
                await ensure_xp_totals_sheet_size(min_rows=max(10000, total_members + 5000))
            except Exception as e:
                if logger:
                    logger.warning(f"[XPAdminVerify] Could not pre-expand xp_totals sheet: {e}")
            
            # Grant XP to missing members with progress updates
            log_or_print("info", f"[XPAdminVerify] Starting repair: granting {amount} XP to {total_members:,} missing members (batch size: {batch_size})")
            
            # Track progress for console logging
            repair_last_update = [time.time()]
            repair_last_percentage = [0]
            repair_update_interval = 10.0  # Update every 10 seconds
            
            def repair_progress_callback(current: int, total: int, batch_num: int):
                """Sync progress callback that logs to console."""
                try:
                    current_time = time.time()
                    percentage = (current / total) * 100 if total > 0 else 0
                    current_percentage_10 = int(percentage // 10) * 10
                    num_batches = (total + batch_size - 1) // batch_size
                    
                    # Log every 10 seconds or every 10% progress
                    time_since_update = current_time - repair_last_update[0]
                    should_log = (
                        time_since_update >= repair_update_interval or
                        current_percentage_10 > repair_last_percentage[0] or
                        current == total  # Always log completion
                    )
                    
                    if should_log:
                        log_or_print("info", f"[XPAdminVerify] Repair progress: {current:,}/{total:,} ({percentage:.1f}%) - Batch {batch_num}/{num_batches}")
                        repair_last_update[0] = current_time
                        repair_last_percentage[0] = current_percentage_10
                except:
                    pass
            
            success_count, error_count, error_messages = await batch_add_xp(
                xp_entries,
                batch_size=batch_size,
                progress_callback=repair_progress_callback
            )
            
            log_or_print("info", f"[XPAdminVerify] Repair complete: {success_count:,} successful, {error_count:,} errors")
            
            report_lines.append(f"\n**Repair Results:**")
            report_lines.append(f"• ✅ Successfully granted: **{success_count:,}** members")
            if error_count > 0:
                report_lines.append(f"• ❌ Errors: **{error_count:,}** members")
                if error_messages and len(error_messages) <= 5:
                    report_lines.append(f"\n**Error details:**")
                    for msg in error_messages:
                        report_lines.append(f"• {msg}")
                elif error_messages:
                    report_lines.append(f"\n**First 5 errors:**")
                    for msg in error_messages[:5]:
                        report_lines.append(f"• {msg}")
                    report_lines.append(f"• ... and {len(error_messages) - 5} more errors")
        elif repair:
            report_lines.append(f"\n✅ **No repair needed** - all members have the expected XP!")
        
        report_text = "\n".join(report_lines)
        # Discord message limit is 2000 characters
        if len(report_text) > 2000:
            # Truncate but keep the summary
            summary_part = "\n".join(report_lines[:10])
            if members_missing_xp:
                summary_part += f"\n\n... (showing first 20 of {len(members_missing_xp)} missing members)"
            if repair and members_missing_xp:
                summary_part += "\n\n" + "\n".join([line for line in report_lines if "Repair Results" in line or "✅ Successfully" in line or "❌ Errors" in line])
            report_text = summary_part
        
        await safe_followup_send(report_text, ephemeral=True)
        
    except Exception as e:
        if logger:
            logger.error(f"[XPAdminVerify] Error verifying XP grants: {e}", exc_info=True)
        try:
            await safe_followup_send(
                f"❌ Error verifying XP grants: {str(e)}",
                ephemeral=True
            )
        except:
            # Last resort - log the error
            log_or_print("error", f"[XPAdminVerify] Could not send error message to user: {e}")


@bot.tree.command(name="xp_admin_check_user", description="Check if a specific user received XP for a role grant (Admin only)")
@app_commands.describe(
    user="User to check",
    role="Role to check XP grant for (optional - checks all role grants if not specified)",
    amount="Expected XP amount (optional - helps narrow down which grant to check)",
    notes="Expected notes (optional - helps narrow down which grant to check)"
)
@admin_or_role_only(get_admin_role_list)
async def xp_admin_check_user(
    interaction: discord.Interaction,
    user: discord.User,
    role: Optional[discord.Role] = None,
    amount: Optional[int] = None,
    notes: Optional[str] = None
):
    """Check if a specific user received XP for a role grant and explain why they did/didn't receive it."""
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Get the member object
        member = interaction.guild.get_member(user.id)
        if not member:
            await interaction.followup.send(
                f"❌ User {user.mention} is not a member of this server.",
                ephemeral=True
            )
            return
        
        # Check if user has the role (if role was specified)
        has_role = True
        if role:
            has_role = role in member.roles
            if not has_role:
                await interaction.followup.send(
                    f"ℹ️ **User Role Check**\n\n"
                    f"User: {user.mention} ({user.id})\n"
                    f"Role: **{role.name}**\n\n"
                    f"❌ User does **not** have this role.\n\n"
                    f"**Why they didn't receive XP:**\n"
                    f"• User must have the role to receive role-based XP grants.",
                    ephemeral=True
                )
                return
        
        # Read XP events
        await interaction.followup.send(
            f"🔍 **Checking XP Grants**\n\n"
            f"User: {user.mention}\n"
            f"Role: **{role.name if role else 'Any role'}**\n"
            f"⏳ Reading XP events...",
            ephemeral=True
        )
        
        try:
            await throttle_sheets_api()
            ws_events = await retry_with_backoff(
                lambda: asyncio.to_thread(get_xp_events_ws),
                max_retries=3,
                initial_delay=1.0,
            )
            
            await throttle_sheets_api()
            rows = await retry_with_backoff(
                lambda: asyncio.to_thread(ws_events.get_all_values),
                max_retries=3,
                initial_delay=1.0,
            )
        except Exception as e:
            log_or_print("error", f"[XPAdminCheckUser] Error reading xp_events: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error reading XP events: {str(e)}",
                ephemeral=True
            )
            return
        
        if not rows or len(rows) < 2:
            await interaction.followup.send(
                "❌ No XP events found in the sheet.",
                ephemeral=True
            )
            return
        
        # Find column indices
        header = rows[0]
        discord_id_col = None
        source_col = None
        amount_col = None
        reference_type_col = None
        reference_id_col = None
        notes_col = None
        timestamp_col = None
        
        for idx, col_name in enumerate(header):
            col_lower = col_name.lower()
            if "discord_id" in col_lower or (col_name == "ID" and discord_id_col is None):
                discord_id_col = idx
            elif "source" in col_lower:
                source_col = idx
            elif "amount" in col_lower or "xp" in col_lower:
                amount_col = idx
            elif "reference_type" in col_lower:
                reference_type_col = idx
            elif "reference_id" in col_lower:
                reference_id_col = idx
            elif "notes" in col_lower:
                notes_col = idx
            elif "timestamp" in col_lower or "date" in col_lower or "time" in col_lower:
                timestamp_col = idx
        
        if discord_id_col is None or source_col is None or amount_col is None:
            await interaction.followup.send(
                "❌ Could not find required columns in xp_events sheet.",
                ephemeral=True
            )
            return
        
        user_id_str = str(user.id)
        
        # Find all admin_grant XP events for this user
        matching_grants = []
        all_admin_grants = []
        
        for row in rows[1:]:
            if len(row) <= max(discord_id_col, source_col, amount_col):
                continue
            
            row_discord_id = row[discord_id_col].strip()
            if row_discord_id != user_id_str:
                continue
            
            row_source = row[source_col].strip() if len(row) > source_col else ""
            row_amount = row[amount_col].strip() if len(row) > amount_col else ""
            row_reference_type = row[reference_type_col].strip() if reference_type_col is not None and len(row) > reference_type_col else ""
            row_reference_id = row[reference_id_col].strip() if reference_id_col is not None and len(row) > reference_id_col else ""
            row_notes = row[notes_col].strip() if notes_col is not None and len(row) > notes_col else ""
            row_timestamp = row[timestamp_col].strip() if timestamp_col is not None and len(row) > timestamp_col else ""
            
            # Collect all admin grants for reference
            if row_source == "admin_grant":
                try:
                    grant_amount = int(row_amount)
                    all_admin_grants.append({
                        "amount": grant_amount,
                        "reference_type": row_reference_type,
                        "reference_id": row_reference_id,
                        "notes": row_notes,
                        "timestamp": row_timestamp,
                    })
                except (ValueError, TypeError):
                    continue
            
            # Check if this matches our criteria
            if row_source != "admin_grant":
                continue
            
            if row_reference_type != "role_bulk_grant":
                continue
            
            # If role specified, check reference_id matches
            if role:
                expected_reference_id = f"role_{role.id}"
                if row_reference_id != expected_reference_id:
                    continue
            
            # If amount specified, check it matches
            if amount is not None:
                try:
                    grant_amount = int(row_amount)
                    if grant_amount != amount:
                        continue
                except (ValueError, TypeError):
                    continue
            
            # If notes specified, check they match
            if notes is not None and notes.strip() != "":
                if row_notes != notes:
                    continue
            
            # This is a matching grant
            try:
                grant_amount = int(row_amount)
                matching_grants.append({
                    "amount": grant_amount,
                    "reference_id": row_reference_id,
                    "notes": row_notes,
                    "timestamp": row_timestamp,
                })
            except (ValueError, TypeError):
                continue
        
        # Build response
        response_lines = [
            f"📊 **XP Grant Check for {user.display_name}**\n",
            f"User: {user.mention} ({user.id})\n",
        ]
        
        if role:
            response_lines.append(f"Role: **{role.name}**")
            response_lines.append(f"Has role: {'✅ Yes' if has_role else '❌ No'}\n")
        else:
            response_lines.append("Role: **Any role** (checking all role grants)\n")
        
        if matching_grants:
            response_lines.append(f"✅ **Found {len(matching_grants)} matching XP grant(s):**\n")
            for i, grant in enumerate(matching_grants, 1):
                role_id_from_ref = grant["reference_id"].replace("role_", "") if grant["reference_id"].startswith("role_") else "Unknown"
                role_name = "Unknown"
                if role_id_from_ref != "Unknown":
                    try:
                        role_obj = interaction.guild.get_role(int(role_id_from_ref))
                        if role_obj:
                            role_name = role_obj.name
                    except (ValueError, TypeError):
                        pass
                
                timestamp_str = grant["timestamp"][:19] if grant["timestamp"] else "Unknown date"
                response_lines.append(
                    f"**Grant #{i}:**\n"
                    f"• Amount: **{grant['amount']} XP**\n"
                    f"• Role: **{role_name}** (ID: {role_id_from_ref})\n"
                    f"• Date: {timestamp_str}\n"
                    f"• Notes: {grant['notes'] or '(no notes)'}\n"
                )
        else:
            response_lines.append("❌ **No matching XP grant found.**\n")
            
            # Enhanced diagnostics
            reasons = []
            diagnostic_info = []
            
            if role and not has_role:
                reasons.append("• User does not have the specified role")
                reasons.append("  → User must have the role to receive role-based XP grants")
            elif role:
                reasons.append(f"• User has the role **{role.name}**, but no matching XP grant found")
                if amount:
                    reasons.append(f"• Expected amount: **{amount} XP**")
                if notes:
                    reasons.append(f"• Expected notes: **{notes}**")
                
                # Check user's message count (diagnostic for require_messages filtering)
                try:
                    current_message_count = await count_discord_messages_for_user(
                        interaction.guild,
                        user.id,
                        max_messages_per_channel=10000
                    )
                    min_posts_required = get_min_discord_posts()
                    
                    diagnostic_info.append(f"\n**📊 Message Activity Check:**")
                    diagnostic_info.append(f"• Current message count: **{current_message_count}** posts")
                    diagnostic_info.append(f"• Minimum required (for quiz XP): **{min_posts_required}+** posts")
                    
                    if current_message_count == 0:
                        diagnostic_info.append(f"⚠️ **User has 0 messages**")
                        reasons.append("• **Most likely reason:** User was filtered out by `require_messages=True`")
                        reasons.append("  → `/xp_admin_give_role` defaults to only grant XP to users who have posted messages")
                        reasons.append("  → If user had 0 messages when the grant was run, they were excluded")
                    elif current_message_count < min_posts_required:
                        diagnostic_info.append(f"⚠️ User has fewer than {min_posts_required} posts")
                        diagnostic_info.append(f"  → This may have affected eligibility, but grant filtering is based on any messages (not minimum)")
                    else:
                        diagnostic_info.append(f"✅ User has sufficient message activity")
                        diagnostic_info.append(f"  → Message count is not the issue")
                except Exception as e:
                    log_or_print("warning", f"[XPAdminCheckUser] Error checking message count: {e}")
                    diagnostic_info.append(f"\n**📊 Message Activity Check:**")
                    diagnostic_info.append(f"⚠️ Could not check message count: {str(e)[:100]}")
            
            # Check if they have any admin grants
            if all_admin_grants:
                role_grants = [g for g in all_admin_grants if g["reference_type"] == "role_bulk_grant"]
                if role_grants:
                    diagnostic_info.append(f"\n**📋 Other Role Grants Found:** {len(role_grants)}")
                    for grant in role_grants[:3]:  # Show first 3
                        role_id_from_ref = grant["reference_id"].replace("role_", "") if grant["reference_id"].startswith("role_") else "Unknown"
                        role_name = "Unknown"
                        if role_id_from_ref != "Unknown":
                            try:
                                role_obj = interaction.guild.get_role(int(role_id_from_ref))
                                if role_obj:
                                    role_name = role_obj.name
                            except (ValueError, TypeError):
                                pass
                        timestamp_str = grant["timestamp"][:19] if grant["timestamp"] else "Unknown date"
                        diagnostic_info.append(f"  • {grant['amount']} XP for **{role_name}** on {timestamp_str}")
                        diagnostic_info.append(f"    Notes: {grant['notes'] or 'no notes'}")
                    if len(role_grants) > 3:
                        diagnostic_info.append(f"  • ... and {len(role_grants) - 3} more")
                    
                    # Check timing - did they get the role before or after other grants?
                    if role:
                        diagnostic_info.append(f"\n**⏰ Timing Analysis:**")
                        diagnostic_info.append(f"• User received {len(role_grants)} other role grant(s)")
                        diagnostic_info.append(f"• If user got role **{role.name}** AFTER the grant was run, they wouldn't have received it")
                        diagnostic_info.append(f"• Check when user received the role vs when grants were executed")
                else:
                    reasons.append("• User has admin grants, but none are role-based grants")
            else:
                reasons.append("• User has no admin_grant XP events at all")
                diagnostic_info.append(f"\n**📋 Grant History:**")
                diagnostic_info.append(f"• No admin grants found in XP events")
                diagnostic_info.append(f"• This could mean:")
                diagnostic_info.append(f"  → Grant was never run for this role")
                diagnostic_info.append(f"  → User was filtered out (e.g., no messages)")
                diagnostic_info.append(f"  → User didn't have the role when grant was executed")
            
            # Add diagnostic info before reasons
            if diagnostic_info:
                response_lines.extend(diagnostic_info)
            
            if reasons:
                response_lines.append(f"\n**🔍 Possible Reasons:**")
                response_lines.extend(reasons)
            
            # Add helpful suggestions
            if role and has_role:
                response_lines.append(f"\n**💡 Next Steps:**")
                response_lines.append(f"• Check if `/xp_admin_give_role` was run with `require_messages: True` (default)")
                response_lines.append(f"• Verify when user received the role (before or after grant execution)")
                response_lines.append(f"• Use `/xp_admin_give_role` with `require_messages: False` to grant to all role members")
                response_lines.append(f"• Or use `/xp_admin_verify_role` with `repair: True` to grant missing XP")
        
        response_text = "\n".join(response_lines)
        
        # Discord message limit is 2000 characters
        if len(response_text) > 2000:
            # Truncate but keep the important parts
            summary = "\n".join(response_lines[:15])
            if len(response_lines) > 15:
                summary += f"\n\n... (truncated, {len(response_lines) - 15} more lines)"
            response_text = summary
        
        await interaction.followup.send(response_text, ephemeral=True)
        
    except Exception as e:
        log_or_print("error", f"[XPAdminCheckUser] Error: {e}", exc_info=True)
        await interaction.followup.send(
            f"❌ Error checking user XP: {str(e)}",
            ephemeral=True
        )


@bot.tree.command(name="xp_admin_remove", description="Remove XP from a user (Admin only)")
@app_commands.describe(
    user="The user to remove XP from",
    amount="Amount of XP to remove"
)
@admin_or_role_only(get_admin_role_list)
async def xp_admin_remove(interaction: discord.Interaction, user: discord.User, amount: int):
    await interaction.response.defer(ephemeral=True)
    
    if amount <= 0:
        await interaction.followup.send("❌ Amount must be positive.", ephemeral=True)
        return
    
    try:
        # Add negative XP to remove (bypass cap for admin actions)
        success, error_msg = add_xp(
            discord_id=user.id,
            discord_name=str(user),
            amount=-amount,
            source="admin_removal",
            reference_type="admin_action",
            reference_id=str(interaction.user.id),
            notes=f"Removed by {interaction.user}",
            bypass_cap=True,
        )
        if success:
            await interaction.followup.send(
                f"✅ Removed **{amount} XP** from {user.mention}.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"⚠️ Error removing XP: {error_msg}",
                ephemeral=True
            )
    except Exception as e:
        log_or_print("error", f"[XPAdmin] Error removing XP: {e}", exc_info=True)
        await interaction.followup.send(
            f"⚠️ Error removing XP: {e}",
            ephemeral=True
        )


@bot.tree.command(name="xp_migrate_check", description="Check how many old leaderboard entries match registered Twitter handles (Admin only)")
@app_commands.describe(
    csv_file="Name of the CSV file (must be in bot directory)"
)
@admin_or_role_only(get_admin_role_list)
async def xp_migrate_check(interaction: discord.Interaction, csv_file: str):
    """Cross-reference old leaderboard with twitter_handles.csv to see match rates."""
    await interaction.response.defer(ephemeral=True)
    
    # Clean up the filename - remove quotes and whitespace
    csv_file = csv_file.strip().strip('"').strip("'")
    
    # Ensure the file path is relative to the bot directory
    if not os.path.isabs(csv_file):
        csv_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), csv_file)
    
    # Check if file exists
    if not os.path.exists(csv_file):
        await interaction.followup.send(
            f"❌ CSV file not found: `{csv_file}`\n"
            f"💡 Make sure the file is in the bot directory and the filename is correct.",
            ephemeral=True
        )
        return
    
    try:
        stats = cross_reference_leaderboard_with_handles(csv_file)
        
        lines = [
            f"📊 **Cross-Reference Report**",
            f"Total entries in old leaderboard: **{stats['total_old_entries']}**",
            f"✅ Matched in twitter_handles.csv: **{stats['matched_by_twitter']}** ({stats['matched_by_twitter']/stats['total_old_entries']*100:.1f}%)",
            f"❌ Not in twitter_handles.csv: **{len(stats['not_in_handles_csv'])}** ({len(stats['not_in_handles_csv'])/stats['total_old_entries']*100:.1f}%)",
        ]
        
        if stats['in_handles_csv']:
            lines.append(f"\n✅ **Found in twitter_handles.csv ({len(stats['in_handles_csv'])}):**")
            for entry in stats['in_handles_csv'][:10]:
                lines.append(f"  - {entry['username']} (@{entry['twitter']}) - {entry['xp']} XP")
            if len(stats['in_handles_csv']) > 10:
                lines.append(f"  ... and {len(stats['in_handles_csv']) - 10} more")
        
        if stats['not_in_handles_csv']:
            lines.append(f"\n❌ **Not in twitter_handles.csv ({len(stats['not_in_handles_csv'])}):**")
            for entry in stats['not_in_handles_csv'][:10]:
                lines.append(f"  - {entry['username']} (@{entry['twitter']}) - {entry['xp']} XP")
            if len(stats['not_in_handles_csv']) > 10:
                lines.append(f"  ... and {len(stats['not_in_handles_csv']) - 10} more")
        
        lines.append(f"\n💡 Use `/xp_migrate_historical` to run the actual migration.")
        
        await interaction.followup.send("\n".join(lines), ephemeral=True)
        
    except Exception as e:
        log_or_print("error", f"[Migration] Error: {e}", exc_info=True)
        await interaction.followup.send(
            f"❌ Check failed: {e}",
            ephemeral=True
        )


@bot.tree.command(name="fix_quiz_bots", description="Remove XP from users with <3 Discord posts who earned quiz XP (Admin only)")
@admin_or_role_only(get_admin_role_list)
@app_commands.describe(
    execute="Actually remove XP events (default is dry run)",
)
async def fix_quiz_bots(interaction: discord.Interaction, execute: bool = False):
    """Remove XP from users who earned quiz XP but have <3 Discord posts.
    
    This is a retroactive fix for the bot detection system.
    """
    await interaction.response.defer(ephemeral=True)
    
    if not interaction.guild:
        await interaction.followup.send("❌ This command must be run in a server.", ephemeral=True)
        return
    
    async def send_update(msg: str):
        try:
            await interaction.followup.send(msg, ephemeral=True)
        except Exception:
            pass  # Ignore errors if message is too long or rate limited
    
    cache_file = "fix_quiz_bots_cache.json"
    csv_file = f"fix_quiz_bots_results_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    
    # Check for cached dry run data if executing
    cached_data = None
    if execute:
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    await send_update(f"📦 Found cached dry run data from {cached_data.get('timestamp', 'unknown')}. Using cached results...")
        except Exception as e:
            log_or_print("warning", f"[FixQuizBots] Error loading cache: {e}")
    
    await send_update(f"🔍 Starting {'EXECUTION' if execute else 'DRY RUN'} mode...")
    
    # Get XP events sheet
    try:
        ws = get_xp_events_ws()
        rows = ws.get_all_values()
    except Exception as e:
        await interaction.followup.send(f"❌ Error accessing xp_events sheet: {e}", ephemeral=True)
        return
    
    if not rows or len(rows) < 2:
        await interaction.followup.send("No XP events found.", ephemeral=True)
        return
    
    header = rows[0]
    
    # Find column indices
    discord_id_col = None
    source_col = None
    amount_col = None
    
    for idx, col_name in enumerate(header):
        col_lower = col_name.lower()
        if "discord_id" in col_lower or (col_name == "ID" and discord_id_col is None):
            discord_id_col = idx
        elif "source" in col_lower:
            source_col = idx
        elif "amount" in col_lower or "xp" in col_lower:
            amount_col = idx
    
    if discord_id_col is None or source_col is None:
        await interaction.followup.send("❌ Error: Could not find required columns in xp_events sheet.", ephemeral=True)
        return
    
    # Use cached data if available and executing
    if cached_data and execute:
        events_to_remove = [e for e in cached_data.get("events_to_remove", [])]
        checked_users = {int(k): tuple(v) for k, v in cached_data.get("checked_users", {}).items()}
        quiz_events_found = cached_data.get("quiz_events_found", 0)
        by_user = {int(k): v for k, v in cached_data.get("by_user", {}).items()}
        total_xp_to_remove = cached_data.get("total_xp_to_remove", 0)
        await send_update(f"✅ Using cached data: {len(events_to_remove)} events to remove from {len(by_user)} users")
    else:
        await send_update(f"📊 Scanning {len(rows) - 1} XP events...")
        
        events_to_remove = []
        checked_users = {}  # Cache: user_id -> (post_count, meets_requirement)
        quiz_events_found = 0
        
        for row_idx, row in enumerate(rows[1:], start=2):
            if len(row) <= max(discord_id_col, source_col):
                continue
            
            source = row[source_col].lower() if len(row) > source_col else ""
            discord_id_str = row[discord_id_col] if len(row) > discord_id_col else ""
            
            # Only check quiz_completion events
            if source != "quiz_completion":
                continue
            
            quiz_events_found += 1
            
            if not discord_id_str:
                continue
            
            try:
                discord_id = int(discord_id_str)
            except (ValueError, TypeError):
                continue
            
            # Check if we've already checked this user
            if discord_id in checked_users:
                post_count, meets_requirement = checked_users[discord_id]
            else:
                # Count Discord posts for this user
                try:
                    # Send update before starting to check user (especially for first user)
                    if len(checked_users) == 0:
                        await send_update(f"⏳ Checking first user (ID: {discord_id})... This may take a while on large servers.")
                    elif len(checked_users) % 100 == 0:
                        await send_update(f"⏳ Checking user {len(checked_users) + 1} (ID: {discord_id})... Processed {quiz_events_found} quiz events so far...")
                    
                    log_or_print("info", f"[FixQuizBots] Checking user {discord_id} (user #{len(checked_users) + 1})...")
                    post_count = await count_discord_messages_for_user(interaction.guild, discord_id)
                    min_posts_required = get_min_discord_posts()
                    meets_requirement = post_count >= min_posts_required
                    checked_users[discord_id] = (post_count, meets_requirement)
                    log_or_print("info", f"[FixQuizBots] User {discord_id} has {post_count} posts (need {min_posts_required}+): {'✓' if meets_requirement else '✗'}")
                    
                    # Add delay between user checks to avoid Discord API rate limits
                    # Especially important for users with 0 posts who require scanning full message history
                    await asyncio.sleep(0.5)  # 500ms delay between user checks
                    
                    # Send progress update every 100 users checked or every 100 events
                    if len(checked_users) % 100 == 0 or quiz_events_found % 100 == 0:
                        await send_update(f"⏳ Progress: Checked {len(checked_users)} unique users, processed {quiz_events_found} quiz events, found {len(events_to_remove)} to remove...")
                except Exception as e:
                    log_or_print("error", f"[FixQuizBots] Error checking user {discord_id}: {e}", exc_info=True)
                    # On error, don't remove (fail safe)
                    checked_users[discord_id] = (0, True)
                    continue
            
            # If user doesn't meet requirement, mark this event for removal
            if not meets_requirement:
                amount = 0
                if amount_col is not None and len(row) > amount_col:
                    try:
                        amount = int(row[amount_col])
                    except (ValueError, TypeError):
                        pass
                
                events_to_remove.append({
                    "row_index": row_idx,
                    "discord_id": discord_id,
                    "amount": amount,
                    "source": source,
                })
        
        if not events_to_remove:
            await interaction.followup.send("✅ No quiz XP events found for users with <3 Discord posts.", ephemeral=True)
            return
        
        # Group by user for summary
        by_user = {}
        total_xp_to_remove = 0
        for event in events_to_remove:
            user_id = event["discord_id"]
            if user_id not in by_user:
                by_user[user_id] = {"count": 0, "total_xp": 0, "post_count": checked_users.get(user_id, (0, False))[0]}
            by_user[user_id]["count"] += 1
            by_user[user_id]["total_xp"] += event["amount"]
            total_xp_to_remove += event["amount"]
        
        # Save cache for dry run
        if not execute:
            try:
                cache_data = {
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "events_to_remove": events_to_remove,
                    "checked_users": {str(k): list(v) for k, v in checked_users.items()},
                    "quiz_events_found": quiz_events_found,
                    "by_user": {str(k): v for k, v in by_user.items()},
                    "total_xp_to_remove": total_xp_to_remove,
                }
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, indent=2)
                log_or_print("info", f"[FixQuizBots] Saved dry run cache to {cache_file}")
            except Exception as e:
                log_or_print("error", f"[FixQuizBots] Error saving cache: {e}")
    
    if not events_to_remove:
        await interaction.followup.send("✅ No quiz XP events found for users with <3 Discord posts.", ephemeral=True)
        return
    
    min_posts_required = get_min_discord_posts()
    summary = (
        f"📊 **Analysis Complete**\n\n"
        f"**Summary:**\n"
        f"• {len(by_user)} unique users affected\n"
        f"• {len(events_to_remove)} XP events to remove\n"
        f"• {total_xp_to_remove} total XP to remove\n"
        f"• Minimum posts required: **{min_posts_required}**\n\n"
    )
    
    # Show top 10 users
    sorted_users = sorted(by_user.items(), key=lambda x: x[1]["total_xp"], reverse=True)[:10]
    summary += "**Top 10 users by XP to remove:**\n"
    for user_id, data in sorted_users:
        user_mention = f"<@{user_id}>"
        summary += f"• {user_mention}: {data['count']} events, {data['total_xp']} XP (has {data['post_count']} posts, need {min_posts_required}+)\n"
    
    if not execute:
        summary += f"\n⚠️ **DRY RUN** - No changes made. Use `execute: true` to actually remove events."
    else:
        summary += f"\n⚠️ **EXECUTING** - This will permanently remove {len(events_to_remove)} XP events."
    
    await send_update(summary)
    
    # Export to CSV (both dry run and execute)
    try:
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Discord ID", "Post Count", "Events Count", "Total XP to Remove", "Status"])
            for user_id, data in sorted(by_user.items(), key=lambda x: x[1]["total_xp"], reverse=True):
                writer.writerow([
                    user_id,
                    data["post_count"],
                    data["count"],
                    data["total_xp"],
                    "DRY RUN" if not execute else "EXECUTED"
                ])
        await send_update(f"📄 Results exported to: `{csv_file}`")
        log_or_print("info", f"[FixQuizBots] Exported results to {csv_file}")
    except Exception as e:
        log_or_print("error", f"[FixQuizBots] Error exporting CSV: {e}")
    
    if not execute:
        return
    
    # Actually remove the events
    await send_update(f"🗑️ Removing {len(events_to_remove)} events...")
    
    # Get current sheet row count to filter out rows that have already been deleted
    try:
        current_rows = ws.get_all_values()
        current_row_count = len(current_rows)
        log_or_print("info", f"[FixQuizBots] Current sheet has {current_row_count} rows (including header)")
    except Exception as e:
        log_or_print("error", f"[FixQuizBots] Error getting current row count: {e}")
        current_row_count = None
    
    # Filter out row indices that are beyond the current sheet size (already deleted)
    valid_events = []
    skipped_already_deleted = 0
    for event in events_to_remove:
        row_idx = event["row_index"]
        # Row index is 1-based, and we need to account for header row
        # If current_row_count is None, we'll try to delete anyway (fallback)
        if current_row_count is not None and row_idx > current_row_count:
            skipped_already_deleted += 1
            log_or_print("debug", f"[FixQuizBots] Skipping row {row_idx} - already deleted (sheet has {current_row_count} rows)")
            continue
        valid_events.append(event)
    
    if skipped_already_deleted > 0:
        await send_update(f"ℹ️ Skipped {skipped_already_deleted} rows that were already deleted. Processing {len(valid_events)} remaining rows...")
        log_or_print("info", f"[FixQuizBots] Skipped {skipped_already_deleted} already-deleted rows, {len(valid_events)} rows to delete")
    
    # Sort by row index in descending order (so we can delete from bottom to top)
    valid_events.sort(key=lambda x: x["row_index"], reverse=True)
    
    removed_count = 0
    failed_count = 0
    rate_limit_errors = 0
    skipped_count = skipped_already_deleted
    
    for event in valid_events:
        try:
            # Throttle API calls to respect rate limits (60 requests per minute)
            await throttle_sheets_api()
            
            row_idx = event["row_index"]
            
            # Use retry with backoff for rate limit handling
            # Wrap synchronous delete_rows in asyncio.to_thread
            def delete_row():
                ws.delete_rows(row_idx)
            
            await retry_with_backoff(
                lambda: asyncio.to_thread(delete_row),
                max_retries=3,
                initial_delay=2.0,
            )
            removed_count += 1
            
            if removed_count % 50 == 0:
                await send_update(f"⏳ Removed {removed_count}/{len(events_to_remove)} events... (failed: {failed_count})")
        except Exception as e:
            error_str = str(e)
            # Check if row doesn't exist (already deleted) - skip without counting as failure
            if "doesn't exist" in error_str or "Cannot delete a row" in error_str or "400" in error_str:
                # This is a 400 error for non-existent row - skip it
                skipped_count += 1
                log_or_print("debug", f"[FixQuizBots] Row {event['row_index']} doesn't exist (already deleted), skipping")
                continue
            
            # Check if it's a rate limit error
            if "429" in error_str or "Quota exceeded" in error_str or "rate limit" in error_str.lower():
                rate_limit_errors += 1
                if rate_limit_errors <= 3:
                    # Wait longer for rate limit
                    wait_time = 60  # Wait 60 seconds for rate limit to reset
                    log_or_print("warning", f"[FixQuizBots] Rate limit hit, waiting {wait_time} seconds before continuing...")
                    await send_update(f"⏸️ Rate limit hit. Waiting {wait_time} seconds... (removed: {removed_count}, failed: {failed_count})")
                    await asyncio.sleep(wait_time)
                    # Retry this event
                    try:
                        await throttle_sheets_api()
                        retry_row_idx = event["row_index"]
                        def retry_delete_row():
                            ws.delete_rows(retry_row_idx)
                        await retry_with_backoff(
                            lambda: asyncio.to_thread(retry_delete_row),
                            max_retries=2,
                            initial_delay=5.0,
                        )
                        removed_count += 1
                        rate_limit_errors = 0  # Reset counter on success
                        continue
                    except Exception as retry_e:
                        log_or_print("error", f"[FixQuizBots] Error removing row {event['row_index']} after retry: {retry_e}")
                        failed_count += 1
                else:
                    log_or_print("error", f"[FixQuizBots] Too many rate limit errors, stopping. Removed: {removed_count}, Failed: {failed_count}")
                    await send_update(f"⚠️ Too many rate limit errors. Stopping deletion. Removed: {removed_count}/{len(events_to_remove)}, Failed: {failed_count}")
                    break
            else:
                log_or_print("error", f"[FixQuizBots] Error removing row {event['row_index']}: {e}")
                failed_count += 1
    
    # Final summary
    summary_msg = f"✅ **Complete!**\n\n"
    summary_msg += f"Removed {removed_count} XP events from {len(by_user)} users.\n"
    summary_msg += f"Total XP removed: {total_xp_to_remove}\n"
    if skipped_count > 0:
        summary_msg += f"\nℹ️ Skipped {skipped_count} rows that were already deleted"
    if failed_count > 0:
        summary_msg += f"\n⚠️ Failed to remove {failed_count} events (check logs for details)"
    
    await interaction.followup.send(summary_msg, ephemeral=True)


async def update_xp_events_for_thread(
    thread_rows_sorted: List[Dict[str, Any]],
    new_xp_amount: int,
    member: str,
    tweet_ids: List[str]
) -> None:
    """Update XP events to match thread consolidation.
    
    For tweets that had XP set to 0 (all except first), delete or set their XP events to 0.
    For the first tweet, update its XP event to the new re-graded amount.
    
    Args:
        thread_rows_sorted: List of thread row data, sorted by row_index (first is the main tweet)
        new_xp_amount: New XP amount for the first tweet (re-graded combined thread)
        member: Discord member name
        tweet_ids: List of all tweet IDs in the thread
    """
    try:
        ws_events = get_xp_events_ws()
        rows = ws_events.get_all_values()
        
        if not rows or len(rows) < 2:
            log_or_print("warning", "[FixTwitterThreads] No XP events found in sheet")
            return
        
        header = rows[0]
        
        # Find column indices
        reference_type_col = None
        reference_id_col = None
        amount_col = None
        discord_id_col = None
        
        for idx, col_name in enumerate(header):
            col_lower = col_name.lower()
            if "reference_type" in col_lower:
                reference_type_col = idx
            elif "reference_id" in col_lower or "reference" in col_lower:
                reference_id_col = idx
            elif "amount" in col_lower or "xp" in col_lower:
                amount_col = idx
            elif "discord_id" in col_lower or col_name == "ID":
                discord_id_col = idx
        
        if reference_type_col is None or reference_id_col is None or amount_col is None:
            log_or_print("warning", "[FixTwitterThreads] Could not find required columns in XP events sheet")
            return
        
        # Extract Discord ID by finding an XP event for one of these tweets
        # This ensures we get the correct Discord ID for this user
        discord_id = None
        if discord_id_col is not None:
            # Try to find Discord ID by matching member name AND one of the tweet IDs
            for row in rows[1:]:
                if len(row) <= max(reference_type_col, reference_id_col, amount_col, discord_id_col):
                    continue
                
                row_reference_type = row[reference_type_col] if len(row) > reference_type_col else ""
                row_reference_id = row[reference_id_col] if len(row) > reference_id_col else ""
                row_discord_name = row[2] if len(row) > 2 else ""  # discord_name is typically column 2 (index 2)
                
                # Match both member name and one of the tweet IDs
                if (row_reference_type.lower() == "tweet" and 
                    row_reference_id in tweet_ids and
                    row_discord_name == member):
                    try:
                        discord_id = int(row[discord_id_col])
                        break
                    except (ValueError, TypeError):
                        continue
        
        if not discord_id:
            log_or_print("warning", f"[FixTwitterThreads] Could not find Discord ID for member {member} with tweets {tweet_ids}")
            return
        
        first_tweet_id = thread_rows_sorted[0].get("tweet_id") if thread_rows_sorted else None
        other_tweet_ids = [row.get("tweet_id") for row in thread_rows_sorted[1:]] if len(thread_rows_sorted) > 1 else []
        
        # Find and update XP events
        events_to_delete = []  # Row indices (1-based) to delete
        events_to_update = []  # (row_index, new_amount) tuples
        
        for row_idx, row in enumerate(rows[1:], start=2):  # Start at 2 because row 1 is header
            if len(row) <= max(reference_type_col, reference_id_col, amount_col):
                continue
            
            row_reference_type = row[reference_type_col] if len(row) > reference_type_col else ""
            row_reference_id = row[reference_id_col] if len(row) > reference_id_col else ""
            row_discord_id = row[discord_id_col] if discord_id_col is not None and len(row) > discord_id_col else ""
            
            # Check if this XP event is for one of our thread tweets
            if (row_reference_type.lower() == "tweet" and 
                row_reference_id in tweet_ids and
                str(row_discord_id) == str(discord_id)):
                
                if row_reference_id == first_tweet_id:
                    # First tweet: update XP amount
                    events_to_update.append((row_idx, new_xp_amount))
                elif row_reference_id in other_tweet_ids:
                    # Other tweets: delete the XP event (since XP is now 0)
                    events_to_delete.append(row_idx)
        
        # Delete XP events for tweets that had XP set to 0
        if events_to_delete:
            # Sort in descending order to delete from bottom to top (avoids index shifting issues)
            events_to_delete.sort(reverse=True)
            for row_idx in events_to_delete:
                try:
                    await throttle_sheets_api()
                    await retry_with_backoff(
                        lambda: asyncio.to_thread(ws_events.delete_rows, row_idx),
                        max_retries=3,
                        initial_delay=1.0,
                    )
                    log_or_print("info", f"[FixTwitterThreads] Deleted XP event for tweet (row {row_idx})")
                except Exception as e:
                    log_or_print("error", f"[FixTwitterThreads] Error deleting XP event row {row_idx}: {e}")
        
        # Update XP amount for first tweet
        if events_to_update:
            def _get_column_letter(col_index: int) -> str:
                result = ""
                col_index += 1
                while col_index > 0:
                    col_index -= 1
                    result = chr(65 + (col_index % 26)) + result
                    col_index //= 26
                return result
            
            batch_updates = []
            for row_idx, new_amount in events_to_update:
                batch_updates.append({
                    "range": f"{_get_column_letter(amount_col)}{row_idx}",
                    "values": [[new_amount]]
                })
            
            if batch_updates:
                await throttle_sheets_api()
                await retry_with_backoff(
                    lambda: asyncio.to_thread(ws_events.batch_update, batch_updates, value_input_option="RAW"),
                    max_retries=3,
                    initial_delay=1.0,
                )
                log_or_print("info", f"[FixTwitterThreads] Updated {len(events_to_update)} XP event(s) for first tweet in thread")
        
        if events_to_delete or events_to_update:
            log_or_print("info", f"[FixTwitterThreads] Updated XP events: deleted {len(events_to_delete)}, updated {len(events_to_update)}")
        
    except Exception as e:
        log_or_print("error", f"[FixTwitterThreads] Error updating XP events: {e}", exc_info=True)
        raise


@bot.tree.command(name="fix_twitter_threads", description="Combine and re-grade Twitter thread submissions (Admin only)")
@admin_or_role_only(get_admin_role_list)
@app_commands.describe(
    execute="Actually update tweets (default is dry run)",
)
async def fix_twitter_threads(interaction: discord.Interaction, execute: bool = False):
    """Find and fix Twitter thread submissions by combining and re-grading them.
    
    This is a retroactive fix for the thread detection system.
    """
    await interaction.response.defer(ephemeral=True)
    
    async def send_update(msg: str):
        try:
            await interaction.followup.send(msg, ephemeral=True)
        except Exception:
            pass
    
    cache_file = "fix_twitter_threads_cache.json"
    csv_file = f"fix_twitter_threads_results_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    
    # Check for cached data (both dry run and execution can use cache)
    cached_data = None
    try:
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                cache_timestamp = cached_data.get('timestamp', 'unknown')
                await send_update(f"📦 Found cached data from {cache_timestamp}. Checking for partial progress...")
                
                # Check if cache has partial tweet data (from rate limit interruption)
                if cached_data.get("all_tweet_data"):
                    fetched_count = len(cached_data.get("fetched_tweet_ids", []))
                    await send_update(f"📊 Cache contains partial data: {fetched_count} tweets already fetched. Will resume from where we left off.")
    except Exception as e:
        log_or_print("warning", f"[FixTwitterThreads] Error loading cache: {e}")
    
    await send_update(f"🔍 Starting {'EXECUTION' if execute else 'DRY RUN'} mode...")
    
    try:
        ws = get_tweets_ws()
        rows = ws.get_all_values()
    except Exception as e:
        await interaction.followup.send(f"❌ Error accessing tweets sheet: {e}", ephemeral=True)
        return
    
    if not rows or len(rows) < 2:
        await interaction.followup.send("No tweets found.", ephemeral=True)
        return
    
    header = rows[0]
    
    # Find column indices
    tweet_id_col = None
    member_col = None
    graded_col = None
    score_col = None
    xp_col = None
    text_col = None
    notes_col = None
    
    for idx, col_name in enumerate(header):
        if col_name == "Tweet ID":
            tweet_id_col = idx
        elif col_name == "Member":
            member_col = idx
        elif col_name == "Graded":
            graded_col = idx
        elif col_name == "Score":
            score_col = idx
        elif col_name == "XP Awarded":
            xp_col = idx
        elif col_name == "Tweet Text":
            text_col = idx
        elif col_name == "Notes" or "notes" in col_name.lower():
            notes_col = idx
    
    if tweet_id_col is None or member_col is None:
        await interaction.followup.send("❌ Error: Could not find required columns in tweets sheet.", ephemeral=True)
        return
    
    # Track processed threads for resume functionality
    processed_threads = set()
    if cached_data:
        processed_threads = set(cached_data.get("processed_threads", []))
        if processed_threads:
            await send_update(f"📦 Found {len(processed_threads)} already-processed threads in cache. Will resume from where we left off.")
    
    # Initialize cached_data structure if executing (even if no cache file exists yet)
    if execute and not cached_data:
        cached_data = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "actual_threads": {},
            "tweet_rows": {},
            "processed_threads": [],
        }
    
    # Use cached data if available (from dry run or previous execution)
    # Check if we have complete cached data (actual_threads) to skip re-analysis
    actual_threads = {}
    tweet_rows = {}
    
    # Check if we have complete cached data to skip re-analysis
    if cached_data and cached_data.get("actual_threads"):
        # We have complete cached data - use it instead of re-doing analysis
        # This works for both dry run and execution modes
        await send_update(f"✅ Using cached data from previous run. Skipping re-analysis...")
        
        # Reconstruct actual_threads from cache
        for k, v in cached_data.get("actual_threads", {}).items():
            actual_threads[k] = []
            for row_data in v:
                actual_threads[k].append({
                    "row_index": row_data["row_index"],
                    "tweet_id": row_data["tweet_id"],
                    "member": row_data["member"],
                    "row": row_data["row"],
                    "tweet_id_col": row_data["tweet_id_col"],
                    "member_col": row_data["member_col"],
                    "graded_col": row_data["graded_col"],
                    "score_col": row_data["score_col"],
                    "xp_col": row_data["xp_col"],
                    "text_col": row_data["text_col"],
                    "notes_col": row_data["notes_col"],
                })
        
        # Reconstruct tweet_rows from cache
        for k, v in cached_data.get("tweet_rows", {}).items():
            tweet_rows[k] = {
                "row_index": v["row_index"],
                "tweet_id": v["tweet_id"],
                "member": v["member"],
                "row": v["row"],
                "tweet_id_col": v["tweet_id_col"],
                "member_col": v["member_col"],
                "graded_col": v["graded_col"],
                "score_col": v["score_col"],
                "xp_col": v["xp_col"],
                "text_col": v["text_col"],
                "notes_col": v["notes_col"],
            }
        
        await send_update(f"✅ Loaded {len(actual_threads)} thread groups from cache. Ready to process.")
        
        # Calculate and show XP consolidation stats from cached data
        total_tweets_cached = sum(len(rows) for rows in actual_threads.values())
        total_original_xp_cached = 0
        
        for thread_key, thread_rows in actual_threads.items():
            for row_data in thread_rows:
                xp_value = 0
                if row_data.get("xp_col") is not None and len(row_data.get("row", [])) > row_data["xp_col"]:
                    try:
                        xp_str = row_data["row"][row_data["xp_col"]]
                        if xp_str:
                            xp_value = float(xp_str) if xp_str else 0
                    except (ValueError, TypeError):
                        xp_value = 0
                total_original_xp_cached += xp_value
        
        tweets_that_will_lose_xp_cached = total_tweets_cached - len(actual_threads)
        
        await send_update(
            f"📊 **Cached Thread Analysis:**\n"
            f"• {len(actual_threads)} thread groups\n"
            f"• {total_tweets_cached} total tweets in threads\n"
            f"• {total_original_xp_cached:.0f} total original XP across all thread tweets\n"
            f"• {tweets_that_will_lose_xp_cached} tweets will have XP consolidated to 0\n"
        )
    else:
        # No cached data or incomplete cache - need to do full analysis
        await send_update(f"📊 Scanning {len(rows) - 1} tweet submissions...")
        
        # Collect all tweet IDs to fetch conversation data
        all_tweet_ids = []
        tweet_rows = {}
        
        for row_idx, row in enumerate(rows[1:], start=2):
            if len(row) <= max(tweet_id_col, member_col):
                continue
            
            tweet_id = row[tweet_id_col] if len(row) > tweet_id_col else ""
            member = row[member_col] if len(row) > member_col else ""
            
            if not tweet_id or not member:
                continue
            
            all_tweet_ids.append(tweet_id)
            tweet_rows[tweet_id] = {
                "row_index": row_idx,
                "tweet_id": tweet_id,
                "member": member,
                "row": row,
                "tweet_id_col": tweet_id_col,
                "member_col": member_col,
                "graded_col": graded_col,
                "score_col": score_col,
                "xp_col": xp_col,
                "text_col": text_col,
                "notes_col": notes_col,
            }
        
        # Check if we have cached tweet data to resume from
        fetched_tweet_ids = set()
        all_tweet_data = {}
        if cached_data and cached_data.get("all_tweet_data"):
            # Restore previously fetched data
            all_tweet_data = cached_data.get("all_tweet_data", {})
            fetched_tweet_ids = set(cached_data.get("fetched_tweet_ids", []))
            already_fetched = len(fetched_tweet_ids)
            await send_update(f"✅ Restored {already_fetched} previously fetched tweets from cache.")
        
        # Only fetch tweet IDs that haven't been fetched yet
        remaining_tweet_ids = [tid for tid in all_tweet_ids if tid not in fetched_tweet_ids]
        
        if remaining_tweet_ids:
            await send_update(f"🔍 Fetching conversation data for {len(remaining_tweet_ids)} remaining tweets (out of {len(all_tweet_ids)} total)...")
            
            # Fetch conversation data in batches with rate limiting
            # Twitter API: 300 requests per 15 minutes = 20 requests/minute = 1 request every 3 seconds
            # We use 4 second intervals to be conservative
            batch_size = 100
            total_batches = (len(remaining_tweet_ids) + batch_size - 1) // batch_size
            rate_limit_errors = 0
            max_rate_limit_errors = 3
            
            # Helper function to save partial cache
            async def save_partial_cache():
                """Save partial progress when rate limit is hit."""
                nonlocal cached_data  # Allow modifying outer scope variable
                try:
                    # Convert to serializable format
                    serializable_tweet_data = {}
                    for k, v in all_tweet_data.items():
                        serializable_tweet_data[k] = v
                    
                    # Update cached_data with partial progress
                    if not cached_data:
                        cached_data = {
                            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            "all_tweet_data": serializable_tweet_data,
                            "fetched_tweet_ids": list(fetched_tweet_ids),
                            "tweet_rows": {},
                            "actual_threads": {},
                            "processed_threads": [],
                        }
                    else:
                        cached_data["all_tweet_data"] = serializable_tweet_data
                        cached_data["fetched_tweet_ids"] = list(fetched_tweet_ids)
                        cached_data["last_saved"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    
                    # Convert tweet_rows to serializable format
                    serializable_tweet_rows = {}
                    for k, v in tweet_rows.items():
                        serializable_tweet_rows[k] = {
                            "row_index": v["row_index"],
                            "tweet_id": v["tweet_id"],
                            "member": v["member"],
                            "row": v["row"],
                            "tweet_id_col": v["tweet_id_col"],
                            "member_col": v["member_col"],
                            "graded_col": v["graded_col"],
                            "score_col": v["score_col"],
                            "xp_col": v["xp_col"],
                            "text_col": v["text_col"],
                            "notes_col": v["notes_col"],
                        }
                    cached_data["tweet_rows"] = serializable_tweet_rows
                    
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(cached_data, f, indent=2, default=str)
                    log_or_print("info", f"[FixTwitterThreads] Saved partial cache: {len(fetched_tweet_ids)}/{len(all_tweet_ids)} tweets fetched")
                except Exception as save_error:
                    log_or_print("error", f"[FixTwitterThreads] Error saving partial cache: {save_error}")
        
            for i in range(0, len(remaining_tweet_ids), batch_size):
                batch = remaining_tweet_ids[i:i+batch_size]
                batch_num = i//batch_size + 1
                await send_update(f"⏳ Fetching batch {batch_num}/{total_batches}...")
                
                try:
                    batch_data = await fetch_tweet_data_for_thread_detection(batch)
                    all_tweet_data.update(batch_data)
                    fetched_tweet_ids.update(batch)  # Track which IDs we've fetched
                    rate_limit_errors = 0  # Reset error counter on success
                    
                    # Save progress after each successful batch (in case of interruption)
                    if batch_num % 5 == 0:  # Save every 5 batches to avoid too many writes
                        await save_partial_cache()
                    
                    # Add delay between batches to respect rate limits (except for last batch)
                    if i + batch_size < len(remaining_tweet_ids):
                        await asyncio.sleep(4.0)  # 4 second delay between batches
                        
                except TwitterRateLimitError as e:
                    rate_limit_errors += 1
                    
                    # Save partial progress before breaking
                    await save_partial_cache()
                    
                    if rate_limit_errors > max_rate_limit_errors:
                        fetched_count = len(fetched_tweet_ids)
                        total_count = len(all_tweet_ids)
                        await send_update(
                            f"❌ Rate limit exceeded after {fetched_count}/{total_count} tweets fetched.\n"
                            f"💾 Progress saved to cache. Wait 15 minutes, then rerun the command to resume."
                        )
                        log_or_print("error", f"[FixTwitterThreads] Rate limit errors exceeded, stopping batch fetch. Saved {fetched_count}/{total_count} tweets.")
                        break
                    
                    wait_time = e.retry_after if e.retry_after else 60
                    await send_update(f"⚠️ Rate limit hit. Waiting {wait_time:.0f} seconds before retrying batch {batch_num}...")
                    log_or_print("warning", f"[FixTwitterThreads] Rate limit hit on batch {batch_num}, waiting {wait_time:.0f}s")
                    await asyncio.sleep(wait_time)
                    
                    # Retry this batch
                    try:
                        batch_data = await fetch_tweet_data_for_thread_detection(batch)
                        all_tweet_data.update(batch_data)
                        fetched_tweet_ids.update(batch)  # Track which IDs we've fetched
                        rate_limit_errors = 0  # Reset on successful retry
                    except Exception as retry_e:
                        log_or_print("error", f"[FixTwitterThreads] Error retrying batch {batch_num}: {retry_e}")
                        await send_update(f"⚠️ Error retrying batch {batch_num}: {retry_e}")
                        continue
                        
                except Exception as e:
                    log_or_print("error", f"[FixTwitterThreads] Error fetching batch {batch_num}: {e}")
                    await send_update(f"⚠️ Error fetching batch {batch_num}: {e}")
                    # Add delay even on error to avoid compounding rate limit issues
                    if i + batch_size < len(remaining_tweet_ids):
                        await asyncio.sleep(2.0)  # Shorter delay on error
                    continue
            
            # Save final progress after all batches complete
            await save_partial_cache()
        else:
            await send_update(f"✅ All {len(all_tweet_ids)} tweets already fetched from cache. Skipping API calls.")
        
        # Group by user and conversation_id
        thread_groups = defaultdict(list)
        
        for tweet_id, row_data in tweet_rows.items():
            if tweet_id not in all_tweet_data:
                continue
            
            tweet_info = all_tweet_data[tweet_id]
            conversation_id = tweet_info.get("conversation_id", "")
            member = row_data["member"]
            
            if conversation_id:
                key = f"{member}_{conversation_id}"
                thread_groups[key].append(row_data)
            else:
                key = f"{member}_{tweet_id}"
                thread_groups[key].append(row_data)
        
        # Filter to only groups with multiple tweets (actual threads)
        actual_threads = {k: v for k, v in thread_groups.items() if len(v) > 1}
        
        # Save cache (both dry run and execution phases)
        try:
            # Convert thread_rows to serializable format
            serializable_tweet_rows = {}
            for k, v in tweet_rows.items():
                serializable_tweet_rows[k] = {
                    "row_index": v["row_index"],
                    "tweet_id": v["tweet_id"],
                    "member": v["member"],
                    "row": v["row"],
                    "tweet_id_col": v["tweet_id_col"],
                    "member_col": v["member_col"],
                    "graded_col": v["graded_col"],
                    "score_col": v["score_col"],
                    "xp_col": v["xp_col"],
                    "text_col": v["text_col"],
                    "notes_col": v["notes_col"],
                }
            
            # Convert actual_threads to serializable format
            serializable_threads = {}
            for k, v in actual_threads.items():
                serializable_threads[k] = []
                for row_data in v:
                    serializable_threads[k].append({
                        "row_index": row_data["row_index"],
                        "tweet_id": row_data["tweet_id"],
                        "member": row_data["member"],
                        "row": row_data["row"],
                        "tweet_id_col": row_data["tweet_id_col"],
                        "member_col": row_data["member_col"],
                        "graded_col": row_data["graded_col"],
                        "score_col": row_data["score_col"],
                        "xp_col": row_data["xp_col"],
                        "text_col": row_data["text_col"],
                        "notes_col": row_data["notes_col"],
                    })
            
            # Convert all_tweet_data to serializable format
            serializable_tweet_data = {}
            for k, v in all_tweet_data.items():
                serializable_tweet_data[k] = v
            
            # Update or create cache data
            if not cached_data:
                cached_data = {
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "all_tweet_data": serializable_tweet_data,
                    "fetched_tweet_ids": list(fetched_tweet_ids),
                    "actual_threads": serializable_threads,
                    "tweet_rows": serializable_tweet_rows,
                    "processed_threads": list(processed_threads),
                }
            else:
                # Update existing cache
                cached_data["all_tweet_data"] = serializable_tweet_data
                cached_data["fetched_tweet_ids"] = list(fetched_tweet_ids)
                cached_data["actual_threads"] = serializable_threads
                cached_data["tweet_rows"] = serializable_tweet_rows
                cached_data["processed_threads"] = list(processed_threads)
                cached_data["last_updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cached_data, f, indent=2, default=str)
            log_or_print("info", f"[FixTwitterThreads] Saved cache to {cache_file} ({'dry run' if not execute else 'execution'})")
        except Exception as e:
            log_or_print("error", f"[FixTwitterThreads] Error saving cache: {e}")
    
    if not actual_threads:
        await interaction.followup.send("✅ No threads found (all tweets are standalone).", ephemeral=True)
        return
    
    total_tweets = sum(len(rows) for rows in actual_threads.values())
    
    # Calculate XP consolidation statistics
    total_original_xp = 0
    thread_xp_details = []
    
    for thread_key, thread_rows in actual_threads.items():
        original_xp_sum = 0
        tweet_ids_in_thread = []
        
        for row_data in thread_rows:
            # Extract XP from the row data
            xp_value = 0
            if row_data.get("xp_col") is not None and len(row_data.get("row", [])) > row_data["xp_col"]:
                try:
                    xp_str = row_data["row"][row_data["xp_col"]]
                    if xp_str:
                        xp_value = float(xp_str) if xp_str else 0
                except (ValueError, TypeError):
                    xp_value = 0
            
            original_xp_sum += xp_value
            tweet_ids_in_thread.append(row_data.get("tweet_id", "unknown"))
        
        total_original_xp += original_xp_sum
        thread_xp_details.append({
            "thread_key": thread_key,
            "member": thread_rows[0]["member"] if thread_rows else "Unknown",
            "tweet_count": len(thread_rows),
            "original_xp": original_xp_sum,
            "tweet_ids": tweet_ids_in_thread
        })
    
    # Calculate XP that will be condensed (all tweets except first will go to 0)
    # After consolidation, only the first tweet gets XP (re-graded), others get 0
    # So condensed XP = original_xp_sum - (XP that first tweet will get after re-grading)
    # Since we don't know the new XP yet (will be re-graded), we show original total
    tweets_that_will_lose_xp = total_tweets - len(actual_threads)  # All tweets except first in each thread
    
    summary = (
        f"📊 **Analysis Complete**\n\n"
        f"**Thread Detection:**\n"
        f"• Found {len(actual_threads)} thread groups with multiple submissions\n"
        f"• Total tweets in threads: {total_tweets}\n"
        f"• Average tweets per thread: {total_tweets / len(actual_threads):.1f}\n\n"
        f"**XP Consolidation:**\n"
        f"• Total original XP across all thread tweets: {total_original_xp:.0f} XP\n"
        f"• Tweets that will be consolidated: {tweets_that_will_lose_xp} tweets\n"
        f"• After consolidation: Each thread will be re-graded as a single combined tweet\n"
        f"• Other tweets in thread will have XP set to 0\n\n"
    )
    
    if not execute:
        summary += "⚠️ **DRY RUN** - No changes made. Use `execute: true` to actually update tweets."
    else:
        summary += "⚠️ **EXECUTING** - This will re-grade and update tweets."
    
    await send_update(summary)
    
    # Export to CSV (both dry run and execute) with XP details
    try:
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Thread Key", 
                "Member", 
                "Tweet Count", 
                "Original Total XP", 
                "Tweet IDs (comma-separated)",
                "Status"
            ])
            for detail in sorted(thread_xp_details, key=lambda x: x["original_xp"], reverse=True):
                writer.writerow([
                    detail["thread_key"],
                    detail["member"],
                    detail["tweet_count"],
                    detail["original_xp"],
                    ", ".join(detail["tweet_ids"]),
                    "DRY RUN" if not execute else "EXECUTED"
                ])
        await send_update(f"📄 Results exported to: `{csv_file}`\n" +
                         f"💡 CSV includes: Thread details, original XP totals, and tweet IDs for each thread.")
        log_or_print("info", f"[FixTwitterThreads] Exported results to {csv_file}")
    except Exception as e:
        log_or_print("error", f"[FixTwitterThreads] Error exporting CSV: {e}")
    
    if not execute:
        return
    
    # Ensure cached_data exists for tracking progress during execution
    # If we don't have cached_data yet (e.g., executing without dry run first), create it
    if not cached_data:
        # Convert current data to serializable format
        serializable_tweet_rows = {}
        for k, v in tweet_rows.items():
            serializable_tweet_rows[k] = {
                "row_index": v["row_index"],
                "tweet_id": v["tweet_id"],
                "member": v["member"],
                "row": v["row"],
                "tweet_id_col": v["tweet_id_col"],
                "member_col": v["member_col"],
                "graded_col": v["graded_col"],
                "score_col": v["score_col"],
                "xp_col": v["xp_col"],
                "text_col": v["text_col"],
                "notes_col": v["notes_col"],
            }
        
        serializable_threads = {}
        for k, v in actual_threads.items():
            serializable_threads[k] = []
            for row_data in v:
                serializable_threads[k].append({
                    "row_index": row_data["row_index"],
                    "tweet_id": row_data["tweet_id"],
                    "member": row_data["member"],
                    "row": row_data["row"],
                    "tweet_id_col": row_data["tweet_id_col"],
                    "member_col": row_data["member_col"],
                    "graded_col": row_data["graded_col"],
                    "score_col": row_data["score_col"],
                    "xp_col": row_data["xp_col"],
                    "text_col": row_data["text_col"],
                    "notes_col": row_data["notes_col"],
                })
        
        cached_data = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "actual_threads": serializable_threads,
            "tweet_rows": serializable_tweet_rows,
            "processed_threads": list(processed_threads),
        }
        # Save initial cache
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cached_data, f, indent=2, default=str)
            log_or_print("info", f"[FixTwitterThreads] Created initial cache for execution")
        except Exception as e:
            log_or_print("warning", f"[FixTwitterThreads] Error creating initial cache: {e}")
    
    # Filter out already-processed threads
    threads_to_process = {k: v for k, v in actual_threads.items() if k not in processed_threads}
    skipped_count = len(actual_threads) - len(threads_to_process)
    
    # Update XP events for already-processed threads (in case they were processed before XP event updates were added)
    if skipped_count > 0 and execute:
        await send_update(f"🔄 Updating XP events for {skipped_count} already-processed threads...")
        xp_events_updated = 0
        xp_events_failed = 0
        
        # Re-read tweets sheet to get current XP values (cache might have stale data)
        try:
            current_rows = ws.get_all_values()
            # Create a lookup: tweet_id -> current row data
            tweet_id_to_row = {}
            for row_idx, row in enumerate(current_rows[1:], start=2):
                if len(row) > tweet_id_col:
                    tweet_id = row[tweet_id_col]
                    if tweet_id:
                        tweet_id_to_row[tweet_id] = {"row": row, "row_index": row_idx}
        except Exception as e:
            log_or_print("error", f"[FixTwitterThreads] Error reading current tweets sheet: {e}")
            current_rows = None
            tweet_id_to_row = {}
        
        for thread_key, thread_rows in list(actual_threads.items()):
            if thread_key in processed_threads:
                try:
                    # Get current XP from tweets sheet for the first tweet
                    thread_rows_sorted = sorted(thread_rows, key=lambda x: x["row_index"])
                    first_row = thread_rows_sorted[0]
                    first_tweet_id = first_row.get("tweet_id")
                    member = first_row.get("member")
                    tweet_ids = [row.get("tweet_id") for row in thread_rows]
                    
                    # Get current XP value from the tweets sheet (use fresh data if available)
                    current_xp = 0
                    if first_tweet_id in tweet_id_to_row and xp_col is not None:
                        # Use fresh data from sheet
                        fresh_row = tweet_id_to_row[first_tweet_id]["row"]
                        if len(fresh_row) > xp_col:
                            try:
                                xp_str = fresh_row[xp_col]
                                if xp_str:
                                    current_xp = int(float(xp_str))
                            except (ValueError, TypeError):
                                pass
                    else:
                        # Fall back to cached data
                        if first_row.get("xp_col") is not None and len(first_row.get("row", [])) > first_row["xp_col"]:
                            try:
                                xp_str = first_row["row"][first_row["xp_col"]]
                                if xp_str:
                                    current_xp = int(float(xp_str))
                            except (ValueError, TypeError):
                                pass
                    
                    # Update XP events for this thread
                    # Use fresh row data if available, otherwise use cached
                    if first_tweet_id in tweet_id_to_row:
                        # Update thread_rows with fresh data
                        for row_data in thread_rows_sorted:
                            tweet_id = row_data.get("tweet_id")
                            if tweet_id in tweet_id_to_row:
                                row_data["row"] = tweet_id_to_row[tweet_id]["row"]
                                row_data["row_index"] = tweet_id_to_row[tweet_id]["row_index"]
                    
                    await update_xp_events_for_thread(
                        thread_rows_sorted,
                        current_xp,
                        member,
                        tweet_ids
                    )
                    xp_events_updated += 1
                except Exception as e:
                    log_or_print("error", f"[FixTwitterThreads] Error updating XP events for thread {thread_key}: {e}", exc_info=True)
                    xp_events_failed += 1
        
        if xp_events_updated > 0:
            await send_update(f"✅ Updated XP events for {xp_events_updated} already-processed threads.")
        if xp_events_failed > 0:
            await send_update(f"⚠️ Failed to update XP events for {xp_events_failed} threads (check logs).")
    
    if skipped_count > 0:
        await send_update(f"⏭️ Skipping {skipped_count} already-processed threads. Processing {len(threads_to_process)} remaining threads...")
    
    if not threads_to_process:
        await interaction.followup.send(
            f"✅ All threads have already been processed!\n\n"
            f"• Total threads: {len(actual_threads)}\n"
            f"• Already processed: {skipped_count}\n"
            f"• Remaining: 0\n\n"
            f"💡 To start fresh, delete the cache file: `{cache_file}`",
            ephemeral=True
        )
        return
    
    # Process each thread group
    await send_update(f"🔄 Processing {len(threads_to_process)} threads...")
    
    results = []
    rate_limit_errors = 0
    max_rate_limit_errors = 3
    processed_count = 0
    
    for group_key, thread_rows in list(threads_to_process.items())[:50]:  # Limit to 50 threads per run
        tweet_ids = [row["tweet_id"] for row in thread_rows]
        member = thread_rows[0]["member"]
        processed_count += 1
        
        try:
            # Add delay before fetching to respect rate limits (except for first thread)
            if processed_count > 1:
                await asyncio.sleep(4.0)  # 4 second delay between thread processing
            
            # Fetch tweet data
            tweet_data = await fetch_tweet_data_for_thread_detection(tweet_ids)
            rate_limit_errors = 0  # Reset error counter on success
            
            # Combine thread text
            combined_text = combine_thread_text(tweet_ids, tweet_data)
            
            if not combined_text:
                results.append({"success": False, "error": "Could not combine thread text"})
                continue
            
            # Re-grade the combined thread
            score, rationale = await grade_tweet(combined_text)
            xp_amount = max(0, round(score)) if score > 0 else 0
            
            # Update rows
            def _get_column_letter(col_index: int) -> str:
                result = ""
                col_index += 1
                while col_index > 0:
                    col_index -= 1
                    result = chr(65 + (col_index % 26)) + result
                    col_index //= 26
                return result
            
            thread_rows_sorted = sorted(thread_rows, key=lambda x: x["row_index"])
            batch_updates = []
            
            for idx, row_data in enumerate(thread_rows_sorted):
                row_idx = row_data["row_index"]
                
                if idx == 0:
                    # First tweet gets combined score and XP
                    if row_data["score_col"] is not None:
                        batch_updates.append({
                            "range": f"{_get_column_letter(row_data['score_col'])}{row_idx}",
                            "values": [[score]]
                        })
                    if row_data["xp_col"] is not None:
                        batch_updates.append({
                            "range": f"{_get_column_letter(row_data['xp_col'])}{row_idx}",
                            "values": [[xp_amount]]
                        })
                    if row_data["text_col"] is not None:
                        truncated_text = combined_text[:49000] if len(combined_text) > 49000 else combined_text
                        batch_updates.append({
                            "range": f"{_get_column_letter(row_data['text_col'])}{row_idx}",
                            "values": [[truncated_text]]
                        })
                    if row_data["notes_col"] is not None:
                        note = f"Thread submission ({len(tweet_ids)} tweets combined). {rationale[:400]}"
                        batch_updates.append({
                            "range": f"{_get_column_letter(row_data['notes_col'])}{row_idx}",
                            "values": [[note[:500]]]
                        })
                else:
                    # Other tweets get 0 XP
                    if row_data["score_col"] is not None:
                        batch_updates.append({
                            "range": f"{_get_column_letter(row_data['score_col'])}{row_idx}",
                            "values": [[0]]
                        })
                    if row_data["xp_col"] is not None:
                        batch_updates.append({
                            "range": f"{_get_column_letter(row_data['xp_col'])}{row_idx}",
                            "values": [[0]]
                        })
                    if row_data["notes_col"] is not None:
                        existing_notes = row_data["row"][row_data["notes_col"]] if len(row_data["row"]) > row_data["notes_col"] else ""
                        note = f"Part of thread (scored as combined thread). {existing_notes}"
                        if "Part of thread" not in existing_notes:
                            batch_updates.append({
                                "range": f"{_get_column_letter(row_data['notes_col'])}{row_idx}",
                                "values": [[note[:500]]]
                            })
            
            if batch_updates:
                await throttle_sheets_api()
                await retry_with_backoff(
                    lambda: asyncio.to_thread(ws.batch_update, batch_updates, value_input_option="RAW"),
                    max_retries=3,
                    initial_delay=1.0,
                )
                
                # Update XP events to match tweet XP changes
                try:
                    await update_xp_events_for_thread(thread_rows_sorted, xp_amount, member, tweet_ids)
                except Exception as xp_error:
                    log_or_print("error", f"[FixTwitterThreads] Error updating XP events: {xp_error}", exc_info=True)
                    # Don't fail the whole operation if XP event update fails
                
                # Mark as processed on success
                processed_threads.add(group_key)
                results.append({"success": True, "tweet_count": len(thread_rows)})
                
                # Update cache after each successful processing
                try:
                    if cached_data:
                        cached_data["processed_threads"] = list(processed_threads)
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(cached_data, f, indent=2, default=str)
                except Exception as cache_error:
                    log_or_print("warning", f"[FixTwitterThreads] Error updating cache: {cache_error}")
            else:
                results.append({"success": False, "error": "No updates to apply"})
            
            # Delay already added before fetch, no need for additional delay here
            
        except TwitterRateLimitError as e:
            rate_limit_errors += 1
            if rate_limit_errors > max_rate_limit_errors:
                await send_update(f"❌ Too many rate limit errors ({rate_limit_errors}). Stopping thread processing.")
                log_or_print("error", f"[FixTwitterThreads] Rate limit errors exceeded, stopping thread processing")
                results.append({"success": False, "error": f"Rate limit exceeded (stopped after {rate_limit_errors} errors)"})
                break
            
            wait_time = e.retry_after if e.retry_after else 60
            await send_update(f"⚠️ Rate limit hit on thread {processed_count}. Waiting {wait_time:.0f} seconds...")
            log_or_print("warning", f"[FixTwitterThreads] Rate limit hit on thread {processed_count}, waiting {wait_time:.0f}s")
            await asyncio.sleep(wait_time)
            
            # Retry this thread
            try:
                tweet_data = await fetch_tweet_data_for_thread_detection(tweet_ids)
                rate_limit_errors = 0  # Reset on successful retry
                
                # Continue with processing
                combined_text = combine_thread_text(tweet_ids, tweet_data)
                if not combined_text:
                    results.append({"success": False, "error": "Could not combine thread text"})
                    continue
                
                score, rationale = await grade_tweet(combined_text)
                xp_amount = max(0, round(score)) if score > 0 else 0
                
                # Update rows (same logic as before)
                def _get_column_letter(col_index: int) -> str:
                    result = ""
                    col_index += 1
                    while col_index > 0:
                        col_index -= 1
                        result = chr(65 + (col_index % 26)) + result
                        col_index //= 26
                    return result
                
                thread_rows_sorted = sorted(thread_rows, key=lambda x: x["row_index"])
                batch_updates = []
                
                for idx, row_data in enumerate(thread_rows_sorted):
                    row_idx = row_data["row_index"]
                    
                    if idx == 0:
                        # First tweet gets combined score and XP
                        if row_data["score_col"] is not None:
                            batch_updates.append({
                                "range": f"{_get_column_letter(row_data['score_col'])}{row_idx}",
                                "values": [[score]]
                            })
                        if row_data["xp_col"] is not None:
                            batch_updates.append({
                                "range": f"{_get_column_letter(row_data['xp_col'])}{row_idx}",
                                "values": [[xp_amount]]
                            })
                        if row_data["text_col"] is not None:
                            truncated_text = combined_text[:49000] if len(combined_text) > 49000 else combined_text
                            batch_updates.append({
                                "range": f"{_get_column_letter(row_data['text_col'])}{row_idx}",
                                "values": [[truncated_text]]
                            })
                        if row_data["notes_col"] is not None:
                            note = f"Thread submission ({len(tweet_ids)} tweets combined). {rationale[:400]}"
                            batch_updates.append({
                                "range": f"{_get_column_letter(row_data['notes_col'])}{row_idx}",
                                "values": [[note[:500]]]
                            })
                    else:
                        # Other tweets get 0 XP
                        if row_data["score_col"] is not None:
                            batch_updates.append({
                                "range": f"{_get_column_letter(row_data['score_col'])}{row_idx}",
                                "values": [[0]]
                            })
                        if row_data["xp_col"] is not None:
                            batch_updates.append({
                                "range": f"{_get_column_letter(row_data['xp_col'])}{row_idx}",
                                "values": [[0]]
                            })
                        if row_data["notes_col"] is not None:
                            existing_notes = row_data["row"][row_data["notes_col"]] if len(row_data["row"]) > row_data["notes_col"] else ""
                            note = f"Part of thread (scored as combined thread). {existing_notes}"
                            if "Part of thread" not in existing_notes:
                                batch_updates.append({
                                    "range": f"{_get_column_letter(row_data['notes_col'])}{row_idx}",
                                    "values": [[note[:500]]]
                                })
                
                if batch_updates:
                    await throttle_sheets_api()
                    await retry_with_backoff(
                        lambda: asyncio.to_thread(ws.batch_update, batch_updates, value_input_option="RAW"),
                        max_retries=3,
                        initial_delay=1.0,
                    )
                    # Mark as processed on success
                    processed_threads.add(group_key)
                    results.append({"success": True, "tweet_count": len(thread_rows)})
                    
                    # Update cache after each successful processing
                    try:
                        if cached_data:
                            cached_data["processed_threads"] = list(processed_threads)
                            with open(cache_file, 'w', encoding='utf-8') as f:
                                json.dump(cached_data, f, indent=2, default=str)
                    except Exception as cache_error:
                        log_or_print("warning", f"[FixTwitterThreads] Error updating cache: {cache_error}")
                else:
                    results.append({"success": False, "error": "No updates to apply"})
                    
            except Exception as retry_e:
                log_or_print("error", f"[FixTwitterThreads] Error retrying thread {processed_count}: {retry_e}")
                results.append({"success": False, "error": f"Retry failed: {str(retry_e)}"})
            
        except Exception as e:
            log_or_print("error", f"[FixTwitterThreads] Error processing thread {processed_count}: {e}")
            results.append({"success": False, "error": str(e)})
            # Add delay even on error to avoid compounding rate limit issues
            if processed_count < len(actual_threads):
                await asyncio.sleep(2.0)  # Shorter delay on error
    
    # Summary
    successful = sum(1 for r in results if r.get("success"))
    failed = len(results) - successful
    total_processed = len(processed_threads)
    remaining = len(actual_threads) - total_processed
    
    # Final cache update
    try:
        if cached_data:
            cached_data["processed_threads"] = list(processed_threads)
            cached_data["last_processed"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cached_data, f, indent=2, default=str)
    except Exception as cache_error:
        log_or_print("warning", f"[FixTwitterThreads] Error updating final cache: {cache_error}")
    
    summary_msg = (
        f"✅ **Processing Complete!**\n\n"
        f"**Results:**\n"
        f"• Processed this run: {len(results)} threads\n"
        f"• Successful: {successful}\n"
        f"• Failed: {failed}\n\n"
        f"**Overall Progress:**\n"
        f"• Total threads: {len(actual_threads)}\n"
        f"• Completed: {total_processed}\n"
        f"• Remaining: {remaining}\n\n"
    )
    
    if remaining > 0:
        summary_msg += f"💡 **Resume:** Run the command again to continue processing remaining threads.\n\n"
    
    summary_msg += f"{'✅ Updates applied to tweets sheet.' if execute else '[DRY RUN] No changes made.'}"
    
    await interaction.followup.send(summary_msg, ephemeral=True)


@bot.tree.command(name="xp_grandfather_bonus", description="Award grandfather bonus to existing contributors based on tweet count (Admin only)")
@app_commands.describe(
    user="The user to award bonus to",
    tweet_count="Number of historical tweets they submitted (old system: 5 XP each)",
    bonus_per_tweet="Bonus XP per tweet (default: 2, so they get 7 XP total per old tweet)"
)
@admin_or_role_only(get_admin_role_list)
async def xp_grandfather_bonus(interaction: discord.Interaction, user: discord.User, tweet_count: int, bonus_per_tweet: int = 2):
    """Award grandfather bonus to existing contributors.
    
    This compensates users who contributed under the old system (5 XP per tweet).
    With bonus_per_tweet=2, they effectively get 7 XP per old tweet (5 original + 2 bonus).
    This recognizes their past contributions while the new system rewards quality.
    """
    await interaction.response.defer(ephemeral=True)
    
    if tweet_count <= 0:
        await interaction.followup.send("❌ Tweet count must be positive.", ephemeral=True)
        return
    
    if bonus_per_tweet < 0:
        await interaction.followup.send("❌ Bonus per tweet cannot be negative.", ephemeral=True)
        return
    
    bonus_amount = tweet_count * bonus_per_tweet
    old_total = tweet_count * 5  # Old system: 5 XP per tweet
    
    try:
        success, error_msg = add_xp(
            discord_id=user.id,
            discord_name=str(user),
            amount=bonus_amount,
            source="grandfather_bonus",
            reference_type="admin_action",
            reference_id=str(interaction.user.id),
            notes=f"Grandfather bonus: {tweet_count} tweets × {bonus_per_tweet} XP (old system: {old_total} XP total)",
            bypass_cap=True,
        )
        
        if success:
            await interaction.followup.send(
                f"✅ Awarded **{bonus_amount} XP** grandfather bonus to {user.mention}.\n"
                f"📊 Based on {tweet_count} historical tweets\n"
                f"💡 Old system total: {old_total} XP, Bonus: {bonus_amount} XP, New effective: {old_total + bonus_amount} XP per tweet",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"⚠️ Error awarding bonus: {error_msg}",
                ephemeral=True
            )
    except Exception as e:
        print(f"[Grandfather] Error: {e}")
        await interaction.followup.send(
            f"❌ Error awarding bonus: {e}",
            ephemeral=True
        )


@bot.tree.command(name="xp_migrate_historical", description="Migrate historical XP from old leaderboard CSV (Admin only)")
@app_commands.describe(
    csv_file="Name of the CSV file (must be in bot directory)",
    dry_run="If true, only shows what would be migrated without actually doing it"
)
@admin_or_role_only(get_admin_role_list)
async def xp_migrate_historical(interaction: discord.Interaction, csv_file: str, dry_run: bool = True):
    await interaction.response.defer(ephemeral=True)
    
    if not interaction.guild:
        await interaction.followup.send("❌ This command can only be used in a server.", ephemeral=True)
        return
    
    # Clean up the filename - remove quotes and whitespace
    csv_file = csv_file.strip().strip('"').strip("'")
    
    # Ensure the file path is relative to the bot directory
    if not os.path.isabs(csv_file):
        csv_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), csv_file)
    
    # Check if file exists
    if not os.path.exists(csv_file):
        await interaction.followup.send(
            f"❌ CSV file not found: `{csv_file}`\n"
            f"💡 Make sure the file is in the bot directory and the filename is correct.",
            ephemeral=True
        )
        return
    
    # Run migration
    try:
        stats = await migrate_historical_xp(interaction.guild, csv_file, dry_run=dry_run)
        
        # Build response message
        lines = [
            f"📊 **Migration {'Dry Run' if dry_run else 'Results'}**",
            f"Total entries in CSV: **{stats['total_entries']}**",
            f"Users found: **{stats['found_users']}**",
            f"{'Would migrate' if dry_run else 'Migrated'}: **{stats['migrated']}**",
            f"Users not found: **{len(stats['not_found'])}**",
        ]
        
        if stats['errors']:
            lines.append(f"\n⚠️ Errors: **{len(stats['errors'])}**")
            # Show first 5 errors
            for error in stats['errors'][:5]:
                lines.append(f"  - {error}")
            if len(stats['errors']) > 5:
                lines.append(f"  ... and {len(stats['errors']) - 5} more")
        
        if stats['not_found']:
            lines.append(f"\n❌ **Users Not Found ({len(stats['not_found'])}):**")
            # Show first 10 not found
            for entry in stats['not_found'][:10]:
                lines.append(f"  - {entry['username']} (@{entry['twitter']}) - {entry['xp']} XP")
            if len(stats['not_found']) > 10:
                lines.append(f"  ... and {len(stats['not_found']) - 10} more")
        
        if dry_run and stats['migrated'] > 0:
            lines.append(f"\n💡 Run with `dry_run: false` to perform the actual migration.")
        
        await interaction.followup.send("\n".join(lines), ephemeral=True)
        
    except Exception as e:
        print(f"[Migration] Error: {e}")
        await interaction.followup.send(
            f"❌ Migration failed: {e}",
            ephemeral=True
        )


# -------------------------------
# Prediction Game Commands
# -------------------------------

@bot.tree.command(name="predict_volume", description="Predict Polymer's total volume for a future date")
@app_commands.describe(
    target_date="Date to predict volume for (YYYY-MM-DD format, defaults to tomorrow)",
    volume_billions="Predicted volume in billions (e.g., 2.5 for $2.5B)"
)
async def predict_volume(interaction: discord.Interaction, volume_billions: float, target_date: Optional[str] = None):
    """Submit a volume prediction."""
    await interaction.response.defer(ephemeral=True)
    
    # Rate limiting (10 seconds cooldown for predictions)
    if not check_user_rate_limit(interaction.user.id, cooldown_seconds=10):
        remaining = get_user_rate_limit_remaining(interaction.user.id, cooldown_seconds=10)
        await interaction.followup.send(
            f"⏳ Please wait {remaining:.0f} seconds before submitting another prediction.",
            ephemeral=True,
        )
        return
    
    # Parse target date
    if target_date:
        try:
            target = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            await interaction.followup.send("❌ Invalid date format. Use YYYY-MM-DD (e.g., 2024-12-25).", ephemeral=True)
            return
    else:
        # Default to tomorrow
        target = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).date()
    
    # Validate volume
    if volume_billions <= 0:
        await interaction.followup.send("❌ Volume must be greater than 0.", ephemeral=True)
        return
    
    # Check if user already has a prediction for this date
    if has_prediction_today(interaction.user.id, "volume", target):
        await interaction.followup.send(
            f"⚠️ You already have a volume prediction for {target.isoformat()}. "
            f"You can only submit one volume prediction per day.",
            ephemeral=True
        )
        return
    
    # Check deadline
    allowed, error_msg = can_submit_prediction(target)
    if not allowed:
        await interaction.followup.send(f"❌ {error_msg}", ephemeral=True)
        return
    
    # Save prediction with throttling
    try:
        ws = get_predictions_ws()
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        row = [
            ts,
            str(interaction.user.id),
            str(interaction.user),
            "volume",
            target.isoformat(),
            str(volume_billions),
            "",  # actual_value (filled on resolution)
            "FALSE",  # resolved
            "",  # accuracy
            "",  # xp_awarded
            f"Predicted ${volume_billions:.3f}B for {target.isoformat()}",
            ""  # resolution_timestamp
        ]
        
        await throttle_sheets_api()
        await retry_with_backoff(
            lambda: asyncio.to_thread(ws.append_row, row, "RAW"),
            max_retries=3,
            initial_delay=1.0,
        )
        
        await interaction.followup.send(
            f"✅ **Volume Prediction Submitted!**\n\n"
            f"📅 Target Date: **{target.isoformat()}**\n"
            f"💰 Predicted Volume: **${volume_billions:.3f} billion**\n\n"
            f"🎯 Predictions will be resolved at {PREDICTION_RESOLUTION_HOUR}:00 UTC on {target.isoformat()}.\n"
            f"🏆 XP will be awarded based on accuracy!",
            ephemeral=True
        )
    except Exception as e:
        print(f"[PredictVolume] Error: {e}")
        await interaction.followup.send(f"❌ Failed to submit prediction: {e}", ephemeral=True)


@bot.tree.command(name="predict_top10", description="Predict changes to the top 10 transactions")
@app_commands.describe(
    target_date="Date to predict for (YYYY-MM-DD format, defaults to tomorrow)",
    new_entries="Comma-separated list of token symbols that will enter top 10 (e.g., USDC,ETH)",
    removed_entries="Comma-separated list of token symbols that will leave top 10 (e.g., BTC,MATIC)"
)
async def predict_top10(interaction: discord.Interaction, target_date: Optional[str] = None, new_entries: Optional[str] = None, removed_entries: Optional[str] = None):
    """Submit a top 10 change prediction."""
    await interaction.response.defer(ephemeral=True)
    
    # Rate limiting (10 seconds cooldown for predictions)
    if not check_user_rate_limit(interaction.user.id, cooldown_seconds=10):
        remaining = get_user_rate_limit_remaining(interaction.user.id, cooldown_seconds=10)
        await interaction.followup.send(
            f"⏳ Please wait {remaining:.0f} seconds before submitting another prediction.",
            ephemeral=True,
        )
        return
    
    # Parse target date
    if target_date:
        try:
            target = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            await interaction.followup.send("❌ Invalid date format. Use YYYY-MM-DD (e.g., 2024-12-25).", ephemeral=True)
            return
    else:
        # Default to tomorrow
        target = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).date()
    
    # Parse entries
    new_list = [t.strip().upper() for t in (new_entries or "").split(",") if t.strip()]
    removed_list = [t.strip().upper() for t in (removed_entries or "").split(",") if t.strip()]
    
    if not new_list and not removed_list:
        await interaction.followup.send(
            "❌ You must specify at least one token that will enter or leave the top 10.\n"
            "Example: `/predict_top10 new_entries:USDC,ETH removed_entries:BTC`",
            ephemeral=True
        )
        return
    
    # Check if user already has a prediction for this date
    if has_prediction_today(interaction.user.id, "top10", target):
        await interaction.followup.send(
            f"⚠️ You already have a top 10 prediction for {target.isoformat()}. "
            f"You can only submit one top 10 prediction per day.",
            ephemeral=True
        )
        return
    
    # Check deadline
    allowed, error_msg = can_submit_prediction(target)
    if not allowed:
        await interaction.followup.send(f"❌ {error_msg}", ephemeral=True)
        return
    
    # Save prediction
    try:
        ws = get_predictions_ws()
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        prediction_data = {
            "new_entries": new_list,
            "removed_entries": removed_list
        }
        
        notes_parts = []
        if new_list:
            notes_parts.append(f"New: {', '.join(new_list)}")
        if removed_list:
            notes_parts.append(f"Removed: {', '.join(removed_list)}")
        notes = f"Top 10 prediction for {target.isoformat()} - {'; '.join(notes_parts)}"
        
        row = [
            ts,
            str(interaction.user.id),
            str(interaction.user),
            "top10",
            target.isoformat(),
            json.dumps(prediction_data),  # prediction_value (JSON)
            "",  # actual_value (filled on resolution)
            "FALSE",  # resolved
            "",  # accuracy
            "",  # xp_awarded
            notes,
            ""  # resolution_timestamp
        ]
        
        await throttle_sheets_api()
        await retry_with_backoff(
            lambda: asyncio.to_thread(ws.append_row, row, "RAW"),
            max_retries=3,
            initial_delay=1.0,
        )
        
        response_lines = [
            f"✅ **Top 10 Prediction Submitted!**",
            f"",
            f"📅 Target Date: **{target.isoformat()}**",
        ]
        
        if new_list:
            response_lines.append(f"🆕 Will Enter Top 10: **{', '.join(new_list)}**")
        if removed_list:
            response_lines.append(f"❌ Will Leave Top 10: **{', '.join(removed_list)}**")
        
        response_lines.extend([
            f"",
            f"🎯 Predictions will be resolved at {PREDICTION_RESOLUTION_HOUR}:00 UTC on {target.isoformat()}.",
            f"🏆 XP will be awarded based on accuracy!"
        ])
        
        await interaction.followup.send("\n".join(response_lines), ephemeral=True)
    except Exception as e:
        print(f"[PredictTop10] Error: {e}")
        await interaction.followup.send(f"❌ Failed to submit prediction: {e}", ephemeral=True)


@bot.tree.command(name="my_predictions", description="View your active predictions")
async def my_predictions(interaction: discord.Interaction):
    """Show user's active (unresolved) predictions."""
    await interaction.response.defer(ephemeral=True)
    
    try:
        ws = get_predictions_ws()
        rows = ws.get_all_values()
    except gspread.WorksheetNotFound:
        await interaction.followup.send("❌ Predictions sheet not found.", ephemeral=True)
        return
    
    if not rows or len(rows) < 2:
        await interaction.followup.send("📭 You have no predictions yet.", ephemeral=True)
        return
    
    discord_id_str = str(interaction.user.id)
    
    # Find column indices
    header = rows[0]
    discord_id_col = 1
    prediction_type_col = 3
    target_date_col = 4
    prediction_value_col = 5
    resolved_col = 7
    
    for idx, col_name in enumerate(header):
        col_lower = col_name.lower()
        if "discord_id" in col_lower:
            discord_id_col = idx
        elif "prediction_type" in col_lower:
            prediction_type_col = idx
        elif "target_date" in col_lower:
            target_date_col = idx
        elif "prediction_value" in col_lower:
            prediction_value_col = idx
        elif "resolved" in col_lower:
            resolved_col = idx
    
    active_predictions = []
    for row in rows[1:]:
        if len(row) <= max(discord_id_col, resolved_col):
            continue
        
        if row[discord_id_col] != discord_id_str:
            continue
        
        if len(row) > resolved_col and row[resolved_col].lower() in ["true", "yes", "1"]:
            continue  # Skip resolved predictions
        
        pred_type = row[prediction_type_col] if len(row) > prediction_type_col else ""
        target_date = row[target_date_col] if len(row) > target_date_col else ""
        pred_value = row[prediction_value_col] if len(row) > prediction_value_col else ""
        
        active_predictions.append({
            "type": pred_type,
            "target_date": target_date,
            "value": pred_value
        })
    
    if not active_predictions:
        await interaction.followup.send("📭 You have no active predictions.", ephemeral=True)
        return
    
    lines = ["📊 **Your Active Predictions**", ""]
    for i, pred in enumerate(active_predictions, 1):
        lines.append(f"**{i}. {pred['type'].upper()}** - {pred['target_date']}")
        if pred['type'] == "volume":
            try:
                vol = float(pred['value'])
                lines.append(f"   💰 Predicted: **${vol:.3f} billion**")
            except ValueError:
                lines.append(f"   💰 Predicted: {pred['value']}")
        elif pred['type'] == "top10":
            try:
                data = json.loads(pred['value'])
                if data.get("new_entries"):
                    lines.append(f"   🆕 New entries: {', '.join(data['new_entries'])}")
                if data.get("removed_entries"):
                    lines.append(f"   ❌ Removed: {', '.join(data['removed_entries'])}")
            except (json.JSONDecodeError, TypeError):
                lines.append(f"   📝 {pred['value']}")
        lines.append("")
    
    await interaction.followup.send("\n".join(lines), ephemeral=True)


@bot.tree.command(name="prediction_leaderboard", description="View the prediction game leaderboard")
@app_commands.describe(
    limit="Number of top predictors to show (default: 10, max: 25)"
)
async def prediction_leaderboard(interaction: discord.Interaction, limit: int = 10):
    """Show prediction game leaderboard based on total XP from predictions."""
    await interaction.response.defer(ephemeral=False)
    
    if not (1 <= limit <= 25):
        await interaction.followup.send("❌ Limit must be between 1 and 25.", ephemeral=True)
        return
    
    try:
        # Get XP events for prediction sources
        ws = get_xp_events_ws()
        rows = ws.get_all_values()
    except gspread.WorksheetNotFound:
        await interaction.followup.send("❌ XP events sheet not found.", ephemeral=True)
        return
    
    if not rows or len(rows) < 2:
        await interaction.followup.send("📊 No prediction data yet.", ephemeral=False)
        return
    
    # Find columns
    header = rows[0]
    discord_id_col = 1
    discord_name_col = 2
    source_col = 4
    amount_col = 5
    
    for idx, col_name in enumerate(header):
        col_lower = col_name.lower()
        if "discord_id" in col_lower:
            discord_id_col = idx
        elif "discord_name" in col_lower or "name" in col_lower:
            discord_name_col = idx
        elif "source" in col_lower:
            source_col = idx
        elif "amount" in col_lower or "xp" in col_lower:
            amount_col = idx
    
    # Calculate total XP from predictions per user
    user_scores: Dict[str, Dict[str, Any]] = {}
    
    for row in rows[1:]:
        if len(row) <= max(discord_id_col, source_col, amount_col):
            continue
        
        source = row[source_col].lower() if len(row) > source_col else ""
        if "prediction" not in source:
            continue
        
        discord_id = row[discord_id_col] if len(row) > discord_id_col else ""
        discord_name = row[discord_name_col] if len(row) > discord_name_col else "Unknown"
        
        try:
            amount = int(float(row[amount_col])) if len(row) > amount_col else 0
        except (ValueError, TypeError):
            continue
        
        if discord_id not in user_scores:
            user_scores[discord_id] = {
                "name": discord_name,
                "total_xp": 0,
                "predictions": 0
            }
        
        user_scores[discord_id]["total_xp"] += amount
        if amount > 0:
            user_scores[discord_id]["predictions"] += 1
    
    if not user_scores:
        await interaction.followup.send("📊 No prediction XP awarded yet.", ephemeral=False)
        return
    
    # Sort by total XP
    sorted_users = sorted(user_scores.items(), key=lambda x: x[1]["total_xp"], reverse=True)
    
    lines = ["🏆 **Prediction Game Leaderboard**", ""]
    for i, (discord_id, data) in enumerate(sorted_users[:limit], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        lines.append(f"{medal} **{data['name']}** - {data['total_xp']} XP ({data['predictions']} predictions)")
    
    await interaction.followup.send("\n".join(lines), ephemeral=False)


# -------------------------------
# Admin Commands - Bot Control
# -------------------------------

@bot.tree.command(name="bot_component_toggle", description="Enable or disable a bot component (Admin only)")
@app_commands.describe(
    component="Component to toggle",
    enabled="True to enable, False to disable"
)
@admin_or_role_only(get_admin_role_list)
async def bot_component_toggle(interaction: discord.Interaction, component: str, enabled: bool):
    """Toggle a bot component on/off."""
    await interaction.response.defer(ephemeral=True)
    
    valid_components = {
        "leaderboard_checking": "Leaderboard Checking (Top 10 TX announcements)",
        "volume_checking": "Volume Checking (Milestones & channel updates)",
        "daily_summary": "Daily Summary (23:59 UTC)",
        "prediction_resolution": "Prediction Resolution",
        "metrics_quiz": "Metrics Quiz (Daily at 23:59 UTC)",
        "thread_cleanup": "Thread Cleanup",
    }
    
    if component not in valid_components:
        await interaction.followup.send(
            f"❌ Invalid component. Valid components:\n" + 
            "\n".join(f"- `{k}`: {v}" for k, v in valid_components.items()),
            ephemeral=True
        )
        return
    
    # Update state
    if "components_enabled" not in state:
        state["components_enabled"] = {}
    state["components_enabled"][component] = enabled
    save_state(state)
    
    status = "✅ Enabled" if enabled else "❌ Disabled"
    await interaction.followup.send(
        f"{status} **{valid_components[component]}**\n"
        f"Component: `{component}`",
        ephemeral=True
    )


@bot_component_toggle.autocomplete('component')
async def bot_component_toggle_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Autocomplete for component names."""
    valid_components = {
        "leaderboard_checking": "Leaderboard Checking (Top 10 TX announcements)",
        "volume_checking": "Volume Checking (Milestones & channel updates)",
        "daily_summary": "Daily Summary (23:59 UTC)",
        "prediction_resolution": "Prediction Resolution",
        "metrics_quiz": "Metrics Quiz (Daily at 23:59 UTC)",
        "thread_cleanup": "Thread Cleanup",
    }
    
    # Filter components based on current input
    matches = [
        app_commands.Choice(name=display_name, value=comp_id)
        for comp_id, display_name in valid_components.items()
        if current.lower() in comp_id.lower() or current.lower() in display_name.lower()
    ]
    
    # Return up to 25 choices (Discord limit)
    return matches[:25]
    
    # Update state
    if "components_enabled" not in state:
        state["components_enabled"] = {}
    state["components_enabled"][component] = enabled
    save_state(state)
    
    status = "✅ Enabled" if enabled else "❌ Disabled"
    await interaction.followup.send(
        f"{status} **{valid_components[component]}**\n"
        f"Component: `{component}`",
        ephemeral=True
    )


@bot.tree.command(name="bot_component_status", description="View status of all bot components (Admin only)")
@admin_or_role_only(get_admin_role_list)
async def bot_component_status(interaction: discord.Interaction):
    """Show status of all bot components."""
    await interaction.response.defer(ephemeral=True)
    
    components = {
        "leaderboard_checking": "Leaderboard Checking",
        "volume_checking": "Volume Checking",
        "daily_summary": "Daily Summary",
        "prediction_resolution": "Prediction Resolution",
        "metrics_quiz": "Metrics Quiz",
        "thread_cleanup": "Thread Cleanup",
    }
    
    enabled_status = state.get("components_enabled", {})
    
    lines = ["🔧 **Bot Component Status**", ""]
    for comp_id, comp_name in components.items():
        is_enabled = enabled_status.get(comp_id, True)
        status_icon = "✅" if is_enabled else "❌"
        status_text = "Enabled" if is_enabled else "Disabled"
        lines.append(f"{status_icon} **{comp_name}**: {status_text}")
    
    # Add task running status
    lines.append("")
    lines.append("**Task Status:**")
    lines.append(f"Leaderboard: {'🟢 Running' if check_leaderboard.is_running() else '🔴 Stopped'}")
    lines.append(f"Volume: {'🟢 Running' if check_volume.is_running() else '🔴 Stopped'}")
    lines.append(f"Daily Summary: {'🟢 Running' if daily_summary.is_running() else '🔴 Stopped'}")
    lines.append(f"Daily Leaderboard: {'🟢 Running' if post_daily_leaderboard.is_running() else '🔴 Stopped'}")
    
    # For prediction resolution, show if task is running AND component is enabled
    pred_task_running = resolve_predictions.is_running()
    pred_enabled = enabled_status.get("prediction_resolution", True)
    if pred_task_running and not pred_enabled:
        lines.append(f"Prediction Resolution: 🟡 Running (Component Disabled)")
    else:
        lines.append(f"Prediction Resolution: {'🟢 Running' if pred_task_running else '🔴 Stopped'}")
    
    lines.append(f"Metrics Quiz: {'🟢 Running' if schedule_metrics_quiz_announcements.is_running() else '🔴 Stopped'}")
    lines.append(f"Thread Cleanup: {'🟢 Running' if cleanup_threads.is_running() else '🔴 Stopped'}")
    
    await interaction.followup.send("\n".join(lines), ephemeral=True)


@bot.tree.command(name="bot_setup_metrics_channel", description="Set the channel for metrics announcements (Admin only)")
@app_commands.describe(
    channel="Channel to use for metrics announcements"
)
@admin_or_role_only(get_admin_role_list)
async def bot_setup_metrics_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """Set the metrics announcement channel."""
    await interaction.response.defer(ephemeral=True)
    
    # Update state (we'll use this for metrics quiz channel)
    state["metrics_quiz_channel_id"] = channel.id
    save_state(state)
    
    await interaction.followup.send(
        f"✅ Metrics quiz channel set to {channel.mention}\n"
        f"Channel ID: `{channel.id}`",
        ephemeral=True
    )


@bot.tree.command(name="bot_setup", description="Configure bot channels and settings (Admin only)")
@app_commands.describe(
    main_metrics_channel="Main channel for metrics announcements (daily summary, top 10 TX)",
    metrics_quiz_channel="Channel for daily metrics quiz posts",
    volume_channel="Voice channel for volume counter (set to None to disable)",
    leaderboard_channel="Channel for daily XP leaderboard posts",
    admin_role="Admin role name (users with this role can use admin commands)",
    tweet_xp_daily_limit="Maximum number of tweets per day that can earn XP (default: 3)"
)
@admin_or_role_only(get_admin_role_list)
async def bot_setup(interaction: discord.Interaction,
                    main_metrics_channel: Optional[discord.TextChannel] = None,
                    metrics_quiz_channel: Optional[discord.TextChannel] = None,
                    volume_channel: Optional[discord.VoiceChannel] = None,
                    leaderboard_channel: Optional[discord.TextChannel] = None,
                    admin_role: Optional[str] = None,
                    tweet_xp_daily_limit: Optional[int] = None):
    """Configure all bot channels and settings in one command."""
    await interaction.response.defer(ephemeral=True)
    
    changes = []
    
    # Update main metrics channel
    if main_metrics_channel is not None:
        state["main_metrics_channel_id"] = main_metrics_channel.id
        changes.append(f"✅ Main metrics channel: {main_metrics_channel.mention} (ID: `{main_metrics_channel.id}`)")
    
    # Update metrics quiz channel
    if metrics_quiz_channel is not None:
        state["metrics_quiz_channel_id"] = metrics_quiz_channel.id
        changes.append(f"✅ Metrics quiz channel: {metrics_quiz_channel.mention} (ID: `{metrics_quiz_channel.id}`)")
    
    # Update volume channel
    # Note: To disable, use the separate /bot_setup_volume_channel command with no channel
    if volume_channel is not None:
        state["volume_channel_id"] = volume_channel.id
        changes.append(f"✅ Volume channel: {volume_channel.mention} (ID: `{volume_channel.id}`)")
    
    # Update leaderboard channel
    if leaderboard_channel is not None:
        state["leaderboard_channel_id"] = leaderboard_channel.id
        changes.append(f"✅ Leaderboard channel: {leaderboard_channel.mention} (ID: `{leaderboard_channel.id}`)")
    
    # Update admin role name
    if admin_role is not None:
        state["admin_role_name"] = admin_role.strip()
        changes.append(f"✅ Admin role: `{admin_role.strip()}`")
    
    # Update tweet XP daily limit
    if tweet_xp_daily_limit is not None:
        if tweet_xp_daily_limit < 0:
            await interaction.followup.send(
                "❌ Tweet XP daily limit must be 0 or greater.",
                ephemeral=True
            )
            return
        state["tweet_xp_daily_limit"] = tweet_xp_daily_limit
        changes.append(f"✅ Tweet XP daily limit: **{tweet_xp_daily_limit}** tweets per day")
    
    # Note: quiz_min_posts is handled by separate command /bot_set_quiz_min_posts
    
    if changes:
        save_state(state)
        response = "🔧 **Bot Configuration Updated**\n\n" + "\n".join(changes)
    else:
        # Show current configuration
        main_id = state.get("main_metrics_channel_id") or CHANNEL_ID
        quiz_id = state.get("metrics_quiz_channel_id")
        volume_id = state.get("volume_channel_id") or VOLUME_CHANNEL_ID
        leaderboard_id = state.get("leaderboard_channel_id") or 1445475021890785383
        
        main_ch = bot.get_channel(main_id)
        quiz_ch = bot.get_channel(quiz_id) if quiz_id else None
        volume_ch = bot.get_channel(volume_id) if volume_id else None
        leaderboard_ch = bot.get_channel(leaderboard_id)
        
        admin_role_name = get_admin_role_name()
        tweet_xp_limit = state.get("tweet_xp_daily_limit", 3)
        min_posts = get_min_discord_posts()
        excluded_channels = get_excluded_channel_ids()
        excluded_str = ", ".join([f"`{cid}`" for cid in excluded_channels])
        response = "🔧 **Current Bot Configuration**\n\n"
        response += f"**Main Metrics Channel:** {main_ch.mention if main_ch else f'Not found (ID: {main_id})'}\n"
        response += f"**Metrics Quiz Channel:** {quiz_ch.mention if quiz_ch else f'Not set (using main channel)'}\n"
        response += f"**Volume Channel:** {volume_ch.mention if volume_ch else 'Disabled'}\n"
        response += f"**Leaderboard Channel:** {leaderboard_ch.mention if leaderboard_ch else f'Not found (ID: {leaderboard_id})'}\n"
        response += f"**Admin Role:** `{admin_role_name}`\n"
        response += f"**Tweet XP Daily Limit:** {tweet_xp_limit} tweets per day\n"
        response += f"**Min Discord Posts (Shared):** {min_posts} posts (use `/bot_set_min_posts` to change)\n"
        response += f"**Excluded Channels:** {excluded_str}\n\n"
        response += "💡 To update a setting, provide the parameter. To disable volume channel, use `/bot_setup_volume_channel` with no channel."
    
    await interaction.followup.send(response, ephemeral=True)


@bot.tree.command(name="bot_setup_volume_channel", description="Set the voice channel for volume counter (Admin only)")
@app_commands.describe(
    channel="Voice channel to use for volume counter (or None to disable)"
)
@admin_or_role_only(get_admin_role_list)
async def bot_setup_volume_channel(interaction: discord.Interaction, channel: Optional[discord.VoiceChannel] = None):
    """Set the volume counter voice channel."""
    await interaction.response.defer(ephemeral=True)
    
    if channel:
        state["volume_channel_id"] = channel.id
        save_state(state)
        await interaction.followup.send(
            f"✅ Volume channel set to {channel.mention}\n"
            f"Channel ID: `{channel.id}`",
            ephemeral=True
        )
    else:
        state["volume_channel_id"] = None
        save_state(state)
        await interaction.followup.send(
            "✅ Volume channel disabled.",
            ephemeral=True
        )


@bot.tree.command(name="bot_set_min_posts", description="Set minimum Discord posts required for XP-earning activities (Admin only)")
@admin_or_role_only(get_admin_role_list)
@app_commands.describe(
    min_posts="Minimum number of Discord posts required to earn XP (default: 3, applies to quizzes and other features)"
)
async def bot_set_min_posts(interaction: discord.Interaction, min_posts: int):
    """Set the minimum number of Discord posts required for users to earn XP.
    
    This is a shared configuration used across multiple features (quizzes, etc.)
    as an anti-bot measure. Users with fewer posts can still participate but won't earn XP (shadow ban).
    """
    await interaction.response.defer(ephemeral=True)
    
    if min_posts < 0:
        await interaction.followup.send("❌ Minimum posts must be 0 or greater.", ephemeral=True)
        return
    
    if min_posts > 100:
        await interaction.followup.send("❌ Minimum posts cannot exceed 100.", ephemeral=True)
        return
    
    old_value = get_min_discord_posts()
    state["min_discord_posts"] = min_posts
    # Also update legacy key for backward compatibility
    state["quiz_min_discord_posts"] = min_posts
    save_state(state)
    
    excluded_channels = get_excluded_channel_ids()
    excluded_str = ", ".join([f"`{cid}`" for cid in excluded_channels])
    
    await interaction.followup.send(
        f"✅ **Minimum Discord Posts Updated**\n\n"
        f"Previous value: **{old_value}** posts\n"
        f"New value: **{min_posts}** posts\n\n"
        f"Users now need at least **{min_posts}** Discord posts to earn XP from quizzes and other activities.\n"
        f"Users with fewer posts can still participate but won't earn XP (shadow ban).\n\n"
        f"**Excluded channels:** {excluded_str} (not counted)",
        ephemeral=True
    )
    log_or_print("info", f"[BotSetup] Admin {interaction.user} set min_discord_posts to {min_posts} (was {old_value})")


@bot.tree.command(name="bot_set_quiz_min_posts", description="Set minimum Discord posts required for quiz XP (Admin only) - Use /bot_set_min_posts instead")
@admin_or_role_only(get_admin_role_list)
@app_commands.describe(
    min_posts="Minimum number of Discord posts required to earn XP from quizzes (default: 3)"
)
async def bot_set_quiz_min_posts(interaction: discord.Interaction, min_posts: int):
    """Legacy command - redirects to /bot_set_min_posts for consistency."""
    await interaction.response.defer(ephemeral=True)
    
    # Just call the new command's logic
    if min_posts < 0:
        await interaction.followup.send("❌ Minimum posts must be 0 or greater.", ephemeral=True)
        return
    
    if min_posts > 100:
        await interaction.followup.send("❌ Minimum posts cannot exceed 100.", ephemeral=True)
        return
    
    old_value = get_min_discord_posts()
    state["min_discord_posts"] = min_posts
    state["quiz_min_discord_posts"] = min_posts  # Backward compatibility
    save_state(state)
    
    await interaction.followup.send(
        f"✅ **Minimum Discord Posts Updated**\n\n"
        f"Previous value: **{old_value}** posts\n"
        f"New value: **{min_posts}** posts\n\n"
        f"💡 **Note:** This setting is now shared across all features. Use `/bot_set_min_posts` for future updates.",
        ephemeral=True
    )
    log_or_print("info", f"[BotSetup] Admin {interaction.user} set min_discord_posts to {min_posts} via legacy command (was {old_value})")


@bot.tree.command(name="bot_manual_quiz_post", description="Manually post a metrics quiz announcement (Admin only)")
@admin_or_role_only(get_admin_role_list)
async def bot_manual_quiz_post(interaction: discord.Interaction):
    """Manually trigger a metrics quiz announcement."""
    await interaction.response.defer(ephemeral=True)
    
    try:
        await post_metrics_quiz_announcement(num_questions=3)
        await interaction.followup.send(
            "✅ Metrics quiz announcement posted successfully!",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error posting quiz: {e}",
            ephemeral=True
        )


# -------------------------------
# Events / startup
# -------------------------------

# -------------------------------
# Thread cleanup task (fixed)
# -------------------------------

@tasks.loop(minutes=10)
async def cleanup_threads():
    """Clean up inactive quiz threads created by the bot."""
    await bot.wait_until_ready()
    
    # Check if component is enabled
    if not state.get("components_enabled", {}).get("thread_cleanup", True):
        return
    
    now = datetime.datetime.utcnow()

    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                # Skip if the bot can't see this channel
                if not channel.permissions_for(guild.me).read_messages:
                    continue

                # Fix: Get threads properly - threads attribute exists on TextChannel
                threads = []
                if hasattr(channel, 'threads'):
                    threads = channel.threads
                else:
                    # Fallback: get from guild threads
                    threads = [t for t in guild.threads if t.parent_id == channel.id]

                for thread in threads:
                    # Only delete threads created by this bot
                    if thread.owner_id != bot.user.id:
                        continue

                    # If no activity for 1 hour
                    last = thread.last_message_at or thread.created_at
                    if last:
                        # Handle timezone-aware datetime
                        if last.tzinfo:
                            last_naive = last.replace(tzinfo=None)
                        else:
                            last_naive = last
                        if (now - last_naive).total_seconds() > 3600:
                            try:
                                await thread.delete()
                                if logger:
                                    logger.debug(f"Deleted inactive thread: {thread.name}")
                                await asyncio.sleep(1.0)  # Rate limit protection
                            except discord.NotFound:
                                pass  # Already deleted
                            except Exception as e:
                                if logger:
                                    logger.warning(f"Failed to delete thread {thread.name}: {e}")

            except Exception as e:
                # Don't spam errors for channels that don't support threads
                if "'TextChannel' object has no attribute" not in str(e):
                    if logger:
                        logger.warning(f"Failed thread cleanup in {channel.name}: {e}")


@bot.event
async def on_ready():
    logger.info(f"Bot logged in as {bot.user} (ID: {bot.user.id})")
    logger.info(f"Connected to {len(bot.guilds)} guild(s)")

    # Initialize chain cache
    global CHAIN_CACHE
    CHAIN_CACHE = load_chain_cache()
    # Save cache to ensure manual mappings are persisted
    save_chain_cache()
    logger.info(f"Loaded {len(CHAIN_CACHE)} chain(s) from cache (including {len(MANUAL_CHAIN_MAPPING)} manual mappings)")
    # Log manual mappings for debugging
    for chain_id, name in MANUAL_CHAIN_MAPPING.items():
        if chain_id in CHAIN_CACHE:
            logger.info(f"[ChainLookup] Manual mapping: Chain {chain_id} -> {CHAIN_CACHE[chain_id]['name']}")

    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} app command(s)")
    except Exception as e:
        logger.error(f"Error syncing commands: {e}", exc_info=True)
        log_error_with_notification("CommandSyncError", e)

    # Start tasks with error handling
    tasks_to_start = [
        ("check_leaderboard", check_leaderboard),
        ("check_volume", check_volume),
        ("daily_summary", daily_summary),
        ("post_daily_leaderboard", post_daily_leaderboard),
        ("resolve_predictions", resolve_predictions),
        ("schedule_metrics_quiz_announcements", schedule_metrics_quiz_announcements),
        ("cleanup_threads", cleanup_threads),
        ("auto_process_ungraded_tweets", auto_process_ungraded_tweets),
    ]
    
    # Start tweet submission queue processor (Phase 2: Queue-based batching)
    try:
        if not tweet_queue_processor_running:
            bot.loop.create_task(process_tweet_submission_queue())
            logger.info("Started tweet submission queue processor")
    except Exception as e:
        logger.error(f"Failed to start tweet submission queue processor: {e}", exc_info=True)
        log_error_with_notification("TweetQueueProcessorStartError", e)
    
    for task_name, task in tasks_to_start:
        try:
            if not task.is_running():
                task.start()
                logger.info(f"Started task: {task_name}")
        except Exception as e:
            logger.error(f"Failed to start task {task_name}: {e}", exc_info=True)
            log_error_with_notification(f"TaskStartError_{task_name}", e)


@bot.event
async def on_error(event: str, *args: Any, **kwargs: Any) -> None:
    """Global error handler for Discord events.
    
    Catches unhandled exceptions in Discord event handlers and logs them,
    optionally notifying admins of critical errors.
    
    Args:
        event: Name of the event where the error occurred
        *args: Additional event arguments
        **kwargs: Additional event keyword arguments
    """
    logger.error(f"Unhandled error in event {event}", exc_info=True)
    error = sys.exc_info()[1]
    if error:
        log_error_with_notification(f"DiscordEventError_{event}", error)


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception) -> None:
    """Handle command errors.
    
    Logs command errors and notifies admins. Ignores CommandNotFound errors
    as they are expected when users type invalid commands.
    
    Args:
        ctx: Command context
        error: The exception that was raised
    """
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore command not found errors
    
    logger.error(f"Command error in {ctx.command}: {error}", exc_info=True)
    log_error_with_notification(f"CommandError_{ctx.command}", error)


# -------------------------------
# Configuration Validation
# -------------------------------

def validate_configuration() -> Tuple[bool, List[str]]:
    """Validate bot configuration on startup.
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    warnings = []
    
    # Required configuration
    if TOKEN == "YOUR_DISCORD_BOT_TOKEN" or not TOKEN:
        errors.append("DISCORD_TOKEN is not set. Please set it in your .env file or environment variables.")
    
    if CHANNEL_ID == 123456789012345678:
        warnings.append("METRICS_CHANNEL_ID is using default value. Set it in your .env file.")
    
    # Google Sheets configuration
    if not os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
        errors.append(f"Google service account file not found: {GOOGLE_SERVICE_ACCOUNT_FILE}")
    
    # Optional but recommended configuration
    if not TWITTER_BEARER_TOKEN:
        warnings.append("TWITTER_BEARER_TOKEN not set. Tweet text fetching will be disabled.")
    
    if not OPENAI_API_KEY:
        warnings.append("OPENAI_API_KEY not set. Automatic tweet grading will be disabled.")
    
    # Validate state file is readable/writable
    try:
        test_state = load_state()
        save_state(test_state)  # Test write
    except Exception as e:
        warnings.append(f"State file may have issues: {e}")
    
    # Log warnings
    for warning in warnings:
        logger.warning(f"[Config Validation] {warning}")
    
    # Log errors
    for error in errors:
        logger.error(f"[Config Validation] {error}")
    
    return len(errors) == 0, errors


# -------------------------------
# Graceful Shutdown Handler
# -------------------------------

def setup_graceful_shutdown() -> None:
    """Setup signal handlers for graceful shutdown.
    
    Registers handlers for SIGINT and SIGTERM signals to allow the bot
    to shut down gracefully, saving state and stopping tasks cleanly.
    """
    import signal
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        asyncio.create_task(shutdown_bot())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def shutdown_bot():
    """Gracefully shutdown the bot."""
    logger.info("Shutting down bot...")
    
    # Save state
    try:
        save_state(state)
        logger.info("State saved successfully")
    except Exception as e:
        logger.error(f"Error saving state during shutdown: {e}", exc_info=True)
    
    # Stop all tasks
    tasks_to_stop = [
        ("check_leaderboard", check_leaderboard),
        ("check_volume", check_volume),
        ("daily_summary", daily_summary),
        ("post_daily_leaderboard", post_daily_leaderboard),
        ("resolve_predictions", resolve_predictions),
        ("schedule_metrics_quiz_announcements", schedule_metrics_quiz_announcements),
        ("cleanup_threads", cleanup_threads),
    ]
    
    for task_name, task in tasks_to_stop:
        if task.is_running():
            try:
                task.cancel()
                logger.info(f"Stopped task: {task_name}")
            except Exception as e:
                logger.error(f"Error stopping task {task_name}: {e}", exc_info=True)
    
    # Close bot connection
    try:
        await bot.close()
        logger.info("Bot connection closed")
    except Exception as e:
        logger.error(f"Error closing bot connection: {e}", exc_info=True)
    
    logger.info("Shutdown complete")


if __name__ == "__main__":
    # Validate configuration
    is_valid, errors = validate_configuration()
    if not is_valid:
        error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.critical(error_msg)
        raise RuntimeError(error_msg)
    
    logger.info("Configuration validation passed")
    
    # Setup graceful shutdown
    setup_graceful_shutdown()
    
    try:
        logger.info("Starting bot...")
        bot.run(TOKEN, log_handler=None)  # We handle logging ourselves
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
    except Exception as e:
        logger.critical(f"Fatal error starting bot: {e}", exc_info=True)
        log_error_with_notification("FatalStartupError", e)
        raise
