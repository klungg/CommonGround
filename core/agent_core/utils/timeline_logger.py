import logging
from datetime import datetime, timezone
from typing import Dict, Any

from ..events.event_triggers import trigger_view_model_update

logger = logging.getLogger(__name__)

async def log_tool_execution_start(
    context: Dict[str, Any], 
    tool_call_id: str, 
    tool_name: str, 
    agent_id: str
):
    """
    Logs the start of a tool execution in team_state['execution_history'].
    """
    # Do not log if the tool is dispatch_submodules
    if tool_name == "dispatch_submodules":
        return
        
    try:
        team_state = context['refs']['team'] # New code
        if "execution_history" not in team_state or not isinstance(team_state.get("execution_history"), list):
            team_state["execution_history"] = []
        
        history_entry = {
            "type": "tool_execution",
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "agent_id": agent_id,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": None,
            "status": "running"
        }
        team_state["execution_history"].append(history_entry)
        logger.info("tool_execution_start_logged", extra={"agent_id": agent_id, "tool_name": tool_name, "tool_call_id": tool_call_id})
        
        # Trigger a view model update to let the frontend know the tool has started
        await trigger_view_model_update(context, "timeline_view")

    except Exception as e:
        logger.error("tool_execution_start_log_failed", extra={"tool_name": tool_name, "error": str(e)}, exc_info=True)


async def log_tool_execution_end(
    agent_context: Dict[str, Any],
    agent_id_for_event: str
):
    """
    [DEPRECATED] This function is deprecated. Tool execution status is now tracked
    within the `Turn` model's `tool_interactions` field. This function is a no-op.
    """
    logger.warning("`log_tool_execution_end` is deprecated and should not be called. Tool status is tracked in the Turn model.")
    return


async def log_tool_execution_end_fallback(agent_context: Dict[str, Any]):
    """
    A fallback function called at the end of a flow to close any tool logs that are still in a 'running' state.
    This is mainly for handling tools that end the flow (like finish_flow), which do not trigger the existing `log_tool_execution_end`.
    """
    agent_id = agent_context.get("state", {}).get("agent_id")
    team_state = agent_context['refs']['team'] # New code
    execution_history = team_state.get("execution_history", [])

    if not agent_id or not isinstance(execution_history, list):
        return

    # Find all 'running' tool entries initiated by this agent, searching backwards
    entries_to_update = [
        entry for entry in reversed(execution_history)
        if entry.get("type") == "tool_execution" and entry.get("agent_id") == agent_id and entry.get("status") == "running"
    ]

    if not entries_to_update:
        return

    logger.info("fallback_logger_closing_running_tools", extra={"agent_id": agent_id, "entries_count": len(entries_to_update)})
    
    end_time = datetime.now(timezone.utc).isoformat()
    needs_update = False
    for entry in entries_to_update:
        entry["end_time"] = end_time
        entry["status"] = "completed" # Assume normal completion
        needs_update = True
        logger.info("fallback_logger_tool_closed", extra={"agent_id": agent_id, "tool_name": entry.get('tool_name'), "tool_call_id": entry.get('tool_call_id')})

    if needs_update:
        await trigger_view_model_update(agent_context, "timeline_view")
