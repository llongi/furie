from __future__ import absolute_import
# Furie-internal
import Furie.DB
import Furie.server.funcs
# From site-packages
try:
    import select26 as select
except ImportError:
    import select
# From built-ins
import os
import socket
import signal
import logging

class Acceptor:
    def __init__(self, proc, dbdsn):
        # Change euid/gid and process title, set process name for logging
        logging._handlerList[0].formatter._fmt = '%(asctime)s %(levelname)-8s (' + proc['name'] + '): %(message)s'
        Furie.server.funcs.change_proctitle(proc['name'])
        Furie.server.funcs.change_user(proc['uid'], proc['gid'], euid=True)

        # Define the basic attributes
        self.__proc = proc
        Furie.DB.Init(dbdsn)
        self.Poll = None
        self.online_socks = {}

    def run(self):
        for sock in Furie.DB.main.ListenSocks.select():
            sock_type = str(sock.type)
            if sock_type == 'SOCK':
                sock_type = socket.AF_UNIX
                addr = str(sock.addr)
                port = -1
            elif sock_type == 'IPV4':
                sock_type = socket.AF_INET
                addr = str(sock.addr)
                port = int(sock.port)
            elif sock_type == 'IPV6' and socket.has_ipv6:
                sock_type = socket.AF_INET6
                addr = str(sock.addr)
                port = int(sock.port)
            else:
                logging.critical('invalid socket type: %s' % sock_type)
                self.acceptor_shutdown()

            new_sock = socket.socket(sock_type, socket.SOCK_STREAM)

            try:
                new_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                new_sock.setblocking(0)
                if port < 0:
                    new_sock.bind(addr)
                elif port < 1024:
                    os.setuid(0)
                    new_sock.bind((addr, port))
                    os.seteuid(self.__proc['uid'])
                else:
                    new_sock.bind((addr, port))
                new_sock.listen(int(sock.queue))
            except socket.error:
                del new_sock
                logging.critical('failed to acquire listening socket at %s:%d' % (addr, port))
                self.acceptor_shutdown()

            self.online_socks[new_sock.fileno()] = new_sock
            del new_sock

        try:
            self.Poll = select.epoll()
            logging.info('using epoll interface')
        except AttributeError:
            self.Poll = select.poll()
            logging.info('using poll interface')

        for fd in self.online_socks:
            self.Poll.register(fd, select.POLLIN)

        self.accept_forever()

    def accept_forever(self):
        self.suicide = False

        def handler_sigterm(sig, frame):
            self.suicide = True

        signal.signal(signal.SIGTERM, handler_sigterm)

        while not self.suicide:
            self.handle_accept()
        else:
            self.acceptor_shutdown()

    def acceptor_shutdown(self):
        for fd in self.online_socks:
            if self.Poll:
                self.Poll.unregister(fd)
            self.online_socks[fd].close()
        if self.Poll and hasattr(self.Poll, 'close'):
            self.Poll.close()
        logging.info('shutting down')
        logging.shutdown()
        os._exit(os.EX_OK)

    def handle_accept(self):
        try:
            fdList = self.Poll.poll()
        except (select.error, IOError):
            return

        for fd in fdList:
            try:
                (req, client_addr) = self.online_socks[fd[0]].accept()
            except socket.error:
                continue

            reqinfo = {
                'sock_family': req.family,
                'sock_type':   req.type,
                'client_addr': client_addr[0],
                'client_port': client_addr[1],
            }

            Furie.server.funcs.finish_request(req, reqinfo, None, self.__proc)