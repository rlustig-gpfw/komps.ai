import json
import os
from typing import Any, Dict

from langchain.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults


def _sample_comps_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "RapidAPI_Comps_response.json",
    )


@tool("get_comps")
def get_comps(address: str = "", apn: str = "", asset_class: str = "") -> Dict[str, Any]:
    """
    Return comparable sales for a subject property. This MVP tool loads static sample data.

    Inputs are accepted for interface parity but are not used.
    """
    try:
        with open(_sample_comps_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"comps": []}


@tool("web_search")
def web_search(address: str) -> Dict[str, Any]:
    """
    Search the web for information about a property and it's local area.
    """
    search_tool = TavilySearchResults(
        max_results=3,
        include_answer=True,
        include_raw_content=False,
        include_images=False,
        search_depth="advanced",
    )

    query = f"Local area and property information for {address}"
    results = search_tool.invoke({"query": query})
    if not results:
        return "Unable to find property information for {address}"
    
    # Build a snippet of info from the results
    snippet = ""
    for result in results:
        snippet += result.get("content","")[:500] + "\n"
    
    return snippet


class ToolsClient:
    """Container for available tools. For now, only comps is implemented."""

    def __init__(self) -> None:
        self._tools: Dict[str, Any] = {
            "get_comps": get_comps,
            "web_search": web_search,
        }

    def call(self, name: str, args: Dict[str, Any]) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            return None
        # LangChain Tool conforms to Runnable -> supports .invoke
        return tool.invoke(args)

    def get_tool(self, name: str):
        return self._tools.get(name)

    def list_tools(self):
        return list(self._tools.keys())


