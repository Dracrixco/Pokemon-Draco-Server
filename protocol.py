"""
Protocol handling classes for the Pokemon Cable Club Server.
Contains RecordParser and RecordWriter for communication protocol.
"""


class RecordParser:
    """Parser for incoming messages from clients."""
    
    def __init__(self, line):
        self.fields = []
        field = ""
        escape = False
        for c in line:
            if c == "," and not escape:
                self.fields.append(field)
                field = ""
            elif c == "\\" and not escape:
                escape = True
            else:
                field += c
                escape = False
        self.fields.append(field)
        self.fields.reverse()

    def bool(self):
        return {'true': True, 'false': False}[self.fields.pop()]

    def bool_or_none(self):
        return {'true': True, 'false': False, '': None}[self.fields.pop()]

    def int(self):
        return int(self.fields.pop())

    def int_or_none(self):
        field = self.fields.pop()
        if not field:
            return None
        else:
            return int(field)

    def str(self):
        return self.fields.pop()

    def raw_all(self):
        return list(reversed(self.fields))


class RecordWriter:
    """Writer for outgoing messages to clients."""
    
    def __init__(self):
        self.fields = []

    def send_now(self, s):
        """Send the message immediately through a socket."""
        line = ",".join(RecordWriter.escape(f) for f in self.fields)
        line += "\n"
        s.send(line.encode("utf-8"))

    def send(self, st):
        """Add the message to a state's send buffer."""
        line = ",".join(RecordWriter.escape(f) for f in self.fields)
        line += "\n"
        st.send_buffer += line.encode("utf-8")

    @staticmethod
    def escape(f):
        """Escape commas and backslashes in field content."""
        return f.replace("\\", "\\\\").replace(",", "\\,")

    def int(self, i):
        """Add an integer field."""
        self.fields.append(str(i))

    def str(self, s):
        """Add a string field."""
        self.fields.append(s)

    def raw(self, fs):
        """Add raw fields (list of strings)."""
        self.fields.extend(fs)