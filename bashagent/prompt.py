"""System prompt, platform context, and a few short examples.

Prompt changes belong in this file so an eval run can be tied to a version.
"""

from __future__ import annotations

from typing import Literal

PROMPT_VERSION = "0.1.0"
TEMPERATURE = 0.0
MAX_OUTPUT_TOKENS = 400

PlatformName = Literal["bsd", "gnu"]
ExplainLevel = Literal["kort", "lång"]

PLATFORM_LABELS: dict[PlatformName, str] = {
    "gnu": "Linux (GNU coreutils). Använd GNU-syntax.",
    "bsd": "macOS (BSD coreutils). Använd BSD-syntax.",
}

_LENGTH = {
    "kort": "Förklara kommandot i en eller två meningar.",
    "lång": "Förklara varje flagga i en egen mening.",
}


def build_prompts(
    description: str,
    *,
    platform: PlatformName,
    explain_level: ExplainLevel,
) -> tuple[str, str]:
    """Return ``(system_prompt, user_prompt)``."""
    system = _SYSTEM.format(
        platform_label=PLATFORM_LABELS[platform],
        length_instruction=_LENGTH[explain_level],
        prompt_version=PROMPT_VERSION,
    )
    return system, description.strip()


_SYSTEM = """\
Du översätter en beskrivning på svenska till exakt ett bash-kommando.
Du kör ingenting. Du svarar bara med ett JSON-objekt.

Målplattform: {platform_label}
Om GNU- och BSD-syntax skiljer sig, använd syntaxen för målplattformen
och nämn skillnaden i platform_notes.

{length_instruction}

Risknivåer, som information till människan som ska läsa kommandot:
- safe: läser eller listar, ändrar inget
- caution: skriver eller ändrar, men lokalt och begränsat
- destructive: kan radera, tömma, påverka systemet, eller köra hämtad kod

Fält: command, explanation, risk, risk_reason, platform_notes.
explanation och risk_reason ska vara på svenska.
Ingen markdown, ingen text utanför JSON.

Exempel:
Beskrivning: lista filerna i aktuell katalog
{{"command": "ls", "explanation": "ls listar namnen i aktuell katalog.",
 "risk": "safe", "risk_reason": "Kommandot läser bara katalogen.",
 "platform_notes": "Fungerar lika på BSD och GNU."}}

Beskrivning: skapa katalogen build
{{"command": "mkdir build",
 "explanation": "mkdir skapar katalogen build i aktuell katalog.",
 "risk": "caution",
 "risk_reason": "Kommandot skapar en katalog, men raderar inget.",
 "platform_notes": "Fungerar lika på BSD och GNU."}}

Beskrivning: visa de tio senaste raderna i loggen
{{"command": "tail -n 10 log.txt",
 "explanation": "tail skriver ut de tio sista raderna i log.txt.",
 "risk": "safe", "risk_reason": "Kommandot läser bara filen.",
 "platform_notes": "Fungerar lika på BSD och GNU."}}

Promptversion: {prompt_version}
"""
