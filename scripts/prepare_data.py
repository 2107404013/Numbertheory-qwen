"""Dataset preparation and inspection utilities.

Stage 1 implements public dataset field inspection only. It does not download
models, train, or save large raw datasets.
"""

from __future__ import annotations

import argparse
import json
from itertools import islice
from pathlib import Path
from typing import Any


RESULTS_DIR = Path("results")
INSPECT_OUTPUT = RESULTS_DIR / "public_dataset_inspect.md"

DATASET_SPECS = [
    {"label": "Omni-MATH-Rule", "name": "Omni-MATH-Rule", "recommended_use": "formal_eval"},
    {"label": "Omni-MATH", "name": "KbsdJames/Omni-MATH", "recommended_use": "formal_eval"},
    {"label": "AI-MO/NuminaMath-1.5", "name": "AI-MO/NuminaMath-1.5", "recommended_use": "train_sft"},
    {"label": "AI-MO/NuminaMath-CoT", "name": "AI-MO/NuminaMath-CoT", "recommended_use": "backup"},
]

FIELD_GROUPS = {
    "problem_question_candidates": ["problem", "question", "prompt", "problem_text"],
    "answer_final_answer_candidates": ["answer", "final_answer", "ground_truth", "gt", "solution_answer"],
    "solution_candidates": ["solution", "rationale", "cot", "response", "messages"],
    "subject_domain_category_problem_type_candidates": [
        "subject",
        "domain",
        "category",
        "problem_type",
        "topic",
        "type",
        "tags",
    ],
    "difficulty_candidates": ["difficulty", "level", "grade"],
}

NUMBER_THEORY_MARKERS = ["number theory", "number_theory", "num theory", "数论"]
PROOF_MARKERS = ["proof", "prove", "证明", "show that"]
IMAGE_MARKERS = ["image", "figure", "diagram", "图", "as shown"]
OPEN_ENDED_MARKERS = ["open-ended", "explain", "discuss", "证明", "任意"]


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _contains_any(value: Any, markers: list[str]) -> bool:
    text = str(value).lower()
    return any(marker.lower() in text for marker in markers)


def _first_rows(dataset: Any, limit: int = 2) -> list[dict[str, Any]]:
    return [dict(row) for row in islice(dataset, limit)]


def _candidate_fields(columns: list[str], names: list[str]) -> list[str]:
    lowered = {column.lower(): column for column in columns}
    result = []
    for name in names:
        for lower, original in lowered.items():
            if name.lower() == lower or name.lower() in lower:
                result.append(original)
    return sorted(set(result))


def _get_dataset_builder_info(dataset_name: str) -> tuple[list[str], list[str]]:
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


def _load_sample_dataset(dataset_name: str, configs: list[str], splits: list[str]) -> tuple[Any | None, str | None, str | None, str | None]:
    from datasets import load_dataset

    config = configs[0] if configs else None
    split = "train" if "train" in splits else (splits[0] if splits else "train")

    attempts = []
    if config:
        attempts.append({"path": dataset_name, "name": config, "split": split, "streaming": True})
    attempts.append({"path": dataset_name, "split": split, "streaming": True})

    errors = []
    for kwargs in attempts:
        try:
            dataset = load_dataset(**kwargs)
            return dataset, kwargs.get("name"), split, None
        except Exception as exc:
            errors.append(repr(exc))

    return None, config, split, " | ".join(errors)


def inspect_one_dataset(spec: dict[str, str]) -> dict[str, Any]:
    label = spec["label"]
    dataset_name = spec["name"]
    result: dict[str, Any] = {
        "label": label,
        "dataset_name": dataset_name,
        "loaded": False,
        "failure_reason": "",
        "available_splits": [],
        "column_names": [],
        "sample_rows": [],
        "recommended_use": spec["recommended_use"],
    }

    try:
        configs, splits = _get_dataset_builder_info(dataset_name)
        dataset, used_config, used_split, error = _load_sample_dataset(dataset_name, configs, splits)
        result["available_configs"] = configs
        result["available_splits"] = splits
        result["used_config"] = used_config
        result["used_split"] = used_split

        if dataset is None:
            result["failure_reason"] = error or "Unable to load dataset sample."
            return result

        sample_rows = _first_rows(dataset, limit=2)
        columns = list(sample_rows[0].keys()) if sample_rows else []
        combined_sample = "\n".join(_safe_json(row) for row in sample_rows)

        result["loaded"] = True
        result["column_names"] = columns
        result["sample_rows"] = sample_rows

        for group_name, candidates in FIELD_GROUPS.items():
            result[group_name] = _candidate_fields(columns, candidates)

        subject_fields = result["subject_domain_category_problem_type_candidates"]
        subject_values = [row.get(field) for row in sample_rows for field in subject_fields if field in row]
        result["can_filter_number_theory"] = _contains_any(subject_values, NUMBER_THEORY_MARKERS)
        result["contains_proof_like"] = _contains_any(combined_sample, PROOF_MARKERS)
        result["contains_image_multimodal_like"] = _contains_any(combined_sample, IMAGE_MARKERS)
        result["contains_open_ended_like"] = _contains_any(combined_sample, OPEN_ENDED_MARKERS)
        result["suitable_for_formal_eval"] = (
            spec["recommended_use"] == "formal_eval"
            and bool(result["problem_question_candidates"])
            and bool(result["answer_final_answer_candidates"])
        )
        result["suitable_for_training"] = (
            spec["recommended_use"] in {"train_sft", "backup"}
            and bool(result["problem_question_candidates"])
            and (bool(result["answer_final_answer_candidates"]) or bool(result["solution_candidates"]))
        )
    except Exception as exc:
        result["failure_reason"] = repr(exc)

    return result


def _write_markdown(results: list[dict[str, Any]]) -> None:
    lines = [
        "# Public Dataset Inspection",
        "",
        "Stage 1 inspection only. This file records dataset schemas and suitability notes; it does not store raw datasets.",
        "",
    ]

    for item in results:
        lines.extend(
            [
                f"## {item['label']}",
                "",
                f"- dataset_name: `{item['dataset_name']}`",
                f"- loaded: {item['loaded']}",
                f"- failure_reason: {item.get('failure_reason') or ''}",
                f"- available_splits: {item.get('available_splits', [])}",
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
    INSPECT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {INSPECT_OUTPUT}")


def inspect_public() -> None:
    results = [inspect_one_dataset(spec) for spec in DATASET_SPECS]
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
