import os

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from models.models import AIConfiguration
from services.ai.providers.base import AIProviderConfigurationError
from services.ai.providers.openai_provider import OpenAIProvider


def default_budget() -> float:
    return float(os.getenv("DEFAULT_MAX_PROJECT_BUDGET", "5.00"))


def default_wait_minutes() -> int:
    return int(os.getenv("DEFAULT_MAX_WAIT_MINUTES", "20"))


def get_ai_configuration(db: Session) -> AIConfiguration:
    values = {
        "id": 1,
        "provider": os.getenv("AI_PROVIDER", "openai"),
        "model": os.getenv("OPENAI_MODEL", "gpt-5"),
        "image_model": os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
        "default_budget": default_budget(),
        "default_wait_minutes": default_wait_minutes(),
    }
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = postgresql_insert(AIConfiguration).values(**values)
    elif dialect == "sqlite":
        statement = sqlite_insert(AIConfiguration).values(**values)
    else:
        configuration = db.get(AIConfiguration, 1)
        if configuration is None:
            configuration = AIConfiguration(**values)
            db.add(configuration)
            db.flush()
        return configuration
    db.execute(
        statement.on_conflict_do_nothing(index_elements=[AIConfiguration.id])
    )
    configuration = db.get(AIConfiguration, 1)
    if configuration is None:
        raise RuntimeError("AI configuration could not be initialized.")
    return configuration


def create_ai_provider(configuration: AIConfiguration) -> OpenAIProvider:
    if configuration.provider != "openai":
        raise AIProviderConfigurationError(
            f"AI provider '{configuration.provider}' is not supported."
        )
    return OpenAIProvider(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model=configuration.model,
        image_model=configuration.image_model,
    )
