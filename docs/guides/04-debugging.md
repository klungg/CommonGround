# Debugging Guide

The framework includes several features to aid in debugging and understanding agent behavior.

## 1. Logging
The primary tool for debugging is the structured logging system.

*   **Log Level**: To see detailed operational logs, set the log level to `DEBUG` in your `.env` file or via the command line argument when running `run_server.py`.
    ```
    # in .env
    LOG_LEVEL="DEBUG"
    ```
    ```bash
    # or via command line
    python run_server.py --log-level DEBUG
    ```
*   **Structured Logs**: Logs are in JSON format, containing rich context like `run_id`, `agent_id`, and `turn_id`, making them easy to parse and filter.

## 2. Environment Variables for Debugging
You can enable advanced debugging features by setting environment variables in your `.env` file.

*   **`STATE_DUMP="true"`**: At the end of a flow, this will dump a complete JSON snapshot of the final `RunContext` to a file in the `reports/` directory. This is invaluable for post-mortem analysis of the agent's state.

*   **`CAPTURE_LLM_REQUEST_BODY="true"`**: This will record the exact request payload (including messages, system prompt, tools, and parameters like temperature) sent to the LLM for every call. This data is stored in the `Turn` object at `llm_interaction.final_request` and can be inspected in the web UI's DevTools panel or in the state dump. Use this to verify the final prompt and configuration seen by the model. Note that this can significantly increase the size of the state object.

## 3. Using the Web UI for Debugging
The built-in web UI is a powerful tool for real-time observation.

*   **DevTools Panel**: This panel provides a raw, real-time stream of all WebSocket events. You can inspect `turns_sync` events to see the detailed structure of each `Turn` object as it's created and updated.
*   **Flow, Kanban, and Timeline Views**: These visualizations are built directly from the `Turn` data and provide high-level insights into the agent team's workflow, task status, and execution timing. Use them to identify bottlenecks or incorrect logic flows.
