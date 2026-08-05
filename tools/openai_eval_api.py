"""Minimal OpenAI REST client and Responses API parsing for skill evaluations."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import random
import re
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable

DEFAULT_API_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5.5-2026-04-23"
RETRY_STATUSES = {408, 409, 429, 500, 502, 503, 504}
SKILL_READ = re.compile(
    r"(?i)(?:^|[;&|]\s*|\b)(?:cat|head|tail|sed|grep|rg|awk|less|more|type|get-content|python\S*)\b[^\n]*\bskill\.md\b"
)


class ApiError(RuntimeError):
    """Raised when an OpenAI API operation fails."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise ApiError("OPENAI_API_KEY is required only with --execute; do not pass keys on the command line")
    return key


def encode_multipart(field: str, path: Path) -> tuple[bytes, str]:
    boundary = f"----openai-skill-eval-{uuid.uuid4().hex}"
    filename = path.name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8")
    suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
    return prefix + path.read_bytes() + suffix, f"multipart/form-data; boundary={boundary}"


class OpenAIHttpClient:
    """Standard-library OpenAI REST client with bounded transient retries."""

    def __init__(
        self,
        api_key: str,
        api_base: str = DEFAULT_API_BASE,
        timeout: float = 300.0,
        max_retries: int = 4,
        opener: Callable[..., Any] = urllib.request.urlopen,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.opener = opener
        self.sleeper = sleeper

    def _headers(self, content_type: str) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": content_type,
            "Accept": "application/json",
            "User-Agent": "octoteo-skills-evaluator/1",
        }
        project = os.environ.get("OPENAI_PROJECT_ID", "").strip()
        organization = os.environ.get("OPENAI_ORG_ID", "").strip()
        if project:
            headers["OpenAI-Project"] = project
        if organization:
            headers["OpenAI-Organization"] = organization
        return headers

    def request(self, method: str, path: str, body: bytes, content_type: str) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.api_base}{path}",
            data=body,
            headers=self._headers(content_type),
            method=method,
        )
        for attempt in range(self.max_retries + 1):
            try:
                with self.opener(request, timeout=self.timeout) as response:
                    payload = response.read()
                    data = json.loads(payload.decode("utf-8")) if payload else {}
                    if not isinstance(data, dict):
                        raise ApiError("OpenAI API returned a non-object JSON response")
                    return data
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:4000]
                if exc.code in RETRY_STATUSES and attempt < self.max_retries:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    try:
                        delay = float(retry_after) if retry_after else min(2**attempt + random.random(), 20.0)
                    except ValueError:
                        delay = min(2**attempt + random.random(), 20.0)
                    self.sleeper(max(0.0, delay))
                    continue
                raise ApiError(f"OpenAI API HTTP {exc.code}: {detail}") from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                if attempt < self.max_retries:
                    self.sleeper(min(2**attempt + random.random(), 20.0))
                    continue
                raise ApiError(f"OpenAI API request failed: {exc}") from exc
        raise ApiError("OpenAI API retry loop exited unexpectedly")

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", path, json.dumps(payload).encode("utf-8"), "application/json")

    def post_zip(self, path: str, package: Path) -> dict[str, Any]:
        body, content_type = encode_multipart("files", package)
        return self.request("POST", path, body, content_type)


def extract_output_text(response: dict[str, Any]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    parts: list[str] = []
    output = response.get("output", [])
    if not isinstance(output, list):
        return ""
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content", [])
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") in {"output_text", "text"}:
                text = part.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
    return "\n".join(parts).strip()


def extract_shell_commands(response: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    output = response.get("output", [])
    if not isinstance(output, list):
        return commands
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "shell_call":
            continue
        action = item.get("action", {})
        if not isinstance(action, dict):
            continue
        value = action.get("commands", [])
        if isinstance(value, str):
            commands.append(value)
        elif isinstance(value, list):
            commands.extend(command for command in value if isinstance(command, str))
    return commands


def activation_evidence(commands: Iterable[str], skill_name: str) -> list[str]:
    evidence: list[str] = []
    skill_marker = skill_name.casefold()
    for command in commands:
        lowered = command.casefold()
        reads_manifest = bool(SKILL_READ.search(command))
        reads_skill_resource = skill_marker in lowered and any(
            marker in lowered for marker in ("skill.md", "references/", "scripts/")
        )
        if reads_manifest or reads_skill_resource:
            evidence.append(command)
    return evidence


def build_response_payload(
    model: str,
    prompt: str,
    skill_id: str | None,
    skill_version: int | str | None,
    reasoning_effort: str,
    max_output_tokens: int,
) -> dict[str, Any]:
    environment: dict[str, Any] = {"type": "container_auto"}
    if skill_id:
        reference: dict[str, Any] = {"type": "skill_reference", "skill_id": skill_id}
        if skill_version is not None:
            reference["version"] = skill_version
        environment["skills"] = [reference]
    return {
        "model": model,
        "input": prompt,
        "reasoning": {"effort": reasoning_effort},
        "max_output_tokens": max_output_tokens,
        "tools": [{"type": "shell", "environment": environment}],
    }
