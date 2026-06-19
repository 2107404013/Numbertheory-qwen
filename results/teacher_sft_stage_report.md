# Stage 6.2 Teacher LoRA SFT Pilot 报告

## 数据选择

1000 条教师回答经过答案一致性、中文比例和 boxed 格式过滤后，保留 666 条安全样本。
只使用最终答案与 gold 等价的样本，避免把教师模型的数学错误监督给学生模型。

## 与 NuminaMath LoRA 的区别

Teacher SFT 使用中文、竞赛教练风格并与 gold 对齐的教师解法；此前 NuminaMath LoRA 主要使用英文原始解法，和中文固定评测 prompt 存在更明显的分布差异。

## 固定 200 题评测

- Teacher LoRA accuracy：0.2750
- boxed answer rate：0.8950
- extraction success rate：0.9000
- 相比 1.5B baseline accuracy 变化：+0.0000
- 相比 Safe LoRA 1k accuracy 变化：-0.0200
- 相比 baseline 改善/退步：11/11
- 相比 Safe LoRA 1k 改善/退步：6/10

## 结论

Teacher SFT 未超过 baseline，下一步应先检查教师数据质量、截断情况和训练策略，不扩展数据规模。

本阶段未进入 GRPO，也未进行 logits 蒸馏。
