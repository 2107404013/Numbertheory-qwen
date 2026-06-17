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

`Omni-MATH-Rule` / `Omni-MATH` 中的 Number Theory 子集，正式 eval 规模为 200 道。

## Training Dataset

`NuminaMath-1.5` 中的 Number Theory 子集。第一版训练规模为 5k，确认提升后扩展到 10k。

## Prompt Language

中文。

## Scoring Protocol

主评分器为 Math-Verify，使用 final-answer equivalence 判断最终答案是否等价。主指标为 Final Answer Accuracy，辅助指标包括 Boxed Answer Rate、Extraction Success Rate 和 Error Type Distribution。自定义 normalize、列表答案、简单数值和 sympy 等价判断只作为 fallback。

## Hardware Plan

远端 2xRTX4090 服务器负责模型下载、数据处理、训练、评测和 checkpoint 保存。

## Local/Remote Execution Rule

本地 Windows 只用于 VSCode/Codex 编辑代码，不运行模型推理和训练。所有模型下载、Hugging Face cache、数据处理、训练、评测和 checkpoint 保存都必须在远端 2xRTX4090 服务器执行。Codex 主要修改本地文件，并给出我手动同步到远端和运行的命令。

## Current Stage

Stage 1 - Scoring Protocol and Dataset Inspection

## Stage 1 Goal

- 接入 Math-Verify。
- 检查公开数据集字段。
- 确认正式数论 eval 和训练数据来源。
- 建立 evaluator unit tests。
- 不训练，不推理，不下载模型权重。

## Formal Evaluation Plan

- 正式 eval 使用 `Omni-MATH-Rule` / `Omni-MATH` 中的 Number Theory 子集。
- 规模为 200 道。
- 只保留纯文本、短答案、适合 rule-based evaluation 的题。

## Training Data Plan

- 使用 `NuminaMath-1.5` Number Theory 子集。
- 第一版 5k。
- 后续扩展到 10k。
- 必须和正式 eval 去重。

## Completed

- Stage 0: 创建项目基础目录结构、README、CONTEXT、requirements、.gitignore、配置文件、脚本占位和 data 说明文件。
- Stage 0: 初始化本地 Git 仓库，并推送到 GitHub。
- Stage 1: 在 `scripts/prepare_data.py` 中实现公开数据集字段检查入口 `--mode inspect_public`。
- Stage 1: 在 `scripts/eval_math.py` 中实现 Math-Verify 主评分器、fallback 等价判断、evaluator unit tests 和 JSONL 数据审计入口。
- Stage 1: 更新 README 中的 Scoring Protocol。

## Next Stage

Stage 2 - Build Formal Number Theory Evaluation Set

## Git Rule

每个阶段完成后更新 `CONTEXT.md`，进行 git commit，并 push 到 GitHub。远程仓库地址由用户提供，Codex 不自动创建 GitHub 远程仓库。
