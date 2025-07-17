import importlib
import logging

logger = logging.getLogger(__name__)

def get_callable_from_path(path_string: str):
    """Dynamically imports and returns a callable from a 'module.function' string."""
    try:
        module_name, function_name = path_string.rsplit('.', 1)
        module = importlib.import_module(module_name)
        return getattr(module, function_name)
    except (ImportError, AttributeError, ValueError) as e:
        logger.error("callable_loading_failed", extra={"path": path_string, "error": str(e)}, exc_info=True)
        raise
