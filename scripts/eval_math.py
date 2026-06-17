"""Math evaluation entry point.

Planned stages:
- Stage 1: --test_evaluator and --audit_data
- Stage 3: --config for formal baseline evaluation

Implementation will be added in the corresponding stages.
"""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate NumberTheory-Qwen model outputs.")
    parser.add_argument("--test_evaluator", action="store_true", help="Test Math-Verify integration.")
    parser.add_argument("--audit_data", action="store_true", help="Audit evaluation data fields.")
    parser.add_argument("--config", type=str, help="Path to evaluation config.")
    parser.parse_args()
    raise NotImplementedError("Evaluation logic will be implemented in Stage 1 and Stage 3.")


if __name__ == "__main__":
    main()
