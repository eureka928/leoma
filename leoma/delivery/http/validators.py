"""
FastAPI dependencies for path/query parameter validation.

Validates SS58 hotkey path and query parameters; returns 400 for invalid format.
"""

from fastapi import HTTPException

from leoma.delivery.http.contracts import validate_ss58_hotkey


def validate_hotkey(hotkey: str) -> str:
    """Validate path/query param 'hotkey' as SS58; raise 400 if invalid."""
    try:
        return validate_ss58_hotkey(hotkey)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid SS58 address format")


def validate_miner_hotkey(miner_hotkey: str) -> str:
    """Validate path/query param 'miner_hotkey' as SS58; raise 400 if invalid."""
    try:
        return validate_ss58_hotkey(miner_hotkey)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid SS58 address format")


def validate_validator_hotkey(validator_hotkey: str) -> str:
    """Validate path/query param 'validator_hotkey' as SS58; raise 400 if invalid."""
    try:
        return validate_ss58_hotkey(validator_hotkey)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid SS58 address format")
