# From built-ins
import socket
import struct

# Listening socket
FCGI_LISTENSOCK_FILENO = 0

# Lengths
FCGI_MAX_LENGTH = 65000
FCGI_HEADER_LEN = 8

# Version number
FCGI_VERSION_1 = 1

# Record types
FCGI_BEGIN_REQUEST = 1
FCGI_ABORT_REQUEST = 2
FCGI_END_REQUEST = 3
FCGI_PARAMS = 4
FCGI_STDIN = 5
FCGI_STDOUT = 6
FCGI_STDERR = 7
FCGI_DATA = 8
FCGI_GET_VALUES = 9
FCGI_GET_VALUES_RESULT = 10
FCGI_UNKNOWN_TYPE = 11
FCGI_MAXTYPE = FCGI_UNKNOWN_TYPE

# Masks for flags component of FCGI_BEGIN_REQUEST
FCGI_KEEP_CONN = 1

# Values for role component of FCGI_BEGIN_REQUEST
FCGI_RESPONDER = 1
FCGI_AUTHORIZER = 2
FCGI_FILTER = 3

# Values for protocolStatus component of FCGI_END_REQUEST
FCGI_REQUEST_COMPLETE = 0 # Request completed ok
FCGI_CANT_MPX_CONN = 1    # This app cannot multiplex
FCGI_OVERLOADED = 2       # Too busy
FCGI_UNKNOWN_ROLE = 3     # Role value not known

class Request(object):
    # Init: define request ID and connect to the FastCGI socket
    def __init__(self, sockinfo, reqid):
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

        self.req_id = reqid

        # Completion trackers
        self.__completed_fcgi_begin    = False
        self.__completed_fcgi_params   = False
        self.__completed_fcgi_stdin    = False
        self.__completed_fcgi_data     = False
        self.__completed_fcgi_stdout   = False
        self.__completed_fcgi_stderr   = False
        self.__completed_fcgi_response = False

        # Read-only results from response
        self.__stdout = None
        self.__stderr = None
        self.__appStatus  = None
        self.__protStatus = None

    # Communication methods, operate the FastCGI request
    def begin(self, role, flags=0):
        '''Begin the FastCGI request by telling the app we're
        talking to what its role is and eventual special flags.
        This method *must* be called first!'''
        content = struct.pack('!HB5x', role, flags)
        self.__write(FCGI_BEGIN_REQUEST, content)
        self.__completed_fcgi_begin = True

    def params(self, data):
        '''Send FastCGI PARAMS over to the app.
        Accepts a dict of name: value pairs.
        Call with an empty dict ({}) to terminate.'''
        if not self.__completed_fcgi_begin or self.__completed_fcgi_params:
            raise IOError

        if not data:
            self.__completed_fcgi_params = True

        content = ''
        for i in data.keys():
            content += self.__write_pair(i, data[i])

        self.__write(FCGI_PARAMS, content)

    def stdin(self, content):
        '''Send FastCGI STDIN over to the app.
        Accepts a string representing the content.
        Call with an empty string ('') to terminate.'''
        if not self.__completed_fcgi_begin or self.__completed_fcgi_stdin:
            raise IOError

        if not content:
            self.__completed_fcgi_stdin = True

        self.__write(FCGI_STDIN, content)

    def data(self, content):
        '''Send FastCGI DATA over to the app.
        Accepts a string representing the content.
        Call with an empty string ('') to terminate.'''
        if not self.__completed_fcgi_begin or self.__completed_fcgi_data:
            raise IOError

        if not content:
            self.__completed_fcgi_data = True

        self.__write(FCGI_DATA, content)

    def response(self, close=True):
        '''Read the response from the FastCGI app.
        Will return when the app sends FCGI_END_REQUEST,
        thus signaling the completion of the request on its part.
        Will close the socket if close=True (default).'''
        if not self.__completed_fcgi_begin or self.__completed_fcgi_response:
            raise IOError

        # FCGI_PARAMS needs to have been completed before we can read
        if not self.__completed_fcgi_params:
            raise IOError

        stdout = ''
        stderr = ''
        appStatus = 0
        protStatus = 0
        received_fcgi_end_request = False

        while True:
            data = self.__read()

            if not data and not received_fcgi_end_request:
                # We got EOF without ever getting a FCGI_END_REQUEST
                # Abnormal termination, raise exception
                raise IOError, 'got EOF without FCGI_END_REQUEST'

            elif not data and received_fcgi_end_request:
                # We got EOF and FCGI_END_REQUEST
                # This is normal termination, so let's exit
                break

            elif data and not received_fcgi_end_request:
                # We got valid data and no FCGI_END_REQUEST yet
                # Let's process this normally
                (rec_type, content) = data

                if rec_type == FCGI_END_REQUEST:
                    (appStatus, protStatus) = struct.unpack('!IB3x', content)
                    received_fcgi_end_request = True

                elif rec_type == FCGI_STDOUT:
                    # We check for stream termination (empty content str)
                    # After a stream was terminated, we can't reuse it!
                    if self.__completed_fcgi_stdout:
                        raise IOError, 'FCGI_STDOUT stream already terminated'

                    if not content:
                        self.__completed_fcgi_stdout = True
                    else:
                        stdout += content

                elif rec_type == FCGI_STDERR:
                    # We check for stream termination (empty content str)
                    # After a stream was terminated, we can't reuse it!
                    if self.__completed_fcgi_stderr:
                        raise IOError, 'FCGI_STDERR stream already terminated'

                    if not content:
                        self.__completed_fcgi_stderr = True
                    else:
                        stderr += content

                else:
                    raise ValueError, 'invalid FastCGI record type'

            elif data and received_fcgi_end_request:
                # There is valid data still, but we already
                # got FCGI_END_REQUEST, this isn't normal
                # Abnormal termination, raise exception
                raise IOError, 'got data after FCGI_END_REQUEST'

        if close:
            self.__sock.close()

        self.__stdout = stdout
        self.__stderr = stderr
        self.__appStatus  = appStatus
        self.__protStatus = protStatus

        self.__completed_fcgi_response = True

    # Read-only attributes (results from response)
    def __get_stdout(self): return self.__stdout
    def __set_stdout(self, param): raise AttributeError, 'read-only attribute'
    stdout = property(__get_stdout, __set_stdout)

    def __get_stderr(self): return self.__stderr
    def __set_stderr(self, param): raise AttributeError, 'read-only attribute'
    stderr = property(__get_stderr, __set_stderr)

    def __get_appStatus(self): return self.__appStatus
    def __set_appStatus(self, param): raise AttributeError, 'read-only attribute'
    appStatus = property(__get_appStatus, __set_appStatus)

    def __get_protStatus(self): return self.__protStatus
    def __set_protStatus(self, param): raise AttributeError, 'read-only attribute'
    protStatus = property(__get_protStatus, __set_protStatus)

    # Internal methods, low-level protocol read/write
    def __read(self):
        data = self.__sock.recv(FCGI_HEADER_LEN)
        if not data:
            # No data received. This means EOF.
            return None

        (version, rec_type, req_id,
         contentLength, paddingLength) = struct.unpack('!BBHHBx', data)

        if version != FCGI_VERSION_1:
            raise IOError, 'invalid FastCGI version'

        if rec_type not in [FCGI_STDOUT, FCGI_STDERR, FCGI_END_REQUEST]:
            raise IOError, 'invalid FastCGI record type'

        if req_id != self.req_id:
            raise IOError, 'invalid FastCGI request ID'

        content = ''
        while len(content) < contentLength:
            data = self.__sock.recv(contentLength - len(content))
            content += data
        if paddingLength != 0:
            self.__sock.recv(paddingLength)

        return (rec_type, content)

    def __write(self, rec_type, content):
        termination = False
        if not content:
            termination = True

        while content or termination:
            termination = False

            ctosend = content[:FCGI_MAX_LENGTH]
            content = content[FCGI_MAX_LENGTH:]

            # Align to 8-byte boundary
            clen = len(ctosend)
            padlen = ((clen + 7) & 0xfff8) - clen

            hdr = struct.pack('!BBHHBx', FCGI_VERSION_1,
                              rec_type, self.req_id,
                              clen, padlen)

            self.__sock.sendall(hdr + ctosend + padlen*'\x00')

    def __write_pair(self, name, value):
        namelen = len(name)
        if namelen < 128:
            data = struct.pack('!B', namelen)
        else:
            # 4-byte name length
            data = struct.pack('!I', namelen | 0x80000000L)

        valuelen = len(value)
        if valuelen < 128:
            data += struct.pack('!B', valuelen)
        else:
            # 4-byte value length
            data += struct.pack('!I', valuelen | 0x80000000L)

        return data + name + value