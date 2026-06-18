# NumberTheory-Qwen

## 项目目标

NumberTheory-Qwen 是一个面向高中竞赛数论题的轻量级数学问答助手项目。项目基于 `Qwen/Qwen2.5-Math-1.5B-Instruct` 构建学生模型，并通过后续阶段的 LoRA SFT、教师答案蒸馏、GRPO 强化学习微调，以及可选白盒 logits 蒸馏，提升模型在数论竞赛题上的最终答案正确率和输出规范性。

## 为什么第一版只做数论

第一版只聚焦高中竞赛数论，原因是数论题具有明确的领域边界、常见题型相对集中，且最终答案通常更适合用规则评分器进行等价判断。先在单一子领域建立稳定的数据处理、评测和训练流程，可以降低项目复杂度，便于观察每个训练阶段是否真实提升最终答案正确率。

## 模型选择

- 学生模型：`Qwen/Qwen2.5-Math-1.5B-Instruct`
- 教师模型：`Qwen/Qwen2.5-Math-7B-Instruct`

学生模型用于最终轻量级问答助手；教师模型用于后续生成更规范、更高质量的数论解答数据。

## 数据选择

- 正式评测：优先使用 `KbsdJames/Omni-MATH`，并参考 Omni-MATH rule-based subset 的过滤标准。
- Rule-based subset：来自 `KbsdJames/omni-math-rule` GitHub 仓库，不作为 Hugging Face dataset name 直接加载。
- 训练数据：`AI-MO/NuminaMath-1.5` 的 Number Theory 子集。
- 备用训练数据：`AI-MO/NuminaMath-CoT`。

如果能够读取 GitHub raw 的 `omni_math_rule.jsonl`，则优先使用 rule-based subset 构造正式评测集；否则从 `KbsdJames/Omni-MATH` 中筛选纯文本、短答案、Number Theory 题。正式评测集目标规模第一版固定为 200 道题。训练集第一版使用 5k 数论样本，确认提升后再扩展到 10k。

## Formal Evaluation Set

Stage 2 已从公开奥赛级数学数据中构造固定的正式数论评测集。第一版只筛选 Number Theory 题，规模为 200 道。

评测集只保留纯文本、短答案、适合 Math-Verify 自动评分的题。证明题、图片题、多模态题、开放题和长解答式答案暂时不进入主评测集。

正式评测文件为：

- `data/processed/public_number_theory_eval.jsonl`

该文件由远端服务器生成，不提交到 GitHub，因为 `data/processed/` 被 `.gitignore` 忽略。

为了保证可复现，Stage 2 会提交轻量级结果文件：

- `results/public_eval_data_summary.json`
- `results/public_eval_manifest.json`
- `results/evaluator_audit.md`

一旦正式 eval 生成，后续 Baseline、LoRA SFT、Teacher Response Distillation、GRPO 和可选 Logit Distillation 都必须使用同一份正式 eval，不能随意改动。

## 评价标准

- 主评分器：Math-Verify final-answer equivalence
- 主指标：Final Answer Accuracy
- 辅助指标：Boxed Answer Rate
- 辅助指标：Extraction Success Rate
- 辅助分析：Error Type Distribution

所有模型输出都应尽量把最终答案写在 `\boxed{}` 中，以便后续统一抽取和评分。

## Scoring Protocol

正式评测使用公开奥赛级数论题。第一版优先使用 `KbsdJames/Omni-MATH`，并参考 `KbsdJames/omni-math-rule` GitHub 仓库中的 rule-based filtering 标准，构造 200 道纯文本、短答案、适合 rule-based evaluation 的 Number Theory 题。

主指标是 Final Answer Accuracy。该指标只判断模型最终答案是否与标准答案数学等价，不把推理过程质量纳入主分数。

最终答案等价判断以 Math-Verify 为主评分器。项目中的自定义 `normalize_answer`、列表答案判断、简单分数/小数/整数判断和 sympy 等价判断只作为 fallback，用于处理 Math-Verify 无法稳定解析的短答案格式。

证明题、图片题、多模态题、开放题和长解答式答案暂时不进入主评测集。推理质量只用于错误分析和人工诊断，不作为主指标。

后续 GRPO 的 rule reward 也会基于同一套 scoring protocol，确保 baseline、SFT、蒸馏和强化学习阶段的评测口径一致。

## 训练路线

1. Baseline
2. LoRA SFT
3. Teacher Response Distillation
4. GRPO
5. Optional Logit Distillation

## Formal Baseline Evaluation

Stage 3 使用未经项目训练的原始学生模型
`Qwen/Qwen2.5-Math-1.5B-Instruct`，在 Stage 2 固定生成的 200 道正式数论题上进行评测。
评测只做推理，不更新模型参数，也不修改正式评测集。

主指标为 Final Answer Accuracy，辅助记录 Boxed Answer Rate、Extraction Success Rate、
错误类型分布及不同难度下的准确率。正式输出包括逐题结果、汇总指标和典型错误分析。
后续 LoRA SFT、Teacher Response Distillation 和 GRPO 都必须使用同一份正式评测集，
并与该 baseline 直接比较。

Baseline 准确率用于判断后续实验空间：

- 20%-60%：通常适合继续训练并观察提升。
- 高于 70%：评测集可能偏简单，需要在不改动本轮正式结果的前提下重新审视难度设计。
- 低于 15%：评测集可能偏难，需要先检查数据、答案抽取和评分协议。

## 本地与远端运行规则

本地 Windows 只用于 VSCode/Codex 编辑代码，不运行模型推理、训练、评测，也不下载模型权重。

远端 2xRTX4090 服务器负责数据处理、模型下载、Hugging Face cache、训练、评测和 checkpoint 保存。Codex 主要修改本地项目文件，并给出需要手动同步到远端和运行的命令。

## 不上传数据和权重

以下内容不得提交到 GitHub：

- `data/raw/`
- `data/processed/`
- `outputs/`
- `checkpoints/`
- `models/`
- Hugging Face cache
- 模型权重和 checkpoint 文件

## 当前阶段

当前阶段：Stage 3 - Formal Baseline Evaluation。当前只实现并运行原始学生模型的正式
baseline 评测，不训练模型，不修改正式评测集，不进入 Stage 4。
