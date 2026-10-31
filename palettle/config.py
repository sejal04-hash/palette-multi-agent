
from pathlib import Path
import yaml


def get_default_config_path():

    config_dir = Path.home() / ".palette"

    config_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    return config_dir / "config.yaml"


def load_config(path=None):

    if path is None:
        path = get_default_config_path()

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}"
        )

    with open(path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise ValueError("Invalid YAML configuration.")

    return config
