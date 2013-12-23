from __future__ import absolute_import
# Furie-internal
import Furie.DB
import Furie.server.funcs
import Furie.server.acceptor
import Furie.server.multiproc
# From site-packages
import passfdmsg
# From built-ins
import os
import fcntl
import signal
import logging
import time
import copy

# Supported actions
SUPERVISOR_ACTIONS = [('add_socket',      'remove_socket'),
                      ('add_multiplexer', 'remove_multiplexer'),
                      ('add_processor',   'remove_processor')]

SUPERVISOR_ACTIONS_LIST = []
for (x, y) in SUPERVISOR_ACTIONS:
    SUPERVISOR_ACTIONS_LIST.append(x)
    SUPERVISOR_ACTIONS_LIST.append(y)

class Supervisor:
    def __init__(self, dbdsn):
        # Define the basic attributes
        Furie.DB.Init(dbdsn)
        self.dbdsn = dbdsn
        self.processes = {}
        self.acceptor_wfd = []
        self.acceptor_wfd_named = {}
        self.multiplexer_rfd = []
        self.multiplexer_wfd = []
        self.multiplexer_wfd_named = {}
        self.processor_rfd = []

    def run(self):
        # Prepare all the data and the needed communication fds for the processes,
        # and correctly assign them

        processorList = Furie.DB.main.Users.select()

        for proc in processorList:
            for x in range(1, int(proc.minprocs)+1):
                name = 'pro_%s_%d' % (str(proc.user), x)
                self.processes.update({name: {
                    'name': name,
                    'type': 'processor',
                    'uid':  int(proc.uid),
                    'gid':  int(proc.gid),
                    'home': str(proc.home),
                    'minprocs': int(proc.minprocs),
                    'maxprocs': int(proc.maxprocs),
                    'tpool_size': int(proc.tpool_size),
                    'rfd':  None,
                }})
                rfd, wfd = passfdmsg.socketpair()
                self.processes[name]['rfd'] = rfd
                self.processor_rfd.append(rfd)
                self.multiplexer_wfd_named[name] = wfd
                self.multiplexer_wfd.append(wfd)

        multiplexerList = range(1, int(Furie.DB.main.ConfVal('multiplexers_minprocs'))+1)

        for mpx in multiplexerList:
            name = 'mpx_%d' % mpx
            self.processes.update({name: {
                'name': name,
                'type': 'multiplexer',
                'uid':  int(Furie.DB.main.ConfVal('multiplexers_uid')),
                'gid':  int(Furie.DB.main.ConfVal('multiplexers_gid')),
                'home': str(Furie.DB.main.ConfVal('multiplexers_home')),
                'minprocs': int(Furie.DB.main.ConfVal('multiplexers_minprocs')),
                'maxprocs': int(Furie.DB.main.ConfVal('multiplexers_maxprocs')),
                'tpool_size': int(Furie.DB.main.ConfVal('multiplexers_tpool_size')),
                'rfd':  None,
                'wfd':  self.multiplexer_wfd_named,
            }})
            rfd, wfd = passfdmsg.socketpair()
            self.processes[name]['rfd'] = rfd
            self.multiplexer_rfd.append(rfd)
            self.acceptor_wfd_named[name] = wfd
            self.acceptor_wfd.append(wfd)

        name = 'accept'
        self.processes.update({name: {
            'name': name,
            'type': 'acceptor',
            'uid':  int(Furie.DB.main.ConfVal('acceptor_uid')),
            'gid':  int(Furie.DB.main.ConfVal('acceptor_gid')),
            'home': str(Furie.DB.main.ConfVal('acceptor_home')),
            'wfd':  self.acceptor_wfd_named,
        }})

        # Make all wfds non-blocking

        for fd in (self.acceptor_wfd + self.multiplexer_wfd):
            fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)

        # Start the processes (removing the not needed fds from them)

        for proc in processorList:
            for x in range(1, int(proc.minprocs)+1):
                self.spawn_child('pro_%s_%d' % (str(proc.user), x),
                                 (self.acceptor_wfd + self.multiplexer_rfd + self.multiplexer_wfd + self.processor_rfd))

        for mpx in multiplexerList:
            self.spawn_child('mpx_%d' % mpx,
                             (self.acceptor_wfd + self.multiplexer_rfd + self.processor_rfd))

        self.spawn_child('accept',
                         (self.multiplexer_rfd + self.multiplexer_wfd + self.processor_rfd))

        self.supervise_forever()

    def add_socket(self, data, num):
        logging.info('add_socket: %s %d' % (data, num))
        os.kill(self.processes['accept'], 42)

    def remove_socket(self, data, num):
        logging.info('remove_socket: %s %d' % (data, num))
        os.kill(self.processes['accept'], 43)

    def add_multiplexer(self, data, num):
        logging.info('add_multiplexer: %s %d' % (data, num))

    def remove_multiplexer(self, data, num):
        logging.info('remove_multiplexer: %s %d' % (data, num))

    def add_processor(self, data, num):
        logging.info('add_processor: %s %d' % (data, num))

    def remove_processor(self, data, num):
        logging.info('remove_processor: %s %d' % (data, num))

    def spawn_child(self, name, fdsToClose):
        pid = os.fork()
        if pid == 0: # Child
            # Close all unneeded file descriptors
            for fd in fdsToClose:
                if 'rfd' in self.processes[name] and self.processes[name]['rfd'] == fd:
                    continue
                try:
                    os.close(fd)
                except OSError:
                    pass

            # Start the various processes
            if self.processes[name]['type'] == 'acceptor':
                Process = Furie.server.acceptor.Acceptor(self.processes[name],
                                                         self.dbdsn)
            elif self.processes[name]['type'] == 'multiplexer':
                Process = Furie.server.multiproc.MultiProc(self.processes[name],
                                                           self.dbdsn)
            elif self.processes[name]['type'] == 'processor':
                Process = Furie.server.multiproc.MultiProc(self.processes[name],
                                                           self.dbdsn)
            else:
                os._exit(os.EX_USAGE)

            Process.run()

        # Register the pid
        Furie.DB.main.OnlineProcs(pid=pid, ppid=os.getpid(), name=name, type=self.processes[name]['type'])

    def supervise_forever(self):
        self.suicide = False

        def handler_sigterm(sig, frame):
            self.suicide = True

        signal.signal(signal.SIGTERM, handler_sigterm)

        signal.signal(signal.SIGCHLD, Furie.server.funcs.handler_sigchld)

        while not self.suicide:
            self.handle_supervise()
        else:
            self.supervisor_shutdown()

    def supervisor_shutdown(self):
        Furie.server.funcs.killall_children(os.getpid())
        logging.info('shutting down')
        logging.shutdown()
        os._exit(os.EX_OK)

    def handle_supervise(self):
        time.sleep(5)

        # First: lets get all the data from the database and order it
        todoDict = {}
        for todo in Furie.DB.main.SupervisorToDo.select():
            todo_action = str(todo.action)
            todo_data   = str(todo.data)

            if todo_action in SUPERVISOR_ACTIONS_LIST:
                if todo_action not in todoDict:
                    todoDict[todo_action] = {}

                if not todo_data:
                    todo_data = None

                if todo_data not in todoDict[todo_action]:
                    todoDict[todo_action][todo_data] = 1
                else:
                    todoDict[todo_action][todo_data] += 1

            todo.delete(int(todo.id))

        # Second: lets annihilate corresponding opposed actions
        for (act1, act2) in SUPERVISOR_ACTIONS:
            if act1 in todoDict and act2 in todoDict:
                todoDictNew = copy.deepcopy(todoDict)
                for data in todoDict[act1]:
                    if data in todoDict[act2]:
                        result = (todoDict[act1][data] - todoDict[act2][data])
                        if result > 0:
                            todoDictNew[act1][data] = abs(result)
                            del todoDictNew[act2][data]
                        elif result < 0:
                            del todoDictNew[act1][data]
                            todoDictNew[act2][data] = abs(result)
                        else:
                            del todoDictNew[act1][data]
                            del todoDictNew[act2][data]
                todoDict = todoDictNew

        # Third: cleanup the todoDict
        for action in SUPERVISOR_ACTIONS_LIST:
            if action in todoDict:
                if not todoDict[action]:
                    del todoDict[action]

        # Fourth: execute the needed actions
        for action in todoDict:
            action_exec = getattr(self, action)
            for data in todoDict[action]:
                action_exec(data, todoDict[action][data])