# Shared cooldown state with disk persistence.
# Survives container restarts — expired entries are discarded on load.
import json
import time
from pathlib import Path

_STATE_FILE = Path(__file__).parent.parent / "cooldown_state.json"

# In-memory store: {agent_id: cooldown_expires_timestamp}
cooldown_store: dict[str, float] = {}

# Global wake flag — set by wake API, cleared after sleep exits
wake_requested: bool = False


def _load():
    """Load state from disk on import, discard expired entries."""
    try:
        if _STATE_FILE.exists():
            data = json.loads(_STATE_FILE.read_text())
            now = time.time()
            for k, v in data.items():
                if isinstance(v, (int, float)) and v > now:
                    cooldown_store[k] = v
    except Exception:
        pass


def save():
    """Write active cooldowns to disk. Call after every update."""
    try:
        now = time.time()
        active = {k: v for k, v in cooldown_store.items() if v > now}
        _STATE_FILE.write_text(json.dumps(active))
    except Exception:
        pass


# Load persisted state at import time
_load()
