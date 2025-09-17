"""
Data models and classes for the Pokemon Cable Club Server.
Contains all the data structures used throughout the application.
"""

import collections


# Named tuples for connection states
Connecting = collections.namedtuple('Connecting', '')
Finding = collections.namedtuple('Finding', 'peer_id name id trainertype party win_text lose_text')
Connected = collections.namedtuple('Connected', 'peer')


# Pokemon data structure
Pokemon = collections.namedtuple('Pokemon', 'genders abilities moves forms')


class Universe:
    """A class that contains everything - used for unlimited form sets."""
    def __contains__(self, item):
        return True


class State:
    """Represents the state of a client connection."""
    
    def __init__(self, address):
        self.address = address
        self.state = Connecting()
        self.send_buffer = b""
        self.recv_buffer = b""

    def __str__(self):
        return f"{self.address[0]}:{self.address[1]}/{type(self.state).__name__.lower()}"


def public_id(id_):
    """Extract the public portion of a trainer ID."""
    return id_ & 0xFFFF