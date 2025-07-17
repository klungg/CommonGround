# File path: nodes/custom_nodes/review_workspace_tool.py
import logging
import os
from pathlib import Path
from typing import Optional
import aiofiles
from ..base_tool_node import BaseToolNode
from ...framework.tool_registry import tool_registry
import uuid
from datetime import datetime, timezone

# --- BeautifulSoup4 (bs4) for HTML parsing ---
# bs4 is a very common and robust library for this task.
# We'll use a try-except block to guide the user if it's not installed.
try:
    from bs4 import BeautifulSoup
except ImportError:
    # If bs4 is not installed, we'll raise an error later when the tool is used.
    # This allows the server to start even if the dependency is missing.
    BeautifulSoup = None

logger = logging.getLogger(__name__)

# Re-use the WORKSPACE_DIR definition for consistency
WORKSPACE_DIR = Path("workspace").resolve()

def _get_run_workspace(run_id: str) -> Optional[Path]:
    """Helper to get the workspace directory for a specific run."""
    if not run_id:
        return None
    return WORKSPACE_DIR.joinpath(run_id).resolve()

@tool_registry(
    name="review_workspace_files",
    description="Reviews the file structure of the current run's workspace. It can list all files and directories, or parse a specific HTML file to check for broken local links (e.g., to other HTML files, CSS, JS, or images).",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Optional. The relative path to a specific HTML file to analyze for broken links. If omitted, the tool will list all files in the run's workspace."
            },
            "recursive": {
                "type": "boolean",
                "default": True,
                "description": "If `path` is omitted, setting this to true will list files in all subdirectories. Defaults to true."
            }
        },
        "required": []
    },
    toolset_name="file_system_tools" # Add it to our existing toolset
)
class ReviewWorkspaceToolNode(BaseToolNode):
    """
    A tool to review files in the workspace, list them, or check an HTML file for broken local links.
    """
    async def exec_async(self, prep_res: dict):
        # --- Start: Logic moved from original prep_async ---
        tool_params = prep_res.get("tool_params", {})
        shared_context = prep_res.get("shared_context", {})

        if BeautifulSoup is None:
            return {"status": "error", "error_message": "Server dependency 'beautifulsoup4' is not installed. This tool cannot function. Please run 'pip install beautifulsoup4'."}

        relative_path = tool_params.get("path")
        recursive_list = tool_params.get("recursive", True)
        
        run_id = shared_context.get('meta', {}).get("run_id")
        if not run_id:
            return {"status": "error", "error_message": "Critical error: 'run_id' not found in shared_context.meta."}

        run_workspace = _get_run_workspace(run_id)
        if not run_workspace or not run_workspace.exists():
            return {"status": "error", "error_message": f"Workspace for run '{run_id}' does not exist yet."}

        target_html_path = None
        if relative_path:
            # Security check for the target file path
            try:
                if ".." in relative_path.split(os.path.sep):
                    return {"status": "error", "error_message": "Invalid file path: '..' sequence is not allowed."}
                target_html_path = run_workspace.joinpath(relative_path).resolve()
                if not str(target_html_path).startswith(str(run_workspace)):
                     return {"status": "error", "error_message": f"Security violation: Attempted to review a file outside the run workspace. Path: {relative_path}"}
                if not target_html_path.is_file():
                    return {"status": "error", "error_message": f"File not found at specified path: '{relative_path}'"}
            except Exception as e:
                logger.exception("workspace_path_resolution_error", extra={"relative_path": relative_path, "run_id": run_id, "error": str(e)})
                return {"status": "error", "error_message": f"Error resolving path: {e}"}
        # --- End: Logic moved from original prep_async ---

        # --- Start: Original exec_async logic ---
        if target_html_path:
            # The helper methods _analyze_html_file and _list_workspace_files
            # already return dicts with "status". We just need to wrap them in a payload.
            result = await self._analyze_html_file(run_workspace, target_html_path)
        else:
            result = self._list_workspace_files(run_workspace, recursive_list)
        
        if result.get("status") == "success":
            return {"status": "success", "payload": result}
        else:
            return {"status": "error", "error_message": result.get("message")}

    def _list_workspace_files(self, run_workspace: Path, recursive: bool) -> dict:
        """Lists files and directories in the workspace."""
        try:
            file_list = []
            if recursive:
                for root, dirs, files in os.walk(run_workspace):
                    for name in files:
                        p = Path(root) / name
                        file_list.append(str(p.relative_to(run_workspace)))
                    for name in dirs:
                        p = Path(root) / name
                        file_list.append(str(p.relative_to(run_workspace)) + '/')
            else:
                for p in run_workspace.iterdir():
                    path_str = str(p.relative_to(run_workspace))
                    if p.is_dir():
                        path_str += '/'
                    file_list.append(path_str)
            
            return {
                "status": "success",
                "message": "Workspace file listing complete.",
                "review_type": "directory_listing",
                "files": sorted(file_list)
            }
        except Exception as e:
            error_message = f"Failed to list workspace files: {e}"
            logger.exception("workspace_list_files_failed", extra={"error": str(e)})
            return {"status": "error", "message": error_message}

    async def _analyze_html_file(self, run_workspace: Path, html_path: Path) -> dict:
        """Analyzes an HTML file for broken local links."""
        try:
            async with aiofiles.open(html_path, mode='r', encoding='utf-8') as f:
                content = await f.read()

            soup = BeautifulSoup(content, 'html.parser')
            
            broken_links = []
            found_links = []
            
            # Attributes to check for local links
            link_attrs = {
                'a': 'href',
                'link': 'href',
                'script': 'src',
                'img': 'src',
                'source': 'src',
                'video': 'src',
                'audio': 'src'
            }
            
            for tag_name, attr_name in link_attrs.items():
                for tag in soup.find_all(tag_name, **{attr_name: True}):
                    link = tag[attr_name]
                    # Filter out external links, data URIs, anchor links, etc.
                    if link.startswith(('http:', 'https:', 'data:', '#', 'mailto:', 'tel:')):
                        continue
                    
                    found_links.append(link)
                    # Resolve the link path relative to the HTML file's directory
                    absolute_link_path = (html_path.parent / link).resolve()
                    
                    # Check if the linked file exists and is within the workspace
                    if not str(absolute_link_path).startswith(str(run_workspace)) or not absolute_link_path.exists():
                        broken_links.append({
                            "link_path": link,
                            "tag": f"<{tag_name}>",
                            "reason": "File not found or outside workspace."
                        })
            
            return {
                "status": "success",
                "message": f"HTML file analysis complete. Found {len(broken_links)} broken local link(s).",
                "review_type": "html_link_check",
                "file_analyzed": str(html_path.relative_to(run_workspace)),
                "found_local_links": sorted(list(set(found_links))),
                "broken_local_links": broken_links
            }
            
        except Exception as e:
            error_message = f"Failed to analyze HTML file '{html_path.relative_to(run_workspace)}': {e}"
            logger.exception("html_file_analysis_failed", extra={"file_path": str(html_path.relative_to(run_workspace)), "error": str(e)})
            return {"status": "error", "message": error_message}

