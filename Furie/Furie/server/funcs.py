from __future__ import absolute_import
# Furie-internal
import Furie.DB
# From site-packages
import passfdmsg
# From built-ins
import os
import signal
import logging
import cPickle

# Server-wide handling (initial values, will later become callables)
multiplexer_handler = None
processor_handler = None
error_handler = None
busyerror_handler = None

busy_counter = {}

def finish_request(req, reqinfo, user, proc):
    # Finish up a request by passing it to the next stage;
    # if next stage too busy, signal this and show busy error

    # First lets find out where we can send the request,
    # based upon the user it shall go to
    if user:
        keyList = filter(lambda str: str.startswith('pro_%s_' % user), proc['wfd'].keys())
        fdList = map(lambda key: proc['wfd'][key], keyList)
        del keyList
    else:
        fdList = proc['wfd'].values()

    # Then lets check which destination is ready
    send_fd = None

    for fd in fdList*200:
        try:
            os.read(fd, 1)
        except OSError:
            continue

        send_fd = fd
        break

    # And now lets send the request away, if possible,
    # else lets signal the busy error
    global busy_counter
    if user not in busy_counter:
        busy_counter[user] = 0

    if send_fd:
        busy_counter[user] = 0
        passfdmsg.sendfdmsg(send_fd,
                            req.fileno(),
                            cPickle.dumps(reqinfo, cPickle.HIGHEST_PROTOCOL))
        req.close()
    else:
        busy_counter[user] += 1
        busyerror_handler(req, reqinfo)

    # If the busy_counter is high, lets tell the Supervisor
    # we want more processes to do our work
    if busy_counter[user] > 20:
        busy_counter[user] = 0
        logging.debug('high busy_counter in %s%s' % (proc['type'], (proc['type'] == 'acceptor' and [''] or [' for %s' % user])[0]))
        Furie.DB.main.SupervisorToDo(action='add_%s' % (proc['type'] == 'acceptor' and ['multiplexer'] or ['processor'])[0], data=user)

def change_user(uid, gid, euid=False):
    # TODO: validate uid/gid, do root checks, etc.
    os.setgid(gid)
    if not euid:
        os.setuid(uid)
    else:
        os.seteuid(uid)

def change_proctitle(proctitle):
    # Change the process title to something else
    try:
        passfdmsg.setproctitle(proctitle, 1)
    except (ValueError, OSError):
        logging.warn('failed to change process name')
    except NotImplementedError:
        pass

def importHandler(module, name):
    # Import a named object from a module
    try:
        mod = __import__('Furie.%s' % module, globals(), locals(), [name])
        return getattr(mod, name)
    except (ImportError, AttributeError):
        return None

def daemonize(umask=None):
    # Fork once to background.
    pid = os.fork()
    if pid != 0: # Original parent.
        os._exit(os.EX_OK)

    # First child. Create a new session.
    os.setsid()

    # Fork a second child to ensure that the daemon never acquires
    # a control terminal again.
    pid = os.fork()
    if pid != 0: # Original child.
        os._exit(os.EX_OK)

    # Second child. Create a new session.
    os.setsid()

    # Change umask, if a value is given.
    if umask:
        os.umask(umask)

    # Go to a neutral corner (the primary file system, so that
    # the daemon doesn't prevent some other file system from being
    # unmounted).
    os.chdir('/')

    # Find out what the maximum number of file descriptors is
    try:
        maxfd = os.sysconf('SC_OPEN_MAX')
    except:
        maxfd = 1024

     # Close all file descriptors.
    for fd in range(0, maxfd):
        # Only close TTYs.
        if os.isatty(fd):
            try:
                os.close(fd)
            except OSError:
                pass

    # Redirect standard input, output and error to something safe.
    # os.open() is guaranteed to return the lowest available file
    # descriptor (0, or standard input). Then, we can dup that
    # descriptor for standard output and standard error.
    os.open(os.devnull, os.O_RDWR)
    os.dup2(0, 1)
    os.dup2(0, 2)

def write_pidfile(pidfile):
    # Write the pid of the process to the specified pidfile.
    pidf = open(pidfile, 'w')
    pidf.write('%d\n' % os.getpid())
    pidf.close()

def handler_sigchld(sig, frame):
    while True:
        try:
            pid = os.waitpid(-1, os.WNOHANG)[0]
        except OSError:
            break
        if pid > 0:
            logging.warn('child with pid %d killed' % pid)
            proc = Furie.DB.main.OnlineProcs.selectBy(pid=pid).getOne()
            proc.delete(int(proc.id))
        else:
            break
    signal.signal(signal.SIGCHLD, handler_sigchld)

def killall_children(ppid):
    processList = Furie.DB.main.OnlineProcs.selectBy(ppid=ppid)
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    for proc in processList:
        os.kill(int(proc.pid), signal.SIGTERM)
    for proc in processList:
        try:
            pid = os.waitpid(int(proc.pid), 0)[0]
            logging.info('child with pid %d shut down' % pid)
        except OSError:
            pass
        proc.delete(int(proc.id))