# Real-estate investment feedback
Problem: Investment teams waste hours collecting comps, zoning data, and market stats. AI agents can fetch relevant data from multiple sources, compute valuations based on local trends, and generate structured investment memos tailored to asset class and location.

Solution: Use an AI Agent to gather data, think through valuations based on comps/trends/collected data, and automatically develop an investment memo using an LLM.


## High level design
```mermaid
graph LR
  %% Nodes
  req([Request])
  planner[[Planner<br/>(LLM)]]
  tools[[Tools<br/>(Parcel, Zoning, Comps)]]
  verifier([Verifier<br/>- Schema & units (range/unit normalization)<br/>- Data freshness<br/>- Cross-check sources])
  humanReview([Human Review<br/>(Escalate if low confidence in data,<br/>freshness, agreement, etc.)])
  valuator[[Valuator<br/>]]
  humanVal([Human Valuation Reviewer])
  report([Report])

  %% Main flow
  req --> planner --> valuator --> humanVal --> report

  %% Tooling & checks
  planner <--> tools
  tools --> verifier
  verifier --> humanReview
  verifier -. feedback .-> planner
  humanReview --> valuator

  %% Styling
  classDef llm fill:#ffe0e0,stroke:#f66,stroke-width:1px;
  classDef human fill:#e4f7e4,stroke:#2da44e,stroke-width:1px;
  classDef system fill:#e6f0ff,stroke:#497cff,stroke-width:1px;
  classDef verify fill:#f5f5f5,stroke:#555,stroke-width:1px;

  class planner,tools,valuator;
  class humanReview,humanVal human;
  class req,report system;
  class verifier verify;
```


## Modules and Classes
/app
  /orchestration
    graph.py              # LangGraph wiring
    nodes.py              # planner(), run_tool(), verify(), update_state(), valuate(), synthesize()
    types.py              # Pydantic/TypedDicts below
  /tools
    client.py             # ToolsClient: get_parcel(), get_zoning(), get_comps()
  /verify
    verifier.py           # deterministic checks + claim scoring
  /valuation
    valuator.py           # deterministic weighted-comps
  /report
    writer.py             # memo_json -> HTML/PDF or JSON-only
  /api
    http.py               # FastAPI routes for React