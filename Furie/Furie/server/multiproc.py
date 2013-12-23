from __future__ import absolute_import
# Furie-internal
import Furie.DB
import Furie.server.funcs
# From site-packages
import passfdmsg
import Vortex
# From built-ins
import os
import socket
import signal
import logging
import Queue
import cPickle

class MultiProc:
    def __init__(self, proc, dbdsn):
        # Change uid/gid and process title, set process name for logging
        logging._handlerList[0].formatter._fmt = '%(asctime)s %(levelname)-8s (' + proc['name'] + '): %(message)s'
        Furie.server.funcs.change_proctitle(proc['name'])
        Furie.server.funcs.change_user(proc['uid'], proc['gid'])

        # Define the basic attributes
        self.__proc = proc
        Furie.DB.Init(dbdsn)
        if self.__proc['type'] == 'multiplexer':
            self.handler = Furie.server.funcs.multiplexer_handler
        elif self.__proc['type'] == 'processor':
            self.handler = Furie.server.funcs.processor_handler
        else:
            self.multiproc_shutdown()
        self.pool = None

    def run(self):
        if self.__proc['tpool_size'] > 0:
            self.pool = Vortex.Vortex(self.__proc['tpool_size'], self.__proc['tpool_size']*2)

        self.multiproc_forever()

    def multiproc_forever(self):
        self.suicide = False

        def handler_sigterm(sig, frame):
            self.suicide = True

        signal.signal(signal.SIGTERM, handler_sigterm)

        signal.signal(signal.SIGCHLD, Furie.server.funcs.handler_sigchld)

        def handler_sigalrm(sig, frame):
            pass

        signal.signal(signal.SIGALRM, handler_sigalrm)

        while not self.suicide:
            os.write(self.__proc['rfd'], 'R')
            self.handle_multiproc()
        else:
            signal.alarm(2)
            self.handle_multiproc()
            signal.alarm(0)
            self.multiproc_shutdown()

    def multiproc_shutdown(self):
        if self.pool:
            self.pool.shutdown()
        Furie.server.funcs.killall_children(os.getpid())
        logging.info('shutting down')
        logging.shutdown()
        os._exit(os.EX_OK)

    def handle_multiproc(self):
        try:
            (fd, msg) = passfdmsg.recvfdmsg(self.__proc['rfd'])
            reqinfo = cPickle.loads(msg)
            req = socket._socketobject(
                _sock=socket.fromfd(fd, reqinfo['sock_family'], reqinfo['sock_type'])
            )
            os.close(fd)
            req.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        except:
            return

        try:
            if self.pool:
                self.pool.addJob(Vortex.Job(self.handler, [req, reqinfo, self.__proc]))
            else:
                self.handler(req, reqinfo, self.__proc)
        except Queue.Full:
            Furie.server.funcs.busyerror_handler(req, reqinfo)
        except:
            Furie.server.funcs.error_handler(req, reqinfo)