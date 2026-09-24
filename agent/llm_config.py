"""
Provider abstraction and configuration for Real and Mock LLMs.
Supports Vertex AI, OpenAI, Anthropic, and explicit Mock modes via environment variables.
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
    provider: str  # "vertex", "openai", "anthropic", "mock"
    model: str
    api_key: Optional[str] = None
    project: Optional[str] = None
    location: Optional[str] = None
    credentials: Optional[Any] = None
    temperature: float = 0.0
    max_tokens: int = 2048

    def __repr__(self) -> str:
        masked_key = "***" if self.api_key else None
        return (
            f"LLMConfig(provider={self.provider!r}, model={self.model!r}, "
            f"api_key={masked_key!r}, project={self.project!r}, "
            f"location={self.location!r}, temperature={self.temperature}, "
            f"max_tokens={self.max_tokens})"
        )

    def __str__(self) -> str:
        return self.__repr__()


def get_llm_config(provider: Optional[str] = None) -> LLMConfig:
    """
    Load LLM configuration from environment variables.
    
    Rules:
    - Supported providers: 'openrouter', 'vertex', 'openai', 'anthropic', 'mock'.
    - Provider must be specified explicitly (either via `provider` parameter or `LLM_PROVIDER` env var).
    - NEVER silently fall back to mock when a live provider is selected but its configuration is missing.
    - Mock mode must only be selected explicitly.
    """
    selected_provider = provider
    if not selected_provider:
        selected_provider = os.getenv("LLM_PROVIDER")

    if not selected_provider or not selected_provider.strip():
        raise ValueError(
            "LLM_PROVIDER environment variable is not set. "
            "Must be explicitly set to 'openrouter', 'vertex', 'openai', 'anthropic', or 'mock'."
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

    if prov == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key or not api_key.strip():
            raise ValueError(
                "OPENROUTER_API_KEY is missing or empty. Live provider 'openrouter' was selected, "
                "so a valid API key is required. Silent fallback to mock is prohibited."
            )
        model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
        if not model or not model.strip():
            model = "google/gemini-2.5-flash"

        return LLMConfig(
            provider="openrouter",
            model=model.strip(),
            api_key=api_key.strip(),
            temperature=temperature,
            max_tokens=max_tokens,
        )

    elif prov == "vertex":
        vertex_api_key = os.getenv("VERTEX_API_KEY")
        if vertex_api_key and vertex_api_key.strip():
            api_key = vertex_api_key.strip()
        else:
            api_key = None

        project = os.getenv("VERTEX_PROJECT")
        if not project or not project.strip():
            if not api_key:
                project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
                if not project or not project.strip():
                    raise ValueError(
                        "GOOGLE_CLOUD_PROJECT is missing or empty. Live provider 'vertex' was selected, "
                        "so a valid Google Cloud project is required. Silent fallback to mock is prohibited."
                    )
            else:
                project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")

        model = os.getenv("VERTEX_MODEL")
        if not model or not model.strip():
            raise ValueError(
                "VERTEX_MODEL is missing or empty. Live provider 'vertex' was selected, "
                "so a valid model name is required (e.g. 'gemini-1.5-flash'). Silent fallback to mock is prohibited."
            )

        location = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("VERTEX_LOCATION", "us-central1")

        return LLMConfig(
            provider="vertex",
            model=model.strip(),
            api_key=api_key,
            project=project.strip() if project and project.strip() else None,
            location=location.strip() if location else "us-central1",
            temperature=temperature,
            max_tokens=max_tokens,
        )

    elif prov == "openai":
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

    elif prov == "gemini":
        raise ValueError(
            "Provider 'gemini' (direct Google AI Studio inference) has been removed. "
            "Please set LLM_PROVIDER=vertex and configure GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, and VERTEX_MODEL."
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
            f"Unsupported LLM_PROVIDER '{prov}'. Supported providers are: 'openrouter', 'vertex', 'openai', 'anthropic', 'mock'."
        )


def create_llm(config: Optional[LLMConfig] = None, **kwargs: Any) -> Any:
    """
    Instantiate the appropriate LangChain chat model or mock model based on LLMConfig.
    """
    if config is None:
        config = get_llm_config()

    if config.provider == "vertex":
        api_key = kwargs.get("api_key") or config.api_key
        if api_key:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
            except ImportError as e:
                raise ImportError(
                    "langchain-google-genai is required for Vertex AI Express Mode API-key authentication. "
                    "Install langchain-google-genai."
                ) from e

            model_kwargs = dict(kwargs)
            model_kwargs.pop("api_key", None)
            model_name = model_kwargs.pop("model", model_kwargs.pop("model_name", config.model))
            explicit_project = model_kwargs.pop(
                "project",
                os.getenv("VERTEX_PROJECT") or (None if os.getenv("VERTEX_API_KEY") else config.project),
            )
            location = model_kwargs.pop("location", config.location or "us-central1")
            temperature = model_kwargs.pop("temperature", config.temperature)
            max_output_tokens = model_kwargs.pop(
                "max_output_tokens",
                model_kwargs.pop("max_tokens", config.max_tokens),
            )

            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                llm = ChatGoogleGenerativeAI(
                    model=model_name,
                    api_key=api_key,
                    vertexai=True,
                    project=explicit_project,
                    location=location if explicit_project else None,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    **model_kwargs,
                )
                try:
                    from google.genai import Client
                    client_kwargs = {"vertexai": True, "api_key": api_key}
                    if explicit_project:
                        client_kwargs["project"] = explicit_project
                        if location:
                            client_kwargs["location"] = location
                    llm.client = Client(**client_kwargs)
                except Exception:
                    pass
                return llm

        try:
            from langchain_google_vertexai import ChatVertexAI
        except ImportError as e:
            raise ImportError(
                "langchain-google-vertexai is required for Vertex AI provider. "
                "Install langchain-google-vertexai."
            ) from e

        model_kwargs = dict(kwargs)
        project = model_kwargs.pop("project", config.project)
        location = model_kwargs.pop("location", config.location or "us-central1")
        credentials = model_kwargs.pop("credentials", config.credentials)
        temperature = model_kwargs.pop("temperature", config.temperature)
        max_output_tokens = model_kwargs.pop(
            "max_output_tokens",
            model_kwargs.pop("max_tokens", config.max_tokens),
        )

        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            return ChatVertexAI(
                model_name=config.model,
                project=project,
                location=location,
                credentials=credentials,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                **model_kwargs,
            )

    elif config.provider == "openrouter":
        try:
            from langchain_openrouter import ChatOpenRouter
        except ImportError as e:
            raise ImportError(
                "langchain-openrouter is required for OpenRouter provider. Install langchain-openrouter."
            ) from e

        model_kwargs = dict(kwargs)
        model_name = model_kwargs.pop("model", model_kwargs.pop("model_name", config.model))
        temperature = model_kwargs.pop("temperature", config.temperature)
        max_tokens = model_kwargs.pop("max_tokens", config.max_tokens)
        api_key = model_kwargs.pop("api_key", config.api_key)

        return ChatOpenRouter(
            model=model_name,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            **model_kwargs,
        )

    elif config.provider == "openai":
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

    elif config.provider == "gemini":
        raise ValueError(
            "Provider 'gemini' (direct Google AI Studio inference) has been removed. "
            "Please use provider 'vertex' with ChatVertexAI."
        )

    elif config.provider == "mock":
        from agent.llm_engine import MockInvestigatorLLM
        return MockInvestigatorLLM()

    raise ValueError(f"Unknown provider: {config.provider}")

