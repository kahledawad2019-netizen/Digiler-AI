"""Aggregate every capability router under the API prefix."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routers import (admin, agents, auth, chat, citations, dashboard, functions, graph,
                             health, instructor, knowledge, llm, planner, quiz, research, rl,
                             search, student, upload)

api_router = APIRouter()
for module in (health, auth, llm, chat, search, knowledge, research, student, dashboard,
               planner, quiz, agents, rl, functions, graph, citations, upload, instructor, admin):
    api_router.include_router(module.router)
