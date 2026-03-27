import time
from helpers.tool import Tool, Response


def _get_cooldown_store():
    """Lazy import to avoid circular import issues at load time."""
    from usr.plugins.apu_governor.lib.state import cooldown_store
    return cooldown_store


class ApuSleep(Tool):
    async def execute(self, seconds: int = 60, **kwargs) -> Response:
        """
        Request a cooldown period. Returns immediately — APU Governor
        enforces the delay on the NEXT tool execution.

        Args:
            seconds: Cooldown duration in seconds (1-3600)
        """
        seconds = max(1, min(int(seconds), 3600))
        cooldown_until = time.time() + seconds

        try:
            self.agent.apu_cooldown_until = cooldown_until
        except Exception:
            pass

        agent_id = getattr(self.agent, "id", "") or ""
        if agent_id:
            cooldown_store = _get_cooldown_store()
            cooldown_store[agent_id] = cooldown_until

        return Response(
            message=f"APU cooldown set: {seconds}s. Next tool execution will be delayed.",
            break_loop=False,
        )
