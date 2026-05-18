from typing import Literal
from pydantic import BaseModel


class GenerateRequest(BaseModel):
    cities: list[str]
    start_address: str
    end_address: str
    route_mode: Literal["per_city", "all_cities"] = "per_city"


class JobStatusResponse(BaseModel):
    id: str
    status: str
    progress: str | None = None
    result: dict | None = None
    error: str | None = None
