# From built-ins
import os
import signal
import socket

class CGI(object):
    # CGI init: start process
    def __init__(self, bin_path, cwd_path='/', env={}, stdin=None, stdout=None, stderr=None):
        self.verify_path(bin_path, is_dir=False)
        self.verify_path(cwd_path, is_dir=True)
        self.verify_env(env)
        stdin  = self.verify_redir(stdin)
        stdout = self.verify_redir(stdout)
        stderr = self.verify_redir(stderr)

        self.pid = os.fork()
        if self.pid == 0: # Child
            if stdin:
                os.dup2(stdin, 0)
            else:
                os.close(0)

            if stdout:
                os.dup2(stdout, 1)
            else:
                os.close(1)

            if stderr:
                os.dup2(stderr, 2)
            else:
                os.close(2)

            try:
                maxfd = os.sysconf('SC_OPEN_MAX')
            except:
                maxfd = 1024

            for fd in range(3, maxfd):
                try:
                    os.close(fd)
                except OSError:
                    pass

            os.chdir(cwd_path)

            if env:
                os.execve(bin_path, [bin_path], env)
            else:
                os.execv(bin_path, [bin_path])

            os._exit(os.EX_OK)

    # Termination methods
    def term(self):
        os.kill(self.pid, signal.SIGTERM)
        os.waitpid(self.pid, 0)

    def kill(self):
        os.kill(self.pid, signal.SIGKILL)
        os.waitpid(self.pid, 0)

    # Internal methods
    def verify_path(self, path, is_dir=True):
        if os.path.isabs(path) and os.access(path, os.R_OK|os.X_OK):
            if is_dir and os.path.isdir(path):
                return
            elif not is_dir and os.path.isfile(path):
                return

        raise ValueError, 'invalid path, not absolute and/or wrong permissions and/or wrong type'

    def verify_env(self, env):
        if isinstance(env, dict):
            return

        raise ValueError, 'invalid env, must be dict instance'

    def verify_redir(self, redir):
        if isinstance(redir, type(None)):
            return None
        else:
            try:
                return redir.fileno()
            except AttributeError:
                raise ValueError, 'invalid redir, must have fileno() method or be None'

class FCGI(CGI):
    # FCGI init: setup socket and start permanent process
    def __init__(self, bin_path, sockinfo, cwd_path='/', env={}, stdout=None, stderr=None):
        self.socket_setup(sockinfo)
        CGI.__init__(self, bin_path, cwd_path, env, self.sock, stdout, stderr)
        self.sock.close()

    # Termination methods
    def term(self):
        CGI.term(self)
        self.socket_cleanup()

    def kill(self):
        CGI.kill(self)
        self.socket_cleanup()

    # Internal methods
    def socket_setup(self, sockinfo):
        if sockinfo[0] == 'SOCK':
            socktype = socket.AF_UNIX
        elif sockinfo[0] == 'IPV4':
            socktype = socket.AF_INET
        elif sockinfo[0] == 'IPV6':
            socktype = socket.AF_INET6
        else:
            raise ValueError, 'invalid socket info'

        self.sock = socket.socket(socktype, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(sockinfo[1])
        self.sock.listen(100)

        self.sockinfo = sockinfo

    def socket_cleanup(self):
        if self.sockinfo[0] == 'SOCK':
            try:
                os.remove(self.sockinfo[1])
            except OSError:
                pass