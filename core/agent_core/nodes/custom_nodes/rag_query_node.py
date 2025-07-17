import logging
from ..base_tool_node import BaseToolNode
from ...framework.tool_registry import tool_registry
import uuid
import json
from datetime import datetime, timezone
from ...llm.config_resolver import LLMConfigResolver
from agent_profiles.loader import SHARED_LLM_CONFIGS

from ...rag.federation import RAGFederationService

logger = logging.getLogger(__name__)

@tool_registry(
    name="rag_query",
    description="Performs a semantic search in the knowledge base based on the user's question. Can specify one or more data sources to query, or search all available sources by default.",
    parameters={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The user question to search for.",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "A list of tags to filter results by (optional)."
            },
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "A list of one or more data source names to query (e.g., ['arxiv_abstract_introduction', 'internal_project_docs']). If omitted, all available data sources will be searched."
            }
        },
        "required": ["question"],
    },
    toolset_name="rag_tools"
)
class RAGQueryNode(BaseToolNode):
    """
    A node that queries across all configured RAG data sources via a federated service.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # No initialization needed, we will use the global RAGFederationService singleton

    async def prep_async(self, shared):
        """Prepare query parameters, including project_id and sources."""
        state = shared.get("state", {})
        current_action = state.get("current_action", {})
        question = current_action.get("question", "")
        tags = current_action.get("tags")
        sources = current_action.get("sources")

        project_id = shared.get("refs", {}).get("run", {}).get("project_id")
        if not project_id:
             logger.error("rag_query_project_id_missing")
             return {"error": "Critical internal error: project_id not found."}

        return {"question": question, "tags": tags, "sources": sources, "project_id": project_id}

    async def exec_async(self, prep_res):
        """Execute the federated search."""
        if "error" in prep_res:
            return prep_res
        
        question = prep_res["question"]
        tags = prep_res.get("tags")
        sources_to_query = prep_res.get("sources")
        project_id = prep_res["project_id"]

        if not question:
            return {"error": "Question cannot be empty."}

        logger.debug("rag_federated_query_debug", extra={"question": question})

        source_log_msg = f"sources: {sources_to_query}" if sources_to_query else "all sources"
        logger.info("rag_federated_query_execution", extra={"question": question, "source_log_msg": source_log_msg})

        results = await RAGFederationService.search_all(
            query_text=question,
            project_id=project_id,
            top_k=10,
            tags=tags,
            sources=sources_to_query
        )
        
        if not results:
            # Even if there are no results, return a standard success structure
            return {
                "status": "success",
                "message": "No relevant documents found in the specified knowledge base(s).",
                "search_results": []
            }

        return {
            "status": "success",
            "message": f"Found {len(results)} potentially relevant document(s).",
            "search_results": results
        }

    async def post_async(self, shared, prep_res, exec_res):
        """Place the JSON search results into the Agent's inbox."""
        state = shared["state"]
        tool_call_id = state.get("current_tool_call_id")
        
        # exec_res is now the payload we want ---
        is_error = "error" in exec_res or exec_res.get("status") != "success"
        
        # exec_res itself is the complete, structured content we want to pass to the LLM
        # We no longer need to build main_content_for_llm
        content_for_payload = exec_res
        
        tool_result_payload = {
            "tool_name": self._tool_info["name"],
            "tool_call_id": tool_call_id,
            "is_error": is_error,
            "content": content_for_payload
        }
        
        state.setdefault('inbox', []).append({
            "item_id": f"inbox_{uuid.uuid4().hex[:8]}",
            "source": "TOOL_RESULT",
            "payload": tool_result_payload,
            "consumption_policy": "consume_on_read",
            "metadata": {"created_at": datetime.now(timezone.utc).isoformat()}
        })

        state['current_action'] = None
        logger.info("rag_query_results_added_to_inbox")
        return "default"
