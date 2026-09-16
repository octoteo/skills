# Open-source design sources

The skill uses design patterns observed in public WeChat-reading projects. Do not copy credentials or private session data from these projects.

- `xiguawang/wechat-reader`
  - Reuse a real browser session.
  - Prefer attach/launch/Playwright strategies instead of pretending that a changed User-Agent solves WeChat verification.
  - Model CAPTCHA and rate limiting as explicit states.
  - Allow manual verification in a visible persistent browser and continue afterward.

- `bzd6661/wechat-article-for-ai`
  - Use a browser renderer and wait for `#js_content`.
  - Detect verification/CAPTCHA indicators explicitly.
  - Treat manual/headful verification as a recovery route rather than automatically solving CAPTCHA challenges.

- `joeseesun/qiaomu-markdown-proxy`
  - Use Playwright to render WeChat pages before extracting `#js_content` and article metadata.

- `Lniosy/wechat-article-download-api`
  - Demonstrates a proxy/API route that can return WeChat content in Markdown, HTML, text, or JSON.
  - Treat public proxy services as replaceable fallbacks because availability and authentication can change.

- `zero-times/wechat-official-studio-mcp`
  - Retry through an authenticated/local browser state after anonymous access hits the WeChat verification wrapper.
  - Keep cookies out of model-visible output.
