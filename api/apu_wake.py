from helpers.api import ApiHandler, Request


class ApuWake(ApiHandler):
    # Clear APU Governor cooldown for all agents immediately.

    @classmethod
    def requires_auth(cls):
        return True

    async def process(self, input: dict, request: Request) -> dict:
        try:
            import usr.plugins.apu_governor.lib.state as _state
            cooldown_store = _state.cooldown_store
            count = len([v for v in cooldown_store.values() if v > 0])
            for key in list(cooldown_store.keys()):
                cooldown_store[key] = 0
            # Set global wake flag so anonymous agents are also woken
            _state.wake_requested = True
            _state.save()
            return {"ok": True, "cleared": count}
        except Exception as e:
            return {"ok": False, "error": str(e)}
