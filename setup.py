#!/usr/bin/env python3
from setuptools import setup

setup(
    name='wcm',
    version='0.1.0',
    description='Wayfire Config Manager — Python/GTK4 Edition',
    author='Andrew Pliatsikas, Scott Moreau',
    license='MIT',
    py_modules=['wcm', 'config_backend', 'metadata'],
    install_requires=[
        'PyGObject',
        'lxml',
    ],
    entry_points={
        'gui_scripts': [
            'wcm = wcm:main',
        ],
    },
    python_requires='>=3.8',
)
