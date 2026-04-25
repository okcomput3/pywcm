#!/usr/bin/env python3
"""Tests for the WCM metadata XML parser."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
from metadata import load_metadata_from_dir, OptionType, PluginType

SAMPLE_XML = """\
<?xml version="1.0"?>
<wayfire>
    <plugin name="move">
        <_short>Move</_short>
        <_long>A plugin to move windows by dragging them.</_long>
        <category>Window Management</category>
        <option name="activate" type="button">
            <_short>Activate</_short>
            <_long>Activate window move.</_long>
            <default>&lt;super&gt; BTN_LEFT</default>
        </option>
        <option name="enable_snap" type="bool">
            <_short>Enable Snap</_short>
            <_long>Enable snapping windows to edges.</_long>
            <default>true</default>
        </option>
        <option name="snap_threshold" type="int">
            <_short>Snap Threshold</_short>
            <_long>Distance in pixels to trigger snapping.</_long>
            <default>10</default>
            <min>0</min>
            <max>100</max>
        </option>
        <option name="opacity" type="double">
            <_short>Opacity</_short>
            <_long>Window opacity while moving.</_long>
            <default>0.8</default>
            <min>0.1</min>
            <max>1.0</max>
            <precision>0.01</precision>
        </option>
        <group>
            <_short>Advanced</_short>
            <option name="mode" type="string">
                <_short>Mode</_short>
                <_long>The move mode to use.</_long>
                <default>normal</default>
                <desc>
                    <value>normal</value>
                    <_name>Normal</_name>
                </desc>
                <desc>
                    <value>lazy</value>
                    <_name>Lazy</_name>
                </desc>
            </option>
            <subgroup>
                <_short>Extra</_short>
                <option name="extra_flag" type="bool">
                    <_short>Extra Flag</_short>
                    <default>false</default>
                </option>
            </subgroup>
        </group>
    </plugin>
</wayfire>
"""

SAMPLE_ANIMATION_XML = """\
<?xml version="1.0"?>
<wayfire>
    <plugin name="grid">
        <_short>Grid</_short>
        <_long>Position windows on a grid.</_long>
        <category>Window Management</category>
        <option name="duration" type="animation">
            <_short>Duration</_short>
            <_long>Animation duration in ms.</_long>
            <default>300ms linear</default>
            <min>0</min>
            <max>5000</max>
        </option>
    </plugin>
</wayfire>
"""


def test_basic_parse():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'move.xml')
        with open(path, 'w') as f:
            f.write(SAMPLE_XML)

        plugins = load_metadata_from_dir(d)
        assert len(plugins) == 1
        p = plugins[0]
        assert p.name == 'move'
        assert p.disp_name == 'Move'
        assert p.category == 'Window Management'
        assert p.type == PluginType.WAYFIRE
        print("PASS: basic_parse")


def test_option_types():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'move.xml')
        with open(path, 'w') as f:
            f.write(SAMPLE_XML)

        plugins = load_metadata_from_dir(d)
        p = plugins[0]

        # Should have 2 groups: auto-created "General" and explicit "Advanced"
        assert len(p.option_groups) == 2

        general = p.option_groups[0]
        assert general.name == 'General'
        assert len(general.options) == 4

        # Check button type
        activate = general.options[0]
        assert activate.name == 'activate'
        assert activate.type == OptionType.BUTTON
        assert activate.default_value == '<super> BTN_LEFT'

        # Check bool
        snap = general.options[1]
        assert snap.type == OptionType.BOOL
        assert snap.default_value is True

        # Check int with min/max
        thresh = general.options[2]
        assert thresh.type == OptionType.INT
        assert thresh.default_value == 10
        assert thresh.min_val == 0
        assert thresh.max_val == 100

        # Check double with precision
        opacity = general.options[3]
        assert opacity.type == OptionType.DOUBLE
        assert opacity.default_value == 0.8
        assert opacity.precision == 0.01

        print("PASS: option_types")


def test_groups_and_subgroups():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'move.xml')
        with open(path, 'w') as f:
            f.write(SAMPLE_XML)

        plugins = load_metadata_from_dir(d)
        p = plugins[0]

        advanced = p.option_groups[1]
        assert advanced.name == 'Advanced'

        # Mode option with string labels
        mode = advanced.options[0]
        assert mode.type == OptionType.STRING
        assert len(mode.str_labels) == 2
        assert mode.str_labels[0] == ('Normal', 'normal')
        assert mode.str_labels[1] == ('Lazy', 'lazy')

        # Subgroup
        subgroup = advanced.options[1]
        assert subgroup.type == OptionType.SUBGROUP
        assert subgroup.name == 'Extra'
        assert len(subgroup.options) == 1
        assert subgroup.options[0].name == 'extra_flag'

        print("PASS: groups_and_subgroups")


def test_animation_type():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'grid.xml')
        with open(path, 'w') as f:
            f.write(SAMPLE_ANIMATION_XML)

        plugins = load_metadata_from_dir(d)
        p = plugins[0]
        assert p.name == 'grid'

        dur_opt = p.option_groups[0].options[0]
        assert dur_opt.type == OptionType.ANIMATION
        assert dur_opt.default_value == '300ms linear'
        assert dur_opt.min_val == 0
        assert dur_opt.max_val == 5000

        print("PASS: animation_type")


def test_import_wcm():
    """Just make sure the main module imports without error."""
    try:
        import wcm as wcm_mod
        assert hasattr(wcm_mod, 'WCM')
        assert hasattr(wcm_mod, 'MainPage')
        assert hasattr(wcm_mod, 'PluginPage')
        assert hasattr(wcm_mod, 'OptionWidget')
        print("PASS: import_wcm")
    except ValueError as e:
        if 'Namespace Gtk not available' in str(e):
            print("SKIP: import_wcm (GTK4 not available)")
        else:
            raise


if __name__ == '__main__':
    test_basic_parse()
    test_option_types()
    test_groups_and_subgroups()
    test_animation_type()
    test_import_wcm()
    print("\nAll metadata tests passed!")
