"""Assembles the coach as a LangGraph StateGraph.

TODO(agent-engineer): wire Analyst -> Planner -> Curator, grounded via coach.rag,
using coach.llm.get_chat_model() so the model stays provider-agnostic.
"""
from __future__ import annotations


def build_coach_graph():
    raise NotImplementedError("agent-engineer: build the StateGraph here")
