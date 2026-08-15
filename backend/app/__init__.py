"""Digiler AI backend — a thin FastAPI layer over the existing ala platform.

Every capability (chat/GraphRAG, retrieval, knowledge base, research, planner,
dashboard, student model, agents, function-calling, citations, video, vision) is
served by calling the already-implemented ``ala`` services — no business logic is
re-implemented here. The API only adds transport, auth, persistence and streaming.
"""

__version__ = "1.0.0"
