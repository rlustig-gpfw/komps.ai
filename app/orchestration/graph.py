from langgraph.graph import StateGraph, END
from orchestration.types import GraphState
from orchestration.nodes import Nodes


def build_graph():
    """
    Build the graph for the real estate investment feedback agent.
    """

    # Initialize node instances
    nodes = Nodes()

    g = StateGraph(GraphState)

    g.add_node("planner", nodes.planner)                 # LLM decides next Action or FINALIZE
    g.add_node("run_tool", nodes.run_tool)               # calls ToolsClient
    g.add_node("verify", nodes.verify)                   # deterministic lib
    g.add_node("update_state", nodes.update_state)       # merge verified claims
    g.add_node("summarize", nodes.summarize)             # summarize web search after update
    g.add_node("valuate", nodes.valuate)                 # deterministic math using verified_state to produce a valuation 
    g.add_node("report", nodes.report)                   # generate report for human review

    # edges
    g.set_entry_point("planner")
    g.add_edge("planner", "run_tool")              # if Action != FINALIZE
    g.add_edge("run_tool", "verify")
    g.add_edge("verify", "update_state")

    # After updating state, determine next step in a single conditional
    def next_after_update(s: GraphState):
        if s.get("human_gate"):
            return END
        if s.get("web_search_results") and not s.get("web_search_summary"):
            return "summarize"
        if s.get("action") and s["action"].kind == "FINALIZE":
            return "valuate"
        return "planner"

    g.add_conditional_edges("update_state", next_after_update, {
        "summarize": "summarize",
        "planner": "planner",
        "valuate": "valuate",
        END: END,
    })

    # After summarize, go back to planner to decide next action
    g.add_edge("summarize", "planner")

    g.add_edge("valuate", "report")
    g.add_edge("report", END)

    g = g.compile()
    # To save the mermaid graph drawing as a PNG file, call without arguments (it will use the default filename):
    g.get_graph().draw_mermaid_png(output_file_path="graph.png")

    return g