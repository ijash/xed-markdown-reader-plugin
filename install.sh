#!/bin/sh
set -eu

cd "$(dirname "$0")"

plugin_dir="${XDG_DATA_HOME:-"$HOME/.local/share"}/xed/plugins"
module_dir="$plugin_dir/markdown_preview"

case "${1:-}" in
    -u|--uninstall)
        if [ "$#" -ne 1 ]; then
            printf 'Usage: %s [--uninstall|-u|--help]\n' "$0" >&2
            exit 2
        fi
        rm -f -- "$plugin_dir/markdown-preview.plugin"
        if [ -d "$module_dir" ]; then
            rm -rf -- "$module_dir"
        fi
        printf 'Uninstalled Markdown Preview for Xed.\n'
        exit 0
        ;;
    -h|--help)
        printf 'Usage: %s [--uninstall|-u|--help]\n' "$0"
        printf 'Run without an option to install for the current user.\n'
        exit 0
        ;;
    '')
        ;;
    *)
        printf 'Unknown option: %s\nUsage: %s [--uninstall|-u|--help]\n' "$1" "$0" >&2
        exit 2
        ;;
esac

if ! /usr/bin/python3 -c '
import gi
import markdown
gi.require_version("Gtk", "3.0")
try:
    gi.require_version("WebKit2", "4.1")
except ValueError:
    gi.require_version("WebKit2", "4.0")
from gi.repository import Gtk, WebKit2
' >/dev/null 2>&1; then
    printf 'Missing dependencies. On Linux Mint, install them with:\\n' >&2
    printf '  sudo apt install python3-markdown gir1.2-webkit2-4.1\\n' >&2
    exit 1
fi

mkdir -p "$module_dir"
install -m 0644 markdown-preview.plugin "$plugin_dir/markdown-preview.plugin"
install -m 0644 markdown_preview/*.py "$module_dir/"

printf 'Installed Markdown Preview for Xed. Restart Xed, then enable it in Edit > Preferences > Plugins.\n'
