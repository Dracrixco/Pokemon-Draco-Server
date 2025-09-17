"""
Main server module for the Pokemon Cable Club Server.
Contains the Server class and main networking logic.
"""

import select
import socket
import logging

from config import RULES_REFRESH_RATE
from models import State, Connecting, Finding, Connected, public_id
from protocol import RecordParser, RecordWriter
from validation import make_party_validator
from rules import find_changed_files, load_rules_files
from api_server import APIServer


class Server:
    """Main server class that handles client connections and matchmaking."""
    
    def __init__(self, host, port, pbs_dir, rules_dir, api_port=8080):
        self.valid_party = make_party_validator(pbs_dir)
        self.loop_count = 1
        _, self.rules_files = find_changed_files(rules_dir, {})
        self.rules = load_rules_files(rules_dir, self.rules_files)
        self.host = host
        self.port = port
        self.rules_dir = rules_dir
        self.socket = None
        self.clients = {}
        self.handlers = {
            Connecting: self.handle_connecting,
            Finding: self.handle_finding,
            Connected: self.handle_connected,
        }
        
        # Initialize API server
        self.api_server = APIServer(host, api_port)
        self.api_server.start()

    def run(self):
        """Start the server and run the main loop."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self.socket:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.socket.bind((self.host, self.port))
                logging.info('Started Server on %s:%d', self.host, self.port)
                self.socket.listen()
                while True:
                    try:
                        self.loop()
                    except KeyboardInterrupt:
                        logging.info('Stopping Server')
                        break
        finally:
            # Stop API server when main server stops
            self.api_server.stop()

    def loop(self):
        """Main server loop iteration."""
        # Check for rule changes periodically
        if (self.loop_count % RULES_REFRESH_RATE) == 0:
            reload_rules, rule_files = find_changed_files(self.rules_dir, self.rules_files)
            if reload_rules:
                self.rules_files = rule_files
                self.rules = load_rules_files(self.rules_dir, self.rules_files)
            self.loop_count = 0
        self.loop_count += 1
        
        # Prepare socket lists for select()
        reads = list(self.clients)
        reads.append(self.socket)
        writes = [s for s, st in self.clients.items() if st.send_buffer]
        readable, writeable, errors = select.select(reads, writes, reads, 1.0)
        
        # Handle errors
        for s in errors:
            if s is self.socket:
                raise Exception("error on listening socket")
            else:
                self.disconnect(s)

        # Handle writes
        for s in writeable:
            st = self.clients[s]
            try:
                n = s.send(st.send_buffer)
            except Exception as e:
                self.disconnect(s, e)
            else:
                st.send_buffer = st.send_buffer[n:]

        # Handle reads
        for s in readable:
            if s is self.socket:
                # New connection
                s, address = self.socket.accept()
                s.setblocking(False)
                st = self.clients[s] = State(address)
                logging.info('%s: connect', st)
            else:
                # Data from existing client
                st = self.clients[s]
                try:
                    recvd = s.recv(4096)
                except ConnectionResetError as e:
                    self.disconnect(s)
                else:
                    if recvd:
                        recv_buffer = st.recv_buffer + recvd
                        while True:
                            message, _, recv_buffer = recv_buffer.partition(b"\n")
                            if not _:
                                # No newline, buffer the partial message.
                                st.recv_buffer = message
                                break
                            else:
                                try:
                                    # Handle the message.
                                    self.handlers[type(st.state)](s, st, message)
                                except Exception as e:
                                    logging.exception('Server Error', exc_info=e)
                                    self.disconnect(s, "server error")
                    else:
                        # Zero-length read from a non-blocking socket is a disconnect.
                        self.disconnect(s, "client disconnected")

    def connect(self, s, s_):
        """Connect two clients together for a battle."""
        connections = [(0, s_, s), (1, s, s_)]
        
        # Send connection info to both clients
        for number, s, s_ in connections:
            st = self.clients[s]
            st_ = self.clients[s_]
            writer = RecordWriter()
            writer.str("found")
            writer.int(number)
            writer.str(st_.state.name)
            writer.str(st_.state.trainertype)
            writer.int(st_.state.win_text)
            writer.int(st_.state.lose_text)
            writer.raw(st_.state.party)
            self.write_server_rules(writer)
            writer.send(st)

        # Update states to Connected
        for _, s, s_ in connections:
            st = self.clients[s]
            st.state = Connected(s_)

        # Log connections
        for _, s, s_ in connections:
            st = self.clients[s]
            st_ = self.clients[s_]
            logging.info('%s: connected to %s', st, st_)

    def disconnect(self, s, reason="unknown error"):
        """Disconnect a client."""
        try:
            st = self.clients.pop(s)
        except:
            pass
        else:
            try:
                writer = RecordWriter()
                writer.str("disconnect")
                writer.str(reason)
                writer.send_now(s)
                s.close()
            except Exception:
                pass
            logging.info('%s: disconnected (%s)', st, reason)
            if isinstance(st.state, Connected):
                self.disconnect(st.state.peer, "peer disconnected")

    def handle_connecting(self, s, st, message):
        """Handle messages from clients in the Connecting state."""
        record = RecordParser(message.decode("utf8", errors="replace"))
        if record.str() != "find":
            self.disconnect(s, "bad assert")
        else:
            version = record.str()
            if (1==2): # not StrictVersion(version) >= GAME_VERSION:
                self.disconnect(s, "invalid version")
            else:
                peer_id = record.int()
                name = record.str()
                id = record.int()
                ttype = record.str()
                win_text = record.int()
                lose_text = record.int()
                party = record.raw_all()
                logging.debug('%s: Trainer %s, id %d (%s) -> Searching %d', 
                             st, name, public_id(id), hex(id), peer_id)
                if (1==2): #not self.valid_party(record):
                    self.disconnect(s, "invalid party")
                else:
                    st.state = Finding(peer_id, name, id, ttype, party, win_text, lose_text)
                    # Is the peer already waiting?
                    for s_, st_ in self.clients.items():
                        if (st is not st_ and
                            isinstance(st_.state, Finding) and
                            public_id(st_.state.id) == peer_id and
                            st_.state.peer_id == public_id(id)):
                            self.connect(s, s_)

    def handle_finding(self, s, st, message):
        """Handle messages from clients in the Finding state."""
        logging.info('%s: message dropped (no peer)', st)

    def handle_connected(self, s, st, message):
        """Handle messages from clients in the Connected state."""
        st_ = self.clients.get(st.state.peer)
        if st_:
            st_.send_buffer += message + b"\n"
        else:
            logging.info('%s: message dropped (no peer)', st)
    
    def write_server_rules(self, writer):
        """Write server rules to a RecordWriter."""
        writer.int(len(self.rules))
        for r in self.rules:
            writer.raw(r)