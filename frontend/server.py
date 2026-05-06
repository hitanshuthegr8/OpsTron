"""
Frontend Development Server
Simple HTTP server to serve the OpsTron dashboard.
"""

import http.server
import socketserver
import os

PORT = 3000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def end_headers(self):
        # Enable CORS for API calls
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()


if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"""
================================================================
                    OpsTron Dashboard                          
================================================================
  Frontend:  http://localhost:{PORT}                         
  Agent:     http://localhost:8001                         
  Backend:   http://localhost:8000                         
================================================================

Press Ctrl+C to stop the server.
        """)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
