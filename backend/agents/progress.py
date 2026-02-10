"""
Real-time progress streaming via asyncio.Queue.

Provides a shared, module-level queue that agents push log messages into.
The SSE endpoint reads from this queue to stream live updates to the frontend.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level queue storage  (one queue per active session)
# ---------------------------------------------------------------------------
_queues: dict[str, asyncio.Queue] = {}


def create_progress_queue(session_id: str) -> asyncio.Queue:
    """Create and register a progress queue for a session."""
    q: asyncio.Queue = asyncio.Queue()
    _queues[session_id] = q
    logger.info(f"Progress queue created for session {session_id}")
    return q


def get_progress_queue(session_id: str) -> asyncio.Queue | None:
    """Get the progress queue for a session (if it exists)."""
    return _queues.get(session_id)


def remove_progress_queue(session_id: str) -> None:
    """Remove and clean up a session's progress queue."""
    _queues.pop(session_id, None)
    logger.info(f"Progress queue removed for session {session_id}")


async def push_event(session_id: str, event: dict[str, Any]) -> None:
    """Push an event into the session's progress queue (non-blocking)."""
    q = _queues.get(session_id)
    if q is not None:
        await q.put(event)


def log_progress(state: dict, message: str) -> None:
    """
    Log a progress message for the current agent.

    - Appends to state["current_logs"] (for LangGraph state tracking)
    - Pushes an SSE event into the session's asyncio Queue (for real-time streaming)
    """
    from datetime import datetime

    # Append to state logs (LangGraph state)
    if "current_logs" not in state:
        state["current_logs"] = []
    state["current_logs"].append(message)

    agent_name = state.get("current_agent", "agent")
    logger.info(f"[{agent_name}] {message}")

    # Push into the real-time queue (fire-and-forget via event loop)
    session_id = state.get("session_id", "")
    q = _queues.get(session_id)
    if q is not None:
        try:
            q.put_nowait({
                "type": "agent_log",
                "agent": agent_name,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
            })
        except Exception:
            pass  # queue full or loop closed — not critical
