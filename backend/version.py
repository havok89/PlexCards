import os
from pathlib import Path

def get_version() -> str:
    """Return the normalized application version from environment or root VERSION file."""
    env_ver = os.environ.get("APP_VERSION")
    if env_ver:
        return env_ver.strip()

    candidates = [
        Path(__file__).resolve().parent.parent / "VERSION",
        Path("/app/VERSION"),
        Path(__file__).resolve().parent / "VERSION",
    ]
    for candidate in candidates:
        try:
            if candidate.is_file():
                v = candidate.read_text(encoding="utf-8").strip()
                if v:
                    return v
        except Exception:
            pass

    return "0.9.0-pre"

__version__ = get_version()
