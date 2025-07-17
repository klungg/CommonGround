import os
import asyncio
from pathlib import Path
import subprocess
import tempfile
import logging
from markitdown import MarkItDown
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent
from typing import Dict, Any, List, Optional

# Import the websocket manager
from .websocket_manager import manager

# To integrate RAG, we'll import the RAGAddNode
from ..nodes.custom_nodes.rag_add_node import RAGAddNode
from ..rag.federation import RAGFederationService

# This will be set at app startup
PROJECTS_ROOT_DIR = ""
# Define which file types should trigger RAG indexing (fallback if yek is not available)
SUPPORTED_DOC_EXTENSIONS = ['.txt', '.md', '.py', '.rst', '.yaml', '.yml']

logger = logging.getLogger(__name__)

def get_project_id_from_path(path: str) -> Optional[str]:
    """Extracts the project_id from a file path based on the root directory."""
    if not PROJECTS_ROOT_DIR:
        return None
    try:
        relative_path = os.path.relpath(path, PROJECTS_ROOT_DIR)
        parts = relative_path.split(os.sep)
        if parts and not parts[0].startswith('.'):
            return parts[0]
    except ValueError:
        return None
    return None

def generate_file_tree(project_path: str) -> List[Dict[str, Any]]:
    """Generates a JSON-serializable file tree for a given project path."""
    tree = []
    if not os.path.isdir(project_path):
        return tree
        
    for item in os.listdir(project_path):
        if item.startswith('.'): # Ignore hidden files/dirs
            continue
        item_path = os.path.join(project_path, item)
        if os.path.isdir(item_path):
            tree.append({
                "name": item, 
                "type": "directory",
                "children": generate_file_tree(item_path)
            })
        else:
            tree.append({"name": item, "type": "file"})
    tree.sort(key=lambda x: (x['type'] != 'directory', x['name']))
    return tree

async def check_yek_available() -> bool:
    """Check if yek command is available in the system."""
    try:
        result = subprocess.run(['yek', '--help'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

async def trigger_rag_indexing_with_yek(project_id: str, changed_file_path: str):
    """
    Intelligently process project files using yek, then perform RAG indexing
    """
    logger.info("rag_indexing_with_yek_start", extra={"project_id": project_id, "trigger_file": changed_file_path})
    
    try:
        project_path = os.path.join(PROJECTS_ROOT_DIR, project_id)
        project_path = os.path.abspath(project_path)  # Ensure it's an absolute path
        
        # Check if the project path exists
        if not os.path.exists(project_path):
            logger.error("rag_indexing_project_path_not_found", extra={"project_path": project_path})
            return
        
        # Prioritize using yek to intelligently select files
        yek_files = await get_files_with_yek(project_path)
        
        if yek_files:
            # Use files identified by yek
            logger.info("rag_indexing_using_yek_files", extra={"file_count": len(yek_files), "project_id": project_id})
            await process_files_for_rag(yek_files, project_id)
        else:
            # If yek is unavailable or fails, fall back to scanning all supported files
            logger.info("rag_indexing_yek_unavailable_or_failed", extra={"project_id": project_id})
            all_files = scan_supported_files(project_path)
            if all_files:
                logger.info("rag_indexing_fallback_to_scan", extra={"file_count": len(all_files), "project_id": project_id})
                await process_files_for_rag(all_files, project_id)
            else:
                logger.info("rag_indexing_no_supported_files_found", extra={"project_id": project_id})
                
    except Exception as e:
        logger.error("rag_indexing_with_yek_error", extra={"error": str(e)}, exc_info=True)
        logger.info("rag_indexing_falling_back_to_simple_processing", extra={"project_id": project_id, "trigger_file": changed_file_path})
        await trigger_rag_indexing_fallback(project_id, changed_file_path)

def scan_supported_files(project_path: str) -> List[str]:
    """
    Scan the project directory to find all supported file types
    """
    supported_files = []
    
    for root, dirs, files in os.walk(project_path):
        # Ignore common irrelevant directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', 'venv', '.venv']]
        
        for file in files:
            if file.startswith('.'):
                continue
                
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext in SUPPORTED_DOC_EXTENSIONS:
                supported_files.append(file_path)
    
    return supported_files

async def get_files_with_yek(project_path: str) -> List[str]:
    """
    Use yek to get a list of important files
    """
    try:
        # Check if yek is available
        if not await check_yek_available():
            return []
        
        # Process the entire project with yek, limiting to a reasonable number of tokens
        yek_command = [
            "yek", 
            project_path,
            "--tokens", "128k"
        ]
        
        logger.info("running_yek_command", extra={"command": ' '.join(yek_command)})
        
        result = subprocess.run(
            yek_command, 
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0:
            # Parse yek's output to get the file list
            # yek uses the ">>>> filename" format to separate files
            files = []
            output_lines = result.stdout.split('\n')
            
            for line in output_lines:
                line = line.strip()
                if line.startswith('>>>> '):
                    # Extract the filename
                    filename = line[5:].strip()  # Remove the ">>>> " prefix
                    if filename:
                        # Convert relative path to absolute path
                        if os.path.isabs(filename):
                            file_path = filename
                        else:
                            file_path = os.path.join(project_path, filename)
                        
                        # Ensure the file exists
                        if os.path.isfile(file_path):
                            files.append(os.path.abspath(file_path))
            
            if files:
                logger.info("yek_file_discovery_success", extra={"file_count": len(files)})
                # Using debug level for file list to avoid flooding logs
                for f in files:
                    try:
                        rel_path = os.path.relpath(f, project_path)
                        logger.debug("yek_discovered_file", extra={"file": rel_path})
                    except ValueError:
                        logger.debug("yek_discovered_file_absolute", extra={"file": f})
                return files
            else:
                logger.warning("yek_output_no_file_markers")
        else:
            logger.error("yek_command_failed", extra={"return_code": result.returncode, "stderr": result.stderr})
        
        return []
        
    except Exception as e:
        logger.error("yek_discovery_exception", extra={"error": str(e)})
        return []

async def process_files_for_rag(file_paths: List[str], project_id: str):
    """
    Pass the file list to the RAG system for indexing
    """
    if not file_paths:
        return
    writable_engine = RAGFederationService.get_writable_engine()
    if not writable_engine:
        logger.error("RAG Indexing failed: No writable RAG engine configured.")
        return

    # --- Core modification: Do not instantiate RAGAddNode anymore, call the engine's method directly ---
    try:
        # Assume we will create a helper method in RAGEngine to handle indexing
        # Or call the db_store's method directly
        
        # 1. Read all file contents
        all_docs_content = []
        for file_path in file_paths:
            if os.path.exists(file_path) and os.path.isfile(file_path):
                 md = MarkItDown(enable_plugins=True)
                 content = md.convert(Path(file_path)).text_content
                 all_docs_content.append(content)

        if not all_docs_content:
            logger.warning("No valid content to index.")
            return

        # 2. Call the db_store's method, passing in the project_id
        for content in all_docs_content:
             await writable_engine.db_store.add_text_chunk(
                 chunk_text=content,
                 project_id=project_id,
                 # Other metadata can be added as needed
             )
        
        # 3. Trigger embedding processing
        await writable_engine.db_store.process_pending_embeddings()
        
        logger.info("rag_indexing_success", extra={"files_processed": len(all_docs_content), "project_id": project_id})

    except Exception as e:
        logger.error("rag_indexing_error", extra={"project_id": project_id, "error_message": str(e)}, exc_info=True)

async def trigger_rag_indexing_fallback(project_id: str, file_path: str):
    """
    Fallback RAG indexing when yek is not available - processes a single file.
    (MODIFIED: Now uses RAGFederationService directly)
    """
    logger.info("rag_indexing_fallback_start", extra={"file_path": file_path, "project_id": project_id})
    
    # 1. Get a writable RAG engine
    writable_engine = RAGFederationService.get_writable_engine()
    if not writable_engine:
        logger.error("rag_indexing_fallback_no_engine", extra={"file_path": file_path})
        return

    try:
        # 2. Check if the file exists
        if os.path.exists(file_path) and os.path.isfile(file_path):
            # 3. Read and convert file content
            md = MarkItDown(enable_plugins=True)
            content = md.convert(Path(file_path)).text_content
            
            if not content:
                logger.warning("rag_indexing_fallback_no_content", extra={"file_path": file_path})
                return

            # 4. Call the db_store's method, passing in the project_id
            await writable_engine.db_store.add_text_chunk(
                chunk_text=content,
                project_id=project_id,
                doc_id=os.path.basename(file_path), # Use filename as doc_id
                url=file_path # Use file path as url
            )
            
            # 5. Trigger embedding processing
            await writable_engine.db_store.process_pending_embeddings()

            logger.info("rag_indexing_fallback_success", extra={"file_path": file_path})
        else:
            logger.warning("rag_indexing_fallback_file_not_found", extra={"file_path": file_path})

    except Exception as e:
        logger.error("rag_indexing_fallback_error", extra={"file_path": file_path, "error_message": str(e)}, exc_info=True)

class ProjectChangeHandler(FileSystemEventHandler):
    """Handles file system events and triggers updates."""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.loop = loop
        self.debounce_timers: Dict[str, asyncio.TimerHandle] = {}
        self.rag_debounce_timers: Dict[str, asyncio.TimerHandle] = {}

    def on_any_event(self, event):
        """
        Catches all events, triggers RAG indexing for relevant files,
        and uses a debouncing strategy to broadcast file tree updates.
        """
        if event.is_directory:
            return

        project_id = get_project_id_from_path(event.src_path)
        if not project_id:
            return

        # --- RAG Indexing Logic (with debouncing for project-level updates) ---
        file_ext = os.path.splitext(event.src_path)[1].lower()
        if file_ext in SUPPORTED_DOC_EXTENSIONS:
            if isinstance(event, (FileCreatedEvent, FileModifiedEvent)):
                # Cancel previous RAG timer for this project if exists
                if project_id in self.rag_debounce_timers:
                    self.rag_debounce_timers[project_id].cancel()
                
                # Set a debounced RAG indexing timer (2 seconds delay)
                self.rag_debounce_timers[project_id] = self.loop.call_later(
                    2.0, self._do_rag_indexing, project_id, event.src_path
                )
            elif isinstance(event, FileDeletedEvent):
                # TODO: Implement logic to remove a document from the index
                logger.warning("file_deleted_rag_removal_not_implemented", extra={"path": event.src_path})

        # --- File Tree Broadcast Logic (with debouncing) ---
        if project_id in self.debounce_timers:
            self.debounce_timers[project_id].cancel()

        self.debounce_timers[project_id] = self.loop.call_later(
            0.5, self._do_broadcast, project_id
        )

    def _do_rag_indexing(self, project_id: str, file_path: str):
        """Execute RAG indexing in the event loop."""
        asyncio.run_coroutine_threadsafe(
            trigger_rag_indexing_with_yek(project_id, file_path),
            self.loop
        )
        if project_id in self.rag_debounce_timers:
            del self.rag_debounce_timers[project_id]

    def _do_broadcast(self, project_id: str):
        """Generates and broadcasts the file tree."""
        logger.info("broadcasting_file_tree_update", extra={"project_id": project_id})
        project_path = os.path.join(PROJECTS_ROOT_DIR, project_id)
        
        new_tree = generate_file_tree(project_path)
        
        message = {
            "event": "file_tree_update",
            "projectId": project_id,
            "tree": new_tree,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        asyncio.run_coroutine_threadsafe(
            manager.broadcast(message, project_id), 
            self.loop
        )
        if project_id in self.debounce_timers:
            del self.debounce_timers[project_id]

def start_file_monitoring(path: str, loop: asyncio.AbstractEventLoop):
    """Initializes and starts the file system observer."""
    if not os.environ.get("RAG_ENABLED"):
        logger.info("rag_disabled_skipping_file_monitoring")
        return
    global PROJECTS_ROOT_DIR
    PROJECTS_ROOT_DIR = os.path.abspath(path)
    
    event_handler = ProjectChangeHandler(loop)
    observer = Observer()
    observer.schedule(event_handler, PROJECTS_ROOT_DIR, recursive=True)
    observer.start()
    logger.info("file_monitoring_started", extra={"path": PROJECTS_ROOT_DIR})
    return observer
