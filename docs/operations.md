# 更新与运维

## 自动更新

`.github/workflows/update-and-deploy.yml` 在工作日北京时间 13:00 同步，并在
17:17 再次检查（UTC cron 为 `0 5 * * 1-5` 与 `17 9 * * 1-5`）。GitHub
可能延迟或丢弃定时事件，因此这些时间是计划触发时间，不保证准点。

每次运行先查询 Axi 的 `/api/dates`，从本地最早的归档日期到当天按时间顺序
补齐缺失日期。已保存的日期直接跳过；上游没有发布的日期不会生成日报。
上游当日尚未完成、接口改变或请求失败会明确报错，后续运行会重新尝试。
自动更新不依赖本机电脑或聊天机器人。

## 在 GitHub 手动补跑

打开 Actions → **Update And Deploy Papers** → **Run workflow**：

| 参数 | 用途 |
| --- | --- |
| `date=auto`（默认） | 同步所有遗漏且已发布的日期；恢复自动更新时优先使用 |
| `date=YYYY-MM-DD` 或 `today` | 只处理指定日期；`today` 使用北京时间 |
| `force=true` | 强制重新抓取、筛选指定单日；`auto` 模式会忽略此参数 |
| `dry_run=true` | 抓取、筛选和元数据检查，不写数据、不提交、不部署 |
| `allow_arxiv_discovery=true` | 仅单日模式下，在 Axi 失败时启用 arXiv 分类回退 |

GitHub CLI 等价命令：

```powershell
gh workflow run update-and-deploy.yml --repo Ning0713/ArXivACReader --field date=auto
gh run list --repo Ning0713/ArXivACReader --workflow update-and-deploy.yml --limit 5
gh run view <run-id> --repo Ning0713/ArXivACReader --log-failed
```

重新筛选某一天：

```powershell
gh workflow run update-and-deploy.yml --repo Ning0713/ArXivACReader --field date=2026-11-13 --field force=true
```

## 本地验证与历史导入

在仓库根目录、已安装依赖的 Python 环境中执行：

```powershell
python -m adpaper sync --dry-run
python -m adpaper sync --since 2026-11-04 --until 2026-11-13
python -m adpaper update --date 2026-11-13 --force --dry-run
python -m adpaper validate
python -m adpaper build
```

本地 `sync` 写入数据但不推送或部署。首次运行的空归档默认只取最新可用日期；
希望从指定日期开始时使用 `--since`。LLM 配置仍见
[密钥安全说明](llm-configuration.md)；本地没有密钥时使用规则和上游翻译。

## 如何判断更新成功

Actions 的 **Paper update** 摘要包含 `status`、上游最新日期、实际更新日期、
候选数、入选数与警告。`updated` 表示写入了新日报；`unchanged` 表示本地已包含
当前可用日期；`preview` 只预览；`failed` 会返回非零退出码并停止部署。

一次请求被接受不代表部署完成。检查 `update` 和 `deploy` 两个 job，并对照
网站首页最新日期。若没有当日数据，先查看 Axi 是否发布了该日期，而不是强行
把前一天的数据标成今天。arXiv 补全失败只记录警告，已有 Axi 内容仍可发布。

## 项目范围

本仓库独立维护情感计算站点。旧自动驾驶仓库已停止自动更新并作为历史参考；
两个仓库的 Secrets、历史数据和部署相互独立。
