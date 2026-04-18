from pydantic import BaseModel, Field
from typing import Literal


class Query(BaseModel):
    query: str
    mode: Literal["rag", "groq"] = Field(default="rag")
