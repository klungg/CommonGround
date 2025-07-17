"""
Helpers for safe and convenient access to nested data within the run context.
"""
import logging
import re
from typing import Dict, Any, List, Callable

logger = logging.getLogger(__name__)

SENTINEL_DEFAULT = object()

class VModelAccessor:
    """
    An accessor class providing syntactic sugar for V-Model paths.
    Allows safe context access in `eval()` environments via `v['path.to.value']`.
    """
    def __init__(self, context_obj: Dict):
        """
        Initializes the accessor, binding it to a specific context object.
        """
        self._context = context_obj

    def __getitem__(self, path_str: str) -> Any:
        """
        Implements the `v['path.to.value']` syntax.
        """
        # No special handling, directly resolve from context
        return get_nested_value_from_context(self._context, path_str)

# Defines the core implementation of the V-Model, mapping prefixes to
# functions that retrieve the base object for that namespace from a SubContext.
PATH_RESOLVER_MAP: Dict[str, Callable[[Dict], Any]] = {
    # Core namespaces
    "state": lambda ctx: ctx.get("state"),
    "meta": lambda ctx: ctx.get("meta"),
    "team": lambda ctx: ctx.get("refs", {}).get("team"),
    "run": lambda ctx: ctx.get("refs", {}).get("run", {}).get("meta"),
    "config": lambda ctx: ctx.get("refs", {}).get("run", {}).get("config"),
    
    # Shortcuts
    "initial_params": lambda ctx: ctx.get("state", {}).get("initial_parameters"),
    "flags": lambda ctx: ctx.get("state", {}).get("flags"),
    
    # Cross-context shortcuts
    "principal": lambda ctx: (pc_ref := ctx.get("refs", {}).get("run", {}).get("sub_context_refs", {}).get("_principal_context_ref")) and pc_ref.get("state"),
    "partner": lambda ctx: (pt_ref := ctx.get("refs", {}).get("run", {}).get("sub_context_refs", {}).get("_partner_context_ref")) and pt_ref.get("state"),
    
    # Debugging/introspection
    "_self": lambda ctx: ctx,
}
DEFAULT_PATH_PREFIX = "state"


def _traverse_path(base_object: Any, path_keys: List[str]) -> Any:
    """
    Helper function to traverse a list of path keys on a given base object.
    This version is "greedy" and can handle keys that contain dots by
    iteratively trying to match the longest possible path segment first.
    It's also enhanced to handle list indices like `[-1]`.
    """
    value = base_object
    i = 0
    while i < len(path_keys):
        if value is None:
            return SENTINEL_DEFAULT

        # Greedily try to match a key from the remaining path segments
        matched = False
        # Check for compound keys from longest possible to shortest
        for j in range(len(path_keys), i, -1):
            potential_key = ".".join(path_keys[i:j])
            
            if isinstance(value, dict) and potential_key in value:
                value = value[potential_key]
                i = j  # Move pointer past the matched segment
                matched = True
                break  # Found the longest possible match, continue to next part of path

        if matched:
            continue
        
        # If no compound key was matched, process one key at a time
        key = path_keys[i]
        list_access_match = re.match(r'^(.*)\[(-?\d+)\]$', key)

        if list_access_match:
            key_part = list_access_match.group(1)
            index_part = int(list_access_match.group(2))
            
            list_value = None
            if key_part: # e.g. key is 'items[0]'
                if isinstance(value, dict) and key_part in value:
                    list_value = value[key_part]
                elif hasattr(value, key_part):
                    list_value = getattr(value, key_part)
            elif isinstance(value, list): # e.g. previous key resolved to a list, current key is '[0]'
                list_value = value

            if isinstance(list_value, list):
                try:
                    value = list_value[index_part]
                except IndexError:
                    return SENTINEL_DEFAULT
            else:
                return SENTINEL_DEFAULT
        elif isinstance(value, dict):
            if key not in value:
                return SENTINEL_DEFAULT
            value = value[key]
        elif isinstance(value, list):
            try:
                idx = int(key)
                if not (-len(value) <= idx < len(value)):
                    return SENTINEL_DEFAULT
                value = value[idx]
            except (ValueError, TypeError):
                return SENTINEL_DEFAULT
        elif hasattr(value, key):
             value = getattr(value, key)
        else:
            return SENTINEL_DEFAULT

        i += 1
        
    return value


def get_nested_value_from_context(
    context_obj: Dict,
    path_str: str,
    default: Any = SENTINEL_DEFAULT
) -> Any:
    """
    Dynamically retrieves a nested value from the context using V-Model paths.
    It first resolves the path's prefix to determine the starting point (the
    base object) and then traverses the remaining path.
    """
    if not path_str or not isinstance(path_str, str):
        if default is SENTINEL_DEFAULT:
            return None
        return default

    path_parts = path_str.split('.', 1)
    prefix = path_parts[0]
    
    resolver_func = PATH_RESOLVER_MAP.get(prefix)
    remaining_path_str = ""
    base_object_name_for_log = "" # For logging purposes

    if resolver_func:
        base_object = resolver_func(context_obj)
        base_object_name_for_log = prefix
        remaining_path_str = path_parts[1] if len(path_parts) > 1 else ""
    else:
        base_object = PATH_RESOLVER_MAP[DEFAULT_PATH_PREFIX](context_obj)
        base_object_name_for_log = DEFAULT_PATH_PREFIX
        remaining_path_str = path_str

    if not remaining_path_str:
        if base_object is not None:
            return base_object
        elif default is SENTINEL_DEFAULT:
            return None
        else:
            return default

    # Split the path by dots, but keep `key[index]` parts together.
    remaining_keys = re.split(r'\.(?![^\[]*\])', remaining_path_str)
    final_value = _traverse_path(base_object, remaining_keys)

    if final_value is SENTINEL_DEFAULT:
        logger.warning(
            f"V-Model path resolution failed for '{path_str}'. "
            f"Could not resolve '{'.'.join(remaining_keys)}' from base object '{base_object_name_for_log}'. "
            f"Returning default value."
        )
        if default is SENTINEL_DEFAULT:
            return None
        return default
        
    return final_value
