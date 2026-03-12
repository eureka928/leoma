"""
Runtime environment and logging.

Loads configuration from the environment and provides console logging helpers.
"""

import inspect
import logging
import os
import sys
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

# Standard logger for leoma; use log_exception() in production to avoid full tracebacks
logger = logging.getLogger("leoma")


def _is_production() -> bool:
    env = os.environ.get("LEOMA_ENV", os.environ.get("ENVIRONMENT", "")).lower()
    return env == "production"


def log_exception(message: str, exc: Optional[BaseException] = None) -> None:
    """Log an exception; in production omit full traceback to avoid leaking paths."""
    if _is_production():
        detail = str(exc) if exc else ""
        logger.error("%s %s", message, detail)
    else:
        logger.exception("%s", message, exc_info=exc is None or True)

USED_VIDEOS: List[str] = []

_RESET = "\033[0m"
_DIM = "\033[90m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_BOLD = "\033[1m"
_HEADER_WIDTH = 60
_LEVEL_TOKENS = {
    "info": f"{_CYAN}▸{_RESET}",
    "success": f"{_GREEN}✓{_RESET}",
    "error": f"{_RED}✗{_RESET}",
    "warn": f"{_YELLOW}⚠{_RESET}",
    "start": f"{_YELLOW}→{_RESET}",
}


def _read_str(name: str, fallback: str) -> str:
    return os.environ.get(name, fallback)


def _read_int(name: str, fallback: int) -> int:
    return int(os.environ.get(name, str(fallback)))


def _read_float(name: str, fallback: float) -> float:
    return float(os.environ.get(name, str(fallback)))


def _read_optional_str(name: str) -> Optional[str]:
    return os.environ.get(name)


def _wall_clock() -> str:
    """Return full datetime string: YYYY-MM-DD HH:MM:SS"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_caller_line() -> int:
    """Get the line number where emit_log was called."""
    # Walk up the stack to find the caller outside this file
    for frame_info in inspect.stack():
        # Skip frames inside runtime.py (where emit_log is defined)
        if frame_info.filename != __file__:
            return frame_info.lineno
    return 0


def _prefix(level: str, ts: str, line: int) -> str:
    timestamp = f"{_DIM}{ts}{_RESET}"
    line_info = f"{_DIM}L{line}{_RESET}"
    return f"{timestamp} {line_info} {_LEVEL_TOKENS.get(level, ' ')}"


def emit_log(msg: str, level: str = "info") -> None:
    """Print a timestamped log line with level prefix and caller line number."""
    ts = _wall_clock()
    line = _get_caller_line()
    print(f"{_prefix(level, ts, line)} {msg}")


def emit_header(title: str) -> None:
    """Print a bold section header."""
    rule = "─" * _HEADER_WIDTH
    print(f"\n{_BOLD}{rule}{_RESET}\n{_BOLD}{title}{_RESET}\n{_BOLD}{rule}{_RESET}\n")


class Settings:
    """Central settings loaded from the environment."""

    def __init__(self) -> None:
        self.netuid = _read_int("NETUID", 99)
        self.epoch_len = _read_int("EPOCH_LEN", 180)
        self.request_timeout = _read_int("REQUEST_TIMEOUT", 600)
        self.chutes_api_url = _read_str("CHUTES_API_URL", "https://api.chutes.ai")
        self.chutes_api_key = _read_optional_str("CHUTES_API_KEY")
        self.wallet_name = _read_str("WALLET_NAME", "default")
        self.hotkey_name = _read_str("HOTKEY_NAME", "default")
        self.network = _read_str("NETWORK", "finney")
        self.hippius_endpoint = _read_str("HIPPIUS_ENDPOINT", "s3.hippius.com")
        self.hippius_region = _read_str("HIPPIUS_REGION", "decentralized")
        self.hippius_videos_read_access_key = _read_optional_str("HIPPIUS_VIDEOS_READ_ACCESS_KEY")
        self.hippius_videos_read_secret_key = _read_optional_str("HIPPIUS_VIDEOS_READ_SECRET_KEY")
        self.hippius_videos_write_access_key = _read_optional_str("HIPPIUS_VIDEOS_WRITE_ACCESS_KEY")
        self.hippius_videos_write_secret_key = _read_optional_str("HIPPIUS_VIDEOS_WRITE_SECRET_KEY")
        self.hippius_samples_read_access_key = _read_optional_str("HIPPIUS_SAMPLES_READ_ACCESS_KEY")
        self.hippius_samples_read_secret_key = _read_optional_str("HIPPIUS_SAMPLES_READ_SECRET_KEY")
        self.hippius_samples_write_access_key = _read_optional_str("HIPPIUS_SAMPLES_WRITE_ACCESS_KEY")
        self.hippius_samples_write_secret_key = _read_optional_str("HIPPIUS_SAMPLES_WRITE_SECRET_KEY")
        self.source_bucket = _read_str("HIPPIUS_SOURCE_BUCKET", "videos")
        self.samples_bucket = _read_str("HIPPIUS_SAMPLES_BUCKET", "samples")
        self.openai_api_key = _read_optional_str("OPENAI_API_KEY")
        self.min_video_size = _read_int("MIN_VIDEO_SIZE", 1_000_000)
        self.max_video_size = _read_int("MAX_VIDEO_SIZE", 200_000_000)
        self.clip_duration = _read_int("CLIP_DURATION", 5)
        self.max_video_history = _read_int("MAX_VIDEO_HISTORY", 50)
        self.chute_cache_ttl = _read_int("CHUTE_CACHE_TTL", 300)
        self.max_concurrent_miners = _read_int("MAX_CONCURRENT_MINERS", 5)
        self.database_url = _read_optional_str("DATABASE_URL")
        self.postgres_host = _read_str("POSTGRES_HOST", "localhost")
        self.postgres_port = _read_str("POSTGRES_PORT", "5432")
        self.postgres_user = _read_str("POSTGRES_USER", "leoma")
        self.postgres_password = _read_str("POSTGRES_PASSWORD", "leoma")
        self.postgres_db = _read_str("POSTGRES_DB", "leoma")
        self.hf_token = _read_optional_str("HF_TOKEN")
        self.model_hash_cache_ttl = _read_int("MODEL_HASH_CACHE_TTL", 3600)
        self.corpus_min_duration = _read_int("CORPUS_MIN_DURATION", 5)
        self.corpus_max_duration = _read_int("CORPUS_MAX_DURATION", 300)
        self.corpus_target_resolution = _read_str("CORPUS_TARGET_RESOLUTION", "720")
        self.corpus_max_filesize = _read_int("CORPUS_MAX_FILESIZE", 200_000_000)
        self.min_validator_stake = _read_float("MIN_VALIDATOR_STAKE", 1000.0)
        self.validator_sync_interval = _read_int("VALIDATOR_SYNC_INTERVAL", 600)


_settings_instance = Settings()
settings = _settings_instance

NETUID = settings.netuid
EPOCH_LEN = settings.epoch_len
REQUEST_TIMEOUT = settings.request_timeout
CHUTES_API_URL = settings.chutes_api_url
CHUTES_API_KEY = settings.chutes_api_key
WALLET_NAME = settings.wallet_name
HOTKEY_NAME = settings.hotkey_name
NETWORK = settings.network
HIPPIUS_ENDPOINT = settings.hippius_endpoint
HIPPIUS_REGION = settings.hippius_region
HIPPIUS_VIDEOS_READ_ACCESS_KEY = settings.hippius_videos_read_access_key
HIPPIUS_VIDEOS_READ_SECRET_KEY = settings.hippius_videos_read_secret_key
HIPPIUS_VIDEOS_WRITE_ACCESS_KEY = settings.hippius_videos_write_access_key
HIPPIUS_VIDEOS_WRITE_SECRET_KEY = settings.hippius_videos_write_secret_key
HIPPIUS_SAMPLES_READ_ACCESS_KEY = settings.hippius_samples_read_access_key
HIPPIUS_SAMPLES_READ_SECRET_KEY = settings.hippius_samples_read_secret_key
HIPPIUS_SAMPLES_WRITE_ACCESS_KEY = settings.hippius_samples_write_access_key
HIPPIUS_SAMPLES_WRITE_SECRET_KEY = settings.hippius_samples_write_secret_key
SOURCE_BUCKET = settings.source_bucket
SAMPLES_BUCKET = settings.samples_bucket
OPENAI_API_KEY = settings.openai_api_key
MIN_VIDEO_SIZE = settings.min_video_size
MAX_VIDEO_SIZE = settings.max_video_size
CLIP_DURATION = settings.clip_duration
MAX_VIDEO_HISTORY = settings.max_video_history
CHUTE_CACHE_TTL = settings.chute_cache_ttl
MAX_CONCURRENT_MINERS = settings.max_concurrent_miners
DATABASE_URL = settings.database_url
POSTGRES_HOST = settings.postgres_host
POSTGRES_PORT = settings.postgres_port
POSTGRES_USER = settings.postgres_user
POSTGRES_PASSWORD = settings.postgres_password
POSTGRES_DB = settings.postgres_db
HF_TOKEN = settings.hf_token
MODEL_HASH_CACHE_TTL = settings.model_hash_cache_ttl
CORPUS_MIN_DURATION = settings.corpus_min_duration
CORPUS_MAX_DURATION = settings.corpus_max_duration
CORPUS_TARGET_RESOLUTION = settings.corpus_target_resolution
CORPUS_MAX_FILESIZE = settings.corpus_max_filesize
MIN_VALIDATOR_STAKE = settings.min_validator_stake
VALIDATOR_SYNC_INTERVAL = settings.validator_sync_interval

# Ensure leoma logger has a handler when not configured by application
if not logger.handlers:
    _log_level = getattr(
        logging,
        os.environ.get("LOG_LEVEL", "INFO").upper(),
        logging.INFO,
    )
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
    logger.setLevel(_log_level)
    logger.addHandler(_handler)
