#!/usr/bin/env python

from distutils import core
from distutils.extension import Extension

kw = dict(
    name = 'passfdmsg',
    version = '1.1',
    description = 'A Python module to pass fds and messages. Sendfile() support and others.',
    author = 'Luca Longinotti',
    author_email = 'chtekk@longitekk.com',
    url = 'http://chtekk.longitekk.com/',
    license = 'GPL-2',
    ext_modules = [Extension(name='passfdmsg', sources=['passfdmsg.c'])],
)

core.setup(**kw)