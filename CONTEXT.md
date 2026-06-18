# CONTEXT

## Thread Handoff

本文档是 NumberTheory-Qwen 在 Stage 0 至 Stage 5 实现阶段的上下文摘要，用于新 Thread
继续后续阶段。开始新阶段前应先阅读本文档、`README.md` 和对应配置，不要重新设计已经
固定的数据与评分协议。

## Project Identity

- Project Name: NumberTheory-Qwen
- Project Goal: 基于轻量级 Qwen 数学模型构建高中竞赛数论问答助手，并逐阶段提升最终答案正确率和输出规范性。
- Target Domain: 高中竞赛数论
- Prompt Language: 中文
- Student Model: `Qwen/Qwen2.5-Math-1.5B-Instruct`
- Teacher Model: `Qwen/Qwen2.5-Math-7B-Instruct`
- GitHub: `https://github.com/2107404013/Numbertheory-qwen`
- Local Windows Path: `D:\pythonfile\Numbertheory-qwen`
- Remote Server Path: `/home/ljk/projects/NumberTheory-Qwen`
- Remote Conda Environment: `ntqwen`
- Remote Hardware: 2x NVIDIA RTX 4090

## Execution Rules

- 本地 Windows 只用于 VSCode/Codex 编辑代码和 Git 操作。
- 本地不运行模型推理、训练或正式评测，不下载 Qwen 权重。
- 远端服务器负责数据下载与处理、Hugging Face cache、模型下载、推理、训练、评测和 checkpoint 保存。
- Codex 主要修改本地文件，然后给出用户手动执行的本地提交命令和远端运行命令。
- 不直接操作远端服务器。
- 每个阶段只完成该阶段任务，不提前实现下一阶段。
- 每个阶段完成后更新本文档，并提交、推送 Git。
- 后续回复需要同时给出文字说明和命令，说明命令在哪里执行、目的、成功标志和异常处理。

## Git And Storage Rules

以下内容不得提交到 GitHub：

- `data/raw/`
- `data/processed/`
- `outputs/`
- `checkpoints/`
- `models/`
- Hugging Face cache
- `*.pt`
- `*.pth`
- `*.bin`
- `*.safetensors`
- `*.ckpt`
- `wandb/`
- `.cache/`
- 日志和环境变量文件

只提交代码、配置、文档和必要的小型结果摘要。正式 eval 和 5k 训练 JSONL 只保存在远端。

## Fixed Scoring Protocol

- Primary Scorer: Math-Verify final-answer equivalence
- Primary Metric: Final Answer Accuracy
- Auxiliary Metrics:
  - Boxed Answer Rate
  - Extraction Success Rate
  - Error Type Distribution
  - Match Method Distribution
  - Accuracy By Difficulty
- `normalize_answer`、列表答案、分数、小数和 SymPy 等价判断只作为 fallback。
- 模型最终答案要求写在 `\boxed{}` 中。
- 正式评测只使用纯文本、短答案、适合 rule-based evaluation 的题。
- 证明题、图片题、开放题和长解答式标准答案不进入正式主评测集。

## Fixed Formal Evaluation Set

- File: `data/processed/public_number_theory_eval.jsonl`
- Size: 200
- Seed: `20260618`
- Source: `KbsdJames/omni-math-rule` GitHub raw rule-based subset
- Subject: Number Theory
- Suitable For Rule Eval: 200/200
- Proof/Image/Open-ended/Unsupported: 0
- 后续 Stage 5、Stage 6、Stage 7 和 Stage 8 必须继续使用完全相同的 200 道 eval。
- 不允许因为训练结果不理想而修改、替换或重新抽样该评测集。

重要数据源决定：

- `Omni-MATH-Rule` 不是 Hugging Face dataset name。
- 不得调用 `datasets.load_dataset("Omni-MATH-Rule")`。
- HF 正式候选来源是 `KbsdJames/Omni-MATH`。
- Rule-based subset 来自 `KbsdJames/omni-math-rule` GitHub 仓库的 raw JSONL。

## Stage 3 Baseline

Baseline 已在远端完成：

- Model: `Qwen/Qwen2.5-Math-1.5B-Instruct`
- Total: 200
- Correct: 55
- Final Answer Accuracy: 0.275
- Boxed Answer Rate: 0.885
- Extraction Success Rate: 0.885
- Average Output Length: 2341.23 characters
- Correct: 55
- Model Error: 122
- Extraction Error: 23
- Math-Verify Matches: 54
- Fallback List Matches: 1

结论：

- 27.5% 位于预设的 20%-60% 合理区间。
- 评测集没有明显过易或过难，适合作为后续 LoRA SFT、教师蒸馏和 GRPO 的固定基线。
- 后续模型必须使用同一评测脚本、同一 prompt 和同一 eval 与该结果比较。

Stage 3 结果文件：

- `results/number_theory_baseline_eval.json`
- `results/number_theory_baseline_summary.json`
- `results/number_theory_baseline_error_analysis.md`

## Stage 4 Training Data

Stage 4 已在远端完成，并生成：

- Training File: `data/processed/train_number_theory_sft_5k.jsonl`
- Summary: `results/train_data_summary.json`

训练数据统计：

- Target Samples: 5000
- Actual Samples: 5000
- Source: `AI-MO/NuminaMath-1.5`
- Subject: `number_theory`
- Selection Method: `field_filter` 5000
- Problem Type: `Number Theory` 5000
- Question Type: `math-word-problem` 5000
- Candidate Count Before Filter: 86373
- Candidate Count After Number Theory Filter: 12966
- Candidate Count After Quality Filter: 5117
- Duplicate Training Problems Removed: 41
- Exact Eval Leakage Removed: 0
- Near Eval Leakage Removed: 0
- Eval Similarity Threshold: 0.85
- Average Problem Length: 235.0366
- Average Solution Length: 959.5308
- Average Answer Length: 9.9432
- Insufficient Samples Reason: empty

训练 JSONL 已验证：

- `wc -l` 为 5000。
- 5000 行均能被 JSON 解析。
- 每条记录均包含 `id`、`subject`、`problem`、`solution`、`answer`、`source`、
  `problem_type`、`question_type` 和 `selection_method`。
- 训练数据本体位于 `data/processed/`，不提交 GitHub。

质量过滤包括：

- 无效 problem/solution 标记
- 空 problem、solution 或 answer
- `proof`、`notfound`、`unknown`、`none` 等无效答案
- proof、image、open-ended 样本
- 过短题目或解答
- 超过 12000 字符的解答
- 训练集内部重复
- 与正式 eval 的规范化精确匹配
- 与正式 eval 的 `SequenceMatcher >= 0.85` 近似匹配

## Important Implementation Decisions

- 所有数据准备继续复用 `scripts/prepare_data.py`，不要新增重复数据脚本。
- 所有评测继续复用 `scripts/eval_math.py`，不要新增重复 eval 脚本。
- `scripts/eval_math.py` 同时保留：
  - `--test_evaluator`
  - `--audit_data`
  - `--config`
- Stage 3 正式评测使用 bf16、`device_map="auto"`、`model.eval()` 和
  `torch.inference_mode()`，不更新模型参数。
- Prompt 渲染只替换 `{problem}`，避免 `\boxed{}` 中的空花括号被 Python
  `str.format()` 误解析。
- Stage 3 逐题写入结果文件，减少长时间远端运行中断造成的数据损失。
- Stage 4 优先按 `problem_type` 等领域字段筛选；领域字段明确为其他学科时，不允许用宽泛关键词覆盖。
- `integer` 等弱关键词不能单独作为 Number Theory 判断依据。
- 5k 数据确认 LoRA SFT 有提升后，才考虑扩展到 10k。

## Network Notes

远端直连 Hugging Face 曾多次出现：

- `Connection reset by peer`
- `Cannot send a request, as the client has been closed`
- 流式下载结束时 `Bad file descriptor`

可用设置：

```bash
export HF_ENDPOINT=https://hf-mirror.com
export HF_HOME=$HOME/hf_cache
export TRANSFORMERS_CACHE=$HF_HOME/transformers
export HF_DATASETS_CACHE=$HF_HOME/datasets
export HF_HUB_ETAG_TIMEOUT=120
export HF_HUB_DOWNLOAD_TIMEOUT=600
export HF_HUB_DISABLE_XET=1
```

Stage 4 曾在写出两个文件后于 Python 退出阶段报 `Bad file descriptor`。随后已验证训练文件为
5000 行且全部 JSON 合法，因此不需要重跑。以后遇到类似退出错误，应先验证产物，不要立即删除
cache 或重复下载。

## Files Modified Through Stage 4

主要文件及职责：

- `README.md`: 项目目标、数据、评分协议、baseline 与训练数据说明。
- `CONTEXT.md`: 阶段状态与新 Thread 接力摘要。
- `.gitignore`: 忽略数据、权重、cache、输出和 checkpoint。
- `requirements.txt`: 远端环境依赖。
- `configs/baseline_eval.yaml`: 固定 baseline 模型、eval、输出路径和中文 prompt。
- `configs/lora_sft.yaml`: Stage 5 占位配置，训练文件已指向
  `data/processed/train_number_theory_sft_5k.jsonl`。
- `scripts/prepare_data.py`: 公开数据检查、正式 eval 构建、5k SFT 数据构建与去重。
- `scripts/eval_math.py`: Math-Verify + fallback、evaluator test、数据审计和正式 baseline。
- `data/README.md`: 数据目录、训练集和 eval 不提交规则。
- `results/`: 可提交的检查、摘要、评测结果和错误分析。

以下脚本仍是后续阶段占位或未完成实现：

- `scripts/train_lora_sft.py`
- `scripts/generate_teacher_data.py`
- `scripts/train_grpo.py`
- `scripts/train_distill.py`
- `scripts/demo.py`

## Completed Stages

- Stage 0: 项目骨架、Git、远端环境说明。
- Stage 1: Math-Verify 评分协议、fallback、公开数据字段检查。
- Stage 2: 固定 200 道正式数论 eval 并完成审计。
- Stage 3: 原始 1.5B 学生模型正式 baseline，accuracy 0.275。
- Stage 4: 筛选并验证 5000 条 NuminaMath-1.5 Number Theory SFT 数据。

## Current Status

Current Stage: Stage 5 - LoRA SFT

Stage 5 Goal:

- 使用 NuminaMath-1.5 Number Theory 5k 数据训练 LoRA adapter。
- 不做全参数微调。
- 不修改 Stage 2 固定的正式 eval。
- 训练后在固定 200 道数论 eval 上评测。
- 与 Stage 3 baseline 直接对比。

Stage 5 本地实现包括：

- `configs/lora_sft.yaml`: 固定模型、5k 训练文件、LoRA 参数和训练超参数。
- `scripts/train_lora_sft.py`: 使用 Transformers + PEFT 训练并只保存 LoRA adapter。
- 训练文本使用 tokenizer chat template，并只对 assistant solution token 计算 loss。
- 超长样本会保留 chat 边界并为 assistant 预留至少 256 token，截断统计写入训练日志。
- 支持使用 `torchrun --nproc_per_node=2` 在两张 GPU 上进行分布式训练；只有主进程保存
  adapter、tokenizer 和最终训练日志。
- adapter 输出到 `outputs/lora_sft_number_theory`，训练日志输出到
  `results/lora_sft_train_log.json`。
- `scripts/eval_math.py` 支持 `--adapter_path` 加载 base model + LoRA，并支持
  `--compare` 生成 baseline/LoRA 对比结果。

本地只完成代码、配置和文档修改，尚未运行远端训练或正式评测，因此不得填写或推测
LoRA accuracy。

Previous Stage:

- Stage 4 completed。
- `train_number_theory_sft_5k.jsonl` 已生成。
- `actual_train_samples = 5000`。
- `eval leakage removed = 0`。

Baseline:

- `accuracy = 0.275`。
- `boxed_answer_rate = 0.885`。
- `extraction_success_rate = 0.885`。

训练与评测完成后必须如实记录结果。即使 LoRA accuracy 没有提升，也不得修改正式 eval、
伪造结果或改变项目路线。

## Next Stage

Stage 6 - Teacher Response Distillation

只有 Stage 5 训练、固定 eval 评测、baseline 对比和结果记录完成后，才进入 Stage 6。
当前不得实现 Stage 6。

## Git Rule

每个阶段完成后：

1. 更新 `CONTEXT.md`。
2. 本地提交实现代码并 push。
3. 用户在远端 pull 后手动运行。
4. 验证结果。
5. 只提交可追踪的小型结果文件并 push。
6. 开始下一阶段前先同步远端最新提交，避免 `fetch first`。
