from typing import List, Dict, Any, Optional, Literal, TypedDict
from pydantic import BaseModel


class RealEstateRequest(BaseModel):
    address: str
    asset_class: Literal["residential", "commercial", "industrial"]
    mlsId: str


class Claim(BaseModel):
    """An claim about a property, gathered from a tool call"""
    field: str
    value: Any
    confidence: float
    source: str
    

class VerifiedState(BaseModel):
    """Verified state of facts/claims about a property"""
    # parcel: Dict[str, Any] = {}
    # zoning: Dict[str, Any] = {}
    comps: List[Dict[str, Any]] = []
    web_search: List[Dict[str, Any]] = []


class Action(BaseModel):
    kind: Literal["GET_PARCEL","GET_ZONING","GET_COMPS","GET_WEB_SEARCH","FINALIZE"]
    params: Dict[str, Any] = {}
    alternates: List[Dict[str, Any]] = []


class ToolResult(BaseModel):
    provider: str
    data: Dict[str, Any]        # raw JSON from provider


class WebSearchSummary(BaseModel):
    summary: str
    drivers: List[str]


class ReportSections(BaseModel):
    executive_summary: str
    market_overview: str
    comparable_analysis: str
    risks: str
    recommendations: str


class GraphState(TypedDict, total=False):
    real_estate_request: RealEstateRequest
    web_search_results: List[Dict[str, Any]]
    web_search_summary: WebSearchSummary
    action: Optional[Action]
    raw: Optional[ToolResult]
    verified_claims: List[Claim]
    verified_state: VerifiedState
    valuation: Dict[str, Any]
    valuation_confident: bool
    valuation_drivers: List[Dict[str, Any]]
    required_failed: bool
    human_gate: Optional[Dict[str, Any]]  # bundle for escalation
    done: bool
    report: Dict[str, Any]