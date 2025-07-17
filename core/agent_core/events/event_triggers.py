import logging
from typing import Dict

# Late import to avoid circular dependency
# from .view_model_generator import generate_view_model

logger = logging.getLogger(__name__)

# --- Start of modification: Rename and simplify old function ---
async def trigger_view_model_update(context: Dict, view_name: str):
    """
    Generates a view model and pushes it to the client via WebSocket.
    This function is robust and can accept either a full run_context 
    or a sub-context (like principal_context) that contains a 'run_context_ref'.
    """
    if not context:
        logger.warning("view_model_update_no_context")
        return
    
    # --- START OF FIX ---
    # 1. Determine the real run_context
    actual_run_context = None
    # Heuristic: If it has 'meta', 'config', 'team_state', 'runtime', and 'sub_context_refs' at the top level, it's likely the RunContext.
    if "meta" in context and "config" in context and "team_state" in context and "runtime" in context and "sub_context_refs" in context:
        actual_run_context = context
    # If it has 'refs' and 'run' inside 'refs', it's a SubContext.
    elif "refs" in context and "run" in context.get("refs", {}): # Safe access to "refs"
        actual_run_context = context.get("refs", {}).get("run")
    
    if not actual_run_context:
        # Try to get run_id from meta for logging, if context is a SubContext
        run_id_for_log = context.get("meta", {}).get("run_id", "Unknown")
        logger.error("view_model_update_context_resolution_failed", extra={"run_id": run_id_for_log})
        return
    # --- END OF FIX ---
        
    events = actual_run_context.get("runtime", {}).get("event_manager") # Access via runtime namespace
    if not events:
        run_id_for_log = actual_run_context.get("meta", {}).get("run_id", "Unknown") # Access run_id via meta
        logger.warning("view_model_update_event_manager_missing", extra={"run_id": run_id_for_log})
        return

    run_id = actual_run_context.get("meta", {}).get("run_id") # Access run_id via meta
    model = None
    try:
        from ..utils.view_model_generator import generate_view_model
        
        # 2. Always pass the real run_context to the generator
        model = await generate_view_model(actual_run_context, view_name)
        
        await events.send_json(
            run_id=run_id,
            message={
                "type": "view_model_update",
                "data": {"view_name": view_name, "model": model}
            }
        )
        if model and (model.get("nodes") or model.get("edges")): # Ensure to check if model is None
            logger.info("view_model_update_success", extra={
                "view_name": view_name,
                "run_id": run_id,
                "node_count": len(model.get('nodes', [])),
                "edge_count": len(model.get('edges', []))
            })
        elif model is not None: # model exists but is empty
            logger.debug("view_model_update_empty_model", extra={"view_name": view_name, "run_id": run_id})
        # If model is None (e.g., events.send_json failed before generate_view_model threw an exception), do not log success or empty model. The error is handled below.

    except Exception as e:
        logger.error("view_model_update_failed", extra={
            "view_name": view_name,
            "run_id": run_id,
            "error": str(e)
        }, exc_info=True)
        await events.send_json(
            run_id=run_id,
            message={
                "type": "view_model_update_failed",
                "data": {"view_name": view_name, "error": str(e)}
            }
        )
# --- End of modification ---


# --- trigger_turns_sync function has been removed, its functionality is integrated into SessionEventManager.emit_turns_sync ---
# async def trigger_turns_sync(context: Dict):
#     """Dedicated to sending turns_sync events."""
#     run_context = context.get("run_context_ref", context)
#     events = run_context.get("event_manager_ref")
#     run_id = run_context.get("run_id")
#     team_state = run_context.get("team_state", {})
#     turns = team_state.get("turns", [])

#     if events and run_id:
#         try:
#             await events.send_json(
#                 run_id=run_id,
#                 message={"type": "turns_sync", "data": {"turns": turns}}
#             )
#             logger.debug(f"Sent turns_sync event for run {run_id} with {len(turns)} turns.")
#         except Exception as e:
#             logger.error(f"Failed to send turns_sync event for run {run_id}: {e}", exc_info=True)
# --- End of new function ---
