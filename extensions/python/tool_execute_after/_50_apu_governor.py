import asyncio
import time

from helpers.extension import Extension
from helpers import plugins

HIGH_RESOURCE_PATTERNS = ["download", "scrape", "crawl", "api", "fetch", "stream"]
LONG_TASK_THRESHOLD_SECONDS = 5
MAX_DELAY_SECONDS = 3600


def _get_state():
    """Lazy import to avoid circular import issues at load time."""
    import usr.plugins.apu_governor.lib.state as _state
    return _state


async def _interruptible_sleep(seconds, agent_id, state):
    """Sleep for `seconds`, but exit early if wake button is pressed.

    Uses time.perf_counter() (monotonic) so NTP clock adjustments cannot
    cause the sleep to run too long or exit too early.
    """
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        await asyncio.sleep(1)
        # Check global wake flag (set by apu_wake API)
        if state.wake_requested:
            state.wake_requested = False
            break
        # Check per-agent store (wake API also zeroes these)
        if agent_id and state.cooldown_store.get(agent_id, -1) == 0:
            break


class APUGovernor(Extension):
    async def execute(self, tool_name="", response=None, **kwargs):
        config = plugins.get_plugin_config("apu_governor", self.agent)
        if not config.get("apu_enabled", True):
            return

        now = time.time()
        agent_id = getattr(self.agent, "id", "") or ""
        state = _get_state()
        cooldown_store = state.cooldown_store

        # --- AGENT-TRIGGERED COOLDOWN CHECK (one-shot, runs first) ---
        cooldown_until = max(
            getattr(self.agent, "apu_cooldown_until", 0) or 0,
            cooldown_store.get(agent_id, 0),
        )
        if cooldown_until > now:
            remaining = cooldown_until - now
            await _interruptible_sleep(remaining, agent_id, state)
            try:
                self.agent.apu_cooldown_until = 0
            except Exception:
                pass
            if agent_id:
                cooldown_store[agent_id] = 0
                state.save()
            return

        # --- SKIP IF NO RESPONSE ---
        if response is None:
            return

        # --- HIGH-COMPUTE DETECTION ---
        is_high_compute = any(p in tool_name.lower() for p in HIGH_RESOURCE_PATTERNS)
        execution_time = getattr(self.agent, "last_tool_runtime", 0) or 0
        if execution_time > LONG_TASK_THRESHOLD_SECONDS:
            is_high_compute = True

        # --- CALCULATE DELAY ---
        base_delay = config.get("base_wait_seconds", 300)
        multiplier = config.get("high_compute_multiplier", 1.75) if is_high_compute else 1.0
        final_delay = int(base_delay * multiplier)

        # Enforce bounds
        min_cooldown = config.get("min_api_cooldown", 60)
        final_delay = max(final_delay, min_cooldown)
        final_delay = min(final_delay, MAX_DELAY_SECONDS)

        # --- UPDATE COOLDOWN TIMESTAMP ---
        cooldown_expires = now + final_delay
        try:
            self.agent.apu_cooldown_until = cooldown_expires
        except Exception:
            pass
        if agent_id:
            cooldown_store[agent_id] = cooldown_expires
            state.save()

        # --- MEMORY COMPACTION (graceful no-op if unavailable) ---
        try:
            from helpers import memory_manager
            memory_manager.compact_context(self.agent)
        except Exception:
            pass

        # --- INTERRUPTIBLE DELAY ---
        await _interruptible_sleep(final_delay, agent_id, state)
