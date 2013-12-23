from __future__ import absolute_import
# Furie-internal
import Furie.HTTPHandler.httpcodes
# From built-ins
import datetime
import logging

def send_error(code, message=None):
    DEFAULT_ERROR_MESSAGE = """
<head>
<title>Error response</title>
</head>
<body>
<h1>Error response</h1>
<p>Error code %(code)d.
<p>Message: %(message)s.
<p>Error code explanation: %(code)d = %(explanation)s.
</body>
"""
    try:
        shortmsg, longmsg = Furie.HTTPHandler.httpcodes.responses[code]
    except KeyError:
        shortmsg, longmsg = '???', '???'
    if not message:
        message = shortmsg
    explanation = longmsg
    logging.error('code %d, message %s' % (code, message))
    content = (DEFAULT_ERROR_MESSAGE %
               {'code': code, 'message': message.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), 'explanation': explanation})
    send_response(code, message)
    send_header('Content-Type', 'text/html')
    send_header('Connection', 'close')
    end_headers()
    if req_command != 'HEAD' and code >= 200 and code not in (204, 304):
        wfile.write(content)

def send_response(code, message=None):
    if not message:
        if code in Furie.HTTPHandler.httpcodes.responses:
            message = Furie.HTTPHandler.httpcodes.responses[code][0]
        else:
            message = ''
    if req_version != 'HTTP/0.9':
        wfile.write('%s %d %s\r\n' % (req_version, code, message))
    send_header('Server', server_version_string())
    send_header('Date', date_time_string())

def send_header(keyword, value):
    """Send a MIME header."""
    if req_version != 'HTTP/0.9':
        wfile.write('%s: %s\r\n' % (keyword, value))

    if keyword.lower() == 'connection':
        if value.lower() == 'close':
            close_connection = 1
        elif value.lower() == 'keep-alive':
            close_connection = 0

def end_headers():
    """Send the blank line ending the MIME headers."""
    if req_version != 'HTTP/0.9':
        wfile.write('\r\n')

def server_version_string():
    """Return the server software version string."""
    return '%s %s on %s' % (server, system, platform)

def date_time_string(timestamp=None):
    """Return the current date and time formatted for a message header."""
    if not timestamp:
        timestamp = time.time()
    year, month, day, hh, mm, ss, wd, y, z = time.gmtime(timestamp)
    s = '%s, %02d %3s %4d %02d:%02d:%02d GMT' % (
            weekdayname[wd],
            day, monthname[month], year,
            hh, mm, ss)
    return s

weekdayname = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

monthname = [None,
             'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

def read_headers(fobj):
    headers = {}
    latest_header = ''

    while True:
        line = fobj.readline()

        if not line:
            raise IOError, 'EOF in headers'

        if line in ['\r\n', '\n']:
            # The delimiter line gets eaten, and we've finished.
            break

        if line[0] in [' ', '\t']:
            if latest_header:
                # It's a continuation line.
                headers[latest_header] = (headers[latest_header] + ' ' + line.strip()).strip()
                continue
            else:
                # It's no continuation line as there wasn't anything before.
                raise IOError, 'Invalid header'

        # This should be a normal header.
        colpos = line.find(':')
        if colpos > 0:
            # It's a legal header line, save it.
            latest_header = line[:colpos].strip().upper()
            headers[latest_header] = line[colpos+1:].strip()
            continue
        else:
            # It's not a header line, stop here.
            raise IOError, 'Unexpected non-header line'

    return headers