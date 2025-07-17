import logging
import copy
from typing import Dict, List
import os

from .tool_registry import get_tools_for_profile, format_tools_for_llm_api, get_tool_by_name
from agent_profiles.loader import get_active_llm_config_by_name

logger = logging.getLogger(__name__)


def get_formatted_api_tools(agent_node_instance, context: Dict) -> List[Dict]:
    """
    Gets tools based on the profile's tool_access_policy and shared state,
    then formats them for the LLM API.
    """
    profile_config = agent_node_instance.loaded_profile
    agent_id = agent_node_instance.agent_id

    applicable_tools = get_tools_for_profile(profile_config, context, agent_id)
    api_tools_list = format_tools_for_llm_api(applicable_tools)
    
    logger.debug("agent_tools_prepared", extra={"agent_id": agent_id, "tool_count": len(api_tools_list)})
    return api_tools_list
