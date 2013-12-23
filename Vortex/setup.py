#!/usr/bin/env python

from distutils import core

kw = dict(
    name = 'Vortex',
    version = '0.9',
    description = 'Very simple thread-pool implementation.',
    author = 'Luca Longinotti',
    author_email = 'chtekk@longitekk.com',
    url = 'http://chtekk.longitekk.com/',
    license = 'GPL-2',
    packages = ['Vortex'],
)

core.setup(**kw)