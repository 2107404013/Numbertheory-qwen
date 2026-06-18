"""Train the Stage 5 Number Theory LoRA adapter."""

from __future__ import annotations

import argparse
import inspect
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SYSTEM_PROMPT = "你是一名高中数学竞赛数论教练。"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required. Install requirements.txt on the remote server.") from exc

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
            if not str(row.get("problem") or "").strip():
                raise ValueError(f"Missing problem at {path}:{line_no}")
            if not str(row.get("solution") or "").strip():
                raise ValueError(f"Missing solution at {path}:{line_no}")
            rows.append(row)
    if not rows:
        raise ValueError(f"No training samples found in {path}")
    return rows


def _render_user_prompt(template: str, problem: str) -> str:
    if "{problem}" not in template:
        raise ValueError("training_prompt_template must contain the literal placeholder {problem}")
    rendered = template.replace("{problem}", problem).strip()
    # Keep the coach identity in the system turn instead of duplicating it for the user.
    if rendered.startswith(SYSTEM_PROMPT):
        rendered = rendered[len(SYSTEM_PROMPT) :].lstrip()
    return rendered


class AssistantOnlyDataset:
    """Tokenize chat examples and mask the system/user prefix from the loss."""

    def __init__(
        self,
        rows: list[dict[str, Any]],
        tokenizer: Any,
        prompt_template: str,
        max_seq_len: int,
        min_assistant_tokens: int,
    ) -> None:
        self.examples: list[dict[str, list[int]]] = []
        self.truncated_prompt_count = 0
        self.truncated_assistant_count = 0

        if min_assistant_tokens < 1 or min_assistant_tokens >= max_seq_len:
            raise ValueError(
                "min_assistant_tokens must be at least 1 and smaller than max_seq_len"
            )

        for index, row in enumerate(rows, start=1):
            problem = str(row["problem"]).strip()
            solution = str(row["solution"]).strip()
            user_prompt = _render_user_prompt(prompt_template, problem)
            prompt_messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
            prompt_ids = tokenizer.apply_chat_template(
                prompt_messages,
                tokenize=True,
                add_generation_prompt=True,
            )
            assistant_text = solution
            if tokenizer.eos_token and not assistant_text.endswith(tokenizer.eos_token):
                assistant_text += tokenizer.eos_token
            assistant_ids = tokenizer(
                assistant_text,
                add_special_tokens=False,
                truncation=False,
            )["input_ids"]
            prompt_ids = list(prompt_ids)
            assistant_ids = list(assistant_ids)

            if not prompt_ids:
                raise ValueError(
                    f"Tokenizer chat template produced no prompt tokens at sample {index}."
                )
            if not assistant_ids:
                raise ValueError(
                    f"Tokenizer produced no assistant solution tokens at sample {index}."
                )

            # The tokenizer chat template supplies the official system/user layout and
            # assistant generation marker. Encoding the solution separately avoids
            # version-dependent templates that omit assistant content when rendering
            # a completed conversation.
            if len(prompt_ids) + len(assistant_ids) > max_seq_len:
                reserved_assistant = min(len(assistant_ids), min_assistant_tokens)
                max_prompt_tokens = max_seq_len - reserved_assistant
                if len(prompt_ids) > max_prompt_tokens:
                    # Preserve both the chat/system prefix and the end of the user turn,
                    # including its role boundary and assistant generation marker.
                    prefix_tokens = min(64, max_prompt_tokens // 4)
                    suffix_tokens = max_prompt_tokens - prefix_tokens
                    prompt_ids = prompt_ids[:prefix_tokens] + prompt_ids[-suffix_tokens:]
                    self.truncated_prompt_count += 1

            assistant_capacity = max_seq_len - len(prompt_ids)
            retained_assistant_ids = assistant_ids[:assistant_capacity]
            if len(retained_assistant_ids) < len(assistant_ids):
                self.truncated_assistant_count += 1
            if not retained_assistant_ids:
                raise ValueError(
                    f"Sample {index} has no retained assistant tokens at "
                    f"max_seq_len={max_seq_len}."
                )

            input_ids = prompt_ids + retained_assistant_ids
            labels = [-100] * len(prompt_ids) + retained_assistant_ids
            self.examples.append(
                {
                    "input_ids": input_ids,
                    "attention_mask": [1] * len(input_ids),
                    "labels": labels,
                }
            )

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, index: int) -> dict[str, list[int]]:
        return self.examples[index]


class AssistantOnlyCollator:
    def __init__(self, tokenizer: Any) -> None:
        self.tokenizer = tokenizer

    def __call__(self, features: list[dict[str, list[int]]]) -> dict[str, Any]:
        import torch

        max_length = max(len(feature["input_ids"]) for feature in features)
        pad_id = self.tokenizer.pad_token_id
        input_ids: list[list[int]] = []
        attention_mask: list[list[int]] = []
        labels: list[list[int]] = []

        for feature in features:
            padding = max_length - len(feature["input_ids"])
            input_ids.append(feature["input_ids"] + [pad_id] * padding)
            attention_mask.append(feature["attention_mask"] + [0] * padding)
            labels.append(feature["labels"] + [-100] * padding)

        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }


def _write_train_log(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _compatible_training_arguments(training_arguments_class: Any, **kwargs: Any) -> Any:
    """Build TrainingArguments while tolerating optional API differences."""
    supported = set(inspect.signature(training_arguments_class.__init__).parameters)
    required_keys = {
        "output_dir",
        "num_train_epochs",
        "per_device_train_batch_size",
        "gradient_accumulation_steps",
        "learning_rate",
        "bf16",
    }
    unsupported_required = sorted(key for key in required_keys if key not in supported)
    if unsupported_required:
        raise RuntimeError(
            "Installed Transformers TrainingArguments is incompatible; missing required "
            f"arguments: {', '.join(unsupported_required)}"
        )

    compatible_kwargs = {key: value for key, value in kwargs.items() if key in supported}
    ignored_kwargs = sorted(set(kwargs) - set(compatible_kwargs))
    if ignored_kwargs and int(os.environ.get("RANK", "0")) == 0:
        print(
            "Ignoring unsupported optional TrainingArguments: "
            + ", ".join(ignored_kwargs)
        )
    return training_arguments_class(**compatible_kwargs)


def train(config_path: Path) -> None:
    config = _load_yaml(config_path)
    model_name = str(_required(config, "model_name"))
    train_file = Path(str(_required(config, "train_file")))
    output_dir = Path(str(_required(config, "output_dir")))
    train_log_path = Path(str(config.get("train_log", "results/lora_sft_train_log.json")))
    prompt_template = str(_required(config, "training_prompt_template"))
    target_modules = list(_required(config, "target_modules"))
    max_seq_len = int(config.get("max_seq_len", 2048))
    min_assistant_tokens = int(config.get("min_assistant_tokens", 256))
    per_device_batch_size = int(config.get("per_device_train_batch_size", 1))
    gradient_accumulation_steps = int(config.get("gradient_accumulation_steps", 8))
    world_size = int(os.environ.get("WORLD_SIZE", "1"))
    start_time = _utc_now()

    log_data: dict[str, Any] = {
        "status": "running",
        "model_name": model_name,
        "train_file": str(train_file),
        "output_dir": str(output_dir),
        "num_train_samples": 0,
        "max_seq_len": max_seq_len,
        "min_assistant_tokens": min_assistant_tokens,
        "lora_r": int(config.get("lora_r", 16)),
        "lora_alpha": int(config.get("lora_alpha", 32)),
        "learning_rate": float(config.get("learning_rate", 1.0e-4)),
        "num_train_epochs": float(config.get("num_train_epochs", 1)),
        "effective_batch_size": (
            per_device_batch_size * gradient_accumulation_steps * world_size
        ),
        "loss": [],
        "start_time": start_time,
        "end_time": None,
    }

    try:
        import torch
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required. Run LoRA SFT on the remote GPU server.")
        if bool(config.get("bf16", True)) and not torch.cuda.is_bf16_supported():
            raise RuntimeError("The selected CUDA device does not support bf16.")
        if not train_file.exists():
            raise FileNotFoundError(
                f"Training file not found: {train_file}. Restore the fixed Stage 4 5k file."
            )

        rows = _read_jsonl(train_file)
        log_data["num_train_samples"] = len(rows)

        tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = tokenizer.eos_token
        tokenizer.padding_side = "right"

        dataset = AssistantOnlyDataset(
            rows,
            tokenizer,
            prompt_template,
            max_seq_len,
            min_assistant_tokens,
        )
        log_data["truncated_prompt_samples"] = dataset.truncated_prompt_count
        log_data["truncated_assistant_samples"] = dataset.truncated_assistant_count
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.bfloat16,
            low_cpu_mem_usage=True,
        )
        model.config.use_cache = False
        model.enable_input_require_grads()

        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=int(config.get("lora_r", 16)),
            lora_alpha=int(config.get("lora_alpha", 32)),
            lora_dropout=float(config.get("lora_dropout", 0.05)),
            target_modules=target_modules,
            bias="none",
        )
        model = get_peft_model(model, lora_config)
        model.print_trainable_parameters()

        training_args = _compatible_training_arguments(
            TrainingArguments,
            output_dir=str(output_dir),
            num_train_epochs=float(config.get("num_train_epochs", 1)),
            per_device_train_batch_size=per_device_batch_size,
            gradient_accumulation_steps=gradient_accumulation_steps,
            learning_rate=float(config.get("learning_rate", 1.0e-4)),
            weight_decay=float(config.get("weight_decay", 0.0)),
            warmup_ratio=float(config.get("warmup_ratio", 0.03)),
            lr_scheduler_type=str(config.get("lr_scheduler_type", "cosine")),
            bf16=bool(config.get("bf16", True)),
            logging_steps=int(config.get("logging_steps", 10)),
            logging_strategy="steps",
            save_steps=int(config.get("save_steps", 500)),
            save_strategy="steps",
            save_total_limit=int(config.get("save_total_limit", 2)),
            seed=int(config.get("seed", 42)),
            data_seed=int(config.get("seed", 42)),
            report_to="none",
            remove_unused_columns=False,
            save_safetensors=True,
        )
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=dataset,
            data_collator=AssistantOnlyCollator(tokenizer),
        )
        train_result = trainer.train()

        # Trainer delegates to PEFT save_pretrained and only the main process writes files.
        # This saves adapter weights/config, not the full base model.
        trainer.save_model(str(output_dir))
        if trainer.is_world_process_zero():
            tokenizer.save_pretrained(output_dir)

        losses = [
            {"step": item.get("step"), "loss": item["loss"]}
            for item in trainer.state.log_history
            if "loss" in item
        ]
        if trainer.is_world_process_zero():
            log_data.update(
                {
                    "status": "completed",
                    "loss": losses,
                    "final_train_loss": float(train_result.training_loss),
                    "global_step": int(trainer.state.global_step),
                    "end_time": _utc_now(),
                }
            )
            _write_train_log(train_log_path, log_data)
            print(f"Saved LoRA adapter to {output_dir}")
            print(f"Wrote training log to {train_log_path}")
    except Exception as exc:
        log_data.update(
            {
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "end_time": _utc_now(),
            }
        )
        if int(os.environ.get("RANK", "0")) == 0:
            _write_train_log(train_log_path, log_data)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the Stage 5 Number Theory LoRA adapter.")
    parser.add_argument("--config", required=True, help="Path to the LoRA SFT YAML config.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train(Path(args.config))


if __name__ == "__main__":
    main()
