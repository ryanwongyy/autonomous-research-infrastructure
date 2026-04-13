from pydantic import BaseModel, Field


class StatsResponse(BaseModel):
    total_papers: int = Field(ge=0)
    total_ai_papers: int = Field(ge=0)
    total_benchmark_papers: int = Field(ge=0)
    total_matches: int = Field(ge=0)
    total_tournament_runs: int = Field(ge=0)
    ai_win_rate: float = Field(ge=0.0, le=1.0)
    avg_elo_ai: float | None
    avg_elo_benchmark: float | None


class RatingDistributionBucket(BaseModel):
    bucket_start: float
    bucket_end: float
    count_ai: int = Field(ge=0)
    count_benchmark: int = Field(ge=0)


class RatingDistributionResponse(BaseModel):
    elo_distribution: list[RatingDistributionBucket]
    conservative_distribution: list[RatingDistributionBucket]


class TrueSkillProgressionPoint(BaseModel):
    date: str
    paper_id: str
    title: str
    source: str
    conservative_rating: float


class TrueSkillProgressionResponse(BaseModel):
    data: list[TrueSkillProgressionPoint]
