# 情感计算算法与可替换领域插件

本仓库默认插件为 `plugins/affective_computing.py`。框架兼容其他领域，无需改写抓取、存储或网页代码；插件定义目标领域、相关性、标签和 arXiv 回退分类。

## 处理顺序

```text
Axi 当日候选全集 → arXiv ID 去重 → evaluate() → assign_tags()
  → 可选 LLM（边界复核 / 已入选翻译） → arXiv 元数据 → data/ → 静态网站
```

默认只处理 Axi 覆盖的候选，不保证覆盖 arXiv 上全部情感计算论文。分类查询仅在 Axi 失败且显式启用 `--allow-arxiv-discovery` 时使用，默认类别为 `cs.CV/cs.CL/cs.HC/cs.AI/cs.LG/eess.AS`。

## 当前算法

### 文本与信号

合并英文和中文标题、摘要；使用 Unicode NFKC、大小写折叠，并统一连字符与空白。英文词用字母数字边界匹配，避免 `affect`、`MELD` 等子串碰撞。评分不使用类别本身作为情感证据。

| 信号 | 示例 | 每个不同词的分值 |
| --- | --- | ---: |
| 明确任务 | affective computing、emotion recognition、sentiment analysis、empathetic response、情绪识别 | 28 |
| 专用数据集 | IEMOCAP、CMU-MOSI、AffectNet、RAVDESS、EmpatheticDialogues | 20 |
| 情感上下文 | emotion、empathy、mood、情绪、共情 | 6 |
| 计算技术 | multimodal、MLLM、speech、recognition、reasoning、大模型 | 3 |

分数为上述加权和，上限 100。`MELD/SEED/DailyDialog/SemEval/RECOLA` 名称较宽泛，只有同时出现情感上下文才算数据集信号。

### 纳入与排除

- 明确任务或专用数据集命中，直接纳入。
- 否则须情感上下文和技术词同时命中，且分数至少 12。
- 通用多模态大模型没有情感证据时，排除且分数归零。
- 标题命中金融市场预测、政治 sentiment、蛋白质/化学或医学分割等范围外词时，优先排除并归零；当前是保守的范围限制，即使其摘要提到 sentiment analysis 也会排除。

分数是规则证据权重，不是概率。标题排除也可能漏掉跨领域方法论文；若研究范围扩大，应修改词表、增加真实正反例，并递增 `version`。

### 标签

插件提供 13 个标签：多模态情感、情绪识别、语音情感、面部表情、文本情感、情感大模型、共情交互、情感生成、心理状态/福祉、社交信号、生理信号、数据集/评测、鲁棒性/偏差。按各标签命中的不同词数排序，同分按 `tags` 顺序，返回一个主标签和最多两个次标签。没有标签命中时回退为情绪识别。心理健康、生理和社交论文仍必须有情感任务证据，不能仅凭 EEG 或 depression 入选。

### LLM 边界

LLM 只复核未入选且分数达到 `filtering.llm_review_min_score=10` 的候选，或为已入选论文补全缺失中文字段。硬排除和无情感证据的论文得分为零，不会因缺少翻译而请求 LLM。模型不能删除规则已纳入论文；模型调用失败时保留规则结果。提示词的领域和标签来自插件。

## 插件接口与换域

实现 `src/adpaper/filtering/base.py` 的接口：

```python
class Plugin:
    slug: str
    version: str
    display_name: str
    tags: tuple[str, ...]
    arxiv_categories: tuple[str, ...]

    def evaluate(self, paper: Paper) -> RelevanceResult: ...
    def assign_tags(self, paper: Paper) -> TagAssignment: ...
```

`evaluate()` 返回 include、score、matched_terms 和 reasons，全部保存在数据中供审计。插件应确定性运行且不请求网络；模型调用由 enrichment 层负责。

1. 在 `plugins/` 新增目标领域模块并导出 `plugin` 对象，设置词表、阈值、标签与类别。
2. 修改 `config/config.yml` 和示例配置中的 `filtering.plugin` 为 `plugins.your_domain:plugin`；同步默认配置、站名、CNAME、User-Agent、收藏存储键与说明。
3. 新领域使用独立仓库和数据目录，不混用现有归档。已有日期默认返回 `unchanged`，仅替换代码不会重新分类旧数据。
4. 编写领域正例、近似误报、缩写边界和 LLM 边界测试；运行 `ruff check .`、`pytest -q`、`python -m adpaper validate` 与 `python -m adpaper build`。
5. 对真实日期执行 `python -m adpaper update --date YYYY-MM-DD --force --dry-run`，核对候选数、入选数与警告，再执行正式更新。

本仓库就是从自动驾驶插件迁移到情感计算的完整实例。只替换一个插件即可改变筛选行为，但公开新领域站点时仍必须隔离历史、更新品牌和仓库部署配置。
