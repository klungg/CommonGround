import logging
from ..base_tool_node import BaseToolNode
from pocketflow import AsyncNode
from ...framework.tool_registry import tool_registry
from typing import Dict, Any, Optional
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

@tool_registry(
    name="generate_message_summary",
    description="Called by an Associate Agent when its work on a module is complete. This tool prepares a structured prompt for the agent to generate its final, comprehensive deliverable summary.",
    parameters={
        "type": "object",
        "properties": {
            "current_associate_findings": {
                "type": "string",
                "description": "A detailed summary of the key findings, conclusions, and deliverables from the associate's work on the current module."
            }
        },
        "required": ["current_associate_findings"]
    },
    toolset_name="flow_control_summary"
)
class GenerateMessageSummaryTool(BaseToolNode):
    """
    A tool that generates an instructional prompt for an Associate Agent
    to create its final deliverable summary.
    """
    async def exec_async(self, prep_res: Dict) -> Dict:
        tool_params = prep_res.get("tool_params", {})
        findings = tool_params.get("current_associate_findings")
        
        instructional_prompt = f"""
<system_directive>
# FINALIZATION PROTOCOL INITIATED

Your tactical work on this module is complete. Your final action is to synthesize all your work into a structured 'deliverables' package for the Principal Agent.

## Your Preliminary Findings (Provided by you):
<preliminary_findings>
{findings}
</preliminary_findings>

## Your Task:
Based on your preliminary findings and your entire message history for this task, formulate a final, comprehensive summary. This summary MUST be structured as a JSON object with a single key, 'primary_summary'. The value should be a detailed Markdown string.

**Example Output Format:**
```json
{{
  "primary_summary": "## 1. Sub-Task Summary\\n- **Objective**: ...\\n- **Outcome**: ...\\n\\n## 2. Key Findings\\n- Finding A: ...\\n- Finding B: ..."
}}
```

## Action:
In your next turn, provide ONLY the final JSON object in the 'content' field of your response. DO NOT call any tools. This will be your final output for this work module.
</system_directive>
        """
        
        return {
            "status": "success",
            "payload": {
                "instructional_prompt": instructional_prompt.strip()
            }
        }

# The original FinishNode remains, as it's a separate tool.
@tool_registry(
    name="finish_flow",
    description="Signals that the current operational flow should conclude. Use this when all tasks are completed or a definitive end state is reached.",
    parameters={"type": "object", "properties": {
        "reason": {
            "type": "string",
            "description": "Optional reason for finishing the flow."
        }
    }},
    ends_flow=True,
    toolset_name="flow_control_end" 
)
class FinishNode(AsyncNode):
    async def prep_async(self, shared: Dict) -> Dict:
        current_action = shared.get("state", {}).get("current_action", {})
        reason = "Flow concluded due to agent policy."
        if current_action:
            reason = current_action.get("reason", "No specific reason provided.")
        parent_agent_id_from_meta = shared['meta'].get("parent_agent_id")
        return {
            "reason": reason,
            "shared_sub_context": shared,
            "parent_agent_id_for_event": parent_agent_id_from_meta
        }

    async def exec_async(self, prep_res: Dict) -> Dict:
        reason = prep_res.get("reason", "No specific reason provided.")
        logger.info("flow_ending", extra={"reason": reason})
        return {
            "status": "flow_ending_initiated", 
            "reason": reason,
            "result_package": {
                "status": "COMPLETED_SUCCESSFULLY",
                "final_summary": f"Flow completed as instructed. Reason: {reason}",
                "terminating_tool": "finish_flow",
                "error_details": None,
                "deliverables": {"final_report": prep_res.get("shared_sub_context", {}).get('state', {}).get("final_report")}
            }
        }

    async def post_async(self, shared: Dict, prep_res: Any, exec_res: Dict) -> Optional[str]:
        current_sub_context = prep_res.get("shared_sub_context")
        if current_sub_context and exec_res and "result_package" in exec_res:
            current_sub_context["state"]["final_result_package"] = exec_res["result_package"]
        return None
