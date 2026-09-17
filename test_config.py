#!/usr/bin/env python3
"""Tests for the WCM config backend — validates line-preserving behavior."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
from config_backend import WayfireConfigFile

SAMPLE_CONFIG = """\
# Wayfire config file
# This is a comment

[core]
# Core plugins
plugins = move resize alpha
vwidth = 3
vheight = 3

[move]
# Move plugin options
activate = <super> BTN_LEFT

[decoration]
active_color = 0.36 0.8 0.72 1.0
title_height = 30
"""


def test_read_and_preserve():
    """Config read preserves all lines exactly."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        path = f.name

    try:
        cfg = WayfireConfigFile(path)
        cfg.save(path + '.out')

        with open(path + '.out') as f:
            result = f.read()

        assert result == SAMPLE_CONFIG, \
            f"Round-trip failed!\n---EXPECTED---\n{SAMPLE_CONFIG}\n---GOT---\n{result}"
        print("PASS: read_and_preserve")
    finally:
        os.unlink(path)
        if os.path.exists(path + '.out'):
            os.unlink(path + '.out')


def test_get_option():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        path = f.name

    try:
        cfg = WayfireConfigFile(path)
        assert cfg.get_option('core', 'vwidth') == '3'
        assert cfg.get_option('move', 'activate') == '<super> BTN_LEFT'
        assert cfg.get_option('decoration', 'title_height') == '30'
        assert cfg.get_option('core', 'nonexistent') is None
        assert cfg.get_option('nonexistent', 'foo') is None
        print("PASS: get_option")
    finally:
        os.unlink(path)


def test_set_existing_option():
    """Setting an existing option only changes that one line."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        path = f.name

    try:
        cfg = WayfireConfigFile(path)
        cfg.set_option('core', 'vwidth', '5')
        cfg.save(path)

        with open(path) as f:
            lines = f.readlines()

        # Comments must be preserved
        assert lines[0] == '# Wayfire config file\n'
        assert lines[1] == '# This is a comment\n'
        assert lines[2] == '\n'

        # The changed line
        found = False
        for line in lines:
            if line.strip() == 'vwidth = 5':
                found = True
            # Old value must not be present
            assert 'vwidth = 3' not in line or 'vheight' in line
        assert found, "Changed option not found"

        # Other options unchanged
        cfg2 = WayfireConfigFile(path)
        assert cfg2.get_option('core', 'vheight') == '3'
        assert cfg2.get_option('core', 'plugins') == 'move resize alpha'
        assert cfg2.get_option('move', 'activate') == '<super> BTN_LEFT'

        # Comment about core plugins still present
        assert any('# Core plugins' in l for l in lines)

        print("PASS: set_existing_option (single-line change, comments preserved)")
    finally:
        os.unlink(path)


def test_add_new_option():
    """Adding a new option to existing section appends it."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        path = f.name

    try:
        cfg = WayfireConfigFile(path)
        cfg.set_option('core', 'close_top_view', '<super> KEY_Q')
        cfg.save(path)

        cfg2 = WayfireConfigFile(path)
        assert cfg2.get_option('core', 'close_top_view') == '<super> KEY_Q'
        # Existing options still there
        assert cfg2.get_option('core', 'vwidth') == '3'
        print("PASS: add_new_option")
    finally:
        os.unlink(path)


def test_add_new_section():
    """Adding option to nonexistent section creates it."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        path = f.name

    try:
        cfg = WayfireConfigFile(path)
        cfg.set_option('wobbly', 'spring_k', '8.0')
        cfg.save(path)

        cfg2 = WayfireConfigFile(path)
        assert cfg2.get_option('wobbly', 'spring_k') == '8.0'
        # Old sections still fine
        assert cfg2.get_option('core', 'vwidth') == '3'
        print("PASS: add_new_section")
    finally:
        os.unlink(path)


def test_remove_option():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        path = f.name

    try:
        cfg = WayfireConfigFile(path)
        cfg.remove_option('decoration', 'title_height')
        cfg.save(path)

        cfg2 = WayfireConfigFile(path)
        assert cfg2.get_option('decoration', 'title_height') is None
        assert cfg2.get_option('decoration', 'active_color') is not None
        print("PASS: remove_option")
    finally:
        os.unlink(path)


def test_enable_disable_plugin():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        path = f.name

    try:
        cfg = WayfireConfigFile(path)
        assert cfg.get_enabled_plugins() == ['move', 'resize', 'alpha']

        cfg.enable_plugin('wobbly')
        assert 'wobbly' in cfg.get_enabled_plugins()

        cfg.disable_plugin('resize')
        assert 'resize' not in cfg.get_enabled_plugins()
        assert 'move' in cfg.get_enabled_plugins()

        cfg.save(path)
        cfg2 = WayfireConfigFile(path)
        plugins = cfg2.get_enabled_plugins()
        assert 'wobbly' in plugins
        assert 'resize' not in plugins
        print("PASS: enable_disable_plugin")
    finally:
        os.unlink(path)


def test_comments_preserved_after_multiple_edits():
    """Multiple edits should still keep all comments."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        path = f.name

    try:
        cfg = WayfireConfigFile(path)
        cfg.set_option('core', 'vwidth', '4')
        cfg.set_option('move', 'activate', '<alt> BTN_LEFT')
        cfg.set_option('decoration', 'title_height', '25')
        cfg.save(path)

        with open(path) as f:
            content = f.read()

        assert '# Wayfire config file' in content
        assert '# This is a comment' in content
        assert '# Core plugins' in content
        assert '# Move plugin options' in content
        print("PASS: comments_preserved_after_multiple_edits")
    finally:
        os.unlink(path)


def test_reuse_section_after_removing_last_rule():
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, 'wayfire.ini')
        cfg = WayfireConfigFile(path)
        for _ in range(3):
            cfg.set_option('window-rules', 'rule_0', '')
            cfg.remove_option('window-rules', 'rule_0')
        rule = 'on created if app_id is "foot" then maximize'
        cfg.set_option('window-rules', 'rule_0', rule)
        cfg.save()
        with open(path) as f:
            assert f.read() == f'[window-rules]\nrule_0 = {rule}\n'
        assert WayfireConfigFile(path).get_option('window-rules', 'rule_0') == rule


def test_empty_section_survives_unrelated_index_rebuild():
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, 'wayfire.ini')
        original = '[window-rules]\n# Keep my rules here\n\n[core]\nplugins = window-rules\n'
        with open(path, 'w') as f:
            f.write(original)
        cfg = WayfireConfigFile(path)
        cfg.set_option('core', 'vwidth', '3')
        cfg.remove_option('core', 'vwidth')
        cfg.set_option('window-rules', 'rule_0', 'on created then maximize')
        cfg.save()
        with open(path) as f:
            assert f.read() == original.replace(
                '\n\n[core]', '\nrule_0 = on created then maximize\n\n[core]')


def test_save_repairs_existing_duplicate_rule_sections():
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, 'wayfire.ini')
        rule = 'on created if app_id is "foot" then maximize'
        with open(path, 'w') as f:
            f.write('[window-rules]\n\nrule_0 = ' + rule + '\n'
                    + '[window-rules]\n\n' * 4)
        cfg = WayfireConfigFile(path)
        cfg.save()
        with open(path) as f:
            repaired = f.read()
        assert repaired == '[window-rules]\nrule_0 = ' + rule + '\n\n'
        cfg.save()
        with open(path) as f:
            assert f.read() == repaired
        assert WayfireConfigFile(path).get_option('window-rules', 'rule_0') == rule
        cfg.remove_option('window-rules', 'rule_0')
        cfg.save()
        cfg.set_option('window-rules', 'rule_0', rule)
        cfg.save()
        with open(path) as f:
            assert f.read().count('[window-rules]') == 1


def test_duplicate_rule_repair_keeps_rules_comments_and_other_sections():
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, 'wayfire.ini')
        core = '[core]\n# Core options\nplugins = window-rules\n\n'
        with open(path, 'w') as f:
            f.write('[window-rules]\n# First rule\nrule_0 = old\n\n' + core
                    + '[window-rules]\n# Second rule\nfoot = foot rule\n'
                    + 'rule_0 = latest\n\n[move]\nactivate = test\n')
        cfg = WayfireConfigFile(path)
        cfg.save()
        with open(path) as f:
            text = f.read()
        assert text.count('[window-rules]') == 1
        assert core in text
        assert '# First rule' in text and '# Second rule' in text
        assert 'rule_0 = old' not in text
        saved = WayfireConfigFile(path)
        assert saved.get_section_options('window-rules') == {
            'foot': 'foot rule', 'rule_0': 'latest'}
        assert saved.get_option('move', 'activate') == 'test'
        cfg.set_option('window-rules', 'rule_1', 'new rule')
        cfg.save()
        assert WayfireConfigFile(path).get_option('window-rules', 'rule_1') == 'new rule'


def test_rule_spacing_after_add_remove_and_existing_gap():
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, 'wayfire.ini')
        for content in ('[window-rules]\n\n[core]\nplugins = window-rules\n',
                        '[window-rules]\n\nrule_0 = old\n\n[core]\nplugins = window-rules\n'):
            with open(path, 'w') as f:
                f.write(content)
            cfg = WayfireConfigFile(path)
            for _ in range(3):
                cfg.set_option('window-rules', 'rule_0', 'on created then maximize')
                cfg.save()
                with open(path) as f:
                    assert f.read() == ('[window-rules]\nrule_0 = on created then maximize\n'
                                        '\n[core]\nplugins = window-rules\n')
                cfg.remove_option('window-rules', 'rule_0')
                cfg.save()


if __name__ == '__main__':
    test_rule_spacing_after_add_remove_and_existing_gap()
    test_save_repairs_existing_duplicate_rule_sections()
    test_duplicate_rule_repair_keeps_rules_comments_and_other_sections()
    test_read_and_preserve()
    test_get_option()
    test_set_existing_option()
    test_add_new_option()
    test_add_new_section()
    test_remove_option()
    test_enable_disable_plugin()
    test_comments_preserved_after_multiple_edits()
    test_reuse_section_after_removing_last_rule()
    test_empty_section_survives_unrelated_index_rebuild()
    print("\nAll tests passed!")
