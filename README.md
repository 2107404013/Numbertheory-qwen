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

本项目正式 baseline 的 Final Answer Accuracy 为 27.5%（55/200），处于适合继续训练和对比提升的区间。

## Training Data Preparation

Stage 4 只准备 SFT 训练数据，不训练模型，也不运行模型推理。训练数据来自
`AI-MO/NuminaMath-1.5` 的 Number Theory 子集，第一版目标规模为 5000 条。

数据构建优先使用 `problem_type` 等领域字段筛选数论题，并进行题目、解答、答案有效性
检查。训练题会与 Stage 2 固定的 200 道正式评测题进行 normalized exact match 和
`SequenceMatcher >= 0.85` 的近似去重，防止评测泄漏。

生成的训练文件为：

- `data/processed/train_number_theory_sft_5k.jsonl`

该文件不提交 GitHub。项目只提交轻量级统计文件
`results/train_data_summary.json` 作为可复现记录。Stage 5 将使用这份训练集进行 LoRA
SFT；确认相对 baseline 有提升后，再考虑扩展到 10000 条。

## LoRA SFT

Stage 5 初始 LoRA SFT 已作为失败实验保留。固定 200 题评测结果为：

- accuracy: 0.0
- boxed_answer_rate: 0.035
- extraction_success_rate: 0.035
- main issue: answer-format collapse and possible ability degradation

可能原因包括 NuminaMath solution 多为英文长解答、训练时没有强制 boxed answer、训练格式
与评测格式不一致、对过多文本模式的学习破坏 instruction-following，以及初始学习率和
LoRA target modules 偏激进。初始失败 adapter 保留在远端，不提交 GitHub。

Stage 5.1 先审计固定 5k 训练数据，再运行 1000 条安全 pilot，而不是立即重跑完整 5k：

- 使用 Qwen chat template。
- system/user labels 全部设为 `-100`，只计算 assistant loss。
- 每条 assistant 解答末尾强制追加 `最终答案：\boxed{answer}`。
- 截断 solution 时始终保留 boxed 最终答案。
- 学习率降至 `2e-5`。
- LoRA 只训练 `q_proj`、`v_proj`、`o_proj`，使用 `r=8`、`alpha=16`。
- pilot adapter 保存到 `outputs/lora_sft_number_theory_safe`。

Stage 5.1 safe pilot 已完成，并在固定 200 题正式 eval 上得到：

- accuracy: 0.295（baseline 为 0.275）
- boxed_answer_rate: 0.91（baseline 为 0.885）
- extraction_success_rate: 0.915（baseline 为 0.885）
- improved_case_count: 9
- regressed_case_count: 5

该结果说明初始 LoRA 的格式崩坏已经修复，且最终答案准确率有小幅提升。因此 Stage 5.2
将相同的保守训练方案从 1000 条稳定扩展到完整 5000 条，不进行激进调参：

- `max_train_samples: 5000`
- 学习率继续保持 `2e-5`
- 保持 assistant-only loss 和强制 boxed 最终答案
- 保持 `q_proj`、`v_proj`、`o_proj` 与 `r=8`、`alpha=16`
- full 5k adapter 保存到 `outputs/lora_sft_number_theory_safe_5k`

训练日志写入 `results/lora_sft_train_log.json`。训练数据主要来自英文数学数据，当前目标
仍是稳定推理、指令遵循和最终答案格式，不要求中文风格完全统一。

训练完成后必须继续使用 Stage 2 固定的
`data/processed/public_number_theory_eval.jsonl`（200 道）和 Stage 3 相同评分协议评测，
并生成与 Stage 3 baseline 的对比结果。重点比较 Final Answer Accuracy、Boxed Answer
Rate 和 Extraction Success Rate。若 LoRA 没有提升，必须如实保留结果，不修改正式评测集，
也不伪造提升。

Stage 5.3 已完成 LoRA SFT 结果整理。所有版本在固定 200 道正式 eval 上的结果如下：

| Model | Accuracy | Boxed Rate | Extraction Rate | Conclusion |
| --- | ---: | ---: | ---: | --- |
| Baseline | 0.275 | 0.885 | 0.885 | 原始基线 |
| Initial LoRA | 0.000 | 0.035 | 0.035 | 格式退化，失败 |
| Safe LoRA 1k | 0.295 | 0.910 | 0.915 | 当前最佳 LoRA |
| Safe LoRA 5k | 0.275 | 0.880 | 0.885 | 稳定但无净提升 |

最终选择 `Safe LoRA 1k` 作为 LoRA 阶段最佳结果，对应远端 adapter
`outputs/lora_sft_number_theory_safe`。该阶段证明了训练格式、assistant-only loss 和
boxed answer 监督对于保持模型稳定性的重要性；同时也表明纯英文 NuminaMath SFT 对中文
数论 eval 的提升有限。由于完整 5k 已回到 baseline 准确率，当前不继续扩展到 10k LoRA。

下一阶段规划使用 `Qwen/Qwen2.5-Math-7B-Instruct` 生成中文、boxed、竞赛教练风格的教师
解法，以减少训练数据与正式评测 prompt 的分布差异。详细结论见
`results/lora_sft_final_report.md` 和 `results/lora_sft_best_selector.json`。

## Teacher Response Distillation

直接使用 NuminaMath 英文解法进行 LoRA SFT 的提升有限：Safe LoRA 1k 仅从 0.275 提升
到 0.295，而完整 5k 又回到 0.275。训练数据主要是英文解法，但项目使用中文正式评测
prompt，二者存在明显的语言和回答风格分布差异。

Stage 6.1 使用 `Qwen/Qwen2.5-Math-7B-Instruct` 生成 1000 条 teacher response pilot：

- 输入固定 5k 数论训练集的前 1000 条题目及 gold answer。
- 教师输出要求使用中文、呈现清晰的高中竞赛数论推理步骤。
- 最终答案必须写入 `\boxed{}`，并与 gold answer 做等价检查。
- 生成过程支持每 50 条保存和按样本 ID 断点续跑。
- 教师数据保存在 `data/processed/train_number_theory_teacher_1k.jsonl`，不提交 GitHub。
- GitHub 只保存轻量级的 `results/teacher_data_summary.json` 和
  `results/teacher_data_audit.md`。

Stage 6.1 完成 1000 条生成后，先对教师模型进行固定 200 题上限评测。评测仍复用
`scripts/eval_math.py` 和 Stage 2 的正式评测集；使用 `torchrun` 启动两个进程，每张
RTX 4090 独立加载一份 4-bit 教师模型并各处理 100 题。各进程写入独立 rank 文件，
最后由 rank 0 按原题顺序合并为 `results/teacher_7b_eval.json`，避免并发覆盖。

7B teacher 在同一固定 200 题上的 accuracy 为 0.32。1000 条 teacher response 的安全
过滤结果为：

- 756 条最终答案与 gold 匹配；
- 244 条答案不匹配，不能用于 Teacher SFT；
- 90 条虽然答案匹配，但中文比例不合格；
- 最终保留 666 条答案匹配、中文合格、内容非空且包含 boxed 答案的安全教师数据。

Stage 6.1.5 使用 `scripts/generate_teacher_data.py --filter_safe` 可重复生成
`data/processed/train_number_theory_teacher_safe_666.jsonl`，并生成轻量级过滤统计和
中文审计报告。教师 JSONL 仍位于 `data/processed/`，不得提交 Git。

Stage 6.2 使用这 666 条安全教师回答，从原始
`Qwen/Qwen2.5-Math-1.5B-Instruct` 开始执行 Teacher LoRA SFT pilot，不接续 Initial
LoRA、Safe LoRA 1k 或 Safe LoRA 5k。训练继续采用 Qwen chat template、
assistant-only loss、强制 boxed answer、低学习率和保守 target modules。训练完成后，
在固定 200 题上与以下结果比较：

- 1.5B baseline：accuracy 0.275；
- Safe LoRA 1k：accuracy 0.295；
- Teacher LoRA 666：以 `results/lora_teacher_sft_666_summary.json` 为准。

如果 Teacher LoRA 明确提升，再考虑扩展到 2k 或 3k 安全教师数据；如果没有提升，先检查
教师数据质量、长解法截断和训练策略。本阶段不进入 GRPO，也不进行 logits 蒸馏。

严格过滤进一步排除了由脚本追加 gold boxed answer 形成的 fallback 样本，得到 599 条干净
教师数据。Strict Teacher LoRA 的 50 题 preview accuracy 为 0.26，低于同一前 50 题的
1.5B baseline 0.30；boxed rate 为 0.86，extraction rate 为 0.88。该结果说明格式稳定性
尚可，但教师监督没有改善推理正确率，因此不继续完整 200 题评测，也不增加训练 epoch。

## Teacher Tournament

Stage 6A 在进行更大规模 teacher response distillation 前先选择教师。已有
`Qwen/Qwen2.5-Math-7B-Instruct` 在固定 200 题上的 accuracy 约为 0.32，优势有限；教师
选择不能只看参数规模或裸跑正确率，还必须检查给定题目与 gold answer 后能否稳定生成中文、
boxed、最终答案正确且不依赖脚本 fallback 的安全解法。

候选教师为：

- `Qwen/Qwen2.5-Math-7B-Instruct`：已有基准，不重复评测；
- `deepseek-ai/DeepSeek-R1-Distill-Qwen-14B`；
- `AI-MO/NuminaMath-7B-CoT`。

两个新候选分别在固定 200 题正式 eval 上评测，并针对训练集固定前 300 条生成 teacher
response pilot。所有候选使用相同评测 prompt、评分器、300 条题目和 teacher prompt。
最终选择综合考虑 eval accuracy、严格 safe rate、answer match rate、中文比例、boxed 和
抽取稳定性，并记录 4bit 单卡运行稳定性。Stage 6A 不训练学生、不进入 GRPO，也不进行
logits 蒸馏。

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

当前阶段：Stage 6A - Teacher Tournament。使用固定 200 题正式 eval 和相同的 300 条
teacher response pilot，对 DeepSeek-R1-Distill-Qwen-14B、NuminaMath-7B-CoT 与已有
Qwen2.5-Math-7B 基准进行比较。本阶段只做教师选择，不训练学生模型。
