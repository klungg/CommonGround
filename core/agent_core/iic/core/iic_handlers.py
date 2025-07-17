import os
import uuid
import shutil
import json
import asyncio
import aiofiles
import logging, re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime
from fastapi import HTTPException
from api.events import broadcast_project_structure_update # Import new broadcast function
from ..parser.parser import IICBlock, parse_iic

logger = logging.getLogger(__name__)

BASE_DIR = "projects"
DEFAULT_PROJECT = "default"
DEFAULT_DELETE_DIR = ".deleted"

# Ensure the base directory exists
os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, DEFAULT_PROJECT), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, DEFAULT_DELETE_DIR), exist_ok=True)

# Module-level variable, maintains an asynchronous lock for each project.iic file
_project_file_locks = defaultdict(asyncio.Lock)

def _slugify(text: str) -> str:
    """Converts a string to a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[\s_]+', '-', text) # Replace spaces and underscores with hyphens
    text = re.sub(r'[^\w\.\-]', '', text) # Remove all non-word, non-dot, non-hyphen chars
    return text or "unnamed-run"

async def _read_project_index(project_path: str) -> Dict[str, str]:
    """
    Safely reads run_index data from a project.iic file.
    Returns an empty dictionary if the index block or file does not exist.
    """
    iic_file = os.path.join(project_path, "project.iic")
    if not os.path.exists(iic_file):
        return {}
    
    # Acquire the lock for the corresponding file to ensure the content is not modified during reading
    lock = _project_file_locks[iic_file]
    async with lock:
        async with aiofiles.open(iic_file, 'r', encoding='utf-8') as f:
            content = await f.read()
    
    blocks = parse_iic(content)
    index_block = next((b for b in blocks if b.attributes.get("type") == "run_index"), None)
    
    if index_block and index_block.content:
        try:
            return json.loads(index_block.content)
        except json.JSONDecodeError:
            logger.warning("iic_run_index_decode_failed", extra={"description": "Failed to decode run_index JSON", "iic_file": iic_file})
            return {}
    return {}

async def _write_project_index(project_path: str, index_data: Dict[str, str]):
    """
    Atomically writes the run_index data back to the project.iic file.
    This function handles reading, modifying, and writing back the file to ensure atomicity.
    """
    iic_file = os.path.join(project_path, "project.iic")
    lock = _project_file_locks[iic_file]
    
    async with lock:
        blocks = []
        if os.path.exists(iic_file):
            async with aiofiles.open(iic_file, 'r', encoding='utf-8') as f:
                content = await f.read()
            blocks = parse_iic(content)
        else:
            # If project.iic does not exist, we should not create it here,
            # because the creation of project.iic should be handled in create_project.
            # This function only focuses on updating the index.
            pass

        # Find or create the run_index block
        index_block = next((b for b in blocks if b.attributes.get("type") == "run_index"), None)
        if not index_block:
            index_block = IICBlock(
                type="block",
                attributes={"id": "project_run_index_block", "type": "run_index", "format": "json"},
                content=""
            )
            blocks.append(index_block)
        
        # Update the content and prepare to write back
        index_block.content = json.dumps(index_data, indent=2, ensure_ascii=False)
        
        # aiofiles for asynchronous writing
        async with aiofiles.open(iic_file, 'w', encoding='utf-8') as f:
            await f.write("\n\n".join(b.to_iic() for b in blocks))

async def find_iic_file_by_run_id(run_id_to_find: str) -> Optional[str]:
    """
    Efficiently finds a file path by scanning the indexes of all projects.
    If not found in the index, it falls back to a filesystem scan and performs self-healing (updates the index).
    """
    projects_dir = Path(BASE_DIR)
    if not projects_dir.is_dir():
        return None

    for project_folder in projects_dir.iterdir():
        if not project_folder.is_dir() or project_folder.name == DEFAULT_DELETE_DIR:
            continue
        
        project_path_str = str(project_folder)
        
        # 1. Prioritize searching from the index
        index_data = await _read_project_index(project_path_str)
        if run_id_to_find in index_data:
            filename = index_data[run_id_to_find]
            file_path = project_folder / filename
            # Ensure the file actually exists to prevent stale index entries
            if file_path.exists():
                return str(file_path.resolve())
            else:
                logger.warning("iic_index_stale_entry", extra={"description": "Index has stale entry for run. File not found. Forcing rescan", "project_name": project_folder.name, "run_id": run_id_to_find, "file_name": filename})
                # The index is outdated, remove the entry and continue with the fallback scan
                del index_data[run_id_to_find]
                await _write_project_index(project_path_str, index_data)

        # 2. Fallback: scan the project folder for .iic files
        logger.debug("iic_run_id_not_in_index", extra={"description": "Run ID not found in index for project. Fallback to FS scan", "run_id": run_id_to_find, "project_name": project_folder.name})
        for iic_file in project_folder.glob("*.iic"):
            if iic_file.is_file():
                try:
                    async with aiofiles.open(iic_file, 'r', encoding='utf-8') as f:
                        # Optimization: only read a small portion of the file header to check for the run_id, avoiding full parsing
                        # Assuming the run_id attribute will be within the first 1024 bytes of the file
                        content_chunk = await f.read(1024) 
                    
                    # Quickly check if the run_id is in the file
                    if f'run_id: {run_id_to_find}' in content_chunk:
                        logger.info("iic_run_id_found_via_scan", extra={"description": "Found match for run via FS scan. Healing index", "run_id": run_id_to_find, "file_name": iic_file.name})
                        
                        # Self-healing: update the index
                        index_data[run_id_to_find] = iic_file.name
                        await _write_project_index(project_path_str, index_data)
                        
                        return str(iic_file.resolve())

                except Exception as e:
                    logger.error("iic_fallback_scan_error", extra={"description": "Error during fallback scan for file", "file_path": str(iic_file), "error": str(e)}, exc_info=False)
            
    return None

def get_iic_dir(project_id: str) -> str:
    """
    Finds and returns the corresponding project directory path based on the project_id.
    If not found, returns the default project path.
    """
    # Handle the default case first
    if not project_id or project_id == DEFAULT_PROJECT:
        return os.path.join(BASE_DIR, DEFAULT_PROJECT)

    try:
        # Iterate over all project directories
        for d in os.listdir(BASE_DIR):
            project_path = os.path.join(BASE_DIR, d)
            iic_file = os.path.join(project_path, "project.iic")

            # Ensure it is a directory and a project.iic file exists
            if os.path.isdir(project_path) and os.path.exists(iic_file):
                with open(iic_file, "r", encoding="utf-8") as f:
                    content = f.read()
                # A quick check can be added here to avoid unnecessary parsing
                if f'project_id: {project_id}' not in content:
                     continue
                blocks = parse_iic(content, to_dict=True)

                for block in blocks:
                    if block["type"] == "meta" and block["attributes"].get("project_id") == project_id:
                        # Found a match, return the correct path immediately
                        return project_path
    except Exception as e:
        # If an error occurs during traversal or file parsing, log it and fall back to the default
        logger.error("iic_project_search_error", extra={"description": "Error while searching for project directory", "project_id": project_id, "error": str(e)}, exc_info=True)
        return os.path.join(BASE_DIR, DEFAULT_PROJECT)

    # If the loop finishes normally without finding any matches, fall back to the default project
    logger.warning("iic_project_not_found_fallback", extra={"description": "Project directory not found. Falling back to default project", "project_id": project_id})
    return os.path.join(BASE_DIR, DEFAULT_PROJECT)

def list_projects():
    """List all projects with parsed attributes and meta information of .iic files."""
    try:
        projects = []
        for d in os.listdir(BASE_DIR):
            # Skip the deleted directory
            if d == DEFAULT_DELETE_DIR:
                continue
            project_path = os.path.join(BASE_DIR, d)
            if not os.path.isdir(project_path):
                continue
            
            # Get all .iic files but exclude those in project's .deleted directory
            iic_files = []
            for item in os.listdir(project_path):
                if item == DEFAULT_DELETE_DIR:
                    continue  # Skip the project's .deleted directory
                item_path = os.path.join(project_path, item)
                if os.path.isfile(item_path) and item.endswith(".iic"):
                    iic_files.append(item)
            
            project_data = {"project": None, "runs": []}
            for iic_file in iic_files:
                iic_path = os.path.join(project_path, iic_file)
                with open(iic_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    blocks = parse_iic(content, to_dict=True)
                    for block in blocks:
                        if block["type"] == "meta":
                            if iic_file == "project.iic":
                                project_data["project"] = block["attributes"]
                            else:
                                project_data["runs"].append({"filename": iic_file, "meta": block["attributes"]})
            if d == DEFAULT_PROJECT and not project_data["project"]:
                project_data["project"] = {
                    "project_id": "default",
                    "name": "Default Project",
                    "created_at": "N/A",
                    "updated_at": "N/A"
                }
            if project_data["project"]:
                projects.append(project_data)
        return projects
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing projects: {str(e)}")

def get_project(project_id: str):
    """Get details of a specific project along with meta information of .iic files."""
    try:
        for d in os.listdir(BASE_DIR):
            project_path = os.path.join(BASE_DIR, d)
            iic_files = [f for f in os.listdir(project_path) if f.endswith(".iic")]
            project_data = {"project": None, "runs": []}
            for iic_file in iic_files:
                iic_path = os.path.join(project_path, iic_file)
                with open(iic_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    blocks = parse_iic(content, to_dict=True)
                    for block in blocks:
                        if block["type"] == "meta":
                            if block["attributes"].get("project_id") == project_id:
                                if iic_file == "project.iic":
                                    project_data["project"] = block["attributes"]
                                else:
                                    project_data["runs"].append({"filename": iic_file, "meta": block["attributes"]})
            if project_data["project"]:
                return project_data
        if project_id == DEFAULT_PROJECT or project_id == "":
            default_project_path = os.path.join(BASE_DIR, DEFAULT_PROJECT)
            iic_files = [f for f in os.listdir(default_project_path) if f.endswith(".iic")]
            project_data = {
                "project": {
                    "project_id": "default",
                    "name": "Default Project",
                    "created_at": "N/A",
                    "updated_at": "N/A"
                },
                "runs": []
            }
            for iic_file in iic_files:
                iic_path = os.path.join(default_project_path, iic_file)
                with open(iic_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    blocks = parse_iic(content, to_dict=True)
                    for block in blocks:
                        if block["type"] == "meta" and iic_file != "project.iic":
                            project_data["runs"].append({"filename": iic_file, "meta": block["attributes"]})
            return project_data
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading project '{project_id}': {str(e)}")

def create_project(name: str):
    """Create a new project directory and project.iic file."""
    project_path = os.path.join(BASE_DIR, name)
    iic_file = os.path.join(project_path, "project.iic")
    if os.path.exists(project_path):
        raise HTTPException(status_code=400, detail=f"Project '{name}' already exists.")
    try:
        os.makedirs(project_path)
        attributes = {
            "project_id": str(uuid.uuid4()),
            "name": name,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        meta_block = IICBlock(type="meta", attributes=attributes, content=None)
        with open(iic_file, "w", encoding="utf-8") as f:
            f.write(meta_block.to_iic())
        
        # Trigger broadcast
        asyncio.create_task(broadcast_project_structure_update("create_project", {"project_id": attributes["project_id"], "name": name}))
        
        return {"message": f"Project '{name}' created successfully.", "data": attributes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating project '{name}': {str(e)}")

def update_project(project_id: str, updates: dict):
    """Update the meta block of a project with the provided key-value pairs."""
    try:
        for d in os.listdir(BASE_DIR):
            project_path = os.path.join(BASE_DIR, d)
            iic_file = os.path.join(project_path, "project.iic")
            if os.path.isdir(project_path) and os.path.exists(iic_file):
                with open(iic_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    blocks = parse_iic(content, to_dict=True)
                updated_blocks = []
                for block in blocks:
                    if block["type"] == "meta" and block["attributes"].get("project_id") == project_id:
                        block["attributes"].update(updates)
                        block["attributes"]["updated_at"] = datetime.now().isoformat()
                    updated_blocks.append(IICBlock(type=block["type"], attributes=block["attributes"], content=block.get("content")))
                with open(iic_file, "w", encoding="utf-8") as f:
                    f.write("\n\n".join(b.to_iic() for b in updated_blocks))
                
                # Trigger broadcast
                asyncio.create_task(broadcast_project_structure_update("update_project", {"project_id": project_id, "updates": updates}))
                
                return {"message": f"Project '{project_id}' updated successfully."}
        raise HTTPException(status_code=404, detail=f"Project with ID '{project_id}' not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating project with ID '{project_id}': {str(e)}")

async def delete_project(project_id: str):
    """Move a project directory to the deleted directory."""
    try:
        # Don't allow deleting the default project
        if project_id == DEFAULT_PROJECT:
            raise HTTPException(status_code=400, detail="Cannot delete the default project.")
        
        for d in os.listdir(BASE_DIR):
            # Skip the deleted directory itself
            if d == DEFAULT_DELETE_DIR:
                continue
            project_path = os.path.join(BASE_DIR, d)
            iic_file = os.path.join(project_path, "project.iic")
            if os.path.isdir(project_path) and os.path.exists(iic_file):
                with open(iic_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    blocks = parse_iic(content, to_dict=True)
                for block in blocks:
                    if block["type"] == "meta" and block["attributes"].get("project_id") == project_id:
                        # Found the project, move it to deleted directory
                        deleted_dir = os.path.join(BASE_DIR, DEFAULT_DELETE_DIR)
                        deleted_project_path = os.path.join(deleted_dir, d)
                        
                        # If a project with the same name already exists in deleted dir, add timestamp
                        if os.path.exists(deleted_project_path):
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            deleted_project_path = os.path.join(deleted_dir, f"{d}_{timestamp}")
                        
                        shutil.move(project_path, deleted_project_path)
                        
                        # Trigger broadcast
                        asyncio.create_task(broadcast_project_structure_update("delete_project", {"project_id": project_id}))
                        
                        return {"message": f"Project '{project_id}' moved to deleted directory successfully."}
        
        raise HTTPException(status_code=404, detail=f"Project with ID '{project_id}' not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting project with ID '{project_id}': {str(e)}")

async def update_run_meta(run_id: str, updates: dict):
    """Update the meta block of a run with the provided key-value pairs."""
    try:
        # Efficiently find the file
        file_path = await find_iic_file_by_run_id(run_id)
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Run with ID '{run_id}' not found.")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        blocks = parse_iic(content, to_dict=True)

        updated_blocks = []
        run_found = False
        for block in blocks:
            if block["type"] == "meta" and block["attributes"].get("run_id") == run_id:
                block["attributes"].update(updates)
                run_found = True
            updated_blocks.append(IICBlock(type=block["type"], attributes=block["attributes"], content=block.get("content")))

        if run_found:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(b.to_iic() for b in updated_blocks))
            
            # Trigger broadcast
            asyncio.create_task(broadcast_project_structure_update("update_run_meta", {"run_id": run_id, "updates": updates}))
            
            return {"message": f"Run '{run_id}' updated successfully."}

        # This part should not be reached if find_iic_file_by_run_id works correctly
        raise HTTPException(status_code=404, detail=f"Run with ID '{run_id}' not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating run '{run_id}': {str(e)}")

async def delete_run(run_id: str):
    """Move a run (.iic file) to the deleted directory within its project and update the index."""
    try:
        file_path = await find_iic_file_by_run_id(run_id)
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Run with ID '{run_id}' not found.")

        project_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)

        # 1. Update the index first
        index_data = await _read_project_index(project_path)
        if run_id in index_data:
            del index_data[run_id]
            await _write_project_index(project_path, index_data)

        # 2. Move the file
        project_deleted_dir = os.path.join(project_path, DEFAULT_DELETE_DIR)
        os.makedirs(project_deleted_dir, exist_ok=True)
        
        deleted_file_path = os.path.join(project_deleted_dir, file_name)
        
        if os.path.exists(deleted_file_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name_without_ext = os.path.splitext(file_name)[0]
            ext = os.path.splitext(file_name)[1]
            deleted_file_path = os.path.join(project_deleted_dir, f"{name_without_ext}_{timestamp}{ext}")
        
        shutil.move(file_path, deleted_file_path)
        
        # Trigger broadcast
        asyncio.create_task(broadcast_project_structure_update("delete_run", {"run_id": run_id}))
        
        return {"message": f"Run '{run_id}' moved to deleted directory successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting run '{run_id}': {str(e)}")

async def update_run_name(run_id: str, new_name: str):
    """Rename a run (.iic file) and update the project index."""
    try:
        display_name_to_store = new_name # Keep original name for meta
        new_name_slug = _slugify(new_name)
        new_filename = f"{new_name_slug}.iic"

        file_path = await find_iic_file_by_run_id(run_id)
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Run with ID '{run_id}' not found.")

        project_path = os.path.dirname(file_path)
        old_filename = os.path.basename(file_path)
        new_file_path = os.path.join(project_path, new_filename)

        # If the name is unchanged, do nothing.
        if old_filename == new_filename:
            return {"message": "Run name is already set to the new name.", "old_filename": old_filename, "new_filename": new_filename}

        if os.path.exists(new_file_path):
            raise HTTPException(
                status_code=409, 
                detail=f"A file named '{new_filename}' already exists in the project."
            )

        # 1. Update the index
        index_data = await _read_project_index(project_path)
        if run_id in index_data:
            index_data[run_id] = new_filename
            await _write_project_index(project_path, index_data)
        
        # 2. Update meta inside the file BEFORE renaming
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        blocks = parse_iic(content, to_dict=False) # Get IICBlock objects

        for block in blocks:
             if block.type == "meta" and block.attributes.get("run_id") == run_id:
                block.attributes["display_name"] = display_name_to_store
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(b.to_iic() for b in blocks))

        # 3. Rename the file
        os.rename(file_path, new_file_path)
        
        # Trigger broadcast
        asyncio.create_task(broadcast_project_structure_update("rename_run", {"run_id": run_id, "new_name": new_name}))
        
        return {
            "message": f"Run '{run_id}' renamed from '{old_filename}' to '{new_filename}' successfully.",
            "old_filename": old_filename,
            "new_filename": new_filename
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error renaming run '{run_id}': {str(e)}")

async def move_iic(run_id: str, from_project_id: str, to_project_id: str):
    """Move a run (.iic file) from one project to another, updating indexes and filesystem location."""
    try:
        # 1. Find source file and project path
        source_file_path = await find_iic_file_by_run_id(run_id)
        if not source_file_path:
            raise HTTPException(status_code=404, detail=f"Run with ID '{run_id}' not found.")
        
        source_project_path = get_iic_dir(from_project_id)
        if not os.path.samefile(os.path.dirname(source_file_path), source_project_path):
             raise HTTPException(status_code=404, detail=f"Run with ID '{run_id}' not found in project '{from_project_id}'.")

        # 2. Find destination project path
        dest_project_path = get_iic_dir(to_project_id)
        if not dest_project_path or not os.path.isdir(dest_project_path):
            raise HTTPException(status_code=404, detail=f"Destination project with ID '{to_project_id}' not found.")

        source_file_name = os.path.basename(source_file_path)
        
        # 3. Handle potential file name conflicts in destination
        dest_file_path = os.path.join(dest_project_path, source_file_name)
        new_file_name = source_file_name
        if os.path.exists(dest_file_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name_without_ext, ext = os.path.splitext(source_file_name)
            new_file_name = f"{name_without_ext}_{timestamp}{ext}"
            dest_file_path = os.path.join(dest_project_path, new_file_name)

        # 4. Update indexes (atomically)
        # From source
        source_index = await _read_project_index(source_project_path)
        if run_id in source_index:
            source_index.pop(run_id)
            await _write_project_index(source_project_path, source_index)

        # To destination
        dest_index = await _read_project_index(dest_project_path)
        dest_index[run_id] = new_file_name
        await _write_project_index(dest_project_path, dest_index)

        # 5. Move the file
        shutil.move(source_file_path, dest_file_path)
        
        # 6. (Optional but good practice) Update meta inside the moved file
        with open(dest_file_path, "r", encoding="utf-8") as f:
            content = f.read()
        blocks = parse_iic(content) # get IICBlock objects
        
        updated = False
        for block in blocks:
            if block.type == "meta" and block.attributes.get("run_id") == run_id:
                block.attributes["project_id"] = to_project_id # Update project_id
                block.attributes["moved_from"] = from_project_id
                block.attributes["moved_to"] = to_project_id
                block.attributes["moved_at"] = datetime.now().isoformat()
                updated = True
        
        if updated:
            with open(dest_file_path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(b.to_iic() for b in blocks))
        
        # Trigger broadcast
        asyncio.create_task(broadcast_project_structure_update("move_run", {"run_id": run_id, "to_project_id": to_project_id}))

        return {
            "message": f"Run '{run_id}' moved from project '{from_project_id}' to project '{to_project_id}' successfully.",
            "old_filename": source_file_name,
            "new_filename": new_file_name,
            "source_project": from_project_id,
            "destination_project": to_project_id
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error moving run: {str(e)}")

async def persist_initial_run_state(run_context: Dict[str, Any]):
    """
    Handles the initial persistence of a run's state right after its creation.
    This includes creating the .iic and .json files and updating the project index.
    """
    run_id = run_context.get("meta", {}).get("run_id")
    project_id = run_context.get("project_id", "default")
    
    if not run_id:
        logger.error("iic_persist_run_id_missing", extra={"description": "Cannot persist, run_id is missing from context"})
        return

    logger.info("iic_initial_persistence_begin", extra={"description": "Performing initial persistence for new run", "run_id": run_id})

    try:
        # Determine paths
        project_path = get_iic_dir(project_id)
        # Use run_id for both .iic and .json initially. Naming can be changed later.
        filename = f"{run_id}.iic"
        iic_path = os.path.join(project_path, filename)
        json_path = os.path.join(project_path, f"{run_id}.json")

        # Update project index
        index_data = await _read_project_index(project_path)
        if run_id not in index_data:
            index_data[run_id] = filename
            await _write_project_index(project_path, index_data)
            logger.debug("iic_run_added_to_index", extra={"description": "Added run to project index", "run_id": run_id, "file_name": filename, "project_id": project_id})

        # Save state and minimal .iic file
        # These helpers need to be defined or imported here. Let's define them locally for now.
        async def _save_run_state(context: dict, path: str):
            from ...utils.serialization import get_serializable_run_snapshot
            snapshot_data = get_serializable_run_snapshot(context)
            async with aiofiles.open(path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(snapshot_data, ensure_ascii=False, indent=2))
            logger.debug("iic_run_state_snapshot_saved", extra={"description": "Initial run state snapshot saved", "path": path})

        async def _save_minimal_iic_file(context: dict, path: str):
            meta_info = context.get("meta", {})
            root_block = IICBlock(
                type="meta",
                attributes={
                    "run_id": meta_info.get("run_id"),
                    "project_id": context.get("project_id", "default"),
                    "run_type": meta_info.get("run_type"),
                    "created": meta_info.get("creation_timestamp"),
                },
                content=""
            )
            async with aiofiles.open(path, 'w', encoding='utf-8') as f:
                await f.write(root_block.to_iic())
            logger.debug("iic_minimal_metadata_saved", extra={"description": "Initial minimal IIC metadata file saved", "path": path})

        await _save_run_state(run_context, json_path)
        await _save_minimal_iic_file(run_context, iic_path)
        
        logger.info("iic_initial_persistence_complete", extra={"description": "Successfully performed initial persistence for run", "run_id": run_id})

    except Exception as e:
        logger.error("iic_initial_persistence_failed", extra={"description": "Failed during initial persistence for run", "run_id": run_id, "error": str(e)}, exc_info=True)
        # We don't re-raise here to avoid crashing the run creation process.
        # The error is logged.
