from __future__ import absolute_import
# Simple shortcut to be able to directly call Furie.ServerInit(params).
# Also offers a FromConfig shortcut to parse a cfg file for the values.
import Furie.Server

def ServerInit(dbdsn, handler):
    Furie.Server.Server(dbdsn, handler)

def ServerInitFromConfig(cfgfile):
    import ConfigParser
    cfgparser = ConfigParser.SafeConfigParser()
    cfgparser.read(cfgfile)
    dbdsn = cfgparser.get('Furie', 'dbdsn')
    handler = cfgparser.get('Furie', 'handler')
    Furie.Server.Server(dbdsn, handler)