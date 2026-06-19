# NumberTheory-Qwen 上下文摘要

更新时间：2026-06-19

## 项目与环境

- 本地项目：`D:\pythonfile\Numbertheory-qwen`
- 远端项目：`/home/ljk/projects/NumberTheory-Qwen`
- Conda 环境：`ntqwen`
- 硬件：2× RTX 4090
- 学生模型：`Qwen/Qwen2.5-Math-1.5B-Instruct`
- 教师模型：`Qwen/Qwen2.5-Math-7B-Instruct`
- 固定评测集：`data/processed/public_number_theory_eval.jsonl`，共 200 题，禁止更换或重新抽样。

## 固定工作规则

- Codex 只修改本地项目文件，不自动运行训练、推理、评测或 Git 命令。
- 用户在远端手动运行；后续回答必须给出文字解释、运行位置、成功标志和预计耗时。
- 脚本支持时优先双卡。双卡评测使用 `torchrun --nproc_per_node=2` 分片；只设置 `CUDA_VISIBLE_DEVICES=0,1` 不等于样本并行。
- 不提交 `data/processed/`、`outputs/`、模型权重、checkpoint、缓存或大型日志。
- 当前不进入 GRPO，也不做 logits 蒸馏。
- 不因结果不理想而修改固定 200 题评测集。

## 已完成实验与决定

### Baseline

- 1.5B baseline：accuracy `0.275`，boxed `0.885`，extraction `0.885`。
- 7B teacher：accuracy `0.320`，boxed/extraction `0.930`。
- 7B 相对 1.5B：改善 26 题、退步 17 题，净改善 9 题。评测集较难，主要瓶颈是推理而非单纯格式。

### Stage 5：NuminaMath LoRA

- Initial LoRA：accuracy `0.000`，boxed/extraction `0.035`，格式崩坏，作废。
- Safe LoRA 1k：accuracy `0.295`，boxed `0.910`，extraction `0.915`；当前最佳正式 LoRA。
- Safe LoRA 5k：accuracy `0.275`，boxed `0.880`，extraction `0.885`；与 baseline 持平。
- 决定：保留 Safe LoRA 1k，不扩展到 10k。
- 最佳 adapter 位于远端：`outputs/lora_sft_number_theory_safe`。

### Stage 6.1：教师数据生成

- 7B teacher 成功生成 1000 条，boxed rate `1.0`，无空输出和 generation error。
- teacher 最终答案与 gold 匹配 756 条，不匹配 244 条。
- 匹配样本中有 90 条中文比例不合格。
- 原过滤流程产出 666 条：`data/processed/train_number_theory_teacher_safe_666.jsonl`。

### Stage 6.2：Teacher LoRA 666

- 1 epoch、固定 200 题：accuracy `0.275`，boxed `0.895`，extraction `0.900`。
- 相对 baseline 改善/退步 `11/11`，无净提升；相对 Safe LoRA 1k 为 `6/10`，总体更差。
- 3 epoch 训练完成，train loss 约 `0.2798`；50 题 preview：accuracy `0.300`，boxed `0.820`，extraction `0.840`。
- 决定：3 epoch 格式稳定性下降并有过拟合迹象，不做完整 200 题评测，不继续扩大 epoch。
- 当前最佳结果仍是 Safe LoRA 1k（accuracy `0.295`）。

## 最新关键发现：666 条教师数据含 fallback 污染

教师生成脚本在模型未输出 boxed answer 时，会把 gold 追加为 `\boxed{...}`，原始记录通过 `boxed_fallback_appended` 标记。

原流程存在两处问题：

1. `scripts/generate_teacher_data.py` 的安全过滤没有排除 `boxed_fallback_appended == true`。
2. `SAFE_TEACHER_FIELDS` 没有将该字段写入过滤后的 JSONL，所以直接检查 666 文件会误以为 fallback 数量为 0。

按 `id` 将原始 1000 条与 safe 666 回连后确认：

- safe 总数：666
- fallback 污染：67
- 真正非 fallback：599
- 污染比例：约 10.1%

因此 Teacher LoRA 666 的“答案匹配”中存在脚本追加 gold 后形成的伪匹配。此前 1 epoch 和 3 epoch 结果只能作为诊断结果，不能视为干净教师蒸馏结论。

## 当前阶段与下一步

Current Stage：Stage 6.2.1 - Strict Teacher Data Repair

不要继续使用 666 数据训练，也不要对 3 epoch 模型做完整评测。下一步：

1. 修复 `scripts/generate_teacher_data.py`：安全过滤明确排除 fallback，并在审计摘要中记录排除数量。
2. 从原始 1000 条重新生成严格数据集，预期 599 条：`data/processed/train_number_theory_teacher_strict_599.jsonl`。
3. 创建严格版 1-epoch 配置；从原始 1.5B base 开始，使用 assistant-only loss、学习率 `2e-5` 和双卡训练。
4. 先做固定评测集前 50 题 preview；accuracy、boxed 和 extraction 均无明显退化后，才运行完整 200 题。
5. 若严格 599 仍不能超过 Safe LoRA 1k，则结束 Teacher LoRA 路线并整理失败诊断，不盲目增加数据量或 epoch。

## 下一步建议修改的文件

- 修改：`scripts/generate_teacher_data.py`
- 新增：`configs/lora_teacher_sft_strict_599.yaml`
- 新增：`configs/teacher_lora_strict_599_preview_eval.yaml`
- 建议结果文件：
  - `results/teacher_data_strict_599_summary.json`
  - `results/lora_teacher_sft_strict_599_train_log.json`
  - `results/lora_teacher_sft_strict_599_preview_summary.json`
- 最终根据结果更新：`README.md`、`CONTEXT.md`、`data/README.md`

## 已修改或新增的主要文件

- `scripts/prepare_data.py`：构建训练集和固定评测集。
- `scripts/eval_math.py`：Math-Verify、fallback 评分、逐题结果、双卡评测和比较报告。
- `scripts/train_lora_sft.py`：LoRA SFT、assistant-only loss、`solution_field`、boxed-aware 截断和双卡训练支持。
- `scripts/generate_teacher_data.py`：7B 教师生成与安全过滤；当前必须修复 fallback 漏洞。
- `configs/teacher_generate.yaml`：教师数据生成。
- `configs/lora_teacher_sft.yaml`：Teacher LoRA 666，1 epoch。
- `configs/lora_teacher_sft_3ep.yaml`：Teacher LoRA 666，3 epoch 诊断实验。
- `configs/teacher_lora_3ep_preview_eval.yaml`：3 epoch 的 50 题预评测。
- `README.md`、`data/README.md`：阶段说明与数据规则。
- `results/`：各阶段的小型摘要、比较和错误分析。

## Git 与同步注意事项

- GitHub SSH 远端：`git@github.com:2107404013/Numbertheory-qwen.git`。
- push 出现 `fetch first` 时，先处理未提交改动，再执行 `git pull --rebase origin main`，解决冲突后再 push。
- 不使用 `git reset --hard` 或强制 push 覆盖另一端提交。
- 本地和远端都有改动时，提交前分别执行 `git status`，明确保留范围。

## 新 Thread 开始时先做

1. 阅读本文件、`README.md` 和 `data/README.md`。
2. 检查 `git status`，不要覆盖未提交改动。
3. 先完成 fallback 过滤漏洞和严格 599 配置，不要直接训练。
4. 只给用户手动命令，不自动运行训练、评测或 Git。
5. 每条远端命令附文字说明、预计耗时和成功标志。

