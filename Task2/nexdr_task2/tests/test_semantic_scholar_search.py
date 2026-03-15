from unittest.mock import Mock
from unittest.mock import patch

from nexdr.agents.deep_research.semantic_scholar_search import SemanticScholarSearch


@patch("nexdr.agents.deep_research.semantic_scholar_search.requests.get")
def test_semantic_scholar_search_mapping(mock_get):
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [
            {
                "paperId": "abc",
                "title": "Paper A",
                "url": "https://example.com/a",
                "abstract": "This is abstract.",
            }
        ]
    }
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    client = SemanticScholarSearch()
    results = client.search("test", num_results=3)

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["title"] == "Paper A"
    assert results[0]["link"] == "https://example.com/a"
    assert "abstract" in results[0]["snippet"].lower()
