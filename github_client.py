import os
import base64
import time

from github import Github, GithubIntegration
from github.GithubException import GithubException


class GitHubClient:
    _TOKEN_LIFETIME = 3300  # refresh 5 min before the 1-hour expiry

    def __init__(self):
        self._app_id = int(os.environ["GITHUB_APP_ID"])
        with open(os.environ["GITHUB_APP_PRIVATE_KEY_PATH"]) as f:
            self._private_key = f.read()
        self._installation_id = int(os.environ["GITHUB_INSTALLATION_ID"])
        self._repo_full_name = os.environ["GITHUB_REPO"]
        self._token_created_at = 0.0
        self._refresh_token()

    def _refresh_token(self):
        integration = GithubIntegration(self._app_id, self._private_key)
        token = integration.get_access_token(self._installation_id)
        self._gh = Github(token.token)
        self._repo = self._gh.get_repo(self._repo_full_name)
        self.owner, self.repo_name = self._repo_full_name.split("/", 1)
        self._token_created_at = time.monotonic()

    def _ensure_token(self):
        if time.monotonic() - self._token_created_at > self._TOKEN_LIFETIME:
            self._refresh_token()

    # -- read operations --

    def get_file_tree(self, max_files: int = 300) -> list[str]:
        self._ensure_token()
        try:
            tree = self._repo.get_git_tree("HEAD", recursive=True)
            return [item.path for item in tree.tree if item.type == "blob"][:max_files]
        except GithubException as e:
            return [f"error: {e}"]

    def get_file_content(self, path: str) -> str | None:
        self._ensure_token()
        try:
            obj = self._repo.get_contents(path)
            if isinstance(obj, list):
                return None  # path is a directory
            raw = base64.b64decode(obj.content)
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return f"[binary file, {len(raw)} bytes]"
        except GithubException:
            return None

    def get_default_branch(self) -> str:
        self._ensure_token()
        return self._repo.default_branch

    def list_pull_requests(self, state: str = "open") -> list[dict]:
        self._ensure_token()
        prs = self._repo.get_pulls(state=state, sort="updated", direction="desc")
        return [
            {"number": pr.number, "title": pr.title, "state": pr.state, "url": pr.html_url}
            for pr in list(prs)[:20]
        ]

    def get_pr(self, pr_number: int) -> dict:
        self._ensure_token()
        pr = self._repo.get_pull(pr_number)
        files = list(pr.get_files())
        return {
            "number": pr.number,
            "title": pr.title,
            "body": pr.body or "",
            "state": pr.state,
            "url": pr.html_url,
            "head_branch": pr.head.ref,
            "base_branch": pr.base.ref,
            "files": [
                {
                    "filename": f.filename,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "patch": (f.patch or "")[:4000],  # cap patch size per file
                }
                for f in files
            ],
        }

    def search_code(self, query: str) -> list[dict]:
        self._ensure_token()
        try:
            results = self._gh.search_code(f"{query} repo:{self.owner}/{self.repo_name}")
            return [{"path": r.path, "url": r.html_url} for r in list(results)[:15]]
        except GithubException as e:
            return [{"error": str(e)}]

    # -- write operations --

    def create_pr(
        self,
        title: str,
        body: str,
        branch: str,
        base: str,
        file_changes: dict[str, str],
    ):
        self._ensure_token()
        base_sha = self._repo.get_branch(base).commit.sha
        self._repo.create_git_ref(f"refs/heads/{branch}", base_sha)

        for path, content in file_changes.items():
            try:
                existing = self._repo.get_contents(path, ref=branch)
                self._repo.update_file(
                    path, f"Update {path}", content, existing.sha, branch=branch
                )
            except GithubException:
                self._repo.create_file(path, f"Add {path}", content, branch=branch)

        return self._repo.create_pull(title=title, body=body, head=branch, base=base)

    def post_pr_review(self, pr_number: int, body: str) -> None:
        self._ensure_token()
        pr = self._repo.get_pull(pr_number)
        pr.create_review(body=body, event="COMMENT")
