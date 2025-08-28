import json
import os
from typing import Any, Dict, List, Tuple

from langchain.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults


_COMPS_CACHE: Dict[str, Dict[str, Any]] | None = None


def _data_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def _normalize_address_from_filename(filename: str) -> str:
    # Strip extension
    name, _ = os.path.splitext(filename)
    # Remove leading comps_######## if present
    parts = name.split("__") if "__" in name else [name]
    base = parts[0]
    # If base starts with "comps_" followed by 8 digits and an underscore, remove that prefix
    import re
    base = re.sub(r"^comps_\d{8}_", "", base)
    # Replace separators with spaces and commas as needed
    base = base.replace("_", " ").replace("--", ", ")
    return base.strip().lower()


def _preload_comps() -> Dict[str, Dict[str, Any]]:
    global _COMPS_CACHE
    if _COMPS_CACHE is not None:
        return _COMPS_CACHE
    cache: Dict[str, Dict[str, Any]] = {}
    directory = _data_dir()
    try:
        for fn in os.listdir(directory):
            if not fn.lower().endswith(".json"):
                continue
            try:
                with open(os.path.join(directory, fn), "r", encoding="utf-8") as f:
                    data = json.load(f)
                key = _normalize_address_from_filename(fn)
                cache[key] = data
            except Exception:
                continue
    finally:
        _COMPS_CACHE = cache
    return cache


@tool("get_comps")
def get_comps(address: str = "", apn: str = "", asset_class: str = "") -> Dict[str, Any]:
    """
    Return comparable sales for a subject property. Loads data based on the subject address.

    File naming convention:
    - Each JSON filename begins with the address portion, followed by optional separators and/or a comps_######## suffix.
    - Example: "1183_Pearce_Drive__comps_20241201.json" → key: "1183 pearce drive".
    """
    if not address:
        return {"comps": []}
    key = _normalize_address_from_filename(address)
    cache = _preload_comps()
    # Exact match first
    if key in cache:
        return cache[key]
    # Fuzzy: try a simplified key (commas removed, multiple spaces collapsed)
    simplified = key.replace(",", " ").split()
    simplified_key = " ".join(simplified)
    for k, v in cache.items():
        if simplified_key in k:
            return v
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


