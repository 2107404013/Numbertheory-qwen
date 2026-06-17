"""Data preparation entry point.

Implemented in Stage 1:
- --mode inspect_public

Planned later:
- Stage 2: --mode build_eval
- Stage 4: --mode build_train
"""

import argparse
import json
from collections import Counter
from itertools import islice
from pathlib import Path
from typing import Any


TOPIC_FIELD_HINTS = ("subject", "category", "domain", "topic", "type", "tag", "subfield")
NUMBER_THEORY_KEYWORDS = ("number theory", "number_theory", "num theory", "数论")


def _load_public_dataset(args: argparse.Namespace) -> Any:
    from datasets import load_dataset

    load_kwargs: dict[str, Any] = {"split": args.split, "streaming": args.streaming}
    if args.subset:
        return load_dataset(args.dataset_name, args.subset, **load_kwargs)
    return load_dataset(args.dataset_name, **load_kwargs)


def _sample_rows(dataset: Any, limit: int) -> list[dict[str, Any]]:
    return [dict(row) for row in islice(dataset, limit)]


def _field_names(dataset: Any, rows: list[dict[str, Any]]) -> list[str]:
    if getattr(dataset, "column_names", None):
        return list(dataset.column_names)
    if getattr(dataset, "features", None):
        return list(dataset.features.keys())

    names: set[str] = set()
    for row in rows:
        names.update(row.keys())
    return sorted(names)


def _is_number_theory_value(value: Any) -> bool:
    text = str(value).lower()
    return any(keyword in text for keyword in NUMBER_THEORY_KEYWORDS)


def inspect_public(args: argparse.Namespace) -> None:
    dataset = _load_public_dataset(args)
    rows = _sample_rows(dataset, args.num_samples)
    fields = _field_names(dataset, rows)

    topic_fields = [
        field for field in fields if any(hint in field.lower() for hint in TOPIC_FIELD_HINTS)
    ]
    topic_value_counts: dict[str, dict[str, int]] = {}
    number_theory_hits = 0

    for field in topic_fields:
        counter: Counter[str] = Counter()
        for row in rows:
            value = row.get(field)
            if isinstance(value, list):
                values = value
            else:
                values = [value]

            for item in values:
                if item is None:
                    continue
                counter[str(item)] += 1
                if _is_number_theory_value(item):
                    number_theory_hits += 1

        topic_value_counts[field] = dict(counter.most_common(args.max_values_per_field))

    summary = {
        "dataset_name": args.dataset_name,
        "subset": args.subset,
        "split": args.split,
        "streaming": args.streaming,
        "sampled_rows": len(rows),
        "fields": fields,
        "topic_candidate_fields": topic_fields,
        "topic_value_counts": topic_value_counts,
        "number_theory_keyword_hits_in_topic_fields": number_theory_hits,
        "first_row_preview": rows[0] if rows else {},
    }

    text = json.dumps(summary, ensure_ascii=False, indent=2)
    print(text)

    if args.output_path:
        output_path = Path(args.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare NumberTheory-Qwen datasets.")
    parser.add_argument("--mode", choices=["inspect_public", "build_eval", "build_train"], required=True)
    parser.add_argument("--dataset_name", default="KbsdJames/Omni-MATH", help="Hugging Face dataset name.")
    parser.add_argument("--subset", default=None, help="Optional Hugging Face dataset subset/config.")
    parser.add_argument("--split", default="train", help="Dataset split to inspect.")
    parser.add_argument("--streaming", action="store_true", help="Use streaming mode for large datasets.")
    parser.add_argument("--num_samples", type=int, default=50, help="Rows to inspect.")
    parser.add_argument("--max_values_per_field", type=int, default=30)
    parser.add_argument("--output_path", default=None, help="Optional JSON summary path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.mode == "inspect_public":
        inspect_public(args)
        return

    raise NotImplementedError(f"--mode {args.mode} will be implemented in its planned stage.")


if __name__ == "__main__":
    main()
