# Affective Computing Papers / ArXivACReader

情感计算领域的公开论文日报与静态归档站点：<https://acpaper.ning0713.top>

基于 [ArXivADReader](https://github.com/Ning0713/ArXivADReader) 的静态发布框架，保留 Axi 风格、收藏、标签与关键词搜索。通过 [paper.axi404.top](https://paper.axi404.top/) 的 JSON API 获取已发布的候选全集，使用可替换插件筛选情绪识别、情感分析、共情交互、情感生成及这些任务中的多模态大模型论文。arXiv API 补齐元数据，GitHub Actions 发布到 Pages，无需个人服务器、邮件服务或数据库。

## 功能与范围

- 每日相关论文全部展示，不设七篇等数量上限；候选覆盖范围仍受 Axi 数据源限制。
- 中英文标题/摘要、arXiv、PDF 和翻译链接。
- 13 个研究标签，支持跨日期搜索、浏览器本地收藏及回到顶部。
- 工作日北京时间 13:00 自动同步，17:17 再检查一次；GitHub 调度可能延迟。
- 自动补齐归档范围内缺失且上游已发布的日期，按 arXiv ID 去重；不收录未完成日报。
- 通用 VLM/MLLM 必须具备情感任务证据；单纯金融市场预测等应用不在默认范围内。

## 本地运行

需要 Python 3.11+，建议两个仓库使用独立虚拟环境。内部兼容命令名仍为 `adpaper`：

```powershell
git clone https://github.com/Ning0713/ArXivACReader.git
Set-Location ArXivACReader
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m adpaper validate
python -m adpaper build
python -m http.server 8000 -d site
```

同步遗漏日期：`python -m adpaper sync`；单日更新：`python -m adpaper update --date YYYY-MM-DD`；无写入预览：`python -m adpaper sync --dry-run`。默认候选来自 Axi；只有单日更新明确传入 `--allow-arxiv-discovery` 才在 Axi 不可用时回退到 arXiv 分类查询。

## 配置与插件

默认配置是 `config/config.yml`，插件是 `plugins/affective_computing.py`。明确情感任务、领域数据集或情感上下文与技术词组合决定相关性；技术词本身不能纳入普通多模态论文。插件只执行规则，不请求网络。完整算法、限制与换域步骤见 [领域插件说明](docs/plugin-development.md)。

LLM 可选，用于边界复核和已入选论文的翻译补全。未设置 `LLM_API_KEY` 时仍可独立更新。真实密钥只能放入环境变量或 GitHub Actions Secrets，见 [LLM 配置与密钥安全](docs/llm-configuration.md)。两个仓库的 Repository Secrets 相互独立，旧仓库的 Key 不会自动转移。

## GitHub Pages 部署

1. 创建普通公开仓库，推送代码；在 Settings / Pages / Source 选择 **GitHub Actions**。首次推送前启用 Pages，避免 `configure-pages` 因仓库尚未注册 Pages 而失败。
2. 自用或 Fork 时修改 `config/config.yml`、`config/config.example.yml`、`CNAME` 中的仓库和域名。
3. DNS 添加 CNAME：`acpaper.ning0713.top` → `Ning0713.github.io`；Pages 中设相同自定义域名，等待证书后启用 HTTPS。
4. 需要 AI 时在新仓库单独创建 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL` Repository Secrets。
5. Actions 中运行 `Update And Deploy Papers`，日期 `auto`。首次同步取最新已发布日期；如需更早的历史，可在本地使用 `sync --since YYYY-MM-DD`。新领域必须使用独立数据目录。

成功更新或 `unchanged` 都会构建并部署，预览不会部署。工作流保留最近一次 Pages 部署并清理旧部署记录。

## 更新与补跑

更新完全由 GitHub Actions 执行，也可用 GitHub CLI 手动触发。日常保持日期参数为 `auto`，程序会查询上游日期列表并补齐遗漏；指定日期时可选择 `force` 强制重新筛选，或用 `dry_run` 预览。详细命令、调度说明和故障排查见 [更新与运维](docs/operations.md)。

2026 年 11 月上游改版后，抓取改用 `/api/dates` 与 `/api/daily/{date}`。接口、日期或完整性检查失败会让 Actions 明确失败，并保留已有数据。上游没有发布的日期不会生成空白日报。详见 [数据来源](docs/data-sources.md)。

## 贡献、来源与许可

贡献前运行 `ruff check .` 和 `pytest -q`，见 [CONTRIBUTING.md](CONTRIBUTING.md)。筛选规则是启发式方法，欢迎提供误报和漏报样本。

论文元数据来自 Axi 和 [arXiv](https://arxiv.org/)，本项目不托管 PDF。页面布局和交互参考 [Axi404/ArxivReader](https://github.com/Axi404/ArxivReader)，与 Axi404 无隶属关系。代码采用 [MIT](LICENSE)，上游版权与许可保留于 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
