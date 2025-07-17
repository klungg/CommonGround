from typing import TypedDict, Dict, List, Any, Optional, Literal
import asyncio # For asyncio.Event type hint

# Forward declaration for RunContext to be used in SubContextRefs
class RunContext(TypedDict): ...

# Definition for TeamState
class TeamState(TypedDict, total=False):
    """Mutable state shared across team members."""
    question: Optional[str]
    work_modules: Dict[str, Any]
    _work_module_next_id: int # New field for generating unique, incrementing module IDs
    profiles_list_instance_ids: List[str]
    is_principal_flow_running: bool
    dispatch_history: List[Dict]
    turns: List[Dict]
    partner_directives_queue: List[Dict]

# Definitions for SubContext parts
class SubContextMeta(TypedDict):
    """Metadata for a sub-process context."""
    run_id: str
    agent_id: str
    parent_agent_id: Optional[str]
    assigned_role_name: Optional[str]

class SubContextState(TypedDict, total=False):
    """Private, serializable state of a sub-process."""
    messages: List[Dict]
    current_action: Optional[Dict]
    inbox: List[Dict]
    flags: Dict
    initial_parameters: Dict
    deliverables: Dict
    last_activity_timestamp: str
    # Agent-specific state fields that might be added by AgentNode or other logic
    # parent_agent_id: Optional[str] # This is in SubContextMeta, but AgentNode also writes to state. Keeping here for full state picture.
    current_iteration_count: int
    archived_messages_history: List[Dict]
    status_summary_for_partner: Dict
    execution_milestones: List[Dict]
    tool_inputs: Dict 
    current_tool_call_id: Optional[str] # Added from AgentNode/state
    current_actor_id: Optional[str] # Added from AgentNode/state
    last_turn_id: Optional[str] 
    consecutive_empty_llm_responses: int 
    _current_llm_stream_id: Optional[str] 
    agent_start_utc_timestamp: str 
    # For Partner agent
    profiles_list_instance_ids: List[str] 
    principal_launch_config_history: List[Dict] 
    # For Principal agent
    # (Many Principal specific states are now in team_state or handled via work_modules)


class SubContextRuntimeObjects(TypedDict, total=False):
    """Non-serializable runtime objects unique to a sub-process."""
    new_user_input_event: Optional[asyncio.Event]
    # Partner specific runtime object
    active_principal_completion_event: Optional[asyncio.Event]

class SubContextRefs(TypedDict):
    """References to global and shared resources within a sub-process context."""
    run: RunContext # Use forward declared RunContext
    team: TeamState

# Definition for SubContext
class SubContext(TypedDict):
    """The common context structure followed by all sub-processes (Partner, Principal, Associate)."""
    meta: SubContextMeta
    state: SubContextState
    runtime_objects: SubContextRuntimeObjects
    refs: SubContextRefs

# Definitions for RunContext parts
class RunContextMeta(TypedDict):
    """Metadata for the `run_context`, containing the run's identity information."""
    run_id: str
    run_type: str
    creation_timestamp: str
    status: Literal["CREATED", "RUNNING", "AWAITING_INPUT", "COMPLETED", "FAILED", "CANCELLED"]

class RunContextConfig(TypedDict):
    """Configuration snapshot for the `run_context`, determined at the start of the run and immutable."""
    agent_profiles_store: Dict[str, Any]
    shared_llm_configs_ref: Dict[str, Any]

class RunContextRuntime(TypedDict, total=False):
    """Global, non-serializable runtime objects for the `run_context`."""
    event_manager: Any  # SessionEventManager
    knowledge_base: Any # KnowledgeBase
    # For Principal launch
    principal_completion_event: Optional[asyncio.Event] 
    principal_flow_task_handle: Optional[asyncio.Task] 
    current_principal_subtask_id: Optional[str] 

class RunContextSubContexts(TypedDict):
    """References to the currently active sub-process contexts within the `run_context`."""
    _partner_context_ref: Optional[SubContext]
    _principal_context_ref: Optional[SubContext]
    _ongoing_associate_tasks: Dict[str, SubContext] # Key is associate_id (str), value is SubContext

# Actual definition of RunContext
class RunContext(TypedDict):
    """The globally unique root context object, representing a complete business run."""
    meta: RunContextMeta
    config: RunContextConfig
    team_state: TeamState
    runtime: RunContextRuntime
    sub_context_refs: RunContextSubContexts
    project_id: str
