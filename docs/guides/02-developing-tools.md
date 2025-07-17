# Developing Custom Tools

In this framework, a "tool" is a `PocketFlow` node that an agent can decide to call. The framework is designed to make tool development straightforward and robust.

## 1. The `BaseToolNode` Class
All custom tools should inherit from `agent_core.nodes.base_tool_node.BaseToolNode`. This base class handles the boilerplate logic of tool execution, such as:
*   Extracting parameters from the agent's state.
*   Managing retries and error handling.
*   Adding tool results back into the agent's `Inbox`.
*   Adding new knowledge items to the `KnowledgeBase`.

This allows you, the developer, to focus purely on the tool's core logic.

## 2. Using the `@tool_registry` Decorator
To make your tool discoverable by the system, you must decorate your class with `@tool_registry`.

```python
from ..base_tool_node import BaseToolNode
from ...framework.tool_registry import tool_registry

@tool_registry(
    name="my_custom_tool",
    description="A brief, clear description of what this tool does.",
    parameters={
        "type": "object",
        "properties": {
            "my_param": { "type": "string", "description": "Description of the parameter." }
        },
        "required": ["my_param"]
    },
    toolset_name="custom_tools"
)
class MyCustomToolNode(BaseToolNode):
    # ... implementation ...
```
*   `name`: The name the LLM will use to call your tool.
*   `description`: A clear, concise description for the LLM.
*   `parameters`: A JSON Schema object defining the tool's input parameters.
*   `toolset_name`: A category for grouping related tools. This is used by the `tool_access_policy` in Agent Profiles.

## 3. Implementing the Core Logic: `exec_async`
The only method you need to implement is `exec_async`.

*   **Input**: It receives a single dictionary, `prep_res`, which contains:
    *   `prep_res["tool_params"]`: A dictionary of the parameters provided by the LLM for this tool call.
    *   `prep_res["shared_context"]`: The full context object of the agent that called the tool, giving you access to `state`, `refs`, etc. if needed.

*   **Output**: Your method **must** return a dictionary with a specific structure:
    ```python
    {
        "status": "success" | "error",
        "payload": { ... }, # Optional: The core result to be sent back to the LLM.
        "error_message": "...", # Optional: A description of the error if status is "error".
        "_knowledge_items_to_add": [ ... ] # Optional: A list of items to add to the knowledge base.
    }
    ```

## 4. Full Example: A Simple Greeting Tool

This example demonstrates a complete, functional tool.

```python
# file: agent_core/nodes/custom_nodes/example_tool.py

import logging
from ..base_tool_node import BaseToolNode
from ...framework.tool_registry import tool_registry

logger = logging.getLogger(__name__)

@tool_registry(
    name="greet_user",
    description="Generates a simple greeting.",
    parameters={
        "type": "object",
        "properties": { "user_name": { "type": "string" } },
        "required": ["user_name"]
    },
    toolset_name="custom_utils"
)
class GreetUserTool(BaseToolNode):
    """A simple tool example inheriting from BaseToolNode."""

    async def exec_async(self, prep_res: dict) -> dict:
        """Implements the core execution logic."""
        try:
            tool_params = prep_res.get("tool_params", {})
            user_name = tool_params.get("user_name", "Guest")

            # 1. Prepare the payload to be returned to the LLM.
            greeting_payload = {
                "message": f"Hello, {user_name}! Welcome to the system.",
                "status": "Greeting generated successfully."
            }

            # 2. (Optional) Prepare a knowledge item to be stored.
            kb_item = {
                "item_type": "GREETING_LOG",
                "content": f"Greeted user: {user_name}",
                "source_uri": f"greeting://{user_name}",
                "metadata": {"tags": ["greeting", "example"]}
            }

            # 3. Return the standard result dictionary.
            return {
                "status": "success",
                "payload": greeting_payload,
                "_knowledge_items_to_add": [kb_item]
            }

        except Exception as e:
            logger.error(f"GreetUserTool failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error_message": f"An unexpected error occurred: {e}"
            }
```

The `BaseToolNode` will automatically handle the return value from `exec_async`:
*   The `payload` will be wrapped in a `TOOL_RESULT` event and placed in the agent's `inbox`.
*   The items in `_knowledge_items_to_add` will be added to the `KnowledgeBase`.
*   If `status` is `error`, the error will be properly logged and reported.
