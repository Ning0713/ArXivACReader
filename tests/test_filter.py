import pytest

from adpaper.models import Paper
from plugins.affective_computing import plugin


@pytest.mark.parametrize(("title", "abstract"), [
    ("Multimodal Emotion Recognition with Large Language Models", "Audio and visual reasoning."),
    ("Speech Emotion Recognition on IEMOCAP", "Cross-corpus speech evaluation."),
    ("Empathetic Response Generation", "Generating supportive dialogue responses."),
    ("Facial Expression Recognition", "Robust evaluation on AffectNet."),
    ("面向多模态大模型的情绪理解", "融合语音与表情的情感推理。"),
    ("Cross-domain classification on CMU-MOSEI", "Learning robust representations."),
    ("Emotion-Aware Audio-Language Models", "Reasoning about human feelings."),
    ("Measuring empathy in LLMs", "A benchmark for reasoning about human emotions."),
    ("EEG emotion classification", "Physiological signals for affective computing."),
])
def test_affective_tasks_are_included(title, abstract):
    paper = Paper(arxiv_id="2609.00001", title=title, abstract=abstract)
    decision = plugin.evaluate(paper)
    assert decision.include
    assert decision.score > 0
    tags = plugin.assign_tags(paper)
    assert tags.primary in plugin.tags
    assert len(tags.secondary) <= 2
    assert len(tags.all) == len(set(tags.all))


@pytest.mark.parametrize(("title", "abstract"), [
    ("A General Multimodal Large Language Model", "Vision-language reasoning and generation."),
    ("Financial Sentiment Prediction from Stock News", "Sentiment analysis with LLMs."),
    ("Political Sentiment Analysis", "Emotion recognition for election prediction."),
    ("Autonomous Driving BEV Perception", "3D detection on nuScenes."),
    ("Medical Image Segmentation with Diffusion", "A healthcare diagnosis benchmark."),
    ("Protein generation", "Affective computing is a possible future application."),
    ("A random SEED for models", "Classification and prediction on a dataset."),
    ("MELD: a general framework", "Document reasoning and speech generation."),
    ("EEG signal compression", "A neural network for physiological data."),
    ("The effect of data scaling", "Large language models for general reasoning."),
])
def test_unrelated_or_ambiguous_papers_are_excluded(title, abstract):
    decision = plugin.evaluate(Paper(arxiv_id="2609.00002", title=title, abstract=abstract))
    assert not decision.include
    assert decision.score == 0


def test_tag_matching_respects_word_boundaries():
    paper = Paper(arxiv_id="2609.00003", title="Emotion recognition", abstract="A bias-free study.")
    assert "生理信号" not in plugin.assign_tags(paper).all


def test_borderline_signal_can_be_reviewed():
    decision = plugin.evaluate(Paper(arxiv_id="2609.00004", title="Emotion and mood"))
    assert not decision.include
    assert decision.score == 12
