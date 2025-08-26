import json
import os
from typing import Any, Dict

from langchain.tools import tool


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


class ToolsClient:
    """Container for available tools. For now, only comps is implemented."""

    def __init__(self) -> None:
        self._tools: Dict[str, Any] = {
            "get_comps": get_comps,
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


