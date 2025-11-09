import socket


class SaproSocket:
    """demonstration class only
      - coded for clarity, not efficiency
    """

    def __init__(self, sock=None):
        if sock is None:
            self.sock = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock

    def connect(self, host, port):
        self.sock.settimeout(20)
        self.sock.connect((host, port))
        self.sock.settimeout(None)

    def send(self, msg, size):
        totalsent = 0
        while totalsent < size:
            sent = self.sock.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent = totalsent + sent

    def recv(self, size):
        chunks = []  # bytearray(size)
        bytes_recd = 0
        while bytes_recd < size:
            chunk = self.sock.recv(size - bytes_recd)
            if chunk == b'':
                raise RuntimeError("socket connection broken")
            chunks.append(chunk)
            bytes_recd = bytes_recd + len(chunk)
        # return chunks
        return b''.join(chunks)
        # return bytearray.join(chunks)

    def close(self):
        self.sock.close()
