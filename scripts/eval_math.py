"""Math scoring utilities for NumberTheory-Qwen.

This script does not load models or run inference.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any


RESULTS_DIR = Path("results")
DEFAULT_AUDIT_FILE = Path("data/processed/public_number_theory_eval.jsonl")

ANSWER_TRIGGER_PATTERNS = [
    r"\u7b54\u6848\u4e3a[:\uff1a]?\s*([^\u3002\n\uff1b;]+)",
    r"\u6700\u7ec8\u7b54\u6848\u662f[:\uff1a]?\s*([^\u3002\n\uff1b;]+)",
    r"\u6700\u7ec8\u7b54\u6848\u4e3a[:\uff1a]?\s*([^\u3002\n\uff1b;]+)",
]
CONCLUSION_PATTERNS = [
    r"\u56e0\u6b64[,，]?\s*([^\u3002\n\uff1b;]{1,80})",
    r"\u6240\u4ee5[,，]?\s*([^\u3002\n\uff1b;]{1,80})",
]


@dataclass
class MatchResult:
    matched: bool
    match_method: str


def extract_boxed_answer(text: Any) -> str | None:
    """Extract the last LaTeX \\boxed{...} answer without raising on malformed text."""
    if text is None:
        return None

    value = str(text)
    starts = [match.start() for match in re.finditer(r"\\boxed\s*\{", value)]
    if not starts:
        return None

    for start in reversed(starts):
        brace_start = value.find("{", start)
        if brace_start < 0:
            continue

        depth = 0
        chars: list[str] = []
        for char in value[brace_start:]:
            if char == "{":
                depth += 1
                if depth > 1:
                    chars.append(char)
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return "".join(chars).strip()
                if depth > 0:
                    chars.append(char)
            elif depth > 0:
                chars.append(char)

    return None


def extract_answer_candidates(text: Any) -> list[str]:
    if text is None:
        return []

    value = str(text)
    candidates: list[str] = []

    boxed = extract_boxed_answer(value)
    if boxed:
        candidates.append(boxed)

    for pattern in ANSWER_TRIGGER_PATTERNS + CONCLUSION_PATTERNS:
        for match in re.finditer(pattern, value):
            candidate = match.group(1).strip()
            if candidate:
                candidates.append(candidate)

    for lhs, rhs in re.findall(r"([A-Za-z0-9_\\^{}+\-*/().]+)\s*=\s*([^,，。\n\uff1b;]+)", value):
        if lhs and rhs:
            candidates.append(rhs.strip())

    if not candidates and value.strip():
        candidates.append(value.strip())

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = normalize_answer(candidate)
        if key and key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return deduped


def _replace_text_commands(text: str) -> str:
    previous = None
    current = text
    pattern = re.compile(r"\\text\s*\{([^{}]*)\}")
    while current != previous:
        previous = current
        current = pattern.sub(r"\1", current)
    return current


def _replace_frac(text: str) -> str:
    previous = None
    current = text
    pattern = re.compile(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}")
    while current != previous:
        previous = current
        current = pattern.sub(r"(\1)/(\2)", current)
    return current


def normalize_answer(ans: Any) -> str:
    if ans is None:
        return ""

    text = unicodedata.normalize("NFKC", str(ans))
    text = _replace_text_commands(text)
    text = _replace_frac(text)
    text = text.replace("\\left", "").replace("\\right", "")
    text = text.replace("\\,", "").replace("\\!", "")
    text = text.replace("$", "")
    text = text.replace("，", ",").replace("；", ",").replace("、", ",")
    text = re.sub(r"(?<=\d)\s*(\u548c|\u6216)\s*(?=\d)", ",", text)
    text = re.sub(r"\s+(\u548c|\u6216)\s+", ",", text)
    text = re.sub(r"[。.;:：]$", "", text.strip())
    text = re.sub(r"\s+", "", text)
    text = text.strip("{}[]()")
    return text


def _parse_math_verify(value: Any) -> Any:
    from math_verify import parse

    return parse(str(value))


def verify_with_math_verify(pred: Any, gold: Any) -> MatchResult:
    try:
        from math_verify import verify

        pred_parsed = _parse_math_verify(pred)
        gold_parsed = _parse_math_verify(gold)
        matched = bool(verify(pred_parsed, gold_parsed))
        return MatchResult(matched=matched, match_method="math_verify" if matched else "failed")
    except Exception:
        return MatchResult(matched=False, match_method="failed")


def _split_list_answer(value: Any) -> list[str]:
    text = normalize_answer(value)
    text = re.sub(r"\b(and|or)\b", ",", text, flags=re.IGNORECASE)
    text = re.sub(r"[{}]", "", text)
    text = text.replace("\u6216", ",").replace("\u548c", ",")
    text = re.sub(r"[A-Za-z]+=", "", text)
    parts = [part for part in re.split(r",|\|", text) if part]
    return sorted(parts)


def _fraction_value(value: Any) -> Fraction | None:
    text = normalize_answer(value)
    if "=" in text:
        text = text.split("=")[-1]
    try:
        return Fraction(text)
    except Exception:
        return None


def _sympy_equiv(pred: Any, gold: Any) -> bool:
    try:
        import sympy as sp

        pred_text = normalize_answer(pred).replace("^", "**")
        gold_text = normalize_answer(gold).replace("^", "**")
        pred_expr = sp.sympify(pred_text)
        gold_expr = sp.sympify(gold_text)
        return bool(sp.simplify(pred_expr - gold_expr) == 0)
    except Exception:
        return False


def _right_side_if_equation(value: Any) -> str | None:
    text = normalize_answer(value)
    if "=" not in text:
        return None
    return text.split("=")[-1]


def is_equiv(pred: Any, gold: Any) -> MatchResult:
    mv_result = verify_with_math_verify(pred, gold)
    if mv_result.matched:
        return mv_result

    pred_norm = normalize_answer(pred)
    gold_norm = normalize_answer(gold)
    if pred_norm and pred_norm == gold_norm:
        return MatchResult(True, "fallback_string")

    pred_list = _split_list_answer(pred)
    gold_list = _split_list_answer(gold)
    if pred_list and gold_list and pred_list == gold_list:
        return MatchResult(True, "fallback_list")

    pred_frac = _fraction_value(pred)
    gold_frac = _fraction_value(gold)
    if pred_frac is not None and gold_frac is not None and pred_frac == gold_frac:
        return MatchResult(True, "fallback_fraction")

    if _sympy_equiv(pred, gold):
        return MatchResult(True, "fallback_sympy")

    pred_rhs = _right_side_if_equation(pred)
    if pred_rhs and is_equiv(pred_rhs, gold).matched:
        return MatchResult(True, "fallback_equation_rhs")

    return MatchResult(False, "failed")


def classify_gold_answer(problem: Any, gold: Any) -> str:
    problem_text = str(problem or "")
    gold_text = str(gold or "").strip()
    combined = f"{problem_text}\n{gold_text}".lower()

    if not gold_text:
        return "empty_answer"
    if any(token in combined for token in ["\u8bc1\u660e", "prove", "show that", "proof"]):
        return "possible_proof"
    if any(token in combined for token in ["\u56fe", "image", "figure", "diagram", "shown below"]):
        return "possible_image_problem"
    if len(gold_text) > 220 or gold_text.count("\n") >= 2:
        return "long_solution_like_answer"
    if any(token in gold_text for token in ["\u65e0\u6cd5\u786e\u5b9a", "\u5f00\u653e", "depends", "\u4efb\u610f"]):
        return "unsupported_format"
    return "short_answer"


def classify_eval_case(pred: Any, gold: Any, model_output: Any) -> str:
    gold_type = classify_gold_answer("", gold)
    if gold_type != "short_answer":
        if gold_type == "empty_answer":
            return "possible_gold_error"
        return "unsuitable_for_rule_eval"

    candidates = extract_answer_candidates(model_output if model_output is not None else pred)
    if not candidates:
        return "extraction_error"

    for candidate in candidates:
        if is_equiv(candidate, gold).matched:
            return "correct"

    if extract_boxed_answer(model_output) is None:
        return "format_error"
    return "model_error"


def run_evaluator_tests() -> None:
    tests = [
        {"pred": "2 \u548c 3", "gold": "2,3", "expected": True},
        {"pred": "{2,3}", "gold": "2,3", "expected": True},
        {"pred": "x=2 \u6216 x=3", "gold": "2,3", "expected": True},
        {"pred": r"\frac{1}{2}", "gold": "1/2", "expected": True},
        {"pred": "0.5", "gold": "1/2", "expected": True},
        {"pred": "x^3+y^3+z^3=3xyz", "gold": "3xyz", "expected": True},
        {"pred": "1", "gold": "6", "expected": False},
        {"pred": "12", "gold": "12", "expected": True},
        {"pred": "-1", "gold": "1", "expected": False},
        {"pred": "n is even", "gold": "\u5076\u6570", "expected": False},
    ]

    rows = []
    for test in tests:
        result = is_equiv(test["pred"], test["gold"])
        rows.append(
            {
                **test,
                "actual": result.matched,
                "passed": result.matched == test["expected"],
                "match_method": result.match_method,
            }
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / "evaluator_test.json"
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")


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
                raise ValueError(f"Invalid JSONL at {path}:{line_no}") from exc
    return rows


def _shorten(value: Any, limit: int) -> str:
    text = str(value or "").replace("\n", " ")
    return text[:limit] + ("..." if len(text) > limit else "")


def audit_data(data_file: Path) -> None:
    rows = _read_jsonl(data_file)
    counts = {
        "total": len(rows),
        "short_answer_count": 0,
        "empty_answer_count": 0,
        "long_solution_like_answer_count": 0,
        "possible_proof_count": 0,
        "possible_image_problem_count": 0,
        "unsupported_format_count": 0,
        "suitable_for_rule_eval_count": 0,
    }
    examples: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        problem = row.get("problem") or row.get("question") or row.get("prompt") or ""
        answer = row.get("answer") or row.get("final_answer") or row.get("gold") or row.get("ground_truth") or ""
        label = classify_gold_answer(problem, answer)
        counts[f"{label}_count"] = counts.get(f"{label}_count", 0) + 1
        if label == "short_answer":
            counts["suitable_for_rule_eval_count"] += 1

        if len(examples) < 10:
            examples.append(
                {
                    "id": row.get("id", index),
                    "subject": row.get("subject") or row.get("domain") or row.get("category") or "",
                    "problem": _shorten(problem, 200),
                    "answer": answer,
                    "source": row.get("source", ""),
                    "difficulty": row.get("difficulty", ""),
                    "classify_gold_answer": label,
                }
            )

    lines = ["# Evaluator Audit", "", "## Summary", ""]
    for key, value in counts.items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Examples", ""])
    for example in examples:
        lines.append(f"### {example['id']}")
        lines.append(f"- subject: {example['subject']}")
        lines.append(f"- problem: {example['problem']}")
        lines.append(f"- answer: {example['answer']}")
        lines.append(f"- source: {example['source']}")
        lines.append(f"- difficulty: {example['difficulty']}")
        lines.append(f"- classify_gold_answer: {example['classify_gold_answer']}")
        lines.append("")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / "evaluator_audit.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate NumberTheory-Qwen answers.")
    parser.add_argument("--test_evaluator", action="store_true", help="Run evaluator unit tests.")
    parser.add_argument(
        "--audit_data",
        nargs="?",
        const=str(DEFAULT_AUDIT_FILE),
        default=None,
        help="Audit a JSONL evaluation file.",
    )
    parser.add_argument("--config", default=None, help="Stage 3 formal evaluation config path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.test_evaluator:
        run_evaluator_tests()
        return

    if args.audit_data:
        audit_data(Path(args.audit_data))
        return

    if args.config:
        raise NotImplementedError("--config formal evaluation will be implemented in Stage 3.")

    raise SystemExit("Choose --test_evaluator, --audit_data, or --config.")


if __name__ == "__main__":
    main()
