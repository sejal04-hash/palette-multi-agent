from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from .api_key import get_api_key

from .error import (
    APIKeyError,
    ProviderError,
    QuotaError,
    ModelNotFoundError
)


# ==========================================
# CREATE MODEL
# ==========================================

def create_model(config):

    provider = config["provider"]
    model = config["model"]
    temperature = config.get("temperature", 0.7)

    try:

        # -------------------------
        # Ollama
        # -------------------------
        if provider == "ollama":

            return ChatOllama(
                model=model,
                temperature=temperature
            )

        # -------------------------
        # OpenAI
        # -------------------------
        elif provider == "openai":

            try:
                api_key = get_api_key("openai")

            except Exception as e:
                raise APIKeyError(
                    "OpenAI API key is missing."
                ) from e

            return ChatOpenAI(
                model=model,
                temperature=temperature,
                api_key=api_key
            )

        # -------------------------
        # Anthropic
        # -------------------------
        elif provider == "anthropic":

            try:
                api_key = get_api_key("anthropic")

            except Exception as e:
                raise APIKeyError(
                    "Anthropic API key is missing."
                ) from e

            return ChatAnthropic(
                model=model,
                temperature=temperature,
                api_key=api_key
            )

        # -------------------------
        # Unsupported provider
        # -------------------------
        else:

            raise ProviderError(
                f"Unsupported provider: {provider}"
            )

    except (APIKeyError, ProviderError):
        raise

    except Exception as e:

        raise ProviderError(
            f"Could not create model '{model}' "
            f"for provider '{provider}'."
        ) from e


# ==========================================
# INVOKE MODEL
# ==========================================

def invoke_model(model, prompt, provider, model_name):

    try:

        return model.invoke(prompt)

    except Exception as e:

        error_text = str(e).lower()
        error_type = type(e).__name__.lower()

        # ==================================
        # OPENAI
        # ==================================

        if provider == "openai":

            # Quota / Credits
            if (
                "insufficient_quota" in error_text
                or "credit_balance_exhausted" in error_text
            ):

                raise QuotaError(
                    f"OpenAI credits/quota are exhausted "
                    f"for model '{model_name}'."
                ) from e

            # API Key
            if (
                "invalid_api_key" in error_text
                or "authentication" in error_text
                or "401" in error_text
            ):

                raise APIKeyError(
                    "OpenAI API key is missing or invalid."
                ) from e

            # Other OpenAI error
            raise ProviderError(
                f"OpenAI request failed "
                f"for model '{model_name}'."
            ) from e


        # ==================================
        # OLLAMA
        # ==================================

        elif provider == "ollama":

            # Ollama server not running
            if (
                "connection refused" in error_text
                or "connecterror" in error_type
                or "10061" in error_text
            ):

                raise ProviderError(
                    "Ollama server is not running. "
                    "Start it using: ollama serve"
                ) from e

            # Model not found
            if (
                "not found" in error_text
                or "404" in error_text
            ):

                raise ModelNotFoundError(
                    f"Ollama model '{model_name}' "
                    f"was not found."
                ) from e

            # Other Ollama error
            raise ProviderError(
                f"Ollama request failed "
                f"for model '{model_name}'."
            ) from e


        # ==================================
        # ANTHROPIC
        # ==================================

        elif provider == "anthropic":

            # Authentication
            if (
                "authentication" in error_text
                or "401" in error_text
                or "api key" in error_text
            ):

                raise APIKeyError(
                    "Anthropic API key is missing or invalid."
                ) from e

            # Rate limit / quota
            if (
                "rate limit" in error_text
                or "quota" in error_text
            ):

                raise QuotaError(
                    f"Anthropic quota/rate limit reached "
                    f"for model '{model_name}'."
                ) from e

            # Other Anthropic error
            raise ProviderError(
                f"Anthropic request failed "
                f"for model '{model_name}'."
            ) from e


        # ==================================
        # UNKNOWN PROVIDER
        # ==================================

        else:

            raise ProviderError(
                f"Model request failed "
                f"for provider '{provider}'."
            ) from e