"""Import every model so Base.metadata is complete for Alembic autogenerate
and for test-suite `create_all()`."""

from app.db.models.approval import Approval
from app.db.models.artwork import Artwork, EtsyListingPackage, Mockup, PrintExport
from app.db.models.base import Base
from app.db.models.collection import Collection
from app.db.models.commercial import CommercialObservation, CreativeFamily
from app.db.models.concept import Concept
from app.db.models.cost import CostEvent, ProviderHealthLog
from app.db.models.evaluation import Evaluation
from app.db.models.experiment import Experiment
from app.db.models.failure import FailureRecord, RepairAttempt
from app.db.models.generation import GenerationCandidate, GenerationJob
from app.db.models.genome import DesignGenome
from app.db.models.market_signal import MarketSignal
from app.db.models.production import DailyProductionPlan

__all__ = [
    "Base",
    "Collection",
    "DesignGenome",
    "Concept",
    "GenerationJob",
    "GenerationCandidate",
    "Evaluation",
    "FailureRecord",
    "RepairAttempt",
    "Experiment",
    "Artwork",
    "PrintExport",
    "Mockup",
    "EtsyListingPackage",
    "CommercialObservation",
    "CreativeFamily",
    "DailyProductionPlan",
    "CostEvent",
    "ProviderHealthLog",
    "Approval",
    "MarketSignal",
]
