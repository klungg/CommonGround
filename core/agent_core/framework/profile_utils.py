import logging
from typing import Dict, Optional
from datetime import datetime # Added import for datetime.fromisoformat

logger = logging.getLogger(__name__)

def get_active_profile_by_name(profiles_store: Dict[str, Dict], name: str) -> Optional[Dict]:
    """
    Finds the latest active version of a Profile dictionary from the profiles_store by its logical name.
    If multiple active versions are found (which should not happen), it returns the one with the highest 'rev'.
    Only considers Profiles where is_active=True and is_deleted=False.

    Args:
        profiles_store: The Profile store dictionary, with instance ID (UUID) as keys and Profile dictionaries as values.
        name: The logical name of the Profile to find.

    Returns:
        Optional[Dict]: The found Profile dictionary, or None if not found.
    """
    if not profiles_store or not name:
        return None

    latest_active_profile: Optional[Dict] = None
    highest_rev = -1

    for profile_instance_id, profile_data in profiles_store.items():
        if (profile_data.get("name") == name and
            profile_data.get("is_active") is True and
            profile_data.get("is_deleted") is False):
            
            current_rev = profile_data.get("rev", 0)
            if current_rev > highest_rev:
                highest_rev = current_rev
                latest_active_profile = profile_data
            elif current_rev == highest_rev and latest_active_profile:
                # If rev is the same, compare timestamps and choose the newer one
                current_ts_str = profile_data.get("timestamp", "")
                latest_ts_str = latest_active_profile.get("timestamp", "")
                try:
                    current_ts = datetime.fromisoformat(current_ts_str.replace("Z", "+00:00")) if current_ts_str else None
                    latest_ts = datetime.fromisoformat(latest_ts_str.replace("Z", "+00:00")) if latest_ts_str else None
                    if current_ts and latest_ts and current_ts > latest_ts:
                        logger.warning(
                            "profile_multiple_active_same_rev_choosing_newer",
                            extra={
                                "profile_name": name,
                                "revision": current_rev,
                                "newer_instance_id": profile_instance_id,
                                "newer_timestamp": current_ts_str,
                                "older_instance_id": latest_active_profile.get('profile_id'),
                                "older_timestamp": latest_ts_str
                            }
                        )
                        latest_active_profile = profile_data
                    elif current_ts and not latest_ts: # current has timestamp, latest doesn't
                        latest_active_profile = profile_data
                    else:
                         logger.warning(
                            "profile_multiple_active_same_rev_timestamps_unclear",
                            extra={
                                "profile_name": name,
                                "revision": current_rev,
                                "current_latest_instance_id": latest_active_profile.get('profile_id'),
                                "new_found_instance_id": profile_instance_id
                            }
                        )
                except ValueError:
                     logger.warning(
                        "profile_multiple_active_same_rev_timestamp_parse_error",
                        extra={
                            "profile_name": name,
                            "revision": current_rev,
                            "first_instance_id": latest_active_profile.get('profile_id'),
                            "second_instance_id": profile_instance_id
                        }
                    )


    if not latest_active_profile:
        logger.debug("profile_not_found", extra={"profile_name": name})
    else:
        logger.debug("profile_found", extra={"profile_name": name, "instance_id": latest_active_profile.get('profile_id'), "revision": latest_active_profile.get('rev')})
        
    # Return a deep copy to prevent modification of the original in the store
    import copy
    return copy.deepcopy(latest_active_profile) if latest_active_profile else None

def get_profile_by_instance_id(profiles_store: Dict[str, Dict], instance_id: str) -> Optional[Dict]:
    """
    Finds a Profile dictionary from the profiles_store by its instance ID (UUID).

    Args:
        profiles_store: The Profile store dictionary, with instance ID (UUID) as keys and Profile dictionaries as values.
        instance_id: The instance ID (UUID) of the Profile to find.

    Returns:
        Optional[Dict]: The found Profile dictionary, or None if not found.
    """
    if not profiles_store or not instance_id:
        return None
    
    profile_data = profiles_store.get(instance_id)
    if profile_data:
        # Ensure the returned profile is not marked as is_deleted: true
        if profile_data.get("is_deleted") is True:
            logger.warning("profile_by_instance_id_deleted", extra={"instance_id": instance_id, "profile_name": profile_data.get('name')})
            return None
        logger.debug("profile_by_instance_id_found", extra={"instance_id": instance_id, "profile_name": profile_data.get('name'), "revision": profile_data.get('rev')})
    else:
        logger.debug("profile_by_instance_id_not_found", extra={"instance_id": instance_id})
        
    # Return a deep copy to prevent modification of the original in the store
    import copy
    return copy.deepcopy(profile_data) if profile_data else None

def get_active_profile_instance_id_by_name(profiles_store: Dict[str, Dict], name: str) -> Optional[str]:
    """
    Finds the instance ID (UUID) of the latest active version of a Profile from the profiles_store by its logical name.

    Args:
        profiles_store: The Profile store dictionary, with instance ID (UUID) as keys and Profile dictionaries as values.
        name: The logical name of the Profile to find.

    Returns:
        Optional[str]: The instance ID (UUID) of the found Profile, or None if not found.
    """
    active_profile = get_active_profile_by_name(profiles_store, name)
    if active_profile:
        return active_profile.get("profile_id")
    return None

# Removed duplicate import from here, added at the top.
