"""Pydantic models for Evon JSON and the API."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Category = Literal["returns", "guarantee", "lock_in", "premium_term", "policy_term", "charges",
                   "liquidity", "tax", "cover", "other"]
Verdict = Literal["WRITTEN", "CONTRADICTED", "NOT_IN_WRITING"]
MAX_CLAIMS = 12


class ExtractedClaim(BaseModel):
    quote: str = Field(min_length=1)
    claim_en: str = Field(min_length=1)
    category: Category = "other"
    numbers: list[str] = Field(default_factory=list)

    @field_validator("category", mode="before")
    @classmethod
    def _cat(cls, v):
        v = str(v or "other").strip().lower().replace("-", "_").replace(" ", "_")
        return v if v in Category.__args__ else "other"

    @field_validator("numbers", mode="before")
    @classmethod
    def _nums(cls, v):
        if v is None:
            return []
        if isinstance(v, (str, int, float)):
            v = [v]
        return [str(x) for x in v if str(x).strip()]


class Extraction(BaseModel):
    claims: list[ExtractedClaim] = Field(default_factory=list)

    @field_validator("claims")
    @classmethod
    def _cap(cls, v):
        return v[:MAX_CLAIMS]


class Verification(BaseModel):
    verdict: Verdict
    clause_id: Optional[str] = None
    clause_quote: Optional[str] = None
    explain_en: str = ""
    explain_local: str = ""
    ask_agent: str = ""

    @field_validator("verdict", mode="before")
    @classmethod
    def _verdict(cls, v):
        return str(v).strip().upper().replace(" ", "_").replace("-", "_")


class LocalText(BaseModel):
    text: str


# ---------- API ----------

class CaseCreate(BaseModel):
    lang: Literal["hi", "en", "ta", "mr"]
    mode: Literal["listen", "recall"]
    consent: bool

    @field_validator("consent")
    @classmethod
    def _consent(cls, v):
        if v is not True:
            raise ValueError("consent must be true")
        return v


class DemoDoc(BaseModel):
    demo_doc: Literal["suraksha_plus"]


class SpeakRequest(BaseModel):
    target: str = Field(min_length=1, max_length=64)  # "summary" or a claim id


class TextSegment(BaseModel):
    text: str = Field(min_length=2, max_length=4000)
