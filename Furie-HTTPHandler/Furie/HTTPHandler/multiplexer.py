from __future__ import absolute_import
# Furie-internal
import Furie.DB
import Furie.server.funcs
import Furie.HTTPHandler.funcs

class Multiplexer:
    def __init__(self, req, reqinfo, proc):
        self.req = req
        self.reqinfo = reqinfo
        self.__proc = proc

        self.handle_request()

    def handle_request(self):
        self.rfile = self.req.makefile('rb', -1)

        self.requestline = self.rfile.readline()

        if not self.requestline or not self.parse_requestline():
            self.rfile.close()
            self.req.close()
            return

        if not self.parse_request():
            self.rfile.close()
            self.req.close()
            return

        self.rfile.close()

        self.reqinfo.update({
            'req_command': self.req_command,
            'req_path':    self.req_path,
            'req_version': self.req_version,
            'req_headers': self.req_headers,
        })

        Furie.server.funcs.finish_request(self.req, self.reqinfo, 'test1', self.__proc)

    def parse_requestline(self):
        if self.requestline[-2:] == '\r\n':
            self.requestline = self.requestline[:-2]
        elif self.requestline[-1:] == '\n':
            self.requestline = self.requestline[:-1]
        else:
            return False
        return True

    def parse_request(self):
        self.req_command = None
        self.req_path = None
        self.req_version = 'HTTP/0.9'

        components = self.requestline.split()

        if len(components) == 3:
            [command, path, version] = components
            if version != 'HTTP/0.9' and version != 'HTTP/1.0' and version != 'HTTP/1.1':
                self.send_error(400, 'Bad request version (%r)' % version)
                return False
        elif len(components) == 2:
            [command, path] = components
            version = 'HTTP/0.9'
        elif not components:
            return False
        else:
            self.send_error(400, 'Bad request syntax (%r)' % self.requestline)
            return False

        self.req_command, self.req_path, self.req_version = command, path, version

        if self.req_version == 'HTTP/0.9' and self.req_command != 'GET':
            self.send_error(400, 'Bad HTTP/0.9 request type (%r)' % self.req_command)
            return False

        self.req_headers = Furie.HTTPHandler.funcs.read_headers(self.rfile)

        return True

    def find_vhost(self):
        host = self.req_headers.get('HOST')
        if not host:
            self.send_error(400, 'Bad request syntax (no HOST header)')
            return False

        return host