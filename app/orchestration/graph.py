from langgraph.graph import StateGraph, END
from app.orchestration.types import GraphState
from app.orchestration.nodes import Nodes
from app.tools.client import ToolsClient


def build_graph():
    """
    Build the graph for the real estate investment feedback agent.
    """

    # Initialize tools and node instance
    tools_client = ToolsClient()
    nodes = Nodes(tools_client)

    g = StateGraph(GraphState)

    g.add_node("planner", nodes.planner)                 # LLM decides next Action or FINALIZE
    g.add_node("run_tool", nodes.run_tool)               # calls ToolsClient
    g.add_node("verify", nodes.verify)                   # deterministic lib
    g.add_node("update_state", nodes.update_state)       # merge verified claims
    g.add_node("valuate", nodes.valuate)                 # deterministic math using verified_state to produce a valuation 
    g.add_node("report", nodes.report)                   # generate report for human review

    # edges
    g.set_entry_point("planner")
    g.add_edge("planner", "run_tool")              # if Action != FINALIZE
    g.add_edge("run_tool", "verify")
    g.add_edge("verify", "update_state")

    # planner loop vs finalize
    def planner_route(s: GraphState):
        if s.get("human_gate"):                    # low-conf required -> pause
            return END                             # caller handles review, then resume
        if s.get("action") and s["action"].kind == "FINALIZE":
            return "valuate"
        return "run_tool"

    g.add_conditional_edges("update_state", planner_route, {
        "run_tool": "run_tool",
        "valuate": "valuate",
        END: END
    })

    g.add_edge("valuate", "report")
    g.add_edge("report", END)

    return g.compile()