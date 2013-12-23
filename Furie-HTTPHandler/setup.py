#!/usr/bin/env python

from distutils import core

kw = dict(
    name = 'Furie-HTTPHandler',
    version = '0.5',
    description = 'HTTP/1.1-compliant handler module for Furie.',
    author = 'Luca Longinotti',
    author_email = 'chtekk@longitekk.com',
    url = 'http://chtekk.longitekk.com/',
    license = 'GPL-2',
    packages = ['Furie.HTTPHandler'],
    py_modules = ['Furie.db.HTTP'],
)

core.setup(**kw)