from __future__ import absolute_import
# From site-packages
from sqlobject import *

# Main database definition

class Conf(SQLObject):
    name  = StringCol(length=255, unique=True)
    value = StringCol(length=255)

def ConfVal(confname):
    val = Conf.selectBy(name=confname)
    return val.getOne().value

class ListenSocks(SQLObject):
    type  = StringCol(length=4)
    addr  = StringCol(length=255)
    port  = IntCol()
    queue = IntCol(default=200)

class OnlineProcs(SQLObject):
    pid    = IntCol(unique=True)
    ppid   = IntCol()
    name   = StringCol(length=255)
    type   = StringCol(length=50)
    served = IntCol(default=0)

class Users(SQLObject):
    user = StringCol(length=255, unique=True)
    uid  = IntCol()
    gid  = IntCol()
    home = StringCol(length=255)
    minprocs   = IntCol()
    maxprocs   = IntCol()
    tpool_size = IntCol()

class SupervisorToDo(SQLObject):
    action = StringCol(length=50)
    data   = StringCol(length=255)

def Setup():
    Conf.createTable(ifNotExists=True)
    ListenSocks.createTable(ifNotExists=True)
    OnlineProcs.createTable(ifNotExists=True)
    Users.createTable(ifNotExists=True)
    SupervisorToDo.createTable(ifNotExists=True)