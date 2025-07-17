# nodes/custom_nodes/rag_add_node.py

import logging
from typing import Optional
from pocketflow import AsyncBatchNode
from ...framework.tool_registry import tool_registry
from markitdown import MarkItDown
from pathlib import Path
import asyncio
import uuid
from datetime import datetime, timezone

# Import the new federated service
from ...rag.federation import RAGFederationService

logger = logging.getLogger(__name__)

@tool_registry(
    name="rag_add",
    description="Indexes one or more documents into the internal RAG knowledge base. Documents can be text strings or file paths.",
    parameters={
        "type": "object",
        "properties": {
            "documents": {
                "type": "array",
                "items": {"type": "string"},
                "description": "A list of documents to index (text content or file paths).",
            },
        },
        "required": ["documents"],
    },
)
class RAGAddNode(AsyncBatchNode):
    """
    A node that indexes documents into the default writable RAG data source.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Get the writable engine on initialization
        self.writable_engine = RAGFederationService.get_writable_engine()
        if not self.writable_engine:
            raise RuntimeError("RAGAddNode cannot be initialized: No default writable RAG data source is configured in rag_configs/index.yaml.")
        logger.info("rag_add_node_data_source", extra={"source_name": self.writable_engine.source_name})

    async def prep_async(self, shared):
        """Prepare the documents to be indexed."""
        state = shared.get("state", {})
        # Get documents from current_action
        documents = state.get("current_action", {}).get("documents", [])
        return documents

    def _sync_process_file(self, file_path: str) -> Optional[str]:
        """
        A synchronous helper function for file reading and conversion.
        This function will run in a separate thread.
        """
        try:
            md = MarkItDown(enable_plugins=True)
            # MarkItDown.convert() accepts a Path object
            result = md.convert(Path(file_path)).text_content
            logger.info("document_converted_in_thread", extra={"file_path": file_path})
            return result
        except Exception as e:
            logger.error("document_conversion_error_in_thread", extra={"file_path": file_path, "error": str(e)})
            return None

    async def exec_async(self, document: str) -> Optional[str]:
        """
        Process a single document: if it's a file path, read and convert the content asynchronously in a separate thread.
        """
        # Check if it is a file path
        if isinstance(document, str) and (Path(document).is_file() or Path(document).exists()):
            # Use asyncio.to_thread to run synchronous blocking operations in a worker thread
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._sync_process_file, document)
        elif isinstance(document, str):
            # If it is a plain text string, return it directly
            return document
        else:
            # If the input is not a string, log a warning and return None
            logger.warning("non_string_document_skipped", extra={"document_type": type(document).__name__})
            return None

    async def post_async(self, shared, prep_res, exec_res_list):
        """Chunk, add, and process embeddings for the processed document content."""
        # Filter out None values that may be returned from exec_async
        valid_docs_content = [content for content in exec_res_list if content]
        
        # The chunking logic here can be made more complex as needed.
        # For simplicity, we assume each document content is a "chunk".
        all_chunks = valid_docs_content

        if not all_chunks:
            logger.warning("RAGAddNode: No valid document content available for indexing.")
            return "default"

        logger.info("indexing_documents", extra={"chunk_count": len(all_chunks)})
        
        # Use the writable engine's db_store to add chunks
        for chunk in all_chunks:
            # Metadata such as doc_id, url, etc., can be obtained from the shared state or elsewhere
            await self.writable_engine.db_store.add_text_chunk(
                chunk_text=chunk,
                doc_id=shared.get("state", {}).get("current_doc_id", "default_doc") # example
            )
        
        # Trigger embedding processing for the newly added chunks
        await self.writable_engine.db_store.process_pending_embeddings()

        logger.info("indexing_completed", extra={"chunk_count": len(all_chunks)})
        
        # Write the result to the Inbox to notify the Agent that the task is complete
        state = shared["state"]
        tool_call_id = state.get("current_tool_call_id")
        
        tool_result_payload = {
            "tool_name": self._tool_info["name"],
            "tool_call_id": tool_call_id,
            "is_error": False,
            "content": {"status": "success", "message": f"Successfully processed {len(all_chunks)} documents for indexing."}
        }
        
        state.setdefault('inbox', []).append({
            "item_id": f"inbox_{uuid.uuid4().hex[:8]}",
            "source": "TOOL_RESULT",
            "payload": tool_result_payload,
            "consumption_policy": "consume_on_read",
            "metadata": {"created_at": datetime.now(timezone.utc).isoformat()}
        })
        
        state['current_action'] = None
        
        return "default"