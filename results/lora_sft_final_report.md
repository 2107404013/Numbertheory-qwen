# LoRA SFT 最终实验报告

## 1. 实验目标

LoRA SFT 阶段使用固定的数论训练数据，对
`Qwen/Qwen2.5-Math-1.5B-Instruct` 进行参数高效微调，目标是在不破坏原模型数学能力和
指令遵循能力的前提下，提高固定 200 道数论正式评测题的最终答案准确率、boxed answer
率和答案提取成功率。所有实验均使用同一正式评测集和评分协议。

## 2. Initial LoRA 失败现象

初始 LoRA 的正式评测结果为：

- accuracy：0.0
- boxed_answer_rate：0.035
- extraction_success_rate：0.035

该版本出现明显的答案格式崩坏和能力退化，不能作为正式 LoRA 结果。主要原因是训练格式
与评测输出协议不一致，训练没有稳定约束最终答案格式，并且初始学习率与 LoRA
target modules 相对激进，导致模型的 instruction-following 和答案输出结构被破坏。

## 3. Stage 5.1 修复策略

Stage 5.1 没有直接重跑完整 5000 条训练，而是先进行 1000 条 safe pilot，采用以下保守
修复：

- 使用 Qwen chat template 对齐模型原生对话格式。
- 使用 assistant-only loss，system/user prompt 和 padding labels 均设为 `-100`。
- 每条 assistant 解答末尾强制追加 `最终答案：\boxed{answer}`。
- 截断长解答时优先保留最终 boxed answer。
- 将 learning rate 降低到 `2e-5`。
- 将 LoRA target modules 缩小为 `q_proj`、`v_proj`、`o_proj`。
- LoRA 使用 `r=8`、`alpha=16`，先验证 1000 条 pilot 的稳定性。

## 4. Safe LoRA Pilot 1000 结果

1000 条 safe pilot 在固定 200 道正式评测题上的结果为：

- accuracy：0.295，相对 baseline 提升 0.02
- boxed_answer_rate：0.91
- extraction_success_rate：0.915
- improved_case_count：9
- regressed_case_count：5

该实验修复了初始 LoRA 的格式崩坏，准确率由 baseline 的 0.275 提升到 0.295，同时
boxed answer 和答案提取指标保持稳定并略有提升。因此它是当前 LoRA 阶段的最佳结果。

## 5. Safe LoRA Full 5k 结果

保持相同保守配置并扩展到完整 5000 条训练数据后，固定 200 道正式评测结果为：

- accuracy：0.275，相对 baseline 提升 0.0
- boxed_answer_rate：0.88
- extraction_success_rate：0.885
- improved_case_count：10
- regressed_case_count：10

完整 5k 模型没有再次出现严重格式崩坏，但改善题与退步题数量相同，最终准确率回到
baseline 水平，并且 boxed answer rate 低于 1000 条 pilot。因此该模型属于稳定但无净
提升的实验，不作为最佳 LoRA。

## 6. 5000 条没有继续提升的可能原因

- NuminaMath 训练数据主要使用英文解法，与项目的中文固定评测 prompt 存在分布差异。
- 数据量增加不保证领域能力线性提升，更多英文解答模式可能覆盖原模型已有的部分解题模式。
- 当前训练数据强调通用数学解题过程，不一定完全匹配固定数论评测的题型和输出风格。
- 较低学习率主要用于保证训练稳定、减少灾难性退化，不一定能显著提高数学推理能力。
- 强制 boxed answer 能改善输出协议，但不能单独解决推理正确性问题。

## 7. 最终选择

- LoRA 阶段最佳结果选择 **Safe LoRA Pilot 1000**。
- 最佳 adapter 对应远端目录：`outputs/lora_sft_number_theory_safe`。
- Safe LoRA Full 5k 作为稳定但无净提升的实验如实保留。
- 当前不继续扩展到 10k LoRA，避免在训练与评测分布不匹配的条件下继续增加成本。
- 下一阶段规划为 Stage 6 Teacher Response Distillation，但 Stage 5.3 不实现或运行
  Stage 6。
- Stage 6 将使用 `Qwen/Qwen2.5-Math-7B-Instruct` 生成中文、boxed、竞赛教练风格解法，
  以减少训练数据和正式评测之间的分布差异。
