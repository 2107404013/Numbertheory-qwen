"""Math scoring, data audit, formal evaluation, and result comparison."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
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


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required. Run: pip install pyyaml") from exc

    with path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    if not isinstance(config, dict):
        raise ValueError(f"Config must contain a YAML mapping: {path}")
    return config


def _required_config_value(config: dict[str, Any], key: str) -> Any:
    value = config.get(key)
    if value is None or value == "":
        raise ValueError(f"Missing required config value: {key}")
    return value


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _row_value(row: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return default


def _render_prompt(template: str, problem: str) -> str:
    if "{problem}" not in template:
        raise ValueError("prompt_template must contain the literal placeholder {problem}")
    return template.replace("{problem}", problem)


def _primary_prediction(model_output: str) -> tuple[str, bool]:
    boxed_answer = extract_boxed_answer(model_output)
    if boxed_answer:
        return boxed_answer, True

    explicit_candidates: list[tuple[int, str]] = []
    for pattern in ANSWER_TRIGGER_PATTERNS + CONCLUSION_PATTERNS:
        for match in re.finditer(pattern, model_output):
            candidate = match.group(1).strip()
            if candidate:
                explicit_candidates.append((match.start(), candidate))

    if explicit_candidates:
        return max(explicit_candidates, key=lambda item: item[0])[1], False
    return "", False


def _score_baseline_row(row: dict[str, Any], model_output: str, index: int) -> dict[str, Any]:
    problem = str(_row_value(row, "problem", "question", "prompt"))
    gold = str(_row_value(row, "answer", "final_answer", "gold", "ground_truth"))
    pred, boxed_found = _primary_prediction(model_output)
    gold_type = classify_gold_answer(problem, gold)
    extraction_success = bool(pred.strip())

    if gold_type == "empty_answer":
        match = MatchResult(False, "failed")
        error_type = "possible_gold_error"
    elif gold_type != "short_answer":
        match = MatchResult(False, "failed")
        error_type = "unsuitable_for_rule_eval"
    elif not extraction_success:
        match = MatchResult(False, "failed")
        error_type = "extraction_error"
    else:
        match = is_equiv(pred, gold)
        if match.matched:
            error_type = "correct"
        elif not boxed_found:
            error_type = "format_error"
        else:
            error_type = "model_error"

    return {
        "id": _row_value(row, "id", default=str(index)),
        "subject": _row_value(row, "subject", "domain", "category", default="number_theory"),
        "source": _row_value(row, "source"),
        "difficulty": _row_value(row, "difficulty", default="unknown"),
        "problem": problem,
        "gold_answer": gold,
        "model_output": model_output,
        "pred_answer": pred,
        "normalized_pred": normalize_answer(pred),
        "normalized_gold": normalize_answer(gold),
        "match_method": match.match_method,
        "boxed_answer_found": boxed_found,
        "extraction_success": extraction_success,
        "is_correct": match.matched,
        "error_type": error_type,
    }


def _distribution(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key, "unknown")) for row in rows).items()))


def _build_summary(
    rows: list[dict[str, Any]],
    model_name: str,
    eval_file: str,
) -> dict[str, Any]:
    total = len(rows)
    correct = sum(bool(row["is_correct"]) for row in rows)
    difficulty_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        difficulty_groups[str(row.get("difficulty") or "unknown")].append(row)

    accuracy_by_difficulty: dict[str, dict[str, Any]] = {}
    for difficulty, group in sorted(difficulty_groups.items()):
        group_correct = sum(bool(row["is_correct"]) for row in group)
        accuracy_by_difficulty[difficulty] = {
            "total": len(group),
            "correct": group_correct,
            "accuracy": group_correct / len(group),
        }

    return {
        "model_name": model_name,
        "eval_file": eval_file,
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else 0.0,
        "boxed_answer_rate": (
            sum(bool(row["boxed_answer_found"]) for row in rows) / total if total else 0.0
        ),
        "extraction_success_rate": (
            sum(bool(row["extraction_success"]) for row in rows) / total if total else 0.0
        ),
        "avg_output_length": (
            sum(len(str(row["model_output"])) for row in rows) / total if total else 0.0
        ),
        "error_type_distribution": _distribution(rows, "error_type"),
        "match_method_distribution": _distribution(rows, "match_method"),
        "difficulty_distribution": _distribution(rows, "difficulty"),
        "accuracy_by_difficulty": accuracy_by_difficulty,
    }


def _error_reason(row: dict[str, Any]) -> str:
    reasons = {
        "model_error": "已抽取到 boxed 答案，但与标准答案不等价，优先检查推理或计算错误。",
        "extraction_error": "输出中没有抽取到可评分的最终答案。",
        "format_error": "未按要求给出 boxed 答案，且抽取到的候选答案不正确。",
        "possible_gold_error": "标准答案为空或可能存在数据质量问题，需要人工复核。",
        "unsuitable_for_rule_eval": "题目或答案格式不适合当前短答案规则评分。",
    }
    return reasons.get(str(row.get("error_type")), "需要人工检查模型推理与最终答案。")


def _select_error_examples(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    incorrect = [row for row in rows if not row["is_correct"]]
    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for error_type in [
        "model_error",
        "extraction_error",
        "format_error",
        "possible_gold_error",
        "unsuitable_for_rule_eval",
    ]:
        match = next((row for row in incorrect if row["error_type"] == error_type), None)
        if match is not None:
            selected.append(match)
            seen_ids.add(str(match["id"]))

    for row in incorrect:
        if len(selected) >= limit:
            break
        if str(row["id"]) not in seen_ids:
            selected.append(row)
            seen_ids.add(str(row["id"]))
    return selected[:limit]


def _write_error_analysis(
    path: Path,
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    lines = [
        "# Formal Evaluation Error Analysis",
        "",
        "## Overall Results",
        "",
        f"- Model: `{summary['model_name']}`",
        f"- Eval file: `{summary['eval_file']}`",
        f"- Total: {summary['total']}",
        f"- Correct: {summary['correct']}",
        f"- Final Answer Accuracy: {summary['accuracy']:.2%}",
        f"- Boxed Answer Rate: {summary['boxed_answer_rate']:.2%}",
        f"- Extraction Success Rate: {summary['extraction_success_rate']:.2%}",
        f"- Average Output Length (characters): {summary['avg_output_length']:.2f}",
        "",
        "## Error Type Distribution",
        "",
        "| Error Type | Count |",
        "| --- | ---: |",
    ]
    for key, value in summary["error_type_distribution"].items():
        lines.append(f"| {key} | {value} |")

    lines.extend(
        [
            "",
            "## Match Method Distribution",
            "",
            "| Match Method | Count |",
            "| --- | ---: |",
        ]
    )
    for key, value in summary["match_method_distribution"].items():
        lines.append(f"| {key} | {value} |")

    lines.extend(
        [
            "",
            "## Accuracy By Difficulty",
            "",
            "| Difficulty | Total | Correct | Accuracy |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for difficulty, metrics in summary["accuracy_by_difficulty"].items():
        lines.append(
            f"| {difficulty} | {metrics['total']} | {metrics['correct']} | "
            f"{metrics['accuracy']:.2%} |"
        )

    lines.extend(["", "## Typical Error Examples", ""])
    examples = _select_error_examples(rows)
    if not examples:
        lines.append("No incorrect examples were found.")

    for number, row in enumerate(examples, start=1):
        lines.extend(
            [
                f"### {number}. {row['id']}",
                "",
                f"- Difficulty: {row['difficulty']}",
                f"- Problem: {_shorten(row['problem'], 300)}",
                f"- Gold answer: {row['gold_answer']}",
                f"- Pred answer: {row['pred_answer'] or '[empty]'}",
                f"- Match method: {row['match_method']}",
                f"- Error type: {row['error_type']}",
                f"- Model output excerpt: {_shorten(row['model_output'], 500)}",
                f"- Possible reason: {_error_reason(row)}",
                "",
            ]
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_formal_evaluation(
    config_path: Path,
    adapter_path: Path | None = None,
    output_override: Path | None = None,
    summary_output_override: Path | None = None,
    error_analysis_output_override: Path | None = None,
) -> None:
    config = _load_yaml(config_path)
    model_name = str(_required_config_value(config, "model_name"))
    eval_file = Path(str(_required_config_value(config, "eval_file")))
    output_path = output_override or Path(str(_required_config_value(config, "output_path")))
    summary_path = summary_output_override or Path(
        str(_required_config_value(config, "summary_path"))
    )
    error_analysis_path = error_analysis_output_override or Path(
        str(_required_config_value(config, "error_analysis_path"))
    )
    prompt_template = str(_required_config_value(config, "prompt_template"))
    max_eval_samples = int(config.get("max_eval_samples", 200))
    max_new_tokens = int(config.get("max_new_tokens", 2048))
    do_sample = bool(config.get("do_sample", False))

    if not eval_file.exists():
        raise FileNotFoundError(
            f"Formal eval file not found: {eval_file}. Generate it in Stage 2 before Stage 3."
        )

    rows = _read_jsonl(eval_file)[:max_eval_samples]
    if not rows:
        raise ValueError(f"No evaluation rows found in {eval_file}")

    try:
        import torch
        from tqdm import tqdm
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("Install requirements.txt in the remote ntqwen environment.") from exc

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required. Run formal evaluation on the remote GPU server.")

    print(f"Loading tokenizer: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"Loading model in bfloat16 with device_map='auto': {model_name}")
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        low_cpu_mem_usage=True,
    )
    evaluated_model_name = model_name
    if adapter_path is not None:
        if not adapter_path.exists():
            raise FileNotFoundError(f"LoRA adapter not found: {adapter_path}")
        try:
            from peft import PeftModel
        except ImportError as exc:
            raise RuntimeError("PEFT is required to evaluate a LoRA adapter.") from exc
        print(f"Loading LoRA adapter: {adapter_path}")
        model = PeftModel.from_pretrained(model, str(adapter_path))
        evaluated_model_name = f"{model_name} + LoRA({adapter_path})"
    model.eval()

    generation_kwargs: dict[str, Any] = {
        "max_new_tokens": max_new_tokens,
        "do_sample": do_sample,
        "pad_token_id": tokenizer.pad_token_id,
        "eos_token_id": tokenizer.eos_token_id,
    }
    if do_sample:
        generation_kwargs["temperature"] = float(config.get("temperature", 1.0))
        generation_kwargs["top_p"] = float(config.get("top_p", 1.0))

    results: list[dict[str, Any]] = []
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for index, row in enumerate(tqdm(rows, desc="Formal evaluation"), start=1):
        problem = str(_row_value(row, "problem", "question", "prompt"))
        user_prompt = _render_prompt(prompt_template, problem)
        chat_text = tokenizer.apply_chat_template(
            [{"role": "user", "content": user_prompt}],
            tokenize=False,
            add_generation_prompt=True,
        )
        model_inputs = tokenizer(chat_text, return_tensors="pt")
        model_inputs = {key: value.to(model.device) for key, value in model_inputs.items()}
        input_length = model_inputs["input_ids"].shape[1]

        with torch.inference_mode():
            generated = model.generate(**model_inputs, **generation_kwargs)

        generated_tokens = generated[0, input_length:]
        model_output = tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()
        results.append(_score_baseline_row(row, model_output, index))

        # Keep the required output file valid and recoverable during a long remote run.
        _write_json(output_path, results)

    summary = _build_summary(results, evaluated_model_name, str(eval_file))
    _write_json(summary_path, summary)
    _write_error_analysis(error_analysis_path, summary, results)
    print(f"Wrote {output_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {error_analysis_path}")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _summary_path_for_eval(eval_path: Path) -> Path:
    name = eval_path.name
    if name.endswith("_eval.json"):
        return eval_path.with_name(name[: -len("_eval.json")] + "_summary.json")
    return eval_path.with_name(eval_path.stem + "_summary.json")


def _load_or_build_comparison_summary(
    eval_path: Path,
    rows: list[dict[str, Any]],
) -> tuple[Path, dict[str, Any]]:
    summary_path = _summary_path_for_eval(eval_path)
    if summary_path.exists():
        summary = _load_json(summary_path)
        if not isinstance(summary, dict):
            raise ValueError(f"Summary must contain a JSON object: {summary_path}")
        return summary_path, summary
    return summary_path, _build_summary(rows, "unknown", "unknown")


def compare_evaluations(baseline_path: Path, current_path: Path, output_path: Path) -> None:
    baseline_rows = _load_json(baseline_path)
    current_rows = _load_json(current_path)
    if not isinstance(baseline_rows, list) or not isinstance(current_rows, list):
        raise ValueError("Baseline and current evaluation files must contain JSON arrays.")

    baseline_summary_path, baseline_summary = _load_or_build_comparison_summary(
        baseline_path, baseline_rows
    )
    current_summary_path, current_summary = _load_or_build_comparison_summary(
        current_path, current_rows
    )

    baseline_by_id = {str(row.get("id")): row for row in baseline_rows}
    current_by_id = {str(row.get("id")): row for row in current_rows}
    shared_ids = set(baseline_by_id) & set(current_by_id)
    improved_case_count = sum(
        not bool(baseline_by_id[row_id].get("is_correct"))
        and bool(current_by_id[row_id].get("is_correct"))
        for row_id in shared_ids
    )
    regressed_case_count = sum(
        bool(baseline_by_id[row_id].get("is_correct"))
        and not bool(current_by_id[row_id].get("is_correct"))
        for row_id in shared_ids
    )

    baseline_accuracy = float(baseline_summary.get("accuracy", 0.0))
    current_accuracy = float(current_summary.get("accuracy", 0.0))
    baseline_boxed_rate = float(baseline_summary.get("boxed_answer_rate", 0.0))
    current_boxed_rate = float(current_summary.get("boxed_answer_rate", 0.0))
    baseline_extraction_rate = float(
        baseline_summary.get("extraction_success_rate", 0.0)
    )
    current_extraction_rate = float(
        current_summary.get("extraction_success_rate", 0.0)
    )

    comparison = {
        "baseline_summary": str(baseline_summary_path),
        "lora_summary": str(current_summary_path),
        "baseline_accuracy": baseline_accuracy,
        "lora_accuracy": current_accuracy,
        "accuracy_delta": current_accuracy - baseline_accuracy,
        "baseline_boxed_answer_rate": baseline_boxed_rate,
        "lora_boxed_answer_rate": current_boxed_rate,
        "boxed_answer_rate_delta": current_boxed_rate - baseline_boxed_rate,
        "baseline_extraction_success_rate": baseline_extraction_rate,
        "lora_extraction_success_rate": current_extraction_rate,
        "extraction_success_rate_delta": (
            current_extraction_rate - baseline_extraction_rate
        ),
        "baseline_error_type_distribution": baseline_summary.get(
            "error_type_distribution", {}
        ),
        "lora_error_type_distribution": current_summary.get(
            "error_type_distribution", {}
        ),
        "improved_case_count": improved_case_count,
        "regressed_case_count": regressed_case_count,
        "shared_case_count": len(shared_ids),
    }
    _write_json(output_path, comparison)
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
    parser.add_argument("--config", default=None, help="Formal evaluation config path.")
    parser.add_argument(
        "--adapter_path",
        default=None,
        help="Optional LoRA adapter directory. Omit it to evaluate the base model.",
    )
    parser.add_argument("--output", default=None, help="Evaluation or comparison output path.")
    parser.add_argument(
        "--summary_output",
        default=None,
        help="Optional formal evaluation summary output override.",
    )
    parser.add_argument(
        "--error_analysis_output",
        default=None,
        help="Optional formal evaluation error analysis output override.",
    )
    parser.add_argument("--compare", action="store_true", help="Compare two evaluation files.")
    parser.add_argument("--baseline", default=None, help="Baseline evaluation JSON path.")
    parser.add_argument("--current", default=None, help="Current evaluation JSON path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.test_evaluator:
        run_evaluator_tests()
        return

    if args.audit_data:
        audit_data(Path(args.audit_data))
        return

    if args.compare:
        if not args.baseline or not args.current or not args.output:
            raise SystemExit("--compare requires --baseline, --current, and --output.")
        compare_evaluations(Path(args.baseline), Path(args.current), Path(args.output))
        return

    if args.config:
        run_formal_evaluation(
            Path(args.config),
            adapter_path=Path(args.adapter_path) if args.adapter_path else None,
            output_override=Path(args.output) if args.output else None,
            summary_output_override=(
                Path(args.summary_output) if args.summary_output else None
            ),
            error_analysis_output_override=(
                Path(args.error_analysis_output) if args.error_analysis_output else None
            ),
        )
        return

    raise SystemExit("Choose --test_evaluator, --audit_data, --config, or --compare.")


if __name__ == "__main__":
    main()
