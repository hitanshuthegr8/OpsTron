"""
Shared runtime singletons for route modules.
"""

from app.core.dedup import AlertCooldown, EventDeduplicator
from app.core.event_engine import EventEngine
from app.core.orchestrator import RCAOrchestrator
from app.core.watch_manager import WatchModeManager
from app.db.supabase_client import db
from app.services.twilio_service import TwilioService

class LazyOrchestrator:
    def __init__(self):
        self._instance = None

    def _get(self) -> RCAOrchestrator:
        if self._instance is None:
            self._instance = RCAOrchestrator()
        return self._instance

    async def analyze(self, *args, **kwargs):
        return await self._get().analyze(*args, **kwargs)


event_deduplicator = EventDeduplicator()
alert_cooldown = AlertCooldown()
watch_manager = WatchModeManager(db=db)
orchestrator = LazyOrchestrator()
twilio_service = TwilioService()

event_engine = EventEngine(
    watch_manager=watch_manager,
    dedup=event_deduplicator,
    cooldown=alert_cooldown,
    orchestrator=orchestrator,
    alert_service=twilio_service,
    db=db,
)
