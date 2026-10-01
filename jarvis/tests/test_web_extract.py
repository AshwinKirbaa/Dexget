import unittest
from unittest.mock import patch, MagicMock

from jarvis.tools import web_extract


SAMPLE_HTML = """
<html><head><title>Test Page</title>
<meta name="description" content="A page for testing extraction.">
</head>
<body>
<script>ignoreme();</script>
<p>Hello world, this is the article body.</p>
<a href="https://example.com/one">One</a>
<a href="/two">Two</a>
<table><tr><th>Name</th><th>Age</th></tr><tr><td>Ada</td><td>30</td></tr></table>
</body></html>
"""


def _fake_response(html=SAMPLE_HTML):
    resp = MagicMock()
    resp.text = html
    resp.raise_for_status = MagicMock()
    return resp


class WebExtractTests(unittest.TestCase):
    @patch("jarvis.tools.web_extract.requests.get")
    def test_extract_page_text_strips_scripts(self, mock_get):
        mock_get.return_value = _fake_response()
        result = web_extract.extract_page_text("https://example.com")
        self.assertTrue(result.success)
        self.assertIn("Hello world", result.output)
        self.assertNotIn("ignoreme", result.output)

    @patch("jarvis.tools.web_extract.requests.get")
    def test_extract_links(self, mock_get):
        mock_get.return_value = _fake_response()
        result = web_extract.extract_links("https://example.com")
        self.assertTrue(result.success)
        hrefs = [l["href"] for l in result.output]
        self.assertIn("https://example.com/one", hrefs)
        self.assertIn("/two", hrefs)

    @patch("jarvis.tools.web_extract.requests.get")
    def test_extract_metadata(self, mock_get):
        mock_get.return_value = _fake_response()
        result = web_extract.extract_metadata("https://example.com")
        self.assertTrue(result.success)
        self.assertEqual(result.output["title"], "Test Page")
        self.assertEqual(result.output["description"], "A page for testing extraction.")

    @patch("jarvis.tools.web_extract.requests.get")
    def test_extract_tables(self, mock_get):
        mock_get.return_value = _fake_response()
        result = web_extract.extract_tables("https://example.com")
        self.assertTrue(result.success)
        self.assertEqual(result.output, [[["Name", "Age"], ["Ada", "30"]]])

    @patch("jarvis.tools.web_extract.requests.get")
    def test_network_error_becomes_failed_result_not_exception(self, mock_get):
        mock_get.side_effect = RuntimeError("connection refused")
        result = web_extract.extract_page_text("https://unreachable.example")
        self.assertFalse(result.success)
        self.assertIn("connection refused", result.error)


if __name__ == "__main__":
    unittest.main()
