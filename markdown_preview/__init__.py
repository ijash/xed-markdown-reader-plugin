from gettext import gettext as _
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Xed", "1.0")
try:
    gi.require_version("WebKit2", "4.1")
except ValueError:
    gi.require_version("WebKit2", "4.0")

from gi.repository import GLib, GObject, Gtk, WebKit2, Xed

from .renderer import render_markdown as _render_markdown


MENU_PATH = "/MenuBar/ViewMenu/ViewOps_1"
PLUGIN_NAME = "MarkdownPreviewPlugin"
DEBOUNCE_MS = 150
MARKDOWN_EXTENSIONS = (".md", ".markdown", ".mdown", ".mkd", ".mkdn", ".mdwn")


class MarkdownPreviewPlugin(GObject.Object, Xed.WindowActivatable):
    __gtype_name__ = PLUGIN_NAME

    window = GObject.Property(type=Xed.Window)

    def __init__(self):
        super().__init__()
        self._buffer_handlers = {}
        self._window_handlers = []
        self._tabs = {}
        self._update_source_id = None
        self._expected_navigation_uri = None

    def do_activate(self):
        self._insert_menu()

        for view in self.window.get_views():
            self._connect_buffer(view.get_buffer())
            tab = Xed.Tab.get_from_document(view.get_buffer())
            if tab is not None:
                self._attach_tab(tab)
                if self._is_markdown_document(view.get_buffer()):
                    self._set_preview_state(tab, True)

        for signal_name, callback in (
            ("tab-added", self._on_tab_added),
            ("tab-removed", self._on_tab_removed),
            ("active-tab-changed", self._on_active_tab_changed),
        ):
            self._window_handlers.append(
                self.window.connect(signal_name, callback)
            )
        self._sync_toggle_action()

    def do_deactivate(self):
        if self._update_source_id is not None:
            GLib.source_remove(self._update_source_id)
            self._update_source_id = None

        for tab in list(self._tabs):
            self._restore_tab(tab)

        for buffer, handler_id in self._buffer_handlers.items():
            buffer.disconnect(handler_id)
        self._buffer_handlers.clear()

        for handler_id in self._window_handlers:
            self.window.disconnect(handler_id)
        self._window_handlers.clear()

        manager = self.window.get_ui_manager()
        manager.remove_ui(self._ui_id)
        manager.remove_action_group(self._action_group)
        self._toolbar.remove(self._toolbar_button)
        manager.ensure_update()
        self._action_group = None
        self._toggle_action = None

    def _attach_tab(self, tab):
        if tab in self._tabs:
            return

        view = tab.get_view()
        editor_root = view
        while editor_root.get_parent() is not tab:
            parent = editor_root.get_parent()
            if parent is None:
                raise RuntimeError("Could not locate the Xed tab's editor container")
            editor_root = parent

        settings = Gtk.Settings.get_default()
        theme_name = settings.get_property("gtk-theme-name").lower()
        dark_theme = (
            settings.get_property("gtk-application-prefer-dark-theme")
            or "dark" in theme_name
        )

        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.NONE)
        tab.remove(editor_root)
        stack.add_named(editor_root, "editor")
        tab.pack_start(stack, True, True, 0)
        stack.show_all()
        stack.set_visible_child_name("editor")

        self._tabs[tab] = {
            "stack": stack,
            "editor_root": editor_root,
            "view": view,
            "editor_editable": view.get_editable(),
            "editor_cursor_visible": view.get_cursor_visible(),
            "web_view": None,
            "dark_theme": dark_theme,
            "preview": False,
            "expected_navigation_uri": None,
        }

    def _restore_tab(self, tab):
        state = self._tabs.pop(tab, None)
        if state is None:
            return
        state["stack"].remove(state["editor_root"])
        tab.remove(state["stack"])
        tab.pack_start(state["editor_root"], True, True, 0)
        state["view"].set_editable(state["editor_editable"])
        state["view"].set_cursor_visible(state["editor_cursor_visible"])
        state["editor_root"].show_all()

    def _insert_menu(self):
        manager = self.window.get_ui_manager()
        self._action_group = Gtk.ActionGroup(name="XedMarkdownPreviewActions")
        self._toggle_action = Gtk.ToggleAction(
            name="MarkdownPreviewAction",
            label=_("Markdown Preview"),
            tooltip=_("Toggle between the editor and Markdown preview"),
            stock_id=None,
        )
        self._toggle_handler_id = self._toggle_action.connect(
            "toggled", self._on_toggle
        )
        self._action_group.add_action_with_accel(
            self._toggle_action, "<Ctrl><Shift>M"
        )
        manager.insert_action_group(self._action_group)
        self._ui_id = manager.new_merge_id()
        manager.add_ui(
            self._ui_id,
            MENU_PATH,
            "MarkdownPreviewAction",
            "MarkdownPreviewAction",
            Gtk.UIManagerItemType.MENUITEM,
            False,
        )
        self._toolbar = self._find_top_toolbar()
        self._toolbar_button = Gtk.ToggleToolButton()
        self._toolbar_button.set_related_action(self._toggle_action)
        self._toolbar_button.set_icon_widget(
            Gtk.Image.new_from_icon_name(
                "document-preview", Gtk.IconSize.LARGE_TOOLBAR
            )
        )
        self._toolbar_button.set_label(_("Preview"))
        self._toolbar_button.set_tooltip_text(
            _("Toggle between the editor and Markdown preview")
        )
        self._toolbar_group = self._find_toolbar_button_group()
        self._toolbar_group.pack_end(self._toolbar_button, False, False, 0)
        self._toolbar_button.show_all()

    def _find_top_toolbar(self):
        widgets = [self.window]
        toolbars = []
        while widgets:
            widget = widgets.pop()
            if isinstance(widget, Gtk.Toolbar):
                allocation = widget.get_allocation()
                if widget.get_visible() and allocation.width > 0:
                    toolbars.append((allocation.width, widget))
            if isinstance(widget, Gtk.Container):
                widgets.extend(widget.get_children())
        if not toolbars:
            raise RuntimeError("Could not locate Xed's visible top toolbar")
        return max(toolbars, key=lambda item: item[0])[1]

    def _find_toolbar_button_group(self):
        groups = []
        widgets = [self._toolbar]
        while widgets:
            widget = widgets.pop()
            if isinstance(widget, Gtk.Box) and any(
                isinstance(child, Gtk.Button) for child in widget.get_children()
            ):
                groups.append(widget)
            if isinstance(widget, Gtk.Container):
                widgets.extend(reversed(widget.get_children()))
        if not groups:
            raise RuntimeError("Could not locate Xed's toolbar button group")
        return groups[-1]

    def _connect_buffer(self, buffer):
        if buffer not in self._buffer_handlers:
            self._buffer_handlers[buffer] = buffer.connect(
                "changed", self._on_buffer_changed
            )

    def _disconnect_buffer(self, buffer):
        handler_id = self._buffer_handlers.pop(buffer, None)
        if handler_id is not None:
            buffer.disconnect(handler_id)

    def _on_tab_added(self, window, tab):
        self._connect_buffer(tab.get_view().get_buffer())
        self._attach_tab(tab)
        if self._is_markdown_document(tab.get_view().get_buffer()):
            self._set_preview_state(tab, True)
        self._sync_toggle_action()

    def _on_tab_removed(self, window, tab):
        self._disconnect_buffer(tab.get_view().get_buffer())
        self._tabs.pop(tab, None)
        self._sync_toggle_action()

    def _on_active_tab_changed(self, window, tab):
        self._sync_toggle_action()
        state = self._tabs.get(tab)
        if state is not None and state["preview"]:
            self._queue_update(tab)

    def _on_buffer_changed(self, buffer):
        tab = Xed.Tab.get_from_document(buffer)
        state = self._tabs.get(tab)
        if state is not None and state["preview"]:
            self._queue_update(tab)

    def _on_toggle(self, action):
        tab = self.window.get_active_tab()
        self._set_preview_state(tab, action.get_active())

    def _set_preview_state(self, tab, active):
        state = self._tabs.get(tab)
        if state is None:
            return
        if active:
            self._ensure_preview_view(tab, state)
        state["preview"] = active
        state["stack"].set_visible_child_name(
            "preview" if active else "editor"
        )
        if active:
            state["view"].set_editable(False)
            state["view"].set_cursor_visible(False)
            state["web_view"].grab_focus()
            self._queue_update(tab)
        else:
            state["view"].set_editable(state["editor_editable"])
            state["view"].set_cursor_visible(state["editor_cursor_visible"])
            state["view"].grab_focus()
        self._sync_toggle_action()

    def _ensure_preview_view(self, tab, state):
        if state["web_view"] is not None:
            return

        web_view = WebKit2.WebView()
        web_view.set_editable(False)
        web_view.connect("decide-policy", self._on_decide_policy)
        web_view.connect("map", self._on_preview_map, tab)

        preview_widget = Gtk.ScrolledWindow()
        preview_widget.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
        )
        preview_widget.add(web_view)
        state["stack"].add_named(preview_widget, "preview")
        state["web_view"] = web_view
        preview_widget.show_all()

    @staticmethod
    def _is_markdown_document(buffer):
        location = buffer.get_location()
        if location is None:
            return False
        path = location.get_path()
        if not path:
            return False
        return path.lower().endswith(MARKDOWN_EXTENSIONS)

    def _sync_toggle_action(self):
        tab = self.window.get_active_tab()
        state = self._tabs.get(tab)
        active = state["preview"] if state is not None else False
        self._toggle_action.handler_block(self._toggle_handler_id)
        self._toggle_action.set_active(active)
        self._toggle_action.handler_unblock(self._toggle_handler_id)
        self._toggle_action.set_sensitive(state is not None)

    def _queue_update(self, tab):
        if self._update_source_id is not None:
            GLib.source_remove(self._update_source_id)
            self._update_source_id = None
        self._update_source_id = GLib.timeout_add(
            DEBOUNCE_MS, self._update_preview, tab
        )

    def _update_preview(self, tab):
        self._update_source_id = None
        state = self._tabs.get(tab)
        if state is None or not state["preview"] or state["web_view"] is None:
            return GLib.SOURCE_REMOVE
        if not state["web_view"].get_mapped():
            return GLib.SOURCE_REMOVE

        document = tab.get_view().get_buffer()
        if document is None:
            source = ""
            base_uri = None
        else:
            start, end = document.get_bounds()
            source = document.get_text(start, end, True)
            location = document.get_location()
            uri = location.get_uri() if location is not None else None
            base_uri = self._get_base_uri(uri)

        html = _render_markdown(source, state["dark_theme"])
        state["expected_navigation_uri"] = base_uri or "about:blank"
        state["web_view"].load_html(html, base_uri)
        return GLib.SOURCE_REMOVE

    def _on_preview_map(self, web_view, tab):
        self._queue_update(tab)

    @staticmethod
    def _get_base_uri(uri):
        if not uri or not uri.startswith("file://"):
            return None
        return uri.rsplit("/", 1)[0] + "/"

    def _on_decide_policy(self, web_view, decision, decision_type):
        state = next(
            (
                tab_state
                for tab_state in self._tabs.values()
                if tab_state["web_view"] is web_view
            ),
            None,
        )
        if state is None:
            return False

        navigation_types = (
            WebKit2.PolicyDecisionType.NAVIGATION_ACTION,
            WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION,
        )
        if decision_type in navigation_types:
            request = decision.get_navigation_action().get_request()
            uri = request.get_uri()
            if uri == state["expected_navigation_uri"]:
                state["expected_navigation_uri"] = None
                decision.use()
            else:
                decision.ignore()
            return True
        return False
