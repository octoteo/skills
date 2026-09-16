#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import socket
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152.0 Safari/537.36"
VERIFY = (
    "wappoc_appmsgcaptcha", "环境异常", "操作频繁", "访问过于频繁",
    "完成验证后", "去验证", "environment anomaly", "environment abnormal",
)
TEXTOOLKIT = "https://textoolkit.com/wechat-to-markdown"
MPTEXT = "https://down.mptext.top/api/public/v1/download"


class FetchError(RuntimeError):
    pass


class VerificationRequired(FetchError):
    pass


@dataclass
class Article:
    source_url: str
    final_url: str
    method: str
    title: str | None
    markdown: str


def unwrap(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.lower() == "mp.weixin.qq.com" and "wappoc_appmsgcaptcha" in parsed.path:
        return urllib.parse.unquote(urllib.parse.parse_qs(parsed.query).get("target_url", [url])[0])
    return url


def validate(url: str) -> str:
    url = unwrap(url)
    parsed = urllib.parse.urlparse(url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.netloc.lower() != "mp.weixin.qq.com"
        or not (parsed.path == "/s" or parsed.path.startswith("/s/"))
    ):
        raise FetchError("Only public mp.weixin.qq.com/s article URLs are supported.")
    return url


def is_verify(text: str, url: str = "") -> bool:
    haystack = (text + "\n" + url).lower()
    return any(marker.lower() in haystack for marker in VERIFY)


def from_markdown(text: str, url: str, final: str, method: str) -> Article:
    text = text.strip()
    if is_verify(text, final):
        raise VerificationRequired(f"{method}: WeChat verification/rate-limit page")
    if len(re.sub(r"\s+", "", text)) < 80:
        raise FetchError(f"{method}: implausibly short response")
    match = re.search(r"(?m)^#\s+(.+)$", text)
    title = match.group(1).strip() if match else None
    return Article(url, final, method, title, text + "\n")


def from_html(html: str, url: str, final: str, method: str) -> Article:
    if is_verify(html, final):
        raise VerificationRequired(f"{method}: WeChat verification/rate-limit page")
    try:
        from bs4 import BeautifulSoup
        from markdownify import markdownify
    except ModuleNotFoundError as exc:
        raise FetchError("HTML conversion requires beautifulsoup4 and markdownify") from exc

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("#js_content")
    if not content:
        raise FetchError(f"{method}: missing #js_content")
    title_node = soup.select_one("#activity-name")
    title = title_node.get_text(" ", strip=True) if title_node else "Untitled WeChat article"
    for image in content.find_all("img"):
        src = image.get("data-src") or image.get("data-original") or image.get("src")
        if src:
            image["src"] = urllib.parse.urljoin(final, src)
        image["alt"] = image.get("alt") or "image"
    for node in content.select("script,style,noscript,iframe"):
        node.decompose()
    body = re.sub(r"\n{3,}", "\n\n", markdownify(str(content), heading_style="ATX")).strip()
    if len(re.sub(r"\s+", "", body)) < 30:
        raise FetchError(f"{method}: article body too short")
    markdown = f"# {title}\n\n- 原文：{url}\n\n{body}\n"
    return Article(url, final, method, title, markdown)


def request_text(url: str, timeout: int, params: dict[str, str] | None = None) -> tuple[str, str]:
    if params:
        query = urllib.parse.urlencode(params)
        url = f"{url}{'&' if '?' in url else '?'}{query}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://mp.weixin.qq.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            text = raw.decode(charset, errors="replace")
        except LookupError:
            text = raw.decode("utf-8", errors="replace")
        return text, response.geturl()


def direct(url: str, timeout: int) -> Article:
    text, final = request_text(url, timeout)
    return from_html(text, url, final, "direct")


def jina(url: str, timeout: int) -> Article:
    text, final = request_text("https://r.jina.ai/" + url, timeout)
    return from_markdown(text, url, final, "jina")


def mptext(url: str, timeout: int) -> Article:
    text, final = request_text(MPTEXT, timeout, {"url": url, "format": "markdown"})
    return from_markdown(text, url, final, "mptext")


def cdp_url() -> str | None:
    for port in range(9222, 9236):
        with socket.socket() as sock:
            sock.settimeout(0.1)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                continue
        try:
            request = urllib.request.Request(f"http://127.0.0.1:{port}/json/version")
            with urllib.request.urlopen(request, timeout=0.4) as response:
                if response.status == 200:
                    return f"http://127.0.0.1:{port}"
        except (OSError, urllib.error.URLError):
            continue
    return None


def headless_default() -> bool:
    return platform.system() == "Linux" and not (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))


def browser(
    url: str,
    timeout: int,
    headless: bool | None = None,
    manual_wait: int = 0,
    cdp: str | None = None,
) -> Article:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise FetchError("Playwright required for browser mode") from exc

    effective_headless = headless_default() if headless is None else headless
    with sync_playwright() as playwright:
        browser_instance = None
        context = None
        owns_context = False
        try:
            endpoint = cdp or cdp_url()
            if endpoint:
                browser_instance = playwright.chromium.connect_over_cdp(endpoint)
                context = browser_instance.contexts[0] if browser_instance.contexts else browser_instance.new_context()
                method = "browser-cdp"
            else:
                profile = Path.home() / ".wechat-article-markdown" / "chrome-profile"
                profile.mkdir(parents=True, exist_ok=True)
                context = playwright.chromium.launch_persistent_context(
                    str(profile), headless=effective_headless, locale="zh-CN"
                )
                owns_context = True
                method = "browser-persistent"

            page = next((item for item in context.pages if "mp.weixin.qq.com" in (item.url or "")), None)
            page = page or (context.pages[0] if context.pages else context.new_page())
            if page.url != url:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                except Exception:
                    pass

            deadline = time.monotonic() + max(5, min(timeout, 15))
            while time.monotonic() < deadline:
                if page.locator("#js_content").count():
                    return from_html(page.content(), url, page.url, method)
                time.sleep(0.5)

            body = page.locator("body").inner_text(timeout=2000) if page.locator("body").count() else ""
            if is_verify(body, page.url) and manual_wait > 0 and not effective_headless:
                deadline = time.monotonic() + manual_wait
                while time.monotonic() < deadline:
                    if page.locator("#js_content").count():
                        return from_html(page.content(), url, page.url, method + "+manual")
                    time.sleep(0.75)
            if is_verify(body, page.url):
                raise VerificationRequired(
                    "browser: complete verification in visible persistent browser, then retry"
                )
            raise FetchError("browser: article did not render")
        finally:
            if owns_context and context:
                try:
                    context.close()
                except Exception:
                    pass
            if browser_instance:
                try:
                    browser_instance.close()
                except Exception:
                    pass


def textoolkit(url: str, timeout: int, headless: bool | None = None) -> Article:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise FetchError("Playwright required for Textoolkit mode") from exc

    effective_headless = headless_default() if headless is None else headless
    with sync_playwright() as playwright:
        browser_instance = playwright.chromium.launch(headless=effective_headless)
        page = browser_instance.new_page(locale="zh-CN", user_agent=UA)
        try:
            page.goto(TEXTOOLKIT, wait_until="domcontentloaded", timeout=max(30, timeout) * 1000)
            page.get_by_label(re.compile("WeChat Article URL", re.I)).fill(url)
            page.get_by_role("button", name=re.compile("convert", re.I)).click()
            deadline = time.monotonic() + max(90, timeout)
            while time.monotonic() < deadline:
                values = page.locator("textarea, pre, code").all_text_contents()
                candidates = [
                    item.strip() for item in values if len(re.sub(r"\s+", "", item)) >= 80
                ]
                if candidates:
                    return from_markdown(max(candidates, key=len), url, page.url, "textoolkit")
                time.sleep(0.75)
            raise FetchError("textoolkit: no Markdown result before timeout")
        finally:
            browser_instance.close()


def fetch(
    url: str,
    timeout: int = 30,
    mode: str = "auto",
    headless: bool | None = None,
    manual_wait: int = 0,
    cdp: str | None = None,
) -> Article:
    url = validate(url)
    methods = {
        "browser": lambda: browser(url, timeout, headless, manual_wait, cdp),
        "textoolkit": lambda: textoolkit(url, timeout, headless),
        "mptext": lambda: mptext(url, timeout),
        "direct": lambda: direct(url, timeout),
        "jina": lambda: jina(url, timeout),
    }
    if mode != "auto":
        return methods[mode]()

    desktop = bool(cdp or cdp_url()) or not headless_default()
    order = (
        ("browser", "textoolkit", "mptext", "direct", "jina")
        if desktop
        else ("textoolkit", "browser", "mptext", "direct", "jina")
    )
    errors: list[str] = []
    verification_seen = False
    for name in order:
        try:
            return methods[name]()
        except VerificationRequired as exc:
            verification_seen = True
            errors.append(str(exc))
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    error_type = VerificationRequired if verification_seen else FetchError
    raise error_type("All retrieval paths failed. " + " | ".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("-o", "--output")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument(
        "--mode", choices=("auto", "browser", "textoolkit", "mptext", "direct", "jina"), default="auto"
    )
    parser.add_argument("--cdp-url")
    parser.add_argument("--manual-wait", type=int, default=0)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--headless", action="store_true")
    group.add_argument("--headful", action="store_true")
    args = parser.parse_args()
    headless = True if args.headless else False if args.headful else None

    try:
        article = fetch(args.url, args.timeout, args.mode, headless, args.manual_wait, args.cdp_url)
    except VerificationRequired as exc:
        print(json.dumps({"ok": False, "error_type": "verification_required", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 3
    except Exception as exc:
        print(json.dumps({"ok": False, "error_type": "fetch_failed", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    if args.output:
        Path(args.output).write_text(article.markdown, encoding="utf-8")
    if args.json:
        print(json.dumps({**asdict(article), "ok": True}, ensure_ascii=False, indent=2))
    elif not args.output:
        print(article.markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
