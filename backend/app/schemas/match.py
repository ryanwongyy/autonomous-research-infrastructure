from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MatchResponse(BaseModel):
    id: int
    tournament_run_id: int
    paper_a_id: str
    paper_b_id: str
    winner_id: str | None
    judge_model: str
    result_a_first: str | None
    result_b_first: str | None
    final_result: str
    batch_number: int = Field(ge=1)
    mu_change_a: float | None = None
    mu_change_b: float | None = None
    elo_change_a: float | None = None
    elo_change_b: float | None = None
    family_id: str | None = None
    integrity_penalty_a: bool = False
    integrity_penalty_b: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MatchDetail(MatchResponse):
    judge_prompt: str | None
    judgment_a_first: str | None
    judgment_b_first: str | None
    paper_a_title: str | None = None
    paper_b_title: str | None = None
