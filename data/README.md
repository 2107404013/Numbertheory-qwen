# Data Directory

`data/raw/` 和 `data/processed/` 不进入 Git。

Stage 2 会在远端服务器生成正式评测集：

- `data/processed/public_number_theory_eval.jsonl`

该文件用于后续 Baseline、LoRA SFT、Teacher Response Distillation、GRPO 和可选蒸馏阶段的统一评测，但不会提交到 GitHub。

为了保证可复现，Stage 2 会提交轻量级结果文件：

- `results/public_eval_data_summary.json`
- `results/public_eval_manifest.json`
- `results/evaluator_audit.md`

训练集会由 Stage 4 生成，第一版规模为 5k 数论样本。

不要手动上传大数据、模型权重或 Hugging Face cache 到 GitHub。
