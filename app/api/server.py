from http.server import HTTPServer


class BotAPIServer(HTTPServer):
    def __init__(self, server_address, request_handler_class, loop):
        super().__init__(server_address, request_handler_class)
        self.loop = loop
