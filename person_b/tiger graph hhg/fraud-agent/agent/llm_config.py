"""
Provider abstraction and configuration for Real and Mock LLMs.
Supports OpenAI, Anthropic, and explicit Mock modes via environment variables.
"""

import os
from dataclasses import dataclass
from typing import Optional, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class LLMConfig:
    provider: str  # "openai", "anthropic", "mock"
    model: str
    api_key: Optional[str] = None
    temperature: float = 0.0
    max_tokens: int = 2048


def get_llm_config(provider: Optional[str] = None) -> LLMConfig:
    """
    Load LLM configuration from environment variables.

    Rules:
    - Supported providers: 'openai', 'anthropic', 'mock'.
    - Provider must be specified explicitly (either via `provider` parameter or `LLM_PROVIDER` env var).
    - NEVER silently fall back to mock when a live provider is selected but its API key is missing.
    - Mock mode must only be selected explicitly.
    """
    selected_provider = provider
    if not selected_provider:
        selected_provider = os.getenv("LLM_PROVIDER")

    if not selected_provider or not selected_provider.strip():
        raise ValueError(
            "LLM_PROVIDER environment variable is not set. "
            "Must be explicitly set to 'openai', 'anthropic', or 'mock'."
        )

    prov = selected_provider.strip().lower()

    # Temperature and max tokens
    try:
        temp_str = os.getenv("LLM_TEMPERATURE", "0.0")
        temperature = float(temp_str)
    except (ValueError, TypeError):
        temperature = 0.0

    try:
        max_tokens_str = os.getenv("LLM_MAX_TOKENS", "2048")
        max_tokens = int(max_tokens_str)
    except (ValueError, TypeError):
        max_tokens = 2048

    if prov == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or not api_key.strip():
            raise ValueError(
                "OPENAI_API_KEY is missing or empty. Live provider 'openai' was selected, "
                "so a valid API key is required. Silent fallback to mock is prohibited."
            )
        model = os.getenv("OPENAI_MODEL", "gpt-4o")
        return LLMConfig(
            provider="openai",
            model=model,
            api_key=api_key.strip(),
            temperature=temperature,
            max_tokens=max_tokens,
        )

    elif prov == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key or not api_key.strip():
            raise ValueError(
                "ANTHROPIC_API_KEY is missing or empty. Live provider 'anthropic' was selected, "
                "so a valid API key is required. Silent fallback to mock is prohibited."
            )
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        return LLMConfig(
            provider="anthropic",
            model=model,
            api_key=api_key.strip(),
            temperature=temperature,
            max_tokens=max_tokens,
        )

    elif prov == "mock":
        return LLMConfig(
            provider="mock",
            model="mock-investigator-v1",
            api_key=None,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    else:
        raise ValueError(
            f"Unsupported LLM_PROVIDER '{prov}'. Supported providers are: 'openai', 'anthropic', 'mock'."
        )


def create_llm(config: Optional[LLMConfig] = None, **kwargs: Any) -> Any:
    """
    Instantiate the appropriate LangChain chat model or mock model based on LLMConfig.
    """
    if config is None:
        config = get_llm_config()

    if config.provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            raise ImportError("langchain-openai is required for OpenAI provider. Install langchain-openai.") from e

        return ChatOpenAI(
            model=config.model,
            api_key=config.api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            **kwargs,
        )

    elif config.provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as e:
            raise ImportError("langchain-anthropic is required for Anthropic provider. Install langchain-anthropic.") from e

        return ChatAnthropic(
            model_name=config.model,
            api_key=config.api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            **kwargs,
        )

    elif config.provider == "mock":
        from agent.llm_engine import MockInvestigatorLLM
        return MockInvestigatorLLM()

    raise ValueError(f"Unknown provider: {config.provider}")
