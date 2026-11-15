# Architecture

The repository is a static-site pipeline:

```text
Axi daily JSON -> parser -> domain plugin -> optional LLM enrichment
                                  |                 |
                             arXiv metadata --------+
                                  |
                   data/papers + data/daily + indexes
                                  |
                         Jinja2 static site
                                  |
                         GitHub Pages / CNAME
```

The Axi JSON API is the default candidate authority. The active domain plugin also
provides the domain name, tags, and arXiv categories used by explicit discovery
fallback. arXiv metadata fills missing
authors, dates, categories, and canonical links. A failed arXiv enrichment does
not discard Axi content. A failed Axi fetch leaves the last published date
untouched unless an operator explicitly enables arXiv discovery fallback.

Favorites are browser-local. No visitor, account, or traffic database is
required.

Scheduled runs call `sync`, which compares `/api/dates` with local manifests and
processes missing days in ascending order. Single-day `update` remains available
for previews and forced reclassification. The module entrypoint propagates the
CLI exit code, and the workflow also checks the report status before deployment;
source failures cannot turn into a successful run with deployment silently skipped.
