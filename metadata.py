"""
Wayfire Plugin Metadata Parser

Reads XML metadata files from wayfire's metadata directory to discover
available plugins and their configurable options.
"""

import os
import glob
import shutil
import subprocess
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any
from lxml import etree


class OptionType(Enum):
    UNDEFINED = auto()
    INT = auto()
    BOOL = auto()
    DOUBLE = auto()
    STRING = auto()
    GESTURE = auto()
    ACTIVATOR = auto()
    BUTTON = auto()
    KEY = auto()
    COLOR = auto()
    GROUP = auto()
    SUBGROUP = auto()
    DYNAMIC_LIST = auto()
    ANIMATION = auto()


class PluginType(Enum):
    NONE = auto()
    WAYFIRE = auto()
    WF_SHELL = auto()


OPTION_TYPE_MAP = {
    'int': OptionType.INT,
    'bool': OptionType.BOOL,
    'double': OptionType.DOUBLE,
    'string': OptionType.STRING,
    'gesture': OptionType.GESTURE,
    'activator': OptionType.ACTIVATOR,
    'button': OptionType.BUTTON,
    'key': OptionType.KEY,
    'color': OptionType.COLOR,
    'dynamic-list': OptionType.DYNAMIC_LIST,
    'animation': OptionType.ANIMATION,
}


@dataclass
class CompoundEntry:
    """An entry in a compound/dynamic-list option."""
    prefix: str = ''
    entry_type: str = 'string'
    name: str = ''
    disp_name: str = ''
    tooltip: str = ''
    hints: List[str] = field(default_factory=list)


@dataclass
class Option:
    name: str = ''
    disp_name: str = ''
    tooltip: str = ''
    type: OptionType = OptionType.UNDEFINED
    default_value: Any = None
    min_val: float = float('-inf')
    max_val: float = float('inf')
    precision: float = 0.1
    hidden: bool = False
    hints: List[str] = field(default_factory=list)
    int_labels: List[Tuple[str, int]] = field(default_factory=list)
    str_labels: List[Tuple[str, str]] = field(default_factory=list)
    options: List['Option'] = field(default_factory=list)
    entries: List[CompoundEntry] = field(default_factory=list)
    plugin_name: str = ''

    @property
    def is_group(self):
        return self.type in (OptionType.GROUP, OptionType.SUBGROUP)


@dataclass
class Plugin:
    name: str = ''
    disp_name: str = ''
    tooltip: str = ''
    category: str = 'Uncategorized'
    type: PluginType = PluginType.NONE
    enabled: bool = False
    option_groups: List[Option] = field(default_factory=list)

    CORE_PLUGINS = {'core', 'input', 'workarounds'}

    @property
    def is_core_plugin(self):
        return self.name in self.CORE_PLUGINS


def _text(node):
    if node is not None and node.text:
        return node.text.strip()
    return ''


def _parse_entry(entry_node):
    """Parse a <entry> element inside a dynamic-list option."""
    e = CompoundEntry()
    e.prefix = entry_node.get('prefix', '')
    e.entry_type = entry_node.get('type', 'string')
    e.name = entry_node.get('name', '')
    for child in entry_node:
        tag = str(child.tag)
        if tag == '_short':
            e.disp_name = _text(child)
        elif tag == '_long':
            e.tooltip = _text(child)
        elif tag == 'hint':
            h = _text(child)
            if h:
                e.hints.append(h)
    return e


def _parse_option(opt_node, plugin_name):
    """Parse an <option> XML element into an Option object."""
    opt = Option()
    opt.plugin_name = plugin_name
    opt.name = opt_node.get('name', '')

    type_str = opt_node.get('type', '')
    opt.type = OPTION_TYPE_MAP.get(type_str, OptionType.UNDEFINED)

    hidden = opt_node.get('hidden', '')
    opt.hidden = (hidden.lower() == 'true')

    # Set defaults based on type
    if opt.type == OptionType.INT:
        opt.default_value = 0
        opt.min_val = -2**31
        opt.max_val = 2**31
    elif opt.type == OptionType.DOUBLE:
        opt.default_value = 0.0
        opt.min_val = -1e15
        opt.max_val = 1e15
        opt.precision = 0.1
    elif opt.type == OptionType.BOOL:
        opt.default_value = False
    elif opt.type in (OptionType.STRING, OptionType.BUTTON, OptionType.KEY,
                      OptionType.ACTIVATOR, OptionType.GESTURE,
                      OptionType.COLOR):
        opt.default_value = ''
    elif opt.type == OptionType.ANIMATION:
        opt.default_value = '300ms linear'
        opt.min_val = 0
        opt.max_val = 1e15
    elif opt.type == OptionType.DYNAMIC_LIST:
        opt.default_value = 'string'

    for child in opt_node:
        tag = str(child.tag)

        if tag == '_short':
            opt.disp_name = _text(child)
        elif tag == '_long':
            opt.tooltip = _text(child)
        elif tag == 'default':
            dtext = _text(child)
            if dtext:
                if opt.type == OptionType.INT:
                    try:
                        opt.default_value = int(dtext)
                    except ValueError:
                        opt.default_value = 0
                elif opt.type == OptionType.DOUBLE:
                    try:
                        opt.default_value = float(dtext)
                    except ValueError:
                        opt.default_value = 0.0
                elif opt.type == OptionType.BOOL:
                    opt.default_value = dtext.lower() in ('true', '1')
                else:
                    opt.default_value = dtext
        elif tag == 'min':
            try:
                opt.min_val = float(_text(child))
            except ValueError:
                pass
        elif tag == 'max':
            try:
                opt.max_val = float(_text(child))
            except ValueError:
                pass
        elif tag == 'precision':
            try:
                opt.precision = float(_text(child))
            except ValueError:
                pass
        elif tag == 'hint':
            h = _text(child)
            if h:
                opt.hints.append(h)
        elif tag == 'type' and opt.type == OptionType.DYNAMIC_LIST:
            opt.default_value = _text(child)
        elif tag == 'entry':
            opt.entries.append(_parse_entry(child))
        elif tag == 'desc':
            val_node = child.find('value')
            name_node = child.find('_name')
            if val_node is not None and name_node is not None:
                val = _text(val_node)
                lname = _text(name_node)
                if opt.type == OptionType.INT:
                    try:
                        opt.int_labels.append((lname, int(val)))
                    except ValueError:
                        pass
                elif opt.type == OptionType.STRING:
                    opt.str_labels.append((lname, val))

    return opt


def _parse_plugin_node(plugin_node):
    """Parse a <plugin> XML element into a Plugin object."""
    plugin = Plugin()
    plugin.name = plugin_node.get('name', '')

    main_group = None

    for child in plugin_node:
        tag = str(child.tag)

        if tag == '_short':
            plugin.disp_name = _text(child)
        elif tag == '_long':
            plugin.tooltip = _text(child)
        elif tag == 'category':
            cat = _text(child)
            if cat:
                plugin.category = cat
        elif tag == 'option':
            if main_group is None:
                main_group = Option(name='General', type=OptionType.GROUP,
                                    plugin_name=plugin.name)
                plugin.option_groups.append(main_group)
            opt = _parse_option(child, plugin.name)
            main_group.options.append(opt)
        elif tag == 'group':
            group = Option(type=OptionType.GROUP, plugin_name=plugin.name)
            for gchild in child:
                gtag = str(gchild.tag)
                if gtag == '_short':
                    group.name = _text(gchild)
                elif gtag == 'option':
                    opt = _parse_option(gchild, plugin.name)
                    group.options.append(opt)
                elif gtag == 'subgroup':
                    subgroup = Option(type=OptionType.SUBGROUP,
                                      plugin_name=plugin.name)
                    for sgchild in gchild:
                        sgtag = str(sgchild.tag)
                        if sgtag == '_short':
                            subgroup.name = _text(sgchild)
                        elif sgtag == 'option':
                            opt = _parse_option(sgchild, plugin.name)
                            subgroup.options.append(opt)
                    group.options.append(subgroup)
            plugin.option_groups.append(group)

    return plugin


def load_metadata_from_dir(xml_dir):
    """Load all plugin metadata XML files from a directory."""
    plugins = []
    if not os.path.isdir(xml_dir):
        return plugins

    for xml_path in sorted(glob.glob(os.path.join(xml_dir, '*.xml'))):
        try:
            tree = etree.parse(xml_path)
            root = tree.getroot()
            root_tag = root.tag

            if root_tag in ('wayfire', 'wf-shell'):
                ptype = (PluginType.WAYFIRE if root_tag == 'wayfire'
                         else PluginType.WF_SHELL)
                for pnode in root.findall('plugin'):
                    plugin = _parse_plugin_node(pnode)
                    plugin.type = ptype
                    if plugin.name:
                        plugins.append(plugin)
        except Exception as e:
            print(f"WARN: Failed to parse {xml_path}: {e}")

    return plugins


def _pkg_config_var(pkg, var):
    """Get a pkg-config variable value."""
    try:
        result = subprocess.run(
            ['pkg-config', '--variable=' + var, pkg],
            capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ''


def _wayfire_prefix():
    """Derive the install prefix from the wayfire binary location.

    Mirrors how the C++ WCM gets WAYFIRE_METADATADIR at build time —
    equivalent to: WF_BIN="$(command -v wayfire)"; echo "${WF_BIN%/bin/wayfire}"
    """
    wf_bin = shutil.which('wayfire')
    if wf_bin:
        # e.g. /opt/wayfire/bin/wayfire -> /opt/wayfire
        # Resolve symlinks so we get the real install prefix
        wf_bin = os.path.realpath(wf_bin)
        return os.path.dirname(os.path.dirname(wf_bin))
    return ''


def find_metadata_dirs():
    """Find wayfire metadata directories on the system."""
    dirs = []

    # 1. Environment variable override (highest priority, user-specified)
    env_path = os.environ.get('WAYFIRE_PLUGIN_XML_PATH', '')
    if env_path:
        for d in env_path.split(':'):
            d = d.strip()
            if d and os.path.isdir(d) and d not in dirs:
                dirs.append(d)

    # 2. Default: derive from wayfire binary location
    #    This is the most reliable method — works for any install prefix
    bin_prefix = _wayfire_prefix()
    if bin_prefix:
        d = os.path.join(bin_prefix, 'share', 'wayfire', 'metadata')
        if os.path.isdir(d) and d not in dirs:
            dirs.append(d)

    # 3. pkg-config (works when dev packages are installed)
    pkg_meta = _pkg_config_var('wayfire', 'metadatadir')
    if pkg_meta and os.path.isdir(pkg_meta) and pkg_meta not in dirs:
        dirs.append(pkg_meta)

    pkg_prefix = _pkg_config_var('wayfire', 'prefix')
    if pkg_prefix:
        d = os.path.join(pkg_prefix, 'share', 'wayfire', 'metadata')
        if os.path.isdir(d) and d not in dirs:
            dirs.append(d)

    # 4. Standard paths
    for prefix in ('/usr', '/usr/local', os.path.expanduser('~/.local')):
        d = os.path.join(prefix, 'share', 'wayfire', 'metadata')
        if os.path.isdir(d) and d not in dirs:
            dirs.append(d)

    # 5. Glob search as last resort
    for pattern in ('/usr/*/share/wayfire/metadata',
                    '/opt/*/share/wayfire/metadata'):
        for d in glob.glob(pattern):
            if os.path.isdir(d) and d not in dirs:
                dirs.append(d)

    return dirs


def find_wfshell_metadata_dirs():
    """Find wf-shell metadata directories."""
    dirs = []

    pkg_meta = _pkg_config_var('wf-shell', 'metadatadir')
    if pkg_meta and os.path.isdir(pkg_meta) and pkg_meta not in dirs:
        dirs.append(pkg_meta)

    # Derive from wayfire binary location
    bin_prefix = _wayfire_prefix()
    if bin_prefix:
        d = os.path.join(bin_prefix, 'share', 'wayfire', 'metadata', 'wf-shell')
        if os.path.isdir(d) and d not in dirs:
            dirs.append(d)

    for prefix in ('/usr', '/usr/local', os.path.expanduser('~/.local')):
        d = os.path.join(prefix, 'share', 'wayfire', 'metadata', 'wf-shell')
        if os.path.isdir(d) and d not in dirs:
            dirs.append(d)

    for pattern in ('/opt/*/share/wayfire/metadata/wf-shell',):
        for d in glob.glob(pattern):
            if os.path.isdir(d) and d not in dirs:
                dirs.append(d)

    return dirs


def load_all_metadata():
    """Load all wayfire and wf-shell metadata."""
    plugins = []
    wf_dirs = find_metadata_dirs()
    ws_dirs = find_wfshell_metadata_dirs()

    if wf_dirs:
        print(f"WCM: Loading wayfire metadata from: {wf_dirs}")
    else:
        print("WCM: WARNING - No wayfire metadata directories found!")
        print("WCM: Plugins will be generated from config file.")
        print("WCM: Set WAYFIRE_PLUGIN_XML_PATH to your metadata dir.")

    for d in wf_dirs:
        plugins.extend(load_metadata_from_dir(d))
    for d in ws_dirs:
        plugins.extend(load_metadata_from_dir(d))

    if plugins:
        cats = {}
        for p in plugins:
            cats[p.category] = cats.get(p.category, 0) + 1
        print(f"WCM: Loaded {len(plugins)} plugins: {dict(cats)}")

    return plugins