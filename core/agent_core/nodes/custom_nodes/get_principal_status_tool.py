import logging
from typing import Dict
from pocketflow import AsyncNode
from ...framework.tool_registry import tool_registry
from datetime import datetime, timezone
import uuid

logger = logging.getLogger(__name__)

@tool_registry(
    name="GetPrincipalStatusSummaryTool",
    description="Retrieves the current execution status summary and recent milestones of the Principal Agent. Use this to monitor progress.",
    parameters={"type": "object", "properties": {}}, # No parameters needed from LLM
    toolset_name="monitoring_tools" 
)
class GetPrincipalStatusSummaryTool(AsyncNode):
    """
    A tool for the Partner Agent to get the status summary and milestones 
    from the Principal Agent's shared state.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # self.agent_id will be Partner's ID when this tool is run by Partner

    async def prep_async(self, partner_context: Dict) -> Dict:
        """
        Preparation step. No specific input needed from LLM for this tool.
        We need to access the parent run_context to get the principal_context.
        """
        # partner_context is Partner's SubContext.
        run_ctx_global = partner_context['refs']['run'] # Access global RunContext
        if not run_ctx_global:
            return {"error": "Critical: Global RunContext not found in Partner's SubContext refs."}
        
        principal_sub_context_ref = run_ctx_global['sub_context_refs'].get("_principal_context_ref")
        # principal_flow_task_handle is stored in the RunContext.runtime
        principal_flow_task_handle = run_ctx_global['runtime'].get("principal_flow_task_handle")

        return {
            "principal_sub_context_ref": principal_sub_context_ref, # Pass Principal's SubContext
            "principal_flow_task_handle": principal_flow_task_handle,
            "partner_sub_context_ref": partner_context # Pass Partner's SubContext
        }

    async def exec_async(self, prep_res: Dict) -> Dict:
        """
        Execution step: Read status from principal_context.
        """
        if "error" in prep_res:
            return {"status": "error", "summary": prep_res["error"], "milestones_summary": "Error accessing shared context."}

        principal_sub_context = prep_res.get("principal_sub_context_ref") # This is Principal's SubContext
        principal_task_handle = prep_res.get("principal_flow_task_handle")
        
        # Access team_state from partner_sub_context's refs
        partner_sub_context = prep_res.get("partner_sub_context_ref")
        team_state_global = partner_sub_context['refs']['team'] if partner_sub_context else None

        if not team_state_global:
            return {"status": "error", "summary": "Critical: Global TeamState not found via Partner's SubContext.", "detailed_report": {"error": "TeamState missing."}}

        is_principal_running_in_team_state = team_state_global.get("is_principal_flow_running", False)

        if not principal_sub_context:
            status_summary = "Principal Agent context has not been initialized yet."
            if not is_principal_running_in_team_state and principal_task_handle and principal_task_handle.done():
                status_summary = "Principal Agent is not currently active (task completed or never fully started, context may be cleared)."
            elif not is_principal_running_in_team_state:
                 status_summary = "Principal Agent is not currently active (based on team_state flag)."
            return {"status": "principal_not_active_or_initialized", "summary": status_summary, "detailed_report": {"error": status_summary, "is_principal_flow_running_in_team_state": is_principal_running_in_team_state}}

        principal_private_state = principal_sub_context["state"] # Principal's private state
        if not principal_private_state:
            return {"status": "error", "summary": "Principal Agent context is invalid (missing 'state').", "detailed_report": {"error": "Principal state invalid.", "is_principal_flow_running_in_team_state": is_principal_running_in_team_state}}
        
        principal_messages = principal_private_state.get("messages", [])
        # Principal's plan (now work_modules) is read from its refs.team (which is team_state_global)
        principal_work_modules = principal_sub_context['refs']['team'].get("work_modules", {})


        # 1. Determine Principal Task Running Status (from task handle, to be reconciled with team_state)
        principal_task_handle_status_text = "Principal Task Handle Status: Unknown"
        if principal_task_handle:
            if principal_task_handle.done():
                if principal_task_handle.cancelled():
                    principal_task_handle_status_text = "Principal Task Handle Status: Cancelled"
                elif principal_task_handle.exception():
                    exc = principal_task_handle.exception()
                    principal_task_handle_status_text = f"Principal Task Handle Status: Failed with error: {type(exc).__name__}"
                else:
                    principal_task_handle_status_text = "Principal Task Handle Status: Completed Successfully"
            else:
                principal_task_handle_status_text = "Principal Task Handle Status: Running"
        else:
            principal_task_handle_status_text = "Principal Task Handle Status: Not launched or handle unavailable"
        
        # Effective running status text based on team_state
        effective_principal_running_status_text = f"Principal Effective Status (from team_state): {'Running' if is_principal_running_in_team_state else 'Not Running'}"


        # 2. Infer if Principal is "Marked Complete" (e.g., finish_flow was called)
        is_marked_complete = False
        # If not running according to team_state, and task handle also shows done without error/cancel, then likely complete.
        if not is_principal_running_in_team_state and principal_task_handle and principal_task_handle.done() and \
           not principal_task_handle.cancelled() and not principal_task_handle.exception():
            is_marked_complete = True
        
        # More robust check: iterate messages for finish_flow tool call and success
        for msg_idx, msg in enumerate(reversed(principal_messages)):
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    if tc.get("function", {}).get("name") == "finish_flow":
                        # Check for corresponding successful tool response
                        # This requires looking ahead or assuming success if no error
                        is_marked_complete = True # Simplified assumption for now
                        break
            if is_marked_complete or msg_idx > 5: # Limit search depth
                break
        is_principal_marked_complete_text = f"Principal Marked Complete: {'Yes' if is_marked_complete else 'No (inferred)'}"


        # 3. Format Full Message History
        full_message_history_parts = []
        if principal_messages:
            for msg_idx, msg in enumerate(principal_messages): # Iterate over ALL messages
                role = msg.get("role", "unknown")
                content = msg.get("content")
                tool_calls = msg.get("tool_calls")
                tool_name_resp = msg.get("name") # For role: tool

                part = f"  - Msg {msg_idx + 1} [{role.upper()}]" # Adjusted message numbering
                if tool_name_resp:
                    part += f" (Tool: {tool_name_resp})"
                
                if content:
                    part += f": {str(content)}" # Use full content
                
                if tool_calls:
                    tools_called_str = ", ".join([tc.get("function",{}).get("name","N/A") for tc in tool_calls])
                    part += f" -> Calls tool(s): [{tools_called_str}]"
                full_message_history_parts.append(part)
        
        full_message_history_text = "Full Principal Message History:\n" + "\n".join(full_message_history_parts) if full_message_history_parts else "Full Principal Message History:\n  No messages recorded."

        # 4. Format Work Modules
        work_modules_summary_parts = ["Principal's Current Work Modules (from team_state):"]
        if principal_work_modules and isinstance(principal_work_modules, dict):
            for module_id, module_data in principal_work_modules.items():
                module_name = module_data.get('name', 'Unnamed Module')
                module_status = module_data.get('status', 'unknown')
                module_desc_snippet = module_data.get('description', 'No description')[:50] + "..."
                work_modules_summary_parts.append(f"  - Module ID: {module_id}, Name: {module_name}, Status: {module_status}, Desc: {module_desc_snippet}")
            if not principal_work_modules: # Empty dict
                work_modules_summary_parts.append("  No work modules defined.")
        else:
            work_modules_summary_parts.append("  No work modules available or format is incorrect.")
        work_modules_summary_text = "\n".join(work_modules_summary_parts)

        # 5. Combine for summary_for_llm
        summary_for_llm = f"{effective_principal_running_status_text}\n{principal_task_handle_status_text}\n{is_principal_marked_complete_text}\n{work_modules_summary_text}\n{full_message_history_text}"
        
        # 6. Prepare detailed_report
        detailed_report = {
            "task_handle_status_raw": str(principal_task_handle),
            "principal_task_handle_status_text": principal_task_handle_status_text,
            "is_principal_flow_running_in_team_state": is_principal_running_in_team_state, # Key for syncing
            "effective_principal_running_status_text": effective_principal_running_status_text,
            "is_principal_marked_complete_text": is_principal_marked_complete_text,
            "message_count": len(principal_messages),
            "work_modules_snapshot_from_team_state_raw": principal_work_modules, # Changed from plan_snapshot
            "full_message_history_raw": principal_messages,
        }

        return {
            "status": "success", 
            "summary_for_llm": summary_for_llm, 
            "detailed_report": detailed_report,
            "ATTENTION": "DO NOT call this tool again in your next turn, unless user explicitly asks for update. This tool is designed to be called once a while, not every turn.",
        }

    async def post_async(self, partner_context: Dict, prep_res: Dict, exec_res: Dict):
        """
        Places the result into the Partner's inbox.
        Also, reconciles team_state.is_principal_flow_running based on the findings.
        """
        partner_private_state = partner_context["state"]
        tool_name = self._tool_info["name"]
        team_state_global = partner_context['refs']['team']
        is_error = exec_res.get("status") != "success"
        
        # --- Inbox Migration ---
        tool_result_payload = {
            "tool_name": tool_name,
            "tool_call_id": partner_private_state.get('current_tool_call_id'),
            "is_error": is_error,
            "content": exec_res
        }

        partner_private_state.setdefault('inbox', []).append({
            "item_id": f"inbox_{uuid.uuid4().hex[:8]}",
            "source": "TOOL_RESULT",
            "payload": tool_result_payload,
            "consumption_policy": "consume_on_read",
            "metadata": {"created_at": datetime.now(timezone.utc).isoformat()}
        })
        logger.info("tool_result_placed_in_inbox", extra={"agent_id": partner_context['meta'].get('agent_id'), "tool_name": tool_name})
        # --- End Inbox Migration ---

        if not is_error:
            detailed_report = exec_res.get("detailed_report", {})
            
            # Reconcile team_state.is_principal_flow_running
            if team_state_global:
                new_flag_value_based_on_report = False
                task_handle_status_text = detailed_report.get("principal_task_handle_status_text", "")
                
                if "Running" in task_handle_status_text:
                    new_flag_value_based_on_report = True
                
                current_team_state_flag = team_state_global.get("is_principal_flow_running")
                
                if current_team_state_flag != new_flag_value_based_on_report:
                    team_state_global["is_principal_flow_running"] = new_flag_value_based_on_report
                    logger.info("team_state_reconciled", extra={"agent_id": partner_context['meta'].get('agent_id'), "new_flag_value": new_flag_value_based_on_report, "task_handle_status": task_handle_status_text, "old_value": current_team_state_flag})
                else:
                    logger.info("team_state_confirmed", extra={"agent_id": partner_context['meta'].get('agent_id'), "current_flag": current_team_state_flag, "task_handle_status": task_handle_status_text})
            else:
                logger.error("team_state_access_failed", extra={"agent_id": partner_context['meta'].get('agent_id')})
        else:
            error_message = exec_res.get("summary", "Unknown error fetching Principal status.")
            logger.error("tool_failed", extra={"agent_id": partner_context['meta'].get('agent_id'), "tool_name": tool_name, "error_message": error_message})
        
        partner_private_state["current_action"] = None
        return "default"
