from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from adpaper.config import SourceConfig
from adpaper.models import Paper, normalize_arxiv_id, normalize_space
from adpaper.storage import validate_date

DATE_RE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")
CATEGORY_RE = re.compile(r"\b(?:cs|eess|stat)\.[A-Z]{2}\b")


@dataclass(slots=True)
class AxiDailyResult:
    date: str
    source_url: str
    source_hash: str
    candidates: list[Paper]
    raw_count: int


class AxiSource:
    def __init__(self, config: SourceConfig):
        self.config = config

    def fetch_daily(self, date: str) -> AxiDailyResult:
        validate_date(date)
        base = self.config.axi_base_url.rstrip("/")
        url = f"{base}/api/daily/{date}"
        try:
            response = self._get(url)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in {404, 405}:
                raise
            # Keep support for installations running the original HTML frontend.
            url = f"{base}/daily/{date}"
            return self.parse_daily_html(self._get(url).text, url=url, expected_date=date)
        return self.parse_daily_json(response.text, url=url, expected_date=date)

    def available_dates(self) -> list[str]:
        url = f"{self.config.axi_base_url.rstrip('/')}/api/dates"
        payload = self._get(url).json()
        if not isinstance(payload, dict) or not isinstance(payload.get("dates"), list):
            raise ValueError("Axi dates API did not return a dates list")
        dates = payload["dates"]
        if any(not isinstance(day, str) for day in dates):
            raise ValueError("Axi dates API contains an invalid date")
        return sorted({validate_date(day) for day in dates})

    def _get(self, url: str) -> httpx.Response:
        for attempt in range(1, self.config.retries + 1):
            try:
                with httpx.Client(
                    timeout=self.config.timeout_seconds,
                    follow_redirects=True,
                    headers={"User-Agent": self.config.user_agent},
                ) as client:
                    response = client.get(url)
                    response.raise_for_status()
                return response
            except httpx.HTTPError as exc:
                if isinstance(exc, httpx.HTTPStatusError):
                    code = exc.response.status_code
                    if code < 500 and code not in {408, 429}:
                        raise
                if attempt == self.config.retries:
                    raise
                time.sleep(min(2 ** (attempt - 1), 8))
        raise RuntimeError(f"No attempts configured to fetch Axi: {url}")

    def parse_daily_json(
        self,
        content: str,
        *,
        url: str,
        expected_date: str,
    ) -> AxiDailyResult:
        payload = json.loads(content)
        if not isinstance(payload, dict) or payload.get("date") != expected_date:
            raise ValueError(f"Axi daily JSON date does not match {expected_date}")
        groups = payload.get("papers_by_category")
        if not isinstance(groups, dict) or not groups:
            raise ValueError("Axi daily JSON does not contain category lists")
        # Modern files are published while collection/translation is still running.
        # Do not store a partial day as complete; the next sync will retry it.
        if payload.get("format", 1) >= 2:
            status = payload.get("status")
            if not isinstance(status, dict) or not status.get("done_at"):
                raise ValueError(f"Axi daily data for {expected_date} is not complete yet")

        page_url = f"{self.config.axi_base_url.rstrip('/')}/daily/{expected_date}"
        papers: dict[str, Paper] = {}
        raw_count = 0
        for category, records in groups.items():
            if not isinstance(category, str) or not isinstance(records, list):
                raise ValueError("Axi daily JSON contains an invalid category list")
            for record in records:
                raw_count += 1
                if not isinstance(record, dict):
                    raise ValueError("Axi daily JSON contains an invalid paper record")
                raw_id = record.get("arxiv_id")
                title = record.get("title")
                if not isinstance(raw_id, str) or not isinstance(title, str) or not title.strip():
                    raise ValueError("Axi daily JSON contains a paper without ID or title")
                arxiv_id = normalize_arxiv_id(raw_id)
                categories = record.get("categories") or []
                authors = record.get("authors") or []
                if not isinstance(categories, list) or not isinstance(authors, list):
                    raise ValueError(f"Invalid author/category lists for {arxiv_id}")
                categories = list(
                    dict.fromkeys(
                        [
                            *categories,
                            category,
                            *(
                                [record["primary_category"]]
                                if record.get("primary_category")
                                else []
                            ),
                        ]
                    )
                )
                paper = Paper(
                    arxiv_id=arxiv_id,
                    title=title,
                    title_zh=record.get("title_zh") or "",
                    authors=authors,
                    abstract=record.get("abstract") or "",
                    abstract_zh=record.get("abstract_zh") or "",
                    categories=categories,
                    published_at=record.get("published") or "",
                    arxiv_url=record.get("arxiv_url") or "",
                    pdf_url=record.get("pdf_url") or "",
                    axi_url=page_url,
                    translation_url=record.get("hjfy_url") or "",
                    source={"axi": page_url, "axi_api": url},
                    fetched_at=datetime.now(UTC).isoformat(),
                )
                if previous := papers.get(arxiv_id):
                    previous.categories = list(
                        dict.fromkeys(
                            [
                                *previous.categories,
                                *paper.categories,
                            ]
                        )
                    )
                    for field in ("title_zh", "abstract", "abstract_zh", "translation_url"):
                        if not getattr(previous, field):
                            setattr(previous, field, getattr(paper, field))
                else:
                    papers[arxiv_id] = paper
        if not papers:
            raise ValueError("Axi daily JSON contains no paper records")
        total = payload.get("total_papers")
        if total is not None and total != len(papers):
            raise ValueError(f"Axi daily JSON expected {total} unique papers, found {len(papers)}")
        return AxiDailyResult(
            date=expected_date,
            source_url=url,
            source_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            candidates=list(papers.values()),
            raw_count=raw_count,
        )

    def parse_daily_html(
        self,
        html: str,
        *,
        url: str,
        expected_date: str | None = None,
    ) -> AxiDailyResult:
        soup = BeautifulSoup(html, "html.parser")
        paper_nodes = soup.select(".paper[data-arxiv-id]")
        if not paper_nodes:
            raise ValueError("Axi page does not contain paper nodes")

        page_date = self._page_date(soup) or expected_date or ""
        if expected_date and page_date and expected_date != page_date:
            raise ValueError(f"Axi returned date {page_date}, expected {expected_date}")

        candidates: list[Paper] = []
        seen: set[str] = set()
        for node in paper_nodes:
            raw_id = node.get("data-arxiv-id", "")
            try:
                arxiv_id = normalize_arxiv_id(str(raw_id))
            except ValueError:
                continue
            if arxiv_id in seen:
                continue
            seen.add(arxiv_id)

            arxiv_link = self._link(node, "link-arxiv", "arxiv.org/abs")
            pdf_link = self._link(node, "link-pdf", "arxiv.org/pdf")
            translation_link = self._link(node, "link-hjfy", "hjfy")
            paper = Paper(
                arxiv_id=arxiv_id,
                title=self._text(node, ".paper-title"),
                title_zh=self._text(node, ".paper-title-zh"),
                authors=self._authors(node),
                abstract=self._text(node, ".abstract-en"),
                abstract_zh=self._text(node, ".abstract-zh"),
                categories=self._categories(node),
                arxiv_url=urljoin(url, arxiv_link) if arxiv_link else "",
                pdf_url=urljoin(url, pdf_link) if pdf_link else "",
                axi_url=f"{url}#paper-{arxiv_id.replace('.', '-')}",
                translation_url=urljoin(url, translation_link) if translation_link else "",
                source={"axi": url},
                fetched_at=datetime.now(UTC).isoformat(),
            )
            if paper.title:
                candidates.append(paper)

        if not candidates:
            raise ValueError("Axi page contained no valid paper records")
        return AxiDailyResult(
            date=page_date,
            source_url=url,
            source_hash=hashlib.sha256(html.encode("utf-8")).hexdigest(),
            candidates=candidates,
            raw_count=len(paper_nodes),
        )

    @staticmethod
    def _text(node: Tag, selector: str) -> str:
        child = node.select_one(selector)
        return normalize_space(child.get_text(" ", strip=True) if child else "")

    @classmethod
    def _authors(cls, node: Tag) -> list[str]:
        text = cls._text(node, ".paper-authors")
        return [text] if text else []

    @classmethod
    def _categories(cls, node: Tag) -> list[str]:
        values: list[str] = []
        category_text = cls._text(node, ".paper-categories")
        number_text = cls._text(node, ".paper-number")
        button = node.select_one("[data-paper-category]")
        button_value = button.get("data-paper-category", "") if button else ""
        for source in (category_text, number_text, str(button_value)):
            values.extend(CATEGORY_RE.findall(source))
        return list(dict.fromkeys(values))

    @staticmethod
    def _link(node: Tag, class_name: str, href_fragment: str) -> str:
        link = node.select_one(f"a.{class_name}") or node.select_one(f'a[href*="{href_fragment}"]')
        return str(link.get("href", "")) if link else ""

    @staticmethod
    def _page_date(soup: BeautifulSoup) -> str:
        date_node = soup.select_one(".header-date")
        if date_node:
            match = DATE_RE.search(date_node.get_text(" ", strip=True))
            if match:
                return match.group(0)
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        match = DATE_RE.search(title)
        return match.group(0) if match else ""
