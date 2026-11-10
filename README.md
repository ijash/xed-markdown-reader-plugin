# Xed Markdown Preview

A Python plugin for Xed that displays a live, formatted Markdown preview in
place of the editor. Use the **Markdown Preview** button in the top toolbar,
**View → Markdown Preview**, or **Ctrl+Shift+M** to switch between editing and
previewing without splitting the view. Editing is disabled while preview mode
is active. The mode is tracked per tab, and the preview updates as the document
changes. Markdown files activate preview automatically when opened; other
documents stay in the editor until the toggle is used.

The renderer supports Markdown headings, emphasis, links, lists, fenced code,
tables, and block quotes, with styled light and dark themes. Links are displayed
but not opened, raw HTML is escaped, and external resources are blocked.

## Requirements

- Xed with Python 3 plugin support
- `python3-markdown`
- WebKitGTK 4.1 (or 4.0)

On Linux Mint, install the runtime dependencies if needed:

```sh
sudo apt install python3-markdown gir1.2-webkit2-4.1
```

## Install for the current user

From this directory, run the installer:

```sh
./install.sh
```

Restart Xed after installation. Enable **Markdown Preview** under **Edit →
Preferences → Plugins**.

To remove the plugin and its cached files from the current user's Xed data
directory, run:

```sh
./install.sh --uninstall
```

Restart Xed after uninstalling if it is currently running.

## Project layout

```text
markdown-preview.plugin       Xed plugin metadata
markdown_preview/
  __init__.py                 Xed integration, UI, and tab lifecycle
  renderer.py                 Markdown-to-HTML conversion and preview styling
tests/
  test_markdown_renderer.py   Renderer and plugin behavior tests
install.sh                    Per-user installer
```

The plugin uses Python because that is Xed's plugin interface. Rust would
require an additional native-extension build and would not remove the GTK or
WebKit runtime, so it would add packaging complexity rather than make this
plugin lighter. WebKit views are created only when a tab first enters preview;
the Markdown parser is reused for subsequent live updates.
