import json
from pathlib import Path

from adpaper.config import AppConfig, PathConfig, SiteConfig
from adpaper.models import Paper, RelevanceResult, TagAssignment
from adpaper.site import SiteBuilder
from adpaper.storage import Repository
from adpaper.validate import validate_repository


def make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        root=tmp_path,
        site=SiteConfig(output_dir="site", base_path="/"),
        paths=PathConfig(
            data_dir="data",
            templates_dir=str(Path.cwd() / "templates"),
            static_dir=str(Path.cwd() / "static"),
        ),
    )


def test_repository_and_static_build(tmp_path):
    config = make_config(tmp_path)
    repository = Repository(config)
    paper = Paper(
        arxiv_id="2608.00001",
        title="Multimodal Emotion Recognition",
        abstract="An affective computing paper.",
        tags=TagAssignment("多模态情感", ["情绪识别"]),
        relevance=RelevanceResult(True, 50),
    )
    repository.upsert_paper(paper, "2026-08-10")
    orphan = Paper(
        arxiv_id="2608.99999",
        title="Orphaned paper",
    )
    repository.upsert_paper(orphan, "2026-08-09")
    orphan_path = repository.paper_path(orphan.arxiv_id)
    assert orphan_path.exists()
    repository.save_daily(
        date="2026-08-10",
        paper_ids=[paper.arxiv_id],
        source_url="https://paper.axi404.top/daily/2026-08-10",
        source_mode="axi",
        candidate_count=2,
        raw_count=2,
    )
    index = repository.rebuild_indexes("/")
    assert not orphan_path.exists()
    assert index["storage_bytes"] > 0
    assert index["storage_mb"] >= 0
    assert validate_repository(repository) == []

    output = SiteBuilder(config).build()
    assert (output / "index.html").exists()
    daily = output / "daily" / "2026-08-10" / "index.html"
    assert daily.exists()
    html = daily.read_text(encoding="utf-8")
    assert "多模态情感" in html
    assert "多模态情感 / 1 / 2608.00001" in html
    assert "paper-2608-00001" in html
    assert (output / "assets" / "search-index.json").exists()
    search_index = json.loads(
        (output / "assets" / "search-index.json").read_text(encoding="utf-8")
    )
    assert search_index["items"]
