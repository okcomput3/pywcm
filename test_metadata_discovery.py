"""Discovery regressions for overlapping plugin installations."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from metadata import PluginType, load_all_metadata


def test_duplicate_installs_preserve_priority_and_distinct_plugins():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        preferred, fallback, shell = [root / name for name in ('preferred', 'fallback', 'shell')]
        for path in (preferred, fallback, shell):
            path.mkdir()
        (preferred / 'core.xml').write_text('''<wayfire><plugin name="core">
            <_short>Preferred core</_short><option name="preferred" type="bool"/>
            </plugin></wayfire>''')
        (fallback / 'core.xml').write_text('''<wayfire><plugin name="core">
            <_short>Old core</_short><option name="old" type="string"/>
            </plugin></wayfire>''')
        (fallback / 'extra.xml').write_text('<wayfire><plugin name="extra"/></wayfire>')
        (shell / 'core.xml').write_text('<wf-shell><plugin name="core"/></wf-shell>')
        alias = root / 'alias'
        alias.symlink_to(preferred, target_is_directory=True)
        originals = {p: p.read_bytes() for p in root.glob('*/*.xml')}
        with patch('metadata.find_metadata_dirs', return_value=[str(preferred), str(alias), str(fallback)]), \
                patch('metadata.find_wfshell_metadata_dirs', return_value=[str(shell)]):
            plugins = load_all_metadata()
        assert [(p.type, p.name) for p in plugins] == [
            (PluginType.WAYFIRE, 'core'), (PluginType.WAYFIRE, 'extra'),
            (PluginType.WF_SHELL, 'core')]
        assert plugins[0].disp_name == 'Preferred core'
        assert [o.name for g in plugins[0].option_groups for o in g.options] == ['preferred']
        assert all(p.read_bytes() == content for p, content in originals.items())


if __name__ == '__main__':
    test_duplicate_installs_preserve_priority_and_distinct_plugins()
    print('PASS: duplicate installations, symlink aliases, priority, and file preservation')
