"""Tests for the safety gate: route_after_analyst + derivation node.

All tests are deterministic and never call the LLM (the analyst node is not
touched).  Structure: Arrange – Act – Assert (AAA).
"""

from __future__ import annotations

import pytest

from coach.graph.graph import route_after_analyst
from coach.graph.nodes.derivation import derivation
from coach.graph.state import (
    CoachState,
    Constraints,
    EnergyLevel,
    Lang,
    Place,
    ResourceType,
    RiskSignal,
    Severity,
    SocialPreference,
    UserProfile,
)

# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _risk(
    flag: bool,
    severity: Severity = Severity.NONE,
    reason: str = "",
) -> RiskSignal:
    """Build a RiskSignal for test setup."""
    return RiskSignal(flag=flag, severity=severity, reason=reason)


def _profile(lang: Lang) -> UserProfile:
    """Build a valid UserProfile for test setup."""
    return UserProfile(
        goals=["reduce screen time"],
        interests=["reading"],
        constraints=Constraints(
            available_minutes=30,
            energy=EnergyLevel.MEDIUM,
            place=Place.HOME,
            social=SocialPreference.SOLO,
        ),
        lang=lang,
    )


# ---------------------------------------------------------------------------
# 1. route_after_analyst — three outcomes
# ---------------------------------------------------------------------------


def test_route_after_analyst_returns_derivation_when_risk_flag_true():
    # Arrange
    state: CoachState = {"risk": _risk(flag=True, severity=Severity.HIGH)}

    # Act
    result = route_after_analyst(state)

    # Assert
    assert result == "derivation"


def test_route_after_analyst_returns_continue_when_risk_flag_false():
    # Arrange
    state: CoachState = {"risk": _risk(flag=False)}

    # Act
    result = route_after_analyst(state)

    # Assert
    assert result == "continue"


def test_route_after_analyst_returns_continue_when_no_risk_key():
    # Arrange – degraded state: no "risk" entry at all
    state: CoachState = {}

    # Act
    result = route_after_analyst(state)

    # Assert
    assert result == "continue"


# ---------------------------------------------------------------------------
# 2. Severity → ResourceType mapping (parametrized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("severity", "expected_resource"),
    [
        (Severity.HIGH, ResourceType.CRISIS_SUPPORT),
        (Severity.MEDIUM, ResourceType.MENTAL_HEALTH),
        (Severity.LOW, ResourceType.GENERAL),
        (Severity.NONE, ResourceType.GENERAL),
    ],
)
def test_derivation_severity_maps_to_correct_resource_type(
    severity: Severity, expected_resource: ResourceType
) -> None:
    # Arrange
    state: CoachState = {
        "risk": _risk(flag=True, severity=severity),
        "profile": _profile(Lang.ES),
    }

    # Act
    result = derivation(state)

    # Assert
    assert "derivation" in result
    assert result["derivation"].resource_type == expected_resource  # type: ignore[index]


# ---------------------------------------------------------------------------
# 3. Defensive guard of derivation
# ---------------------------------------------------------------------------


def test_derivation_returns_errors_and_no_derivation_key_when_no_risk_key():
    # Arrange – state completely missing the "risk" key
    state: CoachState = {}

    # Act
    result = derivation(state)

    # Assert
    assert "errors" in result
    assert len(result["errors"]) > 0  # type: ignore[typeddict-item]
    assert "derivation" not in result


def test_derivation_returns_errors_and_no_derivation_key_when_risk_flag_false():
    # Arrange – risk present but flag is False (node should not have been reached)
    state: CoachState = {"risk": _risk(flag=False, severity=Severity.LOW)}

    # Act
    result = derivation(state)

    # Assert
    assert "errors" in result
    assert len(result["errors"]) > 0  # type: ignore[typeddict-item]
    assert "derivation" not in result


# ---------------------------------------------------------------------------
# 4. Language selection ES / EN / default fallback
# ---------------------------------------------------------------------------


def test_derivation_message_in_spanish_when_lang_es():
    # Arrange
    state: CoachState = {
        "risk": _risk(flag=True, severity=Severity.LOW),
        "profile": _profile(Lang.ES),
    }

    # Act
    result = derivation(state)

    # Assert
    assert "Gracias por compartir" in result["derivation"].message  # type: ignore[index]


def test_derivation_message_in_english_when_lang_en():
    # Arrange
    state: CoachState = {
        "risk": _risk(flag=True, severity=Severity.LOW),
        "profile": _profile(Lang.EN),
    }

    # Act
    result = derivation(state)

    # Assert
    assert "Thank you for sharing" in result["derivation"].message  # type: ignore[index]


def test_derivation_defaults_to_spanish_when_no_profile():
    # Arrange – state with no "profile" key; node must fall back to Lang.ES
    state: CoachState = {"risk": _risk(flag=True, severity=Severity.LOW)}

    # Act
    result = derivation(state)

    # Assert
    assert "Gracias por compartir" in result["derivation"].message  # type: ignore[index]


# ---------------------------------------------------------------------------
# 5. No-digits invariant (parametrized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reason",
    [
        "",
        "ansiedad general",
        "ansiedad desde hace 3 semanas, llama al 112",
        "pensamientos negativos en 2025",
        "siento que no puedo más",
        "llamar al 900 123 456 urgente",
    ],
)
def test_derivation_message_contains_no_digits(reason: str) -> None:
    # Arrange – reason may contain digits; the node must strip them all
    state: CoachState = {
        "risk": _risk(flag=True, severity=Severity.MEDIUM, reason=reason),
        "profile": _profile(Lang.ES),
    }

    # Act
    result = derivation(state)

    # Assert
    message: str = result["derivation"].message  # type: ignore[index]
    assert not any(c.isdigit() for c in message)