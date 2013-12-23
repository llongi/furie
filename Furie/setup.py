#!/usr/bin/env python

from distutils import core

kw = dict(
    name = 'Furie',
    version = '0.5',
    description = 'Powerful, fully DB-driven server framework with lots of useful features.',
    author = 'Luca Longinotti',
    author_email = 'chtekk@longitekk.com',
    url = 'http://chtekk.longitekk.com/',
    license = 'GPL-2',
    packages = ['Furie',
                'Furie.db',
                'Furie.server',
                'Furie.MINIHandler'],
)

core.setup(**kw)