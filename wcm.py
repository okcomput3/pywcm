#!/usr/bin/env python3
"""
Wayfire Config Manager (WCM) — Python/GTK4 — LUXE THEME with system Light/Dark mode
"""
import gi


gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
import sys, os, subprocess, glob, shutil, traceback, re, math
import copy
from decimal import Decimal
from gi.repository import Gtk, Gdk, GLib, Gio, GdkPixbuf, Pango


def _userns_blocked():
    """Return True if unprivileged user namespaces look disabled, which is
    what makes WebKitGTK's bubblewrap (bwrap) sandbox fail with
    'setting up uid map: permission denied'."""
    try:
        with open("/proc/sys/kernel/unprivileged_userns_clone") as f:
            if f.read().strip() == "0":
                return True
    except Exception:
        pass
    try:
        # Ubuntu 23.10+ restricts unprivileged userns via AppArmor.
        with open("/proc/sys/kernel/apparmor_restrict_unprivileged_userns") as f:
            if f.read().strip() == "1":
                return True
    except Exception:
        pass
    return False


# WebKitGTK (GTK4 build) is optional; used to show wiki pages inside the
# side panel. If it isn't installed we fall back to an external browser.
try:
    gi.require_version("WebKit", "6.0")
    from gi.repository import WebKit

    _HAVE_WEBKIT = True
    # WebKitGTK 6.0 always sandboxes its web process with bwrap, which needs
    # unprivileged user namespaces. Where those are blocked (many containers,
    # hardened kernels, or Ubuntu's AppArmor userns restriction) the web
    # process dies with "bwrap: setting up uid map: permission denied" and the
    # page never loads. The set_sandbox_enabled() API was removed in 6.0, so
    # the only way to recover is this env var, which must be set before the
    # first web process starts. Only do it when userns is actually blocked, so
    # the sandbox stays enabled on systems where it works.
    if _userns_blocked():
        os.environ.setdefault("WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS", "1")
    # On some Wayland compositors (Wayfire among them) WebKitGTK's DMABUF
    # renderer triggers "Error 71 (Protocol error)" / internallyFailedLoad
    # failures. Disabling it avoids that whole class of crashes; it's only a
    # rendering-path change and is a no-op where DMABUF already works. Set via
    # setdefault so anyone who needs the accelerated path can override it.
    os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")
except Exception:
    WebKit = None
    _HAVE_WEBKIT = False

from i18n import _
from config_backend import WayfireConfigFile, PresetManager, OutputManager, SaveCommittedError

__version__ = "0.2.0"
from metadata import (
    load_all_metadata,
    merge_extra_animations,
    load_metadata_from_dir,
    find_metadata_dirs,
    Plugin,
    Option,
    OptionType,
    PluginType,
)


def _make_css(dark=True):
    if dark:
        bg_deep, bg_panel, bg_card, bg_input, bg_input_f = (
            "#0b0d16",
            "rgba(13,16,30,0.94)",
            "rgba(18,22,40,0.82)",
            "rgba(12,15,30,0.86)",
            "rgba(16,20,38,0.94)",
        )
        amber, amber_l, rose, teal = "#e0982a", "#f0b84d", "#d25d77", "#38beb3"
        txt1, txt2 = "rgba(228,224,218,0.95)", "rgba(180,175,168,0.78)"
        bdr_s, bdr_a = "rgba(224,152,42,0.10)", "rgba(224,152,42,0.50)"
        ab, ar, at = "224,152,42", "210,93,119", "56,190,179"
        panel_bg = "rgba(12,14,26,0.96)"
        popup_bg = "rgba(12,15,28,0.98)"
        dlg_bg = "#0e1120"
        dlg_hdr = "rgba(14,17,32,0.98)"
        left_bdr = "rgba(224,152,42,0.12)"
        tab_bg = "rgba(10,12,24,0.75)"
    else:
        bg_deep, bg_panel, bg_card, bg_input, bg_input_f = (
            "#f7f4ef",
            "rgba(245,240,232,0.92)",
            "rgba(255,255,255,0.85)",
            "rgba(240,236,228,0.90)",
            "rgba(255,252,248,0.95)",
        )
        amber, amber_l, rose, teal = "#b07818", "#c08828", "#a8405a", "#2a8a80"
        txt1, txt2 = "rgba(42,37,32,0.92)", "rgba(90,82,72,0.75)"
        bdr_s, bdr_a = "rgba(176,120,24,0.15)", "rgba(176,120,24,0.50)"
        ab, ar, at = "176,120,24", "168,64,90", "42,138,128"
        panel_bg = "rgba(240,236,228,0.95)"
        popup_bg = "rgba(250,248,244,0.98)"
        dlg_bg = "#f0ede8"
        dlg_hdr = "rgba(240,236,228,0.98)"
        left_bdr = "rgba(176,120,24,0.10)"
        tab_bg = "rgba(245,240,232,0.80)"
    if dark:
        ini_bg, ini_fg, ini_accent, ini_gutter = "#0a0d18", "#e6e0d8", "#63ded4", "#636b80"
        ini_border, ini_hdr_border = "rgba(95,214,203,0.26)", "rgba(95,214,203,0.22)"
        ini_grad_a, ini_grad_b = "rgba(95,214,203,0.09)", "rgba(9,11,20,0.0)"
        ini_hot, ini_hot_a, ini_hot_b = "#5fd6cb", "rgba(95,214,203,0.40)", "rgba(95,214,203,0.13)"
    else:
        ini_bg, ini_fg, ini_accent, ini_gutter = "#f3efe7", "#2a2520", "#2a8a80", "#a39a8c"
        ini_border, ini_hdr_border = "rgba(42,138,128,0.22)", "rgba(42,138,128,0.20)"
        ini_grad_a, ini_grad_b = "rgba(42,138,128,0.08)", "rgba(243,239,231,0.0)"
        ini_hot, ini_hot_a, ini_hot_b = "#2a8a80", "rgba(42,138,128,0.30)", "rgba(42,138,128,0.12)"
    return f"""
@define-color bg_deep {bg_deep}; @define-color bg_panel {bg_panel}; @define-color bg_card {bg_card};
@define-color bg_input {bg_input}; @define-color bg_input_focus {bg_input_f};
@define-color amber {amber}; @define-color amber_light {amber_l}; @define-color rose {rose}; @define-color teal {teal};
@define-color text_primary {txt1}; @define-color text_secondary {txt2};
@define-color border_subtle {bdr_s}; @define-color border_active {bdr_a};
@define-color danger {rose}; @define-color success {teal};

@keyframes warm-pulse {{ 0% {{ box-shadow: 0 0 4px rgba({ab},0.06); }} 50% {{ box-shadow: 0 0 20px rgba({ab},0.22); }} 100% {{ box-shadow: 0 0 4px rgba({ab},0.06); }} }}
@keyframes border-breathe {{ 0% {{ border-color: rgba({ab},0.08); }} 50% {{ border-color: rgba({ab},0.22); }} 100% {{ border-color: rgba({ab},0.08); }} }}
@keyframes amber-flicker {{ 0% {{ opacity: 0.88; }} 4% {{ opacity: 1; }} 8% {{ opacity: 0.90; }} 12% {{ opacity: 1; }} 88% {{ opacity: 1; }} 92% {{ opacity: 0.85; }} 96% {{ opacity: 1; }} 100% {{ opacity: 0.92; }} }}
@keyframes fade-slide-in {{ from {{ opacity: 0; margin-top: 14px; }} to {{ opacity: 1; margin-top: 0; }} }}
@keyframes fade-in {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
@keyframes rose-pulse {{ 0% {{ box-shadow: 0 0 4px rgba({ar},0.04); }} 50% {{ box-shadow: 0 0 16px rgba({ar},0.20); }} 100% {{ box-shadow: 0 0 4px rgba({ar},0.04); }} }}
@keyframes teal-pulse {{ 0% {{ box-shadow: 0 0 4px rgba({at},0.04); }} 50% {{ box-shadow: 0 0 16px rgba({at},0.22); }} 100% {{ box-shadow: 0 0 4px rgba({at},0.04); }} }}
@keyframes check-glow {{ 0% {{ box-shadow: 0 0 2px rgba({ab},0.08); }} 50% {{ box-shadow: 0 0 14px rgba({ab},0.35); }} 100% {{ box-shadow: 0 0 2px rgba({ab},0.08); }} }}
@keyframes tab-glow {{ 0% {{ box-shadow: 0 2px 4px rgba({ab},0.04); }} 50% {{ box-shadow: 0 2px 18px rgba({ab},0.18); }} 100% {{ box-shadow: 0 2px 4px rgba({ab},0.04); }} }}
@keyframes slide-in-from-bottom {{ from {{ opacity: 0; margin-top: 20px; }} to {{ opacity: 1; margin-top: 0; }} }}
@keyframes slide-in-from-top {{ from {{ opacity: 0; margin-top: -20px; }} to {{ opacity: 1; margin-top: 0; }} }}
@keyframes plugin-entrance {{ 0% {{ opacity: 0; margin-top: 10px; }} 100% {{ opacity: 1; margin-top: 0; }} }}
@keyframes settings-reveal {{ 0% {{ opacity: 0; margin-top: 10px; }} 100% {{ opacity: 1; margin-top: 0; }} }}
@keyframes rail-glow {{ 0% {{ opacity: 0.88; box-shadow: 0 0 0 rgba({ab},0.00); }} 50% {{ opacity: 1; box-shadow: 0 0 20px rgba({ab},0.18); }} 100% {{ opacity: 0.90; box-shadow: 0 0 0 rgba({ab},0.00); }} }}
@keyframes category-slide-in {{ from {{ opacity: 0; margin-start: -30px; }} to {{ opacity: 1; margin-start: 10px; }} }}
@keyframes category-slide-out {{ from {{ opacity: 1; margin-start: 10px; }} to {{ opacity: 0; margin-start: -30px; }} }}
.tab-enter-up {{ animation: slide-in-from-bottom 380ms cubic-bezier(0.22,1,0.36,1); }}
.tab-enter-down {{ animation: slide-in-from-top 380ms cubic-bezier(0.22,1,0.36,1); }}

window {{ background-color: @bg_deep; color: @text_primary; }}
label {{ color: @text_primary; font-family: "Cantarell","Noto Sans","Segoe UI",sans-serif; }}

dialog, window.dialog, colordialog, colorchooser, window.csd colordialog, colorchooserdialog {{ background-color: {dlg_bg}; color: @text_primary; }}
dialog headerbar, window.dialog headerbar, colordialog headerbar, colorchooser headerbar {{ background-color: {dlg_hdr}; color: @text_primary; }}
colorchooser, colorchooserdialog > box {{ background-color: {dlg_bg}; }}

scrolledwindow {{ background-color: transparent; }} scrolledwindow > viewport {{ background-color: transparent; }}
scrollbar trough {{ background-color: rgba({ab},0.03); border-radius: 8px; min-width: 7px; }}
scrollbar slider {{ background-color: rgba({ab},0.14); border-radius: 8px; min-width: 7px; min-height: 44px; transition: all 350ms cubic-bezier(0.22,1,0.36,1); }}
scrollbar slider:hover {{ background-color: rgba({ab},0.32); }}

button {{ background-image: none; background-color: rgba({ab},0.06); color: @amber_light; border: 1px solid rgba({ab},0.10); border-radius: 10px; padding: 7px 16px; font-weight: 600; transition: all 300ms cubic-bezier(0.22,1,0.36,1); }}
button:hover {{ background-color: rgba({ab},0.14); border-color: rgba({ab},0.38); color: @text_primary; text-shadow: 0 0 10px rgba({ab},0.25); }}
button:active {{ background-color: rgba({ab},0.22); border-color: @amber; transition: all 80ms ease; }}
button.flat {{ background-color: transparent; background-image: none; border-color: transparent; box-shadow: none; padding: 4px 10px; }}
button.flat:hover {{ background-color: transparent; background-image: none; border-color: transparent; }}

entry {{ background-color: @bg_input; color: @text_primary; border: 1px solid @border_subtle; border-radius: 8px; padding: 7px 12px; caret-color: @amber; transition: all 300ms cubic-bezier(0.22,1,0.36,1); box-shadow: inset 0 1px 3px rgba(0,0,0,{'0.30' if dark else '0.06'}); }}
entry:focus {{ background-color: @bg_input_focus; border-color: @border_active; box-shadow: inset 0 1px 3px rgba(0,0,0,{'0.30' if dark else '0.06'}), 0 0 16px rgba({ab},0.12); }}
entry > text > selection {{ background-color: rgba({ab},0.22); }}
.plugin-search, entry.plugin-search, entry.search.plugin-search, searchentry.plugin-search {{
    background-color: {'rgba(12,16,28,0.96)' if dark else 'rgba(255,255,255,0.96)'};
    background-image: none;
    border: 1px solid rgba({ab},0.10);
    border-radius: 14px;
    padding: 11px 18px;
    color: @text_primary;
    font-size: 1.05em;
    transition: all 400ms cubic-bezier(0.22,1,0.36,1);
}}
.plugin-search:focus, entry.plugin-search:focus, entry.search.plugin-search:focus, searchentry.plugin-search:focus {{
    background-color: {'rgba(14,18,32,0.98)' if dark else 'rgba(255,255,255,0.98)'};
    background-image: none;
    border-color: @amber;
    box-shadow: 0 0 24px rgba({ab},0.16);
}}
.plugin-search text, entry.plugin-search text, entry.search.plugin-search text, searchentry.plugin-search text {{
    background-color: {'rgba(12,16,28,0.98)' if dark else 'rgba(255,255,255,0.98)'};
    color: @text_primary;
}}
spinbutton {{ background-color: @bg_input; border: 1px solid @border_subtle; border-radius: 8px; color: @text_primary; transition: all 300ms ease; }}
spinbutton:focus-within {{ border-color: @border_active; box-shadow: 0 0 14px rgba({ab},0.12); }}
spinbutton > button {{ background-color: rgba({ab},0.04); border: none; border-radius: 0; color: @amber; min-width: 30px; transition: all 220ms ease; }}
spinbutton > button:hover {{ background-color: rgba({ab},0.14); }}
checkbutton indicator {{ background-color: @bg_input; border: 1.5px solid rgba({ab},0.22); border-radius: 5px; min-width: 22px; min-height: 22px; transition: all 300ms cubic-bezier(0.22,1,0.36,1); }}
checkbutton indicator:checked {{ background-color: rgba({ab},0.18); border-color: @amber; color: @amber; }}
checkbutton indicator:hover {{ border-color: rgba({ab},0.45); }}
combobox > button, comboboxtext > button {{ background-color: @bg_input; border: 1px solid @border_subtle; border-radius: 8px; color: @text_primary; padding: 6px 12px; transition: all 300ms ease; }}
combobox > button:hover, comboboxtext > button:hover {{ border-color: rgba({ab},0.32); }}
popover.menu, popover, popover.background {{ background-color: {popup_bg}; border: 1px solid rgba({ab},0.18); border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,{'0.65' if dark else '0.12'}); color: @text_primary; animation: fade-slide-in 200ms cubic-bezier(0.22,1,0.36,1); }}
popover > contents {{ background-color: {popup_bg}; border-radius: 12px; border: none; padding: 4px; }}
popover modelbutton, popover .model {{ color: @text_primary; padding: 7px 14px; border-radius: 8px; transition: all 220ms ease; }}
popover modelbutton:hover, popover .model:hover {{ background-color: rgba({ab},0.10); color: @amber; }}
dropdown > popover > contents {{ background-color: {popup_bg}; border: none; padding: 2px; }}
dropdown > popover > contents listview {{ background-color: transparent; color: @text_primary; }}
dropdown > popover > contents listview > row {{ background-color: transparent; color: @text_primary; padding: 7px 14px; border-radius: 8px; transition: all 220ms ease; }}
dropdown > popover > contents listview > row:hover {{ background-color: rgba({ab},0.10); color: @amber; }}
dropdown > popover > contents listview > row:selected {{ background-color: rgba({ab},0.16); color: @amber; }}
dropdown > button {{ background-color: @bg_input; border: 1px solid @border_subtle; border-radius: 8px; color: @text_primary; padding: 6px 12px; transition: all 300ms ease; }}
dropdown > button:hover {{ border-color: rgba({ab},0.32); }}
combobox window.popup, comboboxtext window.popup {{ background-color: {popup_bg}; border: 1px solid rgba({ab},0.18); border-radius: 10px; box-shadow: 0 10px 40px rgba(0,0,0,{'0.65' if dark else '0.12'}); }}
combobox window.popup > frame, comboboxtext window.popup > frame {{ background-color: {popup_bg}; border: none; border-radius: 10px; }}
treeview.view {{ background-color: transparent; color: @text_primary; }}
treeview.view:hover {{ background-color: rgba({ab},0.10); color: @amber; }}
treeview.view:selected {{ background-color: rgba({ab},0.16); color: @amber; }}
cellview {{ background-color: transparent; color: @text_primary; }}
menu {{ background-color: {popup_bg}; border: 1px solid rgba({ab},0.14); border-radius: 10px; padding: 4px; box-shadow: 0 8px 32px rgba(0,0,0,{'0.60' if dark else '0.10'}); }}
menu menuitem {{ color: @text_primary; padding: 7px 14px; border-radius: 8px; transition: all 220ms ease; }}
menu menuitem:hover {{ background-color: rgba({ab},0.10); color: @amber; }}
list, listview {{ background-color: transparent; }}
list > row, listview > row {{ background-color: transparent; color: @text_primary; transition: all 200ms ease; }}
list > row:hover, listview > row:hover {{ background-color: rgba({ab},0.05); }}
list > row:selected, listview > row:selected {{ background-color: rgba({ab},0.10); color: @amber; }}
colorbutton button {{ border: 1px solid rgba({ab},0.16); border-radius: 8px; padding: 2px; transition: all 300ms ease; }}
colorbutton button:hover {{ border-color: rgba({ab},0.45); }}

notebook {{ background-color: transparent; }}
notebook > header {{ background-color: {tab_bg}; border-bottom: 1px solid rgba({ab},0.06); }}
notebook > header > tabs > tab {{ background-color: transparent; color: @text_secondary; border: none; border-bottom: 2px solid transparent; padding: 11px 22px; font-weight: 500; transition: all 380ms cubic-bezier(0.22,1,0.36,1); }}
notebook > header > tabs > tab:hover {{ color: @amber; background-color: rgba({ab},0.04); }}
notebook > header > tabs > tab:checked {{ color: @amber; border-bottom-color: @amber; background-color: rgba({ab},0.06); }}
notebook > stack {{ background-color: transparent; }}

frame {{ background-color: @bg_card; border: 1px solid @border_subtle; border-radius: 14px; padding: 2px; transition: all 380ms cubic-bezier(0.22,1,0.36,1); }}
frame:hover {{ border-color: rgba({ab},0.20); }}
frame > label {{ color: @amber; font-weight: 600; font-size: 0.9em; padding: 0 8px; }}
expander title {{ color: @text_primary; font-weight: 500; padding: 7px 6px; border-radius: 8px; transition: all 300ms ease; }}
expander title:hover {{ color: @amber; background-color: rgba({ab},0.03); }}
expander title:checked {{ color: @amber; }}
expander arrow {{ color: @amber; transition: all 380ms cubic-bezier(0.22,1,0.36,1); min-width: 16px; min-height: 16px; }}
expander arrow:checked {{ color: @teal; }}
separator {{ background-color: transparent; min-height: 1px; margin-top: 5px; margin-bottom: 5px; background-image: linear-gradient(90deg, transparent 0%, rgba({ab},0.16) 12%, rgba({ar},0.10) 50%, rgba({at},0.12) 85%, transparent 100%); }}

flowbox {{ background-color: transparent; }}
flowboxchild {{ background-color: transparent; background-image: none; border-radius: 12px; padding: 3px; transition: opacity 450ms cubic-bezier(0.22,1,0.36,1), all 350ms cubic-bezier(0.22,1,0.36,1); }}
flowboxchild:hover, flowboxchild:focus, flowboxchild:active, flowboxchild:selected {{ background-color: transparent; background-image: none; outline: none; box-shadow: none; }}

stack {{ transition-duration: 450ms; }}
.left-panel {{
    background-color: {panel_bg};
    border-right: 1px solid {left_bdr};
    box-shadow: 8px 0 28px rgba(0,0,0,{'0.22' if dark else '0.05'});
}}
.content-surface {{ background-color: {'rgba(10,12,24,0.40)' if dark else 'rgba(247,244,239,0.40)'}; border-radius: 18px; border: 1px solid rgba({ab},0.05); }}
.settings-surface {{ background-color: {'rgba(10,12,24,0.40)' if dark else 'rgba(247,244,239,0.40)'}; border-radius: 16px; border: 1px solid rgba({ab},0.05); padding: 2px; }}
.category-header {{ padding: 10px 12px; border-radius: 12px; margin-top: 8px; margin-start: 10px; }}
.category-header label {{ color: @amber; font-weight: 700; letter-spacing: 0.8px; }}
.category-header image {{ opacity: 0.75; }}
.category-slide {{ animation: category-slide-in 500ms cubic-bezier(0.22,1,0.36,1) backwards; }}
.category-slide-out {{ animation: category-slide-out 400ms cubic-bezier(0.22,1,0.36,1) forwards; }}

.plugin-row {{ padding: 8px 10px; margin: 2px 4px; border-radius: 14px; transition: all 260ms cubic-bezier(0.22,1,0.36,1); background-color: rgba({ab},0.020); background-image: none; border: 1px solid rgba({ab},0.055); min-height: 58px; }}
.plugin-row.card-animate {{ animation: plugin-entrance 420ms cubic-bezier(0.22,1,0.36,1) backwards; }}
.plugin-row:hover {{ background-color: rgba({ab},0.070); border-color: rgba({ab},0.20); box-shadow: 0 6px 22px rgba(0,0,0,{'0.20' if dark else '0.06'}); }}
.plugin-row.plugin-enabled {{ background-color: rgba({ab},0.040); border-color: rgba({ab},0.13); }}
.plugin-row.plugin-protected {{ border-color: rgba({at},0.16); }}
.plugin-row button.flat {{ transition: all 260ms cubic-bezier(0.22,1,0.36,1); background-image: none; padding: 4px 6px; }}
.plugin-row button.flat:hover {{ background-color: transparent; background-image: none; border-color: transparent; box-shadow: none; text-shadow: 0 0 8px rgba({ab},0.22); }}
.plugin-row label {{ font-weight: 500; }}
.plugin-name {{ color: @text_primary; font-weight: 700; }}
.plugin-meta {{ color: @text_secondary; font-size: 0.82em; font-weight: 400; }}
.plugin-subrow {{ margin-top: 1px; }}
.status-pill {{ color: @text_secondary; border: 1px solid rgba({ab},0.10); border-radius: 999px; padding: 1px 7px; font-size: 0.68em; font-weight: 800; letter-spacing: 0.8px; margin-start: 8px; }}
.status-pill.enabled {{ color: @amber_light; background-color: rgba({ab},0.10); border-color: rgba({ab},0.25); }}
.status-pill.locked, .status-pill.shell {{ color: @teal; background-color: rgba({at},0.09); border-color: rgba({at},0.25); }}

.plugin-title {{ color: {'#ffffff' if dark else '#1a1510'}; font-weight: 700; }}
.plugin-desc {{ color: @text_secondary; font-weight: 400; }}
.option-row {{ padding: 7px 10px; border-radius: 11px; transition: all 220ms ease; border-left: 2px solid transparent; }}
.option-row.row-reveal {{ animation: settings-reveal 300ms cubic-bezier(0.22,1,0.36,1) backwards; }}
.option-row:hover {{ background-color: rgba({ab},0.035); }}
.option-row.is-modified {{ background-color: rgba({ab},0.045); border-left-color: rgba({ab},0.65); }}
.option-label {{ color: @text_secondary; font-weight: 500; transition: all 220ms ease; }}
.option-row:hover .option-label, .option-row.is-modified .option-label {{ color: @text_primary; }}

.reset-btn {{ background-color: transparent; border: 1px solid rgba({ar},0.10); border-radius: 8px; color: @rose; padding: 4px 8px; min-width: 30px; min-height: 30px; transition: all 240ms ease; }}
.reset-btn.is-default {{ opacity: 0.42; }}
.reset-btn:hover {{ background-color: rgba({ar},0.10); border-color: rgba({ar},0.40); opacity: 1; }}
.grab-btn {{ background-color: rgba({at},0.05); border: 1px solid rgba({at},0.16); color: @teal; font-weight: 700; min-width: 38px; transition: all 300ms ease; }}
.grab-btn:hover {{ background-color: rgba({at},0.12); border-color: rgba({at},0.45); }}
.add-btn {{ background-color: rgba({at},0.05); border: 1px solid rgba({at},0.16); color: @success; transition: all 300ms ease; }}
.add-btn:hover {{ background-color: rgba({at},0.12); border-color: rgba({at},0.45); }}
.fab-add {{ background-color: {bg_card}; border: 1px solid rgba({at},0.30); border-radius: 11px; color: @success; min-width: 40px; min-height: 40px; padding: 4px; margin: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.35); transition: all 300ms ease; }}
.fab-add:hover {{ background-color: rgba({at},0.16); border-color: rgba({at},0.60); }}
.remove-btn {{ background-color: rgba({ar},0.03); border: 1px solid rgba({ar},0.10); color: @danger; min-width: 30px; transition: all 300ms ease; }}
.remove-btn:hover {{ background-color: rgba({ar},0.10); border-color: rgba({ar},0.40); }}
.run-btn {{ background-color: rgba({at},0.03); border: 1px solid rgba({at},0.10); color: @success; transition: all 300ms ease; }}
.run-btn:hover {{ background-color: rgba({at},0.10); border-color: rgba({at},0.35); }}
.action-btn {{ padding: 11px 22px; border-radius: 12px; font-weight: 600; letter-spacing: 0.1px; }}
.side_toggle_btn {{ min-height: 38px; border-radius: 11px; }}
.side_toggle_btn image {{ -gtk-icon-size: 18px; }}
.action-btn.close-btn {{ background-color: rgba({ar},0.04); border-color: rgba({ar},0.12); color: @rose; }}
.action-btn.close-btn:hover {{ background-color: rgba({ar},0.10); border-color: rgba({ar},0.40); color: @danger; }}
.action-btn.back-btn {{ background-color: rgba({at},0.04); border-color: rgba({at},0.12); color: @teal; }}
.action-btn.back-btn:hover {{ background-color: rgba({at},0.10); border-color: rgba({at},0.40); color: @teal; }}
.grab-dialog {{ background-color: {popup_bg}; }}
.grab-dialog label {{ color: @amber; font-weight: 500; font-size: 1.1em; padding: 28px; }}
.binding-frame {{ background-color: {'rgba(14,18,34,0.60)' if dark else 'rgba(255,255,255,0.50)'}; border: 1px solid rgba({ab},0.05); border-radius: 14px; margin-top: 3px; margin-bottom: 3px; transition: all 380ms cubic-bezier(0.22,1,0.36,1); }}
.binding-frame:hover {{ border-color: rgba({ab},0.18); }}
tooltip {{ background-color: {popup_bg}; border: 1px solid rgba({ab},0.18); border-radius: 10px; color: @text_primary; box-shadow: 0 6px 24px rgba(0,0,0,{'0.55' if dark else '0.10'}); }}
tooltip label {{ color: @text_primary; }}
.enabled-toggle {{ padding: 9px 20px; border-radius: 14px; background-color: rgba({ab},0.03); border: 1px solid rgba({ab},0.06); transition: all 380ms ease; }}
.enabled-toggle:hover {{ background-color: rgba({ab},0.06); border-color: rgba({ab},0.20); }}
.enabled-toggle label {{ font-weight: 600; color: @text_secondary; }}
.subgroup-frame {{ background-color: {'rgba(12,16,32,0.42)' if dark else 'rgba(255,255,255,0.40)'}; border: 1px solid rgba({ab},0.04); border-radius: 14px; margin: 5px 0; }}
.subgroup-frame:hover {{ border-color: rgba({ab},0.12); }}
.filter-label {{ }}
.filter-hidden {{ opacity: 0; transition: none !important; }}
.theme-switch-box {{ padding: 6px 14px; border-radius: 10px; background-color: rgba({ab},0.03); border: 1px solid rgba({ab},0.06); }}
.theme-switch-box label {{ font-size: 0.85em; color: @text_secondary; }}
.preset-section {{ padding: 8px 14px; margin-top: 6px; }}
.preset-section label {{ font-size: 0.85em; }}
.preset-header {{ color: @amber; font-weight: 700; letter-spacing: 0.6px; font-size: 0.80em; margin-bottom: 4px; }}
.preset-combo > button {{ background-color: @bg_input; border: 1px solid rgba({ab},0.10); border-radius: 8px; padding: 5px 10px; font-size: 0.9em; }}
.preset-combo > button:hover {{ border-color: rgba({ab},0.32); }}
.preset-btn-box button {{ padding: 4px 10px; font-size: 0.80em; min-height: 26px; border-radius: 8px; }}
.preset-save {{ background-color: rgba({at},0.06); border: 1px solid rgba({at},0.16); color: @success; }}
.preset-save:hover {{ background-color: rgba({at},0.14); border-color: rgba({at},0.45); }}
.preset-load {{ background-color: rgba({ab},0.06); border: 1px solid rgba({ab},0.12); color: @amber_light; }}
.preset-load:hover {{ background-color: rgba({ab},0.14); border-color: rgba({ab},0.38); }}
.preset-delete {{ background-color: rgba({ar},0.04); border: 1px solid rgba({ar},0.10); color: @rose; }}
.preset-delete:hover {{ background-color: rgba({ar},0.10); border-color: rgba({ar},0.40); }}
.output-warn {{ color: @amber; font-size: 0.85em; margin-top: 2px; }}
.output-error {{ color: @danger; font-weight: 600; font-size: 0.85em; margin-top: 2px; }}

window.confirm-window {{ background-color: {panel_bg}; }}
.confirm-card {{ background-color: {panel_bg}; border: 1px solid rgba({ab},0.22); border-radius: 16px; box-shadow: 0 18px 50px rgba(0,0,0,{'0.65' if dark else '0.18'}); }}
.confirm-title {{ color: {'#ffffff' if dark else '#1a1510'}; font-weight: 700; font-size: 1.12em; }}
.confirm-countbox {{ background-color: @bg_input; border: 1px solid rgba({ab},0.14); border-radius: 14px; }}
.confirm-count {{ color: @amber_light; font-weight: 800; font-size: 2.6em; }}
.confirm-detail {{ color: @text_secondary; font-size: 0.95em; }}
.confirm-keep {{ background-color: rgba({ab},0.22); border: 1px solid @amber; color: @text_primary; font-weight: 700; }}
.confirm-keep:hover {{ background-color: rgba({ab},0.34); border-color: @amber; color: @text_primary; }}
.confirm-close {{ background-color: transparent; border-color: transparent; padding: 2px 8px; }}
.confirm-close:hover {{ background-color: rgba({ab},0.14); border-color: transparent; }}

.ini-panel {{ background-color: {ini_bg}; border-left: 1px solid {ini_border}; box-shadow: -10px 0 30px rgba(0,0,0,{'0.26' if dark else '0.07'}); }}
.ini-header {{ padding: 10px 14px; border-bottom: 1px solid {ini_hdr_border}; background-image: linear-gradient(180deg, {ini_grad_a}, {ini_grad_b}); }}
.ini-dot {{ color: {ini_accent}; font-size: 0.7em; animation: ini-pulse 1.7s ease-in-out infinite; }}
.ini-title {{ color: {ini_fg}; font-family: monospace; font-weight: 600; font-size: 0.95em; letter-spacing: 0.3px; }}
.ini-live {{ color: {ini_accent}; font-family: monospace; font-size: 0.66em; font-weight: 800; letter-spacing: 2px; opacity: 0.82; }}
.ini-scroll {{ background-color: transparent; }}
.ini-body {{ padding: 8px 0 44px 0; font-family: monospace; }}
.ini-line {{ padding: 1px 12px 1px 6px; border-left: 2px solid transparent; }}
.ini-gutter {{ color: {ini_gutter}; font-family: monospace; font-size: 0.82em; margin-right: 10px; }}
.ini-text {{ font-family: monospace; font-size: 0.88em; }}
@keyframes ini-pulse {{ 0% {{ opacity: 0.3; }} 50% {{ opacity: 1; }} 100% {{ opacity: 0.3; }} }}
@keyframes ini-hot {{ 0% {{ background-color: {ini_hot_a}; }} 60% {{ background-color: {ini_hot_b}; }} 100% {{ background-color: transparent; }} }}
.ini-hot {{ border-left: 2px solid {ini_hot}; animation: ini-hot 1.35s cubic-bezier(0.22,1,0.36,1); }}
.wiki-back {{ background-color: rgba({at},0.07); border: 1px solid rgba({at},0.20); color: @teal; border-radius: 8px; padding: 3px 10px; font-weight: 600; }}
.wiki-back:hover {{ background-color: rgba({at},0.15); border-color: rgba({at},0.48); }}
.wiki-nav {{ background-color: transparent; border: 1px solid rgba({at},0.12); color: @text_secondary; border-radius: 8px; min-width: 26px; min-height: 26px; padding: 2px; }}
.wiki-nav:hover {{ background-color: rgba({at},0.10); color: @teal; border-color: rgba({at},0.35); }}
.wiki-fallback {{ color: @text_secondary; }}
.side-rail {{ background-color: rgba({ab},0.02); border-left: 1px solid rgba({at},0.10); }}
.side-toggle {{ min-width: 26px; min-height: 30px; padding: 4px 3px; font-size: 1.15em; font-weight: 700; color: @text_secondary; }}
.side-toggle:hover {{ background-color: rgba({at},0.12); color: @teal; border-color: rgba({at},0.40); }}
.thin-back-btn {{ margin-bottom: 10px; margin-start: 5px; margin-end: 5px; min-width: 34px; min-height: 34px; border-radius: 11px; color: @amber_light; transition: opacity 180ms ease; }}
.thin-back-btn:hover {{ background-color: rgba({ab},0.14); border-color: rgba({ab},0.38); color: @text_primary; }}
.thin-brand {{ padding: 8px 0; border-radius: 18px; animation: rail-glow 4.4s ease-in-out infinite; }}
.thin-brand-letter {{ color: @amber; font-weight: 800; font-size: 0.86em; letter-spacing: 0.8px; opacity: 0.92; text-shadow: 0 0 10px rgba({ab},0.20); padding: 1px 0; }}
.thin-brand-badge {{ opacity: 0.96; animation: rail-glow 4.4s ease-in-out infinite; }}
.thin-brand-icon {{ opacity: 0.95; margin-top: 3px; margin-bottom: 3px; }}
.stagger-0 {{ animation-delay: 0ms; }}
.stagger-1 {{ animation-delay: 45ms; }}
.stagger-2 {{ animation-delay: 90ms; }}
.stagger-3 {{ animation-delay: 135ms; }}
.stagger-4 {{ animation-delay: 180ms; }}
.stagger-5 {{ animation-delay: 225ms; }}
.stagger-6 {{ animation-delay: 270ms; }}
.stagger-7 {{ animation-delay: 315ms; }}
"""


_css_provider = None


def _system_prefers_dark(default=True):
    """Best-effort system light/dark detection.

    Important detail: GNOME/GTK commonly reports light mode as ``default``,
    not ``prefer-light``. Treat ``default`` as light so the app can update from
    dark back to light while it is still open.
    """
    # GNOME / xdg-desktop-portal compatible preference.
    try:
        gs = Gio.Settings.new("org.gnome.desktop.interface")
        scheme = (gs.get_string("color-scheme") or "").strip().strip("'\"").lower()
        if "prefer-dark" in scheme:
            return True
        if "prefer-light" in scheme or scheme in ("default", ""):
            return False
    except Exception:
        pass

    # Shell fallback for systems where Gio.Settings cannot load the schema.
    try:
        r = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if r.returncode == 0:
            scheme = (r.stdout or "").strip().strip("'\"").lower()
            if "prefer-dark" in scheme:
                return True
            if "prefer-light" in scheme or scheme in ("default", ""):
                return False
    except Exception:
        pass

    settings = Gtk.Settings.get_default()
    if settings is not None:
        # Theme-name fallback, useful on non-GNOME GTK desktops.
        try:
            theme = (settings.get_property("gtk-theme-name") or "").lower()
            if "dark" in theme:
                return True
            if "light" in theme:
                return False
        except Exception:
            pass

    # Do not use gtk-application-prefer-dark-theme as a detection fallback here.
    # WCM sets that property itself when applying the theme for WebKit, so using
    # it as input can trap the app in dark mode until restart.
    return bool(default)


def _apply_theme(dark=True):
    global _css_provider, _INI_DARK
    _INI_DARK = dark
    display = Gdk.Display.get_default()
    if display is None:
        return
    if _css_provider:
        Gtk.StyleContext.remove_provider_for_display(display, _css_provider)
    _css_provider = Gtk.CssProvider()
    _css_provider.load_from_data(_make_css(dark).encode("utf-8"))
    Gtk.StyleContext.add_provider_for_display(
        display, _css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 100
    )
    # Let embedded WebKit pages follow the same light/dark choice as the app.
    # The app still *detects* the system theme; this just advertises the chosen
    # preference to embedded pages that honour prefers-color-scheme.
    settings = Gtk.Settings.get_default()
    if settings is not None:
        try:
            settings.set_property("gtk-application-prefer-dark-theme", dark)
        except Exception:
            pass


def parse_color(color_str):
    rgba = Gdk.RGBA()
    if color_str is None:
        rgba.red = rgba.green = rgba.blue = 0.0
        rgba.alpha = 1.0
        return rgba
    s = str(color_str).strip()
    if not s:
        rgba.red = rgba.green = rgba.blue = 0.0
        rgba.alpha = 1.0
        return rgba
    if s.startswith(r"\#"):
        s = s[1:]
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1].strip()
    if s.startswith(r"\#"):
        s = s[1:]
    if not s.startswith("#"):
        for sep in (" ;", "\t;", " #"):
            if sep in s:
                s = s.split(sep, 1)[0].strip()
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 6:
            h += "FF"
        if len(h) == 8:
            try:
                rgba.red = int(h[0:2], 16) / 255.0
                rgba.green = int(h[2:4], 16) / 255.0
                rgba.blue = int(h[4:6], 16) / 255.0
                rgba.alpha = int(h[6:8], 16) / 255.0
                return rgba
            except ValueError:
                pass
    parts = s.split()
    if len(parts) == 3:
        parts.append("1.0")
    if len(parts) == 4:
        try:
            rgba.red = max(0, min(1, float(parts[0])))
            rgba.green = max(0, min(1, float(parts[1])))
            rgba.blue = max(0, min(1, float(parts[2])))
            rgba.alpha = max(0, min(1, float(parts[3])))
            return rgba
        except ValueError:
            pass
    rgba.red = rgba.green = rgba.blue = 0.0
    rgba.alpha = 1.0
    return rgba


def color_to_str(rgba):
    return f"{rgba.red:.4f} {rgba.green:.4f} {rgba.blue:.4f} {rgba.alpha:.4f}"


_GDK_TO_LINUX = {
    Gdk.KEY_Escape: "KEY_ESC",
    Gdk.KEY_Return: "KEY_ENTER",
    Gdk.KEY_KP_Enter: "KEY_ENTER",
    Gdk.KEY_Tab: "KEY_TAB",
    Gdk.KEY_BackSpace: "KEY_BACKSPACE",
    Gdk.KEY_Delete: "KEY_DELETE",
    Gdk.KEY_Insert: "KEY_INSERT",
    Gdk.KEY_Home: "KEY_HOME",
    Gdk.KEY_End: "KEY_END",
    Gdk.KEY_Page_Up: "KEY_PAGEUP",
    Gdk.KEY_Page_Down: "KEY_PAGEDOWN",
    Gdk.KEY_Left: "KEY_LEFT",
    Gdk.KEY_Right: "KEY_RIGHT",
    Gdk.KEY_Up: "KEY_UP",
    Gdk.KEY_Down: "KEY_DOWN",
    Gdk.KEY_space: "KEY_SPACE",
    Gdk.KEY_Pause: "KEY_PAUSE",
    Gdk.KEY_Print: "KEY_SYSRQ",
    Gdk.KEY_Scroll_Lock: "KEY_SCROLLLOCK",
    Gdk.KEY_Caps_Lock: "KEY_CAPSLOCK",
    Gdk.KEY_Num_Lock: "KEY_NUMLOCK",
}
for i in range(1, 13):
    _GDK_TO_LINUX[getattr(Gdk, f"KEY_F{i}")] = f"KEY_F{i}"
for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    _GDK_TO_LINUX[getattr(Gdk, f"KEY_{c.lower()}")] = f"KEY_{c}"
    _GDK_TO_LINUX[getattr(Gdk, f"KEY_{c}")] = f"KEY_{c}"
for c in "0123456789":
    _GDK_TO_LINUX[getattr(Gdk, f"KEY_{c}")] = f"KEY_{c}"
_MODIFIER_KEYVALS = {
    Gdk.KEY_Shift_L,
    Gdk.KEY_Shift_R,
    Gdk.KEY_Control_L,
    Gdk.KEY_Control_R,
    Gdk.KEY_Alt_L,
    Gdk.KEY_Alt_R,
    Gdk.KEY_Meta_L,
    Gdk.KEY_Meta_R,
    Gdk.KEY_Super_L,
    Gdk.KEY_Super_R,
    Gdk.KEY_ISO_Level3_Shift,
}


def _keyval_to_linux(kv):
    n = _GDK_TO_LINUX.get(kv)
    if n:
        return n
    g = Gdk.keyval_name(kv)
    return "KEY_" + g.upper() if g else None


def _make_window_cover_all_surfaces(win, parent=None):
    """Make the key-grab window a real fullscreen toplevel.

    This follows the behavior that works in the C++ WCM: use a normal
    independent GTK toplevel and call Gtk.Window.fullscreen(). Do not fake
    fullscreen by setting output-sized geometry, and do not make the grab window
    transient/modal.
    """
    try:
        win.set_decorated(False)
    except Exception:
        pass
    try:
        win.set_focusable(True)
    except Exception:
        pass

    root = None
    try:
        root = parent.get_root() if parent is not None else None
    except Exception:
        root = None

    # Keep the window associated with the app if possible, but do not make it a
    # transient/modal dialog. On Wayland, fullscreening a dialog can be handled
    # differently by the compositor.
    try:
        app = root.get_application() if root is not None else None
        if app is not None:
            win.set_application(app)
    except Exception:
        pass

    try:
        win.fullscreen()
    except Exception as e:
        print(f"WCM: Gtk.Window.fullscreen() failed for grab overlay: {e}")
    return False


class KeyGrabWindow(Gtk.Window):
    def __init__(s, parent):
        super().__init__(
            title=_("Waiting for Binding"),
            default_width=420,
            default_height=130,
        )
        s.result = ""
        s._mods = set()
        s._done = False
        s.add_css_class("grab-dialog")

        # Behave like C++ WCM: a normal independent toplevel that requests real
        # Gtk.Window.fullscreen().
        s._using_layer_shell = False
        _make_window_cover_all_surfaces(s, parent)

        s._label = Gtk.Label(label=_("Press a key combination…\n(Escape to cancel)"))
        s._label.set_halign(Gtk.Align.CENTER)
        s._label.set_valign(Gtk.Align.CENTER)
        s._label.set_hexpand(True)
        s._label.set_vexpand(True)
        s.set_child(s._label)

        kc = Gtk.EventControllerKey()
        kc.connect("key-pressed", s._on_kp)
        kc.connect("key-released", s._on_kr)
        s.add_controller(kc)

        cl = Gtk.GestureClick()
        cl.set_button(0)
        cl.connect("pressed", s._on_cl)
        s.add_controller(cl)

        # Re-assert fullscreen after the surface exists. This avoids the common
        # GTK/Wayland race where fullscreen called before map is ignored.
        s.connect("realize", lambda *_: s._ensure_covering())
        s.connect("map", lambda *_: s._ensure_covering())
        GLib.idle_add(s._ensure_covering)
        GLib.timeout_add(120, s._ensure_covering)
        GLib.timeout_add(350, s._ensure_covering)

    def _ensure_covering(s):
        try:
            s.fullscreen()
        except Exception:
            pass
        try:
            s.present()
        except Exception:
            pass
        return False

    def _ms(s):
        p = []
        if s._mods & {Gdk.KEY_Super_L, Gdk.KEY_Super_R, Gdk.KEY_Meta_L, Gdk.KEY_Meta_R}:
            p.append("<super>")
        if s._mods & {Gdk.KEY_Control_L, Gdk.KEY_Control_R}:
            p.append("<ctrl>")
        if s._mods & {Gdk.KEY_Alt_L, Gdk.KEY_Alt_R, Gdk.KEY_ISO_Level3_Shift}:
            p.append("<alt>")
        if s._mods & {Gdk.KEY_Shift_L, Gdk.KEY_Shift_R}:
            p.append("<shift>")
        return " ".join(p)

    def _on_kp(s, ctrl, kv, kc, st):
        if kv == Gdk.KEY_Escape and not s._mods:
            s.close()
            return True
        if kv in _MODIFIER_KEYVALS:
            s._mods.add(kv)
            s._label.set_text(s._ms() or _("(No modifiers)"))
            return True
        kn = _keyval_to_linux(kv)
        if kn:
            s.result = (s._ms() + " " + kn).strip()
            s._done = True
            s.close()
        return True

    def _on_kr(s, ctrl, kv, kc, st):
        s._mods.discard(kv)
        s._label.set_text(s._ms() or _("Press a key combination…"))

    def _on_cl(s, g, n, x, y):
        bm = {
            1: "BTN_LEFT",
            2: "BTN_MIDDLE",
            3: "BTN_RIGHT",
            8: "BTN_SIDE",
            9: "BTN_EXTRA",
        }
        bn = bm.get(g.get_current_button())
        if bn:
            s.result = (s._ms() + " " + bn).strip()
            s._done = True
            s.close()


_wf_icon_dir = None
_wcm_icon_dir = None
_xdg_icon_dir = None
_icons_resolved = False


def _resolve_icon_dirs():
    global _xdg_icon_dir, _wf_icon_dir, _wcm_icon_dir, _icons_resolved
    if _icons_resolved:
        return
    _icons_resolved = True
    xdg = os.environ.get("XDG_DATA_HOME", "") or os.path.join(
        os.path.expanduser("~"), ".local", "share"
    )
    _xdg_icon_dir = os.path.join(xdg, "wayfire", "icons")
    try:
        r = subprocess.run(
            ["pkg-config", "--variable=icondir", "wayfire"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            _wf_icon_dir = r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    for b in ("wcm", "wayfire"):
        p = shutil.which(b)
        if p:
            d = os.path.join(
                os.path.dirname(os.path.dirname(os.path.realpath(p))),
                "share",
                "wcm",
                "icons",
            )
            if os.path.isdir(d):
                _wcm_icon_dir = d
                break
    if not _wcm_icon_dir:
        try:
            r = subprocess.run(
                ["pkg-config", "--variable=prefix", "wayfire"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if r.returncode == 0:
                d = os.path.join(r.stdout.strip(), "share", "wcm", "icons")
                if os.path.isdir(d):
                    _wcm_icon_dir = d
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    if not _wcm_icon_dir:
        sd = os.path.dirname(os.path.abspath(__file__))
        for rel in (
            "icons/plugins",
            "icons",
            "../icons/plugins",
            "../wcm/icons/plugins",
            "../wcm/icons",
        ):
            d = os.path.normpath(os.path.join(sd, rel))
            if os.path.isdir(d) and os.path.isfile(os.path.join(d, "plugin-core.svg")):
                _wcm_icon_dir = d
                break
    if not _wcm_icon_dir:
        for root in ("/usr/share", "/usr/local/share", "/opt"):
            try:
                r = subprocess.run(
                    [
                        "find",
                        root,
                        "-maxdepth",
                        "5",
                        "-name",
                        "plugin-core.svg",
                        "-type",
                        "f",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                for l in (r.stdout or "").strip().splitlines():
                    d = os.path.dirname(l.strip())
                    if d:
                        _wcm_icon_dir = d
                        break
                if _wcm_icon_dir:
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass


def find_icon(name):
    _resolve_icon_dirs()
    for d in (_xdg_icon_dir, _wf_icon_dir, _wcm_icon_dir):
        if d:
            p = os.path.join(d, name)
            if os.path.isfile(p):
                return p
    for pfx in ("/usr", "/usr/local", os.path.expanduser("~/.local")):
        p = os.path.join(pfx, "share", "wayfire", "icons", name)
        if os.path.isfile(p):
            return p
    return ""


def find_plugin_icon(pn):
    for n in (pn, pn.replace("_", "-"), pn.replace("-", "_")):
        p = find_icon(f"plugin-{n}.svg")
        if p:
            return p
    return None


def find_app_icon():
    return find_icon("wcm.svg") or None


# Category names come from CATEGORIES below and are looked up with _() at
# display time; N_() marks them for xgettext extraction without translating
# the keys themselves (they must stay English to match plugin metadata).
def N_(x):
    return x


_CATEGORY_TRANSLATIONS = (
    N_("General"), N_("Accessibility"), N_("Desktop"), N_("Shell"),
    N_("Effects"), N_("Window Management"), N_("Utility"), N_("Other"),
    N_("Uncategorized"),
)

CATEGORIES = [
    ("General", "preferences-system"),
    ("Accessibility", "preferences-desktop-accessibility"),
    ("Desktop", "preferences-desktop"),
    ("Shell", "user-desktop"),
    ("Effects", "applications-graphics"),
    ("Window Management", "applications-accessories"),
    ("Utility", "applications-other"),
    ("Other", "applications-other"),
]
CATEGORY_NAMES = [c[0] for c in CATEGORIES]


def get_category_index(cat):
    for i, (n, _icon) in enumerate(CATEGORIES):
        if n == cat:
            return i
    return len(CATEGORIES) - 1


def get_config_path(config_override=None):
    if config_override:
        return os.path.expanduser(config_override)

    # WAYFIRE_CONFIG_FILE is set by Wayfire. Read it, but do not set it from
    # pywcm. If it points to a usable file, follow it; otherwise fall back to
    # the normal user config path.
    ov = os.environ.get("WAYFIRE_CONFIG_FILE")
    if ov:
        ep = os.path.expanduser(ov)
        if os.path.isfile(ep):
            return ep

    ch = os.environ.get("XDG_CONFIG_HOME", "") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    p = os.path.join(ch, "wayfire", "wayfire.ini")
    return p if os.path.isfile(p) else os.path.join(ch, "wayfire.ini")


def get_wfshell_config_path(config_override=None):
    """Get the wf-shell config file path (separate from wayfire.ini)."""
    ov = os.environ.get("WF_SHELL_CONFIG_FILE")
    if ov:
        return os.path.expanduser(ov)
    ch = os.environ.get("XDG_CONFIG_HOME", "") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    # wf-shell looks in these locations
    p = os.path.join(ch, "wf-shell.ini")
    if os.path.isfile(p):
        return p
    p = os.path.join(ch, "wayfire", "wf-shell.ini")
    if os.path.isfile(p):
        return p
    # Default — create alongside wayfire.ini
    wf_path = get_config_path(config_override)
    return os.path.join(os.path.dirname(wf_path), "wf-shell.ini")


LABEL_W = 200
BINDING_PREFIXES = ("binding_", "repeatable_binding_", "always_binding_", "release_binding_")


def _preset_error(parent, error):
    _operation_error(parent, _("Preset operation failed"), error)


def _operation_error(parent, title, error):
    print(f"WCM: {title}: {error}")
    if isinstance(parent, Gtk.Window):
        dialog = Gtk.MessageDialog(
            transient_for=parent, modal=True, buttons=Gtk.ButtonsType.CLOSE,
            message_type=Gtk.MessageType.ERROR, text=title,
            secondary_text=str(error))
        dialog.connect("response", lambda window, *_: window.destroy())
        dialog.present()


EXTRA_WIKI_PLUGINS = {
    'annotate', 'autorotate-iio', 'background-view', 'bench', 'crosshair',
    'extra-animations', 'focus-steal-prevent', 'follow-focus', 'force-fullscreen',
    'ghost', 'hide-cursor', 'keycolor', 'mag', 'obs', 'pin-view', 'showrepaint',
    'view-shot', 'water', 'winzoom', 'workspace-names',
}


def plugin_wiki_url(plg):
    if plg is not None and plg.type == PluginType.WF_SHELL:
        return 'https://github.com/WayfireWM/wf-shell'
    name = plg.name if plg is not None else ''
    repo = 'wayfire-plugins-extra' if name in EXTRA_WIKI_PLUGINS else 'wayfire'
    base = f'https://github.com/WayfireWM/{repo}/wiki/Configuration'
    # Plugin identifiers stay stable when display names are translated.
    return f'{base}#{name}' if name else base


def option_tooltip(opt):
    tip = opt.tooltip or ''
    if 'criteria' in opt.hints:
        tip += '\n\n' + _(
            'Window matching examples:\n'
            'all — every window; none — no windows\n'
            'type is "toplevel" — normal application windows\n'
            'app_id is "foot" — match an application\n'
            'title contains "Terminal" — match a window title\n'
            'Combine conditions with &, | and !, using parentheses.'
        )
    return tip.strip()


def _apply_tooltip(text, *widgets):
    """Apply XML <_long> text as a real tooltip on every useful hit target."""
    tip = (text or "").strip()
    if not tip:
        return
    for widget in widgets:
        if widget is None:
            continue
        try:
            widget.set_tooltip_text(tip)
        except Exception:
            pass


#: Seconds the "Confirm Display Changes" prompt waits before auto-reverting a
#: resolution, refresh-rate or rotation change that the user hasn't confirmed.
CONFIRM_TIMEOUT_SECONDS = 15


def _int(v, d):
    if v is not None:
        try:
            return int(v)
        except (ValueError, TypeError):
            pass
    return d if isinstance(d, int) else 0


def _parse_anim(s):
    parts = str(s).split()
    dur, easing = 300, "linear"
    if parts:
        try:
            dur = int(parts[0].replace("ms", ""))
        except ValueError:
            pass
    if len(parts) > 1:
        easing = parts[1]
    return dur, easing


class OptionWidget(Gtk.Box):
    def __init__(s, opt, cfg, plg, anim_index=0):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        s.option = opt
        s.config = cfg
        s.plugin = plg
        s._block = False
        s._text_save_id = 0
        s.add_css_class("option-row")
        s.add_css_class("row-reveal")
        s.add_css_class(f"stagger-{anim_index % 8}")
        s.set_margin_start(4)
        s.set_margin_end(4)
        s.set_margin_top(2)
        s.set_margin_bottom(2)
        s.lbl = Gtk.Label(label=opt.disp_name or opt.name)
        _apply_tooltip(option_tooltip(opt), s, s.lbl)
        s.lbl.set_size_request(LABEL_W, -1)
        s.lbl.set_xalign(0)
        s.lbl.set_hexpand(False)
        s.lbl.set_halign(Gtk.Align.START)
        s.lbl.add_css_class("option-label")
        s.append(s.lbl)
        s.end_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        s.end_box.set_hexpand(True)
        s.end_box.set_halign(Gtk.Align.FILL)
        _apply_tooltip(option_tooltip(opt), s.end_box)
        s.append(s.end_box)
        cur = cfg.get_option(plg.name, opt.name)
        s._build(opt, cur)
        _apply_tooltip(option_tooltip(opt), getattr(s, "ed", None))
        if opt.type in (OptionType.BOOL, OptionType.COLOR, OptionType.DOUBLE) or (
            opt.type == OptionType.INT and not opt.int_labels
        ):
            s.end_box.set_hexpand(True)
            s.end_box.set_halign(Gtk.Align.END)
        rb = Gtk.Button.new_from_icon_name("edit-clear")
        rb.set_tooltip_text(_("Reset to default"))
        rb.add_css_class("reset-btn")
        rb.connect("clicked", s._reset)
        s.end_box.append(rb)
        s.reset_btn = rb
        s._update_modified_state()

    def _build(s, opt, cur):
        ot = opt.type
        if ot == OptionType.INT:
            if opt.int_labels:
                s.ed = Gtk.ComboBoxText()
                for lb, v in opt.int_labels:
                    s.ed.append(str(v), lb)
                selected = str(_int(cur, opt.default_value))
                if selected not in {str(value) for _, value in opt.int_labels}:
                    s.ed.append(selected, selected)
                s.ed.set_active_id(selected)
                s.ed.connect("changed", lambda w: s._save(w.get_active_id() or "0"))
                s.ed.set_hexpand(True)
            else:
                adj = Gtk.Adjustment(
                    value=_int(cur, opt.default_value),
                    lower=opt.min_val,
                    upper=min(opt.max_val, 2**31 - 1),
                    step_increment=1,
                )
                s.ed = Gtk.SpinButton(adjustment=adj)
                s.ed.connect(
                    "value-changed", lambda w: s._save(str(w.get_value_as_int()))
                )
                s.ed.set_hexpand(False)
            s.end_box.append(s.ed)
        elif ot == OptionType.DOUBLE:
            try:
                v = float(cur) if cur else float(opt.default_value)
            except (ValueError, TypeError):
                v = 0.0
            dec = min(20, max(0, -Decimal(str(opt.precision)).normalize().as_tuple().exponent))
            adj = Gtk.Adjustment(
                value=v,
                lower=max(opt.min_val, -1e15),
                upper=min(opt.max_val, 1e15),
                step_increment=opt.precision,
            )
            s.ed = Gtk.SpinButton(adjustment=adj, digits=dec)
            s.ed.set_hexpand(False)
            s.ed.connect("value-changed", lambda w: s._save(str(w.get_value())))
            s.end_box.append(s.ed)
        elif ot == OptionType.BOOL:
            s.ed = Gtk.CheckButton()
            if cur is not None:
                s.ed.set_active(str(cur).strip().lower() in ("true", "1", "yes", "on"))
            else:
                s.ed.set_active(bool(opt.default_value))
            s.ed.set_hexpand(False)
            s.ed.set_halign(Gtk.Align.END)
            s.ed.connect(
                "toggled", lambda w: s._save("true" if w.get_active() else "false")
            )
            s.end_box.append(s.ed)
        elif ot in (OptionType.STRING, OptionType.GESTURE):
            if opt.str_labels:
                s.ed = Gtk.ComboBoxText()
                for lb, v in opt.str_labels:
                    s.ed.append(v, lb)
                selected = cur if cur is not None else str(opt.default_value or "")
                if selected not in {value for _, value in opt.str_labels}:
                    s.ed.append(selected, selected)
                s.ed.set_active_id(selected)
                s.ed.connect("changed", lambda w: s._save(w.get_active_id() or ""))
                s.ed.set_hexpand(True)
                s.end_box.append(s.ed)
            else:
                eb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                eb.set_hexpand(True)
                s.ed = Gtk.Entry()
                s.ed.set_text(cur if cur is not None else str(opt.default_value or ""))
                s.ed.set_hexpand(True)
                s.ed.connect("changed", s._on_text_changed)
                eb.append(s.ed)
                if "directory" in opt.hints:
                    b = Gtk.Button.new_from_icon_name("folder-open")
                    b.connect("clicked", s._choose_dir)
                    eb.append(b)
                if "file" in opt.hints:
                    b = Gtk.Button.new_from_icon_name("document-open")
                    b.connect("clicked", s._choose_file)
                    eb.append(b)
                s.end_box.append(eb)
        elif ot in (OptionType.KEY, OptionType.BUTTON, OptionType.ACTIVATOR):
            bx = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            bx.set_hexpand(True)
            s.ed = Gtk.Entry()
            s.ed.set_text(cur if cur is not None else str(opt.default_value or ""))
            s.ed.set_hexpand(True)
            s.ed.connect("changed", s._on_text_changed)
            bx.append(s.ed)
            g = Gtk.Button.new_from_icon_name("document-edit")
            g.set_tooltip_text("Grab key/button binding")
            g.add_css_class("grab-btn")
            g.connect("clicked", s._grab_key)
            bx.append(g)
            s.end_box.append(bx)
        elif ot == OptionType.COLOR:
            cs = cur if cur is not None else str(opt.default_value or "0 0 0 1")
            s.ed = Gtk.ColorButton()
            s.ed.set_use_alpha(True)
            s.ed.set_rgba(parse_color(cs))
            s.ed.set_hexpand(False)
            s.ed.set_halign(Gtk.Align.END)
            s.ed.connect("color-set", s._on_color_set)
            s.end_box.append(s.ed)
        elif ot == OptionType.ANIMATION:
            dur, easing = _parse_anim(
                cur if cur is not None else str(opt.default_value or "300ms linear")
            )
            bx = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            bx.set_hexpand(True)
            adj = Gtk.Adjustment(
                value=dur,
                lower=opt.min_val,
                upper=min(opt.max_val, 100000),
                step_increment=1,
            )
            s._aspin = Gtk.SpinButton(adjustment=adj)
            s._acb = Gtk.ComboBoxText()
            s._acb.set_hexpand(True)
            for e in ("linear", "circle", "sigmoid"):
                s._acb.append_text(e)
            for i, e in enumerate(("linear", "circle", "sigmoid")):
                if e == easing:
                    s._acb.set_active(i)
            s._aspin.connect("value-changed", lambda w: s._save_anim())
            s._acb.connect("changed", lambda w: s._save_anim())
            bx.append(s._aspin)
            bx.append(s._acb)
            s.end_box.append(bx)
            s.ed = s._aspin
        else:
            s.ed = Gtk.Entry()
            s.ed.set_text(cur if cur is not None else str(opt.default_value or ""))
            s.ed.set_hexpand(True)
            s.ed.connect("changed", s._on_text_changed)
            s.end_box.append(s.ed)

    def _default_text(s):
        d = s.option.default_value
        if s.option.type == OptionType.BOOL:
            return "true" if bool(d) else "false"
        if s.option.type == OptionType.ANIMATION:
            return str(d or "300ms linear")
        if s.option.type == OptionType.COLOR:
            return str(d or "0 0 0 1")
        return "" if d is None else str(d)

    def _values_equal(s, a, b):
        a = "" if a is None else str(a).strip()
        b = "" if b is None else str(b).strip()
        if s.option.type == OptionType.BOOL:
            def tb(x):
                return str(x).strip().lower() in ("true", "1", "yes", "on")
            return tb(a) == tb(b)
        if s.option.type == OptionType.INT:
            try:
                return int(float(a or 0)) == int(float(b or 0))
            except Exception:
                pass
        if s.option.type == OptionType.DOUBLE:
            try:
                return abs(float(a or 0) - float(b or 0)) < 1e-9
            except Exception:
                pass
        return a == b

    def _update_modified_state(s):
        if not hasattr(s, "reset_btn"):
            return
        cur = s.config.get_option(s.plugin.name, s.option.name)
        default = s._default_text()
        modified = cur is not None and not s._values_equal(cur, default)
        if modified:
            s.add_css_class("is-modified")
            s.reset_btn.remove_css_class("is-default")
            s.reset_btn.set_tooltip_text(_("Reset to default: {default}").format(default=default))
        else:
            s.remove_css_class("is-modified")
            s.reset_btn.add_css_class("is-default")
            s.reset_btn.set_tooltip_text(_("Already at default"))

    def _save(s, v):
        if s._block:
            return
        if getattr(s, "_text_save_id", 0):
            try:
                GLib.source_remove(s._text_save_id)
            except Exception:
                pass
            s._text_save_id = 0
        s.config.set_option(s.plugin.name, s.option.name, str(v))
        s.config.save()
        s.config._pending_edits.discard(s)
        s._update_modified_state()

    def cancel_pending_edit(s):
        if s._text_save_id:
            GLib.source_remove(s._text_save_id)
            s._text_save_id = 0
        s.config._pending_edits.discard(s)

    def flush_pending_edit(s):
        if s in s.config._pending_edits:
            text = s.ed.get_text()
            s._save(text)

    def _on_text_changed(s, widget):
        """Keep pending edits cancellable by presets and flushable on exit."""
        if s._block:
            return
        s.cancel_pending_edit()
        s.config._pending_edits.add(s)

        def do_save():
            s._text_save_id = 0
            if not s._block:
                try:
                    s._save(widget.get_text())
                except OSError as error:
                    print(f"WCM: Could not save edit; pending for retry: {error}")
            return False

        s._text_save_id = GLib.timeout_add(350, do_save)

    def _save_anim(s):
        s._save(
            f"{s._aspin.get_value_as_int()}ms {s._acb.get_active_text() or 'linear'}"
        )

    def _on_color_set(s, btn):
        s._save(color_to_str(btn.get_rgba()))

    def _grab_key(s, btn):
        w = KeyGrabWindow(s)
        w.connect("close-request", s._on_grab_done)
        w.present()

    def _on_grab_done(s, w):
        if w.result:
            s.ed.set_text(w.result)
            s._save(w.result)
        return False

    def _choose_dir(s, btn):
        s._file_dlg = Gtk.FileChooserNative(
            title=_("Select Directory"),
            transient_for=s.get_root(),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        s._file_dlg.connect("response", s._on_file_response)
        s._file_dlg.show()

    def _choose_file(s, btn):
        s._file_dlg = Gtk.FileChooserNative(
            title=_("Select File"),
            transient_for=s.get_root(),
            action=Gtk.FileChooserAction.OPEN,
        )
        s._file_dlg.connect("response", s._on_file_response)
        s._file_dlg.show()

    def _on_file_response(s, dlg, r):
        if r == Gtk.ResponseType.ACCEPT:
            f = dlg.get_file()
            if f:
                s.ed.set_text(f.get_path())
                s._save(f.get_path())
        dlg.destroy()
        s._file_dlg = None

    def _reset(s, btn):
        d = s.option.default_value
        s._block = True
        try:
            if s.option.type == OptionType.INT:
                if s.option.int_labels:
                    s.ed.set_active_id(str(d))
                else:
                    s.ed.set_value(d if isinstance(d, int) else 0)
            elif s.option.type == OptionType.DOUBLE:
                s.ed.set_value(d if isinstance(d, float) else 0.0)
            elif s.option.type == OptionType.BOOL:
                s.ed.set_active(bool(d))
            elif s.option.type in (
                OptionType.STRING,
                OptionType.KEY,
                OptionType.BUTTON,
                OptionType.ACTIVATOR,
                OptionType.GESTURE,
            ):
                if s.option.str_labels:
                    s.ed.set_active_id(str(d or ""))
                else:
                    s.ed.set_text(str(d or ""))
            elif s.option.type == OptionType.COLOR:
                s.ed.set_rgba(parse_color(str(d or "0 0 0 1")))
            elif s.option.type == OptionType.ANIMATION:
                dur, easing = _parse_anim(str(d or "300ms linear"))
                s._aspin.set_value(dur)
                for i, e in enumerate(("linear", "circle", "sigmoid")):
                    if e == easing:
                        s._acb.set_active(i)
                        break
        finally:
            s._block = False
        s._save(s._default_text())


class SubgroupWidget(Gtk.Frame):
    def __init__(s, sg, cfg, plg):
        super().__init__()
        s.add_css_class("subgroup-frame")
        exp = Gtk.Expander(label=sg.name or _("Options"))
        _apply_tooltip(sg.tooltip, s, exp)
        exp.set_expanded(True)
        bx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        bx.set_margin_start(8)
        bx.set_margin_end(8)
        bx.set_margin_top(8)
        bx.set_margin_bottom(8)
        for o in sg.options:
            if o.hidden:
                continue
            try:
                bx.append(OptionWidget(o, cfg, plg))
            except Exception as e:
                bx.append(Gtk.Label(label=f"\u26a0 {o.name}: {e}"))
        exp.set_child(bx)
        s.set_child(exp)


class PluginPage(Gtk.Notebook):
    def __init__(s, plg, cfg):
        super().__init__()
        s.set_scrollable(True)
        s.add_css_class("plugin-notebook")
        s.connect("switch-page", s._on_ts)
        s._lt = 0
        s._br = False
        s._rules_done = False
        s._reveal_i = 0
        for g in plg.option_groups:
            if g.type != OptionType.GROUP or g.hidden:
                continue
            s._pending_add = None
            bx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            bx.set_hexpand(True)
            bx.add_css_class("settings-surface")
            bx.set_margin_start(10)
            bx.set_margin_end(10)
            bx.set_margin_top(10)
            bx.set_margin_bottom(10)
            for o in g.options:
                if o.hidden:
                    continue
                try:
                    if o.type == OptionType.SUBGROUP and o.options:
                        sgw = SubgroupWidget(o, cfg, plg)
                        s._tag_reveal(sgw)
                        bx.append(sgw)
                    elif o.type == OptionType.DYNAMIC_LIST:
                        w = s._make_dynlist(o, cfg, plg)
                        if w:
                            s._tag_reveal(w)
                            bx.append(w)
                    elif o.type != OptionType.GROUP:
                        bx.append(OptionWidget(o, cfg, plg, s._next_reveal_index()))
                except Exception as e:
                    bx.append(Gtk.Label(label=f"\u26a0 {o.name}: {e}"))
                    traceback.print_exc()
            if bx.get_first_child() is None:
                s._append_help(bx, plg)
            s._append_page(_(g.name or "General"), bx, s._pending_add, g.tooltip)
        # Older window-rules metadata may have no options. Still expose
        # the editable rule list and add button.
        if s._is_winrules(plg) and not s._rules_done:
            s._pending_add = None
            bx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            bx.set_hexpand(True)
            bx.add_css_class("settings-surface")
            bx.set_margin_start(10)
            bx.set_margin_end(10)
            bx.set_margin_top(10)
            bx.set_margin_bottom(10)
            so = cfg.get_section_options(plg.name)
            wr = s._make_winrules_box(cfg, plg, so, "")
            s._tag_reveal(wr)
            bx.append(wr)
            s._append_page(_("Rules"), bx, s._pending_add)

        if s.get_n_pages() == 0:
            bx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            s._append_help(bx, plg)
            s._append_page(_("General"), bx, None)

    def _append_help(s, bx, plg):
        label = Gtk.Label(label=_(
            'This page has no editable options. See the plugin documentation for usage.'
        ))
        label.set_wrap(True)
        bx.append(label)
        bx.append(Gtk.LinkButton.new_with_label(plugin_wiki_url(plg), _("Plugin documentation")))

    def _next_reveal_index(s):
        i = s._reveal_i
        s._reveal_i += 1
        return i

    def _tag_reveal(s, widget):
        try:
            widget.add_css_class("row-reveal")
            widget.add_css_class(f"stagger-{s._next_reveal_index() % 8}")
        except Exception:
            pass

    @staticmethod
    def _is_winrules(plg):
        return plg.name == "window-rules"

    def _append_page(s, name, bx, pending_add, tooltip=None):
        sc = Gtk.ScrolledWindow()
        sc.set_vexpand(True)
        # Reserve scrollbar space instead of covering the final editable row.
        sc.set_overlay_scrolling(False)
        sc.set_child(bx)
        if pending_add is not None:
            # Allow the last row to scroll clear of the floating add button.
            bx.set_margin_bottom(max(bx.get_margin_bottom(), 84))
            ov = Gtk.Overlay()
            ov.set_vexpand(True)
            ov.set_child(sc)
            fab = Gtk.Button.new_from_icon_name("list-add")
            fab.add_css_class("fab-add")
            fab.set_halign(Gtk.Align.END)
            fab.set_valign(Gtk.Align.END)
            fab.set_tooltip_text("Add")
            fab.connect("clicked", lambda w, f=pending_add: f())
            ov.add_overlay(fab)
            tab = Gtk.Label(label=name)
            _apply_tooltip(tooltip, tab)
            s.append_page(ov, tab)
        else:
            tab = Gtk.Label(label=name)
            _apply_tooltip(tooltip, tab)
            s.append_page(sc, tab)

    def _on_ts(s, nb, pg, pn):
        if pn > s._lt:
            c = s.get_nth_page(pn)
            if c:
                c.add_css_class("tab-enter-up")
                GLib.timeout_add(
                    420, lambda: c.remove_css_class("tab-enter-up") or False
                )
        elif pn < s._lt:
            c = s.get_nth_page(pn)
            if c:
                c.add_css_class("tab-enter-down")
                GLib.timeout_add(
                    420, lambda: c.remove_css_class("tab-enter-down") or False
                )
        s._lt = pn

    def _make_dynlist(s, opt, cfg, plg):
        pxs = [e.prefix for e in opt.entries] if opt.entries else []
        so = cfg.get_section_options(plg.name)
        if plg.name == "window-rules" or opt.name == "rules":
            return s._make_winrules(opt, cfg, plg, so)
        if opt.name == "autostart" or pxs == [""]:
            return s._make_autostart(opt, cfg, plg, so)
        if any("binding" in p for p in pxs) or opt.name in (
            "bindings",
            "repeatable_bindings",
            "always_bindings",
            "release_bindings",
        ):
            if s._br:
                return None
            s._br = True
            return s._make_bindings(opt, cfg, plg, so)
        fr = Gtk.Frame(label=opt.disp_name or opt.name)
        _apply_tooltip(opt.tooltip, fr)
        bx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        bx.set_margin_start(8)
        bx.set_margin_end(8)
        bx.set_margin_top(8)
        bx.set_margin_bottom(8)
        if pxs:
            for k, v in so.items():
                if any(k.startswith(p) for p in pxs if p):
                    s._add_simple_row(bx, k, v, cfg, plg)
        fr.set_child(bx)
        return fr

    def _make_autostart(s, opt, cfg, plg, so):
        bx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        for k, v in so.items():
            if k != "autostart_wf_shell":
                bx.append(s._make_as_row(k, v, cfg, plg, bx))
        s._pending_add = lambda: s._add_as(cfg, plg, bx)
        return bx

    def _make_as_row(s, k, v, cfg, plg, pb):
        r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        e = Gtk.Entry()
        e.set_text(v)
        e.set_hexpand(True)
        e.connect("changed", lambda w, kk=k: s._so(cfg, plg, kk, w.get_text()))
        r.append(e)
        ch = Gtk.Button.new_from_icon_name("application-x-executable")
        ch.connect("clicked", lambda w, ee=e: s._choose_exec(ee))
        r.append(ch)
        rn = Gtk.Button.new_from_icon_name("media-playback-start")
        rn.add_css_class("run-btn")
        rn.connect("clicked", lambda w, ee=e: s._run_cmd(ee.get_text()))
        r.append(rn)
        rm = Gtk.Button.new_from_icon_name("list-remove")
        rm.add_css_class("remove-btn")
        rm.connect("clicked", lambda w, kk=k, rr=r: s._rm_row(cfg, plg, kk, rr, pb))
        r.append(rm)
        return r

    def _add_as(s, cfg, plg, bx):
        so = cfg.get_section_options(plg.name)
        i = 0
        while f"a{i}" in so:
            i += 1
        k = f"a{i}"
        cfg.set_option(plg.name, k, "")
        cfg.save()
        r = s._make_as_row(k, "", cfg, plg, bx)
        bx.append(r)

    def _make_winrules(s, opt, cfg, plg, so):
        pfx = opt.entries[0].prefix if opt.entries else ""
        return s._make_winrules_box(cfg, plg, so, pfx)

    def _make_winrules_box(s, cfg, plg, so, pfx):
        bx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        for k, v in so.items():
            if k.startswith(pfx):
                bx.append(s._make_wr_row(k, v, cfg, plg, bx))
        s._pending_add = lambda: s._add_wr(cfg, plg, bx, pfx or "rule_")
        s._rules_done = True
        return bx

    def _make_wr_row(s, k, v, cfg, plg, pb):
        r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        e = Gtk.Entry()
        e.set_text(v)
        e.set_hexpand(True)
        e.set_placeholder_text(
            'on created if app_id is "foo" then maximize'
        )
        e.connect("changed", lambda w, kk=k: s._so(cfg, plg, kk, w.get_text()))
        r.append(e)
        rm = Gtk.Button.new_from_icon_name("list-remove")
        rm.add_css_class("remove-btn")
        rm.connect("clicked", lambda w, kk=k, rr=r: s._rm_row(cfg, plg, kk, rr, pb))
        r.append(rm)
        return r

    def _add_wr(s, cfg, plg, bx, pfx):
        so = cfg.get_section_options(plg.name)
        i = 0
        while f"{pfx}{i}" in so:
            i += 1
        k = f"{pfx}{i}"
        cfg.set_option(plg.name, k, "")
        cfg.save()
        r = s._make_wr_row(k, "", cfg, plg, bx)
        bx.append(r)

    def _make_bindings(s, opt, cfg, plg, so):
        bx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        cn = []
        for k in so:
            for prefix in ("command_",) + BINDING_PREFIXES:
                if k.startswith(prefix):
                    n = k[len(prefix):]
                    if n and n not in cn:
                        cn.append(n)
                    break
        for c in sorted(cn):
            bx.append(s._make_bw(c, cfg, plg, so, bx))
        s._pending_add = lambda: s._add_bind(cfg, plg, bx)
        return bx

    def _make_bw(s, cn, cfg, plg, so, pb):
        ck = f"command_{cn}"
        rk = f"binding_{cn}"
        pk = f"repeatable_binding_{cn}"
        ak = f"always_binding_{cn}"
        cv = so.get(ck, "")
        rv = so.get(rk)
        pv = so.get(pk)
        av = so.get(ak)
        release_key = f"release_binding_{cn}"
        release = so.get(release_key)
        if release is not None:
            bt, bv, bk = 3, release, release_key
        elif av is not None:
            bt, bv, bk = 2, av, ak
        elif pv is not None:
            bt, bv, bk = 1, pv, pk
        elif rv is not None:
            bt, bv, bk = 0, rv, rk
        else:
            bt, bv, bk = 0, "none", rk
        fr = Gtk.Frame()
        fr.add_css_class("binding-frame")
        fr.set_margin_top(1)
        fr.set_margin_bottom(1)
        exp = Gtk.Expander(label=_("Command {name}: {command}").format(name=cn, command=cv))
        heading = exp.get_label_widget()
        heading.set_ellipsize(Pango.EllipsizeMode.END)
        heading.set_max_width_chars(48)
        heading.set_hexpand(True)
        heading.set_xalign(0)
        heading.set_tooltip_text(heading.get_text())
        exp.set_expanded(not cv)
        exp.set_margin_top(4)
        exp.set_margin_bottom(4)
        exp.set_margin_start(4)
        exp.set_margin_end(4)
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vb.set_margin_start(5)
        vb.set_margin_end(5)
        vb.set_margin_top(5)
        vb.set_margin_bottom(5)
        tr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        tl = Gtk.Label(label=_("Type"))
        tl.set_size_request(LABEL_W, -1)
        tl.set_xalign(0)
        tl.add_css_class("option-label")
        tr.append(tl)
        tc = Gtk.ComboBoxText()
        tc.append_text(_("Regular"))
        tc.append_text(_("Repeat"))
        tc.append_text(_("Always"))
        tc.append_text(_("Release"))
        tc.set_active(bt)
        tc.set_hexpand(True)
        tc.connect("changed", lambda w, c=cn: s._chg_bt(cfg, plg, c, w.get_active()))
        tr.append(tc)
        vb.append(tr)
        br = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bl = Gtk.Label(label=_("Binding"))
        bl.set_size_request(LABEL_W, -1)
        bl.set_xalign(0)
        bl.add_css_class("option-label")
        br.append(bl)
        be = Gtk.Entry()
        be.set_text(bv)
        be.set_hexpand(True)
        be.connect("changed", lambda w: s._so(
            cfg, plg, BINDING_PREFIXES[tc.get_active()] + cn, w.get_text()))
        br.append(be)
        gb = Gtk.Button.new_from_icon_name("document-edit")
        gb.add_css_class("grab-btn")
        gb.connect("clicked", lambda w: s._grab_for(
            be, cfg, plg, BINDING_PREFIXES[tc.get_active()] + cn))
        br.append(gb)
        vb.append(br)
        cr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        cl = Gtk.Label(label=_("Command"))
        cl.set_size_request(LABEL_W, -1)
        cl.set_xalign(0)
        cl.add_css_class("option-label")
        cr.append(cl)
        ce = Gtk.Entry()
        ce.set_text(cv)
        ce.set_hexpand(True)
        ce.connect(
            "changed",
            lambda w, e=heading, c=cn: e.set_text(
                _("Command {name}: {command}").format(name=c, command=w.get_text())),
        )
        ce.connect("changed", lambda w: heading.set_tooltip_text(heading.get_text()))
        ce.connect("changed", lambda w, c=ck: s._so(cfg, plg, c, w.get_text()))
        cr.append(ce)
        rm = Gtk.Button.new_from_icon_name("list-remove")
        rm.add_css_class("remove-btn")
        rm.connect("clicked", lambda w, c=cn, f=fr: s._rm_bind(cfg, plg, c, f, pb))
        cr.append(rm)
        vb.append(cr)
        exp.set_child(vb)
        fr.set_child(exp)
        return fr

    def _chg_bt(s, cfg, plg, cn, nt):
        if nt not in range(len(BINDING_PREFIXES)):
            return
        keys = [prefix + cn for prefix in BINDING_PREFIXES]
        so = cfg.get_section_options(plg.name)
        bv = next((so[keys[i]] for i in (3, 2, 1, 0) if keys[i] in so), "none")
        for key in keys:
            if key in so:
                cfg.remove_option(plg.name, key)
        cfg.set_option(plg.name, keys[nt], bv)
        cfg.save()

    def _rm_bind(s, cfg, plg, cn, fr, pb):
        for px in ("command_",) + BINDING_PREFIXES:
            cfg.remove_option(plg.name, px + cn)
        cfg.save()
        pb.remove(fr)

    def _add_bind(s, cfg, plg, bx):
        so = cfg.get_section_options(plg.name)
        i = 0
        while any(f"{prefix}new{i}" in so for prefix in ("command_",) + BINDING_PREFIXES):
            i += 1
        n = f"new{i}"
        cfg.set_option(plg.name, f"command_{n}", "")
        cfg.set_option(plg.name, f"binding_{n}", "none")
        cfg.save()
        so = cfg.get_section_options(plg.name)
        w = s._make_bw(n, cfg, plg, so, bx)
        bx.append(w)

    def _add_simple_row(s, bx, k, v, cfg, plg):
        r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        r.add_css_class("option-row")
        l = Gtk.Label(label=k)
        l.set_size_request(LABEL_W, -1)
        l.set_xalign(0)
        l.add_css_class("option-label")
        r.append(l)
        e = Gtk.Entry()
        e.set_text(v)
        e.set_hexpand(True)
        e.connect("changed", lambda w, kk=k: s._so(cfg, plg, kk, w.get_text()))
        r.append(e)
        bx.append(r)

    def _so(s, cfg, plg, k, t):
        cfg.set_option(plg.name, k, t)
        cfg.save()

    def _rm_row(s, cfg, plg, k, r, pb):
        cfg.remove_option(plg.name, k)
        cfg.save()
        pb.remove(r)

    def _choose_exec(s, e):
        s._exec_dlg = Gtk.FileChooserNative(
            title=_("Choose Executable"),
            transient_for=s.get_root(),
            action=Gtk.FileChooserAction.OPEN,
        )
        s._exec_dlg.connect("response", lambda d, r, ee=e: s._on_exec(d, r, ee))
        s._exec_dlg.show()

    def _on_exec(s, dlg, r, e):
        if r == Gtk.ResponseType.ACCEPT:
            f = dlg.get_file()
            if f:
                e.set_text(f.get_path())
        dlg.destroy()
        s._exec_dlg = None

    def _run_cmd(s, cmd):
        if cmd:
            try:
                GLib.spawn_command_line_async(cmd)
            except Exception as e:
                print(f"WCM: Failed to run '{cmd}': {e}")

    def _grab_for(s, e, cfg, plg, k):
        w = KeyGrabWindow(s)

        def done(ww, ee=e, kk=k):
            if ww.result:
                ee.set_text(ww.result)
                s._so(cfg, plg, kk, ww.result)
            return False

        w.connect("close-request", done)
        w.present()


class PluginButtonWidget(Gtk.Box):
    def __init__(s, plg, wcm, anim_index=0):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
        s.plugin = plg
        s.wcm = wcm
        s.set_halign(Gtk.Align.START)
        s.set_valign(Gtk.Align.CENTER)
        s.add_css_class("plugin-row")
        s.add_css_class("card-animate")
        s.add_css_class(f"stagger-{anim_index % 8}")
        if plg.is_core_plugin or plg.type == PluginType.WF_SHELL:
            s.add_css_class("plugin-protected")
        s.check = Gtk.CheckButton()
        _apply_tooltip(plg.tooltip, s, s.check)
        s.check.set_active(plg.enabled)
        s.check.set_valign(Gtk.Align.CENTER)
        if plg.is_core_plugin or plg.type == PluginType.WF_SHELL:
            s.check.set_sensitive(False)
        else:
            s.check.connect("toggled", s._on_t)
        s.append(s.check)
        btn = Gtk.Button()
        btn.add_css_class("flat")
        _apply_tooltip(plg.tooltip, btn)
        btn.connect("clicked", lambda w: wcm.open_page(plg))
        bb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bb.set_halign(Gtk.Align.START)
        bb.set_valign(Gtk.Align.CENTER)
        ip = find_plugin_icon(plg.name)
        if not ip:
            ip = (
                find_icon("wcm.svg")
                or find_icon("wcm.png")
                or find_icon("wayfire.svg")
                or find_icon("wayfire.png")
            )
        if ip:
            img = Gtk.Image.new_from_file(ip)
            img.set_pixel_size(32)
        else:
            img = Gtk.Image.new_from_icon_name("preferences-system")
            img.set_pixel_size(32)
        bb.append(img)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        text_box.set_hexpand(True)
        text_box.set_valign(Gtk.Align.CENTER)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        head.set_hexpand(True)
        l = Gtk.Label(label=plg.disp_name or plg.name)
        _apply_tooltip(plg.tooltip, l)
        l.add_css_class("plugin-name")
        l.set_xalign(0)
        l.set_hexpand(True)
        l.set_ellipsize(Pango.EllipsizeMode.END)
        head.append(l)
        text_box.append(head)

        sub = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        sub.add_css_class("plugin-subrow")
        sub.set_hexpand(True)
        meta = Gtk.Label(label=(plg.tooltip or plg.name or "").strip())
        _apply_tooltip(plg.tooltip, meta)
        meta.add_css_class("plugin-meta")
        meta.set_xalign(0)
        meta.set_hexpand(True)
        meta.set_ellipsize(Pango.EllipsizeMode.END)
        meta.set_max_width_chars(34)
        sub.append(meta)
        s.status = Gtk.Label()
        s.status.add_css_class("status-pill")
        sub.append(s.status)
        text_box.append(sub)
        bb.append(text_box)
        btn.set_child(bb)
        s.append(btn)
        s._refresh_visual_state()

    def _refresh_visual_state(s):
        if s.plugin.enabled:
            s.add_css_class("plugin-enabled")
        else:
            s.remove_css_class("plugin-enabled")
        if s.plugin.is_core_plugin:
            s.status.set_text(_("CORE"))
            s.status.remove_css_class("enabled")
            s.status.remove_css_class("shell")
            s.status.add_css_class("locked")
        elif s.plugin.type == PluginType.WF_SHELL:
            s.status.set_text(_("SHELL"))
            s.status.remove_css_class("enabled")
            s.status.remove_css_class("locked")
            s.status.add_css_class("shell")
        elif s.plugin.enabled:
            s.status.set_text(_("ON"))
            s.status.remove_css_class("locked")
            s.status.remove_css_class("shell")
            s.status.add_css_class("enabled")
        else:
            s.status.set_text(_("OFF"))
            s.status.remove_css_class("enabled")
            s.status.remove_css_class("locked")
            s.status.remove_css_class("shell")

    def _on_t(s, c):
        s.wcm.set_plugin_enabled(s.plugin, c.get_active())
        s._refresh_visual_state()


class MainPage(Gtk.ScrolledWindow):
    def __init__(s, plugins, wcm):
        super().__init__()
        s.set_vexpand(True)
        s.set_hexpand(True)
        s._ft = ""
        s._pw = []
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vb.set_hexpand(True)
        vb.add_css_class("content-surface")
        vb.set_margin_top(18)
        vb.set_margin_bottom(18)
        vb.set_margin_start(10)
        vb.set_margin_end(10)
        s.sg = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.BOTH)
        s.cd = {}
        for i, (cn, ic) in enumerate(CATEGORIES):
            tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            tb.add_css_class("category-header")
            img = Gtk.Image.new_from_icon_name(ic)
            img.set_pixel_size(24)
            tb.append(img)
            l = Gtk.Label()
            l.set_markup(f"<span size='14000'><b>{GLib.markup_escape_text(_(cn))}</b></span>")
            tb.append(l)
            vb.append(tb)
            fb = Gtk.FlowBox()
            fb.set_selection_mode(Gtk.SelectionMode.NONE)
            fb.set_halign(Gtk.Align.START)
            fb.set_min_children_per_line(3)
            fb.set_max_children_per_line(10)
            fb.set_row_spacing(8)
            fb.set_column_spacing(12)
            fb.set_margin_start(10)
            fb.set_filter_func(s._ff)
            vb.append(fb)
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            if i < len(CATEGORIES) - 1:
                vb.append(sep)
            s.cd[cn] = (tb, fb, sep)
        for p in plugins:
            ci = get_category_index(p.category)
            cn = CATEGORIES[ci][0]
            _h, fb, _s2 = s.cd[cn]
            w = PluginButtonWidget(p, wcm, len(s._pw))
            s.sg.add_widget(w)
            fb.append(w)
            s._pw.append(w)
        s.set_child(vb)
        s._sync_category_visibility()

    def _ff(s, child):
        w = child.get_child()
        if not w or not hasattr(w, "plugin"):
            return True
        if not s._ft:
            return True
        p = w.plugin
        return (
            s._ft in p.name.lower()
            or s._ft in p.disp_name.lower()
            or s._ft in p.tooltip.lower()
        )

    def set_filter(s, text):
        s._ft = text.lower()
        for _h, fb, _s2 in s.cd.values():
            fb.invalidate_filter()
        s._sync_category_visibility()

    def _category_has_visible_plugins(s, fb):
        child = fb.get_first_child()
        while child:
            w = child.get_child()
            if w and hasattr(w, "plugin") and s._ff(child):
                return True
            child = child.get_next_sibling()
        return False

    def _sync_category_visibility(s):
        """Hide category headers/separators when filtering leaves no plugins.

        Without this, searches can leave a lone category label like "Other"
        visible even though none of that category's plugin cards match.
        """
        visible_sections = []
        for cn, (header, fb, sep) in s.cd.items():
            visible = s._category_has_visible_plugins(fb)
            header.set_visible(visible)
            fb.set_visible(visible)
            visible_sections.append((visible, sep))

        remaining_visible = sum(1 for visible, _sep in visible_sections if visible)
        seen_visible = 0
        for visible, sep in visible_sections:
            if visible:
                seen_visible += 1
                sep.set_visible(seen_visible < remaining_visible)
            else:
                sep.set_visible(False)


def _parse_refresh(text):
    """Parse a refresh-rate string ('60', '59.97', '60.000 Hz') into mHz.

    Returns 0 for empty input and a negative value for unparseable text,
    which callers flag as invalid so it is never written to the config.
    """
    t = (text or "").strip().lower().replace("hz", "").strip()
    if not t:
        return 0
    try:
        return int(round(float(t) * 1000))
    except (ValueError, OverflowError):
        return -1


def _fmt_refresh(mhz):
    """Format a refresh rate in mHz for display: 60000 -> '60.000 Hz'."""
    try:
        mhz = int(mhz)
    except (TypeError, ValueError):
        return ""
    if mhz <= 0:
        return ""
    return f"{mhz / 1000:.3f} Hz"


def _parse_mode(mode):
    """Parse a wayfire.ini ``mode`` value -> ``(res, refresh_mhz, is_off)``.

    Handles 'off', 'default'/'auto', 'mirror <output>', 'WxH' and
    'WxH@<refresh>'. Wayfire stores the refresh in mHz
    ('1920x1080@60000'); hand-written Hz values ('@60', '@59.97') are
    tolerated and converted.
    """
    m = (mode or "").strip()
    ml = m.lower()
    if not m or ml in ("default", "auto") or ml.startswith("mirror"):
        return "", 0, False
    if ml == "off":
        return "", 0, True
    res, _sep, rate = m.partition("@")
    res = res.strip().lower()
    if not re.match(r"^\d+x\d+$", res):
        return "", 0, False
    mhz = 0
    rate = rate.strip().lower().replace("hz", "").strip()
    if rate:
        try:
            val = float(rate)
            mhz = int(round(val)) if val >= 1000 else int(round(val * 1000))
        except (ValueError, OverflowError):
            mhz = 0
    return res, mhz, False


def _build_mode(res, mhz):
    """Build a wayfire.ini ``mode`` value from a resolution + refresh (mHz)."""
    res = (res or "").strip()
    if mhz and int(mhz) > 0:
        return f"{res}@{int(mhz)}"
    return res


def _mode_human(res, ref_text):
    """Human-readable mode description for the confirm-changes prompt."""
    res = (res or "").strip()
    ref = (ref_text or "").strip()
    if not res:
        return _("auto")
    return f"{res} @ {ref}" if ref else res


class _DisplayConfirmDialog(Gtk.Window):
    """Floating "Confirm Display Changes" prompt with an auto-revert countdown.

    Mirrors the safety prompt other display tools show: once a resolution,
    refresh-rate or rotation change has been applied, the user has a few
    seconds to confirm it. If they don't (Revert, the close button, Escape,
    or the countdown running out), ``on_revert`` restores the previous value;
    ``on_keep`` accepts it. ``on_finished`` always runs once the popup closes,
    so the owner can drop its reference.

    Only resolution / refresh / rotation flow through here — nothing else
    about the output configuration is touched.
    """

    def __init__(s, parent, *, seconds, detail_lines,
                 on_keep, on_revert, on_finished):
        super().__init__()
        s._on_keep = on_keep
        s._on_revert = on_revert
        s._on_finished = on_finished
        s._seconds = seconds
        s._remaining = seconds
        s._timer_id = 0
        s._done = False
        s.connect("close-request", s._on_close_request)

        s.set_title(_("Confirm Display Changes"))
        s.add_css_class("confirm-window")
        s.set_decorated(False)
        s.set_resizable(False)
        if parent is not None:
            s.set_transient_for(parent)
            s.set_modal(True)
        s.set_default_size(360, -1)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        card.add_css_class("confirm-card")
        card.set_margin_start(18)
        card.set_margin_end(18)
        card.set_margin_top(16)
        card.set_margin_bottom(16)
        s.set_child(card)

        # header: title + close (X)
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label=_("Confirm Display Changes"))
        title.set_xalign(0)
        title.set_hexpand(True)
        title.add_css_class("confirm-title")
        hdr.append(title)
        xbtn = Gtk.Button.new_from_icon_name("window-close-symbolic")
        xbtn.add_css_class("confirm-close")
        xbtn.set_valign(Gtk.Align.CENTER)
        xbtn.set_tooltip_text(_("Revert"))
        xbtn.connect("clicked", lambda *_: s._finish("revert"))
        hdr.append(xbtn)
        card.append(hdr)

        # big countdown
        countbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        countbox.add_css_class("confirm-countbox")
        countbox.set_halign(Gtk.Align.FILL)
        countbox.set_margin_top(2)
        s._count_lbl = Gtk.Label(label=f"{s._remaining}s")
        s._count_lbl.add_css_class("confirm-count")
        s._count_lbl.set_hexpand(True)
        s._count_lbl.set_margin_top(14)
        s._count_lbl.set_margin_bottom(14)
        countbox.append(s._count_lbl)
        card.append(countbox)

        # change description
        s._detail_lbl = Gtk.Label()
        s._detail_lbl.set_xalign(0)
        s._detail_lbl.set_wrap(True)
        s._detail_lbl.add_css_class("confirm-detail")
        card.append(s._detail_lbl)
        s._set_detail(detail_lines)
        s._error_lbl = Gtk.Label()
        s._error_lbl.set_wrap(True)
        s._error_lbl.set_xalign(0)
        s._error_lbl.add_css_class("error")
        s._error_lbl.set_visible(False)
        card.append(s._error_lbl)

        # buttons
        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btns.set_halign(Gtk.Align.END)
        btns.set_margin_top(4)
        revert = Gtk.Button(label=_("Revert"))
        revert.connect("clicked", lambda *_: s._finish("revert"))
        keep = Gtk.Button(label=_("Keep Changes"))
        keep.add_css_class("confirm-keep")
        keep.connect("clicked", lambda *_: s._finish("keep"))
        btns.append(revert)
        btns.append(keep)
        card.append(btns)

        # Escape reverts, like dismissing the prompt
        kc = Gtk.EventControllerKey()
        kc.connect("key-pressed", s._on_key)
        s.add_controller(kc)

        s._start_timer()

    # -- public API used by the owner to supersede an in-flight prompt --
    def _on_close_request(s, *args):
        s._finish("revert")
        # _finish destroys the window only after recovery succeeds.
        return True

    def update(s, detail_lines):
        """Refresh the change description and restart the countdown."""
        if s._done:
            return
        s._set_detail(detail_lines)
        s._remaining = s._seconds
        s._count_lbl.set_text(f"{s._remaining}s")
        s._start_timer()

    def close_silent(s):
        """Close without keeping or reverting (e.g. user returned to baseline)."""
        s._finish("silent")

    # -- internals --
    def _set_detail(s, detail_lines):
        text = "\n".join(detail_lines) if detail_lines else ""
        s._detail_lbl.set_text(text)
        s._detail_lbl.set_visible(bool(text))

    def _on_key(s, _c, keyval, _kc, _state):
        if keyval == Gdk.KEY_Escape:
            s._finish("revert")
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            s._finish("keep")
            return True
        return False

    def _start_timer(s):
        if s._timer_id:
            GLib.source_remove(s._timer_id)
        s._timer_id = GLib.timeout_add_seconds(1, s._tick)

    def _tick(s):
        s._remaining -= 1
        if s._remaining <= 0:
            s._timer_id = 0
            s._finish("revert")
            return False
        s._count_lbl.set_text(f"{s._remaining}s")
        return True

    def _finish(s, reason):
        if s._done:
            return True
        if s._timer_id:
            GLib.source_remove(s._timer_id)
            s._timer_id = 0
        try:
            if reason == "keep" and s._on_keep:
                s._on_keep()
            elif reason == "revert" and s._on_revert:
                s._on_revert()
        except OSError as error:
            s._error_lbl.set_text(_("Could not restore display settings") + ": " + str(error))
            s._error_lbl.set_visible(True)
            s._remaining = s._seconds
            s._count_lbl.set_text(f"{s._remaining}s")
            s._start_timer()
            return False
        s._done = True
        s.destroy()
        if s._on_finished:
            s._on_finished()
        return True


class DisplayPage(Gtk.ScrolledWindow):
    """Built-in monitor/output configuration.

    Detects connected monitors with wlr-randr and writes the chosen
    resolution, refresh rate, scale, position, rotation and on/off state
    into the ``[output:<name>]`` sections of wayfire.ini — so outputs can
    be configured from the GUI instead of editing the config by hand.
    Values are saved live (per control), matching the rest of WCM.

    (The original C++ WCM has no output configuration and defers to
    wdisplays, which adjusts outputs at runtime but never persists them
    to the config file.)
    """

    def __init__(s, app):
        super().__init__()
        s.app = app
        s.set_vexpand(True)
        s.set_hexpand(True)
        s._om = OutputManager()
        #: the currently-open "Confirm Display Changes" prompt, if any
        s._active_confirm = None
        #: pending debounce timer ids for the confirm prompt (cancelled on reload)
        s._confirm_sources = set()
        s._pending_reverts = {}
        s._root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        s._root.set_margin_start(14)
        s._root.set_margin_end(14)
        s._root.set_margin_top(14)
        s._root.set_margin_bottom(14)
        s.set_child(s._root)
        s._hotplug_source = 0
        s._monitor_handler = None
        s._monitors = s.get_display().get_monitors()
        s.connect("map", s._watch_outputs)
        s.connect("unmap", s._unwatch_outputs)
        s.reload()

    def _watch_outputs(s, *_):
        if s._monitor_handler is None:
            s._monitor_handler = s._monitors.connect("items-changed", s._outputs_changed)
        s._outputs_changed()

    def _unwatch_outputs(s, *_):
        if s._monitor_handler is not None:
            s._monitors.disconnect(s._monitor_handler)
            s._monitor_handler = None
        if s._hotplug_source:
            GLib.source_remove(s._hotplug_source)
            s._hotplug_source = 0

    def _outputs_changed(s, *_):
        # Coalesce connector events and allow the output protocol to settle.
        if not s._hotplug_source:
            s._hotplug_source = GLib.timeout_add(500, s._refresh_outputs)

    def _refresh_outputs(s):
        # Keep the existing rollback alive until the user confirms or times out.
        if s._active_confirm is not None or s._confirm_sources or s._pending_reverts:
            return True
        s._hotplug_source = 0
        s.reload()
        return False

    def reload(s, *_):
        if s._active_confirm is not None or s._confirm_sources or s._pending_reverts:
            return
        # Rebuild only after confirmation has finished, preserving rollback.
        child = s._root.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            s._root.remove(child)
            child = nxt

        cfg = s.app.config
        detected = s._om.detect()
        det_names = [d["name"] for d in detected]
        merged = list(detected)
        for n in OutputManager.list_configured_outputs(cfg):
            if n not in det_names:
                merged.append({
                    "name": n,
                    "description": "(configured \u2014 not currently connected)",
                    "enabled": True, "modes": [], "current_mode": None,
                    "position": None, "transform": "normal", "scale": 1.0,
                })

        if not merged:
            info = Gtk.Label()
            info.set_wrap(True)
            info.set_xalign(0)
            info.set_markup(
                "<b>No outputs detected.</b>\n\nwlr-randr isn't available, or "
                "Wayfire isn't currently running. You can still add an output "
                "by name below and configure it manually."
            )
            info.add_css_class("plugin-desc")
            s._root.append(info)

        # The "main display" is protected: it can't be switched off or
        # removed, because that blanks the screen and forces the user back to
        # hand-editing the .ini. The protected display is the one the WCM
        # window is currently shown on, so moving WCM to another monitor lets
        # you switch the others off. If that can't be resolved, fall back to
        # the first output that is currently on.
        primary = None
        win_out = s._window_output_name()
        if win_out and any(oi["name"] == win_out for oi in merged):
            primary = win_out
        else:
            for oi in detected:
                m = cfg.get_option(OutputManager.section_name(oi["name"]), "mode")
                on = (m.strip() != "off") if m is not None else oi.get("enabled", True)
                if on:
                    primary = oi["name"]
                    break

        for oi in merged:
            s._root.append(
                s._build_card(oi, cfg, is_primary=(oi["name"] == primary),
                              is_connected=(oi["name"] in det_names)))

        s._root.append(s._build_add_row(cfg))

    def revert_pending_changes(s):
        for sid in list(s._confirm_sources):
            GLib.source_remove(sid)
        s._confirm_sources.clear()
        if s._active_confirm is not None:
            if s._active_confirm._finish("revert") is False:
                raise OSError(_("Display settings have not been restored. Retry before closing."))
        for revert in list(s._pending_reverts.values()):
            revert()
        s._pending_reverts.clear()

    def _window_output_name(s):
        """Return the connector name of the output the WCM window is on.

        Uses the Wayland surface's current monitor (Wayfire reports this via
        wl_surface enter/leave). Returns None if it can't be determined, e.g.
        before the window is mapped or on backends without connector info.
        """
        try:
            surface = s.app.get_surface()
            display = s.app.get_display()
            if surface is None or display is None:
                return None
            monitor = display.get_monitor_at_surface(surface)
            if monitor is None:
                return None
            return monitor.get_connector()
        except Exception:
            return None

    def _build_card(s, oi, cfg, is_primary=False, is_connected=True):
        name = oi["name"]
        sec = OutputManager.section_name(name)
        st = {"block": True}  # suppress writes during initial population

        fr = Gtk.Frame()
        fr.add_css_class("binding-frame")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        fr.set_child(box)

        # --- header: name + description + enable switch ---
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title = Gtk.Label()
        desc = oi.get("description") or ""
        markup = f"<b>{GLib.markup_escape_text(name)}</b>"
        if is_primary:
            markup += ("  <span size='small'>\u2014 "
                       + GLib.markup_escape_text(_("main display (running WCM)"))
                       + "</span>")
        if desc:
            markup += f"  <span size='small'>{GLib.markup_escape_text(desc)}</span>"
        title.set_markup(markup)
        title.set_xalign(0)
        title.set_hexpand(True)
        title.add_css_class("plugin-title")
        hdr.append(title)
        en_lbl = Gtk.Label(label=_("Enabled"))
        en_lbl.add_css_class("option-label")
        hdr.append(en_lbl)
        sw = Gtk.Switch()
        sw.set_valign(Gtk.Align.CENTER)
        hdr.append(sw)
        rmb = Gtk.Button.new_from_icon_name("user-trash")
        rmb.add_css_class("remove-btn")
        rmb.set_valign(Gtk.Align.CENTER)
        if is_primary:
            rmb.set_sensitive(False)
            rmb.set_tooltip_text(_(
                "WCM is running on this display, so it can't be removed — "
                "that would blank your screen. Move WCM to another "
                "display to manage this one."))
        else:
            rmb.set_tooltip_text(_("Remove this output (delete its config section)"))
            rmb.connect("clicked", lambda w, n=name: s._confirm_remove(n))
        hdr.append(rmb)
        box.append(hdr)

        # --- initial state: prefer config, fall back to detection ---
        cfg_mode = cfg.get_option(sec, "mode")
        res0, refresh0, is_off = _parse_mode(cfg_mode)
        if cfg_mode is None:
            cm = oi.get("current_mode")
            if cm:
                res0, refresh0 = f"{cm[0]}x{cm[1]}", cm[2]
            is_off = not oi.get("enabled", True)
        enabled0 = not is_off

        # resolution / refresh option tables from detected modes
        res_list, ref_by_res = [], {}
        for m in oi.get("modes", []):
            r = f"{m['width']}x{m['height']}"
            if r not in ref_by_res:
                ref_by_res[r] = []
                res_list.append(r)
            ref_by_res[r].append(m["refresh"])
        res_list.sort(
            key=lambda r: -(int(r.split("x")[0]) * int(r.split("x")[1]))
        )

        res_combo = Gtk.ComboBoxText.new_with_entry()
        res_combo.append("default", _("Automatic"))
        for r in res_list:
            res_combo.append_text(r)
        if res0 and res0 not in res_list:
            res_combo.append_text(res0)
        res_combo.get_child().set_text(res0 or "")
        if not res0 and enabled0 and not (cfg_mode or "").startswith("mirror"):
            res_combo.set_active_id("default")

        ref_combo = Gtk.ComboBoxText.new_with_entry()

        def populate_refresh(selected_res, keep=""):
            ref_combo.remove_all()
            seen = set()
            for rf in sorted(ref_by_res.get(selected_res, []), reverse=True):
                lbl = _fmt_refresh(rf)
                if lbl and lbl not in seen:
                    seen.add(lbl)
                    ref_combo.append_text(lbl)
            ref_combo.get_child().set_text(keep or "")

        populate_refresh(res0, _fmt_refresh(refresh0))

        scale_val = cfg.get_option(sec, "scale")
        try:
            scale_val = float(scale_val) if scale_val else float(oi.get("scale") or 1.0)
        except (ValueError, OverflowError):
            scale_val = 1.0
        if not math.isfinite(scale_val):
            scale_val = 1.0
        scale_spin = Gtk.SpinButton(
            adjustment=Gtk.Adjustment(value=scale_val, lower=0.25, upper=8.0,
                                      step_increment=0.05),
            digits=2,
        )

        px, py = 0, 0
        cfg_pos = cfg.get_option(sec, "position")
        if cfg_pos and "," in cfg_pos:
            try:
                px, py = (int(float(v)) for v in cfg_pos.split(",")[:2])
            except (ValueError, OverflowError):
                px, py = 0, 0
        elif oi.get("position"):
            px, py = oi["position"]
        posx_spin = Gtk.SpinButton(
            adjustment=Gtk.Adjustment(value=px, lower=-32768, upper=32768,
                                      step_increment=1))
        posy_spin = Gtk.SpinButton(
            adjustment=Gtk.Adjustment(value=py, lower=-32768, upper=32768,
                                      step_increment=1))

        tr_combo = Gtk.ComboBoxText()
        cur_tr = cfg.get_option(sec, "transform") or oi.get("transform") or "normal"
        tr_values = list(OutputManager.TRANSFORMS)
        if cur_tr not in tr_values:
            tr_values.append(cur_tr)
        for t in tr_values:
            tr_combo.append_text(t)
        tr_combo.set_active(tr_values.index(cur_tr))

        # --- live-save helpers (each writes only its own option) ---
        def _set_warn(level, msg):
            warn_lbl.remove_css_class("output-warn")
            warn_lbl.remove_css_class("output-error")
            if not msg:
                warn_lbl.set_visible(False)
                return
            warn_lbl.set_text(msg)
            warn_lbl.add_css_class("output-error" if level == "error"
                                   else "output-warn")
            warn_lbl.set_visible(True)

        # --- "Confirm Display Changes" auto-revert for resolution / refresh /
        #     rotation. The applied value is the live one; if the user doesn't
        #     confirm within the countdown we restore the previous (baseline)
        #     value. baseline updates only when the user keeps a change.
        confirm = {
            "res": res0 or "",
            "ref": _fmt_refresh(refresh0),
            "tr": cur_tr,
            "saved_mode": cfg_mode,
            "saved_transform": cfg.get_option(sec, "transform"),
            "suppress": False,    # don't prompt for enable/disable toggles
            "reverting": False,   # guard against re-entrancy while reverting
            "debounce_id": 0,     # coalesce rapid edits / typing
        }

        def _cur_res():
            if res_combo.get_active_id() == "default":
                return ""
            return (res_combo.get_active_text()
                    or res_combo.get_child().get_text() or "").strip()

        def _cur_ref():
            return (ref_combo.get_active_text()
                    or ref_combo.get_child().get_text() or "").strip()

        def _cur_tr():
            return tr_combo.get_active_text() or "normal"

        def _confirm_detail():
            lines = []
            if sw.get_active() and (
                    (_cur_res(), _cur_ref()) != (confirm["res"], confirm["ref"])
                    or cfg.get_option(sec, "mode") != confirm["saved_mode"]):
                lines.append(_("{name}: Mode → {mode}").format(
                    name=name, mode=_mode_human(_cur_res(), _cur_ref())))
            if _cur_tr() != (confirm["tr"] or "normal"):
                lines.append(_("{name}: Rotation → {rotation}").format(
                    name=name, rotation=_cur_tr()))
            return lines

        def _confirm_keep():
            # Entries may contain rejected or incomplete typing. Keep only
            # values that were actually saved and restore their controls.
            restore_controls("mode")
            restore_controls("transform")
            getattr(s, "_pending_reverts", {}).pop(sec, None)
            confirm["res"], confirm["ref"] = _cur_res(), _cur_ref()
            confirm["tr"] = _cur_tr()
            confirm["saved_mode"] = cfg.get_option(sec, "mode")
            confirm["saved_transform"] = cfg.get_option(sec, "transform")

        def _confirm_revert():
            sid = confirm["debounce_id"]
            if sid in s._confirm_sources:
                GLib.source_remove(sid)
                s._confirm_sources.discard(sid)
            confirm["debounce_id"] = 0
            confirm["reverting"] = True
            try:
                # A failed save must leave both the visible state and queued
                # operations unchanged so Keep and Retry remain meaningful.
                previous = copy.deepcopy((cfg.entries, cfg._operations, cfg._disk_text))
                committed_warning = None
                try:
                    for key, value in (("mode", confirm["saved_mode"]),
                                       ("transform", confirm["saved_transform"])):
                        if key == "mode" and not sw.get_active():
                            continue
                        if value is None:
                            cfg.remove_option(sec, key)
                        else:
                            cfg.set_option(sec, key, value)
                    cfg.save()
                except SaveCommittedError as error:
                    committed_warning = str(error)
                except OSError:
                    cfg.entries, cfg._operations, cfg._disk_text = previous
                    cfg._rebuild_index()
                    raise
                st["block"] = True
                try:
                    if confirm["saved_mode"] == "default":
                        res_combo.set_active_id("default")
                    else:
                        res_combo.set_active(-1)
                        res_combo.get_child().set_text(confirm["res"])
                    populate_refresh(confirm["res"], confirm["ref"])
                    tr_txt = confirm["tr"] or "normal"
                    if tr_txt in tr_values:
                        tr_combo.set_active(tr_values.index(tr_txt))
                finally:
                    st["block"] = False
                remember_controls("mode")
                remember_controls("transform")
                getattr(s, "_pending_reverts", {}).pop(sec, None)
                _set_warn("error" if committed_warning else "ok", committed_warning or "")
            finally:
                # Always clear the guard, or the prompt would only ever fire once.
                confirm["reverting"] = False

        def _cancel_confirm():
            sid = confirm["debounce_id"]
            if sid in s._confirm_sources:
                GLib.source_remove(sid)
                s._confirm_sources.discard(sid)
            confirm["debounce_id"] = 0
            getattr(s, "_pending_reverts", {}).pop(sec, None)
            active = s._active_confirm
            if active is not None and getattr(active, "owner", None) == sec:
                active.close_silent()

        _confirm_revert.cancel = _cancel_confirm

        def _show_confirm():
            s._confirm_sources.discard(confirm["debounce_id"])
            confirm["debounce_id"] = 0
            lines = _confirm_detail()
            active = s._active_confirm
            if not lines:
                getattr(s, "_pending_reverts", {}).pop(sec, None)
                # Returned to the baseline before the prompt mattered.
                if active is not None and getattr(active, "owner", None) == sec:
                    active.close_silent()
                return False
            if active is not None and getattr(active, "owner", None) == sec:
                active.update(lines)
                return False
            if active is not None:
                if active._finish("revert") is False:
                    confirm["debounce_id"] = GLib.timeout_add(600, _show_confirm)
                    s._confirm_sources.add(confirm["debounce_id"])
                    return False

            def _finished():
                if getattr(s._active_confirm, "owner", None) == sec:
                    s._active_confirm = None

            dlg = _DisplayConfirmDialog(
                s.app, seconds=CONFIRM_TIMEOUT_SECONDS, detail_lines=lines,
                on_keep=_confirm_keep, on_revert=_confirm_revert,
                on_finished=_finished)
            dlg.owner = sec
            s._active_confirm = dlg
            dlg.present()
            return False

        def maybe_confirm():
            if st["block"] or confirm["reverting"] or confirm["suppress"]:
                return
            if not is_connected:
                # Not a live output: writing config can't blank a screen,
                # so there's nothing to confirm/revert.
                return
            if confirm["debounce_id"]:
                GLib.source_remove(confirm["debounce_id"])
                s._confirm_sources.discard(confirm["debounce_id"])
            if hasattr(s, "_pending_reverts"):
                s._pending_reverts[sec] = _confirm_revert
            confirm["debounce_id"] = GLib.timeout_add(600, _show_confirm)
            s._confirm_sources.add(confirm["debounce_id"])

        committed_controls = {
            "mode": (res_combo.get_active_id(), res_combo.get_child().get_text(),
                     ref_combo.get_child().get_text(), enabled0),
            "transform": tr_combo.get_active(),
            "scale": scale_spin.get_value(),
            "position": (posx_spin.get_value(), posy_spin.get_value()),
        }

        def remember_controls(key):
            if key == "mode":
                committed_controls[key] = (res_combo.get_active_id(), res_combo.get_child().get_text(),
                                           ref_combo.get_child().get_text(), sw.get_active())
            elif key == "transform":
                committed_controls[key] = tr_combo.get_active()
            elif key == "scale":
                committed_controls[key] = scale_spin.get_value()
            else:
                committed_controls[key] = (posx_spin.get_value(), posy_spin.get_value())

        def restore_controls(key):
            st["block"] = True
            try:
                value = committed_controls[key]
                if key == "mode":
                    active, res, ref, enabled = value
                    if active:
                        res_combo.set_active_id(active)
                    else:
                        res_combo.set_active(-1)
                        res_combo.get_child().set_text(res)
                    populate_refresh(res, ref)
                    sw.set_active(enabled)
                    for ctl in (res_combo, ref_combo, scale_spin, posx_spin, posy_spin, tr_combo):
                        ctl.set_sensitive(enabled)
                elif key == "transform":
                    tr_combo.set_active(value)
                elif key == "scale":
                    scale_spin.set_value(value)
                else:
                    posx_spin.set_value(value[0]); posy_spin.set_value(value[1])
            finally:
                st["block"] = False

        def save_display_option(key, value):
            previous = copy.deepcopy((cfg.entries, cfg._operations, cfg._disk_text))
            try:
                cfg.set_option(sec, key, value)
                cfg.save()
            except SaveCommittedError as error:
                remember_controls(key)
                _set_warn("error", str(error))
                return True
            except OSError as error:
                cfg.entries, cfg._operations, cfg._disk_text = previous
                cfg._rebuild_index()
                restore_controls(key)
                _set_warn("error", str(error))
                return False
            remember_controls(key)
            return True

        def write_mode(*_):
            if st["block"]:
                return
            if not sw.get_active():
                _set_warn("ok", "")
                return save_display_option("mode", "off")
            automatic = res_combo.get_active_id() == "default"
            res = _cur_res()
            if res == "" and not automatic:
                # Mid-edit / incomplete: don't touch the saved mode.
                _set_warn("ok", "")
                return
            ref_text = (ref_combo.get_active_text()
                        or ref_combo.get_child().get_text() or "").strip()
            if automatic or ref_text == "":
                rf = 0
            else:
                rf = _parse_refresh(ref_text)
                if rf <= 0:
                    rf = -1  # typed but unparseable -> flagged invalid
            level, msg = OutputManager.validate_mode(res, rf, True,
                                                     oi.get("modes"))
            _set_warn(level, msg)
            if level == "error":
                # Never hand wayfire a malformed/unsupported mode.
                return
            if save_display_option("mode", "default" if automatic else
                                   _build_mode(res, rf if rf > 0 else 0)):
                maybe_confirm()
                return True
            return False

        def write_scale(*_):
            if st["block"]:
                return
            save_display_option("scale", f"{scale_spin.get_value():.6f}")

        def write_position(*_):
            if st["block"]:
                return
            save_display_option(
                "position",
                f"{posx_spin.get_value_as_int()},{posy_spin.get_value_as_int()}")

        def write_transform(*_):
            if st["block"]:
                return
            if save_display_option("transform", tr_combo.get_active_text() or "normal"):
                maybe_confirm()

        def on_res_changed(_w):
            if st["block"]:
                return
            r = res_combo.get_active_text() or res_combo.get_child().get_text()
            r = (r or "").strip()
            if res_combo.get_active_id() == "default":
                st["block"] = True
                populate_refresh("", "")
                st["block"] = False
            elif r in ref_by_res:
                st["block"] = True
                populate_refresh(r, ref_combo.get_active_text() or "")
                st["block"] = False
            write_mode()

        def commit_resolution(*_):
            # An empty field during typing is not a mode change. Enter or
            # leaving the field commits it as an explicit automatic choice.
            if not st["block"] and not res_combo.get_child().get_text().strip():
                res_combo.set_active_id("default")

        def on_toggle(_w, _p):
            if st["block"]:
                return
            if not sw.get_active():
                # Preserve a usable mode for the next enable. Rejected or
                # incomplete entry text must not become the off-state mode.
                restore_controls("mode")
                st["block"] = True
                try:
                    sw.set_active(False)
                finally:
                    st["block"] = False
            for ctl in (res_combo, ref_combo, scale_spin, posx_spin,
                        posy_spin, tr_combo):
                ctl.set_sensitive(sw.get_active())
            # Turning an output on/off isn't a resolution/refresh/rotation
            # change, so it shouldn't raise the confirm prompt.
            confirm["suppress"] = True
            try:
                if sw.get_active() and not _cur_res():
                    res_combo.set_active_id("default")
                if not write_mode():
                    restore_controls("mode")
                    return
                # On/off is committed immediately. Future rotation rollback
                # must restore this new mode, not the pre-toggle off state.
                expected = "off" if not sw.get_active() else (
                    "default" if res_combo.get_active_id() == "default" else
                    _build_mode(_cur_res(), max(0, _parse_refresh(_cur_ref()))))
                if cfg.get_option(sec, "mode") == expected:
                    confirm["saved_mode"] = expected
                    confirm["res"], confirm["ref"] = _cur_res(), _cur_ref()
            finally:
                confirm["suppress"] = False

        # --- layout the controls ---
        def add_row(label, widget):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.add_css_class("option-row")
            lab = Gtk.Label(label=label)
            lab.set_size_request(LABEL_W, -1)
            lab.set_xalign(0)
            lab.add_css_class("option-label")
            row.append(lab)
            widget.set_hexpand(True)
            row.append(widget)
            box.append(row)

        add_row(_("Resolution"), res_combo)
        add_row(_("Refresh rate"), ref_combo)
        add_row(_("Scale"), scale_spin)
        pos_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        pos_box.append(Gtk.Label(label="X"))
        pos_box.append(posx_spin)
        pos_box.append(Gtk.Label(label="Y"))
        pos_box.append(posy_spin)
        add_row(_("Position"), pos_box)
        add_row(_("Rotation"), tr_combo)

        warn_lbl = Gtk.Label()
        warn_lbl.set_wrap(True)
        warn_lbl.set_xalign(0)
        warn_lbl.set_visible(False)
        warn_lbl.set_margin_start(8)
        box.append(warn_lbl)

        for ctl in (res_combo, ref_combo, scale_spin, posx_spin, posy_spin,
                    tr_combo):
            ctl.set_sensitive(enabled0 or is_primary)
        sw.set_active(enabled0 or is_primary)
        if is_primary:
            sw.set_sensitive(False)
            sw.set_tooltip_text(_(
                "WCM is running on this display, so it can't be switched off — "
                "that would blank your screen. Move WCM to another "
                "display to turn this one off."))

        # connect after initial values are set, then unblock
        sw.connect("notify::active", on_toggle)
        res_combo.connect("changed", on_res_changed)
        res_combo.get_child().connect("activate", commit_resolution)
        resolution_focus = Gtk.EventControllerFocus()
        resolution_focus.connect("leave", commit_resolution)
        res_combo.get_child().add_controller(resolution_focus)
        ref_combo.connect("changed", write_mode)
        scale_spin.connect("value-changed", write_scale)
        posx_spin.connect("value-changed", write_position)
        posy_spin.connect("value-changed", write_position)
        tr_combo.connect("changed", write_transform)
        st["block"] = False

        return fr

    def _confirm_remove(s, name):
        cfg = s.app.config
        dlg = Gtk.AlertDialog()
        dlg.set_modal(True)
        dlg.set_message(_("Remove output “{name}”?").format(name=name))
        dlg.set_detail(_(
            "This deletes its [output:{name}] section from wayfire.ini. "
            "If the monitor is still connected it will reappear unconfigured."
        ).format(name=name))
        dlg.set_buttons([_("Cancel"), _("Remove")])
        dlg.set_cancel_button(0)
        dlg.set_default_button(0)

        def on_resp(d, res):
            try:
                idx = d.choose_finish(res)
            except GLib.Error:
                return  # dismissed
            if idx == 1:
                cfg = s.app.config
                previous = copy.deepcopy((cfg.entries, cfg._operations, cfg._disk_text))
                committed_warning = None
                try:
                    cfg.remove_section(OutputManager.section_name(name))
                    cfg.save()
                except SaveCommittedError as error:
                    committed_warning = error
                except OSError as error:
                    cfg.entries, cfg._operations, cfg._disk_text = previous
                    cfg._rebuild_index()
                    _operation_error(s.app, _("Could not remove output"), error)
                    return
                pending = getattr(s, "_pending_reverts", {}).get(OutputManager.section_name(name))
                if pending is not None:
                    pending.cancel()
                s.reload()
                if committed_warning is not None:
                    _operation_error(s.app, _("Output removed; recovery needs attention"), committed_warning)

        dlg.choose(s.app, None, on_resp)

    def _build_add_row(s, cfg):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_margin_top(8)
        lab = Gtk.Label(label=_("Add output"))
        lab.set_size_request(LABEL_W, -1)
        lab.set_xalign(0)
        lab.add_css_class("option-label")
        row.append(lab)
        ent = Gtk.Entry()
        ent.set_placeholder_text(_("name from wlr-randr, e.g. HDMI-A-1"))
        ent.set_hexpand(True)
        row.append(ent)
        btn = Gtk.Button.new_from_icon_name("list-add")
        btn.add_css_class("add-btn")
        row.append(btn)

        def do_add(*args):
            nm = ent.get_text().strip()
            if not nm:
                return
            if any(char in nm for char in "[]\r\n"):
                _operation_error(s.app, _("Could not add output"),
                                 _("Output names cannot contain brackets or line breaks."))
                return
            sec = OutputManager.section_name(nm)
            if cfg.get_option(sec, "mode") is None:
                previous = copy.deepcopy((cfg.entries, cfg._operations, cfg._disk_text))
                try:
                    cfg.set_option(sec, "mode", "default")
                    cfg.save()
                except SaveCommittedError as error:
                    s.reload()
                    _operation_error(s.app, _("Output added; recovery needs attention"), error)
                    return
                except OSError as error:
                    cfg.entries, cfg._operations, cfg._disk_text = previous
                    cfg._rebuild_index()
                    _operation_error(s.app, _("Could not add output"), error)
                    return
            s.reload()

        btn.connect("clicked", do_add)
        ent.connect("activate", do_add)
        return row


# Colors for the live .ini view (kept constant so the panel reads like a
# terminal regardless of the light/dark UI theme).
# Syntax-highlight colours for the live .ini editor, per theme. `_markup`
# reads whichever palette matches the active theme so the editor recolours
# (not just its chrome) when the light/dark switch is flipped.
_INI_PALETTE = {
    True: {  # dark
        "section": "#f0b84d", "key": "#5fd6cb", "eq": "#5a6172",
        "val": "#d7d3cb", "num": "#c9a9e6", "bool": "#7fd1a6",
        "comment": "#6d7488",
    },
    False: {  # light
        "section": "#b07818", "key": "#1f8f86", "eq": "#9a948c",
        "val": "#2a2520", "num": "#7a4fb0", "bool": "#2f8f5a",
        "comment": "#9a948c",
    },
}
_INI_DARK = True


def _ini_colors():
    return _INI_PALETTE[_INI_DARK]

# Shared width for the right-hand side panel so the editor and the embedded
# wiki/webpage render at exactly the same size (the panel must not resize when
# it switches from the .ini editor to a wiki page).
SIDE_PANEL_W = 800
# The live .ini editor is much narrower than a rendered web page, so it gets its
# own (smaller) width. The panel grows the window by whichever of these matches
# the view currently shown (editor vs wiki).
SIDE_INIPANEL_W = 400


class LiveIniPanel(Gtk.Box):
    """A live, syntax-highlighted view of the .ini file on disk.

    Whenever a config save fires, the panel re-renders and the lines that
    changed since the previous render flash with a glow, then it scrolls to
    the first change — so edits look like they're being written into the
    file in real time.
    """

    def __init__(s):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        s.add_css_class("ini-panel")
        s.set_size_request(SIDE_INIPANEL_W, -1)
        s.set_hexpand(False)

        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hdr.add_css_class("ini-header")
        dot = Gtk.Label(label="\u25cf")
        dot.add_css_class("ini-dot")
        hdr.append(dot)
        s._title = Gtk.Label(label="wayfire.ini")
        s._title.add_css_class("ini-title")
        s._title.set_xalign(0)
        s._title.set_hexpand(True)
        s._title.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        hdr.append(s._title)
        live = Gtk.Label(label=_("LIVE"))
        live.add_css_class("ini-live")
        hdr.append(live)
        s.append(hdr)

        s._scroll = Gtk.ScrolledWindow()
        s._scroll.set_vexpand(True)
        s._scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        s._scroll.add_css_class("ini-scroll")
        s._list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        s._list.add_css_class("ini-body")
        s._scroll.set_child(s._list)
        s.append(s._scroll)

        s._prev = {}
        s._first = True
        s._path = None
        s._anim_id = 0
        s._cfg = None

    def restyle(s):
        """Re-render with the current theme palette (no change-flash)."""
        if s._cfg is not None:
            s.show(s._cfg)

    def show(s, cfg):
        if cfg is None:
            return
        s._cfg = cfg
        path = getattr(cfg, "path", None)
        s._title.set_text(os.path.basename(path) if path else "config.ini")
        file_changed = path != s._path
        s._path = path
        suppress = s._first or file_changed

        cur = {}
        for e in cfg.entries:
            if e.kind == "option":
                cur[(e.section, e.key)] = e.value

        c = s._list.get_first_child()
        while c:
            nxt = c.get_next_sibling()
            s._list.remove(c)
            c = nxt

        first_hot = None
        first_lbl = None
        ln = 0
        for e in cfg.entries:
            ln += 1
            hot = False
            if not suppress and e.kind == "option":
                kk = (e.section, e.key)
                if kk not in s._prev or s._prev[kk] != e.value:
                    hot = True
            row, lbl = s._make_line(ln, e, hot)
            s._list.append(row)
            if hot and first_hot is None:
                first_hot = row
                first_lbl = lbl

        s._prev = cur
        s._first = False
        if first_hot is not None:
            GLib.timeout_add(
                70, lambda r=first_hot, l=first_lbl: s._fly_to(r, l)
            )

    def _make_line(s, ln, e, hot):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        row.add_css_class("ini-line")
        if hot:
            row.add_css_class("ini-hot")
        num = Gtk.Label(label=str(ln))
        num.add_css_class("ini-gutter")
        num.set_xalign(1.0)
        num.set_width_chars(3)
        row.append(num)
        txt = Gtk.Label()
        txt.set_xalign(0)
        txt.set_hexpand(True)
        txt.set_wrap(False)
        # No ellipsis: long lines keep their full width so the panel can
        # scroll horizontally to reveal the part being edited.
        txt.set_ellipsize(Pango.EllipsizeMode.NONE)
        txt.set_use_markup(True)
        txt.set_markup(s._markup(e))
        txt.add_css_class("ini-text")
        row.append(txt)
        return row, txt

    def _markup(s, e):
        esc = GLib.markup_escape_text
        c = _ini_colors()
        if e.kind == "section":
            return (
                f"<span foreground='{c['section']}' weight='bold'>"
                f"[{esc(e.section or '')}]</span>"
            )
        if e.kind == "comment":
            return f"<span foreground='{c['comment']}'>{esc(e.text.rstrip())}</span>"
        if e.kind == "option":
            k = esc(e.key or "")
            v = str(e.value)
            vlow = v.strip().lower()
            if vlow in ("true", "false"):
                vc = c["bool"]
            else:
                vc = c["val"]
                try:
                    float(v.strip())
                    vc = c["num"]
                except ValueError:
                    pass
            return (
                f"<span foreground='{c['key']}'>{k}</span>"
                f"<span foreground='{c['eq']}'> = </span>"
                f"<span foreground='{vc}'>{esc(v)}</span>"
            )
        return " "

    def _fly_to(s, row, lbl):
        """Compute scroll targets (down to the line, across to reveal the
        edited part of a long line) and animate smoothly to them."""
        try:
            vadj = s._scroll.get_vadjustment()
            hadj = s._scroll.get_hadjustment()
            vtarget = vadj.get_value()
            htarget = 0.0

            okr, rr = row.compute_bounds(s._list)
            if okr:
                vpage = vadj.get_page_size()
                vtarget = rr.origin.y - vpage / 3.0
                vmax = max(0.0, vadj.get_upper() - vpage)
                vtarget = max(0.0, min(vtarget, vmax))

            if lbl is not None:
                okl, rl = lbl.compute_bounds(s._list)
                _mn, nat = lbl.get_preferred_size()
                if okl and nat is not None:
                    hpage = hadj.get_page_size()
                    line_right = rl.origin.x + nat.width + 18
                    if line_right > hpage:
                        hmax = max(0.0, hadj.get_upper() - hpage)
                        htarget = max(0.0, min(line_right - hpage, hmax))

            s._animate_scroll(vtarget, htarget)
        except Exception:
            pass
        return False

    def _animate_scroll(s, vtarget, htarget):
        vadj = s._scroll.get_vadjustment()
        hadj = s._scroll.get_hadjustment()
        v0 = vadj.get_value()
        h0 = hadj.get_value()
        if abs(vtarget - v0) < 0.5 and abs(htarget - h0) < 0.5:
            return
        if s._anim_id:
            try:
                s.remove_tick_callback(s._anim_id)
            except Exception:
                pass
            s._anim_id = 0
        dur = 520000.0  # microseconds (~0.52s)
        state = {"start": None}

        def tick(widget, fclock):
            now = fclock.get_frame_time()
            if state["start"] is None:
                state["start"] = now
            t = min(1.0, (now - state["start"]) / dur)
            e = 1.0 - pow(1.0 - t, 3)  # ease-out cubic
            vadj.set_value(v0 + (vtarget - v0) * e)
            hadj.set_value(h0 + (htarget - h0) * e)
            if t >= 1.0:
                s._anim_id = 0
                return False
            return True

        s._anim_id = s.add_tick_callback(tick)


class WikiView(Gtk.Box):
    """Shows Wayfire wiki pages inside the side panel, with a button to
    return to the live .ini editor. Uses an embedded WebKit view when
    available, otherwise offers to open the page in the default browser.
    """

    def __init__(s, on_back, open_external):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        s.add_css_class("ini-panel")
        s.set_size_request(SIDE_PANEL_W, -1)
        s.set_hexpand(False)
        s._open_external = open_external
        s._url = ""
        s._sandbox_retry = False
        # WebKitGTK often fails the very first load after the web process starts
        # ("internallyFailedLoadTimerFired"); a reload then works. We track load
        # success and silently retry so the page comes up on first open.
        s._load_ok = False
        s._load_retries = 0
        s._load_wd_id = 0
        s._max_load_retries = 5

        s._web = None
        if WebKit is not None:
            try:
                s._web = WebKit.WebView()
            except Exception:
                s._web = None

        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hdr.add_css_class("ini-header")
        editor_btn = Gtk.Button(label="\u2039 " + _("Close Help"))
        editor_btn.add_css_class("wiki-back")
        editor_btn.set_tooltip_text(_("Back to the WCM"))
        editor_btn.connect("clicked", lambda w: on_back())
        hdr.append(editor_btn)

        if s._web is not None:
            s._back = Gtk.Button.new_from_icon_name("go-previous")
            s._back.add_css_class("wiki-nav")
            s._back.set_tooltip_text(_("Back"))
            s._back.set_sensitive(False)
            s._back.connect("clicked", lambda w: s._web.go_back())
            hdr.append(s._back)
            s._fwd = Gtk.Button.new_from_icon_name("go-next")
            s._fwd.add_css_class("wiki-nav")
            s._fwd.set_tooltip_text(_("Forward"))
            s._fwd.set_sensitive(False)
            s._fwd.connect("clicked", lambda w: s._web.go_forward())
            hdr.append(s._fwd)
        else:
            s._back = s._fwd = None

        s._title = Gtk.Label(label=_("Wayfire Wiki"))
        s._title.add_css_class("ini-title")
        s._title.set_xalign(0)
        s._title.set_hexpand(True)
        s._title.set_ellipsize(Pango.EllipsizeMode.END)
        hdr.append(s._title)

        reload_btn = Gtk.Button.new_from_icon_name("view-refresh")
        reload_btn.add_css_class("wiki-nav")
        reload_btn.set_tooltip_text(_("Reload"))
        reload_btn.connect("clicked", lambda w: s.reload())
        hdr.append(reload_btn)

        ext_btn = Gtk.Button.new_from_icon_name("web-browser")
        ext_btn.add_css_class("wiki-nav")
        ext_btn.set_tooltip_text(_("Open in external browser"))
        ext_btn.connect("clicked", lambda w: s._open_external(s._url) if s._url else None)
        hdr.append(ext_btn)
        s.append(hdr)

        if s._web is not None:
            s._web.set_vexpand(True)
            s._web.set_hexpand(True)
            try:
                s._web.connect("load-changed", s._on_load_changed)
                s._web.connect("notify::title", s._on_title)
                s._web.connect("web-process-terminated", s._on_web_crash)
                s._web.connect("load-failed", s._on_load_failed)
            except Exception:
                pass
            # The WebView and a GTK error page share a stack, so when WebKit
            # can't load a page (network-process failure, Wayland protocol
            # error, etc.) the panel shows a usable fallback with a button to
            # open the page in the system browser, instead of a blank view.
            s._web_stack = Gtk.Stack()
            s._web_stack.set_vexpand(True)
            s._web_stack.set_hexpand(True)
            s._web_stack.add_named(s._web, "web")
            s._web_stack.add_named(s._build_error_page(), "error")
            s._web_stack.set_visible_child_name("web")
            s.append(s._web_stack)
        else:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            box.set_vexpand(True)
            box.set_valign(Gtk.Align.CENTER)
            box.set_margin_start(18)
            box.set_margin_end(18)
            msg = Gtk.Label()
            msg.set_wrap(True)
            msg.set_justify(Gtk.Justification.CENTER)
            msg.add_css_class("wiki-fallback")
            msg.set_markup(_(
                "<b>In-app wiki needs WebKitGTK</b>\n\n"
                "Install the GTK4 build (e.g. <tt>webkit2gtk-6.0</tt> / "
                "<tt>webkitgtk-6.0</tt>) to read wiki pages right here. "
                "For now you can open the page in your browser."
            ))
            box.append(msg)
            s._fb_label = Gtk.Label()
            s._fb_label.set_wrap(True)
            s._fb_label.set_justify(Gtk.Justification.CENTER)
            s._fb_label.add_css_class("wiki-fallback")
            box.append(s._fb_label)
            ob = Gtk.Button(label=_("Open in browser"))
            ob.add_css_class("action-btn")
            ob.set_halign(Gtk.Align.CENTER)
            ob.connect("clicked", lambda w: s._open_external(s._url) if s._url else None)
            box.append(ob)
            s.append(box)

    def do_measure(s, orientation, for_size):
        # The embedded WebView reports a large "natural" width for web content,
        # which would otherwise make the side panel render much wider than the
        # editor. Pin the horizontal measurement to the shared panel width so
        # the webpage is always exactly the same size the editor was.
        if orientation == Gtk.Orientation.HORIZONTAL:
            return (SIDE_PANEL_W, SIDE_PANEL_W, -1, -1)
        return Gtk.Box.do_measure(s, orientation, for_size)

    def _build_error_page(s):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_vexpand(True)
        box.set_valign(Gtk.Align.CENTER)
        box.set_margin_start(18)
        box.set_margin_end(18)
        head = Gtk.Label()
        head.set_wrap(True)
        head.set_justify(Gtk.Justification.CENTER)
        head.add_css_class("wiki-fallback")
        head.set_markup(_("<b>This page couldn't be loaded in-app</b>"))
        box.append(head)
        s._err_label = Gtk.Label()
        s._err_label.set_wrap(True)
        s._err_label.set_justify(Gtk.Justification.CENTER)
        s._err_label.add_css_class("wiki-fallback")
        s._err_label.set_text(_(
            "WebKit couldn't render the page (this is usually a WebKitGTK or "
            "Wayland issue, not the wiki). You can open it in your browser."
        ))
        box.append(s._err_label)
        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btns.set_halign(Gtk.Align.CENTER)
        retry = Gtk.Button(label=_("Retry"))
        retry.add_css_class("wiki-nav")
        retry.connect("clicked", lambda w: s.reload())
        btns.append(retry)
        ob = Gtk.Button(label=_("Open in browser"))
        ob.add_css_class("action-btn")
        ob.connect("clicked", lambda w: s._open_external(s._url) if s._url else None)
        btns.append(ob)
        box.append(btns)
        return box

    def _show_web(s):
        if getattr(s, "_web_stack", None) is not None:
            s._web_stack.set_visible_child_name("web")

    def _show_error(s, url="", msg=""):
        if getattr(s, "_err_label", None) is not None:
            text = _("WebKit couldn't render the page (usually a WebKitGTK "
                     "or Wayland issue, not the wiki).")
            if msg:
                text += f"\n\n{msg}"
            if url:
                text += f"\n\n{url}"
            s._err_label.set_text(text)
        if getattr(s, "_web_stack", None) is not None:
            s._web_stack.set_visible_child_name("error")

    def load(s, url):
        s._url = url
        s._load_ok = False
        s._load_retries = 0
        s._title.set_text(_("Wayfire Wiki"))
        s._show_web()
        if s._web is not None:
            s._web.load_uri(url)
            s._arm_load_watchdog()
        elif getattr(s, "_fb_label", None) is not None:
            s._fb_label.set_text(url)

    def _arm_load_watchdog(s):
        # Backstop for the case where the first load stalls *silently* (no
        # load-failed signal). If the page hasn't committed within the timeout,
        # quietly re-issue the load, a few times, the way a manual reload would.
        if s._load_wd_id:
            try:
                GLib.source_remove(s._load_wd_id)
            except Exception:
                pass
            s._load_wd_id = 0

        def _tick():
            if s._load_ok or s._web is None or not s._url:
                s._load_wd_id = 0
                return False
            if s._load_retries >= s._max_load_retries:
                s._load_wd_id = 0
                return False
            s._load_retries += 1
            try:
                s._show_web()
                s._web.load_uri(s._url)
            except Exception:
                s._load_wd_id = 0
                return False
            return True  # keep watching until it commits or we hit the cap

        s._load_wd_id = GLib.timeout_add(1500, _tick)

    def reload(s):
        s._load_ok = False
        s._load_retries = 0
        if s._web is not None:
            s._show_web()
            if s._url:
                s._web.load_uri(s._url)
            else:
                s._web.reload()
            s._arm_load_watchdog()
        elif s._url:
            s._open_external(s._url)

    def _on_title(s, web, _p):
        t = web.get_title()
        if t:
            s._title.set_text(t)

    def _on_load_changed(s, web, event):
        try:
            if event == WebKit.LoadEvent.STARTED:
                s._show_web()  # a fresh load clears any previous error page
            elif event in (WebKit.LoadEvent.COMMITTED, WebKit.LoadEvent.FINISHED):
                # The page actually started rendering: stop the retry watchdog.
                s._load_ok = True
        except Exception:
            pass
        try:
            if s._back is not None:
                s._back.set_sensitive(web.can_go_back())
            if s._fwd is not None:
                s._fwd.set_sensitive(web.can_go_forward())
        except Exception:
            pass

    def _on_load_failed(s, web, load_event, failing_uri, error):
        # Fires for genuine load failures, including the WebKit
        # "internallyFailedLoadTimerFired" network-process failure. Skip the
        # cancellations that happen normally during redirects/navigation.
        msg = ""
        try:
            msg = error.message or ""
        except Exception:
            pass
        if "cancel" in msg.lower():
            return False
        # The first load after the web process starts frequently fails with an
        # internal WebKit error; a reload reliably works. Quietly retry a few
        # times before giving up and showing the error page, so the page comes
        # up on first open instead of forcing the user to hit reload.
        if s._load_retries < s._max_load_retries:
            s._load_retries += 1
            url = failing_uri or s._url
            if url and s._web is not None:
                GLib.timeout_add(
                    300 * s._load_retries,
                    lambda: (s._show_web(), s._web.load_uri(url), False)[2])
                return True  # suppress WebKit's default error page while we retry
        s._title.set_text(_("Couldn't load page"))
        s._show_error(failing_uri or s._url, msg)
        return True  # we showed our own page; suppress WebKit's default one

    def _on_web_crash(s, *_args):
        # bwrap/userns failures surface as a terminated web process. If we
        # haven't already, disable the sandbox and retry once — the only
        # recovery path on WebKit 6.0. Otherwise show the fallback page.
        if not s._sandbox_retry:
            s._sandbox_retry = True
            os.environ["WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS"] = "1"
            if s._url and s._web is not None:
                GLib.timeout_add(250, lambda: (s._web.load_uri(s._url), False)[1])
            return False
        s._title.set_text(_("Couldn't render the page"))
        s._show_error(s._url, _("The WebKit process stopped unexpectedly."))
        return False


class WCM(Gtk.ApplicationWindow):
    def __init__(s, app, config_path=None):
        super().__init__(application=app, title=_("Wayfire Config Manager"))
        # The side panel is collapsed by default, so the window opens at the
        # usual (panel-less) WCM size and grows wider when the panel is opened.
        s.set_default_size(1000, 600)
        s.set_size_request(640, 520)
        ip = find_app_icon()
        if ip:
            try:
                GdkPixbuf.Pixbuf.new_from_file(ip)
                s.set_icon_name("wcm")
            except:
                pass
        s.connect("close-request", s._before_close)
        s.config = WayfireConfigFile(get_config_path(config_path))
        s.wf_shell_config = WayfireConfigFile(get_wfshell_config_path(config_path))
        s.preset_mgr = PresetManager()
        s.plugins = load_all_metadata()
        if not s.plugins:
            s._gen_from_config()
        enabled = s.config.get_enabled_plugins()
        for p in s.plugins:
            p.enabled = (
                p.is_core_plugin or p.type == PluginType.WF_SHELL or p.name in enabled
            )
        s.plugins.sort(
            key=lambda p: (
                get_category_index(p.category),
                (p.disp_name or p.name).lower(),
            )
        )
        _resolve_icon_dirs()
        s.current_plugin = None
        s._dark = _system_prefers_dark(True)
        _apply_theme(s._dark)
        s._build_ui()
        s._watch_system_theme()
        kc = Gtk.EventControllerKey()
        kc.connect("key-pressed", s._on_key)
        s.add_controller(kc)

    def _before_close(s, *args):
        try:
            s.config.flush_pending_edits()
            s.wf_shell_config.flush_pending_edits()
            if s.display_page is not None:
                s.display_page.revert_pending_changes()
        except OSError as error:
            _operation_error(s, _("Could not save changes. Window kept open."), error)
            return True
        return False

    def _gen_from_config(s):
        for sec in s.config.get_sections():
            p = Plugin()
            p.name = sec
            p.disp_name = sec.replace("-", " ").replace("_", " ").title()
            p.category = "Other"
            p.type = PluginType.WAYFIRE
            p.tooltip = _("Configuration for {section}").format(section=sec)
            g = Option(name="General", type=OptionType.GROUP, plugin_name=sec)
            for k, v in s.config.get_section_options(sec).items():
                o = Option()
                o.name = k
                o.disp_name = k.replace("_", " ").title()
                o.plugin_name = sec
                o.default_value = v
                if v.lower() in ("true", "false"):
                    o.type = OptionType.BOOL
                    o.default_value = v.lower() == "true"
                else:
                    try:
                        o.default_value = int(v)
                        o.type = OptionType.INT
                    except ValueError:
                        try:
                            o.default_value = float(v)
                            o.type = OptionType.DOUBLE
                        except ValueError:
                            o.type = OptionType.STRING
                            o.default_value = v
                g.options.append(o)
            if g.options:
                p.option_groups.append(g)
            s.plugins.append(p)

    def _side_panel_width(s):
        """Target width of the side panel for whichever view is showing: the
        wide rendered wiki page vs the narrow live .ini editor."""
        ss = getattr(s, "side_stack", None)
        if ss is not None and ss.get_visible_child_name() == "wiki":
            return SIDE_PANEL_W
        return SIDE_INIPANEL_W

    def _side_toggle_icon_name(s, open_):
        return "sidebar-hide-right-symbolic" if open_ else "sidebar-show-right-symbolic"

    def _set_side_panel(s, open_):
        if s._side_open == open_:
            return
        s._side_open = open_
        # Keep every "show/collapse panel" button (main + plugin panels) in sync.
        for img in getattr(s, "_side_toggle_imgs", []):
            img.set_from_icon_name(s._side_toggle_icon_name(open_))
        for btn in getattr(s, "_side_toggle_btns", []):
            btn.set_tooltip_text(_("Hide side panel") if open_ else _("Show side panel"))
        if open_:
            s.left_stack.set_visible_child_name("thin")
            # Capture the panel-less width only when we're starting from a fully
            # collapsed state, so a fast reverse mid-animation keeps the right
            # base instead of reading a half-animated width.
            if (not s._resize_tick_id
                    and not s._side_revealer.get_child_revealed()):
                s._collapsed_w = max(s.get_width(), 1)
            s._side_revealer.set_reveal_child(True)
            s._anim_panel_w = s._side_panel_width()
        else:
            s.left_stack.set_visible_child_name(
                getattr(s, "_page_left_child", "main"))
            if not getattr(s, "_collapsed_w", 0):
                s._collapsed_w = max(640, s.get_width() - s._side_panel_width())
            s._side_revealer.set_reveal_child(False)
            s._anim_panel_w = 0
        # The window without the panel is always the collapsed width; the panel
        # slides in on top of it. Height isn't animated, so keep whatever it is.
        s._anim_base_w = max(getattr(s, "_collapsed_w", 0) or s.get_width(), 1)
        s._anim_base_h = max(s.get_height(), 1)
        s._start_resize_anim(open_)

    def _start_resize_anim(s, target_open):
        """Drive the window width so it stays snug against the sliding panel.

        The revealer animates its own width between 0 and the panel's width
        (SIDE_INIPANEL_W for the editor, SIDE_PANEL_W for the wiki); each
        frame we read that width and size the window to base + panel, so the
        window grows/shrinks smoothly in lockstep with the slide — no snap, no
        clipping, and the shrink actually happens (a plain size-request can't
        shrink a window, but pairing it with the collapsing revealer can)."""
        s._stop_resize_anim()
        s._resize_target_open = target_open
        clock = s.get_frame_clock()
        if clock is None:
            # No frame clock (window not mapped yet) — just snap to the target.
            s._finish_resize_anim()
            return
        s._resize_t0 = clock.get_frame_time()
        try:
            s._resize_tick_id = s.add_tick_callback(s._resize_tick)
        except Exception:
            s._resize_tick_id = 0
            s._finish_resize_anim()

    def _resize_tick(s, _widget, clock, *_args):
        rev = getattr(s, "_side_revealer", None)
        if rev is None:
            s._finish_resize_anim()
            return False
        panel_w = max(rev.get_width(), 0)
        w = s._anim_base_w + panel_w
        s.set_size_request(w, s._anim_base_h)
        s.set_default_size(w, s._anim_base_h)
        # The transition is finished once the revealer reaches its target state.
        done = (rev.get_child_revealed() == s._resize_target_open)
        # Safety valve so a stuck transition can't keep the callback alive.
        if clock.get_frame_time() - s._resize_t0 > 900_000:
            done = True
        if done:
            s._resize_tick_id = 0
            s._finish_resize_anim()
            return False
        return True

    def _finish_resize_anim(s):
        # Settle on the exact final size, then relax the forced minimum so the
        # user can resize the window freely again.
        fw = s._anim_base_w + getattr(s, "_anim_panel_w", 0)
        s.set_size_request(fw, s._anim_base_h)
        s.set_default_size(fw, s._anim_base_h)
        GLib.timeout_add(40, lambda: (s.set_size_request(640, 520), False)[1])
        s._side_anim_id = 0

    def _stop_resize_anim(s):
        if getattr(s, "_resize_tick_id", 0):
            try:
                s.remove_tick_callback(s._resize_tick_id)
            except Exception:
                pass
            s._resize_tick_id = 0

    def _sync_left_panel(s):
        """Show the left panel that matches the current page, unless the side
        panel is expanded — in which case the left rail stays collapsed to the
        thin strip. Called after every navigation so the plugin/display/main
        panels and the expandable side panel never fight over the left stack."""
        if hasattr(s, "_thin_back_btn"):
            show_back = getattr(s, "_page_left_child", "main") == "plugin"
            s._thin_back_btn.set_opacity(1.0 if show_back else 0.0)
            s._thin_back_btn.set_sensitive(show_back)
        if getattr(s, "_side_open", False):
            s.left_stack.set_visible_child_name("thin")
        else:
            s.left_stack.set_visible_child_name(
                getattr(s, "_page_left_child", "main"))

    def _build_ui(s):
        gb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        s.left_stack = Gtk.Stack()
        s.left_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        s.left_stack.set_transition_duration(450)
        s.left_stack.add_css_class("left-panel")
        s.left_stack.set_vexpand(True)
        s.left_stack.set_size_request(0, -1)
        s.left_stack.set_hexpand(False)
        s.left_stack.set_halign(Gtk.Align.START)
        s._left_panel_size_group = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        ml = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        s._left_content = Gtk.Revealer()
        s._left_content.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        s._left_content.set_transition_duration(250)
        s._left_content.set_reveal_child(True)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        fl = Gtk.Label()
        fl.set_markup("<span size='large'><b>"
                      + GLib.markup_escape_text(_("Filter")) + "</b></span>")
        fl.set_margin_top(14)
        fl.set_margin_start(14)
        fl.add_css_class("filter-label")
        inner.append(fl)
        s.search_entry = Gtk.SearchEntry()
        s.search_entry.add_css_class("plugin-search")
        s.search_entry.set_placeholder_text(_("Search plugins…"))
        s.search_entry.set_margin_start(14)
        s.search_entry.set_margin_end(14)
        s.search_entry.set_margin_top(8)
        s.search_entry.connect("search-changed", s._on_search)
        inner.append(s.search_entry)

        # --- Master presets section ---
        ps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        ps.add_css_class("preset-section")
        ph = Gtk.Label(label=_("PRESETS"))
        ph.set_xalign(0)
        ph.add_css_class("preset-header")
        ps.append(ph)
        s._master_combo = Gtk.ComboBoxText()
        s._master_combo.add_css_class("preset-combo")
        s._master_combo.set_hexpand(True)
        s._refresh_master_presets()
        ps.append(s._master_combo)
        pb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        pb.add_css_class("preset-btn-box")
        pb.set_margin_top(4)
        lb = Gtk.Button(label=_("Load"))
        lb.add_css_class("preset-load")
        lb.connect("clicked", s._on_master_load)
        pb.append(lb)
        sb = Gtk.Button(label=_("Save"))
        sb.add_css_class("preset-save")
        sb.connect("clicked", s._on_master_save)
        pb.append(sb)
        db = Gtk.Button(label=_("Delete"))
        db.add_css_class("preset-delete")
        db.connect("clicked", s._on_master_delete)
        pb.append(db)
        ps.append(pb)
        inner.append(ps)

        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        inner.append(spacer)
        inner.append(s._make_side_toggle_btn())
        disp_btn = s._make_button(_("Display"), "preferences-desktop-display")
        disp_btn.add_css_class("action-btn")
        disp_btn.set_margin_start(14)
        disp_btn.set_margin_end(14)
        disp_btn.set_margin_bottom(8)
        disp_btn.connect("clicked", s.open_display)
        inner.append(disp_btn)

        ob = s._make_button(_("Outputs"), "video-display")
        ob.add_css_class("action-btn")
        ob.set_margin_start(14)
        ob.set_margin_end(14)
        ob.set_margin_bottom(8)
        ob.connect("clicked", s._launch_wd)
        inner.append(ob)
        cb = s._make_button(_("Close"), "window-close")
        cb.add_css_class("action-btn")
        cb.add_css_class("close-btn")
        cb.set_margin_start(14)
        cb.set_margin_end(14)
        cb.set_margin_bottom(14)
        cb.connect("clicked", lambda w: s.close())
        inner.append(cb)
        s._left_content.set_child(inner)
        ml.append(s._left_content)
        s._left_panel_size_group.add_widget(ml)
        s.left_stack.add_named(ml, "main")
        pl = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        s.pnl = Gtk.Label()
        s.pnl.set_wrap(True)
        s.pnl.set_max_width_chars(15)
        s.pnl.set_justify(Gtk.Justification.CENTER)
        s.pnl.set_halign(Gtk.Align.CENTER)
        s.pnl.set_margin_top(50)
        s.pnl.set_margin_bottom(25)
        s.pnl.set_margin_start(10)
        s.pnl.set_margin_end(10)
        s.pnl.add_css_class("plugin-title")
        pl.append(s.pnl)

        s.pdl = Gtk.Label()
        s.pdl.set_wrap(True)
        s.pdl.set_max_width_chars(20)
        s.pdl.set_justify(Gtk.Justification.CENTER)
        s.pdl.set_halign(Gtk.Align.CENTER)
        s.pdl.set_margin_start(10)
        s.pdl.set_margin_end(10)
        s.pdl.add_css_class("plugin-desc")
        pl.append(s.pdl)
        s.eb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        s.eb.set_halign(Gtk.Align.CENTER)
        s.eb.set_margin_top(25)
        s.eb.add_css_class("enabled-toggle")
        s.ec = Gtk.CheckButton()
        s.eb.append(s.ec)
        s.el = Gtk.Label(label=_("Use This Plugin"))
        s.eb.append(s.el)
        s.ec.connect("toggled", s._on_pe)
        pl.append(s.eb)

        # --- Plugin presets section ---
        pps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        pps.add_css_class("preset-section")
        pps.set_margin_top(12)
        pph = Gtk.Label(label=_("PLUGIN PRESETS"))
        pph.set_xalign(0)
        pph.add_css_class("preset-header")
        pps.append(pph)
        s._plugin_combo = Gtk.ComboBoxText()
        s._plugin_combo.add_css_class("preset-combo")
        s._plugin_combo.set_hexpand(True)
        pps.append(s._plugin_combo)
        ppb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        ppb.add_css_class("preset-btn-box")
        ppb.set_margin_top(4)
        plb = Gtk.Button(label=_("Load"))
        plb.set_tooltip_text(_("Merge saved settings. Extra commands and settings are kept."))
        plb.add_css_class("preset-load")
        plb.connect("clicked", s._on_plugin_load)
        ppb.append(plb)
        psb = Gtk.Button(label=_("Save"))
        psb.add_css_class("preset-save")
        psb.connect("clicked", s._on_plugin_save)
        ppb.append(psb)
        pdb = Gtk.Button(label=_("Delete"))
        pdb.add_css_class("preset-delete")
        pdb.connect("clicked", s._on_plugin_delete)
        ppb.append(pdb)
        pps.append(ppb)
        pl.append(pps)

        sp2 = Gtk.Box()
        sp2.set_vexpand(True)
        pl.append(sp2)
        pl.append(s._make_side_toggle_btn())
        wk = s._make_button(_("Wiki"), "help-browser")
        wk.add_css_class("action-btn")
        wk.set_margin_start(14)
        wk.set_margin_end(14)
        wk.set_margin_bottom(8)
        wk.set_tooltip_text(_("Open the Wayfire wiki for this plugin"))
        wk.connect("clicked", s._open_wiki)
        pl.append(wk)
        bb = s._make_button(_("Back"), "go-previous")
        bb.add_css_class("action-btn")
        bb.add_css_class("back-btn")
        bb.set_margin_start(14)
        bb.set_margin_end(14)
        bb.set_margin_bottom(14)
        bb.connect("clicked", lambda w: s.open_page(None))
        pl.append(bb)
        s._left_panel_size_group.add_widget(pl)
        s.left_stack.add_named(pl, "plugin")



        # --- DISPLAY left panel ---
        dlp = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        dtitle = Gtk.Label()
        dtitle.set_markup("<span size='12000'><b>"
                          + GLib.markup_escape_text(_("DISPLAY")) + "</b></span>")
        dtitle.set_halign(Gtk.Align.CENTER)
        dtitle.set_margin_top(50)
        dtitle.set_margin_bottom(20)
        dtitle.add_css_class("plugin-title")
        dlp.append(dtitle)
        ddesc = Gtk.Label()
        ddesc.set_wrap(True)
        ddesc.set_max_width_chars(24)
        ddesc.set_justify(Gtk.Justification.CENTER)
        ddesc.set_halign(Gtk.Align.CENTER)
        ddesc.set_margin_start(12)
        ddesc.set_margin_end(12)
        ddesc.set_text(_(
            "Set resolution, refresh rate, scale, position and rotation for "
            "each monitor, or turn outputs on and off. Changes are written "
            "to wayfire.ini. Connected displays refresh automatically; saved "
            "settings are kept when a monitor is unplugged."
        ))
        ddesc.add_css_class("plugin-desc")
        dlp.append(ddesc)
        dsp = Gtk.Box()
        dsp.set_vexpand(True)
        dlp.append(dsp)
        drb = s._make_button(_("Detect Outputs"), "view-refresh")
        drb.set_tooltip_text(_(
            'Refresh connected displays and their available resolutions and refresh rates '
            'using wlr-randr. Saved displays remain listed when disconnected. '
            'Also updates which display is protected from being disabled, based on '
            'the display containing this window. This does not change display settings.'
        ))
        drb.add_css_class("action-btn")
        drb.add_css_class("back-btn")
        drb.set_margin_start(14)
        drb.set_margin_end(14)
        drb.set_margin_bottom(8)
        drb.connect("clicked",
                    lambda w: s.display_page and s.display_page.reload())
        dlp.append(drb)
        dbb = s._make_button(_("Back"), "go-previous")
        dbb.add_css_class("action-btn")
        dbb.add_css_class("back-btn")
        dbb.set_margin_start(14)
        dbb.set_margin_end(14)
        dbb.set_margin_bottom(14)
        dbb.connect("clicked", lambda w: s.open_page(None))
        dlp.append(dbb)
        s._left_panel_size_group.add_widget(dlp)
        s.left_stack.add_named(dlp, "display")
        gb.append(s.left_stack)
        s.main_stack = Gtk.Stack()
        s.main_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        s.main_stack.set_transition_duration(500)
        s.main_stack.set_hexpand(True)
        s.main_stack.set_vexpand(True)
        s.main_page = MainPage(s.plugins, s)
        s.main_stack.add_named(s.main_page, "main")
        gb.append(s.main_stack)

        # Thin strip shown when side panel is open
        thin = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        thin.set_size_request(48, -1)
        thin.set_hexpand(False)
        thin.set_halign(Gtk.Align.START)
        thin.add_css_class("left-panel")
        back_thin = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        back_thin.add_css_class("wiki-nav")
        back_thin.add_css_class("side_toggle_btn")
        back_thin.set_tooltip_text(_("Close panel"))
        back_thin.set_margin_start(14)
        back_thin.set_margin_end(14)
        back_thin.set_margin_top(10)
        back_thin.set_margin_bottom(8)
        back_thin.connect("clicked", s._toggle_side_panel)
        thin.append(back_thin)

        brand = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        brand.set_vexpand(True)
        brand.set_valign(Gtk.Align.CENTER)
        brand.set_halign(Gtk.Align.CENTER)
        brand.add_css_class("thin-brand")

        badge_path = s._make_wayfire_rail_badge()
        if badge_path:
            badge = Gtk.Picture.new_for_filename(badge_path)
            badge.set_size_request(40, 320)
            badge.set_can_shrink(True)
            badge.add_css_class("thin-brand-badge")
            brand.append(badge)
        else:
            # Fallback for systems that cannot render the SVG badge: still show
            # a neat stacked rail without using unsupported Gtk.Label rotation.
            rail_icon = (
                find_icon("wcm.svg")
                or find_icon("wcm.png")
                or find_icon("wayfire.svg")
                or find_icon("wayfire.png")
            )
            if rail_icon:
                top_img = Gtk.Image.new_from_file(rail_icon)
                top_img.set_pixel_size(18)
                top_img.add_css_class("thin-brand-icon")
                brand.append(top_img)
            for ch in "WAYFIRE":
                ll = Gtk.Label(label=ch)
                ll.add_css_class("thin-brand-letter")
                ll.set_halign(Gtk.Align.CENTER)
                brand.append(ll)

        thin.append(brand)

        s._thin_back_btn = Gtk.Button.new_from_icon_name("go-previous")
        s._thin_back_btn.add_css_class("thin-back-btn")
        s._thin_back_btn.set_tooltip_text(_("Back to plugin selection"))
        s._thin_back_btn.set_opacity(0.0)
        s._thin_back_btn.set_sensitive(False)
        s._thin_back_btn.connect("clicked", lambda w: s.open_page(None))
        thin.append(s._thin_back_btn)

        s.left_stack.add_named(thin, "thin")
        s.left_stack.set_visible_child_name("main")
        s.left_stack.set_hhomogeneous(False)
        s._sync_left_panel()

        # --- Live .ini panel + embedded wiki on the right ---
        s.ini_panel = LiveIniPanel()
        s.wiki_view = WikiView(on_back=s._show_editor, open_external=s._open_url)
        s.side_stack = Gtk.Stack()
        s.side_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        s.side_stack.set_transition_duration(300)
        # Size to whichever view is visible (narrow editor vs wide wiki) rather
        # than always reserving the widest child's width.
        s.side_stack.set_hhomogeneous(False)
        s.side_stack.set_hexpand(False)
        s.side_stack.add_named(s.ini_panel, "editor")
        s.side_stack.add_named(s.wiki_view, "wiki")
        s.side_stack.set_visible_child_name("editor")

        # The whole side panel lives in a Revealer so it slides in/out cleanly:
        # its measured width animates between 0 and the visible view's width
        # (narrow editor vs wide wiki), which we read each frame to grow/shrink
        # the window in lockstep (see _resize_tick). It starts collapsed, so the
        # window opens at the usual panel-less size.
        s._side_revealer = Gtk.Revealer()
        s._side_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        s._side_revealer.set_transition_duration(280)
        s._side_revealer.set_child(s.side_stack)
        s._side_revealer.set_reveal_child(False)
        gb.append(s._side_revealer)
        s._side_open = False
        s._side_anim_id = 0
        s._resize_tick_id = 0
        s._collapsed_w = 0
        # Which left panel belongs to the page currently shown in main_stack
        # (main / plugin / display). This is the single source of truth the
        # side-panel expand/collapse restores to, so navigating into a plugin
        # always shows that plugin's left panel rather than the main menu.
        s._page_left_child = "main"

        # --- collapse / expand rail, sat at the top-right just before the
        # side panel. The button hides or shows the whole side panel (editor
        # *and* webpage) and grows/shrinks the window width to match. ---
        s._side_rail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        s._side_rail.set_valign(Gtk.Align.START)
        s._side_rail.add_css_class("side-rail")

        s.config.add_save_listener(lambda c: s.ini_panel.show(c))
        if s.wf_shell_config is not s.config:
            s.wf_shell_config.add_save_listener(lambda c: s.ini_panel.show(c))
        s.ini_panel.show(s.config)

        s.set_child(gb)
        s.plugin_page = None
        s.display_page = None

    def _make_wayfire_rail_badge(s):
        """Create a small SVG badge used in the collapsed left rail.

        This avoids Gtk.Label.set_angle(), which is not available in GTK4, and
        avoids relying on CSS transforms, which some GTK themes/builds ignore.
        """
        try:
            cache_dir = os.path.join(tempfile.gettempdir(), "pywcm")
            os.makedirs(cache_dir, exist_ok=True)
            path = os.path.join(cache_dir, "wayfire-rail-badge.svg")
            if not os.path.exists(path):
                svg = """<svg xmlns="http://www.w3.org/2000/svg" width="44" height="320" viewBox="0 0 44 320">
  <defs>
    <filter id="glow" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur stdDeviation="2.2" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <linearGradient id="gold" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffd36c"/>
      <stop offset="0.55" stop-color="#d99b20"/>
      <stop offset="1" stop-color="#9f6812"/>
    </linearGradient>
  </defs>

  <g opacity="0.95">
    <text x="22" y="170"
          transform="rotate(-90 22 170)"
          text-anchor="middle"
          dominant-baseline="middle"
          font-family="Cantarell, Noto Sans, Segoe UI, sans-serif"
          font-size="25"
          font-weight="900"
          letter-spacing="6.5"
          fill="url(#gold)"
          filter="url(#glow)">WAYFIRE</text>
  </g>

  <g transform="translate(22 28)" filter="url(#glow)">
    <path d="M0,-16 L14,-8 L14,8 L0,16 L-14,8 L-14,-8 Z"
          fill="#111827" stroke="#d99b20" stroke-width="1.8"/>
    <path d="M0,-11 C8,-10 12,-2 7,5 C4,11 -5,11 -9,5 C-12,-2 -7,-10 0,-11Z"
          fill="#e94124"/>
    <path d="M0,-12 C-6,-6 -6,4 0,10 C6,4 6,-6 0,-12Z"
          fill="#f2b11b"/>
    <path d="M-10,2 C-3,2 5,-3 9,-8 C10,1 6,9 -2,11 C-6,9 -9,6 -10,2Z"
          fill="#11a37f"/>
  </g>

  <g transform="translate(22 292)" filter="url(#glow)">
    <path d="M0,-16 L14,-8 L14,8 L0,16 L-14,8 L-14,-8 Z"
          fill="#111827" stroke="#d99b20" stroke-width="1.8"/>
    <path d="M0,-11 C8,-10 12,-2 7,5 C4,11 -5,11 -9,5 C-12,-2 -7,-10 0,-11Z"
          fill="#e94124"/>
    <path d="M0,-12 C-6,-6 -6,4 0,10 C6,4 6,-6 0,-12Z"
          fill="#f2b11b"/>
    <path d="M-10,2 C-3,2 5,-3 9,-8 C10,1 6,9 -2,11 C-6,9 -9,6 -10,2Z"
          fill="#11a37f"/>
  </g>
</svg>
"""
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(svg)
            return path
        except Exception:
            return None

    def _make_side_toggle_btn(s):
        """Create a 'show / collapse side panel' button. Several of these can
        exist (one per left panel), so each is registered and kept in sync by
        _set_side_panel. Clicking any of them toggles the side panel, which in
        turn collapses the left rail to the thin strip for consistency."""
        if not hasattr(s, "_side_toggle_btns"):
            s._side_toggle_btns = []
            s._side_toggle_imgs = []
        open_ = getattr(s, "_side_open", False)
        btn = Gtk.Button()
        btn.add_css_class("wiki-nav")
        btn.add_css_class("side_toggle_btn")
        btn.set_margin_start(14)
        btn.set_margin_end(14)
        btn.set_margin_bottom(8)
        img = Gtk.Image.new_from_icon_name(s._side_toggle_icon_name(open_))
        btn.set_child(img)
        btn.set_tooltip_text(_("Hide side panel") if open_ else _("Show side panel"))
        btn.connect("clicked", s._toggle_side_panel)
        s._side_toggle_btns.append(btn)
        s._side_toggle_imgs.append(img)
        # Keep the legacy single-button references pointing at the first one.
        s._side_toggle_btn = s._side_toggle_btns[0]
        s._side_toggle_img = s._side_toggle_imgs[0]
        return btn

    def _make_button(s, text, icon):
        btn = Gtk.Button()
        bx = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        bx.set_halign(Gtk.Align.CENTER)
        bx.append(Gtk.Image.new_from_icon_name(icon))
        bx.append(Gtk.Label(label=text))
        btn.set_child(bx)
        return btn

    def _open_url(s, url):
        try:
            Gio.AppInfo.launch_default_for_uri(url, None)
            return
        except Exception:
            pass
        for cmd in (["xdg-open", url], ["gio", "open", url]):
            try:
                subprocess.Popen(cmd)
                return
            except Exception:
                continue

    def _wiki_url_for(s, plg):
        """Return the documentation for the plugin's repository and identifier."""
        return plugin_wiki_url(plg)

    def _open_wiki(s, *_):
        url = s._wiki_url_for(s.current_plugin)
        if getattr(s, "wiki_view", None) and getattr(s, "side_stack", None):
            s.wiki_view.load(url)
            s.side_stack.set_visible_child_name("wiki")
            s._set_side_panel(True)
        else:
            s._open_url(url)

    def _show_editor(s, *_):
        # Collapse the panel, animating from whatever it's currently showing
        # (the wide wiki at this point), then quietly reset to the editor view
        # once it's hidden so the next open shows the editor at its own width.
        # Switching the child before the slide would snap the width first.
        s._set_side_panel(False)

        def _reset_to_editor():
            if getattr(s, "side_stack", None):
                s.side_stack.set_visible_child_name("editor")
            return False

        GLib.timeout_add(360, _reset_to_editor)

    def _toggle_side_panel(s, *_):
        s._set_side_panel(not getattr(s, "_side_open", False))


    def _cfg_for(s, plg):
        """Return the correct config file for a plugin.

        wf-shell plugins (background, panel, dock, etc.) read from
        wf-shell.ini, not wayfire.ini.  The C++ WCM handles this
        with separate wf::config instances; we mirror that here.
        """
        if plg.type == PluginType.WF_SHELL:
            return s.wf_shell_config
        return s.config

    def _sync_system_theme(s, *_args):
        dark = _system_prefers_dark(getattr(s, "_dark", True))
        if dark == getattr(s, "_dark", None):
            return False
        s._dark = dark
        _apply_theme(dark)
        # The editor's syntax colours are inline Pango markup, so re-render it
        # to pick up the new palette (the CSS-based chrome updates on its own).
        if getattr(s, "ini_panel", None) is not None:
            s.ini_panel.restyle()
        return False

    def _watch_system_theme(s):
        """Follow the desktop light/dark preference while the app is open."""
        settings = Gtk.Settings.get_default()
        if settings is not None:
            for prop in (
                "gtk-theme-name",
                "gtk-application-prefer-dark-theme",
            ):
                try:
                    settings.connect(f"notify::{prop}", s._sync_system_theme)
                except Exception:
                    pass
        try:
            s._color_scheme_settings = Gio.Settings.new("org.gnome.desktop.interface")
            s._color_scheme_settings.connect(
                "changed::color-scheme", s._sync_system_theme
            )
        except Exception:
            s._color_scheme_settings = None

        # Some Wayfire / GTK setups do not emit a GTK notify signal when the
        # portal/GSettings colour scheme moves back from prefer-dark to default.
        # A light polling watch keeps the UI synced both ways without requiring
        # a restart.
        s._system_theme_watch_id = GLib.timeout_add_seconds(
            1, lambda: (s._sync_system_theme(), True)[1]
        )

    def _on_search(s, entry):
        s.main_page.set_filter(entry.get_text())

    def open_page(s, plg=None):
        s.config.flush_pending_edits()
        s.wf_shell_config.flush_pending_edits()
        if plg:
            if plg.name == "animate":
                # Read the saved list on every visit, including external edits.
                cfg = s.config
                if cfg.path and os.path.isfile(cfg.path):
                    cfg = WayfireConfigFile(cfg.path)
                merge_extra_animations(s.plugins, cfg.get_enabled_plugins())
            s.current_plugin = plg
            s.eb.set_visible(not plg.is_core_plugin and plg.type != PluginType.WF_SHELL)
            s.ec.handler_block_by_func(s._on_pe)
            s.ec.set_active(plg.enabled)
            s.ec.handler_unblock_by_func(s._on_pe)
            s.pnl.set_markup(
                f"<span size='12000'><b>{plg.disp_name or plg.name}</b></span>"
            )
            s.pdl.set_markup(f"<span size='10000'><b>{plg.tooltip or ''}</b></span>")
            _apply_tooltip(plg.tooltip, s.pnl, s.pdl)
            s._refresh_plugin_presets()
            if s.plugin_page:
                s.main_stack.remove(s.plugin_page)
            s.plugin_page = PluginPage(plg, s._cfg_for(plg))
            s.main_stack.add_named(s.plugin_page, "plugin")
            s.main_stack.set_visible_child_name("plugin")
            s._page_left_child = "plugin"
            # Keep the side panel pointed at the live editor (not a stale wiki)
            # and follow this plugin's config.
            if getattr(s, "side_stack", None):
                s.side_stack.set_visible_child_name("editor")
            if getattr(s, "ini_panel", None):
                s.ini_panel.show(s._cfg_for(plg))
            s._sync_left_panel()
        else:
            s.main_stack.set_visible_child_name("main")
            s.current_plugin = None
            s._page_left_child = "main"
            if getattr(s, "side_stack", None):
                s.side_stack.set_visible_child_name("editor")
            if getattr(s, "ini_panel", None):
                s.ini_panel.show(s.config)
            s._sync_left_panel()

    def open_display(s, btn=None):
        s.current_plugin = None
        if s.display_page is not None:
            s.display_page.revert_pending_changes()
            try:
                s.main_stack.remove(s.display_page)
            except Exception:
                pass
        s.display_page = DisplayPage(s)
        s.main_stack.add_named(s.display_page, "display")
        s.main_stack.set_visible_child_name("display")
        s._page_left_child = "display"
        s._sync_left_panel()

    def set_plugin_enabled(s, plg, en):
        if plg.is_core_plugin or plg.type == PluginType.WF_SHELL:
            return
        plg.enabled = en
        if en:
            s.config.enable_plugin(plg.name)
        else:
            s.config.disable_plugin(plg.name)
        s.config.save()
        for w in s.main_page._pw:
            if w.plugin is plg:
                w.check.handler_block_by_func(w._on_t)
                w.check.set_active(en)
                w.check.handler_unblock_by_func(w._on_t)
                if hasattr(w, "_refresh_visual_state"):
                    w._refresh_visual_state()
                break

    def _on_pe(s, c):
        if s.current_plugin:
            s.set_plugin_enabled(s.current_plugin, c.get_active())

    # ------------------------------------------------------------------
    # Preset helpers
    # ------------------------------------------------------------------

    def _refresh_master_presets(s):
        s._master_combo.remove_all()
        for name in s.preset_mgr.list_master_presets():
            s._master_combo.append_text(name)
        if s._master_combo.get_model().iter_n_children(None) > 0:
            s._master_combo.set_active(0)

    def _refresh_plugin_presets(s):
        s._plugin_combo.remove_all()
        if s.current_plugin:
            for name in s.preset_mgr.list_plugin_presets(s.current_plugin.name):
                s._plugin_combo.append_text(name)
            if s._plugin_combo.get_model().iter_n_children(None) > 0:
                s._plugin_combo.set_active(0)

    def _prompt_name(s, title, callback):
        """Show a dialog asking for a preset name, then call callback(name)."""
        dlg = Gtk.Window(
            title=title, modal=True, transient_for=s,
            default_width=340, default_height=120)
        dlg.add_css_class("grab-dialog")
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vb.set_margin_start(16); vb.set_margin_end(16)
        vb.set_margin_top(16); vb.set_margin_bottom(16)
        lbl = Gtk.Label(label=_("Preset name:"))
        lbl.set_xalign(0)
        vb.append(lbl)
        entry = Gtk.Entry()
        entry.set_hexpand(True)
        vb.append(entry)
        bb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bb.set_halign(Gtk.Align.END)
        ok_btn = Gtk.Button(label=_("Save"))
        ok_btn.add_css_class("preset-save")
        cancel_btn = Gtk.Button(label=_("Cancel"))

        def do_save(w):
            name = entry.get_text().strip()
            if name:
                dlg.close()
                callback(name)

        ok_btn.connect("clicked", do_save)
        entry.connect("activate", do_save)
        cancel_btn.connect("clicked", lambda w: dlg.close())
        bb.append(cancel_btn)
        bb.append(ok_btn)
        vb.append(bb)
        dlg.set_child(vb)
        dlg.present()

    # --- Master preset actions ---

    def _on_master_save(s, btn):
        def do(name):
            try:
                # Snapshot the whole config file(s) verbatim. Copying the
                # entire file preserves the multi-line `plugins = \ ...`
                # list and all formatting, so loading the preset later can
                # never blank out the enabled-plugins list.
                s.config.flush_pending_edits()
                s.wf_shell_config.flush_pending_edits()
                committed_warning = None
                try:
                    s.preset_mgr.save_master_preset_file(
                        name, s.config.path, s.wf_shell_config.path)
                except SaveCommittedError as error:
                    committed_warning = error
                s._refresh_master_presets()
                # Select the one just saved (stored under its sanitized name)
                saved = s.preset_mgr._sanitize(name)
                model = s._master_combo.get_model()
                it = model.get_iter_first()
                i = 0
                while it:
                    if model.get_value(it, 0) == saved:
                        s._master_combo.set_active(i)
                        break
                    it = model.iter_next(it)
                    i += 1
                if committed_warning is not None:
                    _operation_error(s, _("Preset saved; recovery needs attention"), committed_warning)
            except Exception as e:
                _preset_error(s, e)
        s._prompt_name(_("Save Master Preset"), do)

    def _on_master_load(s, btn):
        name = s._master_combo.get_active_text()
        if not name:
            return
        try:
            if s.display_page is not None:
                s.display_page.revert_pending_changes()
            # Copy the stored snapshot back over the live config file(s)
            # verbatim, then reload the in-memory config from disk.
            committed_warning = None
            try:
                s.preset_mgr.load_master_preset_file(
                    name, s.config.path, s.wf_shell_config.path)
            except SaveCommittedError as error:
                committed_warning = error
            # Synchronous loading cannot dispatch GTK timers. Cancel only
            # after success so failed loads leave pending typing intact.
            s.config.cancel_pending_edits()
            s.wf_shell_config.cancel_pending_edits()
            s.config = WayfireConfigFile(s.config.path)
            s.wf_shell_config = WayfireConfigFile(s.wf_shell_config.path)
            s.config.add_save_listener(lambda c: s.ini_panel.show(c))
            s.wf_shell_config.add_save_listener(lambda c: s.ini_panel.show(c))
            s.ini_panel.show(s.config)

            if s.display_page is not None:
                s.display_page.reload()

            # Refresh enabled states
            enabled = s.config.get_enabled_plugins()
            for p in s.plugins:
                p.enabled = (p.is_core_plugin or
                             p.type == PluginType.WF_SHELL or
                             p.name in enabled)
            # Refresh the main page checkboxes
            for w in s.main_page._pw:
                w.check.handler_block_by_func(w._on_t)
                w.check.set_active(w.plugin.enabled)
                w.check.handler_unblock_by_func(w._on_t)
                if hasattr(w, "_refresh_visual_state"):
                    w._refresh_visual_state()
            # Refresh plugin page if open
            if s.current_plugin:
                s.open_page(s.current_plugin)
            if committed_warning is not None:
                _operation_error(s, _("Preset loaded; recovery needs attention"), committed_warning)
        except Exception as e:
            _preset_error(s, e)

    def _on_master_delete(s, btn):
        name = s._master_combo.get_active_text()
        if not name:
            return
        try:
            committed_warning = None
            try:
                s.preset_mgr.delete_master_preset(name)
            except SaveCommittedError as error:
                committed_warning = error
            s._refresh_master_presets()
            if committed_warning is not None:
                _operation_error(s, _("Preset deleted; recovery needs attention"), committed_warning)
        except Exception as e:
            _preset_error(s, e)

    # --- Plugin preset actions ---

    def _on_plugin_save(s, btn):
        if not s.current_plugin:
            return
        plg = s.current_plugin

        def do(name):
            try:
                s._cfg_for(plg).flush_pending_edits()
                s.preset_mgr.save_plugin_preset(
                    name, plg.name, s._cfg_for(plg), manage_enabled=plg.type != PluginType.WF_SHELL)
                s._refresh_plugin_presets()
                saved = s.preset_mgr._sanitize(name)
                model = s._plugin_combo.get_model()
                it = model.get_iter_first()
                i = 0
                while it:
                    if model.get_value(it, 0) == saved:
                        s._plugin_combo.set_active(i)
                        break
                    it = model.iter_next(it)
                    i += 1
            except Exception as e:
                _preset_error(s, e)
        s._prompt_name(f"Save {plg.disp_name or plg.name} Preset", do)

    def _on_plugin_load(s, btn):
        if not s.current_plugin:
            return
        name = s._plugin_combo.get_active_text()
        if not name:
            return
        try:
            committed_warning = None
            try:
                s.preset_mgr.load_plugin_preset(
                    name, s.current_plugin.name, s._cfg_for(s.current_plugin),
                    manage_enabled=s.current_plugin.type != PluginType.WF_SHELL)
            except SaveCommittedError as error:
                committed_warning = error
            # Refresh enabled state
            enabled = s.config.get_enabled_plugins()
            plg = s.current_plugin
            plg.enabled = (plg.is_core_plugin or
                           plg.type == PluginType.WF_SHELL or
                           plg.name in enabled)
            for w in s.main_page._pw:
                if w.plugin is plg:
                    w.check.handler_block_by_func(w._on_t)
                    w.check.set_active(plg.enabled)
                    w.check.handler_unblock_by_func(w._on_t)
                    if hasattr(w, "_refresh_visual_state"):
                        w._refresh_visual_state()
                    break
            # Update sidebar toggle
            s.ec.handler_block_by_func(s._on_pe)
            s.ec.set_active(plg.enabled)
            s.ec.handler_unblock_by_func(s._on_pe)
            # Re-create the plugin page to reflect new values
            s.open_page(plg)
            if committed_warning is not None:
                _operation_error(s, _("Preset loaded; recovery needs attention"), committed_warning)
        except Exception as e:
            _preset_error(s, e)

    def _on_plugin_delete(s, btn):
        if not s.current_plugin:
            return
        name = s._plugin_combo.get_active_text()
        if not name:
            return
        try:
            s.preset_mgr.delete_plugin_preset(name, s.current_plugin.name)
            s._refresh_plugin_presets()
        except Exception as e:
            _preset_error(s, e)

    def _launch_wd(s, btn):
        try:
            subprocess.Popen(["wdisplays"])
        except FileNotFoundError:
            d = Gtk.AlertDialog()
            d.set_message(_("Cannot find program wdisplays."))
            d.show(s)

    def _on_key(s, ctrl, kv, kc, st):
        if kv == Gdk.KEY_q and st & Gdk.ModifierType.CONTROL_MASK:
            s.close()
            return True
        return False


class WCMApp(Gtk.Application):
    def __init__(s, config_path=None):
        super().__init__(
            application_id="org.wayfire.wcm", flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        s.window = None
        s.config_path = config_path

    def do_startup(s):
        Gtk.Application.do_startup(s)
        _apply_theme(_system_prefers_dark(True))

    def do_activate(s):
        if not s.window:
            s.window = WCM(s, s.config_path)
        s.window.present()


def main():
    import argparse

    pa = argparse.ArgumentParser(description=_("Wayfire Config Manager"))
    pa.add_argument("-c", "--config", help=_("Wayfire config file"))
    pa.add_argument("-p", "--plugin", help=_("Plugin to open"))
    pa.add_argument("-v", "--version", action="version",
                    version=f"wcm {__version__}")
    args = pa.parse_args()
    app = WCMApp(args.config)
    if args.plugin:

        def oap(a):
            if app.window:
                for p in app.window.plugins:
                    if p.name == args.plugin:
                        app.window.open_page(p)
                        break

        app.connect("activate", oap)
    sys.exit(app.run(sys.argv[:1]))


if __name__ == "__main__":
    main()
