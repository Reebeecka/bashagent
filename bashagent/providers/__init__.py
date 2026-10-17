"""Provider implementations behind one protocol."""

from bashagent.providers.base import (
    CompletionRequest,
    Provider,
    ProviderError,
    RawResponse,
    UnknownProviderError,
)
from bashagent.providers.fake import FakeProvider
from bashagent.providers.openai import MissingAPIKeyError, OpenAIProvider

__all__ = [
    "CompletionRequest",
    "FakeProvider",
    "MissingAPIKeyError",
    "OpenAIProvider",
    "Provider",
    "ProviderError",
    "RawResponse",
    "UnknownProviderError",
    "get_provider",
]


def get_provider(name: str, *, model: str) -> Provider:
    if name == "fake":
        return FakeProvider()
    if name == "openai":
        return OpenAIProvider(model=model)
    raise UnknownProviderError(name)
