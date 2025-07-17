import logging, json
from .serialization import get_serializable_run_snapshot # Added import

logger = logging.getLogger(__name__)

async def dump_state_to_file(run_context_to_dump: dict): # Parameter name changed to run_context_to_dump
    """Dumps the complete run context snapshot to a file."""
    # The filename can include the run_id to distinguish different dumps
    run_id = run_context_to_dump.get("meta", {}).get("run_id", "unknown_run")
    dump_filename = f"run_context_dump_{run_id}.json"
    
    with open(dump_filename, "w", encoding="utf-8") as f:
        try:
            # Use the new serialization function to get a serializable snapshot
            snapshot_data = get_serializable_run_snapshot(run_context_to_dump)
            json.dump(snapshot_data, f, ensure_ascii=False, indent=2)
            logger.info("run_context_snapshot_dumped", extra={"run_id": run_id, "dump_filename": dump_filename})
        except Exception as e: # Catch a broader exception, as get_serializable_run_snapshot can also raise errors
            logger.error("run_context_serialization_failed", extra={"run_id": run_id, "error": str(e)}, exc_info=True)
            # Write error information to the file
            error_info = {
                "error": "Could not serialize run context",
                "details": str(e),
                "run_id_attempted": run_id
            }
            try:
                # Try to write the error information; if even this fails, there's nothing more to be done
                json.dump(error_info, f, ensure_ascii=False, indent=2)
            except Exception as dump_error_e:
                logger.critical("dump_error_write_failed", extra={"dump_filename": dump_filename, "error": str(dump_error_e)})
                f.write(f'{{"critical_error": "Failed to even dump error information: {str(dump_error_e)}"}}')
