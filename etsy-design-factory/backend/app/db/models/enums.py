"""Enums shared between DB models, genome schema and pipeline stages.

Kept as plain Python str-enums (stored as VARCHAR) rather than native
Postgres ENUM types so SQLite (used in the test suite) and Postgres share
one code path, and so new values don't require a migration.
"""

from __future__ import annotations

from enum import StrEnum


class CollectionStatus(StrEnum):
    DISCOVERY = "DISCOVERY"
    PRODUCTION = "PRODUCTION"
    SATURATED = "SATURATED"
    RETIRED = "RETIRED"


class ProductionMode(StrEnum):
    DISCOVERY = "DISCOVERY"
    PRODUCTION = "PRODUCTION"


class GenomeCreatedBy(StrEnum):
    SYSTEM_DISCOVERY = "SYSTEM_DISCOVERY"
    SYSTEM_MUTATION = "SYSTEM_MUTATION"
    HUMAN_EDIT = "HUMAN_EDIT"


class GateStatus(StrEnum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    REJECTED = "REJECTED"


class CandidateStatus(StrEnum):
    QUEUED = "QUEUED"
    GENERATING = "GENERATING"
    GENERATED = "GENERATED"
    QC_IN_PROGRESS = "QC_IN_PROGRESS"
    QC_PASSED = "QC_PASSED"
    QC_FAILED = "QC_FAILED"
    DIAGNOSED = "DIAGNOSED"
    REPAIR_QUEUED = "REPAIR_QUEUED"
    REPAIRING = "REPAIRING"
    REPAIRED = "REPAIRED"
    TERMINAL = "TERMINAL"
    SELECTION_PENDING = "SELECTION_PENDING"
    SELECTED = "SELECTED"
    ELIMINATED = "ELIMINATED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PRINT_PROCESSING = "PRINT_PROCESSING"
    PRINT_READY = "PRINT_READY"
    PACKAGED = "PACKAGED"


class FailureClass(StrEnum):
    TERMINAL_FAILURE = "TERMINAL_FAILURE"
    REPAIRABLE_FAILURE = "REPAIRABLE_FAILURE"
    PROMISING = "PROMISING"
    ACCEPTED = "ACCEPTED"


class RepairOutcome(StrEnum):
    PENDING = "PENDING"
    IMPROVED = "IMPROVED"
    NO_IMPROVEMENT = "NO_IMPROVEMENT"
    FAILED = "FAILED"


class PrintRatio(StrEnum):
    R_2_3 = "2:3"
    R_3_4 = "3:4"
    R_4_5 = "4:5"
    R_5_7 = "5:7"
    R_11_14 = "11:14"
    A_SERIES = "A"


class PortfolioBucket(StrEnum):
    PROVEN = "PROVEN"
    GROWING = "GROWING"
    EXPERIMENTAL = "EXPERIMENTAL"
    WINNER_MUTATION = "WINNER_MUTATION"
    WILDCARD = "WILDCARD"


class ApprovalAction(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    MORE_ORIGINAL = "MORE_ORIGINAL"
    CLOSER_TO_COLLECTION = "CLOSER_TO_COLLECTION"
    CHANGE_COMPOSITION = "CHANGE_COMPOSITION"
    CHANGE_PALETTE = "CHANGE_PALETTE"
    MORE_TEXTURE = "MORE_TEXTURE"
    LESS_TEXTURE = "LESS_TEXTURE"
    MORE_MINIMAL = "MORE_MINIMAL"
    MORE_DETAILED = "MORE_DETAILED"
    CREATE_VARIATIONS = "CREATE_VARIATIONS"


class CreativeFamilyStatus(StrEnum):
    CHALLENGER = "CHALLENGER"
    CHAMPION = "CHAMPION"
    RETIRED = "RETIRED"


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"
