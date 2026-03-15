# Copyright (c) Nex-AGI. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import time
from typing import Any

import requests

from nexau.archs.main_sub.agent_context import GlobalStorage
from nexdr.agents.deep_research.update_search_resources import update_search_resources
from nexdr.agents.tool_types import create_error_tool_result
from nexdr.agents.tool_types import create_success_tool_result


class SemanticScholarSearch:
    """Semantic Scholar Graph API paper search."""

    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    fields = (
        "title,url,abstract,year,authors,venue,citationCount,paperId,openAccessPdf"
    )

    def __init__(self, timeout: float = 30.0, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()

    def search(self, query: str, num_results: int = 10) -> list[dict[str, Any]] | str:
        if not query.strip():
            return "Query is empty."
        limit = max(1, min(num_results, 100))
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        params = {
            "query": query.strip(),
            "limit": limit,
            "fields": self.fields,
        }

        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    self.base_url,
                    headers=headers,
                    params=params,
                    timeout=self.timeout,
                )
                if response.status_code == 429:
                    if attempt == self.max_retries - 1:
                        return "Semantic Scholar API rate limit exceeded."
                    time.sleep(2**attempt)
                    continue
                response.raise_for_status()
                data = response.json().get("data", [])
                return self._normalize(data, limit)
            except requests.RequestException as exc:
                if attempt == self.max_retries - 1:
                    return f"Semantic Scholar request failed: {exc}"
                time.sleep(2**attempt)
        return "Semantic Scholar search failed unexpectedly."

    def _normalize(
        self, papers: list[dict[str, Any]], max_results: int
    ) -> list[dict[str, Any]]:
        normalized = []
        for paper in papers:
            paper_id = paper.get("paperId")
            link = (
                paper.get("url")
                or paper.get("openAccessPdf", {}).get("url")
                or (
                    f"https://www.semanticscholar.org/paper/{paper_id}"
                    if paper_id
                    else None
                )
            )
            if not link:
                continue

            title = paper.get("title") or "Untitled"
            snippet = (paper.get("abstract") or "").strip()
            if len(snippet) > 500:
                snippet = snippet[:500].rstrip() + "..."
            if not snippet:
                authors = [a.get("name", "") for a in paper.get("authors", [])]
                author_text = ", ".join([a for a in authors if a][:3])
                venue = paper.get("venue") or ""
                year = paper.get("year")
                citation_count = paper.get("citationCount")
                pieces = []
                if author_text:
                    pieces.append(f"Authors: {author_text}")
                if venue:
                    pieces.append(f"Venue: {venue}")
                if year:
                    pieces.append(f"Year: {year}")
                if citation_count is not None:
                    pieces.append(f"Citations: {citation_count}")
                snippet = " | ".join(pieces) if pieces else "No abstract available."

            normalized.append(
                {
                    "title": title,
                    "link": link,
                    "snippet": snippet,
                }
            )
            if len(normalized) >= max_results:
                break
        return normalized


def semantic_scholar_search(
    query: str,
    num_results: int = 10,
    global_storage: GlobalStorage = None,
):
    searcher = SemanticScholarSearch()
    results = searcher.search(query, num_results)
    if isinstance(results, list):
        results = update_search_resources(results, global_storage)
        data = {"semantic_scholar_search_result": results}
        message = "Successfully searched Semantic Scholar"
        return create_success_tool_result(
            data=data,
            message=message,
            tool_name="semantic_scholar_search",
        )
    return create_error_tool_result(
        error=results,
        message="Failed to search Semantic Scholar",
        tool_name="semantic_scholar_search",
    )
