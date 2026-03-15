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

from nexdr.agents.deep_research.semantic_scholar_search import semantic_scholar_search
from nexau.archs.main_sub.agent_context import GlobalStorage
from nexdr.agents.tool_types import create_error_tool_result


def web_search(
    query: str,
    search_type: str = "search",
    num_results: int = 10,
    global_storage: GlobalStorage = None,
):
    # Compatibility wrapper: legacy "web" source is redirected to Semantic Scholar.
    if search_type != "search":
        return create_error_tool_result(
            error=(
                "Only search_type='search' is supported in Task2 web mode. "
                "For images/news/places, use other specialized tools."
            ),
            message="Failed to search web",
            tool_name="web_search",
        )
    return semantic_scholar_search(
        query=query,
        num_results=num_results,
        global_storage=global_storage,
    )
