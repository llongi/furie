#!/usr/bin/env python

from distutils import core

kw = dict(
    name = 'cgiws',
    version = '1.1',
    description = 'Implement the Webserver part of Webserver<->CGI communication. ' \
                  'Supports CGI, FastCGI and SCGI. ' \
                  'Also support spawning of CGI and FastCGI processes.',
    author = 'Luca Longinotti',
    author_email = 'chtekk@longitekk.com',
    url = 'http://chtekk.longitekk.com/',
    license = 'GPL-2',
    packages = ['cgiws'],
)

core.setup(**kw)