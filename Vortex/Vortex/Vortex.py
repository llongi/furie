# From built-ins
import threading
import Queue
import logging
import time

class WorkerThread(threading.Thread):
    def __init__(self, jobQueue):
        threading.Thread.__init__(self)
        self.setDaemon(1)
        self.jobQueue = jobQueue
        self.suicide = False
        self.start()

    def run(self):
        while not self.suicide:
            job = self.jobQueue.get(True)

            try:
                job.callable(*job.args, **job.kwds)
            except (MemoryError, SystemError):
                logging.debug(
                    'Vortex: serious exception, logging and exiting ...',
                    exc_info=True
                )
                self.suicide = True
            except:
                logging.debug(
                    'Vortex: uncaught exception, logging and continuing ...',
                    exc_info=True
                )

    def kill(self):
        self.suicide = True

class Job:
    def __init__(self, callable, args=None, kwds=None):
        self.callable = callable
        self.args = args or []
        self.kwds = kwds or {}

class Vortex:
    def __init__(self, num_workers, queue_size=0):
        self.jobQueue = Queue.Queue(queue_size)
        self.acceptJobs = True
        self.workerThreads = []
        self.createWorkers(num_workers)

    def createWorkers(self, num_workers):
        for i in range(num_workers):
            self.workerThreads.append(WorkerThread(self.jobQueue))

    def killWorkers(self, num_workers):
        for i in range(min(num_workers, len(self.workerThreads))):
            workerThread = self.workerThreads.pop()
            workerThread.kill()

    def shutdown(self, graceful=True):
        self.acceptJobs = False
        if graceful:
            while not self.jobQueue.empty():
                time.sleep(2)
        self.killWorkers(len(self.workerThreads))

    def addJob(self, job, block=True, timeout=2):
        if self.acceptJobs:
            assert isinstance(job, Job)
            self.jobQueue.put(job, block, timeout)