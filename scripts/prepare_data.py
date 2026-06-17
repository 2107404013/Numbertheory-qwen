"""Dataset preparation and inspection utilities.

Stage 1:
- inspect public dataset schemas.

Stage 2:
- build a fixed public Number Theory evaluation set.

This script does not download models, train, or run inference.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
from collections import Counter
from itertools import islice
from pathlib import Path
from typing import Any, Iterable, Iterator

from eval_math import classify_gold_answer


SEED = 20260618
RESULTS_DIR = Path("results")
DATA_PROCESSED_DIR = Path("data/processed")
INSPECT_OUTPUT = RESULTS_DIR / "public_dataset_inspect.md"
EVAL_FILE = DATA_PROCESSED_DIR / "public_number_theory_eval.jsonl"
SUMMARY_FILE = RESULTS_DIR / "public_eval_data_summary.json"
MANIFEST_FILE = RESULTS_DIR / "public_eval_manifest.json"

HF_DATASET_SPECS = [
    {
        "label": "KbsdJames/Omni-MATH",
        "dataset_name": "KbsdJames/Omni-MATH",
        "recommended_use": "formal_eval",
        "notes": "Primary HF source for formal eval candidates.",
    },
    {
        "label": "AI-MO/NuminaMath-1.5",
        "dataset_name": "AI-MO/NuminaMath-1.5",
        "recommended_use": "train_sft",
        "notes": "Primary training source; inspect whether problem_type == Number Theory is available.",
    },
    {
        "label": "AI-MO/NuminaMath-CoT",
        "dataset_name": "AI-MO/NuminaMath-CoT",
        "recommended_use": "backup",
        "notes": "Backup training source; inspect schema before use.",
    },
]

RULE_SUBSET_SPEC = {
    "label": "Omni-MATH rule-based subset",
    "source_type": "github_raw",
    "repo": "KbsdJames/omni-math-rule",
    "recommended_use": "formal_eval",
    "notes": (
        "This is not a Hugging Face dataset name. It is a GitHub repository "
        "used as the reference for rule-based evaluation filtering."
    ),
    "raw_urls": [
        "https://raw.githubusercontent.com/KbsdJames/omni-math-rule/main/omni_math_rule.jsonl",
        "https://raw.githubusercontent.com/KbsdJames/omni-math-rule/master/omni_math_rule.jsonl",
        "https://raw.githubusercontent.com/KbsdJames/omni-math-rule/main/data/omni_math_rule.jsonl",
        "https://raw.githubusercontent.com/KbsdJames/omni-math-rule/master/data/omni_math_rule.jsonl",
    ],
}

FIELD_GROUPS = {
    "problem_question_candidates": ["problem", "question", "prompt", "problem_text"],
    "answer_final_answer_candidates": ["answer", "final_answer", "ground_truth", "gt", "solution_answer"],
    "solution_candidates": ["solution", "rationale", "cot", "response", "messages"],
    "subject_domain_category_problem_type_candidates": [
        "subject",
        "domain",
        "category",
        "subdomain",
        "original_subject",
        "problem_type",
        "question_type",
        "topic",
        "type",
        "tags",
    ],
    "difficulty_candidates": ["difficulty", "level", "grade"],
}

PROBLEM_FIELDS = ["problem", "question", "prompt", "problem_text"]
ANSWER_FIELDS = ["answer", "final_answer", "ground_truth", "gt", "solution_answer"]
DIFFICULTY_FIELDS = ["difficulty", "level", "grade"]
SUBJECT_FIELDS = [
    "subject",
    "domain",
    "category",
    "subdomain",
    "original_subject",
    "problem_type",
    "question_type",
    "topic",
    "type",
    "tags",
]
ID_FIELDS = ["id", "problem_id", "uid", "source_id"]

NUMBER_THEORY_FIELD_MARKERS = ["number theory", "number_theory", "num theory", "\u6570\u8bba"]
NUMBER_THEORY_STRONG_KEYWORDS = [
    "divisibility",
    "modular",
    "congruence",
    "modulo",
    "gcd",
    "lcm",
    "prime",
    "remainder",
    "diophantine",
    "coprime",
    "factorization over integers",
    "euler theorem",
    "fermat theorem",
    "\u6570\u8bba",
    "\u6574\u9664",
    "\u540c\u4f59",
    "\u4f59\u6570",
    "\u6700\u5927\u516c\u7ea6\u6570",
    "\u6700\u5c0f\u516c\u500d\u6570",
    "\u8d28\u6570",
    "\u7d20\u6570",
    "\u4e0d\u5b9a\u65b9\u7a0b",
    "\u4e92\u8d28",
    "\u6b27\u62c9\u5b9a\u7406",
    "\u8d39\u9a6c\u5c0f\u5b9a\u7406",
]
NUMBER_THEORY_WEAK_KEYWORDS = ["integer", "\u6574\u6570", "\u6a21"]
IMAGE_MARKERS = ["image", "figure", "diagram", "shown below", "as shown", "\u56fe", "\u5982\u56fe"]
PROOF_MARKERS = ["prove", "proof", "show that", "\u8bc1\u660e"]
OPEN_ENDED_MARKERS = ["explain", "discuss", "justify", "\u89e3\u91ca", "\u8ba8\u8bba"]


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _contains_any(value: Any, markers: list[str]) -> bool:
    text = str(value).lower()
    return any(marker.lower() in text for marker in markers)


def _first_non_empty(sample: dict[str, Any], fields: Iterable[str]) -> Any:
    for field in fields:
        value = sample.get(field)
        if value not in (None, ""):
            return value
    return ""


def _candidate_fields(columns: list[str], names: list[str]) -> list[str]:
    lowered = {column.lower(): column for column in columns}
    result = []
    for name in names:
        for lower, original in lowered.items():
            if name.lower() == lower or name.lower() in lower:
                result.append(original)
    return sorted(set(result))


def _first_rows(dataset: Any, limit: int = 2) -> list[dict[str, Any]]:
    return [dict(row) for row in islice(dataset, limit)]


def _stable_hash(value: Any) -> str:
    text = _compact_text(value).lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def extract_problem(sample: dict[str, Any]) -> str:
    return _compact_text(_first_non_empty(sample, PROBLEM_FIELDS))


def extract_answer(sample: dict[str, Any]) -> str:
    return _compact_text(_first_non_empty(sample, ANSWER_FIELDS))


def extract_difficulty(sample: dict[str, Any]) -> str:
    return _compact_text(_first_non_empty(sample, DIFFICULTY_FIELDS))


def extract_original_subject(sample: dict[str, Any]) -> str:
    values = []
    for field in SUBJECT_FIELDS:
        value = sample.get(field)
        if value not in (None, ""):
            values.append(str(value))
    return " | ".join(values)


def extract_id(sample: dict[str, Any], fallback: str) -> str:
    value = _first_non_empty(sample, ID_FIELDS)
    return _compact_text(value) or fallback


def is_text_only_problem(problem: str) -> bool:
    return bool(problem) and not is_image_like(problem)


def is_image_like(problem: str) -> bool:
    return _contains_any(problem, IMAGE_MARKERS)


def is_proof_like(problem: str, answer: str) -> bool:
    combined = f"{problem}\n{answer}"
    return _contains_any(combined, PROOF_MARKERS)


def is_open_ended_like(problem: str) -> bool:
    return _contains_any(problem, OPEN_ENDED_MARKERS)


def is_number_theory_sample(sample: dict[str, Any]) -> tuple[bool, str]:
    subject_text = extract_original_subject(sample)
    if _contains_any(subject_text, NUMBER_THEORY_FIELD_MARKERS):
        return True, "field_filter"

    problem = extract_problem(sample)
    text = problem.lower()
    strong_hits = sum(1 for keyword in NUMBER_THEORY_STRONG_KEYWORDS if keyword.lower() in text)
    weak_hits = sum(1 for keyword in NUMBER_THEORY_WEAK_KEYWORDS if keyword.lower() in text)

    if strong_hits >= 1 and (strong_hits + weak_hits) >= 1:
        return True, "keyword_filter"
    return False, "not_number_theory"


def normalize_sample(sample: dict[str, Any], source: str, index: int, selection_method: str) -> dict[str, Any]:
    problem = extract_problem(sample)
    answer = extract_answer(sample)
    item_id = extract_id(sample, f"{source}-{index}-{_stable_hash(problem)}")
    return {
        "id": item_id,
        "subject": "number_theory",
        "problem": problem,
        "answer": answer,
        "source": source,
        "original_subject": extract_original_subject(sample),
        "difficulty": extract_difficulty(sample),
        "selection_method": selection_method,
        "suitable_for_rule_eval": True,
        "problem_hash": _stable_hash(problem),
        "answer_hash": _stable_hash(answer),
    }


def _skip_reason(sample: dict[str, Any]) -> str | None:
    problem = extract_problem(sample)
    answer = extract_answer(sample)

    if not problem:
        return "empty_problem"
    if not answer:
        return "empty_answer"
    if len(problem) < 20:
        return "problem_too_short"
    if len(answer) > 220:
        return "answer_too_long"
    if answer.count("\n") >= 2:
        return "answer_solution_like"
    if not is_text_only_problem(problem):
        return "image_like_problem"
    if is_proof_like(problem, answer):
        return "proof_like_problem"
    if is_open_ended_like(problem):
        return "open_ended_problem"
    if classify_gold_answer(problem, answer) != "short_answer":
        return "gold_not_short_answer"
    return None


def _add_schema_analysis(result: dict[str, Any], sample_rows: list[dict[str, Any]]) -> None:
    columns = list(sample_rows[0].keys()) if sample_rows else []
    combined_sample = "\n".join(_safe_json(row) for row in sample_rows)

    result["column_names"] = columns
    result["sample_rows"] = sample_rows

    for group_name, candidates in FIELD_GROUPS.items():
        result[group_name] = _candidate_fields(columns, candidates)

    subject_fields = result["subject_domain_category_problem_type_candidates"]
    subject_values = [row.get(field) for row in sample_rows for field in subject_fields if field in row]
    result["can_filter_number_theory"] = _contains_any(subject_values, NUMBER_THEORY_FIELD_MARKERS) or _contains_any(
        combined_sample, NUMBER_THEORY_FIELD_MARKERS
    )
    result["contains_proof_like"] = _contains_any(combined_sample, PROOF_MARKERS)
    result["contains_image_multimodal_like"] = _contains_any(combined_sample, IMAGE_MARKERS)
    result["contains_open_ended_like"] = _contains_any(combined_sample, OPEN_ENDED_MARKERS)
    result["suitable_for_formal_eval"] = (
        result.get("recommended_use") == "formal_eval"
        and bool(result["problem_question_candidates"])
        and bool(result["answer_final_answer_candidates"])
    )
    result["suitable_for_training"] = (
        result.get("recommended_use") in {"train_sft", "backup"}
        and bool(result["problem_question_candidates"])
        and (bool(result["answer_final_answer_candidates"]) or bool(result["solution_candidates"]))
    )


def _get_hf_builder_info(dataset_name: str) -> tuple[list[str], list[str]]:
    from datasets import get_dataset_config_names, get_dataset_split_names

    configs: list[str] = []
    splits: list[str] = []

    try:
        configs = list(get_dataset_config_names(dataset_name))
    except Exception:
        configs = []

    try:
        if configs:
            splits = list(get_dataset_split_names(dataset_name, configs[0]))
        else:
            splits = list(get_dataset_split_names(dataset_name))
    except Exception:
        splits = []

    return configs, splits


def _load_hf_sample(dataset_name: str, configs: list[str], splits: list[str]) -> tuple[Any | None, str | None, str, str]:
    from datasets import load_dataset

    split = "train" if "train" in splits else (splits[0] if splits else "train")
    attempts = []
    if configs:
        attempts.append({"path": dataset_name, "name": configs[0], "split": split, "streaming": True})
    attempts.append({"path": dataset_name, "split": split, "streaming": True})

    errors = []
    for kwargs in attempts:
        try:
            dataset = load_dataset(**kwargs)
            return dataset, kwargs.get("name"), split, ""
        except Exception as exc:
            errors.append(f"{kwargs}: {exc!r}")

    return None, configs[0] if configs else None, split, " | ".join(errors)


def inspect_hf_dataset(spec: dict[str, str]) -> dict[str, Any]:
    dataset_name = spec["dataset_name"]
    result: dict[str, Any] = {
        "label": spec["label"],
        "source_type": "huggingface_dataset",
        "dataset_name": dataset_name,
        "loaded": False,
        "failure_reason": "",
        "available_configs": [],
        "available_splits": [],
        "column_names": [],
        "sample_rows": [],
        "recommended_use": spec["recommended_use"],
        "notes": spec["notes"],
    }

    try:
        configs, splits = _get_hf_builder_info(dataset_name)
        dataset, used_config, used_split, error = _load_hf_sample(dataset_name, configs, splits)
        result["available_configs"] = configs
        result["available_splits"] = splits
        result["used_config"] = used_config
        result["used_split"] = used_split

        if dataset is None:
            result["failure_reason"] = error or "Unable to load dataset sample."
            return result

        sample_rows = _first_rows(dataset, limit=2)
        result["loaded"] = True
        _add_schema_analysis(result, sample_rows)
    except Exception as exc:
        result["failure_reason"] = repr(exc)

    return result


def _open_raw_url(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "NumberTheory-Qwen-stage2"})
    return urllib.request.urlopen(request, timeout=30)


def _read_raw_jsonl_sample(url: str, limit: int = 2) -> list[dict[str, Any]]:
    with _open_raw_url(url) as response:
        rows: list[dict[str, Any]] = []
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if len(rows) >= limit:
                break
        return rows


def iter_raw_jsonl(url: str) -> Iterator[dict[str, Any]]:
    with _open_raw_url(url) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if line:
                yield json.loads(line)


def inspect_rule_subset(spec: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "label": spec["label"],
        "source_type": spec["source_type"],
        "repo": spec["repo"],
        "loaded": False,
        "failure_reason": "",
        "available_splits": ["jsonl"],
        "column_names": [],
        "sample_rows": [],
        "recommended_use": spec["recommended_use"],
        "notes": spec["notes"],
        "raw_url_attempts": spec["raw_urls"],
    }

    errors = []
    for url in spec["raw_urls"]:
        try:
            sample_rows = _read_raw_jsonl_sample(url, limit=2)
            result["loaded"] = True
            result["used_raw_url"] = url
            _add_schema_analysis(result, sample_rows)
            return result
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            errors.append(f"{url}: {exc!r}")
        except Exception as exc:
            errors.append(f"{url}: {exc!r}")

    result["failure_reason"] = " | ".join(errors) if errors else "No raw URL attempts were configured."
    return result


def _write_markdown(results: list[dict[str, Any]]) -> None:
    lines = [
        "# Public Dataset Inspection",
        "",
        "Stage 1 inspection only. This file records dataset schemas and suitability notes; it does not store raw datasets.",
        "",
        "Important correction: `Omni-MATH-Rule` is not treated as a Hugging Face dataset name.",
        "The rule-based subset is inspected from the `KbsdJames/omni-math-rule` GitHub repository when a raw JSONL URL is reachable.",
        "",
    ]

    for item in results:
        lines.extend(
            [
                f"## {item['label']}",
                "",
                f"- source_type: {item.get('source_type', '')}",
                f"- dataset_name: `{item.get('dataset_name', '')}`",
                f"- repo: `{item.get('repo', '')}`",
                f"- loaded: {item.get('loaded', False)}",
                f"- failure_reason: {item.get('failure_reason') or ''}",
                f"- available_configs: {item.get('available_configs', [])}",
                f"- available_splits: {item.get('available_splits', [])}",
                f"- used_config: {item.get('used_config', '')}",
                f"- used_split: {item.get('used_split', '')}",
                f"- used_raw_url: {item.get('used_raw_url', '')}",
                f"- column_names: {item.get('column_names', [])}",
                f"- problem/question field candidates: {item.get('problem_question_candidates', [])}",
                f"- answer/final_answer field candidates: {item.get('answer_final_answer_candidates', [])}",
                f"- solution field candidates: {item.get('solution_candidates', [])}",
                f"- subject/domain/category/problem_type field candidates: {item.get('subject_domain_category_problem_type_candidates', [])}",
                f"- difficulty field candidates: {item.get('difficulty_candidates', [])}",
                f"- can_filter_number_theory: {item.get('can_filter_number_theory', False)}",
                f"- contains_proof_like: {item.get('contains_proof_like', False)}",
                f"- contains_image_multimodal_like: {item.get('contains_image_multimodal_like', False)}",
                f"- contains_open_ended_like: {item.get('contains_open_ended_like', False)}",
                f"- suitable_for_formal_eval: {item.get('suitable_for_formal_eval', False)}",
                f"- suitable_for_training: {item.get('suitable_for_training', False)}",
                f"- recommended_use: {item.get('recommended_use', 'not_recommended')}",
                f"- notes: {item.get('notes', '')}",
                "",
                "### First 2 Samples",
                "",
                "```json",
                _safe_json(item.get("sample_rows", [])),
                "```",
                "",
            ]
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    INSPECT_OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {INSPECT_OUTPUT}")


def inspect_public() -> None:
    results: list[dict[str, Any]] = [inspect_rule_subset(RULE_SUBSET_SPEC)]
    for spec in HF_DATASET_SPECS:
        results.append(inspect_hf_dataset(spec))
    _write_markdown(results)


def _iter_hf_omni_math() -> tuple[Iterator[dict[str, Any]] | None, str]:
    configs, splits = _get_hf_builder_info("KbsdJames/Omni-MATH")
    dataset, _, _, error = _load_hf_sample("KbsdJames/Omni-MATH", configs, splits)
    if dataset is None:
        return None, error or "Unable to load KbsdJames/Omni-MATH."
    return (dict(row) for row in dataset), ""


def _process_source(
    rows: Iterable[dict[str, Any]],
    source: str,
    candidates: list[dict[str, Any]],
    seen_hashes: set[str],
    stats: dict[str, Any],
    candidate_scan_limit: int,
) -> None:
    for index, sample in enumerate(rows):
        if stats["candidate_count_before_filter"] >= candidate_scan_limit:
            stats["source_notes"].append(f"Stopped scanning at candidate_scan_limit={candidate_scan_limit}.")
            break

        stats["candidate_count_before_filter"] += 1
        is_nt, selection_method = is_number_theory_sample(sample)
        if not is_nt:
            stats["skip_reasons"]["not_number_theory"] += 1
            continue

        stats["candidate_count_after_number_theory_filter"] += 1
        reason = _skip_reason(sample)
        if reason:
            stats["skip_reasons"][reason] += 1
            continue

        normalized = normalize_sample(sample, source, index, selection_method)
        problem_hash = normalized["problem_hash"]
        if problem_hash in seen_hashes:
            stats["duplicate_removed"] += 1
            stats["skip_reasons"]["duplicate_problem"] += 1
            continue

        seen_hashes.add(problem_hash)
        candidates.append(normalized)
        stats["candidate_count_after_rule_eval_filter"] += 1


def build_eval_set(max_eval_samples: int, candidate_scan_limit: int) -> None:
    candidates: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    stats: dict[str, Any] = {
        "candidate_count_before_filter": 0,
        "candidate_count_after_number_theory_filter": 0,
        "candidate_count_after_rule_eval_filter": 0,
        "skipped_count": 0,
        "skip_reasons": Counter(),
        "duplicate_removed": 0,
        "source_errors": [],
        "source_notes": [],
    }

    rule_loaded = False
    for url in RULE_SUBSET_SPEC["raw_urls"]:
        try:
            _process_source(
                iter_raw_jsonl(url),
                "omni_math_rule",
                candidates,
                seen_hashes,
                stats,
                candidate_scan_limit,
            )
            stats["source_notes"].append(f"Loaded rule-based subset from {url}.")
            rule_loaded = True
            break
        except Exception as exc:
            stats["source_errors"].append({"source": "omni_math_rule", "url": url, "error": repr(exc)})

    if len(candidates) < max_eval_samples:
        hf_rows, error = _iter_hf_omni_math()
        if hf_rows is None:
            stats["source_errors"].append({"source": "KbsdJames/Omni-MATH", "error": error})
        else:
            if not rule_loaded:
                stats["source_notes"].append("Fell back to KbsdJames/Omni-MATH because rule subset was unavailable.")
            else:
                stats["source_notes"].append("Added KbsdJames/Omni-MATH candidates because rule subset had fewer than target.")
            _process_source(
                hf_rows,
                "KbsdJames/Omni-MATH",
                candidates,
                seen_hashes,
                stats,
                candidate_scan_limit,
            )

    selected = sorted(candidates, key=lambda item: (item["source"], str(item["id"]), item["problem_hash"]))[
        :max_eval_samples
    ]

    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with EVAL_FILE.open("w", encoding="utf-8") as file:
        for item in selected:
            row = {key: value for key, value in item.items() if key not in {"problem_hash", "answer_hash"}}
            file.write(json.dumps(row, ensure_ascii=False) + "\n")

    manifest = [
        {
            "id": item["id"],
            "source": item["source"],
            "subject": "number_theory",
            "original_subject": item["original_subject"],
            "difficulty": item["difficulty"],
            "problem_hash": item["problem_hash"],
            "answer_hash": item["answer_hash"],
            "selection_method": item["selection_method"],
            "suitable_for_rule_eval": True,
        }
        for item in selected
    ]
    MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    problem_lengths = [len(item["problem"]) for item in selected]
    answer_lengths = [len(item["answer"]) for item in selected]
    summary = {
        "target_samples": max_eval_samples,
        "actual_samples": len(selected),
        "seed": SEED,
        "selection_rule": "stable_sort_by_source_id_problem_hash_then_take_first_n",
        "candidate_scan_limit": candidate_scan_limit,
        "source_distribution": dict(Counter(item["source"] for item in selected)),
        "difficulty_distribution": dict(Counter(item["difficulty"] for item in selected)),
        "original_subject_distribution": dict(Counter(item["original_subject"] for item in selected)),
        "selection_method_distribution": dict(Counter(item["selection_method"] for item in selected)),
        "candidate_count_before_filter": stats["candidate_count_before_filter"],
        "candidate_count_after_number_theory_filter": stats["candidate_count_after_number_theory_filter"],
        "candidate_count_after_rule_eval_filter": stats["candidate_count_after_rule_eval_filter"],
        "skipped_count": sum(stats["skip_reasons"].values()),
        "skip_reasons": dict(stats["skip_reasons"]),
        "duplicate_removed": stats["duplicate_removed"],
        "avg_problem_length": sum(problem_lengths) / len(problem_lengths) if problem_lengths else 0.0,
        "avg_answer_length": sum(answer_lengths) / len(answer_lengths) if answer_lengths else 0.0,
        "eval_file": str(EVAL_FILE),
        "manifest_file": str(MANIFEST_FILE),
        "source_errors": stats["source_errors"],
        "source_notes": stats["source_notes"],
        "insufficient_samples_reason": ""
        if len(selected) >= max_eval_samples
        else "Filtered public Number Theory short-answer candidates were fewer than target; no non-NT samples were added.",
    }
    SUMMARY_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {EVAL_FILE}")
    print(f"Wrote {SUMMARY_FILE}")
    print(f"Wrote {MANIFEST_FILE}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare NumberTheory-Qwen datasets.")
    parser.add_argument("--mode", choices=["inspect_public", "build_eval", "build_train"], required=True)
    parser.add_argument("--max_eval_samples", type=int, default=200)
    parser.add_argument("--candidate_scan_limit", type=int, default=20000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.mode == "inspect_public":
        inspect_public()
        return
    if args.mode == "build_eval":
        build_eval_set(args.max_eval_samples, args.candidate_scan_limit)
        return

    raise NotImplementedError(f"--mode {args.mode} will be implemented in a later stage.")


if __name__ == "__main__":
    main()
