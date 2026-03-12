import base64
import os
import sys

from dotenv import load_dotenv
from httpx import AsyncClient

load_dotenv()

_token = os.environ.get("GITHUB_ACCESS_TOKEN")

if not _token or _token.strip() == "":
    print(
        "\n"
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║  ERROR: GITHUB_ACCESS_TOKEN is not set.                      ║\n"
        "║                                                              ║\n"
        "║  1. Create a PAT at https://github.com/settings/tokens       ║\n"
        "║     (needs 'repo' and 'read:org' scopes)                     ║\n"
        "║  2. Add it to api/.env:                                      ║\n"
        '║       GITHUB_ACCESS_TOKEN="ghp_..."                          ║\n'
        "║  3. Restart the server.                                      ║\n"
        "╚══════════════════════════════════════════════════════════════╝\n",
        file=sys.stderr,
    )
    sys.exit(1)

_BASE_URL = "https://api.github.com"
_headers = {
    "Authorization": f"Bearer {_token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


async def _client() -> AsyncClient:
    return AsyncClient(base_url=_BASE_URL, headers=_headers, timeout=15)


async def search_repos(query: str, per_page: int = 10) -> list[dict]:
    """Search GitHub repositories by query string."""
    async with await _client() as client:
        resp = await client.get(
            "/search/repositories",
            params={"q": query, "per_page": per_page, "sort": "stars", "order": "desc"},
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [
            {
                "full_name": r["full_name"],
                "description": r.get("description"),
                "url": r["html_url"],
                "stars": r["stargazers_count"],
                "language": r.get("language"),
            }
            for r in items
        ]


async def search_files(
    owner: str, repo: str, query: str, per_page: int = 10
) -> list[dict]:
    """Search for files within a specific repository."""
    async with await _client() as client:
        resp = await client.get(
            "/search/code",
            params={"q": f"{query} repo:{owner}/{repo}", "per_page": per_page},
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [
            {
                "name": f["name"],
                "path": f["path"],
                "url": f["html_url"],
            }
            for f in items
        ]


async def get_file_content(owner: str, repo: str, path: str, ref: str = "main") -> dict:
    """Read the contents of a single file from a repository."""
    async with await _client() as client:
        resp = await client.get(
            f"/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref},
        )
        resp.raise_for_status()
        data = resp.json()

        content = ""
        if data.get("encoding") == "base64" and data.get("content"):
            content = base64.b64decode(data["content"]).decode("utf-8")

        return {
            "name": data["name"],
            "path": data["path"],
            "size": data["size"],
            "content": content,
            "url": data["html_url"],
        }
