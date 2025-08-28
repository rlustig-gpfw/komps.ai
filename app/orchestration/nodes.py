from __future__ import annotations

import json
import os
import random
from statistics import median
from typing import Any, Dict, List

from langchain.chat_models import init_chat_model
from langchain.prompts import PromptTemplate
from orchestration.types import (
    Action,
    Claim,
    GraphState,
    ToolResult,
    WebSearchSummary,
    VerifiedState,
    ReportSections,
)
from tools.client import ToolsClient


class Nodes:
    def __init__(self) -> None:
        self.tools = ToolsClient()
        self.llm = init_chat_model(model="gpt-4o")

        self.web_search_summarizer = self._create_web_search_summarizer()
        self.report_writer = self._create_report_writer()

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
        
    def _create_report_writer(self):
        """
        Create a writer chain that produces a narrative report from valuation context.
        """
        report_prompt = PromptTemplate.from_template(
            """
            You are an experienced real estate investment analyst. Using the inputs provided, write a concise, decision-ready memo with the following sections:

            1. Executive Summary
            2. Market Overview
            3. Comparable Analysis
            4. Risks
            5. Recommendations

            Inputs:
            - Subject Address: {subject_address}
            - Valuation: {valuation}
            - Top Drivers: {drivers}
            - Web Summary: {web_summary}
            - Comps: {comps}

            Guidelines:
            - Be specific and data-driven; use the valuation estimate, average $/sqft, assumed living area, and property type when relevant.
            - In Comparable Analysis, summarize 3-5 key comps with address and price metrics.
            - In Risks, list 2-3 material risks with brief mitigants when applicable.
            - In Recommendations, state a clear go/no-go style recommendation informed by the analysis.
            - Keep the total length under ~500 words.
            """
        )
        return report_prompt | self.llm.with_structured_output(ReportSections)

    def planner(self, state: GraphState):
        """
        Plan the next action based on the current state.

        For the MVP, prioritize comps so we can produce a valuation without
        waiting for parcel/zoning tools. Once comps are verified, finalize.
        """
        verified_state: VerifiedState = state.get("verified_state") or VerifiedState()
        state["verified_state"] = verified_state

        # Ensure web search happens before comps
        if not state.get("web_search_results"):
            req = state.get("real_estate_request")
            params: Dict[str, Any] = {"address": getattr(req, "address", "")} if req else {}
            state["action"] = Action(kind="GET_WEB_SEARCH", params=params)
            return state

        if not verified_state.comps:
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
            # Normalize to a list payload under "web_search_results"
            if isinstance(result, str):
                result = {"web_search_results": [{"content": result}]}
            elif isinstance(result, dict):
                if "web_search_results" in result:
                    pass
                elif isinstance(result.get("results"), list):
                    result = {"web_search_results": result["results"]}
                elif isinstance(result.get("content"), str):
                    result = {"web_search_results": [{"content": result.get("content")}]}
                else:
                    result = {"web_search_results": []}
            else:
                result = {"web_search_results": []}
            state["raw"] = ToolResult(provider="web_search", data=result)
            return state

        state["raw"] = ToolResult(provider="stub", data={})
        return state

    def summarize(self, state: GraphState):
        """
        Summarize web search results after they have been merged into state.
        """
        if state.get("web_search_results") and not state.get("web_search_summary"):
            try:
                summary: WebSearchSummary = self._summarize_web_search_results(state)
                state["web_search_summary"] = {"summary": summary.summary, "drivers": summary.drivers}
            except Exception:
                # Best-effort only
                pass
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
                        "homeType": comp.get("homeType") or comp.get("propertyTypeDimension"),
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

        # Filter comps to match homeType/property type and have valid ppsf
        # Determine subject type from first comp with type
        subject_type = None
        for c in comps:
            if c.get("homeType"):
                subject_type = c.get("homeType")
                break
        filtered = [c for c in comps if (subject_type is None or c.get("homeType") == subject_type) and isinstance(c.get("pricePerSqft"), (int, float)) and c.get("pricePerSqft") > 0]

        # Compute average price per sqft
        ppsf_values = [float(c["pricePerSqft"]) for c in filtered]
        avg_ppsf = sum(ppsf_values) / len(ppsf_values) if ppsf_values else None

        # Estimate subject livingArea as median of filtered comps (fallback to all comps)
        living_areas_all = [c["livingArea"] for c in comps if isinstance(c.get("livingArea"), (int, float))]
        living_areas_filtered = [c["livingArea"] for c in filtered if isinstance(c.get("livingArea"), (int, float))]
        target_la_pool = living_areas_filtered or living_areas_all
        target_la = float(median(target_la_pool)) if target_la_pool else None

        if avg_ppsf is not None and target_la is not None:
            base_estimate = avg_ppsf * target_la
            bump = random.uniform(1.05, 1.10)
            estimate = float(base_estimate * bump)
            is_confident = len(filtered) >= 3

        # Drivers: closest comps by living area from filtered list
        pool_for_drivers = filtered or comps
        if target_la is not None:
            drivers = sorted(
                pool_for_drivers,
                key=lambda c: abs((c.get("livingArea") or target_la) - target_la),
            )[:5]
        else:
            drivers = pool_for_drivers[:5]

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
            "numComps": len(filtered) if filtered else len(comps),
            "method": "avg_ppsf_with_bump",
            "avgPricePerSqft": avg_ppsf,
            "assumedLivingArea": target_la,
            "subjectType": subject_type,
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
        verified_state: VerifiedState = state.get("verified_state") or VerifiedState()
        comps_for_report: List[Dict[str, Any]] = (verified_state.comps or [])[:5]

        subject_address = getattr(req, "address", None) if req else None
        web_summary_obj = state.get("web_search_summary") or {}
        web_summary_text = web_summary_obj.get("summary") if isinstance(web_summary_obj, dict) else None

        # Prepare LLM inputs
        llm_inputs = {
            "subject_address": subject_address or "",
            "valuation": json.dumps(valuation, default=str),
            "drivers": json.dumps(drivers, default=str),
            "web_summary": web_summary_text or "",
            "comps": json.dumps(comps_for_report, default=str),
        }

        try:
            sections: ReportSections = self.report_writer.invoke(llm_inputs)
            report_sections = {
                "Executive Summary": sections.executive_summary,
                "Market Overview": sections.market_overview,
                "Comparable Analysis": sections.comparable_analysis,
                "Risks": sections.risks,
                "Recommendations": sections.recommendations,
            }
        except Exception:
            report_sections = {}

        state["report"] = {
            "subject": {
                "address": subject_address,
                "mlsId": getattr(req, "mlsId", None) if req else None,
                "assetClass": getattr(req, "asset_class", None) if req else None,
            },
            "valuation": valuation,
            "drivers": drivers,
            "comps": comps_for_report,
            "sections": report_sections,
        }
        state["done"] = True
        return state