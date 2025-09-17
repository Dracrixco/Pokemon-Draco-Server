"""
HTTP API server for Pokemon Cable Club Server.
Provides REST endpoints for gifts and other features.
"""

import os
import glob
import re
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, List, Any, Optional
import threading
import logging

from config import API_PORT


class GiftManager:
    """Manages gift data and logic from .txt files."""
    
    def __init__(self, gifts_dir: str = "Gifts"):
        """Initialize GiftManager with directory containing .txt gift files."""
        self.gifts_dir = gifts_dir
        self.gifts_data = self._load_gifts()
    
    def _load_gifts(self) -> List[Dict[str, Any]]:
        """Load gifts from .txt files in the gifts directory."""
        gifts = []
        
        if not os.path.exists(self.gifts_dir):
            logging.warning(f"Gifts directory {self.gifts_dir} does not exist")
            return gifts
        
        # Find all .txt files in gifts directory
        gift_files = glob.glob(os.path.join(self.gifts_dir, "*.txt"))
        
        for file_path in gift_files:
            try:
                gift_data = self._parse_gift_file(file_path)
                if gift_data:
                    gifts.append(gift_data)
                    logging.info(f"Loaded gift file: {os.path.basename(file_path)}")
            except Exception as e:
                logging.error(f"Error loading gift file {file_path}: {e}")
        
        return gifts
    
    def _parse_gift_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Parse a single gift .txt file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if not lines:
                return None
            
            # First line should contain date range
            date_line = lines[0].strip()
            date_match = re.match(r'(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})', date_line)
            
            if not date_match:
                logging.error(f"Invalid date format in {file_path}: {date_line}")
                return None
            
            init_date, last_date = date_match.groups()
            
            # Parse gift levels from the rest of the file
            gift_levels = {}
            current_level = None
            current_content = []
            
            for line in lines[1:]:
                line = line.rstrip('\n\r')
                
                # Check for gift level marker
                level_match = re.match(r'#\s*Gift\s+Lv\s+(\d+)', line, re.IGNORECASE)
                if level_match:
                    # Save previous level if exists
                    if current_level is not None:
                        gift_levels[current_level] = '\n'.join(current_content)
                    
                    # Start new level
                    current_level = int(level_match.group(1))
                    current_content = []
                else:
                    # Add line to current content
                    if current_level is not None:
                        current_content.append(line)
            
            # Save last level
            if current_level is not None:
                gift_levels[current_level] = '\n'.join(current_content)
            
            return {
                'initDate': init_date,
                'lastDate': last_date,
                'gifts': gift_levels,
                'filename': os.path.basename(file_path)
            }
            
        except Exception as e:
            logging.error(f"Error parsing gift file {file_path}: {e}")
            return None
    
    def get_gift_for_level(self, gift_level: int) -> Optional[str]:
        """Get gift for specific level based on current date."""
        current_date = datetime.now().date()
        
        for gift_period in self.gifts_data:
            try:
                init_date = datetime.strptime(gift_period['initDate'], '%Y-%m-%d').date()
                last_date = datetime.strptime(gift_period['lastDate'], '%Y-%m-%d').date()
                
                # Check if current date is within this period
                if init_date <= current_date <= last_date:
                    gifts = gift_period.get('gifts', {})
                    
                    if not gifts:
                        continue
                    
                    # Convert keys to integers and sort them
                    available_levels = sorted([int(k) for k in gifts.keys()])
                    
                    # Find appropriate gift level
                    if gift_level in gifts:
                        return gifts[gift_level]
                    elif available_levels:
                        # Return the highest available level if requested level is too high
                        closest_level = max([level for level in available_levels if level <= gift_level], 
                                          default=available_levels[-1])
                        return gifts[closest_level]
                        
            except (ValueError, KeyError) as e:
                logging.error(f"Error processing gift period: {e}")
                continue
        
        return None
    
    def get_all_gifts(self) -> List[Dict[str, Any]]:
        """Get all gift periods."""
        return self.gifts_data
    
    def reload_gifts(self):
        """Reload gifts from files."""
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
        
        # Get gift for the specified level
        gift = self.gift_manager.get_gift_for_level(gift_level)
        
        if gift is not None:
            self._send_response(200, gift, content_type="text/plain")
        else:
            self._send_response(404, "No gift available for the current date and level")
    
    def _handle_health(self):
        """Handle health check endpoint."""
        self._send_response(200, "API Server is running")
    
    def _handle_reload_gifts(self):
        """Handle reload gifts endpoint."""
        try:
            self.gift_manager.reload_gifts()
            gift_count = len(self.gift_manager.get_all_gifts())
            self._send_response(200, f"Gifts reloaded successfully. {gift_count} gift periods available.")
        except Exception as e:
            logging.error(f"Error reloading gifts: {e}")
            self._send_error(500, "Error reloading gifts")
    
    def _send_response(self, status_code: int, message: str, content_type: str = "text/plain"):
        """Send HTTP response."""
        self.send_response(status_code)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(message.encode('utf-8'))
    
    def _send_error(self, status_code: int, message: str):
        """Send HTTP error response."""
        self._send_response(status_code, message)
    
    def log_message(self, format_str, *args):
        """Override to use logging module."""
        logging.info(f"{self.address_string()} - {format_str % args}")


class APIServer:
    """HTTP API Server for Pokemon Cable Club."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = API_PORT, gifts_dir: str = "Gifts"):
        """Initialize API server."""
        self.host = host
        self.port = port
        self.gift_manager = GiftManager(gifts_dir)
        self.server = None
        self.server_thread = None
    
    def _create_handler(self):
        """Create request handler with gift manager."""
        def handler(*args, **kwargs):
            return APIRequestHandler(*args, gift_manager=self.gift_manager, **kwargs)
        return handler
    
    def start(self):
        """Start the API server."""
        try:
            handler = self._create_handler()
            self.server = HTTPServer((self.host, self.port), handler)
            
            # Start server in a separate thread
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            logging.info(f"API Server started on http://{self.host}:{self.port}")
            
        except Exception as e:
            logging.error(f"Error starting API server: {e}")
            raise
    
    def stop(self):
        """Stop the API server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logging.info("API Server stopped")
    
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self.server_thread is not None and self.server_thread.is_alive()


if __name__ == "__main__":
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
    print("  GET /reload-gifts    - Reload gifts from txt files")
    print("Press Ctrl+C to stop...")
    
    try:
        # Keep the main thread alive
        api_server.server_thread.join()
    except KeyboardInterrupt:
        print("\nStopping server...")
        api_server.stop()