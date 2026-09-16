"""Deterministic affective-computing filter; generic multimodal work is out of scope."""

from __future__ import annotations

import re
import unicodedata

from adpaper.models import Paper, RelevanceResult, TagAssignment


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\s\-‐‑–—]+", " ", value)


def _matches(text: str, terms: tuple[str, ...]) -> list[str]:
    matches = []
    for term in terms:
        normalized = _normalize(term)
        pattern = rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])"
        if re.search(pattern, text):
            matches.append(term)
    return matches


def _text(paper: Paper) -> str:
    return _normalize(" ".join([
        paper.title, paper.title_zh, paper.abstract, paper.abstract_zh,
    ]))


class AffectiveComputingPlugin:
    slug = "affective-computing"
    version = "affective-computing-v3"
    display_name = "情感计算（情绪理解、情感分析、共情交互及相关多模态大模型）"
    arxiv_categories = ("cs.CV", "cs.CL", "cs.HC", "cs.AI", "cs.LG", "eess.AS")
    minimum_weak_score = 12
    tags = (
        "多模态情感", "情绪识别", "语音情感", "面部表情", "文本情感", "情感大模型",
        "共情交互", "情感生成", "心理状态/福祉", "社交信号", "生理信号",
        "数据集/评测", "鲁棒性/偏差",
    )
    explicit_terms = (
        "affective computing", "affect recognition", "affect prediction", "affect detection",
        "emotion recognition", "emotion understanding", "emotion reasoning", "emotion detection",
        "emotion classification", "emotion prediction", "emotion analysis", "emotion estimation",
        "emotional intelligence", "emotion aware", "emotion cause", "emotion regulation",
        "sentiment analysis", "sentiment classification", "sentiment prediction",
        "facial expression recognition", "facial expression analysis", "micro expression",
        "empathetic dialogue", "empathetic response", "empathetic conversation",
        "empathic dialogue", "empathic response", "empathy detection", "empathy recognition",
        "emotional support", "emotional speech", "expressive speech synthesis",
        "emotion synthesis", "emotion generation", "emotion controlled",
        "情感计算", "情绪识别", "情感识别", "情绪理解", "情感理解", "情绪推理",
        "情感分析", "情感分类", "情感预测", "情绪检测", "情感智能", "情绪智能",
        "情感大模型", "情绪感知", "表情识别", "微表情", "共情对话", "共情响应",
        "共情交互", "情感支持", "情绪支持", "情感语音", "情绪生成",
    )
    # Ambiguous names such as MELD, SEED and DailyDialog need affective context.
    dataset_terms = (
        "IEMOCAP", "CMU MOSI", "CMU MOSEI", "AffectNet", "RAF DB", "FER2013",
        "RAVDESS", "CREMA D", "EmoVoxCeleb", "EmoryNLP", "EmpatheticDialogues",
        "DEAP dataset", "WESAD", "DREAMER dataset", "MAFW", "DFEW", "EmoSet",
    )
    contextual_datasets = ("MELD", "SEED", "DailyDialog", "SemEval", "RECOLA")
    context_terms = (
        "emotion", "emotions", "emotional", "affective", "empathy", "empathetic", "empathic",
        "mood", "emotional valence", "emotional arousal", "情绪", "共情",
    )
    technical_terms = (
        "multimodal", "multi modal", "large language model", "large language models",
        "vision language", "audio language", "MLLM", "MLLMs", "VLM", "LLM", "LLMs",
        "recognition", "classification", "detection", "prediction", "reasoning",
        "generation", "dialogue", "conversation", "benchmark", "dataset",
        "speech", "audio", "EEG", "physiological", "neural network", "deep learning",
        "多模态", "大模型", "识别", "分类", "检测", "预测", "推理", "生成", "对话", "评测",
    )
    excluded_title_terms = (
        "stock market", "stock price", "financial sentiment", "investor sentiment",
        "market sentiment", "cryptocurrency", "asset pricing", "trading strategy",
        "political sentiment", "election prediction", "voter sentiment",
        "protein", "molecular", "chemical", "tumor segmentation", "medical image segmentation",
        "金融情绪", "股票预测", "股价预测", "投资者情绪", "市场情绪", "政治情绪",
    )
    tag_terms = {
        "多模态情感": ("multimodal", "multi modal", "audio visual", "cross modal", "多模态"),
        "情绪识别": ("emotion recognition", "emotion detection", "emotion classification",
                   "affect recognition", "情绪识别", "情感识别", "情绪检测"),
        "语音情感": ("speech", "audio", "prosody", "IEMOCAP", "RAVDESS", "语音", "声学"),
        "面部表情": ("facial expression", "micro expression", "AffectNet", "RAF DB", "表情"),
        "文本情感": ("sentiment analysis", "aspect based", "textual", "opinion mining",
                   "文本", "情感分析"),
        "情感大模型": ("large language model", "large language models", "MLLM", "MLLMs",
                    "LLM", "LLMs", "vision language", "audio language", "大模型"),
        "共情交互": ("empathy", "empathetic", "empathic", "emotional support", "共情"),
        "情感生成": ("generation", "synthesis", "expressive", "情感生成", "情绪生成", "合成"),
        "心理状态/福祉": ("mental health", "depression", "anxiety", "well being", "stress",
                        "心理", "抑郁", "焦虑"),
        "社交信号": ("social signal", "social interaction", "nonverbal", "社交", "非语言"),
        "生理信号": ("EEG", "ECG", "EDA", "physiological", "electroencephalogram", "生理", "脑电"),
        "数据集/评测": ("dataset", "benchmark", "evaluation", "数据集", "评测", "基准"),
        "鲁棒性/偏差": ("robust", "robustness", "bias", "fairness", "domain adaptation",
                       "鲁棒", "偏差", "公平"),
    }

    def evaluate(self, paper: Paper) -> RelevanceResult:
        text = _text(paper)
        title = _normalize(" ".join([paper.title, paper.title_zh]))
        explicit = _matches(text, self.explicit_terms)
        contexts = _matches(text, self.context_terms)
        datasets = _matches(text, self.dataset_terms)
        if contexts:
            datasets += _matches(text, self.contextual_datasets)
        technical = _matches(text, self.technical_terms)
        excluded = _matches(title, self.excluded_title_terms)
        score = min(100, 28 * len(explicit) + 20 * len(datasets)
                    + 6 * len(contexts) + 3 * len(technical))
        has_domain_evidence = bool(explicit or datasets or contexts)
        include = bool(explicit or datasets or (
            contexts and technical and score >= self.minimum_weak_score
        ))
        reasons = []
        if explicit:
            reasons.append("明确的情感计算任务")
        if datasets:
            reasons.append("情感计算数据集证据")
        if contexts and technical:
            reasons.append("情感上下文与计算技术共同命中")
        if excluded or not has_domain_evidence:
            include = False
            score = 0  # Also prevents unrelated papers entering optional LLM review.
            reasons.append("标题属于范围外应用" if excluded else "缺少情感计算证据")
        return RelevanceResult(
            include=include,
            score=float(score),
            matched_terms=list(dict.fromkeys([*explicit, *datasets, *contexts,
                                              *technical, *excluded])),
            reasons=reasons,
        )

    def assign_tags(self, paper: Paper) -> TagAssignment:
        text = _text(paper)
        ranked = sorted(
            ((len(_matches(text, self.tag_terms[tag])), -order, tag)
             for order, tag in enumerate(self.tags)), reverse=True,
        )
        ordered = [tag for score, _, tag in ranked if score] or ["情绪识别"]
        return TagAssignment(ordered[0], ordered[1:3]).normalized()


plugin = AffectiveComputingPlugin()
