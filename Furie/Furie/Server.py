from __future__ import absolute_import
# Furie-internal
import Furie.DB
import Furie.server.funcs
import Furie.server.supervisor
# From built-ins
import sys
import logging

class Server:
    def __init__(self, dbdsn, handler):
        # Setup database and first connection
        try:
            Furie.DB.Init(dbdsn)
            Furie.DB.main.Setup()
        except:
            sys.exit('CRITICAL: failed connection or setup of main database')

        # Validate handler
        if len(handler) > 6 or not handler.isalnum():
            sys.exit('CRITICAL: invalid main handler name')

        # Now import the handler database portion and set it up
        HandlerDB = Furie.server.funcs.importHandler('db', handler)
        if HandlerDB and hasattr(HandlerDB, 'Setup'):
            HandlerDB.Setup()
        setattr(Furie.DB, handler.lower(), HandlerDB)
        del HandlerDB

        # Import the main Multiplexer handler
        Furie.server.funcs.multiplexer_handler = Furie.server.funcs.importHandler('%sHandler.multiplexer' % handler, 'Multiplexer')
        if not Furie.server.funcs.multiplexer_handler:
            sys.exit('CRITICAL: failed to import %sHandler Multiplexer handler' % handler)

        # Import the main Processor handler
        Furie.server.funcs.processor_handler = Furie.server.funcs.importHandler('%sHandler.processor' % handler, 'Processor')
        if not Furie.server.funcs.processor_handler:
            sys.exit('CRITICAL: failed to import %sHandler Processor handler' % handler)

        # And now import the error handlers from the main handler
        Furie.server.funcs.error_handler = Furie.server.funcs.importHandler('%sHandler.errorhandlers' % handler, 'ErrorHandler')
        if not Furie.server.funcs.error_handler:
            sys.exit('CRITICAL: failed to import %sHandler error handler' % handler)

        Furie.server.funcs.busyerror_handler = Furie.server.funcs.importHandler('%sHandler.errorhandlers' % handler, 'BusyErrorHandler')
        if not Furie.server.funcs.busyerror_handler:
            # If not defined, default to main error handler
            Furie.server.funcs.busyerror_handler = Furie.server.funcs.error_handler

        # Real logging setup, using the data from the database
        logging.basicConfig(level    = int(Furie.DB.main.ConfVal('log_level')),
                            format   = '%(asctime)s %(levelname)-8s (furie): %(message)s',
                            datefmt  = '%Y-%m-%d %H:%M:%S',
                            filename = str(Furie.DB.main.ConfVal('log_filename')),
                            filemode = 'a')

        # Now, background!
        Furie.server.funcs.daemonize()

        # And then write out the pid of the new process
        Furie.server.funcs.write_pidfile(str(Furie.DB.main.ConfVal('pidfile')))

        # And switch to the Supervisor class, to keep code simple here
        Supervisor = Furie.server.supervisor.Supervisor(dbdsn)
        Supervisor.run()