from __future__ import absolute_import
# Furie-internal
import Furie.db.main as main
# From site-packages
from sqlobject import connectionForURI, sqlhub

# General convenience function

def Init(dsn):
    if sqlhub and hasattr(sqlhub, 'processConnection'):
        sqlhub.processConnection._pool = None
        del sqlhub.processConnection
    main.dbconnection.TheURIOpener.cachedURIs = {}
    sqlhub.processConnection = connectionForURI(dsn)