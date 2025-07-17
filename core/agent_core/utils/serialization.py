
def get_serializable_run_snapshot(run_context: dict) -> dict:
    """Creates a serializable snapshot of the entire run context."""
    if not run_context: return {}
    
    snapshot = {
        "meta": run_context.get("meta"),
        "config": { # Adding config as per typical snapshot needs
            "run_type": run_context.get("meta", {}).get("run_type"),
            # Potentially add selected non-sensitive config items if needed by UI
        },
        "team_state": run_context.get("team_state"),
        "sub_contexts_state": {}
    }
    
    # Serialize KnowledgeBase
    kb_instance = run_context.get("runtime", {}).get("knowledge_base")
    if kb_instance and hasattr(kb_instance, 'to_dict'):
        snapshot["knowledge_base"] = kb_instance.to_dict()
    else:
        snapshot["knowledge_base"] = None
    
    sub_refs = run_context.get("sub_context_refs", {})
    for key, ref_obj in sub_refs.items():
        if ref_obj and isinstance(ref_obj, dict) and 'state' in ref_obj:
            # --- Start of modification ---
            # No longer create simple_key, use the original key directly
            # The original key is "_partner_context_ref" or "_principal_context_ref"
            snapshot["sub_contexts_state"][key] = ref_obj['state']
            # --- End of modification ---
    
    return snapshot
