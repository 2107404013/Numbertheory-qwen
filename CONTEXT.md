# CONTEXT

## Project Name

NumberTheory-Qwen

## Project Goal

基于 `Qwen/Qwen2.5-Math-1.5B-Instruct`，构建一个面向高中竞赛数论题的轻量级数学问答助手。后续通过 LoRA SFT、`Qwen/Qwen2.5-Math-7B-Instruct` 教师答案蒸馏、GRPO 强化学习微调，以及可选白盒 logits 蒸馏，提升模型在数论竞赛题上的最终答案正确率和输出规范性。

## Target Domain

高中竞赛数论。

## Student Model

`Qwen/Qwen2.5-Math-1.5B-Instruct`

## Teacher Model

`Qwen/Qwen2.5-Math-7B-Instruct`

## Formal Eval Dataset

优先使用 `KbsdJames/Omni-MATH` 的 Number Theory 子集，并参考 `KbsdJames/omni-math-rule` GitHub 仓库中的 rule-based subset 过滤标准。`Omni-MATH-Rule` 不是直接的 Hugging Face dataset name，不能使用 `datasets.load_dataset("Omni-MATH-Rule")`。正式 eval 目标规模为 200 道。

## Training Dataset

`AI-MO/NuminaMath-1.5` 中的 Number Theory 子集。第一版训练规模为 5k，确认提升后扩展到 10k。`AI-MO/NuminaMath-CoT` 作为备用训练数据源。

## Prompt Language

中文。

## Scoring Protocol

主评分器为 Math-Verify，使用 final-answer equivalence 判断最终答案是否等价。主指标为 Final Answer Accuracy，辅助指标包括 Boxed Answer Rate、Extraction Success Rate 和 Error Type Distribution。自定义 normalize、列表答案、简单数值和 sympy 等价判断只作为 fallback。

## Hardware Plan

远端 2xRTX4090 服务器负责模型下载、数据处理、训练、评测和 checkpoint 保存。

## Local/Remote Execution Rule

本地 Windows 只用于 VSCode/Codex 编辑代码，不运行模型推理和训练。所有模型下载、Hugging Face cache、数据处理、训练、评测和 checkpoint 保存都必须在远端 2xRTX4090 服务器执行。Codex 主要修改本地文件，并给出我手动同步到远端和运行的命令。

## Current Stage

Stage 4 - Prepare Number Theory SFT Data

## Stage 4 Goal

- 从 `AI-MO/NuminaMath-1.5` 中筛选 5k 条数论 SFT 训练数据。
- 与固定的 200 道正式 eval 进行精确和近似去重。
- 生成 `data/processed/train_number_theory_sft_5k.jsonl`。
- 生成 `results/train_data_summary.json`。
- 不训练，不推理，不下载 Qwen 权重。

## Previous Stage

- Stage 3 formal baseline completed。
- Baseline model: `Qwen/Qwen2.5-Math-1.5B-Instruct`。
- Total: 200。
- Correct: 55。
- Final Answer Accuracy: 0.275。
- Boxed Answer Rate: 0.885。
- Extraction Success Rate: 0.885。
- 该 baseline 难度适合后续训练对比。

## Formal Evaluation Plan

- 如果能读取 `KbsdJames/omni-math-rule` 的 GitHub raw rule-based subset，则优先使用该子集。
- 否则从 `KbsdJames/Omni-MATH` 中筛选 Number Theory 子集。
- 目标规模为 200 道。
- 使用固定 seed：20260618。
- 只保留纯文本、短答案、适合 rule-based evaluation 的题。
- 一旦正式 eval 生成，后续 Stage 3、Stage 5、Stage 6、Stage 7 和 Stage 8 都必须使用同一份 eval，不得随意改动。
- 如果不足 200 道，不造题、不混入非数论题，在 summary 中如实记录实际数量和原因。

## Training Data Plan

- 使用 `AI-MO/NuminaMath-1.5` Number Theory 子集。
- 第一版 5k。
- 后续扩展到 10k。
- 必须和正式 eval 去重。
- `AI-MO/NuminaMath-CoT` 作为备用训练数据源。

## Completed

- Stage 0: 创建项目基础目录结构、README、CONTEXT、requirements、.gitignore、配置文件、脚本占位和 data 说明文件。
- Stage 0: 初始化本地 Git 仓库，并推送到 GitHub。
- Stage 1: 接入 Math-Verify 主评分器、fallback 等价判断、evaluator unit tests 和 JSONL 数据审计入口。
- Stage 1: 修正公开数据源检查逻辑，避免错误调用 `datasets.load_dataset("Omni-MATH-Rule")`。
- Stage 2: 实现 `scripts/prepare_data.py --mode build_eval --max_eval_samples 200`。
- Stage 2: 更新 `scripts/eval_math.py --audit_data`，输出正式 eval 审计文件。
- Stage 2: 更新 `configs/baseline_eval.yaml` 指向正式 eval 文件。
- Stage 2: 正式 eval 已在远端生成并通过审计，共 200 道 rule-based subset 数论题。
- Stage 3: 实现 `scripts/eval_math.py --config configs/baseline_eval.yaml` 的正式 baseline
  推理、Math-Verify + fallback 评分、汇总指标和错误分析输出。
- Stage 3: 正式 baseline 已在远端完成，Final Answer Accuracy 为 0.275（55/200）。
- Stage 4: 实现 `scripts/prepare_data.py --mode build_train --max_train_samples 5000`。
- Stage 4: 训练数据构建包含字段优先数论筛选、质量过滤、eval 精确及 0.85 近似去重。

## Next Stage

Stage 5 - LoRA SFT。只有在用户确认 Stage 4 训练数据结果合格并保存后才能进入。

## Git Rule

每个阶段完成后更新 `CONTEXT.md`，进行 git commit，并 push 到 GitHub。远程仓库地址由用户提供，Codex 不自动创建 GitHub 远程仓库。
