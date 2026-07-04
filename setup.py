#!/usr/bin/env python3
import glob
import os

from setuptools import setup


def compile_translations():
    """Compile locale/<lang>/LC_MESSAGES/wcm.po to .mo using the project's
    pure-Python compiler (no gettext tools required). Done eagerly so the
    data_files list below can pick the .mo files up."""
    try:
        import i18n
    except ImportError:
        return
    for po in glob.glob(os.path.join('locale', '*', 'LC_MESSAGES', 'wcm.po')):
        mo = po[:-3] + '.mo'
        try:
            if (os.path.isfile(mo)
                    and os.path.getmtime(mo) >= os.path.getmtime(po)):
                continue
            entries = i18n.parse_po(po)
            if entries:
                i18n.compile_mo(entries, mo)
        except Exception as e:
            print(f'warning: could not compile {po}: {e}')


def locale_data_files():
    files = []
    for mo in glob.glob(os.path.join('locale', '*', 'LC_MESSAGES', 'wcm.mo')):
        lang = mo.split(os.sep)[1]
        files.append((f'share/locale/{lang}/LC_MESSAGES', [mo]))
    return files


compile_translations()

setup(
    name='wcm',
    version='0.2.0',
    description='Wayfire Config Manager — Python/GTK4 Edition',
    author='Andrew Pliatsikas, Scott Moreau',
    license='MIT',
    py_modules=['wcm', 'config_backend', 'metadata', 'i18n'],
    install_requires=[
        'PyGObject',
        'lxml',
    ],
    entry_points={
        'gui_scripts': [
            'wcm = wcm:main',
        ],
    },
    data_files=(
        locale_data_files()
        + [('share/applications', ['wcm.desktop'])]
    ),
    python_requires='>=3.8',
)
