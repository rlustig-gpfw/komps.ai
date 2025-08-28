from __future__ import annotations

import json
import sys
from typing import Any, Dict

from orchestration.graph import build_graph
from orchestration.types import RealEstateRequest, GraphState


def run_once(address: str, asset_class: str = "residential", mls_id: str = "TEST-MLS") -> Dict[str, Any]:
    graph = build_graph()

    request = RealEstateRequest(address=address, asset_class=asset_class, mlsId=mls_id)
    state: GraphState = {
        "real_estate_request": request,
    }

    final_state = graph.invoke(state)
    return final_state


def main() -> None:
    #address = "1183 Pearce Drive, Sonoma, CA 95476"
    address = "13413 Landfair Rd, San Diego, CA 92130"
    if len(sys.argv) > 1:
        address = " ".join(sys.argv[1:])

    result = run_once(address)

    report = result.get("final_report")
    if report is None:
        print("Graph completed without a report. Full state:")
        print(json.dumps(result, indent=2, default=str))
        return

    print("Report:\n" + json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()


