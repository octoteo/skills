from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "wechat-article-markdown" / "scripts" / "fetch_wechat_article.py"
SPEC = importlib.util.spec_from_file_location("wechat_fetch", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class Tests(unittest.TestCase):
    def test_unwrap(self):
        url = (
            "https://mp.weixin.qq.com/mp/wappoc_appmsgcaptcha?"
            "target_url=https%3A%2F%2Fmp.weixin.qq.com%2Fs%2Fabc"
        )
        self.assertEqual(mod.validate(url), "https://mp.weixin.qq.com/s/abc")

    def test_reject_non_wechat(self):
        with self.assertRaises(mod.FetchError):
            mod.validate("https://example.com/a")

    def test_verification_detection(self):
        self.assertTrue(mod.is_verify("当前环境异常，完成验证后即可继续访问"))

    def test_html_conversion(self):
        html = """
        <h1 id='activity-name'>T</h1>
        <div id='js_content'>
          <p>正文内容足够长用于测试正文内容足够长用于测试正文内容足够长用于测试。</p>
          <img data-src='https://mmbiz.qpic.cn/x.jpg'>
        </div>
        """
        article = mod.from_html(
            html,
            "https://mp.weixin.qq.com/s/x",
            "https://mp.weixin.qq.com/s/x",
            "test",
        )
        self.assertIn("mmbiz.qpic.cn/x.jpg", article.markdown)

    def test_desktop_prefers_browser(self):
        fake = mod.Article("u", "u", "browser", "t", "# t\n" + ("正文" * 50))
        with patch.object(mod, "cdp_url", return_value="http://127.0.0.1:9222"), \
             patch.object(mod, "browser", return_value=fake), \
             patch.object(mod, "textoolkit", side_effect=AssertionError()):
            result = mod.fetch("https://mp.weixin.qq.com/s/x")
        self.assertEqual(result.method, "browser")

    def test_headless_prefers_textoolkit(self):
        fake = mod.Article("u", "u", "textoolkit", "t", "# t\n" + ("正文" * 50))
        with patch.object(mod, "cdp_url", return_value=None), \
             patch.object(mod, "headless_default", return_value=True), \
             patch.object(mod, "textoolkit", return_value=fake), \
             patch.object(mod, "browser", side_effect=AssertionError()):
            result = mod.fetch("https://mp.weixin.qq.com/s/x")
        self.assertEqual(result.method, "textoolkit")


if __name__ == "__main__":
    unittest.main()
