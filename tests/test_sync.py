import json
import runpy
import sys
from pathlib import Path

import pytest

from adpaper.config import AppConfig, LlmConfig
from adpaper.pipeline import UpdatePipeline, UpdateReport
from adpaper.sources.axi import AxiSource

FIXTURE = Path(__file__).parent / "fixtures" / "axi_daily.json"


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    pipeline = UpdatePipeline(AppConfig(root=tmp_path, llm=LlmConfig(enabled=False)))
    pipeline.repository.save_daily(
        date="2026-11-03",
        paper_ids=[],
        source_url="test",
        source_mode="axi",
        candidate_count=0,
        raw_count=0,
    )
    monkeypatch.setattr(
        pipeline.axi,
        "available_dates",
        lambda: [
            "2026-11-03",
            "2026-11-04",
            "2026-11-13",
            "2026-11-16",
        ],
    )
    monkeypatch.setattr(pipeline, "_enrich_from_arxiv", lambda _: [])

    def fetch(day):
        content = json.loads(FIXTURE.read_text("utf-8"))
        content["date"] = day
        return AxiSource(pipeline.config.sources).parse_daily_json(
            json.dumps(content),
            url=f"https://example.test/api/daily/{day}",
            expected_date=day,
        )

    monkeypatch.setattr(pipeline.axi, "fetch_daily", fetch)
    return pipeline


def test_sync_fills_missing_published_dates_and_is_idempotent(pipeline):
    report = pipeline.sync("2026-11-15")
    assert report.status == "updated"
    assert report.upstream_latest == "2026-11-13"
    assert report.updated_dates == ["2026-11-04", "2026-11-13"]
    assert report.candidate_count == 4
    assert report.selected_count == 2
    assert pipeline.repository.dates() == ["2026-11-13", "2026-11-04", "2026-11-03"]
    assert pipeline.sync("2026-11-15").status == "unchanged"


def test_sync_preview_does_not_store_new_days(pipeline):
    report = pipeline.sync("2026-11-15", dry_run=True)
    assert report.status == "preview"
    assert report.changed is False
    assert report.updated_dates == ["2026-11-04", "2026-11-13"]
    assert pipeline.repository.dates() == ["2026-11-03"]


def test_sync_source_failure_is_reported_and_preserves_existing_day(pipeline, monkeypatch):
    existing = pipeline.repository.load_daily("2026-11-03")

    def broken(day):
        raise ValueError("daily data is incomplete")

    monkeypatch.setattr(pipeline.axi, "fetch_daily", broken)
    report = pipeline.sync("2026-11-15")
    assert report.status == "failed"
    assert "2026-11-04" in report.warnings[0]
    assert pipeline.repository.load_daily("2026-11-03") == existing
    assert pipeline.repository.load_daily("2026-11-04") is None
    assert pipeline.run("2026-11-03", force=True).status == "failed"
    assert pipeline.repository.load_daily("2026-11-03") == existing


def test_sync_dates_failure_is_not_a_success(pipeline, monkeypatch):
    def broken():
        raise ValueError("API no longer matches schema")

    monkeypatch.setattr(pipeline.axi, "available_dates", broken)
    assert pipeline.sync("2026-11-15").status == "failed"


def test_sync_explicit_range_and_rejects_inverted_range(pipeline):
    report = pipeline.sync("2026-11-15", since="2026-11-13")
    assert report.updated_dates == ["2026-11-13"]
    with pytest.raises(ValueError):
        pipeline.sync("2026-11-13", since="2026-11-15")


def test_module_entrypoint_propagates_source_failure(tmp_path, monkeypatch, capsys):
    config = tmp_path / "config.yml"
    config.write_text("paths:\n  data_dir: data\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "adpaper",
            "--config",
            str(config),
            "update",
            "--date",
            "2026-11-13",
        ],
    )
    monkeypatch.setattr(
        UpdatePipeline,
        "run",
        lambda *args, **kwargs: UpdateReport(
            status="failed",
            date="2026-11-13",
            warnings=["source schema changed"],
        ),
    )
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("adpaper", run_name="__main__")
    assert exc.value.code == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"
