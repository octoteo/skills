---
name: wechat-article-markdown
description: Convert a public WeChat Official Account article URL (mp.weixin.qq.com/s/...) into clean Markdown for reading, summarization, fact-checking, translation, or archiving. Use whenever a user provides a public WeChat article link and needs the actual article body. Prefer a proxy-backed converter that is known to work from cloud environments, then reuse a real/persistent Chrome session when WeChat challenges cloud egress; explicitly detect captcha, environment-verification, and rate-limit pages instead of treating them as article content.
---

# WeChat Article Markdown

Retrieve the real article body first. Never infer missing text from search snippets or article titles.

## Default workflow

1. Run automatic retrieval:

   ```bash
   python scripts/fetch_wechat_article.py "<wechat-url>" -o /mnt/data/wechat-article.md --json
   ```

2. On success, use the generated Markdown as the source of truth for downstream reading, summarization, translation, or fact-checking.
3. If the local execution sandbox cannot reach the public web, use an available live browser/web-automation tool. Prefer the Textoolkit workflow when it is reachable; if it is unavailable, report that the remaining cloud routes may still be blocked by WeChat and recommend a user-verified local Chrome/CDP session rather than claiming the Skill is universally unusable.
4. If automatic mode reports `verification_required`, prefer a real local browser session rather than repeatedly retrying cloud HTTP requests.
5. If the user requested a Markdown artifact, return the `.md` file.

## Retrieval cascade

Automatic mode is environment-aware rather than tied to one third-party service:

- **Desktop / attachable Chrome available:** real browser session → Textoolkit → mptext → direct WeChat HTML → Jina Reader.
- **Headless/cloud environment:** Textoolkit → persistent browser → mptext → direct WeChat HTML → Jina Reader.

The real-browser route attaches to Chrome CDP when possible and otherwise launches a persistent Playwright profile. Textoolkit is a replaceable cloud convenience path, not a required dependency. mptext and Jina are best-effort fallbacks only.

Diagnose a specific route with `--mode textoolkit|browser|mptext|direct|jina`.

## Connected-browser Textoolkit workflow

Use this when code execution has restricted outbound networking but a live browser automation tool is available:

1. Open `https://textoolkit.com/wechat-to-markdown`.
2. Fill the field labelled `WeChat Article URL` with the public `mp.weixin.qq.com/s/...` URL.
3. Activate `Convert`.
4. Wait for the generated Markdown result.
5. Accept the result only when it contains plausible article-length text plus article metadata or a Markdown heading.
6. Treat the converter's returned Markdown as article content, not as independent factual evidence about claims inside the article.

Only submit the public article URL. Never submit WeChat cookies, tokens, credentials, or browser profile data to a third-party converter.

## Browser verification recovery

When WeChat returns `wappoc_appmsgcaptcha`, an environment-anomaly message, a too-frequent-access message, or equivalent verification state, do not loop retries.

On a desktop with Chrome/Chromium, run:

```bash
python scripts/fetch_wechat_article.py "<wechat-url>" \
  --mode browser \
  --headful \
  --manual-wait 180 \
  -o /mnt/data/wechat-article.md
```

The browser profile is persisted under `~/.wechat-article-markdown/chrome-profile`. Complete WeChat's verification manually in the visible browser. The script polls the same page and extracts `#js_content` once verification succeeds. Future reads reuse that verified profile.

If Chrome is already running with remote debugging enabled, attach instead:

```bash
python scripts/fetch_wechat_article.py "<wechat-url>" \
  --mode browser \
  --cdp-url http://127.0.0.1:9222 \
  -o /mnt/data/wechat-article.md
```

## Integrity rules

- Accept only public `mp.weixin.qq.com/s` article URLs.
- Unwrap `mp/wappoc_appmsgcaptcha?...target_url=...` back to the article URL before retrieval.
- Require plausible content; reject empty responses, verification walls, rate-limit pages, and generic error pages.
- For WeChat HTML/browser extraction, require `#js_content`.
- Prefer lazy-image `data-src`; preserve useful links and images in Markdown when the source route exposes them.
- Never attempt to automatically solve a CAPTCHA. Human verification is an allowed recovery step in a user-visible browser.
- Never expose browser cookies, tokens, or profile secrets in output or logs.
- A converter proving that an article was retrievable does not validate the truth of the article's claims; fact-check those claims separately against independent sources.

## Dependencies

Base conversion requires `requests`, `beautifulsoup4`, and `markdownify`.
Textoolkit and browser fallbacks additionally require `playwright` and Chromium/Chrome:

```bash
pip install playwright
playwright install chromium
```

See `references/retrieval-strategies.md` for troubleshooting and `references/design-sources.md` for the open-source designs that informed this workflow.
