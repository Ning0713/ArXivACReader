from adpaper.config import AppConfig
from adpaper.models import Paper
from adpaper.pipeline import UpdatePipeline


def test_llm_does_not_admit_unrelated_candidates(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-only")
    pipeline = UpdatePipeline(AppConfig(root=tmp_path))
    calls = []

    def enrich(paper, *, borderline):
        calls.append(paper.arxiv_id)
        return {"relevant": True, "title_zh": "模型结果", "abstract_zh": "摘要"}

    monkeypatch.setattr(pipeline.llm, "enrich", enrich)
    candidates = [
        Paper(arxiv_id="2609.00001", title="General multimodal large language models"),
        Paper(arxiv_id="2609.00002", title="Financial sentiment analysis"),
        Paper(arxiv_id="2609.00003", title="Speech emotion recognition"),
        Paper(arxiv_id="2609.00004", title="Emotion and mood"),
    ]
    selected = pipeline._filter(candidates, [])
    assert calls == ["2609.00003", "2609.00004"]
    assert [paper.arxiv_id for paper in selected] == calls
    assert selected[0].title_zh == "模型结果"
    assert selected[1].relevance.classifier == "rules+llm"


def test_pipeline_runs_rules_without_llm_key(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    pipeline = UpdatePipeline(AppConfig(root=tmp_path))
    selected = pipeline._filter([
        Paper(arxiv_id="2609.00001", title="Empathetic Response Generation"),
        Paper(arxiv_id="2609.00002", title="General multimodal reasoning"),
    ], [])
    assert [paper.arxiv_id for paper in selected] == ["2609.00001"]
    assert selected[0].relevance.classifier == "rules"
