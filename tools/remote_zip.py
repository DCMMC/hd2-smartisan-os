"""Read a historical ROM ZIP over HTTP Range without downloading its payload."""
import io
import requests

class RemoteFile(io.RawIOBase):
    def __init__(self, url, size, blocksize=1024*1024):
        self.url, self.size, self.blocksize = url, size, blocksize
        self.pos, self.cache = 0, {}
        self.session = requests.Session()

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else (self.pos if whence == 1 else self.size) + offset
        if self.pos < 0:
            raise ValueError('Negative seek')
        return self.pos

    def read(self, length=-1):
        end = self.size if length < 0 else min(self.size, self.pos + length)
        result = bytearray()
        while self.pos < end:
            block = self.pos // self.blocksize
            if block not in self.cache:
                start = block * self.blocksize
                last = min(self.size, start + self.blocksize) - 1
                response = self.session.get(self.url, headers={'Range': f'bytes={start}-{last}'}, timeout=60)
                response.raise_for_status()
                if response.status_code != 206 or len(response.content) != last-start+1:
                    raise ValueError('Server did not honor byte range')
                self.cache[block] = response.content
            offset = self.pos % self.blocksize
            chunk = self.cache[block][offset:offset + end-self.pos]
            if not chunk:
                raise EOFError('Truncated remote ZIP')
            result.extend(chunk)
            self.pos += len(chunk)
        return bytes(result)
