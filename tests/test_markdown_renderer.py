import unittest
from types import MethodType, SimpleNamespace

import gi

try:
    gi.require_version("WebKit2", "4.1")
except ValueError:
    gi.require_version("WebKit2", "4.0")
from gi.repository import WebKit2

from markdown_preview import MarkdownPreviewPlugin, _render_markdown


class MarkdownRendererTests(unittest.TestCase):
    def test_renders_common_markdown_as_styled_html(self):
        rendered = _render_markdown(
            "# Hello **world**\n\n- first\n- second\n\n```python\nprint(1)\n```"
        )

        self.assertIn("<h1>Hello <strong>world</strong></h1>", rendered)
        self.assertIn("<li>first</li>", rendered)
        self.assertIn("<code class=\"language-python\">", rendered)
        self.assertIn("max-width: 900px", rendered)
        self.assertIn("border-radius: 7px", rendered)

    def test_escapes_raw_html_and_blocks_remote_resources(self):
        rendered = _render_markdown(
            '<script>alert("x")</script>\n\n![tracker](https://example.com/a.png)'
        )

        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("default-src 'none'", rendered)
        self.assertIn("img-src data: file:", rendered)
        self.assertIn('src="https://example.com/a.png"', rendered)

    def test_supports_dark_theme(self):
        rendered = _render_markdown("# Dark preview", dark=True)

        self.assertIn('<body class="dark">', rendered)
        self.assertIn("background: #242629", rendered)

    def test_reuses_renderer_without_carrying_document_state(self):
        first = _render_markdown("[first]: https://example.com/\n\n[first]")
        second = _render_markdown("# Second document")

        self.assertIn('href="https://example.com/"', first)
        self.assertIn("<h1>Second document</h1>", second)
        self.assertNotIn("https://example.com/", second)

    def test_allows_preview_navigation_and_blocks_link_navigation(self):
        class FakeDecision:
            def __init__(self, uri):
                self.uri = uri
                self.used = False
                self.ignored = False

            def get_navigation_action(self):
                return self

            def get_request(self):
                return self

            def get_uri(self):
                return self.uri

            def use(self):
                self.used = True

            def ignore(self):
                self.ignored = True

        web_view = object()
        state = {
            "web_view": web_view,
            "expected_navigation_uri": "file:///tmp/document/",
        }
        plugin = SimpleNamespace(_tabs={object(): state})
        preview_load = FakeDecision("file:///tmp/document/")
        handled = MarkdownPreviewPlugin._on_decide_policy(
            plugin,
            web_view,
            preview_load,
            WebKit2.PolicyDecisionType.NAVIGATION_ACTION,
        )

        self.assertTrue(handled)
        self.assertTrue(preview_load.used)
        self.assertIsNone(state["expected_navigation_uri"])

        link_navigation = FakeDecision("https://example.com/")
        handled = MarkdownPreviewPlugin._on_decide_policy(
            plugin,
            web_view,
            link_navigation,
            WebKit2.PolicyDecisionType.NAVIGATION_ACTION,
        )
        self.assertTrue(handled)
        self.assertTrue(link_navigation.ignored)

    def test_preview_mode_disables_editing_and_restores_it(self):
        class FakeAction:
            def __init__(self, active):
                self.active = active

            def get_active(self):
                return self.active

        class FakeStack:
            def __init__(self):
                self.visible_child = None

            def set_visible_child_name(self, name):
                self.visible_child = name

        class FakeView:
            def __init__(self):
                self.editable = True
                self.cursor_visible = True
                self.focused = False

            def set_editable(self, editable):
                self.editable = editable

            def set_cursor_visible(self, visible):
                self.cursor_visible = visible

            def grab_focus(self):
                self.focused = True

        class FakeWebView:
            def grab_focus(self):
                pass

        tab = object()
        view = FakeView()
        state = {
            "stack": FakeStack(),
            "view": view,
            "editor_editable": True,
            "editor_cursor_visible": True,
            "web_view": FakeWebView(),
            "preview": False,
        }
        plugin = SimpleNamespace(
            window=SimpleNamespace(get_active_tab=lambda: tab),
            _tabs={tab: state},
            _queue_update=lambda active_tab: None,
            _sync_toggle_action=lambda: None,
            _ensure_preview_view=lambda active_tab, tab_state: None,
        )
        plugin._set_preview_state = MethodType(
            MarkdownPreviewPlugin._set_preview_state, plugin
        )

        MarkdownPreviewPlugin._on_toggle(plugin, FakeAction(True))
        self.assertFalse(view.editable)
        self.assertFalse(view.cursor_visible)
        self.assertEqual(state["stack"].visible_child, "preview")
        self.assertTrue(state["preview"])

        MarkdownPreviewPlugin._on_toggle(plugin, FakeAction(False))
        self.assertTrue(view.editable)
        self.assertTrue(view.cursor_visible)
        self.assertEqual(state["stack"].visible_child, "editor")
        self.assertFalse(state["preview"])

    def test_markdown_documents_are_detected_by_extension(self):
        class FakeLocation:
            def __init__(self, path):
                self.path = path

            def get_path(self):
                return self.path

        class FakeBuffer:
            def __init__(self, path):
                self.location = FakeLocation(path) if path else None

            def get_location(self):
                return self.location

        for path in (
            "/home/user/notes.md",
            "/home/user/README.MARKDOWN",
            "/home/user/doc.mdown",
            "/home/user/doc.mkd",
        ):
            self.assertTrue(
                MarkdownPreviewPlugin._is_markdown_document(FakeBuffer(path))
            )

        for path in (
            "/home/user/notes.txt",
            "/home/user/script.py",
            "/home/user/archive.md.bak",
            None,
        ):
            self.assertFalse(
                MarkdownPreviewPlugin._is_markdown_document(FakeBuffer(path))
            )

    def test_opening_markdown_document_activates_preview(self):
        class FakeStack:
            def __init__(self):
                self.visible_child = None

            def set_visible_child_name(self, name):
                self.visible_child = name

        class FakeView:
            def __init__(self):
                self.editable = True
                self.cursor_visible = True

            def set_editable(self, editable):
                self.editable = editable

            def set_cursor_visible(self, visible):
                self.cursor_visible = visible

            def grab_focus(self):
                pass

        class FakeWebView:
            def grab_focus(self):
                pass

        tab = object()
        state = {
            "stack": FakeStack(),
            "view": FakeView(),
            "editor_editable": True,
            "editor_cursor_visible": True,
            "web_view": FakeWebView(),
            "preview": False,
        }
        plugin = SimpleNamespace(
            _tabs={tab: state},
            _queue_update=lambda active_tab: None,
            _sync_toggle_action=lambda: None,
            _ensure_preview_view=lambda active_tab, tab_state: None,
        )

        MarkdownPreviewPlugin._set_preview_state(plugin, tab, True)
        self.assertTrue(state["preview"])
        self.assertEqual(state["stack"].visible_child, "preview")
        self.assertFalse(state["view"].editable)


if __name__ == "__main__":
    unittest.main()
