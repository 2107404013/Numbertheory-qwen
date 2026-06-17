"""Data preparation entry point.

Planned stages:
- Stage 1: --mode inspect_public
- Stage 2: --mode build_eval
- Stage 4: --mode build_train

Implementation will be added in the corresponding stages.
"""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare NumberTheory-Qwen datasets.")
    parser.add_argument(
        "--mode",
        choices=["inspect_public", "build_eval", "build_train"],
        required=True,
        help="Data preparation mode implemented in later stages.",
    )
    args = parser.parse_args()
    raise NotImplementedError(f"--mode {args.mode} will be implemented in its planned stage.")


if __name__ == "__main__":
    main()
