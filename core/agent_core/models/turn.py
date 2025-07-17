# Define Turn structure using TypedDict
from typing import Any, Dict, List, Literal, Optional, TypedDict


class AgentInfo(TypedDict):
    agent_id: str
    profile_logical_name: str
    profile_instance_id: str
    assigned_role_name: Optional[str]


class LLMAttempt(TypedDict):
    stream_id: str
    status: Literal["success", "failed"]
    error: Optional[str]


class LLMInteraction(TypedDict):
    status: Literal["running", "completed", "failed"]
    attempts: List[LLMAttempt]
    final_request: Optional[Any]  # Changed from Optional[Dict] to accommodate "[omitted]"
    final_response: Optional[Dict]
    predicted_usage: Optional[Dict[str, int]] # <--- New
    actual_usage: Optional[Dict[str, int]]    # <--- New


class ToolInteraction(TypedDict):
    tool_call_id: str
    tool_name: str
    start_time: str
    end_time: Optional[str]
    status: Literal["running", "completed", "error", "cancelled", "interrupted"]
    input_params: Dict  
    result_payload: Optional[Any] 
    error_details: Optional[str]


class ProcessedInboxItemLog(TypedDict, total=False):
    """
    Detailed log for processing a single InboxItem.
    Corresponds to the new Turn.inputs Schema in refactor_pitfalls.md.
    """
    item_id: str
    source: str
    triggering_observer_id: Optional[str]
    handling_strategy_source: Literal["profile", "global", "fallback"]
    ingestor_used: str
    injection_mode: str
    injected_content: str
    predicted_token_count: Optional[int] # <--- New


class TurnInputs(TypedDict, total=False):
    """
    Structured Turn inputs for enhanced traceability.
    """
    processed_inbox_items: List[ProcessedInboxItemLog]


class Turn(TypedDict):
    turn_id: str
    run_id: str
    flow_id: str  # New: Used to identify a continuous execution flow
    agent_info: AgentInfo
    turn_type: Literal["agent_turn", "dispatch_turn", "aggregation_turn", "user_turn"]
    status: Literal["running", "completed", "error"]
    start_time: str
    end_time: Optional[str]
    source_turn_ids: List[str]  # Replaces triggering_event
    source_tool_call_id: Optional[str] # Replaces triggering_event
    inputs: TurnInputs  # Update: Use structured TurnInputs instead of a generic Dict
    outputs: Dict  # e.g., {"state_keys_modified": ["key2"]}
    llm_interaction: Optional[LLMInteraction]
    tool_interactions: List[ToolInteraction]
    metadata: Optional[Dict]  # e.g., {"consecutive_no_tool_call_count": 1}
    error_details: Optional[str]
