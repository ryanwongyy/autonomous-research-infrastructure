from pydantic import BaseModel, ConfigDict, Field


class CategoryInfo(BaseModel):
    slug: str
    name: str


class DataSourceInfo(BaseModel):
    name: str
    type: str = "api"
    base_url: str
    requires_key: bool = False


class EvaluationCriteria(BaseModel):
    rewards: list[str] = []
    penalties: list[str] = []


class DomainConfigResponse(BaseModel):
    id: str
    name: str
    description: str | None
    analysis_tool: str
    judge_model: str
    generation_model: str
    categories: list[CategoryInfo] = []
    methods: list[str] = []
    active: bool

    model_config = ConfigDict(from_attributes=True)


class DomainConfigUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=5000)
    judge_model: str | None = Field(None, max_length=200)
    generation_model: str | None = Field(None, max_length=200)
    active: bool | None = None
