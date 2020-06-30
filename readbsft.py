import struct 

def read_uint32(f):
    return struct.unpack(">I", f.read(4))[0]

def write_uint32(f, val):
    f.write(struct.pack(">I", val))

def read_string(f):
    out = b""
    next = f.read(1)
    while next != b"\x00":
        out += next 
        next = f.read(1)
    return str(out, encoding="ascii")

class BSFT(object):
    def __init__(self):
        self.tracks = []
    
    def from_file(self, f):
        self.tracks = []
        bsft_start = f.tell()
        magic = f.read(4)
        if magic != b"bsft":
            raise RuntimeError("File does not have bsft header!")
        
        entries = read_uint32(f)
        for i in range(entries):
            offset = read_uint32(f)
            curr = f.tell()
            f.seek(bsft_start+offset)
            self.tracks.append(read_string(f))
            f.seek(curr)
        
    def write_to_file(self, f):
        bsft_start = f.tell()
        f.write(b"bsft")
        write_uint32(f, len(self.tracks))
        offset_start = f.tell()
        offsets = []
        for i in range(len(self.tracks)):
            f.write(b"F00B")
            
        for path in self.tracks:
            offsets.append(f.tell()-bsft_start)
            f.write(bytes(path, encoding="ascii"))
            f.write(b"\x00")
        
        f.seek(offset_start)
        for offset in offsets:
            write_uint32(f, offset)
        
if __name__ == "__main__":
    import json 
    
    if True:
        with open("GCKart.bsft", "rb") as f:
            bsft = BSFT()
            bsft.from_file(f)
            
        with open("tracks.json", "w") as f:
            json.dump(bsft.tracks, f, indent=4)
    else:
        bsft = BSFT()
        with open("tracks.json", "r") as f:
            tracks = json.load(f)
        for track in tracks:
            bsft.tracks.append(track)
        with open("NewGCKart.bsft", "wb") as f:
            bsft.write_to_file(f)