"""Math evaluation entry point.

Implemented in Stage 1:
- --test_evaluator
- --audit_data

Planned later:
- Stage 3: --config for formal baseline evaluation
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


BOXED_PATTERN = re.compile(r"\\boxed\s*\{")
PROBLEM_FIELDS = ("problem", "question", "prompt")
ANSWER_FIELDS = ("answer", "final_answer", "ground_truth", "gt")


def _load_math_verify() -> tuple[Any, Any]:
    try:
        from math_verify import parse, verify
    except ImportError as exc:
        raise RuntimeError(
            "math-verify is not installed. Install requirements on the remote ntqwen environment first."
        ) from exc
    return parse, verify


def _parse_answer(value: Any) -> Any:
    parse, _ = _load_math_verify()
    return parse(str(value))


def final_answer_equivalent(gold: Any, prediction: Any) -> bool:
    parse, verify = _load_math_verify()
    return bool(verify(parse(str(gold)), parse(str(prediction))))


def has_boxed_answer(text: Any) -> bool:
    return bool(BOXED_PATTERN.search(str(text)))


def _first_present(row: dict[str, Any], candidates: tuple[str, ...]) -> Any:
    for field in candidates:
        if field in row and row[field] not in (None, ""):
            return row[field]
    return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_no}: {path}") from exc
    return rows


def test_evaluator() -> None:
    cases = [
        {"gold": "2", "prediction": r"\boxed{2}", "expected": True},
        {"gold": "3", "prediction": r"\boxed{4}", "expected": False},
    ]

    results = []
    for case in cases:
        matched = final_answer_equivalent(case["gold"], case["prediction"])
        results.append({**case, "matched": matched})

    print(json.dumps({"math_verify_smoke_test": results}, ensure_ascii=False, indent=2))


def audit_data(args: argparse.Namespace) -> None:
    data_path = Path(args.data_file)
    rows = _read_jsonl(data_path)
    counters: Counter[str] = Counter()
    fields: Counter[str] = Counter()
    parse_failures: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        fields.update(row.keys())
        problem = row.get(args.problem_field) if args.problem_field else _first_present(row, PROBLEM_FIELDS)
        answer = row.get(args.answer_field) if args.answer_field else _first_present(row, ANSWER_FIELDS)

        if problem is None:
            counters["missing_problem"] += 1
        if answer is None:
            counters["missing_answer"] += 1
            continue

        if has_boxed_answer(answer):
            counters["boxed_answer"] += 1

        try:
            parsed = _parse_answer(answer)
            if parsed:
                counters["extraction_success"] += 1
            else:
                counters["extraction_empty"] += 1
        except Exception as exc:  # Math-Verify can raise parser-specific exceptions.
            counters["extraction_error"] += 1
            if len(parse_failures) < args.max_error_examples:
                parse_failures.append({"index": index, "answer": answer, "error": repr(exc)})

    total = len(rows)
    summary = {
        "data_file": str(data_path),
        "total_rows": total,
        "fields": dict(fields),
        "missing_problem": counters["missing_problem"],
        "missing_answer": counters["missing_answer"],
        "boxed_answer_rate": counters["boxed_answer"] / total if total else 0.0,
        "extraction_success_rate": counters["extraction_success"] / total if total else 0.0,
        "extraction_empty": counters["extraction_empty"],
        "extraction_error": counters["extraction_error"],
        "parse_failure_examples": parse_failures,
    }

    text = json.dumps(summary, ensure_ascii=False, indent=2)
    print(text)

    if args.output_path:
        output_path = Path(args.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate NumberTheory-Qwen model outputs.")
    parser.add_argument("--test_evaluator", action="store_true", help="Test Math-Verify integration.")
    parser.add_argument("--audit_data", action="store_true", help="Audit evaluation data fields.")
    parser.add_argument("--config", type=str, help="Path to evaluation config.")
    parser.add_argument("--data_file", default="data/processed/public_number_theory_eval.jsonl")
    parser.add_argument("--problem_field", default=None)
    parser.add_argument("--answer_field", default=None)
    parser.add_argument("--output_path", default=None)
    parser.add_argument("--max_error_examples", type=int, default=5)
    args = parser.parse_args()

    if args.test_evaluator:
        test_evaluator()
        return

    if args.audit_data:
        audit_data(args)
        return

    if args.config:
        raise NotImplementedError("--config formal evaluation will be implemented in Stage 3.")

    parser.error("Choose one of --test_evaluator, --audit_data, or --config.")


if __name__ == "__main__":
    main()
