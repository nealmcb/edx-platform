from collections import namedtuple
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
import threading


class StubServer(HTTPServer):
    """
    Based on Will Daly's implementation of a stub server up at
    http://blog.will-daly.com/2013/06/05/stub-http-server/
    """

    def __init__(self, request_handler):
        address = ('127.0.0.1', 9203)
        HTTPServer.__init__(self, address, request_handler)
        self.start()

        self.requests = []
        self.request = namedtuple("Request", "request_type path content")

        self.header_dict = {}
        self.status_code = 200
        self.content = ""

    def start(self):
        """
        Starts the server
        """

        server_thread = threading.Thread(target=self.serve_forever)
        server_thread.daemon = True
        server_thread.start()

    def stop(self):
        """
        Cleanly stops the server
        """

        self.shutdown()
        self.socket.close()

    def log_request(self, request_type, path, content):
        """
        Keeps track of the request and alters content if a search request is launched
        """

        self.requests.append(self.request(request_type, path, content))

    def set_response(self, header_dict, status_code, content):
        """
        Set server response
        """

        self.header_dict = header_dict
        self.status_code = status_code
        self.content = content


class StubRequestHandler(BaseHTTPRequestHandler):
    """
    Request handler that mocks Elastic Search
    """

    def do_POST(self):
        """
        Handling for a POST request
        """
 
        self.server.log_request('POST', self.path, self.content())
        self._send_server_response()

    def do_GET(self):
        """
        Handling for a GET request
        """

        self.server.log_request('GET', self.path, self.content())
        self._send_server_response()

    def do_PUT(self):
        """
        Handling for a PUT request
        """

        self.server.log_request('PUT', self.path, self.content())
        self._send_server_response()

    def do_HEAD(self):
        """
        Handling for a HEAD request
        """

        self.server.log_request('HEAD', self.path, self.content())
        self._send_server_response()

    def content(self):
        """
        Returns request content
        """

        try:
            length = int(self.headers.getheader('content-length'))
        except (TypeError, ValueError):
            return ""
        self.rfile.read(length)

    def _send_server_response(self):
        """
        Sends the Server's current response to the client
        """

        self.send_response(self.server.status_code)
        for (key, value) in self.server.header_dict.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(self.server.content)
