# File path: nodes/custom_nodes/stage_planner_node.py (Refactored)

import logging
from typing import Dict, Any, List
from datetime import datetime, timezone
import copy

# Import the new base class
from ..base_tool_node import BaseToolNode
from ...framework.tool_registry import tool_registry

logger = logging.getLogger(__name__)

# The _apply_work_module_actions helper function remains unchanged as it doesn't belong to the node itself
async def _apply_work_module_actions(team_state: Dict[str, Any], actions: List[Dict]) -> Dict[str, Any]:
    # ... (The implementation of this function remains unchanged) ...
    if "work_modules" not in team_state or not isinstance(team_state["work_modules"], dict):
        team_state["work_modules"] = {}
    work_modules_copy = copy.deepcopy(team_state["work_modules"])
    action_results = []
    for i, action_item in enumerate(actions):
        action_type = action_item.get("action")
        module_id = action_item.get("module_id")
        try:
            if action_type == "create":
                # Get and increment the work module ID counter from team_state
                next_id = team_state.get("_work_module_next_id", 1)
                new_module_id = f"WM_{next_id}"
                team_state["_work_module_next_id"] = next_id + 1
                
                if not action_item.get("name") or not action_item.get("description"):
                    raise ValueError("'name' and 'description' are required for 'create' action.")
                work_modules_copy[new_module_id] = { "module_id": new_module_id, "name": action_item["name"], "description": action_item["description"], "status": "pending", "notes_from_principal": action_item.get("notes_from_principal", ""), "deliverables": [], "context_archive": [], "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat() }
                action_results.append({"action": "create", "status": "success", "module_id": new_module_id})
            elif action_type in ["update", "status_change"]:
                if not module_id or module_id not in work_modules_copy:
                    raise ValueError(f"Module with id '{module_id}' not found for '{action_type}' action.")
                module_to_update = work_modules_copy[module_id]
                if action_type == "update":
                    if "name" in action_item: module_to_update["name"] = action_item["name"]
                    if "description" in action_item: module_to_update["description"] = action_item["description"]
                    if "notes_from_principal" in action_item: module_to_update["notes_from_principal"] = action_item["notes_from_principal"]
                if action_type == "status_change":
                    new_status = action_item.get("new_status")
                    if not new_status: raise ValueError("'new_status' is required for 'status_change' action.")
                    module_to_update["status"] = new_status
                module_to_update["updated_at"] = datetime.now(timezone.utc).isoformat()
                action_results.append({"action": action_type, "status": "success", "module_id": module_id})
            else:
                raise ValueError(f"Unknown action type: '{action_type}'")
        except Exception as e:
            logger.error("work_module_action_failed", extra={"action_index": i, "action_type": action_type, "error": str(e)}, exc_info=True)
            return { "overall_status": "failure", "status_message": f"Failed on action {i} ({action_type}): {e}", "final_work_modules": team_state["work_modules"], "action_results": action_results }
    team_state["work_modules"] = work_modules_copy
    return { "overall_status": "success", "status_message": f"Successfully applied {len(actions)} actions.", "final_work_modules": work_modules_copy, "action_results": action_results }


@tool_registry(
    name="manage_work_modules",
    description="Manages the project's work modules. Allows creating, updating, and changing the status of modules that define the overall plan.",
    parameters={
        "type": "object",
        "properties": {
            "actions": {
                "type": "array",
                "description": "A list of actions to perform on the work modules.",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": { "type": "string", "enum": ["create", "update", "status_change"], "description": "The type of action to perform." },
                        "module_id": { "type": "string", "description": "The ID of the module to update or change status for. Not used for 'create'." },
                        "name": {"type": "string", "description": "The name of the module. Required for 'create'."},
                        "description": {"type": "string", "description": "The description of the module. Required for 'create'."},
                        "notes_from_principal": {"type": "string", "description": "Additional notes for the module."},
                        "new_status": { "type": "string", "enum": ["pending", "in_progress", "pending_review", "completed", "deprecated"], "description": "The new status for the module. Required for 'status_change'." }
                    },
                    "required": ["action"]
                }
            }
        },
        "required": ["actions"]
    },
    toolset_name="planning_tools"
)
class StagePlannerNode(BaseToolNode):
    """
    A tool node for managing the plan (work modules) in the team_state.
    This node now inherits from BaseToolNode, simplifying its implementation.
    """
    
    # The prep_async and post_async methods have been removed as their functionality is provided by BaseToolNode.

    async def exec_async(self, prep_res: Dict) -> Dict[str, Any]:
        """
        Applies actions to work modules. This is the core logic of the tool.
        It directly modifies team_state, which is a valid side-effect for this specific tool.
        """
        # 1. Safely get the required data from prep_res provided by the base class
        tool_params = prep_res.get("tool_params", {})
        shared_context = prep_res.get("shared_context", {})
        
        actions = tool_params.get("actions")
        if not actions or not isinstance(actions, list):
            return {"status": "error", "error_message": "The 'actions' parameter is required and must be a list."}

        # 2. Access team_state (path is clear)
        team_state = shared_context.get('refs', {}).get('team')
        if not team_state:
             return {"status": "error", "error_message": "Critical error: team_state not found in context."}

        # 3. Execute the core business logic (directly modifying team_state)
        update_result = await _apply_work_module_actions(team_state, actions)

        # 4. Return a standardized result according to the base class contract
        if update_result.get("overall_status") == "failure":
            return {
                "status": "error", 
                "error_message": update_result.get("status_message", "Unknown error during work module update.")
            }

        # 5. On success, generate the payload to be returned to the LLM
        updated_modules = update_result.get("final_work_modules", {})
        pending_count = sum(1 for m in updated_modules.values() if m.get('status') == 'pending')
        ongoing_count = sum(1 for m in updated_modules.values() if m.get('status') == 'in_progress')
        review_count = sum(1 for m in updated_modules.values() if m.get('status') == 'pending_review')
        completed_count = sum(1 for m in updated_modules.values() if m.get('status') == 'completed')

        summary_for_llm = (
            "The project plan (Work Modules) has been successfully updated. "
            f"Current status: {pending_count} pending, {ongoing_count} ongoing, "
            f"{review_count} pending review, {completed_count} completed."
        )

        return {
            "status": "success",
            "payload": {
                "summary": summary_for_llm
            }
        }
