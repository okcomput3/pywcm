#!/usr/bin/env python3
"""
Wayfire Config Manager (WCM) — Python/GTK4 — LUXE THEME with Light/Dark toggle
"""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
import sys, os, subprocess, glob, shutil, traceback
from gi.repository import Gtk, Gdk, GLib, Gio, GdkPixbuf, Pango
from config_backend import WayfireConfigFile, PresetManager
from metadata import (
    load_all_metadata,
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
            "rgba(14,17,32,0.88)",
            "rgba(18,22,40,0.72)",
            "rgba(12,15,30,0.78)",
            "rgba(16,20,38,0.90)",
        )
        amber, amber_l, rose, teal = "#e0982a", "#f0b84d", "#d25d77", "#38beb3"
        txt1, txt2 = "rgba(228,224,218,0.95)", "rgba(180,175,168,0.78)"
        bdr_s, bdr_a = "rgba(224,152,42,0.10)", "rgba(224,152,42,0.50)"
        ab, ar, at = "224,152,42", "210,93,119", "56,190,179"
        panel_bg = "rgba(12,14,26,0.92)"
        popup_bg = "rgba(12,15,28,0.96)"
        dlg_bg = "#0e1120"
        dlg_hdr = "rgba(14,17,32,0.98)"
        left_bdr = "rgba(224,152,42,0.06)"
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
@keyframes plugin-entrance {{ 0% {{ opacity: 0; }} 100% {{ opacity: 1; }} }}
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
searchentry {{ background-color: @bg_input; border: 1px solid rgba({ab},0.10); border-radius: 14px; padding: 11px 18px; color: @text_primary; font-size: 1.05em; transition: all 400ms cubic-bezier(0.22,1,0.36,1); }}
searchentry:focus {{ border-color: @amber; box-shadow: 0 0 24px rgba({ab},0.16); }}
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
}}
.category-header {{ padding: 10px 12px; margin-top: 8px; margin-start: 10px; }}
.category-header label {{ color: @amber; font-weight: 700; letter-spacing: 0.8px; }}
.category-header image {{ opacity: 0.75; }}
.category-slide {{ animation: category-slide-in 500ms cubic-bezier(0.22,1,0.36,1) backwards; }}
.category-slide-out {{ animation: category-slide-out 400ms cubic-bezier(0.22,1,0.36,1) forwards; }}

.plugin-row {{ padding: 5px 8px; border-radius: 10px; transition: all 320ms cubic-bezier(0.22,1,0.36,1); background-color: transparent; background-image: none; }}
.plugin-row:hover {{ background-color: transparent; background-image: none; }}
.plugin-row button.flat {{ transition: all 320ms cubic-bezier(0.22,1,0.36,1); background-image: none; }}
.plugin-row button.flat:hover {{ background-color: transparent; background-image: none; border-color: transparent; box-shadow: none; text-shadow: 0 0 10px rgba({ab},0.35); }}
.plugin-row label {{ font-weight: 500; }}

.plugin-title {{ color: {'#ffffff' if dark else '#1a1510'}; font-weight: 700; }}
.plugin-desc {{ color: @text_secondary; font-weight: 400; }}
.option-row {{ padding: 7px 10px; border-radius: 10px; transition: all 280ms ease; }}
.option-row:hover {{ background-color: rgba({ab},0.03); }}
.option-label {{ color: @text_secondary; font-weight: 500; transition: all 280ms ease; }}
.option-row:hover .option-label {{ color: @text_primary; }}

.reset-btn {{ background-color: transparent; border: 1px solid rgba({ar},0.10); border-radius: 8px; color: @rose; padding: 4px 8px; min-width: 30px; min-height: 30px; transition: all 300ms ease; }}
.reset-btn:hover {{ background-color: rgba({ar},0.10); border-color: rgba({ar},0.40); }}
.grab-btn {{ background-color: rgba({at},0.05); border: 1px solid rgba({at},0.16); color: @teal; font-weight: 700; min-width: 38px; transition: all 300ms ease; }}
.grab-btn:hover {{ background-color: rgba({at},0.12); border-color: rgba({at},0.45); }}
.add-btn {{ background-color: rgba({at},0.05); border: 1px solid rgba({at},0.16); color: @success; transition: all 300ms ease; }}
.add-btn:hover {{ background-color: rgba({at},0.12); border-color: rgba({at},0.45); }}
.remove-btn {{ background-color: rgba({ar},0.03); border: 1px solid rgba({ar},0.10); color: @danger; min-width: 30px; transition: all 300ms ease; }}
.remove-btn:hover {{ background-color: rgba({ar},0.10); border-color: rgba({ar},0.40); }}
.run-btn {{ background-color: rgba({at},0.03); border: 1px solid rgba({at},0.10); color: @success; transition: all 300ms ease; }}
.run-btn:hover {{ background-color: rgba({at},0.10); border-color: rgba({at},0.35); }}
.action-btn {{ padding: 11px 22px; border-radius: 12px; font-weight: 600; letter-spacing: 0.4px; }}
.action-btn.close-btn {{ background-color: rgba({ar},0.04); border-color: rgba({ar},0.12); color: @rose; }}
.action-btn.close-btn:hover {{ background-color: rgba({ar},0.10); border-color: rgba({ar},0.40); color: @danger; }}
.action-btn.back-btn {{ background-color: rgba({at},0.04); border-color: rgba({at},0.12); color: @teal; }}
.action-btn.back-btn:hover {{ background-color: rgba({at},0.10); border-color: rgba({at},0.40); color: @teal; }}
.grab-dialog {{ background-color: {popup_bg}; }}
.grab-dialog label {{ color: @amber; font-weight: 500; font-size: 1.1em; }}
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
"""


_css_provider = None


def _apply_theme(dark=True):
    global _css_provider
    display = Gdk.Display.get_default()
    if _css_provider:
        Gtk.StyleContext.remove_provider_for_display(display, _css_provider)
    _css_provider = Gtk.CssProvider()
    _css_provider.load_from_data(_make_css(dark).encode("utf-8"))
    Gtk.StyleContext.add_provider_for_display(
        display, _css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 100
    )


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


class KeyGrabWindow(Gtk.Window):
    def __init__(s, parent):
        super().__init__(
            title="Waiting for Binding",
            modal=True,
            transient_for=parent.get_root(),
            default_width=420,
            default_height=130,
        )
        s.result = ""
        s._mods = set()
        s._done = False
        s.add_css_class("grab-dialog")
        s._label = Gtk.Label(label="Press a key combination\u2026\n(Escape to cancel)")
        s._label.set_halign(Gtk.Align.CENTER)
        s._label.set_valign(Gtk.Align.CENTER)
        s.set_child(s._label)
        kc = Gtk.EventControllerKey()
        kc.connect("key-pressed", s._on_kp)
        kc.connect("key-released", s._on_kr)
        s.add_controller(kc)
        cl = Gtk.GestureClick()
        cl.set_button(0)
        cl.connect("pressed", s._on_cl)
        s.add_controller(cl)

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
            s._label.set_text(s._ms() or "(No modifiers)")
            return True
        kn = _keyval_to_linux(kv)
        if kn:
            s.result = (s._ms() + " " + kn).strip()
            s._done = True
            s.close()
        return True

    def _on_kr(s, ctrl, kv, kc, st):
        s._mods.discard(kv)
        s._label.set_text(s._ms() or "Press a key combination\u2026")

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
    for i, (n, _) in enumerate(CATEGORIES):
        if n == cat:
            return i
    return len(CATEGORIES) - 1


def get_config_path():
    ov = os.environ.get("WAYFIRE_CONFIG_FILE")
    if ov:
        return os.path.expanduser(ov)
    ch = os.environ.get("XDG_CONFIG_HOME", "") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    p = os.path.join(ch, "wayfire", "wayfire.ini")
    return p if os.path.isfile(p) else os.path.join(ch, "wayfire.ini")


def get_wfshell_config_path():
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
    wf_path = get_config_path()
    return os.path.join(os.path.dirname(wf_path), "wf-shell.ini")


LABEL_W = 200


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
    def __init__(s, opt, cfg, plg):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        s.option = opt
        s.config = cfg
        s.plugin = plg
        s._block = False
        s.add_css_class("option-row")
        s.set_margin_start(4)
        s.set_margin_end(4)
        s.set_margin_top(2)
        s.set_margin_bottom(2)
        s.lbl = Gtk.Label(label=opt.disp_name or opt.name)
        s.lbl.set_tooltip_text(opt.tooltip or "")
        s.lbl.set_size_request(LABEL_W, -1)
        s.lbl.set_xalign(0)
        s.lbl.set_hexpand(False)
        s.lbl.set_halign(Gtk.Align.START)
        s.lbl.add_css_class("option-label")
        s.append(s.lbl)
        s.end_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        s.end_box.set_hexpand(True)
        s.end_box.set_halign(Gtk.Align.FILL)
        s.append(s.end_box)
        cur = cfg.get_option(plg.name, opt.name)
        s._build(opt, cur)
        if opt.type in (OptionType.BOOL, OptionType.COLOR, OptionType.DOUBLE) or (
            opt.type == OptionType.INT and not opt.int_labels
        ):
            s.end_box.set_hexpand(True)
            s.end_box.set_halign(Gtk.Align.END)
        rb = Gtk.Button.new_from_icon_name("edit-clear")
        rb.set_tooltip_text("Reset to default")
        rb.add_css_class("reset-btn")
        rb.connect("clicked", s._reset)
        s.end_box.append(rb)
        s.reset_btn = rb

    def _build(s, opt, cur):
        ot = opt.type
        if ot == OptionType.INT:
            if opt.int_labels:
                s.ed = Gtk.ComboBoxText()
                for lb, v in opt.int_labels:
                    s.ed.append(str(v), lb)
                s.ed.set_active_id(str(_int(cur, opt.default_value)))
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
            dec = (
                len(str(opt.precision).split(".")[-1])
                if "." in str(opt.precision)
                else 3
            )
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
                s.ed.set_active_id(
                    cur if cur is not None else str(opt.default_value or "")
                )
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

    def _save(s, v):
        if s._block:
            return
        s.config.set_option(s.plugin.name, s.option.name, str(v))
        s.config.save()

    def _on_text_changed(s, widget):
        """Called on every keystroke — mirrors C++ WCM live-save behaviour."""
        if not s._block:
            s.config.set_option(s.plugin.name, s.option.name,
                                str(widget.get_text()))
            s.config.save()

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
            title="Select Directory",
            transient_for=s.get_root(),
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        s._file_dlg.connect("response", s._on_file_response)
        s._file_dlg.show()

    def _choose_file(s, btn):
        s._file_dlg = Gtk.FileChooserNative(
            title="Select File",
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
        s._save(str(d or ""))


class SubgroupWidget(Gtk.Frame):
    def __init__(s, sg, cfg, plg):
        super().__init__()
        s.add_css_class("subgroup-frame")
        exp = Gtk.Expander(label=sg.name or "Options")
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
        s.connect("switch-page", s._on_ts)
        s._lt = 0
        s._br = False
        for g in plg.option_groups:
            if g.type != OptionType.GROUP or g.hidden:
                continue
            sc = Gtk.ScrolledWindow()
            sc.set_vexpand(True)
            bx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            bx.set_margin_start(10)
            bx.set_margin_end(10)
            bx.set_margin_top(10)
            bx.set_margin_bottom(10)
            for o in g.options:
                if o.hidden:
                    continue
                try:
                    if o.type == OptionType.SUBGROUP and o.options:
                        bx.append(SubgroupWidget(o, cfg, plg))
                    elif o.type == OptionType.DYNAMIC_LIST:
                        w = s._make_dynlist(o, cfg, plg)
                        if w:
                            bx.append(w)
                    elif o.type != OptionType.GROUP:
                        bx.append(OptionWidget(o, cfg, plg))
                except Exception as e:
                    bx.append(Gtk.Label(label=f"\u26a0 {o.name}: {e}"))
                    traceback.print_exc()
            sc.set_child(bx)
            s.append_page(sc, Gtk.Label(label=g.name or "General"))

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
        ab = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        btn = Gtk.Button.new_from_icon_name("list-add")
        btn.add_css_class("add-btn")
        btn.set_halign(Gtk.Align.END)
        btn.connect("clicked", lambda w: s._add_as(cfg, plg, bx))
        ab.append(btn)
        ab.set_halign(Gtk.Align.END)
        bx.append(ab)
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
        c = bx.get_first_child()
        last = None
        while c:
            last = c
            c = c.get_next_sibling()
        if last:
            bx.insert_child_after(r, None)
            bx.reorder_child_after(
                r, last.get_prev_sibling() if last.get_prev_sibling() else None
            )
        else:
            bx.append(r)

    def _make_bindings(s, opt, cfg, plg, so):
        bx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        cn = []
        for k in so:
            if k.startswith("command_"):
                n = k[8:]
                if n and n not in cn:
                    cn.append(n)
        for c in sorted(cn):
            bx.append(s._make_bw(c, cfg, plg, so, bx))
        ab = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        ab.set_hexpand(True)
        btn = Gtk.Button.new_from_icon_name("list-add")
        btn.add_css_class("add-btn")
        btn.set_halign(Gtk.Align.END)
        btn.connect("clicked", lambda w: s._add_bind(cfg, plg, bx))
        ab.append(btn)
        ab.set_halign(Gtk.Align.END)
        ab.set_margin_top(6)
        bx.append(ab)
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
        if av is not None:
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
        exp = Gtk.Expander(label=f"Command {cn}: {cv}")
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
        tl = Gtk.Label(label="Type")
        tl.set_size_request(LABEL_W, -1)
        tl.set_xalign(0)
        tl.add_css_class("option-label")
        tr.append(tl)
        tc = Gtk.ComboBoxText()
        tc.append_text("Regular")
        tc.append_text("Repeat")
        tc.append_text("Always")
        tc.set_active(bt)
        tc.set_hexpand(True)
        tc.connect("changed", lambda w, c=cn: s._chg_bt(cfg, plg, c, w.get_active()))
        tr.append(tc)
        vb.append(tr)
        br = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bl = Gtk.Label(label="Binding")
        bl.set_size_request(LABEL_W, -1)
        bl.set_xalign(0)
        bl.add_css_class("option-label")
        br.append(bl)
        be = Gtk.Entry()
        be.set_text(bv)
        be.set_hexpand(True)
        be.connect("changed", lambda w, b=bk: s._so(cfg, plg, b, w.get_text()))
        br.append(be)
        gb = Gtk.Button.new_from_icon_name("input-keyboard")
        gb.add_css_class("grab-btn")
        gb.connect("clicked", lambda w, e=be, b=bk: s._grab_for(e, cfg, plg, b))
        br.append(gb)
        vb.append(br)
        cr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        cl = Gtk.Label(label="Command")
        cl.set_size_request(LABEL_W, -1)
        cl.set_xalign(0)
        cl.add_css_class("option-label")
        cr.append(cl)
        ce = Gtk.Entry()
        ce.set_text(cv)
        ce.set_hexpand(True)
        ce.connect(
            "changed",
            lambda w, e=exp, c=cn: e.set_label(f"Command {c}: {w.get_text()}"),
        )
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
        rk, pk, ak = f"binding_{cn}", f"repeatable_binding_{cn}", f"always_binding_{cn}"
        so = cfg.get_section_options(plg.name)
        bv = so.get(ak) or so.get(pk) or so.get(rk) or "none"
        for k in (rk, pk, ak):
            if k in so:
                cfg.remove_option(plg.name, k)
        cfg.set_option(plg.name, [rk, pk, ak][nt], bv)
        cfg.save()

    def _rm_bind(s, cfg, plg, cn, fr, pb):
        for px in ("command_", "binding_", "repeatable_binding_", "always_binding_"):
            cfg.remove_option(plg.name, px + cn)
        cfg.save()
        pb.remove(fr)

    def _add_bind(s, cfg, plg, bx):
        so = cfg.get_section_options(plg.name)
        i = 0
        while f"command_new{i}" in so:
            i += 1
        n = f"new{i}"
        cfg.set_option(plg.name, f"command_{n}", "")
        cfg.set_option(plg.name, f"binding_{n}", "none")
        cfg.save()
        so = cfg.get_section_options(plg.name)
        w = s._make_bw(n, cfg, plg, so, bx)
        c = bx.get_first_child()
        last = None
        while c:
            last = c
            c = c.get_next_sibling()
        if last:
            bx.insert_child_after(
                w, last.get_prev_sibling() if last.get_prev_sibling() else None
            )
        else:
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
            title="Choose Executable",
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
    def __init__(s, plg, wcm):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        s.plugin = plg
        s.wcm = wcm
        s.set_halign(Gtk.Align.START)
        s.add_css_class("plugin-row")
        s.check = Gtk.CheckButton()
        s.check.set_active(plg.enabled)
        if plg.is_core_plugin or plg.type == PluginType.WF_SHELL:
            s.check.set_sensitive(False)
        else:
            s.check.connect("toggled", s._on_t)
        s.append(s.check)
        btn = Gtk.Button()
        btn.add_css_class("flat")
        btn.set_tooltip_text(plg.tooltip or "")
        btn.connect("clicked", lambda w: wcm.open_page(plg))
        bb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        bb.set_halign(Gtk.Align.START)
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
        l = Gtk.Label(label=plg.disp_name or plg.name)
        l.set_ellipsize(Pango.EllipsizeMode.END)
        bb.append(l)
        btn.set_child(bb)
        s.append(btn)

    def _on_t(s, c):
        s.wcm.set_plugin_enabled(s.plugin, c.get_active())


class MainPage(Gtk.ScrolledWindow):
    def __init__(s, plugins, wcm):
        super().__init__()
        s.set_vexpand(True)
        s.set_hexpand(True)
        s._ft = ""
        s._pw = []
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vb.set_margin_top(10)
        vb.set_margin_bottom(10)
        s.sg = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.BOTH)
        s.cd = {}
        for i, (cn, ic) in enumerate(CATEGORIES):
            tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            tb.add_css_class("category-header")
            img = Gtk.Image.new_from_icon_name(ic)
            img.set_pixel_size(24)
            tb.append(img)
            l = Gtk.Label()
            l.set_markup(f"<span size='14000'><b>{cn}</b></span>")
            tb.append(l)
            vb.append(tb)
            fb = Gtk.FlowBox()
            fb.set_selection_mode(Gtk.SelectionMode.NONE)
            fb.set_halign(Gtk.Align.START)
            fb.set_min_children_per_line(3)
            fb.set_max_children_per_line(10)
            fb.set_margin_start(20)
            fb.set_filter_func(s._ff)
            vb.append(fb)
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            if i < len(CATEGORIES) - 1:
                vb.append(sep)
            s.cd[cn] = (tb, fb, sep)
        for p in plugins:
            ci = get_category_index(p.category)
            cn = CATEGORIES[ci][0]
            _, fb, _ = s.cd[cn]
            w = PluginButtonWidget(p, wcm)
            s.sg.add_widget(w)
            fb.append(w)
            s._pw.append(w)
        s.set_child(vb)

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
        for cn in CATEGORY_NAMES:
            _, fb, _ = s.cd[cn]
            child = fb.get_first_child()
            while child:
                child.add_css_class("filter-hidden")
                child = child.get_next_sibling()
        for cn in CATEGORY_NAMES:
            _, fb, _ = s.cd[cn]
            fb.invalidate_filter()
        GLib.idle_add(s._reveal)

    def _reveal(s):
        delay = 0
        for cn in CATEGORY_NAMES:
            title, fb, sep = s.cd[cn]
            vis = False
            child = fb.get_first_child()
            while child:
                w = child.get_child()
                if w and hasattr(w, "plugin"):
                    p = w.plugin
                    if (
                        not s._ft
                        or s._ft in p.name.lower()
                        or s._ft in p.disp_name.lower()
                        or s._ft in p.tooltip.lower()
                    ):
                        vis = True
                        d = delay
                        GLib.timeout_add(
                            d,
                            lambda c=child: (
                                c.remove_css_class("filter-hidden") or False
                            ),
                        )
                        delay += 50
                child = child.get_next_sibling()
            was_visible = title.get_visible()
            if vis and not was_visible:
                title.set_visible(True)
                fb.set_visible(True)
                sep.set_visible(True)
                title.remove_css_class("category-slide-out")
                title.remove_css_class("category-slide")
                GLib.timeout_add(
                    10, lambda t=title: (t.add_css_class("category-slide") or False)
                )
            elif vis and was_visible:
                title.remove_css_class("category-slide")
                GLib.timeout_add(
                    10, lambda t=title: (t.add_css_class("category-slide") or False)
                )
            elif not vis and was_visible:
                title.remove_css_class("category-slide")
                title.add_css_class("category-slide-out")
                GLib.timeout_add(
                    420,
                    lambda t=title, f=fb, sp=sep: (
                        t.set_visible(False)
                        or f.set_visible(False)
                        or sp.set_visible(False)
                        or t.remove_css_class("category-slide-out")
                        or False
                    ),
                )
        return False


class WCM(Gtk.ApplicationWindow):
    def __init__(s, app):
        super().__init__(application=app, title="Wayfire Config Manager")
        s.set_default_size(1000, 580)
        s.set_size_request(750, 550)
        ip = find_app_icon()
        if ip:
            try:
                GdkPixbuf.Pixbuf.new_from_file(ip)
                s.set_icon_name("wcm")
            except:
                pass
        s.config = WayfireConfigFile(get_config_path())
        s.wf_shell_config = WayfireConfigFile(get_wfshell_config_path())
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
        s._dark = True
        s._build_ui()
        kc = Gtk.EventControllerKey()
        kc.connect("key-pressed", s._on_key)
        s.add_controller(kc)

    def _gen_from_config(s):
        for sec in s.config.get_sections():
            p = Plugin()
            p.name = sec
            p.disp_name = sec.replace("-", " ").replace("_", " ").title()
            p.category = "Other"
            p.type = PluginType.WAYFIRE
            p.tooltip = f"Configuration for {sec}"
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

    def _build_ui(s):
        gb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        s.left_stack = Gtk.Stack()
        s.left_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        s.left_stack.set_transition_duration(450)
        s.left_stack.add_css_class("left-panel")
        s.left_stack.set_vexpand(True)
        s.left_stack.set_size_request(260, -1)
        s.left_stack.set_hexpand(False)
        s.left_stack.set_halign(Gtk.Align.START)
        ml = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        fl = Gtk.Label()
        fl.set_markup("<span size='large'><b>Filter</b></span>")
        fl.set_margin_top(14)
        fl.set_margin_start(14)
        fl.add_css_class("filter-label")
        ml.append(fl)
        s.search_entry = Gtk.SearchEntry()
        s.search_entry.set_margin_start(14)
        s.search_entry.set_margin_end(14)
        s.search_entry.set_margin_top(8)
        s.search_entry.connect("search-changed", s._on_search)
        ml.append(s.search_entry)

        # --- Master presets section ---
        ps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        ps.add_css_class("preset-section")
        ph = Gtk.Label(label="PRESETS")
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
        lb = Gtk.Button(label="Load")
        lb.add_css_class("preset-load")
        lb.connect("clicked", s._on_master_load)
        pb.append(lb)
        sb = Gtk.Button(label="Save")
        sb.add_css_class("preset-save")
        sb.connect("clicked", s._on_master_save)
        pb.append(sb)
        db = Gtk.Button(label="Delete")
        db.add_css_class("preset-delete")
        db.connect("clicked", s._on_master_delete)
        pb.append(db)
        ps.append(pb)
        ml.append(ps)

        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        ml.append(spacer)
        theme_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        theme_box.set_halign(Gtk.Align.CENTER)
        theme_box.set_margin_bottom(10)
        theme_box.add_css_class("theme-switch-box")
        dark_icon = Gtk.Label(label="\u263e")
        dark_icon.set_tooltip_text("Dark")
        theme_box.append(dark_icon)
        s._theme_switch = Gtk.Switch()
        s._theme_switch.set_active(False)
        s._theme_switch.set_valign(Gtk.Align.CENTER)
        s._theme_switch.connect("notify::active", s._on_theme_toggle)
        theme_box.append(s._theme_switch)
        light_icon = Gtk.Label(label="\u2600")
        light_icon.set_tooltip_text("Light")
        theme_box.append(light_icon)
        ml.append(theme_box)
        ob = s._make_button("Configure Outputs", "video-display")
        ob.add_css_class("action-btn")
        ob.set_margin_start(14)
        ob.set_margin_end(14)
        ob.set_margin_bottom(8)
        ob.connect("clicked", s._launch_wd)
        ml.append(ob)
        cb = s._make_button("Close", "window-close")
        cb.add_css_class("action-btn")
        cb.add_css_class("close-btn")
        cb.set_margin_start(14)
        cb.set_margin_end(14)
        cb.set_margin_bottom(14)
        cb.connect("clicked", lambda w: s.close())
        ml.append(cb)
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
        s.el = Gtk.Label(label="Use This Plugin")
        s.eb.append(s.el)
        s.ec.connect("toggled", s._on_pe)
        pl.append(s.eb)

        # --- Plugin presets section ---
        pps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        pps.add_css_class("preset-section")
        pps.set_margin_top(12)
        pph = Gtk.Label(label="PLUGIN PRESETS")
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
        plb = Gtk.Button(label="Load")
        plb.add_css_class("preset-load")
        plb.connect("clicked", s._on_plugin_load)
        ppb.append(plb)
        psb = Gtk.Button(label="Save")
        psb.add_css_class("preset-save")
        psb.connect("clicked", s._on_plugin_save)
        ppb.append(psb)
        pdb = Gtk.Button(label="Delete")
        pdb.add_css_class("preset-delete")
        pdb.connect("clicked", s._on_plugin_delete)
        ppb.append(pdb)
        pps.append(ppb)
        pl.append(pps)

        sp2 = Gtk.Box()
        sp2.set_vexpand(True)
        pl.append(sp2)
        bb = s._make_button("Back", "go-previous")
        bb.add_css_class("action-btn")
        bb.add_css_class("back-btn")
        bb.set_margin_start(14)
        bb.set_margin_end(14)
        bb.set_margin_bottom(14)
        bb.connect("clicked", lambda w: s.open_page(None))
        pl.append(bb)
        s.left_stack.add_named(pl, "plugin")
        gb.append(s.left_stack)
        s.main_stack = Gtk.Stack()
        s.main_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        s.main_stack.set_transition_duration(500)
        s.main_stack.set_hexpand(True)
        s.main_stack.set_vexpand(True)
        s.main_page = MainPage(s.plugins, s)
        s.main_stack.add_named(s.main_page, "main")
        gb.append(s.main_stack)
        s.set_child(gb)
        s.plugin_page = None

    def _make_button(s, text, icon):
        btn = Gtk.Button()
        bx = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        bx.set_halign(Gtk.Align.CENTER)
        bx.append(Gtk.Image.new_from_icon_name(icon))
        bx.append(Gtk.Label(label=text))
        btn.set_child(bx)
        return btn

    def _cfg_for(s, plg):
        """Return the correct config file for a plugin.

        wf-shell plugins (background, panel, dock, etc.) read from
        wf-shell.ini, not wayfire.ini.  The C++ WCM handles this
        with separate wf::config instances; we mirror that here.
        """
        if plg.type == PluginType.WF_SHELL:
            return s.wf_shell_config
        return s.config

    def _on_theme_toggle(s, switch, pspec):
        s._dark = not switch.get_active()
        _apply_theme(s._dark)

    def _on_search(s, entry):
        s.main_page.set_filter(entry.get_text())

    def open_page(s, plg=None):
        if plg:
            s.current_plugin = plg
            s.eb.set_visible(not plg.is_core_plugin and plg.type != PluginType.WF_SHELL)
            s.ec.handler_block_by_func(s._on_pe)
            s.ec.set_active(plg.enabled)
            s.ec.handler_unblock_by_func(s._on_pe)
            s.pnl.set_markup(
                f"<span size='12000'><b>{plg.disp_name or plg.name}</b></span>"
            )
            s.pdl.set_markup(f"<span size='10000'><b>{plg.tooltip or ''}</b></span>")
            s._refresh_plugin_presets()
            if s.plugin_page:
                s.main_stack.remove(s.plugin_page)
            s.plugin_page = PluginPage(plg, s._cfg_for(plg))
            s.main_stack.add_named(s.plugin_page, "plugin")
            s.main_stack.set_visible_child_name("plugin")
            s.left_stack.set_visible_child_name("plugin")
        else:
            s.main_stack.set_visible_child_name("main")
            s.left_stack.set_visible_child_name("main")
            s.current_plugin = None

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
        lbl = Gtk.Label(label="Preset name:")
        lbl.set_xalign(0)
        vb.append(lbl)
        entry = Gtk.Entry()
        entry.set_hexpand(True)
        vb.append(entry)
        bb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bb.set_halign(Gtk.Align.END)
        ok_btn = Gtk.Button(label="Save")
        ok_btn.add_css_class("preset-save")
        cancel_btn = Gtk.Button(label="Cancel")

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
                # Save both wayfire and wf-shell options into one preset
                s.preset_mgr.save_master_preset(name, s.config)
                # Merge wf-shell options into the same preset file
                ws_opts = s.wf_shell_config.get_all_options()
                if ws_opts:
                    path = s.preset_mgr._master_path(
                        s.preset_mgr._sanitize(name))
                    preset = WayfireConfigFile(path)
                    for section, opts in ws_opts.items():
                        for key, value in opts.items():
                            preset.set_option(section, key, value)
                    preset.save()
                s._refresh_master_presets()
                # Select the one just saved
                model = s._master_combo.get_model()
                it = model.get_iter_first()
                i = 0
                while it:
                    if model.get_value(it, 0) == name:
                        s._master_combo.set_active(i)
                        break
                    it = model.iter_next(it)
                    i += 1
            except Exception as e:
                print(f"WCM: Failed to save master preset: {e}")
        s._prompt_name("Save Master Preset", do)

    def _on_master_load(s, btn):
        name = s._master_combo.get_active_text()
        if not name:
            return
        try:
            # Build set of wf-shell section names so we route correctly
            ws_sections = {p.name for p in s.plugins
                           if p.type == PluginType.WF_SHELL}

            path = s.preset_mgr._master_path(name)
            preset = WayfireConfigFile(path)
            for section in preset.get_sections():
                opts = preset.get_section_options(section)
                target = (s.wf_shell_config if section in ws_sections
                          else s.config)
                for key, value in opts.items():
                    target.set_option(section, key, value)
            s.config.save()
            s.wf_shell_config.save()

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
            # Refresh plugin page if open
            if s.current_plugin:
                s.open_page(s.current_plugin)
        except Exception as e:
            print(f"WCM: Failed to load master preset: {e}")

    def _on_master_delete(s, btn):
        name = s._master_combo.get_active_text()
        if not name:
            return
        s.preset_mgr.delete_master_preset(name)
        s._refresh_master_presets()

    # --- Plugin preset actions ---

    def _on_plugin_save(s, btn):
        if not s.current_plugin:
            return
        plg = s.current_plugin

        def do(name):
            try:
                s.preset_mgr.save_plugin_preset(name, plg.name, s._cfg_for(plg))
                s._refresh_plugin_presets()
                model = s._plugin_combo.get_model()
                it = model.get_iter_first()
                i = 0
                while it:
                    if model.get_value(it, 0) == name:
                        s._plugin_combo.set_active(i)
                        break
                    it = model.iter_next(it)
                    i += 1
            except Exception as e:
                print(f"WCM: Failed to save plugin preset: {e}")
        s._prompt_name(f"Save {plg.disp_name or plg.name} Preset", do)

    def _on_plugin_load(s, btn):
        if not s.current_plugin:
            return
        name = s._plugin_combo.get_active_text()
        if not name:
            return
        try:
            s.preset_mgr.load_plugin_preset(
                name, s.current_plugin.name, s._cfg_for(s.current_plugin))
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
                    break
            # Update sidebar toggle
            s.ec.handler_block_by_func(s._on_pe)
            s.ec.set_active(plg.enabled)
            s.ec.handler_unblock_by_func(s._on_pe)
            # Re-create the plugin page to reflect new values
            s.open_page(plg)
        except Exception as e:
            print(f"WCM: Failed to load plugin preset: {e}")

    def _on_plugin_delete(s, btn):
        if not s.current_plugin:
            return
        name = s._plugin_combo.get_active_text()
        if not name:
            return
        s.preset_mgr.delete_plugin_preset(name, s.current_plugin.name)
        s._refresh_plugin_presets()

    def _launch_wd(s, btn):
        try:
            subprocess.Popen(["wdisplays"])
        except FileNotFoundError:
            d = Gtk.AlertDialog()
            d.set_message("Cannot find program wdisplays.")
            d.show(s)

    def _on_key(s, ctrl, kv, kc, st):
        if kv == Gdk.KEY_q and st & Gdk.ModifierType.CONTROL_MASK:
            s.close()
            return True
        return False


class WCMApp(Gtk.Application):
    def __init__(s):
        super().__init__(
            application_id="org.wayfire.wcm", flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        s.window = None

    def do_startup(s):
        Gtk.Application.do_startup(s)
        _apply_theme(True)

    def do_activate(s):
        if not s.window:
            s.window = WCM(s)
        s.window.present()


def main():
    import argparse

    pa = argparse.ArgumentParser(description="Wayfire Config Manager")
    pa.add_argument("-c", "--config", help="Wayfire config file")
    pa.add_argument("-p", "--plugin", help="Plugin to open")
    args = pa.parse_args()
    if args.config:
        os.environ["WAYFIRE_CONFIG_FILE"] = args.config
    app = WCMApp()
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