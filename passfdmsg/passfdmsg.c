/*
 * Passing file descriptors and additional data with Python,
 * all in one go, using UNIX sockets.
 * Also supports sendfile() and setting the process name.
 * Tested on Linux 2.6 and FreeBSD. Should also work on Solaris.
 * Portability fixes or success stories welcome.
 */

#include "Python.h"

#ifndef __OpenBSD__
#ifndef _XOPEN_SOURCE
#define _XOPEN_SOURCE 500
#endif
#ifndef _XOPEN_SOURCE_EXTENDED
#define _XOPEN_SOURCE_EXTENDED 1 /* Solaris <= 2.7 needs this too */
#endif
#endif /* __OpenBSD__ */

#include <sys/types.h>
#include <sys/socket.h>
#include <sys/uio.h>
#include <stddef.h>

/* for platforms that don't provide CMSG_*  macros */
#ifndef ALIGNBYTES
#define ALIGNBYTES (sizeof(int) - 1)
#endif

#ifndef ALIGN
#define ALIGN(p) (((unsigned int)(p) + ALIGNBYTES) & ~ ALIGNBYTES)
#endif

#ifndef CMSG_LEN
#define CMSG_LEN(len) (ALIGN(sizeof(struct cmsghdr)) + ALIGN(len))
#endif

#ifndef CMSG_SPACE
#define CMSG_SPACE(len) (ALIGN(sizeof(struct cmsghdr)) + ALIGN(len))
#endif

/* define max length of the string that can be passed as msg */
#ifndef PASSFDMSG_MAX_STR_LEN
#define PASSFDMSG_MAX_STR_LEN 8192
#endif

static PyObject *
passfdmsg_sendfdmsg(PyObject *self, PyObject *args)
{
    int ret = -1;
    struct msghdr msg;
    struct cmsghdr *cmsg;
    struct iovec iov[2];
    char tmp[CMSG_SPACE(sizeof(int))];
    char *content = NULL;
    int content_len = 0;
    int sockfd, fd;

    if (!PyArg_ParseTuple(args, "ii|s#:sendfdmsg", &sockfd, &fd, &content, &content_len))
        return NULL;

    if (content_len > PASSFDMSG_MAX_STR_LEN) {
        char buf[107] = "";
        sprintf(buf,
                "sendfdmsg() argument 3 exceeds maximum string length (actual=%d,max=%d)",
                content_len,
                PASSFDMSG_MAX_STR_LEN);
        PyErr_SetString(PyExc_ValueError, buf);
        return NULL;
    }

    iov[0].iov_base = &content_len;
    iov[0].iov_len  = sizeof(content_len);
    iov[1].iov_base = content;
    iov[1].iov_len  = content_len;

    memset(&msg, 0, sizeof(msg));
    msg.msg_iov        = iov;
    msg.msg_iovlen     = 2;
    msg.msg_control    = (caddr_t) tmp;
    msg.msg_controllen = CMSG_LEN(sizeof(int));

    cmsg = CMSG_FIRSTHDR(&msg);
    cmsg->cmsg_len   = CMSG_LEN(sizeof(int));
    cmsg->cmsg_level = SOL_SOCKET;
    cmsg->cmsg_type  = SCM_RIGHTS;
    *(int *)CMSG_DATA(cmsg) = fd;

    Py_BEGIN_ALLOW_THREADS
    ret = sendmsg(sockfd, &msg, 0);
    Py_END_ALLOW_THREADS

    if (ret < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
passfdmsg_recvfdmsg(PyObject *self, PyObject *args)
{
    int ret = -1;
    struct msghdr msg;
    struct cmsghdr *cmsg;
    struct iovec iov[2];
    char tmp[CMSG_SPACE(sizeof(int))];
    char content[PASSFDMSG_MAX_STR_LEN] = "";
    int content_len = 0;
    int sockfd, fd;

    if (!PyArg_ParseTuple(args, "i:recvfdmsg", &sockfd))
        return NULL;

    iov[0].iov_base = &content_len;
    iov[0].iov_len  = sizeof(content_len);
    iov[1].iov_base = &content;
    iov[1].iov_len  = PASSFDMSG_MAX_STR_LEN;

    memset(&msg, 0, sizeof(msg));
    msg.msg_iov        = iov;
    msg.msg_iovlen     = 2;
    msg.msg_control    = tmp;
    msg.msg_controllen = sizeof(tmp);

    Py_BEGIN_ALLOW_THREADS
    ret = recvmsg(sockfd, &msg, 0);
    Py_END_ALLOW_THREADS

    if (ret < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    cmsg = CMSG_FIRSTHDR(&msg);
    fd = *(int *)CMSG_DATA(cmsg);

    if (fd < 0) {
        PyErr_SetString(PyExc_OSError, "invalid file descriptor value");
        return NULL;
    }

    return Py_BuildValue("(is#)", fd, &content, content_len);
}

static PyObject *
passfdmsg_socketpair(PyObject *self, PyObject *args)
{
    int fd[2];

    if (socketpair(AF_UNIX, SOCK_STREAM, 0, fd) < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    return Py_BuildValue("(ii)", fd[0], fd[1]);
}

static PyObject *
passfdmsg_sendfile(PyObject *self, PyObject *args)
{
    int sockfd, fd;
    long py_offset, py_nbytes;
    char *head = NULL;
    size_t head_len = 0;
    char *tail = NULL;
    size_t tail_len = 0;

    if (!PyArg_ParseTuple(args, "iill|s#s#:sendfile", &fd, &sockfd, &py_offset, &py_nbytes, &head, &head_len, &tail, &tail_len))
        return NULL;

    off_t offset = py_offset;
    size_t nbytes = py_nbytes;

#if defined (__linux__)

#include <netinet/tcp.h>

    PyObject *py_result = NULL;
    ssize_t sent_head = 0;
    ssize_t sent_file = 0;
    ssize_t sent_tail = 0;
    int orig_cork = 1;
    int orig_cork_len = sizeof(int);

    if (head || tail) {
      int cork = 1;
      getsockopt(sockfd, SOL_TCP, TCP_CORK, (void*)&orig_cork, &orig_cork_len);
      setsockopt(sockfd, SOL_TCP, TCP_CORK, (void*)&cork, sizeof(cork));
    }

    // send head
    if (head) {
        Py_BEGIN_ALLOW_THREADS
        sent_head = send(sockfd, head, head_len, 0);
        Py_END_ALLOW_THREADS
        if (sent_head < 0) {
            PyErr_SetFromErrno(PyExc_OSError);
            py_result = NULL;
            goto done;
        } else if (sent_head < head_len) {
            py_result = PyInt_FromLong(sent_head);
            goto done;
        }
    }

    // send file
    Py_BEGIN_ALLOW_THREADS
    sent_file = sendfile(sockfd, fd, &offset, nbytes);
    Py_END_ALLOW_THREADS
    if (sent_file < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        py_result = NULL;
        goto done;
    } else if (sent_file < nbytes) {
        py_result = PyInt_FromLong(sent_head + sent_file);
        goto done;
    }

    // send tail
    if (tail) {
        Py_BEGIN_ALLOW_THREADS
        sent_tail = send(sockfd, tail, tail_len, 0);
        Py_END_ALLOW_THREADS
        if (sent_tail < 0) {
            PyErr_SetFromErrno(PyExc_OSError);
            py_result = NULL;
            goto done;
        }
    }

    py_result = PyInt_FromLong(sent_head + sent_file + sent_tail);

    done:
       if (head || tail) {
           setsockopt(sockfd, SOL_TCP, TCP_CORK, (void*)&orig_cork, sizeof(orig_cork));
       }
       return py_result;

#elif defined (__FreeBSD__)

    off_t sent;
    int result;

    if (head || tail) {
        struct iovec ivhead = {head, head_len};
        struct iovec ivtail = {tail, tail_len};
        struct sf_hdtr hdtr = {&ivhead, 1, &ivtail, 1};
        Py_BEGIN_ALLOW_THREADS
        result = sendfile(fd, sockfd, offset, nbytes, &hdtr, &sent, 0);
        Py_END_ALLOW_THREADS
    } else {
        Py_BEGIN_ALLOW_THREADS
        result = sendfile(fd, sockfd, offset, nbytes, NULL, &sent, 0);
        Py_END_ALLOW_THREADS
    }

    if (result == -1) {
        if (errno == EAGAIN) {
            return PyInt_FromLong(sent);
        } else {
            PyErr_SetFromErrno(PyExc_OSError);
            return NULL;
        }
    } else {
        return PyInt_FromLong(sent);
    }

#else

    PyErr_SetString(PyExc_NotImplementedError, "not implemented");
    return NULL;

#endif

}

static PyObject *
passfdmsg_setproctitle(PyObject *self, PyObject *args)
{
    char *proctitle = NULL;
    int zeroout = 0;

    if (!PyArg_ParseTuple(args, "s|i:setproctitle", &proctitle, &zeroout))
        return NULL;

#if defined (__linux__)

#include <sys/prctl.h>

    int ret = -1;
    int argc;
    char **argv;
    int argv_len = 0;
    int proctitle_len = 0;

    Py_GetArgcArgv(&argc, &argv);

    argv_len = strlen(argv[0]);
    proctitle_len = strlen(proctitle);

    if (argv_len < proctitle_len) {
        char buf[110] = "";
        sprintf(buf,
                "setproctitle() argument 1 exceeds maximum string length (actual=%d,max=%d)",
                proctitle_len,
                argv_len);
        PyErr_SetString(PyExc_ValueError, buf);
        return NULL;
    }

    ret = prctl(PR_SET_NAME, proctitle, 0, 0, 0);

    if (ret < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    strncpy(argv[0], proctitle , proctitle_len);
    memset(&argv[0][proctitle_len], '\0', strlen(&argv[0][proctitle_len]));

    if (zeroout) {
        int i = 0;

        for (i=1; i < argc; i++) {
            memset(argv[i], '\0', strlen(argv[i]));
        }
    }

    Py_INCREF(Py_None);
    return Py_None;

#elif defined (__FreeBSD__)

#include <unistd.h>

    setproctitle("-%s", proctitle);

    Py_INCREF(Py_None);
    return Py_None;

#elif defined (__OpenBSD__)

#include <stdlib.h>

    setproctitle("%s", proctitle);

    Py_INCREF(Py_None);
    return Py_None;

#else

    PyErr_SetString(PyExc_NotImplementedError, "not implemented");
    return NULL;

#endif

}

/* List of functions */

static PyMethodDef passfdmsg_methods[] = {
    {"sendfdmsg",    passfdmsg_sendfdmsg,    METH_VARARGS, "sendfdmsg(int sockfd, int fd[, string msg])"},
    {"recvfdmsg",    passfdmsg_recvfdmsg,    METH_VARARGS, "recvfdmsg(int sockfd) -> (int fd, string msg)"},
    {"socketpair",   passfdmsg_socketpair,   METH_NOARGS,  "socketpair() -> (int fd, int fd)"},
    {"sendfile",     passfdmsg_sendfile,     METH_VARARGS, "sendfile(int fd, int sockfd, long offset, long nbytes[, string head, string tail]) -> int sent_bytes"},
    {"setproctitle", passfdmsg_setproctitle, METH_VARARGS, "setproctitle(string proctitle[, int zeroout])"},
    {NULL, NULL} /* sentinel */
};

DL_EXPORT(void)
initpassfdmsg(void)
{
    PyObject *m;

    /* Create the module and add the functions and documentation */
    m = Py_InitModule3("passfdmsg", passfdmsg_methods, "A Python module to pass fds and messages. Sendfile() support and others.");
}
