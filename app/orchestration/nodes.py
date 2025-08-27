from __future__ import annotations

import json
import os
from statistics import median
from typing import Any, Dict, List

from app.orchestration.types import (
    Action,
    Claim,
    GraphState,
    ToolResult,
    WebSearchSummary,
    VerifiedState,
)
from app.tools.client import ToolsClient

from langchain.prompts import PromptTemplate
from langchain.chat_models import init_chat_model


# def planner(state: GraphState):
#     """
#     Plan the next action based on the current state.

#     For the MVP, prioritize comps so we can produce a valuation without
#     waiting for parcel/zoning tools. Once comps are verified, finalize.
#     """
#     verified_state: VerifiedState = state.get("verified_state") or VerifiedState()
#     state["verified_state"] = verified_state

#     if not verified_state.comps:
#         req = state.get("real_estate_request")
#         params: Dict[str, Any] = {}
#         if req is not None:
#             params = {"address": req.address, "mlsId": req.mlsId, "asset_class": req.asset_class}
#         state["action"] = Action(kind="GET_COMPS", params=params)
#         return state

#     # If we have comps, we can move to valuation
#     state["action"] = Action(kind="FINALIZE")
#     return state

# def run_tool(state: GraphState):
#     """
#     Run a tool to gather data about the property based on the current state. 
#     This tool calling should be hooked up to the LLM graph using the @tool decorator from langchain.
    
#     Only need to run a tool if the action is not FINALIZE.
#     In general, only need to run the tool once per action.

#     Each tool output is stored in the Claims list.

#     Current tools:
#     - get_parcel
#     - get_zoning
#     - get_comps
#     """
#     action: Action | None = state.get("action")
#     if action is None or action.kind == "FINALIZE":
#         return state

#     # Use tools client for GET_COMPS
#     if action.kind == "GET_COMPS":
#         if _tools_client is None:
#             state["raw"] = ToolResult(provider="get_comps", data={"comps": []})
#             return state
#         result = _tools_client.call("get_comps", action.params or {})
#         if not isinstance(result, dict):
#             result = {"comps": []}
#         state["raw"] = ToolResult(provider="get_comps", data=result)
#         return state

#     # Stubs for unimplemented tools
#     state["raw"] = ToolResult(provider="stub", data={})
#     return state
    
# def verify(state: GraphState):
#     """
#     Verify the data gathered from the tool call.

#     Current verifiers:
#     - parcel_verifier
#     - zoning_verifier
#     - comps_verifier
#     """
#     action: Action | None = state.get("action")
#     raw: ToolResult | None = state.get("raw")
#     verified_claims: List[Claim] = []

#     if action is None or raw is None:
#         state["verified"] = verified_claims
#         return state

#     if action.kind == "GET_COMPS":
#         comps: List[Dict[str, Any]] = (raw.data or {}).get("comps", []) or []

#         # Normalize and filter to ensure deterministic valuation fields
#         normalized: List[Dict[str, Any]] = []
#         for comp in comps:
#             price = comp.get("price")
#             living_area = comp.get("livingArea") or comp.get("livingAreaValue")
#             if not price or not living_area:
#                 continue

#             addr_obj = comp.get("address") or {}
#             formatted = comp.get("formattedChip", {}).get("location", [])
#             pretty_address = None
#             if formatted and isinstance(formatted, list):
#                 try:
#                     line1 = formatted[0].get("fullValue")
#                     line2 = formatted[1].get("fullValue") if len(formatted) > 1 else ""
#                     pretty_address = ", ".join([v for v in [line1, line2] if v])
#                 except Exception:
#                     pretty_address = None
#             if not pretty_address:
#                 pretty_address = ", ".join(
#                     [v for v in [addr_obj.get("streetAddress"), addr_obj.get("city"), addr_obj.get("state"), addr_obj.get("zipcode")] if v]
#                 )

#             try:
#                 living_area_num = float(living_area)
#                 price_num = float(price)
#             except Exception:
#                 continue

#             if living_area_num <= 0 or price_num <= 0:
#                 continue

#             price_per_sqft = price_num / living_area_num
#             normalized.append(
#                 {
#                     "address": pretty_address,
#                     "price": price_num,
#                     "livingArea": living_area_num,
#                     "bedrooms": comp.get("bedrooms"),
#                     "bathrooms": comp.get("bathrooms"),
#                     "zpid": comp.get("zpid"),
#                     "url": comp.get("hdpUrl"),
#                     "pricePerSqft": price_per_sqft,
#                     "source": raw.provider,
#                 }
#             )

#         confidence = 0.9 if len(normalized) >= 3 else 0.4 if len(normalized) == 2 else 0.2 if len(normalized) == 1 else 0.0
#         verified_claims.append(
#             Claim(field="comps", value=normalized, confidence=confidence, source=raw.provider)
#         )

#     # Parcel/zoning verifiers can be added later

#     state["verified"] = verified_claims
#     return state

# def update_state(state: GraphState):
#     """
#     Merge verified claims into a single state. Claims should be merged into the verified_state.
#     """
#     verified_state: VerifiedState = state.get("verified_state") or VerifiedState()
#     state["verified_state"] = verified_state

#     claims: List[Claim] = state.get("verified") or []
#     for claim in claims:
#         if claim.field == "comps" and isinstance(claim.value, list) and claim.confidence >= 0.2:
#             verified_state.comps = claim.value
#         elif claim.field == "parcel" and isinstance(claim.value, dict) and claim.confidence >= 0.5:
#             verified_state.parcel = claim.value
#         elif claim.field == "zoning" and isinstance(claim.value, dict) and claim.confidence >= 0.5:
#             verified_state.zoning = claim.value

#     # Clear transient per-action fields
#     state.pop("raw", None)
#     state.pop("verified", None)
#     return state

# def valuate(state: GraphState):
#     """
#     Valuate the property based on the verified state object. This should be a deterministic function using a weighted comps model.
#     Output should also include a binary confidence score for the valuation. 
#     """
#     verified_state: VerifiedState = state.get("verified_state") or VerifiedState()
#     comps: List[Dict[str, Any]] = verified_state.comps or []

#     estimate: float | None = None
#     is_confident: bool = False
#     drivers: List[Dict[str, Any]] = []

#     valid_prices = [c["price"] for c in comps if isinstance(c.get("price"), (int, float))]
#     if valid_prices:
#         estimate = float(median(valid_prices))
#         is_confident = len(valid_prices) >= 3

#     # Top drivers: choose up to 5 comps closest to median living area
#     living_areas = [c["livingArea"] for c in comps if isinstance(c.get("livingArea"), (int, float))]
#     if living_areas:
#         target_la = float(median(living_areas))
#         drivers = sorted(
#             comps,
#             key=lambda c: abs((c.get("livingArea") or target_la) - target_la),
#         )[:5]
#     else:
#         drivers = comps[:5]

#     state["valuation"] = {
#         "estimate": estimate,
#         "numComps": len(comps),
#         "method": "median_price",
#     }
#     state["valuation_confident"] = bool(is_confident)
#     state["valuation_drivers"] = drivers
#     return state

# def report(state: GraphState):
#     """
#     Create a report of the property valuation and the top 5 drivers for the valuation. If needed, some of this data should be gathered from the valuate node.

#     Be sure to include any data sources used in the report and the confidence of the valuation.
#     """
#     req = state.get("real_estate_request")
#     valuation = state.get("valuation") or {}
#     drivers: List[Dict[str, Any]] = state.get("valuation_drivers") or []
#     confident: bool = bool(state.get("valuation_confident"))

#     sources = []
#     for d in drivers:
#         src = d.get("source")
#         if src and src not in sources:
#             sources.append(src)

#     state["report"] = {
#         "subject": {
#             "address": getattr(req, "address", None) if req else None,
#             "mlsId": getattr(req, "mlsId", None) if req else None,
#             "assetClass": getattr(req, "asset_class", None) if req else None,
#         },
#         "valuation": valuation,
#         "confidence": confident,
#         "topDrivers": drivers,
#         "sources": sources,
#     }
#     state["done"] = True
#     return state


class Nodes:
    def __init__(self) -> None:
        self.tools = ToolsClient()
        self.llm = init_chat_model(model="gpt-4o")

        self.web_search_summarizer = self._create_web_search_summarizer()

    def _create_web_search_summarizer(self):
        """
        Create a summary of the web search results.
        """
        web_search_summary_prompt = PromptTemplate.from_template(
            """
            Role and Objective: Provide a summary of web search results based on a property and it's local area to be used in evaluating a real estate investment.

            Instructions:
            - Summarize the web search results and include any key drivers that are critical to the valuation, like school ratings, neighborhood area, etc.
            - Key property details, like square footage, number of bedrooms, number of bathrooms don't need to be included as these are already known.
            
            Context:
            Web search results: {web_search_results}
            """
        )
        web_search_summarizer = web_search_summary_prompt | self.llm.with_structured_output(WebSearchSummary)
        return web_search_summarizer
        

    def planner(self, state: GraphState):
        """
        Plan the next action based on the current state.

        For the MVP, prioritize comps so we can produce a valuation without
        waiting for parcel/zoning tools. Once comps are verified, finalize.
        """
        verified_state: VerifiedState = state.get("verified_state") or VerifiedState()
        state["verified_state"] = verified_state

        # If we already have web search results but no summary, summarize now so it's ready before valuation
        if state.get("web_search_results") and not state.get("web_search_summary"):
            try:
                summary: WebSearchSummary = self._summarize_web_search_results(state)
                state["web_search_summary"] = {"summary": summary.summary, "drivers": summary.drivers}
            except Exception:
                # Non-fatal; continue planning without a summary
                pass

        if not verified_state.comps and not verified_state.web_search:
            req = state.get("real_estate_request")
            params: Dict[str, Any] = {}
            if req is not None:
                params = {"address": req.address, "mlsId": req.mlsId, "asset_class": req.asset_class}
            state["action"] = Action(kind="GET_COMPS", params=params)
            return state

        state["action"] = Action(kind="FINALIZE")
        return state

    def run_tool(self, state: GraphState):
        """
        Run a tool to gather data about the property based on the current state. 
        This tool calling should be hooked up to the LLM graph using the @tool decorator from langchain.
        
        Only need to run a tool if the action is not FINALIZE.
        In general, only need to run the tool once per action.

        Each tool output is stored in the Claims list.

        Current tools:
        - get_parcel
        - get_zoning
        - get_comps
        """
        action: Action | None = state.get("action")
        if action is None or action.kind == "FINALIZE":
            return state

        if action.kind == "GET_COMPS":
            result = None
            if self.tools is not None:
                result = self.tools.call("get_comps", action.params or {})
            if not isinstance(result, dict):
                result = {"comps": []}
            state["raw"] = ToolResult(provider="get_comps", data=result)
            return state

        if action.kind == "GET_WEB_SEARCH":
            result = None
            if self.tools is not None:
                result = self.tools.call("web_search", action.params or {})
            if not isinstance(result, dict):
                result = {"web_search_results": []}
            state["raw"] = ToolResult(provider="web_search", data=result)
            return state

        state["raw"] = ToolResult(provider="stub", data={})
        return state

    def verify(self, state: GraphState):
        """
        Verify the data gathered from the tool call.

        Current verifiers:
        - parcel_verifier
        - zoning_verifier
        - comps_verifier
        """
        action: Action | None = state.get("action")
        raw: ToolResult | None = state.get("raw")
        verified_claims: List[Claim] = []

        if action is None or raw is None:
            state["verified_claims"] = verified_claims
            return state

        if action.kind == "GET_COMPS":
            comps: List[Dict[str, Any]] = (raw.data or {}).get("comps", []) or []

            normalized: List[Dict[str, Any]] = []
            for comp in comps:
                price = comp.get("price")
                living_area = comp.get("livingArea") or comp.get("livingAreaValue")
                if not price or not living_area:
                    continue

                addr_obj = comp.get("address") or {}
                formatted = comp.get("formattedChip", {}).get("location", [])
                pretty_address = None
                if formatted and isinstance(formatted, list):
                    try:
                        line1 = formatted[0].get("fullValue")
                        line2 = formatted[1].get("fullValue") if len(formatted) > 1 else ""
                        pretty_address = ", ".join([v for v in [line1, line2] if v])
                    except Exception:
                        pretty_address = None
                if not pretty_address:
                    pretty_address = ", ".join(
                        [v for v in [addr_obj.get("streetAddress"), addr_obj.get("city"), addr_obj.get("state"), addr_obj.get("zipcode")] if v]
                    )

                try:
                    living_area_num = float(living_area)
                    price_num = float(price)
                except Exception:
                    continue

                if living_area_num <= 0 or price_num <= 0:
                    continue

                price_per_sqft = price_num / living_area_num
                normalized.append(
                    {
                        "address": pretty_address,
                        "price": price_num,
                        "livingArea": living_area_num,
                        "bedrooms": comp.get("bedrooms"),
                        "bathrooms": comp.get("bathrooms"),
                        "zpid": comp.get("zpid"),
                        "url": comp.get("hdpUrl"),
                        "pricePerSqft": price_per_sqft,
                        "source": raw.provider,
                    }
                )

            confidence = 0.9 if len(normalized) >= 3 else 0.4 if len(normalized) == 2 else 0.2 if len(normalized) == 1 else 0.0
            verified_claims.append(
                Claim(field="comps", value=normalized, confidence=confidence, source=raw.provider)
            )

        if action.kind == "GET_WEB_SEARCH":
            web_results: List[Dict[str, Any]] = (raw.data or {}).get("web_search_results", []) or []
            confidence = 0.7 if len(web_results) >= 2 else 0.4 if len(web_results) == 1 else 0.0
            verified_claims.append(
                Claim(field="web_search", value=web_results, confidence=confidence, source=raw.provider)
            )

        state["verified_claims"] = verified_claims
        return state

    def update_state(self, state: GraphState):  
        """
        Merge verified claims into a single state. Claims should be merged into the verified_state.
        """
        verified_state: VerifiedState = state.get("verified_state") or VerifiedState()
        state["verified_state"] = verified_state

        claims: List[Claim] = state.get("verified_claims") or []
        for claim in claims:
            if claim.field == "comps" and isinstance(claim.value, list) and claim.confidence >= 0.2:
                verified_state.comps = claim.value
            elif claim.field == "parcel" and isinstance(claim.value, dict) and claim.confidence >= 0.5:
                verified_state.parcel = claim.value
            elif claim.field == "zoning" and isinstance(claim.value, dict) and claim.confidence >= 0.5:
                verified_state.zoning = claim.value
            elif claim.field == "web_search" and isinstance(claim.value, list) and claim.confidence >= 0.2:
                verified_state.web_search = claim.value
                state["web_search_results"] = claim.value

        state.pop("raw", None)
        state.pop("verified_claims", None)
        return state

    def _summarize_web_search_results(self, state: GraphState) -> WebSearchSummary:
        """
        Summarize the web search results based on a property and it's local area to be used in evaluating a real estate investment.
        """
        web_search_results = state.get("web_search_results") or []
        web_search_summary = self.web_search_summarizer.invoke({"web_search_results": web_search_results})
        return web_search_summary

    def valuate(self, state: GraphState):
        """
        Valuate the property based on the verified state object. This should be a deterministic function using a weighted comps model.
        Output should also include a binary confidence score for the valuation. 
        """
        verified_state: VerifiedState = state.get("verified_state") or VerifiedState()
        comps: List[Dict[str, Any]] = verified_state.comps or []

        estimate: float | None = None
        is_confident: bool = False
        drivers: List[Dict[str, Any]] = []

        valid_prices = [c["price"] for c in comps if isinstance(c.get("price"), (int, float))]
        if valid_prices:
            estimate = float(median(valid_prices))
            is_confident = len(valid_prices) >= 3

        living_areas = [c["livingArea"] for c in comps if isinstance(c.get("livingArea"), (int, float))]
        if living_areas:
            target_la = float(median(living_areas))
            drivers = sorted(
                comps,
                key=lambda c: abs((c.get("livingArea") or target_la) - target_la),
            )[:5]
        else:
            drivers = comps[:5]

        # Use precomputed web search summary from planner (if available)
        web_summary = state.get("web_search_summary")
        if web_summary:
            drivers.append({
                "type": "web_search_summary",
                "summary": web_summary.get("summary"),
                "drivers": web_summary.get("drivers", []),
                "source": "web_search",
            })

        state["valuation"] = {
            "estimate": estimate,
            "numComps": len(comps),
            "method": "median_price",
        }
        state["valuation_confident"] = bool(is_confident)
        state["valuation_drivers"] = drivers
        return state

    def report(self, state: GraphState):
        """
        Create a report of the property valuation and the top 3-5 drivers for the valuation. If needed, some of this data should be gathered from the valuate node.

        Be sure to include any data sources used in the report and the confidence of the valuation.
        """
        req = state.get("real_estate_request")
        valuation = state.get("valuation") or {}
        drivers: List[Dict[str, Any]] = state.get("valuation_drivers") or []
        confident: bool = bool(state.get("valuation_confident"))

        sources = []
        for d in drivers:
            src = d.get("source")
            if src and src not in sources:
                sources.append(src)

        state["report"] = {
            "subject": {
                "address": getattr(req, "address", None) if req else None,
                "mlsId": getattr(req, "mlsId", None) if req else None,
                "assetClass": getattr(req, "asset_class", None) if req else None,
            },
            "valuation": valuation,
            "confidence": confident,
            "topDrivers": drivers,
            "sources": sources,
        }
        state["done"] = True
        return state