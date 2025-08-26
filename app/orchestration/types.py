from typing import List, Dict, Any, Optional, Literal, TypedDict
from pydantic import BaseModel


class RealEstateRequest(BaseModel):
    address: str
    asset_class: Literal["residential", "commercial", "industrial"]
    apn: str


class Claim(BaseModel):
    """An claim about a property, gathered from a tool call"""
    field: str
    value: Any
    confidence: float
    source: str
    

class VerifiedState(BaseModel):
    """Verified state of facts/claims about a property"""
    parcel: Dict[str, Any] = {}
    zoning: Dict[str, Any] = {}
    comps: List[Dict[str, Any]] = []


class Action(BaseModel):
    kind: Literal["GET_PARCEL","GET_ZONING","GET_COMPS","FINALIZE"]
    params: Dict[str, Any] = {}
    alternates: List[Dict[str, Any]] = []


class ToolResult(BaseModel):
    provider: str
    data: Dict[str, Any]        # raw JSON from provider


class GraphState(TypedDict, total=False):
    real_estate_request: RealEstateRequest
    verified_state: VerifiedState
    action: Optional[Action]
    raw: Optional[ToolResult]
    verified: List[Claim]
    required_failed: bool
    human_gate: Optional[Dict[str, Any]]  # bundle for escalation
    done: bool