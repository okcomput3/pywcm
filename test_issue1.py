"""Issue #1 regressions; run directly with a GTK display, or with pytest."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from lxml import etree
from config_backend import WayfireConfigFile
from metadata import CompoundEntry, Option, OptionType, Plugin, PluginType, _parse_option
from wcm import Gtk, PluginPage, option_tooltip, plugin_wiki_url


def test_command_heading_width_and_full_text():
    Gtk.init()
    with tempfile.TemporaryDirectory() as directory:
        cfg = WayfireConfigFile(str(Path(directory) / 'wayfire.ini'))
        command = 'echo ' + 'long-command-argument ' * 500
        cfg.set_option('command', 'command_test', command)
        cfg.save()
        original = Path(cfg.path).read_bytes()
        plugin = Plugin(name='command', option_groups=[Option(
            name='General', type=OptionType.GROUP, options=[Option(
                name='bindings', type=OptionType.DYNAMIC_LIST)])])
        page = PluginPage(plugin, cfg)
        overlay = page.get_nth_page(0)
        scroll = overlay.get_child()
        box = scroll.get_child().get_child()  # ScrolledWindow's viewport
        expander = box.get_first_child().get_first_child().get_child()
        heading = expander.get_label_widget()
        assert command in heading.get_text()
        assert command in heading.get_tooltip_text()
        assert heading.measure(Gtk.Orientation.HORIZONTAL, -1).natural < 1000
        assert not scroll.get_overlay_scrolling()
        assert box.get_margin_bottom() >= 84
        assert Path(cfg.path).read_bytes() == original
        expander.set_expanded(True)
        command_row = expander.get_child().get_last_child()
        entry = command_row.get_first_child().get_next_sibling()
        entry.set_text(command + ' updated')
        assert heading.get_tooltip_text().endswith(' updated')
        assert cfg.get_option('command', 'command_test') == command + ' updated'


def test_rules_have_one_editor_and_preserve_every_name():
    Gtk.init()
    with tempfile.TemporaryDirectory() as directory:
        cfg = WayfireConfigFile(str(Path(directory) / 'wayfire.ini'))
        for key in ('terminal', 'rule_0', 'custom_rule'):
            cfg.set_option('window-rules', key, 'on created then maximize')
        cfg.save()
        original = Path(cfg.path).read_bytes()
        plugin = Plugin(name='window-rules', option_groups=[Option(
            name='General', type=OptionType.GROUP, options=[Option(
                name='rules', type=OptionType.DYNAMIC_LIST,
                entries=[CompoundEntry(prefix='')])])])
        with patch.object(PluginPage, '_make_as_row', side_effect=AssertionError('Rules are not commands')):
            page = PluginPage(plugin, cfg)
        assert page.get_n_pages() == 1
        assert page._rules_done
        assert Path(cfg.path).read_bytes() == original


def test_wiki_routes_and_empty_pages():
    Gtk.init()
    for name in ('extra-animations', 'pin-view', 'background-view'):
        plugin = Plugin(name=name, disp_name='Translated display name')
        assert plugin_wiki_url(plugin).endswith('wayfire-plugins-extra/wiki/Configuration#' + name)
        page = PluginPage(plugin, WayfireConfigFile())
        assert page.get_n_pages() == 1
        box = page.get_nth_page(0).get_child().get_child()
        assert box.get_last_child().get_uri() == plugin_wiki_url(plugin)
    assert plugin_wiki_url(Plugin(name='blur')).endswith('wayfire/wiki/Configuration#blur')
    assert plugin_wiki_url(Plugin(type=PluginType.WF_SHELL)).endswith('/wf-shell')


def test_criteria_help_preserves_description_and_free_text():
    option = _parse_option(etree.fromstring(b'''<option name="blur_by_default" type="string">
        <_long>Criteria for which apps to be blurred</_long>
        <default>type is "toplevel"</default></option>'''), 'blur')
    tip = option_tooltip(option)
    assert tip.startswith(option.tooltip)
    assert 'all' in tip and 'none' in tip and 'type is "toplevel"' in tip
    assert option.type == OptionType.STRING and not option.str_labels
    ordinary = Option(tooltip='A command to run', type=OptionType.STRING)
    assert option_tooltip(ordinary) == ordinary.tooltip


if __name__ == '__main__':
    for name, test in list(globals().items()):
        if name.startswith('test_'):
            test()
            print('PASS:', name)
