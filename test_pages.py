"""Page behavior checks without opening a GTK window or changing user config."""
from types import SimpleNamespace
from unittest.mock import Mock, patch
import tempfile
from pathlib import Path

from config_backend import WayfireConfigFile
from metadata import CompoundEntry, Option, Plugin
from wcm import PluginPage, DisplayPage


def test_empty_prefix_rules_use_rule_editor():
    page = SimpleNamespace(_make_winrules=Mock(return_value='rules'),
                           _make_autostart=Mock())
    option = Option(name='rules', entries=[CompoundEntry(prefix='')])
    cfg = WayfireConfigFile()
    plugin = Plugin(name='window-rules')
    assert PluginPage._make_dynlist(page, option, cfg, plugin) == 'rules'
    page._make_autostart.assert_not_called()
    page._make_winrules_box = Mock()
    PluginPage._make_winrules(page, option, cfg, plugin, {})
    assert page._make_winrules_box.call_args.args[-1] == ''


def test_rules_keep_arbitrary_names_and_avoid_collisions():
    with tempfile.TemporaryDirectory() as directory:
        cfg = WayfireConfigFile(str(Path(directory) / 'wayfire.ini'))
        cfg.set_option('window-rules', 'maximize_terminal', 'on created then maximize')
        cfg.set_option('window-rules', 'rule_0', 'on created then minimize')
        plugin = Plugin(name='window-rules')
        page = SimpleNamespace(_make_wr_row=Mock(), _add_wr=Mock())
        with patch('wcm.Gtk.Box') as box:
            PluginPage._make_winrules_box(page, cfg, plugin,
                                         cfg.get_section_options(plugin.name), '')
            assert page._make_wr_row.call_count == 2
            page._pending_add()
            assert page._add_wr.call_args.args[-1] == 'rule_'
            PluginPage._add_wr(page, cfg, plugin, box.return_value, 'rule_')
        saved = WayfireConfigFile(cfg.path).get_section_options(plugin.name)
        assert set(saved) == {'maximize_terminal', 'rule_0', 'rule_1'}


def test_hotplug_preserves_confirmation_and_coalesces_events():
    page = SimpleNamespace(_hotplug_source=0, _refresh_outputs=Mock(), _pending_reverts={})
    with patch('wcm.GLib.timeout_add', return_value=123) as timer:
        DisplayPage._outputs_changed(page)
        DisplayPage._outputs_changed(page)
        timer.assert_called_once()
    page._active_confirm = object()
    page._confirm_sources = set()
    page.reload = Mock()
    assert DisplayPage._refresh_outputs(page) is True
    page.reload.assert_not_called()
    page._active_confirm = None
    page._confirm_sources = {45}
    assert DisplayPage._refresh_outputs(page) is True
    page._confirm_sources.clear()
    assert DisplayPage._refresh_outputs(page) is False
    page.reload.assert_called_once()
    assert page._hotplug_source == 0


def test_hotplug_keeps_disconnected_config():
    cfg = WayfireConfigFile()
    cfg.set_option('output:HDMI-A-1', 'mode', '1920x1080@60000')
    root = Mock()
    root.get_first_child.return_value = None
    page = SimpleNamespace(_active_confirm=None, _confirm_sources=set(), _pending_reverts={},
                           _root=root, app=SimpleNamespace(config=cfg),
                           _om=Mock(), _window_output_name=lambda: None,
                           _build_card=Mock(), _build_add_row=Mock())
    page._om.detect.return_value = []
    DisplayPage.reload(page)
    assert page._build_card.call_args.kwargs == {'is_primary': False, 'is_connected': False}
    assert cfg.get_option('output:HDMI-A-1', 'mode') == '1920x1080@60000'
    page._om.detect.return_value = [{'name': 'HDMI-A-1', 'enabled': True}]
    DisplayPage.reload(page)
    assert page._build_card.call_args.kwargs == {'is_primary': True, 'is_connected': True}
    assert cfg.get_option('output:HDMI-A-1', 'mode') == '1920x1080@60000'
