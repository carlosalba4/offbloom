"""Shared state for the coach graph.

TODO(agent-engineer): define the real state — user goals/profile, the (simulated
or self-reported) usage data, the Analyst's findings, the weekly plan, and the
curated activities.
"""
from __future__ import annotations

from typing import TypedDict


class CoachState(TypedDict, total=False):
    goals: list[str]
    usage: dict
    analysis: dict
    plan: dict
    activities: list[dict]
