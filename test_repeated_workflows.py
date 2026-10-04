"""Repeated normal-use workflows with temporary configs and GTK controls."""
import time
from unittest.mock import patch
from config_backend import WayfireConfigFile, OutputManager
from metadata import Option, OptionType, Plugin
from test_followup import fixture
from test_release_safety import display
from wcm import Gtk, GLib, WCM, DisplayPage, OptionWidget


def wait_for_prompt(page):
    end = time.monotonic() + 2
    while page._active_confirm is None and time.monotonic() < end:
        GLib.MainContext.default().iteration(False)
        time.sleep(.005)
    assert page._active_confirm is not None


def test_repeated_master_switches_with_display_and_pending_typing(tmp_path):
    Gtk.init()
    window = fixture(tmp_path)
    for name, mode in [('small', '1280x720'), ('large', '1920x1080')]:
        window.config.set_option('output:DP-1', 'mode', mode)
        window.config.set_option('demo', 'text', name)
        window.config.save()
        window.preset_mgr.save_master_preset_file(name, window.config.path, window.wf_shell_config.path)
    with patch.object(OutputManager, 'detect', return_value=[dict(name='DP-1', enabled=True, modes=[])]):
        window.display_page = DisplayPage(window)
        for i in range(20):
            name, expected = [('small', '1280x720'), ('large', '1920x1080')][i % 2]
            old = window.config
            editor = OptionWidget(Option(name='text', type=OptionType.STRING, default_value=''), old, Plugin(name='demo'))
            editor.ed.set_text('obsolete typing')
            window._master_combo.get_active_text.return_value = name
            WCM._on_master_load(window, None)
            assert not old._pending_edits
            card = window.display_page._root.get_first_child()
            resolution = card.get_child().get_first_child().get_next_sibling().get_last_child()
            assert resolution.get_child().get_text() == expected
            resolution.get_child().set_text('1600x900')
            window.display_page.revert_pending_changes()
            assert WayfireConfigFile(window.config.path).get_option('output:DP-1', 'mode') == expected
            assert WayfireConfigFile(window.config.path).get_option('demo', 'text') == name


def test_repeated_plugin_switches_preserve_unrelated_settings(tmp_path):
    window = fixture(tmp_path); cfg = window.config
    for name in ('first', 'second'):
        cfg.set_option('demo', 'text', name); cfg.save()
        window.preset_mgr.save_plugin_preset(name, 'demo', cfg)
    cfg.set_option('demo', 'extra', 'retain me')
    cfg.set_option('other', 'value', 'untouched'); cfg.save()
    for i in range(50):
        name = ('first', 'second')[i % 2]
        window.preset_mgr.load_plugin_preset(name, 'demo', cfg)
        saved = WayfireConfigFile(cfg.path)
        assert saved.get_option('demo', 'text') == name
        assert saved.get_option('demo', 'extra') == 'retain me'
        assert saved.get_option('other', 'value') == 'untouched'


def test_keep_automatic_then_numeric_revert(tmp_path):
    Gtk.init()
    cfg = fixture(tmp_path).config
    page, cards, resolutions = display(cfg)
    resolution = resolutions[0]
    try:
        DisplayPage.revert_pending_changes(page)
        resolution.set_active_id('default')
        wait_for_prompt(page); page._active_confirm._finish('keep')
        assert cfg.get_option('output:DP-1', 'mode') == 'default'
        assert resolution.get_active_id() == 'default'
        resolution.get_child().set_text('1600x900')
        DisplayPage.revert_pending_changes(page)
        assert cfg.get_option('output:DP-1', 'mode') == 'default'
        assert resolution.get_active_id() == 'default'
    finally:
        DisplayPage.revert_pending_changes(page)


def test_repeated_scale_edits_survive_mode_revert(tmp_path):
    Gtk.init()
    cfg = fixture(tmp_path).config
    page, cards, resolutions = display(cfg)
    rows = []
    child = cards[0].get_child().get_first_child()
    while child:
        rows.append(child); child = child.get_next_sibling()
    scale = rows[3].get_last_child()
    try:
        for i in range(20):
            value = 1 + (i % 4) * .25
            scale.set_value(value)
            resolutions[0].get_child().set_text('1600x900')
            DisplayPage.revert_pending_changes(page)
            saved = WayfireConfigFile(cfg.path)
            assert float(saved.get_option('output:DP-1', 'scale', '1')) == value
            assert saved.get_option('output:DP-1', 'mode') == '1920x1080'
    finally:
        DisplayPage.revert_pending_changes(page)
