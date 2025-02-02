import logging
import operator
import struct
from io import BytesIO, RawIOBase

log = logging.getLogger(__name__)

def read_load_immediate_r0(f):
    if f.read(2) != b"\x38\x00":
        raise RuntimeError("Invalid instruction")
    else:
        return struct.unpack(">h", f.read(2))[0]

def write_load_immediate_r0(f, val):
    f.write(b"\x38\x00")
    f.write(struct.pack(">h", val))


def read_float(f):
    return struct.unpack(">f", f.read(4))[0]

def write_float(f, val):
    f.write(struct.pack(">f", val))

def read_ubyte(f):
    return struct.unpack("B", f.read(1))[0]
    
def read_ushort(f):
    return struct.unpack(">H", f.read(2))[0]

def read_uint32(f):
    return struct.unpack(">I", f.read(4))[0]

def write_uint32(f, val):
    f.write(struct.pack(">I", val))

def write_uint32_offset(f, val, offset):
    f.seek(offset)
    f.write(struct.pack(">I", val))


class UnmappedAddress(Exception):
    pass
    
class SectionCountFull(Exception):
    pass

class DolFile(object):
    def __init__(self, f):
        self._rawdata = BytesIO(f.read())
        f.seek(0)
        fileoffset = 0
        addressoffset = 0x48
        sizeoffset = 0x90 
        
        self._text = []
        self._data = []
        
        nomoretext = False 
        nomoredata = False
        
        self._current_end = None 
        
        # Read text and data section addresses and sizes 
        for i in range(18):
            f.seek(fileoffset+i*4)
            offset = read_uint32(f)
            f.seek(addressoffset+i*4)
            address = read_uint32(f)
            f.seek(sizeoffset+i*4)
            size = read_uint32(f)
            
            if i <= 6:
                if offset != 0:
                    self._text.append((offset, address, size))
                    log.debug(f"text{i} {hex(offset)} {hex(address)} {hex(size)}")
            else:
                datanum = i - 7
                if offset != 0:
                    self._data.append((offset, address, size))
                    log.debug(f"text{i} {hex(offset)} {hex(address)} {hex(size)}")
        
        f.seek(0xD8)
        self.bssaddr = read_uint32(f)
        self.bsssize = read_uint32(f)
        
        #self.bss = BytesIO(self._rawdata.getbuffer()[self._bssaddr:self._bssaddr+self.bsssize])
        
        self._curraddr = self._text[0][1]
        self.seek(self._curraddr)

    def get_raw_data(self) -> BytesIO:
        return self._rawdata

    @property
    def sections(self):
        for i in self._text:
            yield i
        for i in self._data:
            yield i 
        
        return

    def is_address_resolvable(self, gc_addr: int) -> bool:
        for _offset, address, size in self.sections:
            if address <= gc_addr < address + size:
                return True
        return False

    # Internal function for resolving a gc address 
    def _resolve_address(self, gc_addr):
        for offset, address, size in self.sections:
            if address <= gc_addr < address+size:
                return offset, address, size 
        """for offset, address, size in self._text:
            if address <= gc_addr < address+size:
                return offset, address, size 
        for offset, address, size in self._data:
            if address <= gc_addr < address+size:
                return offset, address, size """
        
        raise UnmappedAddress("Unmapped address: {0}".format(hex(gc_addr)))
    
    def _adjust_header(self):
        curr = self._rawdata.tell()
        fileoffset = 0
        addressoffset = 0x48
        sizeoffset = 0x90 
        f = self._rawdata 
        
        i = 0
        for offset, address, size in self._text:
            f.seek(fileoffset+i*4)
            write_uint32(f, offset)
            f.seek(addressoffset+i*4)
            write_uint32(f, address)
            f.seek(sizeoffset+i*4)
            write_uint32(f, size)
            i += 1 
            
        i = 7
        for offset, address, size in self._data:
            f.seek(fileoffset+i*4)
            write_uint32(f, offset)
            f.seek(addressoffset+i*4)
            write_uint32(f, address)
            f.seek(sizeoffset+i*4)
            write_uint32(f, size)
            i += 1 
                
        f.seek(0xD8)
        write_uint32(f, self.bssaddr)
        write_uint32(f, self.bsssize)
        
        f.seek(curr)

    def can_write_or_read_in_current_section(self, size: int) -> bool:
        return self._curraddr + size <= self._current_end

    def check_section_and_grow_if_needed(self, gc_addr: int, gc_size: int) -> tuple[bool, str]:
        assert gc_size > 0
        gc_end_addr = gc_addr + gc_size

        sections = tuple(self.sections)

        # Check whether the section already exists and can fit the size.
        for _offset, address, size in sections:
            end_address = address + size
            if address <= gc_addr < end_address and address < gc_end_addr <= end_address:
                return True, ''

        sorted_sections = sorted(sections, key=operator.itemgetter(1))

        # Find the section that precedes the input address; this will be the section that needs to
        # grow.
        for section in reversed(sorted_sections):
            offset, address, size = section
            if address <= gc_addr:
                break
        else:
            return False, f'Unable to find suitable section for 0x{gc_addr:08X}.'

        # Check how much it needs to grow.
        end_address = address + size
        delta = gc_end_addr - end_address

        # Verify that the new section size would not overlap with the next section.
        if section is not sorted_sections[-1]:
            next_section = sorted_sections[sorted_sections.index(section) + 1]
            if end_address + delta > next_section[1]:
                return (
                    False,
                    f'Unable to grow section at 0x{address:08X} to fit {gc_size} bytes at '
                    f'0x{gc_addr:08X} (overlapping with next section at 0x{next_section[1]:08X}).',
                )

        # Advance offsets in sections that follow the target section and update section size in the
        # target section.
        new_text = []
        for section in self._text:
            if section[0] > offset:
                new_text.append((section[0] + delta, section[1], section[2]))
            elif section[1] == address:
                new_text.append((section[0], section[1], section[2] + delta))
            else:
                new_text.append(section)
        self._text.clear()
        self._text.extend(new_text)
        new_data = []
        for section in self._data:
            if section[0] > offset:
                new_data.append((section[0] + delta, section[1], section[2]))
            elif section[1] == address:
                new_data.append((section[0], section[1], section[2] + delta))
            else:
                new_data.append(section)
        self._data.clear()
        self._data.extend(new_data)

        # All good to update the DOL header.
        self._adjust_header()

        # And finally insert zeros at the back of the section.
        rawdata = bytes(self._rawdata.getbuffer())
        rawdata = rawdata[:offset + size] + b'\x00' * delta + rawdata[offset + size:]
        self._rawdata = BytesIO(rawdata)

        # Incapacitate `memset()` in `__init_data()` (same address in all known builds), as
        # otherwise it is likely that the data that is written to memory outside of the DOL sections
        # will be zeroed, making this work futile.
        self.seek(0x800033D8)
        self.write(struct.pack('>I', 0x60000000))
        # NOTE: Tests have shown that this should be safe: all the data that the `memset()` calls
        # would clear, except for one single 32-bit word written by `OSSetErrorHandler()`, is
        # already null. The word that `OSSetErrorHandler()` writes holds the address to the previous
        # error handler, which is returned to the caller in r3 (to allow the caller to restore the
        # previous handler, presumably). However, the next call to `OSSetErrorHandler()` does not
        # consume the return value (in fact, the value is discarded in absolutely all calls, even in
        # the debug build), therefore not zeroing the value is not an issue.

        return True, ''

    # Unsupported: Reading an entire dol file 
    # Assumption: A read should not go beyond the current section 
    def read(self, size):
        if self._curraddr + size > self._current_end:
            raise RuntimeError("Read goes over current section")
            
        return self._rawdata.read(size)
        self._curraddr += size  
        
    # Assumption: A write should not go beyond the current section 
    def write(self, data):
        if self._curraddr + len(data) > self._current_end:
            raise RuntimeError("Write goes over current section")
            
        self._rawdata.write(data)
        self._curraddr += len(data)
    
    def seek(self, addr):
        offset, gc_start, gc_size = self._resolve_address(addr)
        self._rawdata.seek(offset + (addr-gc_start))
        
        self._curraddr = addr 
        self._current_end = gc_start + gc_size 
        
    def _add_section(self, newsize, section, addr=None):
        if addr is not None:
            last_addr = addr 
        else:
            last_addr = 0
        last_offset = 0 
        
        for offset, address, size in self.sections:
            if last_addr < address+size:
                last_addr = address+size 
            if last_offset < offset + size:
                last_offset = offset+size 
        
        if last_addr < self.bssaddr+self.bsssize:
            last_addr = self.bssaddr+self.bsssize 
        
        section.append((last_offset, last_addr, newsize))
        curr = self._rawdata.tell()
        self._rawdata.seek(last_offset)
        self._rawdata.write(b" "*newsize)
        self._rawdata.seek(curr)
        
        return (last_offset, last_addr, newsize)
        
    def allocate_text_section(self, size, addr=None):
        assert len(self._text) <= 7 
        if len(self._text) >= 7:
            raise SectionCountFull("Maximum amount of text sections reached!")
        
        return self._add_section(size, self._text, addr)
    
    def allocate_data_section(self, size, addr=None):
        assert len(self._data) <= 11 
        if len(self._data) >= 11:
            raise SectionCountFull("Maximum amount of data sections reached!")
        
        return self._add_section(size, self._data, addr=None)
        
        
    def tell(self):
        return self._curraddr
    
    def save(self, f):
        self._adjust_header()
        f.write(self._rawdata.getbuffer())
    
    
    def print_info(self):
        log.info("Dol Info:")
        i = 0
        for offset, addr, size in self._text:
            log.info(f"text{0}: fileoffset {1:x}, addr {2:x}, size {3:x}".format(i, offset, addr, size))
            i += 1
        i = 0
        
        for offset, addr, size in self._data:
            log.info("data{0}: fileoffset {1:x}, addr {2:x}, size {3:x}".format(i, offset, addr, size))
            i += 1
            
        log.info("bss addr: {0:x}, bss size: {1:x}, bss end: {2:x}".format(self.bssaddr, self.bsssize,
                                                                            self.bssaddr+ self.bsssize))
        
if __name__ == "__main__":
    symbols = {}

    with open("GM4E01.map", "r") as f:
        for line in f:
            line = line.strip()
            split =  line.split(" ", 4)
            if len(split) < 5: 
                continue 
            _, _, address, _, symbol = split
            symbols[int(address, 16)] = symbol 


    with open("mkddus.dol", "rb") as f:
        dol = DolFile(f)
    
    dol.seek(0x803532e8)
    out = {}
    #with open("mkddobjects.txt", "w") as f: 
    for i in range(160):#0x84+100):
        log.info(i)
        objectid = read_ushort(dol)
        log.info(hex(objectid))
        assert dol.read(2) == b"\x00\x00"
        pointer = read_uint32(dol)
        assert dol.read(4) == b"\x00\x00\x00\x00"
        sym = symbols[pointer]
        start = sym.find("<")
        end = sym.find(">")
        
        objname = sym[start+1:end]
        
        while objname[0].isdigit():
            objname = objname[1:]
        
        #out[objectid] = "Object ID: {:x} (dec: {}) Object Name: {}\n".format(
        #    objectid, objectid, objname)
        
        out[objectid] = "\"{}\": \"{}\",\n".format(
            objectid, objname)
        
        
    with open("mkddobjects.json", "w") as f:
        f.write("{\n")
        for key in sorted(out.keys()):
            f.write(out[key])
        f.write("}\n")