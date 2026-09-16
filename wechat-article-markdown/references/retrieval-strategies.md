# Retrieval strategies

## Why plain HTTP is not sufficient

WeChat can redirect datacenter/cloud requests for public articles to `/mp/wappoc_appmsgcaptcha` with an environment-verification page. Changing only the User-Agent does not reliably change that state.

## Strategy order

### 1. Real/persistent browser

A user browser has two properties a cloud scraper often lacks: a stable local network reputation and a session that can be manually verified. Reuse the same browser profile rather than creating a fresh incognito context on every request.

Preferred browser order:

1. Attach to an already running Chrome CDP endpoint on localhost ports 9222-9235.
2. Launch a persistent Playwright browser profile.
3. If verification appears in a visible browser, allow the user to complete it and poll until `#js_content` appears.

Do not copy cookies out of the browser profile and do not print them.

### 2. Textoolkit proxy converter

Web UI:

```text
https://textoolkit.com/wechat-to-markdown
```

The public page states that it fetches a WeChat article through a proxy, parses the HTML, and returns clean Markdown with title and metadata. Use the published UI rather than guessing an undocumented private API.

Treat this as a replaceable cloud convenience route, not as a required dependency.

### 3. mptext public download endpoint

Candidate endpoint:

```text
GET https://down.mptext.top/api/public/v1/download
  ?url=<URL-encoded WeChat article URL>
  &format=markdown
```

Treat this as an optional external convenience route. Public availability, authentication requirements, quotas, and anti-bot behavior can change.

### 4. Direct HTML

Useful when WeChat serves the article normally. A valid article must contain `#js_content` and must not contain verification markers.

### 5. Jina Reader

Useful on ordinary pages, but WeChat may challenge the Reader's egress. Reject short, blocked, or verification responses.

## Exit status

- `0`: article retrieved successfully.
- `2`: retrieval/parsing/network error not classified as WeChat verification.
- `3`: a WeChat verification/rate-limit state blocked all usable routes.
