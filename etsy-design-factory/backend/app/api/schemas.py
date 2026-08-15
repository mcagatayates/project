"""API request/response schemas. Kept separate from the domain models
(app/db/models) and the creative schema (app/genome/schema) so the wire
format can evolve independently of either."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.enums import ApprovalAction


class DashboardSummary(BaseModel):
    plan_date: str
    target_final_designs: int | None = None
    generated: int = 0
    qc_passed: int = 0
    repairing: int = 0
    awaiting_approval: int = 0
    approved: int = 0
    rejected: int = 0
    today_cost_usd: float = 0.0
    cost_per_approved_design_usd: float | None = None


class ScoreSummary(BaseModel):
    value: float
    confidence: float
    reasoning: str
    problems: list[str] = Field(default_factory=list)


class CandidateSummary(BaseModel):
    id: uuid.UUID
    concept_id: uuid.UUID
    design_genome_id: uuid.UUID
    collection_id: uuid.UUID | None
    collection_name: str | None
    status: str
    image_url: str
    width_px: int
    height_px: int
    is_repair: bool
    created_at: datetime
    scores: dict[str, ScoreSummary] | None = None
    subject: str | None = None
    style: str | None = None
    palette: str | None = None


class CandidateListResponse(BaseModel):
    items: list[CandidateSummary]
    total: int


class ApprovalRequest(BaseModel):
    action: ApprovalAction
    actor: str = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class BulkApprovalRequest(BaseModel):
    candidate_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    action: ApprovalAction
    actor: str = Field(min_length=1, max_length=200)


class ApprovalResult(BaseModel):
    candidate_id: uuid.UUID
    action: str
    artwork_id: uuid.UUID | None = None
    new_concept_id: uuid.UUID | None = None


class BulkApprovalResponse(BaseModel):
    results: list[ApprovalResult]


class ProductionPlanRequest(BaseModel):
    plan_date: str = Field(description="ISO date, e.g. 2026-08-14")
    target_final_designs: int | None = Field(default=None, ge=1, le=500)


class ProductionPlanResponse(BaseModel):
    id: uuid.UUID
    plan_date: str
    target_final_designs: int
    portfolio_allocation: dict[str, int]
    production_slots: int
    experimental_slots: int
    winner_mutation_slots: int
    budget_cap_usd: float
    rationale: str


class MarketSignalIn(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = Field(
        min_length=1,
        max_length=200,
        description="Where this actually came from, e.g. 'claude_web_research:2026-08-14' or a URL",
    )


class MarketSignalIngestRequest(BaseModel):
    signals: list[MarketSignalIn] = Field(min_length=1, max_length=100)


class MarketSignalOut(BaseModel):
    id: uuid.UUID
    category: str
    description: str
    confidence: float
    source: str
    created_at: datetime


class MarketSignalListResponse(BaseModel):
    items: list[MarketSignalOut]


class ResearchQueryOut(BaseModel):
    query: str
    category: str
    reason: str


class ResearchPlanResponse(BaseModel):
    plan_date: str
    queries: list[ResearchQueryOut]


class GetvelaExportRequest(BaseModel):
    requested_by: str = Field(min_length=1, max_length=200)
    collection_id: uuid.UUID | None = None
    limit: int = Field(default=50, ge=1, le=200)


class GetvelaExportResponse(BaseModel):
    batch_id: uuid.UUID
    listing_count: int
    row_count: int
    skus: list[str]
    csv: str


class GetvelaExportBatchOut(BaseModel):
    id: uuid.UUID
    requested_by: str
    listing_count: int
    row_count: int
    created_at: datetime


class GetvelaExportHistoryResponse(BaseModel):
    items: list[GetvelaExportBatchOut]


class GetvelaPendingCountResponse(BaseModel):
    pending_count: int


class DriveArchiveSyncResponse(BaseModel):
    archived_count: int
    failed_count: int
    skus: list[str]


class DriveArchiveRecordOut(BaseModel):
    artwork_id: uuid.UUID
    sku: str
    drive_file_id: str
    drive_file_url: str
    created_at: datetime


class DriveArchiveHistoryResponse(BaseModel):
    items: list[DriveArchiveRecordOut]


class DriveArchivePendingCountResponse(BaseModel):
    pending_count: int
