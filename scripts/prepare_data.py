"""Dataset preparation and inspection utilities.

Stage 1 implements public dataset field inspection only. It does not download
models, train, run inference, or save large raw datasets.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from itertools import islice
from pathlib import Path
from typing import Any


RESULTS_DIR = Path("results")
INSPECT_OUTPUT = RESULTS_DIR / "public_dataset_inspect.md"

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
        "problem_type",
        "question_type",
        "topic",
        "type",
        "tags",
    ],
    "difficulty_candidates": ["difficulty", "level", "grade"],
}

NUMBER_THEORY_MARKERS = ["number theory", "number_theory", "num theory", "\u6570\u8bba"]
PROOF_MARKERS = ["proof", "prove", "\u8bc1\u660e", "show that"]
IMAGE_MARKERS = ["image", "figure", "diagram", "\u56fe", "as shown"]
OPEN_ENDED_MARKERS = ["open-ended", "explain", "discuss", "\u8bc1\u660e", "\u4efb\u610f"]


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _contains_any(value: Any, markers: list[str]) -> bool:
    text = str(value).lower()
    return any(marker.lower() in text for marker in markers)


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


def _add_schema_analysis(result: dict[str, Any], sample_rows: list[dict[str, Any]]) -> None:
    columns = list(sample_rows[0].keys()) if sample_rows else []
    combined_sample = "\n".join(_safe_json(row) for row in sample_rows)

    result["column_names"] = columns
    result["sample_rows"] = sample_rows

    for group_name, candidates in FIELD_GROUPS.items():
        result[group_name] = _candidate_fields(columns, candidates)

    subject_fields = result["subject_domain_category_problem_type_candidates"]
    subject_values = [row.get(field) for row in sample_rows for field in subject_fields if field in row]
    result["can_filter_number_theory"] = _contains_any(subject_values, NUMBER_THEORY_MARKERS) or _contains_any(
        combined_sample, NUMBER_THEORY_MARKERS
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


def _read_raw_jsonl_sample(url: str, limit: int = 2) -> list[dict[str, Any]]:
    request = urllib.request.Request(url, headers={"User-Agent": "NumberTheory-Qwen-stage1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        rows: list[dict[str, Any]] = []
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if len(rows) >= limit:
                break
        return rows


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
    results: list[dict[str, Any]] = []
    results.append(inspect_rule_subset(RULE_SUBSET_SPEC))
    for spec in HF_DATASET_SPECS:
        results.append(inspect_hf_dataset(spec))
    _write_markdown(results)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare NumberTheory-Qwen datasets.")
    parser.add_argument("--mode", choices=["inspect_public", "build_eval", "build_train"], required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.mode == "inspect_public":
        inspect_public()
        return

    raise NotImplementedError(f"--mode {args.mode} will be implemented in a later stage.")


if __name__ == "__main__":
    main()
