# Kimi Actions 评估工具

基于 Nutanix Code Review 数据集评估 Kimi Actions PR Review 质量。

## 数据集配置

评估脚本使用 [Nutanix Code Review Dataset](https://huggingface.co/datasets/Nutanix/code_review_dataset)。

### 下载数据集

```bash
# 创建数据集目录
mkdir -p datasets/nutanix-codereview
cd datasets/nutanix-codereview

# 从 Hugging Face 下载
# 方式1: 使用 huggingface-cli
huggingface-cli download Nutanix/code_review_dataset --local-dir .

# 方式2: 手动下载
# 访问 https://huggingface.co/datasets/Nutanix/code_review_dataset
# 下载 code_suggestions.csv 和 pull_requests.csv
```

### 目录结构

```
datasets/
└── nutanix-codereview/
    ├── code_suggestions.csv   # 人工审查建议
    └── pull_requests.csv      # PR 上下文和 diff
```

## 使用方法

### 快速评估（少量 PR）

```bash
cd kimi-actions
KIMI_API_KEY=xxx python eval/eval_nutanix.py --num 10
```

参数：
- `--num`: 评估 PR 数量（默认 10）
- `--min-suggestions`: 最少 Nutanix 建议数（默认 2）
- `--review-level`: 审查级别 strict/normal/gentle（默认 normal）
- `--output`: 输出文件路径

### 完整评估（全量数据）

```bash
cd kimi-actions
KIMI_API_KEY=xxx python eval/eval_nutanix_full.py
```

参数：
- `--output`: 输出文件路径（默认 eval/eval_full_results.json）
- `--checkpoint`: checkpoint 文件路径（默认 eval/eval_checkpoint.json）
- `--limit`: 限制 PR 数量（0=全部）

特性：
- 断点续跑：每 10 个 PR 保存 checkpoint
- 中间报告：每 100 个 PR 生成报告
- 进度追踪：显示 ETA

## 评估指标

| 指标 | 说明 |
|------|------|
| Kimi/Nutanix 比例 | Kimi 建议数 / Nutanix 建议数，目标 ~1.0 |
| 重叠分数 | Kimi 建议与 Nutanix 建议的关键词重叠率 |
| 质量评分 | 5 分制：文件引用、行号、摘要、详细说明、代码修复 |
| 代码修复率 | 包含 improved_code 的建议比例 |

## 评估报告

完整评估报告见 [EVAL_REPORT.md](./EVAL_REPORT.md)
