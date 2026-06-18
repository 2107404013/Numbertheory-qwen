# Data Directory

`data/raw/` 和 `data/processed/` 不进入 Git。

Stage 2 会在远端服务器生成正式评测集：

- `data/processed/public_number_theory_eval.jsonl`

该文件用于后续 Baseline、LoRA SFT、Teacher Response Distillation、GRPO 和可选蒸馏阶段的统一评测，但不会提交到 GitHub。

为了保证可复现，Stage 2 会提交轻量级结果文件：

- `results/public_eval_data_summary.json`
- `results/public_eval_manifest.json`
- `results/evaluator_audit.md`

Stage 4 会从 `AI-MO/NuminaMath-1.5` 生成第一版 5000 条 Number Theory SFT 训练数据：

- `data/processed/train_number_theory_sft_5k.jsonl`

训练集必须与 `data/processed/public_number_theory_eval.jsonl` 中固定的 200 道正式评测题
进行精确和近似去重。训练数据本体不提交 GitHub，只提交
`results/train_data_summary.json` 记录筛选与去重统计。

后续只有在 LoRA SFT 相对正式 baseline 确认提升后，才会把训练规模扩展到 10000 条。

Stage 6.1 会在远端生成 1000 条教师答案试验数据：

- `data/processed/train_number_theory_teacher_1k.jsonl`

该数据由 `Qwen/Qwen2.5-Math-7B-Instruct` 根据原始数论题和 gold answer 生成，目标格式为
中文、步骤清晰、竞赛教练风格，并在最后一行提供 `\boxed{}` 答案。教师数据本体仍属于
`data/processed/`，不得提交 GitHub；只提交
`results/teacher_data_summary.json` 和 `results/teacher_data_audit.md`。

不要手动上传大数据、模型权重或 Hugging Face cache 到 GitHub。
