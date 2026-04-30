from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PaperBase(BaseModel):
    title: str = Field(..., max_length=500)
    abstract: str | None = Field(None, max_length=50000)
    source: str = Field("ape", max_length=100)
    category: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    method: str | None = Field(None, max_length=200)
    version: int = 1
    domain_config_id: str | None = None


class PaperCreate(PaperBase):
    id: str | None = Field(None, max_length=64)  # Auto-generated if not provided


class PaperImport(BaseModel):
    papers: list[PaperCreate] = Field(..., max_length=500)


class PaperResponse(PaperBase):
    id: str
    status: str
    review_status: str
    paper_pdf_path: str | None = None
    created_at: datetime
    updated_at: datetime

    # Funnel stage tracks the orchestrator's pipeline progress
    # (idea / designed / locked / ingesting / analyzing / drafting /
    # reviewing / candidate / killed). Surfaced for fire-and-poll
    # clients that want to know how far the pipeline has progressed.
    funnel_stage: str | None = None

    # Parsed error string when status='error' (the orchestrator's
    # ``_set_error`` writes ``{"error": "..."}`` to metadata_json).
    # Surfaced so failed papers tell the operator what went wrong
    # without needing backend log access.
    error_message: str | None = None

    # Heartbeat fields populated by the orchestrator at each stage.
    # Polling clients use these to detect stalled tasks
    # (heartbeat >5 min stale = likely-dead background task).
    last_heartbeat_at: datetime | None = None
    last_heartbeat_stage: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PaperWithRating(PaperResponse):
    mu: float | None = None
    sigma: float | None = None
    conservative_rating: float | None = None
    elo: float | None = None
    matches_played: int | None = None
    rank: int | None = None
    rank_change_48h: int | None = None
