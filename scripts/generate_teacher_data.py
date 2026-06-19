"""Generate and audit the Stage 6.1 teacher-response pilot dataset."""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from eval_math import extract_answer_candidates, extract_boxed_answer, is_equiv


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required. Install the project requirements first.") from exc

    with path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    if not isinstance(config, dict):
        raise ValueError(f"Config must contain a YAML mapping: {path}")
    return config


def _required(config: dict[str, Any], key: str) -> Any:
    value = config.get(key)
    if value is None or value == "":
        raise ValueError(f"Missing required config value: {key}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Expected a JSON object at {path}:{line_no}")
            rows.append(row)
    return rows


def _atomic_write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as file:
            temp_path = Path(file.name)
            for row in rows:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")
            file.flush()
            os.fsync(file.fileno())
        temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _render_prompt(template: str, problem: str, answer: str) -> str:
    if "{problem}" not in template or "{answer}" not in template:
        raise ValueError("prompt_template must contain {problem} and {answer}")
    return template.replace("{problem}", problem).replace("{answer}", answer)


def _is_chinese_like(text: str) -> bool:
    cjk_count = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", text))
    latin_count = len(re.findall(r"[A-Za-z]", text))
    return cjk_count >= 20 and cjk_count >= latin_count * 0.35


def _score_teacher_answer(solution: str, gold: str) -> tuple[bool | None, str | None]:
    boxed = extract_boxed_answer(solution)
    candidates = [boxed] if boxed else extract_answer_candidates(solution)
    candidates = [candidate for candidate in candidates if candidate]
    if not candidates:
        return None, None

    for candidate in candidates:
        result = is_equiv(candidate, gold)
        if result.matched:
            return True, result.match_method
    return False, "failed"


def _model_input_device(model: Any) -> Any:
    for parameter in model.parameters():
        if getattr(parameter, "device", None) is not None and parameter.device.type != "meta":
            return parameter.device
    raise RuntimeError("Unable to determine the teacher model input device.")


def _chat_input_ids(tokenizer: Any, prompt: str, device: Any) -> Any:
    if getattr(tokenizer, "chat_template", None):
        messages = [{"role": "user", "content": prompt}]
        encoded = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
        )
    else:
        encoded = tokenizer(prompt, return_tensors="pt")["input_ids"]
    if hasattr(encoded, "input_ids"):
        encoded = encoded.input_ids
    if not hasattr(encoded, "shape"):
        raise TypeError(
            "Tokenizer chat template must return a tensor or BatchEncoding with input_ids."
        )
    return encoded.to(device)


def _load_teacher_model(config: dict[str, Any]) -> tuple[Any, Any]:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_name = str(_required(config, "teacher_model"))
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"

    load_in_4bit = bool(config.get("load_in_4bit", True))
    model_kwargs: dict[str, Any] = {
        "device_map": "auto",
        "low_cpu_mem_usage": True,
    }
    if load_in_4bit:
        try:
            from transformers import BitsAndBytesConfig

            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )
            model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)
        except Exception as exc:
            raise RuntimeError(
                "Failed to load the teacher model in 4-bit mode. Verify that CUDA, "
                "bitsandbytes, accelerate, and Transformers are installed correctly. "
                "If the GPU environment cannot support 4-bit loading, set "
                "load_in_4bit: false in configs/teacher_generate.yaml and rerun; "
                "bf16 loading requires substantially more GPU memory."
            ) from exc
    else:
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required for teacher response generation.")
        model_kwargs["torch_dtype"] = torch.bfloat16
        model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)

    model.eval()
    return tokenizer, model


def _build_output_row(
    source_row: dict[str, Any],
    row_id: str,
    teacher_solution: str,
    answer_match: bool | None,
    answer_match_method: str | None,
    boxed_fallback_appended: bool,
    teacher_model: str,
    model_tag: str,
) -> dict[str, Any]:
    return {
        "id": row_id,
        "subject": source_row.get("subject") or "number_theory",
        "problem": str(source_row.get("problem") or ""),
        "answer": str(source_row.get("answer") or ""),
        "original_solution": str(source_row.get("solution") or ""),
        "teacher_solution": teacher_solution,
        "source": f"teacher_{model_tag}",
        "teacher_model": teacher_model,
        "base_source": source_row.get("source") or "AI-MO/NuminaMath-1.5",
        "problem_type": source_row.get("problem_type", ""),
        "question_type": source_row.get("question_type", ""),
        "has_boxed_answer": extract_boxed_answer(teacher_solution) is not None,
        "teacher_answer_match_gold": answer_match,
        "teacher_answer_match_method": answer_match_method,
        "boxed_fallback_appended": boxed_fallback_appended,
    }


def _summarize(
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    target_samples: int,
    empty_output_count: int,
    non_chinese_like_count: int,
    append_boxed_fallback_count: int,
    generation_errors: list[dict[str, Any]],
    status: str,
) -> dict[str, Any]:
    actual_samples = len(rows)
    boxed_count = sum(bool(row.get("has_boxed_answer")) for row in rows)
    matched_values = [
        row.get("teacher_answer_match_gold")
        for row in rows
        if row.get("teacher_answer_match_gold") is not None
    ]
    matched_count = sum(value is True for value in matched_values)
    total_length = sum(len(str(row.get("teacher_solution") or "")) for row in rows)
    computed_non_chinese = sum(
        not _is_chinese_like(str(row.get("teacher_solution") or "")) for row in rows
    )
    computed_fallback_count = sum(
        bool(row.get("boxed_fallback_appended")) for row in rows
    )
    chinese_like_count = actual_samples - computed_non_chinese
    safe_count = sum(
        row.get("teacher_answer_match_gold") is True
        and _is_chinese_like(str(row.get("teacher_solution") or ""))
        and bool(str(row.get("teacher_solution") or "").strip())
        and extract_boxed_answer(str(row.get("teacher_solution") or "")) is not None
        and row.get("boxed_fallback_appended") is not True
        for row in rows
    )
    return {
        "status": status,
        "teacher_model": str(_required(config, "teacher_model")),
        "input_file": str(_required(config, "input_file")),
        "output_file": str(_required(config, "output_file")),
        "target_samples": target_samples,
        "total": target_samples,
        "actual_samples": actual_samples,
        "boxed_answer_rate": boxed_count / actual_samples if actual_samples else 0.0,
        "empty_output_count": empty_output_count,
        "non_chinese_like_count": max(non_chinese_like_count, computed_non_chinese),
        "chinese_like_count": chinese_like_count,
        "chinese_like_rate": chinese_like_count / actual_samples if actual_samples else 0.0,
        "avg_teacher_solution_length": total_length / actual_samples if actual_samples else 0.0,
        "teacher_answer_match_gold_count": matched_count,
        "teacher_answer_match_gold_rate": (
            matched_count / len(matched_values) if matched_values else 0.0
        ),
        "teacher_answer_checked_count": len(matched_values),
        "answer_match_gold_count": matched_count,
        "answer_match_gold_rate": (
            matched_count / len(matched_values) if matched_values else 0.0
        ),
        "safe_teacher_data_count": safe_count,
        "safe_teacher_data_rate": safe_count / actual_samples if actual_samples else 0.0,
        "append_boxed_fallback_count": max(
            append_boxed_fallback_count,
            computed_fallback_count,
        ),
        "generation_error_count": len(generation_errors),
        "generation_errors": generation_errors,
    }


def _write_audit(path: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Teacher Data Audit",
        "",
        "## Summary",
        "",
        f"- status: {summary['status']}",
        f"- generated samples: {summary['actual_samples']} / {summary['target_samples']}",
        f"- boxed answer rate: {summary['boxed_answer_rate']:.4f}",
        f"- Chinese-like rate: {summary['chinese_like_rate']:.4f}",
        f"- strict safe teacher data rate: {summary['safe_teacher_data_rate']:.4f}",
        (
            "- teacher answer / gold answer match rate: "
            f"{summary['teacher_answer_match_gold_rate']:.4f} "
            f"({summary['teacher_answer_match_gold_count']}/"
            f"{summary['teacher_answer_checked_count']})"
        ),
        f"- empty output count: {summary['empty_output_count']}",
        f"- non-Chinese-like output count: {summary['non_chinese_like_count']}",
        (
            "- average teacher solution length: "
            f"{summary['avg_teacher_solution_length']:.2f} characters"
        ),
        f"- appended boxed fallback count: {summary['append_boxed_fallback_count']}",
        f"- generation error count: {summary['generation_error_count']}",
        "",
        "## Samples",
        "",
    ]

    for row in rows[:5]:
        problem = str(row.get("problem") or "")
        solution = str(row.get("teacher_solution") or "")
        lines.extend(
            [
                f"### {row.get('id', '')}",
                "",
                f"- problem: {problem[:300]}{'...' if len(problem) > 300 else ''}",
                f"- gold answer: {row.get('answer', '')}",
                (
                    "- teacher solution: "
                    f"{solution[:800]}{'...' if len(solution) > 800 else ''}"
                ),
                f"- has boxed answer: {row.get('has_boxed_answer')}",
                (
                    "- teacher answer matches gold: "
                    f"{row.get('teacher_answer_match_gold')}"
                ),
                "",
            ]
        )

    if summary["generation_errors"]:
        lines.extend(["## Generation Errors", ""])
        for error in summary["generation_errors"][:20]:
            lines.append(
                f"- id={error.get('id', '')}: {error.get('type', '')}: "
                f"{error.get('error', '')}"
            )
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


SAFE_TEACHER_FIELDS = [
    "id",
    "subject",
    "problem",
    "answer",
    "original_solution",
    "teacher_solution",
    "source",
    "base_source",
    "problem_type",
    "question_type",
    "has_boxed_answer",
    "teacher_answer_match_gold",
    "teacher_answer_match_method",
    "boxed_fallback_appended",
]


def filter_safe_teacher_data(
    input_path: Path,
    output_path: Path,
    summary_path: Path,
    audit_path: Path,
) -> None:
    """Create a strict teacher dataset without gold-appended fallback answers."""

    if not input_path.exists():
        raise FileNotFoundError(f"Teacher data file not found: {input_path}")

    rows = _read_jsonl(input_path)
    answer_matched = [
        row for row in rows if row.get("teacher_answer_match_gold") is True
    ]
    fallback_appended = [
        row for row in rows if row.get("boxed_fallback_appended") is True
    ]
    matched_fallback = [
        row for row in answer_matched if row.get("boxed_fallback_appended") is True
    ]
    answer_matched_non_fallback = [
        row for row in answer_matched if row.get("boxed_fallback_appended") is not True
    ]
    fallback_rejected_from_previous_safe = sum(
        _is_chinese_like(str(row.get("teacher_solution") or ""))
        for row in matched_fallback
    )
    matched_chinese = [
        row
        for row in answer_matched_non_fallback
        if _is_chinese_like(str(row.get("teacher_solution") or ""))
    ]

    safe_rows: list[dict[str, Any]] = []
    rejected_empty = 0
    rejected_missing_boxed = 0
    for row in matched_chinese:
        solution = str(row.get("teacher_solution") or "").strip()
        if not solution:
            rejected_empty += 1
            continue
        if extract_boxed_answer(solution) is None:
            rejected_missing_boxed += 1
            continue

        safe_row = {field: row.get(field, "") for field in SAFE_TEACHER_FIELDS}
        safe_row["teacher_solution"] = solution
        safe_row["has_boxed_answer"] = True
        safe_row["teacher_answer_match_gold"] = True
        safe_row["boxed_fallback_appended"] = False
        safe_rows.append(safe_row)

    _atomic_write_jsonl(output_path, safe_rows)
    summary = {
        "input_total": len(rows),
        "answer_match_count": len(answer_matched),
        "answer_mismatch_count": len(rows) - len(answer_matched),
        "fallback_appended_count": len(fallback_appended),
        "answer_matched_fallback_count": len(matched_fallback),
        "fallback_rejected_from_previous_safe_count": (
            fallback_rejected_from_previous_safe
        ),
        "answer_matched_non_fallback_count": len(answer_matched_non_fallback),
        "matched_but_chinese_not_qualified": (
            len(answer_matched_non_fallback) - len(matched_chinese)
        ),
        "matched_chinese_but_empty_count": rejected_empty,
        "matched_chinese_but_missing_boxed_count": rejected_missing_boxed,
        "strict_teacher_data_count": len(safe_rows),
        "strict_data_file": str(output_path),
    }
    _write_json(summary_path, summary)

    audit_lines = [
        "# 安全教师数据过滤审计",
        "",
        "## 过滤结果",
        "",
        f"- 输入教师样本：{summary['input_total']}",
        f"- 最终答案与 gold 匹配：{summary['answer_match_count']}",
        f"- 最终答案与 gold 不匹配：{summary['answer_mismatch_count']}",
        f"- 原始数据包含 fallback：{summary['fallback_appended_count']}",
        f"- 答案匹配但属于 fallback：{summary['answer_matched_fallback_count']}",
        (
            "- 从旧版安全数据口径中排除的 fallback："
            f"{summary['fallback_rejected_from_previous_safe_count']}"
        ),
        (
            "- 答案匹配且非 fallback："
            f"{summary['answer_matched_non_fallback_count']}"
        ),
        (
            "- 答案匹配但中文比例不合格："
            f"{summary['matched_but_chinese_not_qualified']}"
        ),
        f"- 中文合格但内容为空：{summary['matched_chinese_but_empty_count']}",
        (
            "- 中文合格但缺少 boxed 答案："
            f"{summary['matched_chinese_but_missing_boxed_count']}"
        ),
        f"- 最终严格教师样本：{summary['strict_teacher_data_count']}",
        f"- 严格数据文件：`{summary['strict_data_file']}`",
        "",
        "## 为什么只保留安全样本",
        "",
        "- Teacher SFT 不能使用最终答案与 gold 不匹配的样本，否则会把教师错误直接监督给学生模型。",
        "- 脚本追加 gold 形成的 boxed fallback 不属于教师独立推理，必须排除。",
        "- 中文比例不合格的解法会重新引入训练数据与中文固定评测 prompt 之间的分布差异。",
        "- 空输出或缺少 `\\boxed{}` 的样本不满足当前项目的统一回答协议。",
        "- 少量高质量、答案可验证的数据优先于大量低质量或存在标签噪声的数据。",
        "",
        "该过滤过程只读取已生成的教师数据，不调用模型，也不修改固定 200 题正式评测集。",
        "",
    ]
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text("\n".join(audit_lines), encoding="utf-8")

    print(f"Wrote safe teacher data: {output_path}")
    print(f"Wrote safe filter summary: {summary_path}")
    print(f"Wrote safe filter audit: {audit_path}")


def _default_model_tag(model_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", model_name.lower()).strip("_")


def _resolve_generation_config(
    config: dict[str, Any],
    model_name_override: str | None,
    model_tag_override: str | None,
    max_samples_override: int | None,
    output_override: Path | None,
) -> tuple[dict[str, Any], str]:
    resolved = dict(config)
    candidates = config.get("models", [])
    selected: dict[str, Any] | None = None
    if isinstance(candidates, list) and candidates:
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            if model_name_override and candidate.get("name") == model_name_override:
                selected = candidate
                break
            if model_tag_override and candidate.get("tag") == model_tag_override:
                selected = candidate
                break
        if selected is None:
            raise ValueError(
                "Tournament config requires --model_name or --model_tag matching a models entry."
            )
        resolved.update(
            {key: value for key, value in selected.items() if key not in {"name", "tag"}}
        )

    model_name = model_name_override or (
        str(selected["name"]) if selected else str(_required(resolved, "teacher_model"))
    )
    model_tag = model_tag_override or (
        str(selected.get("tag")) if selected and selected.get("tag") else _default_model_tag(model_name)
    )
    resolved["teacher_model"] = model_name
    resolved["model_tag"] = model_tag
    resolved["input_file"] = resolved.get("input_file") or resolved.get("train_file")
    resolved["prompt_template"] = resolved.get("prompt_template") or resolved.get(
        "teacher_prompt_template"
    )
    if max_samples_override is not None:
        resolved["max_samples"] = max_samples_override
    elif "max_samples" not in resolved:
        resolved["max_samples"] = resolved.get("teacher_pilot_samples", 300)
    if output_override is not None:
        resolved["output_file"] = str(output_override)
    elif not resolved.get("output_file"):
        resolved["output_file"] = (
            f"data/processed/teacher_pilot_{model_tag}_{resolved['max_samples']}.jsonl"
        )
    if isinstance(candidates, list) and candidates:
        resolved["summary_file"] = f"results/teacher_pilot_summary_{model_tag}.json"
        resolved["audit_file"] = f"results/teacher_pilot_audit_{model_tag}.md"
    return resolved, model_tag


def generate(
    config_path: Path,
    model_name_override: str | None = None,
    model_tag_override: str | None = None,
    max_samples_override: int | None = None,
    output_override: Path | None = None,
) -> None:
    import torch
    from tqdm import tqdm

    invocation_started = time.monotonic()
    config, model_tag = _resolve_generation_config(
        _load_yaml(config_path),
        model_name_override,
        model_tag_override,
        max_samples_override,
        output_override,
    )
    input_path = Path(str(_required(config, "input_file")))
    output_path = Path(str(_required(config, "output_file")))
    summary_path = Path(
        str(config.get("summary_file", "results/teacher_data_summary.json"))
    )
    audit_path = Path(str(config.get("audit_file", "results/teacher_data_audit.md")))
    prompt_template = str(_required(config, "prompt_template"))
    max_samples = int(config.get("max_samples", 1000))
    save_every = max(1, int(config.get("save_every", 50)))
    seed = int(config.get("seed", 20260618))

    if max_samples < 1:
        raise ValueError("max_samples must be at least 1")
    if not input_path.exists():
        raise FileNotFoundError(
            f"Teacher input file not found: {input_path}. Restore the fixed Stage 4 data."
        )
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required. Run Stage 6.1 on the remote GPU server.")

    source_rows = _read_jsonl(input_path)[:max_samples]
    if len(source_rows) < max_samples:
        raise ValueError(
            f"Input contains only {len(source_rows)} rows, fewer than max_samples={max_samples}."
        )

    source_ids: list[str] = []
    seen_source_ids: set[str] = set()
    for index, row in enumerate(source_rows):
        row_id = str(row.get("id") or "").strip()
        if not row_id:
            raise ValueError(f"Input sample {index + 1} is missing a stable id.")
        if row_id in seen_source_ids:
            raise ValueError(f"Input contains duplicate id: {row_id}")
        seen_source_ids.add(row_id)
        source_ids.append(row_id)

    output_rows = _read_jsonl(output_path) if output_path.exists() else []
    completed_ids: set[str] = set()
    for row in output_rows:
        row_id = str(row.get("id") or "")
        if not row_id:
            raise ValueError(f"Existing output contains a row without id: {output_path}")
        if row_id in completed_ids:
            raise ValueError(f"Existing output contains duplicate id: {row_id}")
        if row_id not in seen_source_ids:
            raise ValueError(
                f"Existing output id is not part of the configured first "
                f"{max_samples} input samples: {row_id}"
            )
        completed_ids.add(row_id)

    pending_rows = [
        (index, source_ids[index], row)
        for index, row in enumerate(source_rows)
        if source_ids[index] not in completed_ids
    ]
    previous_summary = _read_json_if_exists(summary_path)
    previous_errors = previous_summary.get("generation_errors", [])
    if not isinstance(previous_errors, list):
        previous_errors = []
    previous_empty_count = int(previous_summary.get("empty_output_count", 0) or 0)
    previous_non_chinese_count = int(
        previous_summary.get("non_chinese_like_count", 0) or 0
    )
    previous_fallback_count = int(
        previous_summary.get("append_boxed_fallback_count", 0) or 0
    )
    previous_elapsed_seconds = float(
        previous_summary.get("generation_elapsed_seconds", 0.0) or 0.0
    )

    if not pending_rows:
        print(f"All {len(output_rows)} teacher samples already exist; rebuilding audit only.")
        summary = _summarize(
            config,
            output_rows,
            max_samples,
            empty_output_count=previous_empty_count,
            non_chinese_like_count=previous_non_chinese_count,
            append_boxed_fallback_count=previous_fallback_count,
            generation_errors=previous_errors,
            status="completed",
        )
        summary["generation_elapsed_seconds"] = previous_elapsed_seconds
        summary["generation_samples_per_second"] = (
            len(output_rows) / previous_elapsed_seconds
            if previous_elapsed_seconds > 0
            else None
        )
        _write_json(summary_path, summary)
        _write_audit(audit_path, summary, output_rows)
        return

    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    tokenizer, model = _load_teacher_model(config)
    input_device = _model_input_device(model)

    max_new_tokens = int(config.get("max_new_tokens", 2048))
    do_sample = bool(config.get("do_sample", True))
    generation_kwargs: dict[str, Any] = {
        "max_new_tokens": max_new_tokens,
        "do_sample": do_sample,
        "pad_token_id": tokenizer.pad_token_id,
        "eos_token_id": tokenizer.eos_token_id,
    }
    if do_sample:
        generation_kwargs.update(
            {
                "temperature": float(config.get("temperature", 0.2)),
                "top_p": float(config.get("top_p", 0.9)),
            }
        )

    empty_output_count = previous_empty_count
    non_chinese_like_count = previous_non_chinese_count
    append_boxed_fallback_count = previous_fallback_count
    generation_errors: list[dict[str, Any]] = list(previous_errors)
    generated_since_save = 0
    interrupted = False

    try:
        for index, row_id, row in tqdm(pending_rows, desc="Teacher generation"):
            problem = str(row.get("problem") or "").strip()
            answer = str(row.get("answer") or "").strip()
            if not problem or not answer:
                generation_errors.append(
                    {
                        "id": row_id,
                        "type": "invalid_source_sample",
                        "error": "Missing problem or gold answer.",
                    }
                )
                continue

            try:
                per_sample_seed = seed + index
                random.seed(per_sample_seed)
                torch.manual_seed(per_sample_seed)
                torch.cuda.manual_seed_all(per_sample_seed)

                prompt = _render_prompt(prompt_template, problem, answer)
                input_ids = _chat_input_ids(tokenizer, prompt, input_device)
                with torch.inference_mode():
                    generated = model.generate(input_ids=input_ids, **generation_kwargs)
                new_tokens = generated[0, input_ids.shape[-1] :]
                teacher_solution = tokenizer.decode(
                    new_tokens,
                    skip_special_tokens=True,
                ).strip()
            except Exception as exc:
                generation_errors.append(
                    {
                        "id": row_id,
                        "type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                continue

            if not teacher_solution:
                empty_output_count += 1
                generation_errors.append(
                    {
                        "id": row_id,
                        "type": "empty_output",
                        "error": "Teacher model returned an empty response.",
                    }
                )
                continue

            if not _is_chinese_like(teacher_solution):
                non_chinese_like_count += 1

            boxed_fallback_appended = extract_boxed_answer(teacher_solution) is None
            if boxed_fallback_appended:
                teacher_solution = (
                    teacher_solution.rstrip()
                    + f"\n\n最终答案：\\boxed{{{answer}}}"
                )
                append_boxed_fallback_count += 1

            answer_match, match_method = _score_teacher_answer(teacher_solution, answer)
            output_rows.append(
                _build_output_row(
                    row,
                    row_id,
                    teacher_solution,
                    answer_match,
                    match_method,
                    boxed_fallback_appended,
                    str(config["teacher_model"]),
                    model_tag,
                )
            )
            completed_ids.add(row_id)
            generated_since_save += 1

            if generated_since_save >= save_every:
                _atomic_write_jsonl(output_path, output_rows)
                generated_since_save = 0
                print(f"Checkpoint saved: {len(output_rows)}/{max_samples}")
    except KeyboardInterrupt:
        interrupted = True
        print("Generation interrupted; saving completed teacher samples.")
    finally:
        _atomic_write_jsonl(output_path, output_rows)
        status = (
            "completed"
            if len(output_rows) >= max_samples
            else "interrupted"
            if interrupted
            else "completed_with_errors"
        )
        summary = _summarize(
            config,
            output_rows,
            max_samples,
            empty_output_count,
            non_chinese_like_count,
            append_boxed_fallback_count,
            generation_errors,
            status,
        )
        elapsed_seconds = previous_elapsed_seconds + (
            time.monotonic() - invocation_started
        )
        summary["generation_elapsed_seconds"] = elapsed_seconds
        summary["generation_samples_per_second"] = (
            len(output_rows) / elapsed_seconds if elapsed_seconds > 0 else None
        )
        _write_json(summary_path, summary)
        _write_audit(audit_path, summary, output_rows)
        print(f"Wrote teacher data: {output_path}")
        print(f"Wrote summary: {summary_path}")
        print(f"Wrote audit: {audit_path}")


def _summary_rate(summary: dict[str, Any], rate_key: str, count_key: str) -> float | None:
    value = summary.get(rate_key)
    if isinstance(value, (int, float)):
        return float(value)
    count = summary.get(count_key)
    total = summary.get("actual_samples") or summary.get("input_total")
    if isinstance(count, (int, float)) and isinstance(total, (int, float)) and total:
        return float(count) / float(total)
    return None


def _tournament_recommendation(
    eval_accuracy: float | None,
    safe_rate: float | None,
    answer_rate: float | None,
    chinese_rate: float | None,
    baseline_accuracy: float,
) -> str:
    if None in {eval_accuracy, safe_rate, answer_rate, chinese_rate}:
        return "结果缺失"
    assert eval_accuracy is not None
    assert safe_rate is not None
    assert answer_rate is not None
    assert chinese_rate is not None
    if (
        eval_accuracy > baseline_accuracy
        and safe_rate > 0.70
        and answer_rate > 0.75
        and chinese_rate > 0.80
    ):
        return "推荐进入下一轮"
    if eval_accuracy > baseline_accuracy:
        return "推理更强，但生成质量未达标"
    return "不优于现有 Qwen 7B"


def summarize_tournament(config_path: Path, output_path: Path, json_path: Path) -> None:
    config = _load_yaml(config_path)
    candidates = config.get("models")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Tournament config must define a non-empty models list.")

    baseline_eval = _read_json_if_exists(Path("results/teacher_7b_summary.json"))
    if not baseline_eval:
        baseline_eval = _read_json_if_exists(
            Path("results/teacher_summary_qwen2_5_math_7b.json")
        )
    baseline_accuracy = float(baseline_eval.get("accuracy", 0.32))

    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or not candidate.get("name") or not candidate.get("tag"):
            raise ValueError("Each tournament model requires name and tag.")
        model_name = str(candidate["name"])
        tag = str(candidate["tag"])
        eval_summary = _read_json_if_exists(Path(f"results/teacher_summary_{tag}.json"))
        pilot_summary = _read_json_if_exists(
            Path(f"results/teacher_pilot_summary_{tag}.json")
        )
        eval_accuracy = (
            float(eval_summary["accuracy"]) if "accuracy" in eval_summary else None
        )
        boxed_rate = (
            float(eval_summary["boxed_answer_rate"])
            if "boxed_answer_rate" in eval_summary
            else None
        )
        extraction_rate = (
            float(eval_summary["extraction_success_rate"])
            if "extraction_success_rate" in eval_summary
            else None
        )
        safe_rate = _summary_rate(
            pilot_summary, "safe_teacher_data_rate", "safe_teacher_data_count"
        )
        answer_rate = _summary_rate(
            pilot_summary, "answer_match_gold_rate", "answer_match_gold_count"
        )
        chinese_rate = _summary_rate(
            pilot_summary, "chinese_like_rate", "chinese_like_count"
        )
        rows.append(
            {
                "teacher": model_name,
                "tag": tag,
                "eval_accuracy": eval_accuracy,
                "boxed_rate": boxed_rate,
                "extraction_rate": extraction_rate,
                "pilot_safe_rate": safe_rate,
                "answer_match_rate": answer_rate,
                "chinese_rate": chinese_rate,
                "avg_length": pilot_summary.get("avg_teacher_solution_length"),
                "pilot_status": pilot_summary.get("status", "missing"),
                "generation_error_count": pilot_summary.get("generation_error_count"),
                "runtime_note": (
                    f"4-bit on GPU {candidate.get('cuda_visible_devices', '?')}; "
                    f"elapsed={pilot_summary.get('generation_elapsed_seconds', 'N/A')}s; "
                    f"speed={pilot_summary.get('generation_samples_per_second', 'N/A')} samples/s"
                ),
                "recommendation": _tournament_recommendation(
                    eval_accuracy,
                    safe_rate,
                    answer_rate,
                    chinese_rate,
                    baseline_accuracy,
                ),
            }
        )

    if baseline_eval:
        baseline_pilot = _read_json_if_exists(Path("results/teacher_data_summary.json"))
        strict_summary = _read_json_if_exists(
            Path("results/teacher_data_strict_599_summary.json")
        )
        safe_rate = _summary_rate(
            strict_summary, "safe_teacher_data_rate", "strict_teacher_data_count"
        )
        answer_rate = _summary_rate(
            baseline_pilot,
            "answer_match_gold_rate",
            "teacher_answer_match_gold_count",
        )
        chinese_rate = _summary_rate(
            baseline_pilot, "chinese_like_rate", "chinese_like_count"
        )
        if chinese_rate is None and baseline_pilot.get("actual_samples"):
            chinese_rate = 1.0 - float(
                baseline_pilot.get("non_chinese_like_count", 0)
            ) / float(baseline_pilot["actual_samples"])
        rows.insert(
            0,
            {
                "teacher": "Qwen/Qwen2.5-Math-7B-Instruct",
                "tag": "qwen2_5_math_7b",
                "eval_accuracy": float(baseline_eval.get("accuracy", 0.0)),
                "boxed_rate": baseline_eval.get("boxed_answer_rate"),
                "extraction_rate": baseline_eval.get("extraction_success_rate"),
                "pilot_safe_rate": safe_rate,
                "answer_match_rate": answer_rate,
                "chinese_rate": chinese_rate,
                "avg_length": baseline_pilot.get("avg_teacher_solution_length"),
                "pilot_status": baseline_pilot.get("status", "completed"),
                "generation_error_count": baseline_pilot.get("generation_error_count"),
                "runtime_note": "existing 7B baseline",
                "recommendation": "现有基准",
            },
        )

    payload = {
        "stage": "stage-6A-teacher-tournament",
        "baseline_teacher_accuracy": baseline_accuracy,
        "thresholds": {
            "eval_accuracy": f"> {baseline_accuracy}",
            "pilot_safe_rate": "> 0.70",
            "answer_match_rate": "> 0.75",
            "chinese_rate": "> 0.80",
        },
        "teachers": rows,
    }
    _write_json(json_path, payload)

    def display(value: Any, percent: bool = True) -> str:
        if not isinstance(value, (int, float)):
            return "N/A"
        return f"{float(value):.2%}" if percent else f"{float(value):.1f}"

    lines = [
        "# Stage 6A Teacher Tournament",
        "",
        "| Teacher | Eval Accuracy | Boxed Rate | Extraction Rate | Pilot Safe Rate | Answer Match Rate | Chinese Rate | Avg Length | Recommendation |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['teacher']} | {display(row['eval_accuracy'])} | "
            f"{display(row['boxed_rate'])} | {display(row['extraction_rate'])} | "
            f"{display(row['pilot_safe_rate'])} | {display(row['answer_match_rate'])} | "
            f"{display(row['chinese_rate'])} | {display(row['avg_length'], False)} | "
            f"{row['recommendation']} |"
        )
    lines.extend(["", "## Runtime And Stability Notes", ""])
    for row in rows:
        lines.append(
            f"- `{row['tag']}`: status={row['pilot_status']}, "
            f"generation_errors={row['generation_error_count']}, {row['runtime_note']}."
        )
    lines.extend(
        [
            "",
            "Safe rate uses the strict definition and excludes gold-appended boxed fallback rows.",
            "The final selection must consider both formal evaluation accuracy and pilot response quality.",
            "",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote tournament summary: {output_path}")
    print(f"Wrote tournament JSON: {json_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or safely filter the Stage 6 teacher-response dataset."
    )
    parser.add_argument("--config", help="Teacher generation YAML config.")
    parser.add_argument("--model_name", help="Teacher model override.")
    parser.add_argument("--model_tag", help="Stable tag used in tournament output names.")
    parser.add_argument("--max_samples", type=int, help="Teacher sample count override.")
    parser.add_argument(
        "--summarize_tournament",
        action="store_true",
        help="Summarize completed teacher tournament result files.",
    )
    parser.add_argument("--output", help="Tournament Markdown summary path.")
    parser.add_argument("--json_output", help="Tournament JSON summary path.")
    parser.add_argument(
        "--filter_safe",
        action="store_true",
        help="Filter an existing teacher JSONL into the safe Teacher SFT dataset.",
    )
    parser.add_argument("--input_file", help="Input teacher JSONL for --filter_safe.")
    parser.add_argument("--output_file", help="Output safe JSONL for --filter_safe.")
    parser.add_argument(
        "--summary_file",
        default="results/teacher_data_strict_599_summary.json",
        help="Strict filter summary JSON path.",
    )
    parser.add_argument(
        "--audit_file",
        default="results/teacher_data_strict_599_audit.md",
        help="Strict filter audit Markdown path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.summarize_tournament:
        if not args.config or not args.output or not args.json_output:
            raise SystemExit(
                "--summarize_tournament requires --config, --output, and --json_output."
            )
        summarize_tournament(
            Path(args.config), Path(args.output), Path(args.json_output)
        )
        return
    if args.filter_safe:
        if not args.input_file or not args.output_file:
            raise SystemExit("--filter_safe requires --input_file and --output_file.")
        filter_safe_teacher_data(
            Path(args.input_file),
            Path(args.output_file),
            Path(args.summary_file),
            Path(args.audit_file),
        )
        return
    if not args.config:
        raise SystemExit("Generation mode requires --config.")
    generate(
        Path(args.config),
        model_name_override=args.model_name,
        model_tag_override=args.model_tag,
        max_samples_override=args.max_samples,
        output_override=Path(args.output_file) if args.output_file else None,
    )


if __name__ == "__main__":
    main()
