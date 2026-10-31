
import argparse

from .runner import run_palette


def main():

    parser = argparse.ArgumentParser(
        description="Palette Multi-Agent Framework"
    )

    parser.add_argument(
        "--config",
        help="Path to Palette YAML configuration",
        default=None
    )

    args = parser.parse_args()

    run_palette(args.config)


if __name__ == "__main__":
    main()
