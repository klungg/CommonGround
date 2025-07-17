# File path: nodes/custom_nodes/write_file_tool.py
import logging
import os
from pathlib import Path
import aiofiles # For asynchronous file operations
from ..base_tool_node import BaseToolNode
from ...framework.tool_registry import tool_registry

logger = logging.getLogger(__name__)

# --- MODIFICATION START ---
# WORKSPACE_DIR is now the main workspace for all runs
WORKSPACE_DIR = Path("workspace").resolve()
# No longer needs to be created here, as subdirectories for each run will be created on demand
# --- MODIFICATION END ---


@tool_registry(
    name="write_file",
    description="Writes or overwrites content to a specified file path. This tool performs a full overwrite; any existing file at the path will be completely replaced. It is crucial to provide the **entire, complete file content** in the 'content' parameter, even when making small changes.",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The relative path of the file to be written inside the run's workspace directory (e.g., 'index.html', 'js/script.js')."
            },
            "content": {
                "type": "string",
                "description": "The full content to be written to the file."
            }
        },
        "required": ["file_path", "content"]
    },
    toolset_name="file_system_tools"
)
class WriteFileToolNode(BaseToolNode):
    """
    A tool node that writes content to a specified file, including security checks and isolating output by run_id.
    """
    async def exec_async(self, prep_res: dict):
        # --- Start: Logic moved from original prep_async ---
        tool_params = prep_res.get("tool_params", {})
        shared_context = prep_res.get("shared_context", {})

        file_path = tool_params.get("file_path")
        content = tool_params.get("content")

        run_id = shared_context.get('meta', {}).get("run_id")
        if not run_id:
            return {"status": "error", "error_message": "Critical error: 'run_id' not found in shared_context.meta. Cannot determine workspace."}

        if not file_path or not isinstance(file_path, str):
            return {"status": "error", "error_message": "Missing or invalid 'file_path' parameter."}
        if content is None or not isinstance(content, str):
            return {"status": "error", "error_message": "Missing or invalid 'content' parameter."}

        try:
            per_run_workspace = WORKSPACE_DIR.joinpath(run_id).resolve()
            per_run_workspace.mkdir(parents=True, exist_ok=True)

            if ".." in file_path.split(os.path.sep):
                return {"status": "error", "error_message": "Invalid file path: '..' sequence is not allowed."}

            safe_full_path = per_run_workspace.joinpath(file_path).resolve()

            if not str(safe_full_path).startswith(str(per_run_workspace)):
                return {"status": "error", "error_message": f"Security violation: Attempted to write outside of the designated run workspace directory. Path: {file_path}"}

        except Exception as e:
            logger.exception("write_file_path_resolution_error", extra={"file_path": file_path, "run_id": run_id, "error": str(e)})
            return {"status": "error", "error_message": f"Error resolving path: {e}"}
        # --- End: Logic moved from original prep_async ---

        # --- Start: Original exec_async logic ---
        content_to_write = content
        relative_path_str = str(safe_full_path.relative_to(WORKSPACE_DIR))

        try:
            safe_full_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(safe_full_path, mode='w', encoding='utf-8') as f:
                await f.write(content_to_write)
            
            message = f"Successfully wrote {len(content_to_write)} bytes to '{relative_path_str}'"
            logger.info("file_write_success", extra={"bytes_written": len(content_to_write), "path": relative_path_str})
            return {
                "status": "success", 
                "payload": {"message": message, "file_path_written": relative_path_str}
            }
            
        except Exception as e:
            error_message = f"Failed to write to file '{relative_path_str}': {e}"
            logger.exception("file_write_failed", extra={"path": relative_path_str, "error": str(e)})
            return {"status": "error", "error_message": error_message}
