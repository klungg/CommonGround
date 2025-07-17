import logging
from pocketflow import AsyncNode
from ...framework.tool_registry import tool_registry
import uuid
from datetime import datetime, timezone

from ...rag.federation import RAGFederationService

logger = logging.getLogger(__name__)

@tool_registry(
    name="list_rag_sources",
    description="Lists all available RAG (knowledge base) data sources and their descriptions, to help decide which knowledge base to query next.",
    parameters={"type": "object", "properties": {}}, # This tool requires no parameters
    toolset_name="rag_tools"
)
class ListRAGSourcesNode(AsyncNode):
    """A tool node that calls the RAG federation service to list available data sources."""

    async def prep_async(self, shared):
        # No preparation needed
        return {}

    async def exec_async(self, prep_res):
        """Execute: Get data source details from the federation service."""
        logger.info("Executing list_rag_sources tool...")
        source_details = RAGFederationService.get_source_details()
        return {"sources": source_details}

    async def post_async(self, shared, prep_res, exec_res):
        """Place the results into the Agent's inbox."""
        state = shared["state"]
        tool_call_id = state.get("current_tool_call_id")
        
        tool_result_payload = {
            "tool_name": self._tool_info["name"],
            "tool_call_id": tool_call_id,
            "is_error": False,
            "content": exec_res # Directly return the content of exec_res
        }
        
        state.setdefault('inbox', []).append({
            "item_id": f"inbox_{uuid.uuid4().hex[:8]}",
            "source": "TOOL_RESULT",
            "payload": tool_result_payload,
            "consumption_policy": "consume_on_read",
            "metadata": {"created_at": datetime.now(timezone.utc).isoformat()}
        })
        
        state['current_action'] = None
        logger.info("rag_sources_added_to_inbox")
        return "default"