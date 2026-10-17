"""Scripted provider for tests and development. Makes no network call.

The answers are fixtures for the pipeline, not a model. A match against them
is not a measurement.
"""

from __future__ import annotations

from bashagent.providers.base import CompletionRequest, RawResponse
from bashagent.schema import RiskName, Suggestion


class FakeProvider:
    def complete(self, request: CompletionRequest) -> RawResponse:
        suggestion = scripted_suggestion(request.user_prompt, request.system_prompt)
        text = suggestion.model_dump_json()
        return RawResponse(
            text=text,
            input_tokens=_estimate(request.system_prompt) + _estimate(request.user_prompt),
            output_tokens=_estimate(text),
            latency_ms=0.0,
            model=request.model,
        )


def scripted_suggestion(user_prompt: str, system_prompt: str) -> Suggestion:
    text = user_prompt.lower()
    gnu = _target_is_gnu(system_prompt)
    if "pdf" in text:
        return _suggestion(
            "find . -type f -name '*.pdf' -size +10M",
            "find . söker rekursivt från aktuell katalog. -type f begränsar till filer, "
            "-name '*.pdf' matchar pdf-filer och -size +10M behåller de som är "
            "större än 10 megabyte.",
            "safe",
            "Kommandot läser bara filsystemet.",
            "Fungerar lika på BSD och GNU.",
        )
    if "404" in text:
        return _suggestion(
            "grep -c 404 access.log",
            "grep -c räknar raderna i access.log som innehåller 404.",
            "safe",
            "Kommandot läser bara filen.",
            "Fungerar lika på BSD och GNU.",
        )
    if ".sh" in text or "körbar" in text:
        return _suggestion(
            "find . -type f -name '*.sh' -exec chmod +x {} +",
            "find letar upp filer vars namn slutar på .sh och chmod +x gör dem körbara.",
            "caution",
            "Kommandot ändrar rättigheter, men raderar inget.",
            "Fungerar lika på BSD och GNU.",
        )
    if "foo" in text and "bar" in text:
        if gnu:
            command = "sed -i 's/foo/bar/' notes.txt"
            notes = "GNU tar inget extra argument efter -i. BSD kräver sed -i ''."
        else:
            command = "sed -i '' 's/foo/bar/' notes.txt"
            notes = "BSD kräver ett tomt argument efter -i. GNU skriver sed -i utan det."
        return _suggestion(
            command,
            "sed byter ut foo mot bar direkt i notes.txt.",
            "caution",
            "Kommandot skriver om filen på plats. Originalet utan säkerhetskopia försvinner.",
            notes,
        )
    if ".tmp" in text or "tmp-fil" in text:
        return _suggestion(
            "find . -type f -name '*.tmp' -delete",
            "find letar upp .tmp-filer och -delete tar bort dem. Det går inte att ångra.",
            "destructive",
            "Kommandot raderar filer.",
            "Fungerar lika på BSD och GNU.",
        )
    return _suggestion(
        "ls",
        "ls listar filerna i aktuell katalog. "
        "Fake-providern har inget skriptat svar för den här beskrivningen.",
        "safe",
        "Kommandot läser bara katalogen.",
        "Fungerar lika på BSD och GNU.",
    )


def _suggestion(
    command: str,
    explanation: str,
    risk: RiskName,
    risk_reason: str,
    platform_notes: str,
) -> Suggestion:
    return Suggestion(
        command=command,
        explanation=explanation,
        risk=risk,
        risk_reason=risk_reason,
        platform_notes=platform_notes,
    )


def _target_is_gnu(system_prompt: str) -> bool:
    for line in system_prompt.splitlines():
        if line.startswith("Målplattform:"):
            return "GNU" in line
    return True


def _estimate(text: str) -> int:
    return max(1, len(text) // 4)
