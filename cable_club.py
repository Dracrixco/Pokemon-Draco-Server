"""
Pokemon Cable Club Server - Main Entry Point

This is the v20\v21 version of the server. It is not compatible with earlier versions of the script.
"""

import argparse
import logging
import os.path

from config import HOST, PORT, PBS_DIR, LOG_DIR, RULES_DIR
from server import Server

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pokemon Cable Club Server")
    parser.add_argument("--host", default=HOST, 
                       help='The host IP Address to run this server on. Should be 0.0.0.0 for Google Cloud.')
    parser.add_argument("--port", default=PORT, 
                       help='The port the server is listening on.')
    parser.add_argument("--pbs_dir", default=PBS_DIR, 
                       help='The path, relative to the working directory, where the PBS files are located.')
    parser.add_argument("--rules_dir", default=RULES_DIR, 
                       help='The path, relative to the working directory, where the rules files are located.')
    parser.add_argument("--log", default="INFO", 
                       help='The log level of the server. Logging messages lower than the level are not written.')
    
    args = parser.parse_args()
    
    # Configure logging
    loglevel = getattr(logging, args.log.upper())
    if not isinstance(loglevel, int):
        raise ValueError('Invalid log level: %s' % loglevel)
    logging.basicConfig(
        format='%(asctime)s: %(levelname)s: %(message)s', 
        filename=os.path.join(LOG_DIR, 'server.log'), 
        level=loglevel
    )
    logging.info('---------------')
    
    # Start the server
    try:
        Server(args.host, int(args.port), args.pbs_dir, args.rules_dir).run()
    finally:
        logging.shutdown()
