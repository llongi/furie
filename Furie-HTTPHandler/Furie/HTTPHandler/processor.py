from __future__ import absolute_import
# Furie-internal
import Furie.DB
import Furie.HTTPHandler.funcs
import Furie.HTTPHandler.mimemaps
# From site-packages
import cgiws
# From built-ins
import os
import urlparse
import urllib
import logging
import datetime
import csv

class Processor:
    def __init__(self, req, reqinfo, proc):
        self.req = req
        self.reqinfo = reqinfo
        self.__proc = proc

        self.handle_request()

    def handle_request(self):
        # Setup request headers
        req_headers = {
                       'SERVER_NAME': '127.0.0.1',
                       'SERVER_ADDR': '127.0.0.1',
                       'SERVER_PORT': '8000',
                       'SERVER_PROTOCOL': 'HTTP/1.1',
                       'SERVER_SOFTWARE': 'Furie',
                       'SERVER_SIGNATURE': 'Furie',
                       'GATEWAY_INTERFACE': 'CGI/1.1',
                       'REQUEST_METHOD': 'GET',
                       'PATH_INFO': '', # extra path_info, after the script_name
                       'PATH_TRANSLATED': '/var/www/localhost/htdocs/asd/phpinfo.php', # absolute path to the script
                       'SCRIPT_NAME': '/phpinfo.php', # virtual path to the script (as seen from the webserver)
                       'QUERY_STRING': 'lol=name&pota=rota', # blabla=bla&1=2
                       'DOCUMENT_ROOT': '/var/www/localhost/htdocs/asd', # base directory of the domain
                       'REQUEST_URI': '/phpinfo.php?lol=name&pota=rota', # full request url
                       'REMOTE_ADDR': '127.0.0.1',
                       'REMOTE_PORT': '48000',
                       'HTTP_HOST': '127.0.0.1',
                       'HTTP_USER_AGENT': 'Mozilla 25',
                       'HTTP_REFERER': 'www.test.com',
                       }

        # Setup connection info
        fcgi_addr = ['IPV4', ('127.0.0.1', 8080)]

        try:
            fcgi_req = cgiws.fcgi.Request(fcgi_addr, 1)
        except:
            bin = '/usr/bin/php-cgi'
            env_dict = {'PATH': '/bin:/usr/bin',
                        'SHELL': '/bin/false',
                        'USER': 'chtekk',
                        'PHP_FCGI_CHILDREN': '5'}
            fcgi_srv = cgiws.spawn.FCGI(bin, fcgi_addr, env=env_dict)
            logging.info('new fcgi server at %s:%d spawned with pid %d' % (fcgi_addr[1] + (fcgi_srv.pid,)))
            Furie.DB.main.OnlineProcs(pid=fcgi_srv.pid, ppid=os.getpid(), name='fcgi_%s' % self.__proc['name'], type='fastcgi')

            fcgi_req = cgiws.fcgi.Request(fcgi_addr, 1)
            logging.info('connection to fcgi server at %s:%d successfull' % fcgi_addr[1])

        fcgi_req.begin(cgiws.fcgi.FCGI_RESPONDER)
        fcgi_req.params(req_headers)
        fcgi_req.params({})
        fcgi_req.stdin('')
        fcgi_req.response()

        body = fcgi_req.stdout.split('\r\n\r\n', 1)[1]
        self.req.sendall('HTTP/1.0 200 OK\r\n' \
                         'Content-Type: text/html\r\n' \
                         'Content-Length: %d\r\n' \
                         'Connection: close\r\n' \
                         '\r\n' \
                         '%s' \
                          % (len(body), body))

        log_data = (
                    'sys1',
                    datetime.datetime.now(),
                    req_headers['REMOTE_ADDR'],
                    '',
                    'test1',
                    req_headers['HTTP_HOST'],
                    req_headers['HTTP_USER_AGENT'],
                    req_headers['HTTP_REFERER'],
                    req_headers['REQUEST_METHOD'],
                    req_headers['REQUEST_URI'],
                    req_headers['SERVER_PROTOCOL'],
                    200,
                    'text/html',
                    0,
                    len(body)
                   )

        db_log = True
        if db_log:
            log_data_sql = ()
            for cp in log_data:
                log_data_sql += (Furie.DB.sqlhub.processConnection.sqlrepr(cp),)

            # Access as Furie.DB.http.Log
            Furie.DB.sqlhub.processConnection.query(
                'INSERT INTO log ' \
                '(system, time, remote_host, remote_auth, user, vhost, user_agent, referer, ' \
                'http_method, http_request, http_version, resp_code, resp_content, in_bytes, out_bytes) ' \
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);' % log_data_sql
            )
        else:
            traffic_log = open('/home/chtekk/httpd/traffic_log', 'a')
            csv.writer(traffic_log).writerow(log_data)
            traffic_log.close()

        self.req.close()

    def setup(self):
        self.rfile = self.req.makefile('rb', -1)
        self.wfile = self.req.makefile('wb',  0)

    def handle(self):
        self.close_connection = 1
        self.handle_request()
        while not self.close_connection:
            self.handle_request()

    def finish(self):
        if not self.wfile.closed:
            self.wfile.flush()
        self.wfile.close()
        self.rfile.close()

    #method_name = 'do_' + self.req_command
    #if not hasattr(self, method_name):
    #    self.send_error(501, 'Unsupported method (%r)' % self.req_command)
    #    return
    #method = getattr(self, method_name)
    #method()

    # host rfc931 authuser [DD/Mon/YYYY:hh:mm:ss] "request" ddd bbbb

    def do_GET(self):
        """Serve a GET request."""
        f = self.send_head()
        if f:
            self.copyfile(f, self.wfile)
            f.close()

    def do_HEAD(self):
        """Serve a HEAD request."""
        f = self.send_head()
        if f:
            f.close()

    def send_head(self):
        """Common code for GET and HEAD commands.
        This sends the response code and MIME headers.
        Return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.
        """
        path = self.translate_path(self.req_path)
        f = None
        if os.path.isdir(path):
            if not self.req_path.endswith('/'):
                # redirect browser - doing basically what Apache does
                self.send_response(301)
                self.send_header('Location', self.req_path + '/')
                self.send_header('Connection', 'close')
                self.end_headers()
                return None
            for index in 'index.html', 'index.htm':
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
            else:
                return self.list_directory(path)
        ctype = self.guess_type(path)
        if ctype.startswith('text/'):
            mode = 'r'
        else:
            mode = 'rb'
        try:
            f = open(path, mode)
        except IOError:
            self.send_error(404, 'File not found')
            return None
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        fs = os.fstat(f.fileno())
        self.send_header('Content-Length', str(fs.st_size))
        self.send_header('Last-Modified', self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f

    def list_directory(self, path):
        """Helper to produce a directory listing (absent index.html).
        Return value is either a file object, or None (indicating an
        error).  In either case, the headers are sent, making the
        interface the same as for send_head().
        """
        try:
            list = os.listdir(path)
        except os.error:
            self.send_error(404, 'No permission to list directory')
            return None
        list.sort(key=lambda a: a.lower())
        try:
            from cStringIO import StringIO
        except ImportError:
            from StringIO import StringIO
        f = StringIO()
        displaypath = urllib.unquote(self.req_path).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        f.write('<title>Directory listing for %s</title>\n' % displaypath)
        f.write('<h2>Directory listing for %s</h2>\n' % displaypath)
        f.write('<hr>\n<ul>\n')
        for name in list:
            fullname = os.path.join(path, name)
            displayname = linkname = name
            # Append / for directories or @ for symbolic links
            if os.path.isdir(fullname):
                displayname = name + '/'
                linkname = name + '/'
            if os.path.islink(fullname):
                displayname = name + '@'
                # Note: a link to a directory displays with @ and links with /
            f.write('<li><a href="%s">%s</a></li>\n'
                    % (urllib.quote(linkname), displayname.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')))
        f.write('</ul>\n<hr>\n')
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', str(length))
        self.end_headers()
        return f

    def translate_path(self, path):
        """Translate a /-separated PATH to the local filename syntax.
        Components that mean special things to the local file system
        (e.g. drive or directory names) are ignored.
        """
        path = urlparse.urlparse(path)[2]
        path = urllib.unquote(path)
        path = os.path.normpath(path)
        words = path.split(os.sep)
        words = filter(None, words)
        path = os.getcwd()
        for word in words:
            (drive, word) = os.path.splitdrive(word)
            (head, word) = os.path.split(word)
            if word in (os.curdir, os.pardir): continue
            path = os.path.join(path, word)
        return path

    def copyfile(self, source, outputfile):
        """Copy all data between two file objects.
        The SOURCE argument is a file object open for reading
        (or anything with a read() method) and the DESTINATION
        argument is a file object open for writing (or
        anything with a write() method).
        The only reason for overriding this would be to change
        the block size or perhaps to replace newlines by CRLF
        -- note however that this the default server uses this
        to copy binary data as well.
        """
        shutil.copyfileobj(source, outputfile)

    def guess_type(self, path):
        """Guess the type of a file.
        Argument is a PATH (a filename).
        Return value is a string of the form type/subtype,
        usable for a MIME Content-type header.
        The default implementation looks the file's extension
        up in the table self.extensions_map, using application/octet-stream
        as a default; however it would be permissible (if
        slow) to look inside the data to make a better guess.
        """
        base, ext = os.path.splitext(path)
        if ext in Furie.HTTPHandler.mimemaps.extmap:
            return Furie.HTTPHandler.mimemaps.extmap[ext]
        ext = ext.lower()
        if ext in Furie.HTTPHandler.mimemaps.extmap:
            return Furie.HTTPHandler.mimemaps.extmap[ext]
        else:
            return 'application/octet-stream'