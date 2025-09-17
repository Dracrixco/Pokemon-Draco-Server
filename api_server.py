"""
HTTP API server for Pokemon Cable Club Server.
Provides REST endpoints for gifts and other features.
"""

import json
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, List, Any, Optional
import threading
import logging

from config import API_PORT


class GiftManager:
    """Manages gift data and logic."""
    
    def __init__(self, gifts_file: str = "gifts.json"):
        self.gifts_file = gifts_file
        self.gifts_data = self._load_gifts()
    
    def _load_gifts(self) -> List[Dict[str, Any]]:
        """Load gifts data from JSON file."""
        if not os.path.exists(self.gifts_file):
            # Create default gifts file if it doesn't exist
            default_gifts = [
                {
                    "initDate": "2025-01-01",
                    "lastDate": "2025-12-31",
                    "gift": ["POKEBALL", "GREATBALL", "ULTRABALL", "MASTERBALL"]
                }
            ]
            self._save_gifts(default_gifts)
            return default_gifts
        
        try:
            with open(self.gifts_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logging.error(f"Error loading gifts file: {e}")
            return []
    
    def _save_gifts(self, gifts: List[Dict[str, Any]]):
        """Save gifts data to JSON file."""
        try:
            with open(self.gifts_file, 'w', encoding='utf-8') as f:
                json.dump(gifts, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error saving gifts file: {e}")
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string in YYYY-MM-DD format."""
        return datetime.strptime(date_str, "%Y-%m-%d")
    
    def get_current_gift(self, gift_level: int) -> Optional[str]:
        """
        Get the current gift based on date and gift level.
        
        Args:
            gift_level: Level of gift (0-based index)
            
        Returns:
            Gift string or None if no valid gift found
        """
        current_date = datetime.now()
        
        # Find the first gift period that contains the current date
        for gift_period in self.gifts_data:
            try:
                init_date = self._parse_date(gift_period["initDate"])
                last_date = self._parse_date(gift_period["lastDate"])
                
                if init_date <= current_date <= last_date:
                    gifts = gift_period["gift"]
                    if not gifts:
                        continue
                    
                    # If gift_level is greater than available gifts, return the last one
                    if gift_level >= len(gifts):
                        return gifts[-1]
                    else:
                        return gifts[gift_level]
                        
            except (ValueError, KeyError) as e:
                logging.error(f"Error processing gift period: {e}")
                continue
        
        return None
    
    def get_all_gifts(self) -> List[Dict[str, Any]]:
        """Get all gift periods."""
        return self.gifts_data
    
    def reload_gifts(self):
        """Reload gifts from file."""
        self.gifts_data = self._load_gifts()


class APIRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the API endpoints."""
    
    def __init__(self, *args, gift_manager: GiftManager, **kwargs):
        self.gift_manager = gift_manager
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)
        
        try:
            if path == "/gifts" or path == "/regalos":
                self._handle_gifts(query_params)
            elif path == "/health":
                self._handle_health()
            elif path == "/reload-gifts":
                self._handle_reload_gifts()
            else:
                self._send_error(404, "Endpoint not found")
        except Exception as e:
            logging.error(f"Error handling request: {e}")
            self._send_error(500, "Internal server error")
    
    def _handle_gifts(self, query_params: Dict[str, List[str]]):
        """Handle gifts endpoint."""
        # Get gift level from query parameters
        nivel_param = query_params.get('nivel', ['0'])
        try:
            gift_level = int(nivel_param[0])
        except (ValueError, IndexError):
            self._send_error(400, "Invalid 'nivel' parameter. Must be a number.")
            return
        
        # Get current gift
        current_gift = self.gift_manager.get_current_gift(gift_level)
        
        if current_gift is None:
            self._send_error(404, "No gift available for current date")
            return
        
        # Return only the gift text as plain text
        self._send_text_response(current_gift)
    
    def _handle_health(self):
        """Handle health check endpoint."""
        response_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "gifts_loaded": len(self.gift_manager.gifts_data)
        }
        self._send_json_response(response_data)
    
    def _handle_reload_gifts(self):
        """Handle gifts reload endpoint."""
        self.gift_manager.reload_gifts()
        response_data = {
            "message": "Gifts reloaded successfully",
            "gifts_count": len(self.gift_manager.gifts_data),
            "timestamp": datetime.now().isoformat()
        }
        self._send_json_response(response_data)
    
    def _send_json_response(self, data: Dict[str, Any], status_code: int = 200):
        """Send JSON response."""
        response_json = json.dumps(data, ensure_ascii=False, indent=2)
        
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')  # Enable CORS
        self.send_header('Content-Length', str(len(response_json.encode('utf-8'))))
        self.end_headers()
        
        self.wfile.write(response_json.encode('utf-8'))
    
    def _send_text_response(self, text: str, status_code: int = 200):
        """Send plain text response."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')  # Enable CORS
        self.send_header('Content-Length', str(len(text.encode('utf-8'))))
        self.end_headers()
        
        self.wfile.write(text.encode('utf-8'))
    
    def _send_error(self, status_code: int, message: str):
        """Send error response."""
        error_data = {
            "error": message,
            "status_code": status_code,
            "timestamp": datetime.now().isoformat()
        }
        self._send_json_response(error_data, status_code)
    
    def log_message(self, format, *args):
        """Override to use our logging system."""
        logging.info(f"HTTP: {format % args}")


class APIServer:
    """HTTP API Server for Pokemon Cable Club."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = API_PORT, gifts_file: str = "gifts.json"):
        self.host = host
        self.port = port
        self.gift_manager = GiftManager(gifts_file)
        self.server = None
        self.server_thread = None
    
    def start(self):
        """Start the API server in a separate thread."""
        def create_handler(*args, **kwargs):
            return APIRequestHandler(*args, gift_manager=self.gift_manager, **kwargs)
        
        self.server = HTTPServer((self.host, self.port), create_handler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        
        logging.info(f'API Server started on http://{self.host}:{self.port}')
        logging.info(f'Gifts endpoint: http://{self.host}:{self.port}/gifts?nivel=0')
    
    def stop(self):
        """Stop the API server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logging.info('API Server stopped')
    
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self.server_thread is not None and self.server_thread.is_alive()


def create_example_gifts_file(filename: str = "gifts.json"):
    """Create an example gifts.json file."""
    example_gifts = [
        {
            "initDate": "2025-01-01",
            "lastDate": "2025-03-31",
            "gift": ["POKEBALL", "POTION", "ANTIDOTE"]
        },
        {
            "initDate": "2025-04-01",
            "lastDate": "2025-06-30",
            "gift": ["GREATBALL", "SUPERPOTION", "PARALYZEHEAL", "AWAKENING"]
        },
        {
            "initDate": "2025-07-01",
            "lastDate": "2025-09-30",
            "gift": ["ULTRABALL", "HYPERPOTION", "BURNHEAL", "ICEHEAL", "FULLHEAL"]
        },
        {
            "initDate": "2025-10-01",
            "lastDate": "2025-12-31",
            "gift": ["MASTERBALL", "MAXPOTION", "FULLRESTORE", "REVIVE", "MAXREVIVE", "RARECANDY"]
        }
    ]
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(example_gifts, f, indent=2, ensure_ascii=False)
    
    print(f"Created example gifts file: {filename}")


if __name__ == "__main__":
    # Create example gifts file if it doesn't exist
    if not os.path.exists("gifts.json"):
        create_example_gifts_file()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s: %(levelname)s: %(message)s'
    )
    
    # Start API server
    api_server = APIServer()
    api_server.start()
    
    print("API Server running. Available endpoints:")
    print("  GET /gifts?nivel=0    - Get gift for level 0")
    print("  GET /health          - Health check")
    print("  GET /reload-gifts    - Reload gifts from file")
    print("Press Ctrl+C to stop...")
    
    try:
        # Keep the main thread alive
        api_server.server_thread.join()
    except KeyboardInterrupt:
        print("\nStopping server...")
        api_server.stop()