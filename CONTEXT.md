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

主评分器为 Math-Verify，使用 final-answer equivalence 判断最终答案是否等价。主指标为 Final Answer Accuracy，辅助指标包括 Boxed Answer Rate、Extraction Success Rate 和 Error Type Distribution。

## Hardware Plan

远端 2xRTX4090 服务器负责模型下载、数据处理、训练、评测和 checkpoint 保存。

## Local/Remote Execution Rule

本地 Windows 只用于 VSCode/Codex 编辑代码，不运行模型推理和训练。所有模型下载、Hugging Face cache、数据处理、训练、评测和 checkpoint 保存都必须在远端 2xRTX4090 服务器执行。Codex 主要修改本地文件，并给出我手动同步到远端和运行的命令。

## Current Stage

Stage 0 - 初始化项目骨架、本地 Git、远端运行说明、新虚拟环境说明。

## Completed

- 创建项目基础目录结构。
- 创建 README、CONTEXT、requirements、.gitignore。
- 创建 Stage 0 所需配置文件占位。
- 创建脚本占位文件，标注后续 Stage 实现范围。
- 创建 data 说明文件。
- 初始化本地 Git 仓库。

## Next Stage

Stage 1 - Scoring Protocol and Dataset Inspection，接入 Math-Verify，检查公开数据集字段。

## Git Rule

每个阶段完成后更新 `CONTEXT.md`，进行 git commit，并 push 到 GitHub。远程仓库地址由用户提供，Codex 不自动创建 GitHub 远程仓库。
