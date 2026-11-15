import json
from pathlib import Path

import httpx
import pytest

from adpaper.config import SourceConfig
from adpaper.models import normalize_arxiv_id
from adpaper.sources.arxiv import ArxivSource
from adpaper.sources.axi import AxiSource

FIXTURES = Path(__file__).parent / "fixtures"


def test_normalize_arxiv_id_variants():
    assert normalize_arxiv_id("https://arxiv.org/abs/2608.00001v2") == "2608.00001"
    assert normalize_arxiv_id("arXiv:hep-th/9901001v1") == "hep-th/9901001"


def test_axi_parser_deduplicates_and_extracts_fields():
    result = AxiSource(SourceConfig()).parse_daily_html(
        (FIXTURES / "axi_daily.html").read_text(encoding="utf-8"),
        url="https://paper.axi404.top/daily/2026-08-10",
        expected_date="2026-08-10",
    )
    assert result.raw_count == 3
    assert len(result.candidates) == 2
    paper = result.candidates[0]
    assert paper.arxiv_id == "2608.00001"
    assert paper.title_zh.startswith("面向自动驾驶")
    assert paper.translation_url.endswith("2608.00001")
    assert "cs.CV" in paper.categories


def test_arxiv_atom_parser():
    papers = ArxivSource(SourceConfig()).parse_feed(
        (FIXTURES / "arxiv_feed.xml").read_text(encoding="utf-8")
    )
    assert len(papers) == 1
    assert papers[0].arxiv_id == "2608.00001"
    assert papers[0].authors == ["Jane Doe", "Alex Smith"]
    assert papers[0].pdf_url.endswith("2608.00001v2")


def test_arxiv_discovery_uses_plugin_categories(monkeypatch):
    source = ArxivSource(
        SourceConfig(),
        discovery_categories=("quant-ph", "physics.optics"),
    )
    captured: dict[str, str] = {}

    def fake_get(params: dict[str, str]) -> str:
        captured.update(params)
        return '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'

    monkeypatch.setattr(source, "_get", fake_get)
    assert source.discover_for_date("2026-08-12") == []
    assert "cat:quant-ph OR cat:physics.optics" in captured["search_query"]


def test_axi_json_deduplicates_cross_lists_and_merges_metadata():
    result = AxiSource(SourceConfig()).parse_daily_json(
        (FIXTURES / "axi_daily.json").read_text(encoding="utf-8"),
        url="https://paper.axi404.top/api/daily/2026-11-13",
        expected_date="2026-11-13",
    )
    assert result.raw_count == 3
    assert len(result.candidates) == 2
    paper = result.candidates[0]
    assert paper.arxiv_id == "2611.14685"
    assert paper.title_zh == "多模态情绪识别"
    assert paper.abstract_zh
    assert paper.authors == ["Jane Doe", "Alex Smith"]
    assert paper.categories == ["cs.CV", "cs.CL"]
    assert paper.published_at == "2026-11-13"
    assert paper.translation_url == "https://hjfy.top/arxiv/2611.14685"
    assert paper.axi_url == "https://paper.axi404.top/daily/2026-11-13"
    assert paper.source["axi_api"] == result.source_url


@pytest.mark.parametrize("change", ["date", "incomplete", "count", "schema", "record"])
def test_axi_json_rejects_wrong_or_partial_data(change):
    payload = json.loads((FIXTURES / "axi_daily.json").read_text(encoding="utf-8"))
    if change == "date":
        payload["date"] = "2026-11-12"
    elif change == "incomplete":
        payload["status"] = {"fetched_at": "2026-11-13T07:00:00"}
    elif change == "count":
        payload["total_papers"] = 99
    elif change == "schema":
        payload["papers_by_category"] = []
    else:
        payload["papers_by_category"]["cs.CV"][0].pop("arxiv_id")
    with pytest.raises(ValueError):
        AxiSource(SourceConfig()).parse_daily_json(
            json.dumps(payload),
            url="https://example.test/api/daily/2026-11-13",
            expected_date="2026-11-13",
        )


def test_axi_fetch_uses_api_and_only_falls_back_for_missing_endpoint(monkeypatch):
    source = AxiSource(SourceConfig())
    urls = []

    def get(url):
        urls.append(url)
        if "/api/" in url:
            return httpx.Response(200, text=(FIXTURES / "axi_daily.json").read_text("utf-8"))
        pytest.fail("The redesigned frontend must use the JSON API")

    monkeypatch.setattr(source, "_get", get)
    assert len(source.fetch_daily("2026-11-13").candidates) == 2
    assert urls == ["https://paper.axi404.top/api/daily/2026-11-13"]

    def legacy_get(url):
        if "/api/" in url:
            response = httpx.Response(404, request=httpx.Request("GET", url))
            response.raise_for_status()
        return httpx.Response(200, text=(FIXTURES / "axi_daily.html").read_text("utf-8"))

    monkeypatch.setattr(source, "_get", legacy_get)
    assert len(source.fetch_daily("2026-08-10").candidates) == 2


def test_axi_dates_reject_invalid_calendar_dates(monkeypatch):
    source = AxiSource(SourceConfig())
    monkeypatch.setattr(
        source,
        "_get",
        lambda _: httpx.Response(
            200,
            json={"dates": ["2026-11-13", "2026-02-30"]},
        ),
    )
    with pytest.raises(ValueError):
        source.available_dates()
