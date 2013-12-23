from __future__ import absolute_import
# From site-packages
from sqlobject import *

# HTTP database definition

class Log(SQLObject):
    system       = StringCol(length=50)
    time         = DateTimeCol(default=DateTimeCol.now)
    remote_host  = StringCol(length=255)
    remote_auth  = StringCol(length=255)
    user         = StringCol(length=255)
    vhost        = StringCol(length=255)
    user_agent   = StringCol(length=255)
    referer      = StringCol(length=255)
    http_method  = StringCol(length=10)
    http_request = StringCol(length=255)
    http_version = StringCol(length=10)
    resp_code    = IntCol()
    resp_content = StringCol(length=80)
    in_bytes     = IntCol()
    out_bytes    = IntCol()

class VHosts(SQLObject):
    host = StringCol(length=255, unique=True)
    path = StringCol(length=255)
    user = StringCol(length=255)

def Setup():
    Log.createTable(ifNotExists=True)
    VHosts.createTable(ifNotExists=True)