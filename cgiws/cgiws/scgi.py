# From built-ins
import socket

class Request(object):
    # Init: connect to the SCGI socket
    def __init__(self, sockinfo):
        if sockinfo[0] == 'SOCK':
            socktype = socket.AF_UNIX
        elif sockinfo[0] == 'IPV4':
            socktype = socket.AF_INET
        elif sockinfo[0] == 'IPV6':
            socktype = socket.AF_INET6
        else:
            raise ValueError, 'invalid socket info'

        self.__sock = socket.socket(socktype, socket.SOCK_STREAM)
        self.__sock.connect(sockinfo[1])

        # Completion trackers
        self.__completed_scgi_headers  = False
        self.__completed_scgi_response = False

        # Read-only results from response
        self.__stdout = None

    # Communication methods, operate the SCGI request
    def headers(self, headers):
        '''Send the SCGI request headers.
        This method *must* be called first!'''
        if self.__completed_scgi_headers:
            raise IOError

        hdrstr = ''

        clen = headers.pop('CONTENT_LENGTH', '0')
        hdrstr += 'CONTENT_LENGTH\0%s\0' % clen
        scgi = headers.pop('SCGI', '1')
        hdrstr += 'SCGI\0%s\0' % scgi

        for i in headers.keys():
            hdrstr += '%s\0%s\0' % (i, headers[i])

        self.__sock.sendall('%d:%s,' % (len(hdrstr), hdrstr))

        self.__completed_scgi_headers = True

    def body(self, body):
        '''Send the SCGI request body.
        Must be called after sending the headers.
        This can be called multiple times.'''
        if not self.__completed_scgi_headers:
            raise IOError

        self.__sock.sendall(body)

    def response(self, close=True):
        '''Read the response from the SCGI app.
        Will close the socket if close=True (default).'''
        if not self.__completed_scgi_headers or self.__completed_scgi_response:
            raise IOError

        stdout = ''

        while True:
            data = self.__sock.recv(4096)
            if not data:
                break
            stdout += data

        if close:
            self.__sock.close()

        self.__stdout = stdout

        self.__completed_scgi_response = True

    # Read-only attributes (results from response)
    def __get_stdout(self): return self.__stdout
    def __set_stdout(self, param): raise AttributeError, 'read-only attribute'
    stdout = property(__get_stdout, __set_stdout)