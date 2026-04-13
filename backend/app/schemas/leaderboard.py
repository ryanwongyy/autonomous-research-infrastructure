from pydantic import BaseModel, ConfigDict, Field


class LeaderboardEntry(BaseModel):
    rank: int | None = None
    rank_change_48h: int = 0
    paper_id: str
    title: str
    source: str
    category: str | None = None
    mu: float
    sigma: float = Field(ge=0.0)
    conservative_rating: float
    elo: float
    matches_played: int = Field(ge=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    draws: int = Field(ge=0)
    review_status: str

    model_config = ConfigDict(from_attributes=True)


class LeaderboardResponse(BaseModel):
    entries: list[LeaderboardEntry]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    family_id: str | None = None
    family_name: str | None = None
