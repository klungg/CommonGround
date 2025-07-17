import yaml
import logging
from pathlib import Path
import copy
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

PROFILES_DIR = Path(__file__).parent / "profiles"
LLM_CONFIGS_DIR = Path(__file__).parent / "llm_configs"

def _deep_merge(parent: dict, child: dict) -> dict:
    """
    Recursively merges two dictionaries, with special handling for lists.
    - For dictionaries, it merges keys recursively.
    - For lists of dictionaries with 'id' keys, it merges based on 'id'.
    - For other lists, it concatenates and removes duplicates.
    """
    merged = parent.copy()
    for key, value in child.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        elif key in merged and isinstance(merged[key], list) and isinstance(value, list):
            parent_list = merged[key]
            child_list = value
            
            # Check if all items in both lists are dicts with an 'id' key
            is_list_of_identifiable_dicts = all(isinstance(item, dict) and 'id' in item for item in parent_list + child_list)

            if is_list_of_identifiable_dicts:
                # Merge lists of dicts by 'id'
                merged_by_id = {item['id']: item for item in parent_list}
                for item in child_list:
                    merged_by_id[item['id']] = item  # Add or overwrite
                merged[key] = list(merged_by_id.values())
            else:
                # Merge simple lists, remove duplicates, preserve order
                temp_list = parent_list[:]
                for item in child_list:
                    if item not in temp_list:
                        temp_list.append(item)
                merged[key] = temp_list
        else:
            merged[key] = value
    return merged

def _resolve_inheritance_generic(config_name: str, raw_configs: dict, resolved_configs: dict, processing_stack: set, base_config_key: str):
    if config_name in processing_stack:
        raise Exception(f"Circular configuration inheritance detected: {' -> '.join(processing_stack)} -> {config_name}")
    if config_name in resolved_configs:
        return resolved_configs[config_name]
    if config_name not in raw_configs:
        raise Exception(f"Base configuration not found: '{config_name}'")

    processing_stack.add(config_name)
    try:
        config_data = raw_configs[config_name]
        base_config_name = config_data.get(base_config_key)
        final_config = config_data
        if base_config_name:
            parent_config = _resolve_inheritance_generic(base_config_name, raw_configs, resolved_configs, processing_stack, base_config_key)
            final_config = _deep_merge(parent_config, config_data)
        
        resolved_configs[config_name] = final_config
        return final_config
    finally:
        processing_stack.remove(config_name)

def _load_and_resolve_configs_from_dir(
    config_directory: Path,
    id_key: str,
    base_config_key: str
) -> dict:
    raw_configs_by_name = {}
    
    # 1. Discovery Phase: Load all YAML files and store them by their logical name
    if not config_directory.is_dir():
        logger.error("configuration_directory_not_found", extra={"config_directory": str(config_directory)})
        return {}

    for yaml_file in config_directory.glob("*.yaml"):
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            if not isinstance(config_data, dict):
                logger.warning("invalid_yaml_file_skipped", extra={"file_name": yaml_file.name})
                continue
            
            if "name" not in config_data:
                config_data["name"] = yaml_file.stem
            
            config_name = config_data["name"]
            if config_name in raw_configs_by_name:
                logger.warning("duplicate_configuration_name_overwriting", extra={"config_name": config_name, "file_name": yaml_file.name})
            raw_configs_by_name[config_name] = config_data
        except Exception as e:
            logger.error("configuration_file_load_error", extra={"file_name": yaml_file.name, "error": str(e)})

    # 2. Resolution Phase: Process inheritance relationships
    resolved_configs_by_name = {}
    for name in raw_configs_by_name:
        if name not in resolved_configs_by_name:
            try:
                _resolve_inheritance_generic(name, raw_configs_by_name, resolved_configs_by_name, set(), base_config_key)
            except Exception as e:
                logger.error("configuration_inheritance_parse_failed", extra={"config_name": name, "error": str(e)})

    # 3. Finalization Phase: Complete metadata and build the final dictionary by UUID
    final_configs_by_uuid = {}
    for name, config_data in resolved_configs_by_name.items():
        if id_key not in config_data or not isinstance(config_data.get(id_key), str):
            config_data[id_key] = str(uuid.uuid4())
        if "rev" not in config_data:
            config_data["rev"] = 1
        if "is_active" not in config_data:
            config_data["is_active"] = True
        if "is_deleted" not in config_data:
            config_data["is_deleted"] = False
        if "timestamp" not in config_data:
            config_data["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        instance_id = config_data[id_key]
        final_configs_by_uuid[instance_id] = config_data
        config_type = config_data.get('type', 'Config')
        logger.info("configuration_loaded_and_resolved", extra={"config_type": config_type, "config_name": name, "instance_id": instance_id, "base": config_data.get(base_config_key, 'None')})

    return final_configs_by_uuid

# --- Executed when the module is loaded ---
AGENT_PROFILES = _load_and_resolve_configs_from_dir(
    config_directory=PROFILES_DIR,
    id_key="profile_id",
    base_config_key="base_profile"
)

SHARED_LLM_CONFIGS = _load_and_resolve_configs_from_dir(
    config_directory=LLM_CONFIGS_DIR,
    id_key="llm_config_id",
    base_config_key="base_llm_config"
)

# --- Other module-level functions ---
def get_profile_copy(profile_instance_id: str) -> dict | None:
    profile = AGENT_PROFILES.get(profile_instance_id)
    return copy.deepcopy(profile) if profile else None

def get_shared_llm_config_copy(config_id: str) -> dict | None:
    """
    Gets a copy of an active LLM configuration from the global shared store by its logical name.
    Note: This function now searches by name, not by the old dictionary key.
    """
    config = get_active_llm_config_by_name(SHARED_LLM_CONFIGS, config_id)
    return config # get_active_llm_config_by_name already returns a deep copy

def get_global_active_profile_by_logical_name_copy(logical_name: str) -> dict | None:
    if not logical_name: return None
    latest_active_profile_for_name: dict | None = None
    highest_rev = -1
    for profile_data in AGENT_PROFILES.values():
        if (profile_data.get("name") == logical_name and
            profile_data.get("is_active") is True and
            profile_data.get("is_deleted") is False):
            current_rev = profile_data.get("rev", 0)
            if current_rev > highest_rev:
                highest_rev = current_rev
                latest_active_profile_for_name = profile_data
            elif current_rev == highest_rev and latest_active_profile_for_name:
                # Fallback logic for same rev (e.g., timestamp comparison) can be added here
                pass
    return copy.deepcopy(latest_active_profile_for_name) if latest_active_profile_for_name else None

def get_active_llm_config_by_name(llm_configs_store: dict, name: str) -> dict | None:
    """
    (New function) Finds the latest active version of an LLM configuration from the llm_configs_store by its logical name.
    """
    if not llm_configs_store or not name: return None
    latest_active_config = None
    highest_rev = -1
    for config_data in llm_configs_store.values():
        if (config_data.get("name") == name and
            config_data.get("is_active") is True and
            config_data.get("is_deleted") is False):
            current_rev = config_data.get("rev", 0)
            if current_rev > highest_rev:
                highest_rev = current_rev
                latest_active_config = config_data
            # (Timestamp conflict resolution logic can be omitted here for brevity)
    return copy.deepcopy(latest_active_config) if latest_active_config else None


__all__ = [
    "AGENT_PROFILES", 
    "SHARED_LLM_CONFIGS", 
    "get_profile_copy", 
    "get_shared_llm_config_copy", 
    "get_global_active_profile_by_logical_name_copy",
    "get_active_llm_config_by_name"
]
