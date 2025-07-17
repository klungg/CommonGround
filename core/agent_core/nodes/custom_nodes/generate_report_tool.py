import logging
from ..base_tool_node import BaseToolNode
from ...framework.tool_registry import tool_registry

logger = logging.getLogger(__name__)

@tool_registry(
    name="generate_markdown_report",
    description="Called by the Principal Agent when all work modules are complete. This tool prepares a structured prompt for the Principal to generate its final, comprehensive Markdown report.",
    parameters={
        "type": "object",
        "properties": {
            "principal_final_synthesis": {
                "type": "string",
                "description": "A concise result synthesis of the research (one paragraph), and the proposed final report structure."
            }
        },
        "required": ["principal_final_synthesis"]
    },
    toolset_name="reporting_tools"
)
class GenerateMarkdownReportTool(BaseToolNode):
    async def exec_async(self, prep_res: dict):
        tool_params = prep_res.get("tool_params", {})
        synthesis = tool_params.get("principal_final_synthesis", "No synthesis was provided.")
        
        instructional_prompt = f"""
<system_directive>
# FINAL REPORT GENERATION PROTOCOL

All analytical work is complete. Your final task is to synthesize all project findings into a single, comprehensive, and well-structured Markdown research report.

## Your Final Synthesis (Provided by you):
<final_synthesis>
{synthesis}
</final_synthesis>

## Your Task:
Based on your synthesis and the entire project history available in your context, write the final Markdown report. You MUST adhere to the following structure:

## Main Title (Derived from the original research question)

### Key Points
- A bulleted list of the most important findings (4-6 concise points).

### Overview
- A brief introduction to the topic, its significance, and the scope of the report (1-2 paragraphs).

### Detailed Analysis
- Organize information into logical sections with clear H3 or H4 headings.
- Present information in a structured, easy-to-follow manner.
- Use bullet points, numbered lists, and tables where appropriate.

### Conclusion
- A summary of the main findings and their implications.

### Key Citations / References (If available)
- List source URLs here. Format: `- [Source Title](URL)`
- Make sure to include all relevant sources that informed your analysis.
- Include link to the page, not just the domain.

## Action:
In your next turn, provide ONLY the final Markdown report in the 'content' field of your response. After this, you MUST call the `finish_flow` tool to conclude the project.
</system_directive>
        """
        
        # Return a dictionary in the standard format
        return {
            "status": "success",
            "payload": {
                "instructional_prompt": instructional_prompt.strip()
            }
        }
