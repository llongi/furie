from __future__ import absolute_import
# Furie-internal
import Furie.server.funcs

class Multiplexer:
    def __init__(self, req, reqinfo, proc):
        self.req = req
        self.reqinfo = reqinfo
        self.__proc = proc

        self.handle_request()

    def handle_request(self):
        rfile = self.req.makefile('rb', -1)
        firstline = rfile.readline()
        rfile.close()

        Furie.server.funcs.finish_request(self.req, self.reqinfo, 'test1', self.__proc)