from __future__ import absolute_import
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
        req.sendall('HTTP/1.0 503 Service Unavailable\r\n' \
                    'Content-Type: text/plain\r\n' \
                    'Content-Length: 44\r\n' \
                    'Connection: close\r\n' \
                    '\r\n' \
                    'The service is unavailable due to high load.')
        req.close()