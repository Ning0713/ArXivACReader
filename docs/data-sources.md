# Data Sources

Since the November 2026 Axi redesign, the updater uses `/api/dates` to discover
published days and `/api/daily/{date}` for `papers_by_category` JSON. It requests
all categories without pagination or category filters, includes both new and
cross-listed papers, and deduplicates canonical arXiv IDs while merging category
and translation metadata. `raw_count` counts category entries; `candidate_count`
counts unique papers. Requests use a descriptive User-Agent, timeouts and retries.

The parser verifies the requested date, category/record shapes, unique-paper
count when supplied, and `status.done_at` for format 2 files. An unfinished or
malformed day fails without replacing an existing manifest. A 404/405 API endpoint
can fall back to the original BeautifulSoup HTML parser for older installations;
schema errors never silently fall back to an unrelated date or an empty archive.

`sync` fills missing published dates from the earliest local archive date through
today (Asia/Shanghai). `--since` and `--until` override that range. With an empty
archive and no start date, it imports only the latest published day. Missing dates
are reconsidered on each run, so delayed upstream publication can be picked up
later. Dates absent from Axi, including weekends, are not fabricated.

Selected IDs are sent to the arXiv Atom API in batches. The updater does not
download or mirror PDFs. arXiv discovery is an explicit, single-day fallback;
its submitted-date semantics differ from Axi's announcement dates.

The generated record retains `axi_url`, `arxiv_url`, source mode, and filter
version so a future contributor can audit how a paper entered the archive.

