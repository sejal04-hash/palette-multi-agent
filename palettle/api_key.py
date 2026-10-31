
import os
from dotenv import load_dotenv


# Load .env from the current user's working directory.
# Users can also set environment variables directly.
load_dotenv()


def get_api_key(provider):

    key_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }

    env_name = key_map.get(provider)

    if env_name is None:
        return None

    api_key = os.getenv(env_name)

    if not api_key:
        raise ValueError(
            f"{env_name} is required for provider '{provider}'."
        )

    return api_key
