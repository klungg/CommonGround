import logging
from typing import Dict, Any
import uuid
from datetime import datetime, timezone
from pocketflow import AsyncNode
from ...framework.tool_registry import tool_registry

logger = logging.getLogger(__name__)

@tool_registry(
    name="SendDirectiveToPrincipalTool",
    description="Sends a directive or new information from the user (via Partner) to the currently running Principal Agent. Use this to provide updates, clarifications, or new instructions to the Principal.",
    parameters={
        "type": "object",
        "properties": {
            "directive_type": {
                "type": "string",
                "description": "The type of directive. Examples: 'ADD_CONTEXT', 'USER_QUERY_FOR_PRINCIPAL', 'MODIFY_SUB_TASK'.",
                "enum": ["ADD_CONTEXT", "USER_QUERY_FOR_PRINCIPAL", "MODIFY_SUB_TASK"]
            },
            "payload": {
                "type": "object",
                "description": "The content of the directive.",
                "properties": {
                    "user_facing_message_for_principal": {
                        "type": "string",
                        "description": "The message, query, or instruction to be passed to the Principal Agent, as if it came directly from a user or is a summary of user's intent."
                    },
                    "target_task_id": {
                        "type": "string",
                        "description": "Optional: If the directive targets a specific task in the Principal's plan, provide its ID."
                    },
                    "internal_notes_for_principal_llm": {
                        "type": "string",
                        "description": "Optional: Internal notes or context for the Principal's LLM, not necessarily for direct display or verbatim use in its plan."
                    }
                },
                "required": ["user_facing_message_for_principal"]
            }
        },
        "required": ["directive_type", "payload"]
    },
    toolset_name="intervention_tools" # New toolset for clarity
)
class SendDirectiveToPrincipalTool(AsyncNode):
    """
    A tool for the Partner Agent to send directives to the Principal Agent.
    """

    async def prep_async(self, partner_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepares parameters for exec_async.
        'partner_context' is the context of the calling Partner Agent.
        Tool input arguments are retrieved from partner_context["state"]["current_action"].
        """
        current_action_data = partner_context["state"].get("current_action")

        if current_action_data is None or current_action_data.get("type") != "SendDirectiveToPrincipalTool":
            logger.error("current_action_not_found_or_type_mismatch", extra={"expected_type": "SendDirectiveToPrincipalTool", "got_type": current_action_data.get('type') if current_action_data else 'None'})
            return {"_prep_error": True, "message": "Internal configuration error: Tool input arguments not found or type mismatch for SendDirectiveToPrincipalTool."}

        tool_input_args = current_action_data
        run_context_global = partner_context['refs']['run']
        if not run_context_global:
            logger.error("SendDirectiveToPrincipalTool (prep_async): Global RunContext not found in Partner's SubContext refs.")
            return {"_prep_error": True, "message": "Internal configuration error: Global RunContext not found."}
            
        return {
            "run_context_global": run_context_global,
            "directive_input_from_llm": tool_input_args 
        }

    async def exec_async(self, prepared_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the tool to send a directive using prepared parameters.
        'prepared_params' is the dictionary returned by prep_async.
        """
        if prepared_params.get("_prep_error"):
            return {"status": "error", "message": prepared_params.get("message", "Error during prep_async.")}

        run_context_global = prepared_params.get("run_context_global")
        directive_input = prepared_params.get("directive_input_from_llm")

        if not run_context_global or not directive_input:
            logger.error("SendDirectiveToPrincipalTool (exec_async): Missing global RunContext or directive_input in prepared_params.")
            return {"status": "error", "message": "Internal error: Invalid parameters from prep_async."}

        principal_sub_context_ref = run_context_global['sub_context_refs'].get("_principal_context_ref")
        principal_flow_task_handle = run_context_global['runtime'].get("principal_flow_task_handle")

        if not principal_sub_context_ref or not principal_flow_task_handle or principal_flow_task_handle.done():
            status_message = "Principal Agent is not active or has completed its execution. Cannot send directive."
            if principal_flow_task_handle and principal_flow_task_handle.done():
                 if principal_flow_task_handle.cancelled():
                     status_message = "Principal Agent's task was cancelled. Cannot send directive."
                 elif principal_flow_task_handle.exception():
                     status_message = f"Principal Agent's task failed with an error: {principal_flow_task_handle.exception()}. Cannot send directive."
            logger.warning("principal_not_active", extra={"status_message": status_message})
            return {"status": "error", "message": status_message}

        # --- Inbox Migration ---
        principal_state = principal_sub_context_ref.get("state")
        if not isinstance(principal_state, dict):
            logger.error("SendDirectiveToPrincipalTool (exec_async): Principal's state is invalid or not found.")
            return {"status": "error", "message": "Internal configuration error: Principal's state is invalid."}

        try:
            inbox_item = {
                "item_id": f"inbox_{uuid.uuid4().hex[:8]}",
                "source": "PARTNER_DIRECTIVE",
                "payload": directive_input,
                "consumption_policy": "consume_on_read",
                "metadata": {"created_at": datetime.now(timezone.utc).isoformat()}
            }
            principal_state.setdefault("inbox", []).append(inbox_item)
            # --- End Inbox Migration ---

            logger.info("directive_sent_successfully", extra={"directive_type": directive_input.get('directive_type')})
            return {"status": "directive_sent", "message": f"Directive of type '{directive_input.get('directive_type')}' has been sent to the Principal Agent."}
        except Exception as e:
            logger.error("directive_append_failed", extra={"error": str(e)}, exc_info=True)
            return {"status": "error", "message": f"Failed to send directive: {str(e)}"}

    async def post_async(self, partner_context: Dict, prep_res: Dict, exec_res: Dict) -> str:
        """
        Places the result into the Partner's inbox.
        """
        partner_state = partner_context["state"]
        agent_id_for_log = partner_context['meta'].get('agent_id', 'UnknownAgent')
        is_error = exec_res.get("status") != "directive_sent"

        # --- Inbox Migration ---
        tool_result_payload = {
            "tool_name": "SendDirectiveToPrincipalTool",
            "tool_call_id": partner_state.get('current_tool_call_id'),
            "is_error": is_error,
            "content": exec_res
        }

        partner_state.setdefault('inbox', []).append({
            "item_id": f"inbox_{uuid.uuid4().hex[:8]}",
            "source": "TOOL_RESULT",
            "payload": tool_result_payload,
            "consumption_policy": "consume_on_read",
            "metadata": {"created_at": datetime.now(timezone.utc).isoformat()}
        })
        # --- End Inbox Migration ---

        if not is_error:
            logger.info("directive_sent_to_principal", extra={"agent_id": agent_id_for_log, "result": exec_res.get('message')})
        else:
            logger.warning("directive_send_failed", extra={"agent_id": agent_id_for_log, "error": exec_res.get('message')})
        
        partner_state["current_action"] = None
        logger.debug("current_action_cleared", extra={"agent_id": agent_id_for_log})

        return "default"
