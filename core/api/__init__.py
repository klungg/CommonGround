"""PocketFlow API Package

Provides WebSocket API services, supporting:
1. Session management (WebSocket connection credentials)
2. Real-time communication (via SessionEventManager)
3. Business run management (via run_id and active_runs_store)
"""

from .events import SessionEventManager
from .session import create_session, active_runs_store # get_session, remove_session are removed
# Potentially add run_manager functions here if active_runs_store moves to a dedicated module

__all__ = [
    'SessionEventManager',
    'create_session', # For WebSocket connection credentials
    'active_runs_store', # Global store for active run contexts
]
