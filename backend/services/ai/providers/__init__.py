from services.ai.providers.base import AIProvider, AIProviderConfigurationError, AIProviderError

__all__ = [
    "AIProvider",
    "AIProviderConfigurationError",
    "AIProviderError",
    "OpenAIProvider",
]


def __getattr__(name: str):
    if name == "OpenAIProvider":
        from services.ai.providers.openai_provider import OpenAIProvider
        return OpenAIProvider
    raise AttributeError(name)
