"""Regression tests from the bug audit; only temporary configs are modified."""
import unittest
import sys, json, tempfile, random, hashlib, time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from config_backend import WayfireConfigFile, PresetManager
from metadata import Option, OptionType, Plugin, CompoundEntry
from wcm import Gtk, GLib, OptionWidget, PluginPage, DisplayPage
TESTS = []
def check(name, fn):
    def test():
        if name.startswith('gui.'):
            if not Gtk.init_check():
                raise unittest.SkipTest('GTK display required')
        with tempfile.TemporaryDirectory(prefix='pywcm-regression-') as tmp:
            path = Path(tmp) / 'wayfire.ini'
            fn(WayfireConfigFile(str(path)), Path(tmp))
    test.__name__ = 'test_' + name.replace('.', '_')
    globals()[test.__name__] = test
    TESTS.append(test)

def require(ok, detail):
    if not ok: raise AssertionError(detail)
def pump():
    deadline=time.monotonic()+.5
    ctx=GLib.MainContext.default()
    while time.monotonic()<deadline:
        while ctx.pending(): ctx.iteration(False)
        time.sleep(.005)

def backend():
    def fuzz(c,t):
        r=random.Random(81297); expected={}
        for i in range(2000):
            sec=r.choice(['core','command','window-rules','output:DP-1','extra'])
            key='key_'+str(r.randrange(20)); op=r.randrange(5)
            if op==0:
                c.remove_section(sec);expected.pop(sec,None)
            elif op==1:
                c.remove_option(sec,key);expected.setdefault(sec,{}).pop(key,None)
            else:
                value=r.choice(['none','true','0','hello 世界','x = y','<super> KEY_A','a\\b'])
                c.set_option(sec,key,value);expected.setdefault(sec,{})[key]=value
            c.save();c=WayfireConfigFile(c.path)
            actual={s:dict(c.get_section_options(s)) for s in c.get_sections() if c.get_section_options(s)}
            require(actual=={s:v for s,v in expected.items() if v},f'operation {i}: {actual}')
        return '2000 seeded operations including section deletion and Unicode'
    check('config.randomized_2000_operations',fuzz)
    def duplicate_section(c,t):
        Path(c.path).write_text('[output:DP-1]\nscale = 1\n[core]\nvwidth = 2\n[output:DP-1]\nmode = off\n')
        c=WayfireConfigFile(c.path); c.remove_section('output:DP-1');c.save()
        require('output:DP-1' not in WayfireConfigFile(c.path).get_sections(),Path(c.path).read_text())
    check('config.remove_duplicate_output_sections',duplicate_section)
    def shell_preset(c,t):
        c.set_option('panel','position','top');c.save()
        pm=PresetManager(str(t/'presets'));pm.save_plugin_preset('top','panel',c)
        pm.load_plugin_preset('top','panel',c)
        require('core' not in c.get_sections(),f'wf-shell config gained {c.get_all_options()}')
    check('preset.wfshell_no_core_pollution',shell_preset)
    def master_bytes(c,t):
        data=b'# comment\r\n[core]\r\nplugins = move\r\n'
        Path(c.path).write_bytes(data); pm=PresetManager(str(t/'presets'))
        pm.save_master_preset_file('snap',c.path);Path(c.path).write_text('[core]\nplugins = blur\n')
        pm.load_master_preset_file('snap',c.path)
        require(Path(c.path).read_bytes()==data,'snapshot bytes changed')
    check('preset.master_verbatim_crlf',master_bytes)
    def plugin_unicode(c,t):
        c.set_option('core','plugins','move blur');c.set_option('move','label','窗口');c.save()
        pm=PresetManager(str(t/'presets'));pm.save_plugin_preset('测试','move',c)
        c.set_option('move','label','changed');pm.load_plugin_preset('测试','move',c)
        require(c.get_option('move','label')=='窗口',c.get_all_options())
        require(c.get_enabled_plugins()==['move','blur'],c.get_enabled_plugins())
    check('preset.unicode_roundtrip',plugin_unicode)
    def malformed_rate(c,t):
        from wcm import _parse_refresh
        for v in ['abc','--60','60 HzHz','nan','NaN','1e309','-1e309','60..0','0','-60']:
            try: result=_parse_refresh(v)
            except Exception as e: raise AssertionError(f'{v!r} raised {type(e).__name__}')
    check('display.invalid_refresh_matrix',malformed_rate)

def gui():
    def widget(c,opt,value):
        if value is not None:c.set_option('demo',opt.name,value)
        c.save(); return OptionWidget(opt,c,Plugin(name='demo'))
    def precision(c,t):
        w=widget(c,Option(name='fine',type=OptionType.DOUBLE,default_value=.00001,precision=.00001,min_val=0,max_val=1),None)
        require(w.ed.get_digits()>=5,f'digits={w.ed.get_digits()}, displayed={w.ed.get_text()!r}, value={w.ed.get_value()}')
    check('gui.small_double_precision',precision)
    def custom_choice(c,t):
        w=widget(c,Option(name='animation',type=OptionType.STRING,default_value='fade',str_labels=[('Fade','fade')]),'custom-animation')
        require(w.ed.get_active_text() is not None,f'saved custom-animation, displayed={w.ed.get_active_text()!r}')
    check('gui.unlisted_saved_choice_visible',custom_choice)
    def race(c,t):
        w=widget(c,Option(name='text',type=OptionType.STRING,default_value=''), 'old')
        pm=PresetManager(str(t/'presets'))
        c.set_option('demo','text','preset-value');c.save()
        pm.save_plugin_preset('chosen','demo',c)
        w.ed.set_text('typed-before-preset')
        pm.load_plugin_preset('chosen','demo',c)
        pump()
        require(c.get_option('demo','text')=='preset-value',f'pending old edit overwrote preset: {c.get_option("demo","text")}')
    check('gui.pending_edit_after_preset',race)
    def collision(c,t):
        c.set_option('command','binding_new0','<super> KEY_Z');c.save()
        page=SimpleNamespace(_make_bw=Mock(return_value=Gtk.Box()))
        PluginPage._add_bind(page,c,Plugin(name='command'),Gtk.Box())
        require(c.get_option('command','binding_new0')=='<super> KEY_Z',str(c.get_section_options('command')))
    check('gui.new_command_preserves_existing_binding',collision)
    def unmatched(c,t):
        c.set_option('command','binding_orphan','<super> KEY_X'); c.save()
        page=SimpleNamespace(_make_bw=Mock(return_value=Gtk.Box()))
        PluginPage._make_bindings(page,Option(),c,Plugin(name='command'),c.get_section_options('command'))
        require(page._make_bw.call_count==1,'binding without command has no editable row')
    check('gui.binding_without_command_visible',unmatched)
    def switchtype(c,t):
        c.set_option('command','command_demo','echo hi');c.set_option('command','binding_demo','<super> KEY_A');c.save()
        page=PluginPage(Plugin(name='command'),c)
        fr=page._make_bw('demo',c,Plugin(name='command'),c.get_section_options('command'),Gtk.Box())
        vb=fr.get_child().get_child();typ=vb.get_first_child().get_last_child()
        br=vb.get_first_child().get_next_sibling(); entry=br.get_first_child().get_next_sibling()
        typ.set_active(1);entry.set_text('<super> KEY_B')
        require(c.get_option('command','repeatable_binding_demo')=='<super> KEY_B',str(c.get_section_options('command')))
    check('gui.binding_type_edit_real_signals_known_bug',switchtype)
    def reset(c,t):
        w=widget(c,Option(name='zero',type=OptionType.INT,default_value=0,min_val=0,max_val=10),'3')
        w.reset_btn.emit('clicked')
        require(c.get_option('demo','zero')=='0',repr(c.get_option('demo','zero')))
    check('gui.reset_zero_real_signals_known_bug',reset)
    def initialization(c,t):
        opts=[Option(name='integer',type=OptionType.INT,default_value=2,min_val=0,max_val=10),Option(name='bool',type=OptionType.BOOL,default_value=True),Option(name='double',type=OptionType.DOUBLE,default_value=.5,min_val=0,max_val=1),Option(name='color',type=OptionType.COLOR,default_value='1 0 0 1'),Option(name='key',type=OptionType.KEY,default_value='none'),Option(name='anim',type=OptionType.ANIMATION,default_value='300ms linear',min_val=0,max_val=1000)]
        c.set_option('core','plugins','move');c.save();before=Path(c.path).read_bytes()
        widgets=[OptionWidget(o,c,Plugin(name='demo')) for o in opts];pump()
        require(before==Path(c.path).read_bytes(),'opening controls changed config')
    check('gui.open_options_no_writes',initialization)
    def debounce(c,t):
        w=widget(c,Option(name='text',type=OptionType.STRING,default_value=''),'initial')
        with patch.object(c,'save',wraps=c.save) as save:
            for value in ['a','ab','abc']:w.ed.set_text(value)
            pump();require(save.call_count==1,f'{save.call_count} saves')
            require(c.get_option('demo','text')=='abc',c.get_option('demo','text'))
    check('gui.debounce_latest_value',debounce)
    def display_init(c,t):
        c.set_option('output:DP-1','mode','1920x1080@60000');c.save();before=Path(c.path).read_bytes()
        page=SimpleNamespace(_active_confirm=None,_confirm_sources=set(),app=None)
        card=DisplayPage._build_card(page,dict(name='DP-1',enabled=True,modes=[],current_mode=(1920,1080,60000)),c,is_primary=True)
        require(before==Path(c.path).read_bytes(),'display initialization wrote config')
    check('gui.display_open_no_writes',display_init)
    def bad_position(c,t):
        c.set_option('output:DP-1','position','inf,0');c.save()
        page=SimpleNamespace(_active_confirm=None,_confirm_sources=set(),app=None)
        DisplayPage._build_card(page,dict(name='DP-1',enabled=True,modes=[]),c,is_primary=True)
    check('gui.invalid_position_does_not_break_page',bad_position)


backend()
gui()

def additional():
    def multiline(c,t):
        text='# preserved\r\n[core]\r\nplugins = \\\r\n    move \\\r\n    resize\r\n  vwidth  = 2\r\n[blur]\r\nmethod=kawase\r\n'
        Path(c.path).write_bytes(text.encode());c=WayfireConfigFile(c.path)
        require(c.get_enabled_plugins()==['move','resize'],c.get_enabled_plugins())
        c.set_option('core','vwidth','3');c.save()
        require(Path(c.path).read_bytes()==text.replace('vwidth  = 2','vwidth  = 3').encode(),Path(c.path).read_bytes())
        c.enable_plugin('blur');c.save()
        require(WayfireConfigFile(c.path).get_enabled_plugins()==['move','resize','blur'],Path(c.path).read_text())
    check('config.multiline_toggle_and_crlf_preservation',multiline)
    def external(c,t):
        c.set_option('core','a','1');c.set_option('core','b','2');c.save()
        other=WayfireConfigFile(c.path);other.set_option('core','b','9');other.save()
        c.set_option('core','a','3');c.save()
        require(c.get_option('core','b')=='9',c.get_all_options())
        require(WayfireConfigFile(c.path).get_option('core','a')=='3','local edit lost')
    check('config.external_merge',external)
    def duplicate(c,t):
        Path(c.path).write_text('[command]\ncommand_x = old\ncommand_x = new\n')
        c=WayfireConfigFile(c.path);c.remove_option('command','command_x');c.save()
        require(WayfireConfigFile(c.path).get_option('command','command_x') is None,'duplicate survived')
    check('config.delete_all_duplicate_keys',duplicate)
    def newline(c,t):
        Path(c.path).write_text('[core]');c=WayfireConfigFile(c.path)
        c.set_option('core','a','1');c.save()
        require(WayfireConfigFile(c.path).get_option('core','a')=='1',Path(c.path).read_text())
    check('config.unterminated_header',newline)
    def zero(c,t):
        from config_backend import OutputManager
        for res in ('0x1080','1920x0','0x0'):
            require(OutputManager.validate_mode(res,60000,True,[])[0]=='error',res)
    check('display.zero_dimensions',zero)
    def legacy_shell(c,t):
        pm=PresetManager(str(t/'presets'));c.set_option('panel','position','top');c.save()
        pm.save_plugin_preset('old','panel',c)
        p=WayfireConfigFile(pm._plugin_path('panel','old'))
        p.set_option('_preset_meta','enabled','false');p.save()
        pm.load_plugin_preset('old','panel',c,manage_enabled=False)
        require('core' not in c.get_sections(),c.get_all_options())
    check('preset.legacy_shell_metadata_ignored',legacy_shell)
    def release(c,t):
        c.set_option('command','command_x','echo test');c.set_option('command','release_binding_x','<super> KEY_A');c.save()
        plg=Plugin(name='command');page=PluginPage(plg,c);parent=Gtk.Box()
        frame=page._make_bw('x',c,plg,c.get_section_options('command'),parent);parent.append(frame)
        box=frame.get_child().get_child();combo=box.get_first_child().get_last_child()
        entry=box.get_first_child().get_next_sibling().get_first_child().get_next_sibling()
        require(combo.get_active()==3,'release type not selected')
        for typ,prefix in [(0,'binding_'),(3,'release_binding_'),(2,'always_binding_'),(1,'repeatable_binding_')]:
            combo.set_active(typ);entry.set_text('<super> KEY_'+str(typ))
            require(c.get_option('command',prefix+'x')=='<super> KEY_'+str(typ),c.get_all_options())
            require(len(c.get_section_options('command'))==2,c.get_all_options())
        combo.set_active(3);page._rm_bind(c,plg,'x',frame,parent)
        require(not c.get_section_options('command'),c.get_all_options())
    check('gui.release_switch_edit_delete',release)
    def close_flush(c,t):
        from wcm import WCM
        w=OptionWidget(Option(name='text',type=OptionType.STRING,default_value=''),c,Plugin(name='demo'))
        w.ed.set_text('last keystroke')
        window=SimpleNamespace(config=c,wf_shell_config=WayfireConfigFile(),display_page=None)
        require(WCM._before_close(window) is False,'close blocked')
        require(WayfireConfigFile(c.path).get_option('demo','text')=='last keystroke','last edit missing')
        require(not c._pending_edits and not w._text_save_id,'pending callback survived')
    check('gui.close_flushes_last_edit',close_flush)
    def rollback(c,t):
        for baseline in (None,'mirror DP-2','1920x1080@60000'):
            c.remove_section('output:DP-1')
            if baseline is not None:c.set_option('output:DP-1','mode',baseline)
            c.save()
            page=SimpleNamespace(_active_confirm=None,_confirm_sources=set(),_pending_reverts={},app=None,_root=Mock())
            card=DisplayPage._build_card(page,dict(name='DP-1',enabled=True,modes=[],current_mode=(1920,1080,60000)),c,is_primary=True)
            box=card.get_child();row=box.get_first_child().get_next_sibling();combo=row.get_last_child()
            combo.get_child().set_text('1280x720')
            require(c.get_option('output:DP-1','mode','').split('@')[0]=='1280x720',str(c.get_all_options()))
            require(page._confirm_sources and page._pending_reverts,'no rollback registered')
            DisplayPage.reload(page)
            page._root.get_first_child.assert_not_called()
            DisplayPage.revert_pending_changes(page)
            require(c.get_option('output:DP-1','mode')==baseline,c.get_all_options())
            require(c.get_option('output:DP-1','transform') is None,c.get_all_options())
            require(not page._confirm_sources and not page._pending_reverts,'rollback left timers')
    check('gui.pending_display_refresh_and_close_rollback',rollback)
    def reset_bool(c,t):
        for typ,default,expected in [(OptionType.BOOL,False,'false'),(OptionType.BOOL,True,'true'),(OptionType.DOUBLE,0.0,'0.0')]:
            opt=Option(name='setting',type=typ,default_value=default,min_val=0,max_val=1)
            w=OptionWidget(opt,c,Plugin(name='demo'));w.reset_btn.emit('clicked')
            require(c.get_option('demo','setting')==expected,c.get_all_options())
    check('gui.reset_boolean_and_double',reset_bool)

additional()

if __name__ == '__main__':
    suite = unittest.TestSuite(unittest.FunctionTestCase(test) for test in TESTS)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
