import json
import discord

from github_client import GitHubClient
from ollama_client import OllamaClient

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_file_tree",
            "description": "List all files in the repository. Call this first to understand the structure.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_content",
            "description": "Read the full content of a file by path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to repo root"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search for a keyword or pattern across the repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term or symbol name"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_pull_requests",
            "description": "List open (or closed) pull requests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "description": "Filter by PR state. Defaults to open.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pull_request",
            "description": "Get full details and file diffs for a specific pull request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pr_number": {"type": "integer", "description": "Pull request number"}
                },
                "required": ["pr_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "post_pr_review",
            "description": "Post a review comment on a pull request (does not approve or reject).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pr_number": {"type": "integer"},
                    "body": {"type": "string", "description": "Markdown review body"},
                },
                "required": ["pr_number", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_pull_request",
            "description": (
                "Create a branch with file changes and open a pull request. "
                "Always read the relevant existing files first so your changes are accurate."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string", "description": "PR description in markdown"},
                    "branch": {
                        "type": "string",
                        "description": "New branch name in kebab-case (e.g. 'feat/add-dark-mode')",
                    },
                    "base": {
                        "type": "string",
                        "description": "Base branch to merge into (e.g. 'main')",
                    },
                    "file_changes": {
                        "type": "object",
                        "description": "Map of file path -> complete new file content",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["title", "body", "branch", "base", "file_changes"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "You are a GitHub assistant bot operating on a single repository. "
    "You have tools to read the file tree, read file contents, search code, "
    "list and inspect pull requests, post PR reviews, and create new PRs with code changes.\n\n"
    "Guidelines:\n"
    "- Always call get_file_tree first to orient yourself unless the task is purely PR-focused.\n"
    "- Read relevant files before generating code or answering architecture questions.\n"
    "- When creating a PR, read the files you intend to modify first, then produce complete, "
    "correct file contents (not partial diffs).\n"
    "- Keep your final response concise and well-formatted with markdown.\n"
    "- Use code blocks with language tags in responses.\n"
    "- If you post a PR review, also summarize what you posted in your reply."
)

MAX_TOOL_CALLS = 15


async def handle_message(
    message: discord.Message,
    content: str,
    github: GitHubClient,
    ollama: OllamaClient,
) -> None:
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]

    for _ in range(MAX_TOOL_CALLS):
        try:
            response = await ollama.chat(messages, tools=TOOLS)
        except Exception as e:
            await message.reply(f"LLM error: {e}")
            return

        if response.get("tool_calls"):
            tool_results = []
            for tc in response["tool_calls"]:
                result = _execute_tool(tc["function"]["name"], tc["function"]["arguments"], github)
                tool_results.append(
                    {"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(result)}
                )

            messages.append({"role": "assistant", "tool_calls": response["tool_calls"]})
            messages.extend(tool_results)
        else:
            await _send_chunked(message, response.get("content") or "Done.")
            return

    await message.reply("Reached the tool call limit. Try a more focused request.")


def _execute_tool(name: str, args: str | dict, github: GitHubClient) -> dict:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}

    try:
        if name == "get_file_tree":
            return {"files": github.get_file_tree()}

        if name == "get_file_content":
            content = github.get_file_content(args["path"])
            return {"content": content} if content is not None else {"error": "File not found"}

        if name == "search_code":
            return {"results": github.search_code(args["query"])}

        if name == "list_pull_requests":
            state = args.get("state", "open")
            return {"pull_requests": github.list_pull_requests(state)}

        if name == "get_pull_request":
            return github.get_pr(int(args["pr_number"]))

        if name == "post_pr_review":
            github.post_pr_review(int(args["pr_number"]), args["body"])
            return {"success": True}

        if name == "create_pull_request":
            pr = github.create_pr(
                title=args["title"],
                body=args["body"],
                branch=args["branch"],
                base=args["base"],
                file_changes=args["file_changes"],
            )
            return {"success": True, "url": pr.html_url, "number": pr.number}

        return {"error": f"unknown tool: {name}"}

    except Exception as e:
        return {"error": str(e)}


async def _send_chunked(message: discord.Message, text: str) -> None:
    limit = 1900
    if len(text) <= limit:
        await message.reply(text)
        return

    chunks: list[str] = []
    while len(text) > limit:
        split = text[:limit].rfind("\n")
        if split == -1:
            split = limit
        chunks.append(text[:split])
        text = text[split:].lstrip()
    if text:
        chunks.append(text)

    await message.reply(chunks[0])
    for chunk in chunks[1:]:
        await message.channel.send(chunk)
