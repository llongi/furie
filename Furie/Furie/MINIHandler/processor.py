from __future__ import absolute_import
# Furie-internal
from Furie.MINIHandler import metadata as MINIHandler_MetaData
from Furie.db import metadata as DB_MetaData
from Furie.server import metadata as Server_MetaData

class Processor:
    def __init__(self, req, reqinfo, proc):
        self.req = req
        self.reqinfo = reqinfo
        self.__proc = proc

        self.handle_request()

    def handle_request(self):
        msg = 'This is %s/%s running on %s/%s, using %s/%s.' % (MINIHandler_MetaData['name'],
                                                                MINIHandler_MetaData['version'],
                                                                Server_MetaData['name'],
                                                                Server_MetaData['version'],
                                                                DB_MetaData['name'],
                                                                DB_MetaData['version'])
        self.req.sendall('HTTP/1.0 200 OK\r\n' \
                         'Content-Type: text/plain\r\n' \
                         'Content-Length: %d\r\n' \
                         'Connection: close\r\n' \
                         '\r\n' \
                         '%s' \
                          % (len(msg), msg))
        self.req.close()