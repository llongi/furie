from __future__ import absolute_import
# Furie-internal
import Furie.HTTPHandler.httpcodes
# From built-ins
import logging

class ErrorHandler:
    def __init__(self, req, reqinfo):
        logging.debug(
            'exception happened during processing of request from %s' % reqinfo['client_addr'],
            exc_info=True
        )
        req.close()

class BusyErrorHandler:
    def __init__(self, req, reqinfo):
        logging.debug('rejected request from %s, server too busy' % reqinfo['client_addr'])
        # Some clients seem to go crazy if the connection is written to while nothing was read
        try:
            req.setblocking(0)
            req.recv(256)
        except:
            pass
        req.sendall('HTTP/1.0 %d %s\r\n' \
                    'Content-Type: text/plain\r\n' \
                    'Content-Length: %d\r\n' \
                    'Connection: close\r\n' \
                    '\r\n' \
                    '%s' \
                    % (503,
                       Furie.HTTPHandler.httpcodes.responses[503][0],
                       len(Furie.HTTPHandler.httpcodes.responses[503][1]),
                       Furie.HTTPHandler.httpcodes.responses[503][1]))
        req.close()