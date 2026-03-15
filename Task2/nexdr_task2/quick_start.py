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

"""Quick start for Task2: markdown-only generation and revision workflow."""

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import dotenv

from nexau.archs.config.config_loader import load_agent_config
from nexau.archs.main_sub.agent_context import GlobalStorage
from nexdr.agents.doc_reader.doc_preprocess import doc_preprocess_function
from nexdr.utils.markdown_diff import build_change_summary_text
from nexdr.utils.markdown_diff import build_unified_diff
from nexdr.utils.markdown_diff import summarize_markdown_changes
from nexdr.utils.update_citation import update_citations


SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR / ".env"
dotenv.load_dotenv(dotenv_path=ENV_PATH, override=False)

logger = logging.getLogger()

PROFILE_SETTINGS: dict[str, dict] = {
    "micro": {
        "research_config": None,
        "report_config": "configs/markdown_report_writer/report_writer_lite.yaml",
        "reviser_config": "configs/markdown_reviser/reviser_lite.yaml",
        "default_history_limit": 0,
        "compact_reviser_prompt": True,
        "skip_research": True,
    },
    "lite": {
        "research_config": "configs/deep_research/deep_research_lite.yaml",
        "report_config": "configs/markdown_report_writer/report_writer_lite.yaml",
        "reviser_config": "configs/markdown_reviser/reviser_lite.yaml",
        "default_history_limit": 12,
        "compact_reviser_prompt": True,
        "skip_research": False,
    },
    "full": {
        "research_config": "configs/deep_research/deep_research.yaml",
        "report_config": "configs/markdown_report_writer/report_writer.yaml",
        "reviser_config": "configs/markdown_reviser/reviser.yaml",
        "default_history_limit": 120,
        "compact_reviser_prompt": False,
        "skip_research": False,
    },
}


def get_profile_settings(profile: str) -> dict:
    if profile not in PROFILE_SETTINGS:
        raise ValueError(f"Unsupported profile: {profile}")
    return PROFILE_SETTINGS[profile]


def _first_non_empty_env_var(names: list[str]) -> str | None:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None


def _normalize_llm_env_aliases() -> None:
    alias_pairs = [
        ("LLM_MODEL", "MODEL"),
        ("LLM_BASE_URL", "OPENAI_BASE_URL"),
        ("LLM_API_KEY", "OPENAI_API_KEY"),
    ]
    for source, target in alias_pairs:
        source_value = os.getenv(source, "").strip()
        target_value = os.getenv(target, "").strip()
        if source_value and not target_value:
            os.environ[target] = source_value


def _ensure_llm_env_ready() -> None:
    model = _first_non_empty_env_var(["MODEL", "OPENAI_MODEL", "LLM_MODEL"])
    base_url = _first_non_empty_env_var(["OPENAI_BASE_URL", "BASE_URL", "LLM_BASE_URL"])
    api_key = _first_non_empty_env_var(
        ["LLM_API_KEY", "OPENAI_API_KEY", "API_KEY", "ANTHROPIC_API_KEY"]
    )
    missing: list[str] = []
    if not model:
        missing.append("LLM_MODEL")
    if not base_url:
        missing.append("LLM_BASE_URL")
    if not api_key:
        missing.append("LLM_API_KEY")

    if missing:
        env_location = str(ENV_PATH)
        missing_str = ", ".join(missing)
        raise ValueError(
            "LLM environment variables are missing: "
            f"{missing_str}. Please set them in {env_location}, then rerun."
        )

    if base_url and not (
        base_url.startswith("http://") or base_url.startswith("https://")
    ):
        raise ValueError(
            "LLM_BASE_URL is invalid. It must start with http:// or https://, "
            f"but got: {base_url!r}"
        )

    if api_key and (
        api_key.startswith("http://")
        or api_key.startswith("https://")
        or api_key.startswith("localhost")
    ):
        raise ValueError(
            "LLM_API_KEY looks like a URL. You may have swapped LLM_API_KEY and "
            "LLM_BASE_URL in .env."
        )


def get_date() -> str:
    return datetime.now().strftime("%Y-%m-%d-%H-%M-%S")


now_date = get_date()


def setup_logger(workspace: str) -> None:
    logger.setLevel(logging.INFO)
    if logger.handlers:
        logger.handlers.clear()

    file_handler = logging.FileHandler(
        os.path.join(workspace, f"logs_{now_date}.log"), encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


def _load_agent(config_path: str, global_storage: GlobalStorage):
    return load_agent_config(config_path, global_storage=global_storage)


def _abs_config_path(relative_path: str) -> str:
    return str(SCRIPT_DIR / relative_path)


def _truncate_history(messages: list[dict], max_messages: int) -> list[dict]:
    if max_messages == 0:
        return []
    if max_messages < 0 or len(messages) <= max_messages:
        return messages
    return messages[-max_messages:]


def _collect_deep_research_trace_history(global_storage: GlobalStorage) -> list[dict]:
    keys = global_storage.keys()
    all_messages: list[dict] = []
    for key in keys:
        if key.startswith("deep_research_agent") and key.endswith("messages"):
            messages = global_storage.get(key, [])
            if isinstance(messages, list):
                all_messages.extend(messages[1:])  # index-0 is system message
    return all_messages


def research_agent_run(
    query: str,
    context: dict,
    global_storage: GlobalStorage,
    research_config_path: str,
) -> list[dict]:
    agent = _load_agent(research_config_path, global_storage)
    agent.run(query, context=context)
    return _collect_deep_research_trace_history(global_storage)


def markdown_report_agent_run(
    deep_research_trace_history: list[dict],
    context: dict,
    global_storage: GlobalStorage,
    report_config_path: str,
) -> tuple[str, dict]:
    agent = _load_agent(report_config_path, global_storage)
    message = "Please write a markdown report based on the research result."
    response = agent.run(message, history=deep_research_trace_history, context=context)
    report_content, citations = update_citations(response, global_storage)
    return report_content, citations


def markdown_report_direct_run(
    query: str,
    context: dict,
    global_storage: GlobalStorage,
    report_config_path: str,
) -> tuple[str, dict]:
    agent = _load_agent(report_config_path, global_storage)
    message = (
        "Write a concise markdown report directly from the user query.\n"
        "Keep it practical and avoid unnecessary elaboration.\n"
        "If evidence is limited, clearly mark assumptions.\n\n"
        f"<user_query>\n{query}\n</user_query>\n"
    )
    response = agent.run(message, context=context)
    report_content, citations = update_citations(response, global_storage)
    return report_content, citations


def markdown_reviser_agent_run(
    *,
    user_query: str,
    original_markdown: str,
    edited_markdown: str,
    diff_patch: str,
    diff_summary_text: str,
    deep_research_trace_history: list[dict],
    context: dict,
    global_storage: GlobalStorage,
    reviser_config_path: str,
    compact_prompt: bool,
) -> tuple[str, dict]:
    agent = _load_agent(reviser_config_path, global_storage)
    if compact_prompt:
        message = (
            "Please polish the user edited markdown and keep citation quality.\n\n"
            "<user_query>\n"
            f"{user_query}\n"
            "</user_query>\n\n"
            "<change_summary>\n"
            f"{diff_summary_text}\n"
            "</change_summary>\n\n"
            "<user_edited_markdown>\n"
            f"{edited_markdown}\n"
            "</user_edited_markdown>\n"
        )
    else:
        message = (
            "Please revise the markdown report based on user edits and keep citation quality.\n\n"
            "<user_query>\n"
            f"{user_query}\n"
            "</user_query>\n\n"
            "<change_summary>\n"
            f"{diff_summary_text}\n"
            "</change_summary>\n\n"
            "<original_markdown>\n"
            f"{original_markdown}\n"
            "</original_markdown>\n\n"
            "<user_edited_markdown>\n"
            f"{edited_markdown}\n"
            "</user_edited_markdown>\n\n"
            "<unified_diff_patch>\n"
            f"{diff_patch}\n"
            "</unified_diff_patch>\n"
        )
    response = agent.run(message, history=deep_research_trace_history, context=context)
    report_content, citations = update_citations(response, global_storage)
    return report_content, citations


def _resolve_input_path(input_path: str, workspace: str) -> str:
    candidate = Path(input_path)
    if candidate.is_absolute():
        return str(candidate)
    workspace_candidate = Path(workspace) / input_path
    if workspace_candidate.exists():
        return str(workspace_candidate.resolve())
    return str((Path.cwd() / input_path).resolve())


def preprocess_input_files(
    input_files: list[str],
    global_storage: GlobalStorage,
) -> list[dict]:
    if not input_files:
        return []
    workspace = global_storage.get("workspace", os.getcwd())
    docs = []
    for file_path in input_files:
        resolved = _resolve_input_path(file_path, workspace)
        success, result = doc_preprocess_function(resolved, global_storage)
        docs.append(
            {
                "input": file_path,
                "resolved_path": resolved,
                "success": success,
                "result": result,
            }
        )
    return docs


def build_query_with_inputs(query: str, preprocessed_docs: list[dict]) -> str:
    if not preprocessed_docs:
        return query
    lines = [
        query.strip(),
        "",
        "Additional local materials are available. Please read these materials with agent:VisitPage before writing conclusions.",
    ]
    for doc in preprocessed_docs:
        result = doc.get("result", {})
        doc_id = result.get("doc_id")
        link = result.get("link")
        status = "success" if doc.get("success") else "failed"
        lines.append(f"- doc_id={doc_id}, path={link}, status={status}")
    return "\n".join(lines).strip()


def write_generation_artifacts(
    workspace: str, report_content: str, citations: dict
) -> dict[str, str]:
    original_path = os.path.join(workspace, "markdown_report.original.md")
    report_path = os.path.join(workspace, "markdown_report.md")
    citation_path = os.path.join(workspace, "citations.json")

    with open(original_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    with open(citation_path, "w", encoding="utf-8") as f:
        json.dump(citations, f, ensure_ascii=False, indent=2)
    return {
        "markdown_report_original_path": original_path,
        "markdown_report_path": report_path,
        "citation_path": citation_path,
    }


def write_revision_artifacts(
    workspace: str,
    user_edited_content: str,
    diff_patch: str,
    diff_summary: dict,
    revised_content: str,
    citations: dict,
) -> dict[str, str]:
    user_edited_path = os.path.join(workspace, "markdown_report.user_edited.md")
    patch_path = os.path.join(workspace, "markdown_diff.patch")
    summary_path = os.path.join(workspace, "markdown_diff_summary.json")
    revised_path = os.path.join(workspace, "markdown_report.revised.md")
    report_path = os.path.join(workspace, "markdown_report.md")
    citation_path = os.path.join(workspace, "citations.json")

    with open(user_edited_path, "w", encoding="utf-8") as f:
        f.write(user_edited_content)
    with open(patch_path, "w", encoding="utf-8") as f:
        f.write(diff_patch)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(diff_summary, f, ensure_ascii=False, indent=2)
    with open(revised_path, "w", encoding="utf-8") as f:
        f.write(revised_content)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(revised_content)
    with open(citation_path, "w", encoding="utf-8") as f:
        json.dump(citations, f, ensure_ascii=False, indent=2)

    return {
        "markdown_report_user_edited_path": user_edited_path,
        "markdown_diff_patch_path": patch_path,
        "markdown_diff_summary_path": summary_path,
        "markdown_report_revised_path": revised_path,
        "markdown_report_path": report_path,
        "citation_path": citation_path,
    }


def load_previous_state(workspace: str, global_storage: GlobalStorage) -> dict:
    final_state_path = os.path.join(workspace, "final_state.json")
    if not os.path.exists(final_state_path):
        return {}
    with open(final_state_path, "r", encoding="utf-8") as f:
        state = json.load(f)
    for key in ("resources", "date", "request_id"):
        if key in state:
            global_storage.set(key, state[key])
    return state


def write_final_state(
    workspace: str,
    start_time: datetime,
    artifacts: dict,
    global_storage: GlobalStorage,
    extra: dict | None = None,
) -> str:
    final_state = {"artifacts": artifacts}
    if extra:
        final_state.update(extra)
    for key, value in global_storage.items():
        try:
            json.dumps(value)
            final_state[key] = value
        except (TypeError, ValueError):
            continue
    end_time = datetime.now()
    final_state["start_time"] = start_time.isoformat()
    final_state["end_time"] = end_time.isoformat()
    final_state["used_time"] = (end_time - start_time).total_seconds()
    final_state_path = os.path.join(workspace, "final_state.json")
    with open(final_state_path, "w", encoding="utf-8") as f:
        json.dump(final_state, f, ensure_ascii=False, indent=4)
    logger.info("Final state is saved at: %s", final_state_path)
    return final_state_path


def agent_generate(
    query: str,
    output_dir: str,
    input_files: list[str],
    profile: str,
    history_limit: int,
) -> None:
    start_time = datetime.now()
    request_id = f"request_{now_date}"
    workspace = os.path.abspath(output_dir)
    os.makedirs(workspace, exist_ok=True)

    global_storage = GlobalStorage()
    global_storage.set("request_id", request_id)
    global_storage.set("workspace", workspace)
    global_storage.set("date", now_date)
    context = {"date": now_date, "request_id": request_id, "workspace": workspace}

    profile_settings = get_profile_settings(profile)
    resolved_history_limit = (
        history_limit
        if history_limit > 0
        else int(profile_settings["default_history_limit"])
    )
    preprocessed_docs = preprocess_input_files(input_files, global_storage)
    full_query = build_query_with_inputs(query, preprocessed_docs)
    skip_research = bool(profile_settings.get("skip_research", False))
    if skip_research:
        deep_research_trace_history = []
        trimmed_history = []
        report_content, citations = markdown_report_direct_run(
            query=full_query,
            context=context,
            global_storage=global_storage,
            report_config_path=_abs_config_path(profile_settings["report_config"]),
        )
    else:
        deep_research_trace_history = research_agent_run(
            full_query,
            context,
            global_storage,
            research_config_path=_abs_config_path(profile_settings["research_config"]),
        )
        trimmed_history = _truncate_history(
            deep_research_trace_history, resolved_history_limit
        )
        report_content, citations = markdown_report_agent_run(
            trimmed_history,
            context,
            global_storage,
            report_config_path=_abs_config_path(profile_settings["report_config"]),
        )
    artifacts = write_generation_artifacts(workspace, report_content, citations)
    logger.info("Generate mode artifacts: %s", artifacts)

    write_final_state(
        workspace=workspace,
        start_time=start_time,
        artifacts=artifacts,
        global_storage=global_storage,
        extra={
            "mode": "generate",
            "query": query,
            "query_with_inputs": full_query,
            "input_files": input_files,
            "preprocessed_docs": preprocessed_docs,
            "profile": profile,
            "history_limit": resolved_history_limit,
            "history_messages_total": len(deep_research_trace_history),
            "history_messages_used": len(trimmed_history),
        },
    )


def agent_revise(
    query: str,
    output_dir: str,
    edited_markdown_path: str,
    profile: str,
    history_limit: int,
    reuse_research_history: bool,
) -> None:
    start_time = datetime.now()
    request_id = f"revise_{now_date}"
    workspace = os.path.abspath(output_dir)
    if not os.path.exists(workspace):
        raise ValueError(f"Output workspace does not exist: {workspace}")

    global_storage = GlobalStorage()
    global_storage.set("request_id", request_id)
    global_storage.set("workspace", workspace)
    global_storage.set("date", now_date)
    context = {"date": now_date, "request_id": request_id, "workspace": workspace}

    profile_settings = get_profile_settings(profile)
    resolved_history_limit = (
        history_limit
        if history_limit > 0
        else int(profile_settings["default_history_limit"])
    )
    previous_state = load_previous_state(workspace, global_storage)
    if reuse_research_history:
        for key, value in previous_state.items():
            if key.startswith("deep_research_agent") and key.endswith("messages"):
                global_storage.set(key, value)
    deep_research_trace_history = _collect_deep_research_trace_history(global_storage)
    trimmed_history = _truncate_history(deep_research_trace_history, resolved_history_limit)

    original_path = os.path.join(workspace, "markdown_report.original.md")
    if not os.path.exists(original_path):
        fallback = os.path.join(workspace, "markdown_report.md")
        if not os.path.exists(fallback):
            raise ValueError(
                "Original markdown report not found. Expected markdown_report.original.md or markdown_report.md"
            )
        original_path = fallback

    edited_path = _resolve_input_path(edited_markdown_path, workspace)
    if not os.path.exists(edited_path):
        raise ValueError(f"Edited markdown file not found: {edited_path}")

    with open(original_path, "r", encoding="utf-8") as f:
        original_content = f.read()
    with open(edited_path, "r", encoding="utf-8") as f:
        edited_content = f.read()

    diff_patch = build_unified_diff(original_content, edited_content)
    diff_summary = summarize_markdown_changes(original_content, edited_content)
    diff_summary_text = build_change_summary_text(diff_summary)

    revised_content, citations = markdown_reviser_agent_run(
        user_query=query or previous_state.get("query", ""),
        original_markdown=original_content,
        edited_markdown=edited_content,
        diff_patch=diff_patch,
        diff_summary_text=diff_summary_text,
        deep_research_trace_history=trimmed_history,
        context=context,
        global_storage=global_storage,
        reviser_config_path=_abs_config_path(profile_settings["reviser_config"]),
        compact_prompt=bool(profile_settings["compact_reviser_prompt"]),
    )

    artifacts = write_revision_artifacts(
        workspace=workspace,
        user_edited_content=edited_content,
        diff_patch=diff_patch,
        diff_summary=diff_summary,
        revised_content=revised_content,
        citations=citations,
    )
    logger.info("Revise mode artifacts: %s", artifacts)

    write_final_state(
        workspace=workspace,
        start_time=start_time,
        artifacts=artifacts,
        global_storage=global_storage,
        extra={
            "mode": "revise",
            "query": query or previous_state.get("query", ""),
            "edited_markdown_input_path": edited_path,
            "markdown_diff_summary_text": diff_summary_text,
            "profile": profile,
            "history_limit": resolved_history_limit,
            "reuse_research_history": reuse_research_history,
            "history_messages_total": len(deep_research_trace_history),
            "history_messages_used": len(trimmed_history),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Task2 quick start: markdown-only generate/revise workflow.",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="generate",
        choices=["generate", "revise"],
        help="Execution mode: generate or revise.",
    )
    parser.add_argument(
        "--query",
        type=str,
        default="",
        help="Research query. Required in generate mode.",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=f"workspaces/workspace_{now_date}",
        help="Workspace directory to save outputs.",
    )
    parser.add_argument(
        "--edited_markdown_path",
        type=str,
        default="",
        help="Edited markdown file path for revise mode.",
    )
    parser.add_argument(
        "--input_files",
        nargs="*",
        default=[],
        help="Optional local inputs (pdf/png/jpg/webp/md/txt/docx...) to preload.",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default="micro",
        choices=["micro", "lite", "full"],
        help="Execution profile. micro is cheapest; lite is balanced; full is deepest.",
    )
    parser.add_argument(
        "--history_limit",
        type=int,
        default=-1,
        help="Limit messages passed to writer/reviser (<=0 uses profile default).",
    )
    parser.add_argument(
        "--reuse_research_history",
        action="store_true",
        help="Reuse deep research history in revise mode (higher token cost).",
    )
    args = parser.parse_args()

    _normalize_llm_env_aliases()
    _ensure_llm_env_ready()

    os.makedirs(args.output_dir, exist_ok=True)
    setup_logger(args.output_dir)

    if args.mode == "generate":
        if not args.query.strip():
            parser.error("--query is required when --mode=generate")
        agent_generate(
            args.query,
            args.output_dir,
            args.input_files,
            args.profile,
            args.history_limit,
        )
    else:
        if not args.edited_markdown_path.strip():
            parser.error("--edited_markdown_path is required when --mode=revise")
        agent_revise(
            args.query,
            args.output_dir,
            args.edited_markdown_path,
            args.profile,
            args.history_limit,
            args.reuse_research_history,
        )


if __name__ == "__main__":
    main()
