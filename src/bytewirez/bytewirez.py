"""
Bytewirez: A library for comfortable binary data reading, writing, and structure tracking.
"""
import io
import os
import struct
from functools import wraps
from itertools import count
from typing import Any, Dict, List, Optional, Tuple, Union, BinaryIO

import logging
logger = logging.getLogger(__name__)

ENDIAN_BIG    = ">"
ENDIAN_LITTLE = "<"


class IncrementalNameGenerator:
    """Generates incremental names for items when a name is not provided."""
    def __init__(self, start: int = 0, item_format: str = "{name}__{count}"):
        self._count = count(start)
        self.item_format = item_format

    def next(self, name: str = "ITEM") -> str:
        return self.item_format.format(name=name, count=next(self._count))


def unpack_ex(fmt: str, data: bytes, into: Optional[List[str]] = None) -> Any:
    """
    Extended struct.unpack that can return a dictionary if 'into' is provided.
    """
    parts = struct.unpack(fmt, data)
    if not parts:
        return None
    if not into:
        return parts[0] if len(parts) == 1 else parts
    
    if len(parts) > len(into):
        raise struct.error(f"unpack_ex: too many values unpacked ({len(parts)}) for names provided ({len(into)})!")
    
    return dict(zip(into, parts))


def make_hookable(func):
    """Decorator to allow pre and post hooks for instance methods."""
    f_name = func.__name__

    @wraps(func)
    def _new_func(self, *a, **kw):
        pre_hooks = getattr(self, "_pre_hooks", {}).get(f_name, [])
        for hook in pre_hooks:
            tmp = hook(*a, **kw)
            if tmp is not None:
                a, kw = tmp
        
        result = func(self, *a, **kw)
        
        post_hooks = getattr(self, "_post_hooks", {}).get(f_name, [])
        for hook in post_hooks:
            result = hook(result)
        return result

    setattr(_new_func, '__is_hookable', True)
    return _new_func


def hexdump(
    src: bytes,
    bytes_per_line: int = 16,
    hex_per_group: int = 0,
    char_per_group: int = 0,
    offset: int = 0,
    subst: str = '.'
) -> str:
    """Returns a formatted hexdump string of the provided bytes."""
    if not src:
        return ""

    lines = []
    max_addr_len = len(hex(len(src) + offset)) - 2 # estimate
    max_addr_len = max(max_addr_len, 4)

    hex_per_group = hex_per_group or bytes_per_line
    char_per_group = char_per_group or bytes_per_line

    hex_pad = bytes_per_line * 2 + (bytes_per_line // hex_per_group) - (1 if bytes_per_line % hex_per_group == 0 else 0)
    str_pad = bytes_per_line + (bytes_per_line // char_per_group) - (1 if bytes_per_line % char_per_group == 0 else 0)

    for addr in range(0, len(src), bytes_per_line):
        chars = src[addr : addr + bytes_per_line]
        hex_parts = []
        printable_parts = []

        for i in range(0, len(chars), hex_per_group):
            chunk = chars[i : i + hex_per_group]
            hex_parts.append("".join(f"{c:02X}" for c in chunk))
        
        for i in range(0, len(chars), char_per_group):
            chunk = chars[i : i + char_per_group]
            printable_parts.append("".join(chr(c) if 32 <= c <= 126 else subst for c in chunk))

        hex_str = " ".join(hex_parts).ljust(hex_pad)
        printable = " ".join(printable_parts).ljust(str_pad)
        
        lines.append(f'0x{(offset + addr):0{max_addr_len}X} | {hex_str} | {printable} |')
    
    return '\n'.join(lines)





class Wire:
    """
    Provides an interface for comfortable reading and writing of bytes.
    Wraps a file-like object (BytesIO, file descriptor, etc.).
    """
    def __init__(
        self,
        from_fd: Optional[BinaryIO] = None,
        from_bytes: Optional[bytes] = None,
        from_string: Optional[str] = None
    ):
        if from_fd is not None:
            self._obj = from_fd
        elif from_bytes is not None:
            self._obj = io.BytesIO(from_bytes)
        elif from_string is not None:
            self._obj = io.BytesIO(from_string.encode('utf-8'))
        else:
            logger.info("Initialized with empty BytesIO")
            self._obj = io.BytesIO(b"")
        
        self._pos_stack: List[int] = []
        self._endian: str = ENDIAN_BIG
        self._pre_hooks: Dict[str, List] = {}
        self._post_hooks: Dict[str, List] = {}
        
        self._post_init()

    @classmethod
    def from_bytes(cls, b: bytes) -> 'Wire':
        return cls(from_bytes=b)

    @classmethod
    def from_fd(cls, fd: BinaryIO) -> 'Wire':
        return cls(from_fd=fd)
    
    @classmethod
    def from_string(cls, s: str) -> 'Wire':
        return cls(from_string=s)
    
    def _post_init(self):
        for key in dir(self):
            attr = getattr(self, key)
            if getattr(attr, '__is_hookable', False):
                self._pre_hooks[key] = []
                self._post_hooks[key] = []
        self.initialize()

    def initialize(self):
        """Optional initialization method for subclasses."""
        pass

    def install_hook(self, func, pre=None, post=None):
        """Installs pre or post hooks for a hookable method."""
        name = func.__name__
        if pre:
            self._pre_hooks[name].append(pre)
        if post:
            self._post_hooks[name].append(post)

    def hexdump(self, size: int = 128, start_at: Optional[int] = None) -> str:
        """Returns a hexdump of a portion of the data."""
        blob = self.peek(size, at=start_at)
        return hexdump(blob, offset=start_at if start_at is not None else self.get_pos())

    def dump(self) -> bytes:
        """Returns the entire contents of the underlying object if possible."""
        if hasattr(self._obj, 'getvalue'):
            return self._obj.getvalue()
        # For files, we might need to read all, but that's risky.
        # Original code used getvalue() blindly.
        return b""

    def set_endian(self, e: str):
        """Sets the endianness ('>' for big, '<' for little)."""
        assert e in (ENDIAN_BIG, ENDIAN_LITTLE), f"Endian should be {ENDIAN_BIG} or {ENDIAN_LITTLE}"
        self._endian = e
        
    def get_endian(self) -> str:
        """Returns the current endianness."""
        return self._endian

    def fix_endian(self, fmt: str) -> str:
        """Prepends the current endianness to the format string if missing."""
        if fmt and fmt[0] not in "><@=!" and self._endian:
            return self._endian + fmt
        return fmt

    def pushd(self):
        """Pushes the current position onto a stack."""
        self._pos_stack.append(self.get_pos())

    def popd(self):
        """Pops a position from the stack and seeks to it."""
        if not self._pos_stack:
            raise IndexError("popd from empty position stack")
        self.goto(self._pos_stack.pop())

    def peekn(self, size: int) -> bytes:
        """Peeks exactly n bytes, raising an error if fewer are available."""
        b = self.peek(size)
        if len(b) != size:
            raise EOFError(f"Failed to peek {size} bytes, got {len(b)}")
        return b

    def readn(self, size: int) -> bytes:
        """Reads exactly n bytes, raising an error if fewer are available."""
        b = self.read(size)
        if len(b) != size:
            raise EOFError(f"Failed to read {size} bytes, got {len(b)}")
        return b

    def peek(self, size: int, at: Optional[int] = None) -> bytes:
        """Peeks bytes without moving the current position."""
        self.pushd()
        if at is not None:
            if at < 0:
                self._obj.seek(at, os.SEEK_CUR)
            else:
                self._obj.seek(at, os.SEEK_SET)
        value = self._obj.read(size)
        self.popd()
        return value

    @make_hookable
    def write(self, b: bytes) -> int:
        """Writes bytes to the stream."""
        return self._obj.write(b)

    @make_hookable
    def read(self, n: Optional[int] = None) -> bytes:
        """Reads bytes from the stream."""
        return self._obj.read(n)

    def bytes_available(self) -> int:
        """Returns the number of bytes remaining in the stream."""
        pos = self.get_pos()
        self._obj.seek(0, os.SEEK_END)
        end = self.get_pos()
        self._obj.seek(pos, os.SEEK_SET)
        return end - pos

    def get_pos(self) -> int:
        """Returns the current position."""
        return self._obj.tell()

    def goto(self, p: int):
        """Seeks to an absolute position."""
        self._obj.seek(p, os.SEEK_SET)

    def goto_begin(self):
        """Seeks to the beginning of the stream."""
        self.goto(0)

    def goto_end(self):
        """Seeks to the end of the stream."""
        self._obj.seek(0, os.SEEK_END)

    @make_hookable
    def read_fmt(self, fmt: str, into_dict: Optional[List[str]] = None) -> Any:
        """Reads data using a struct format string."""
        fmt = self.fix_endian(fmt)
        sz = struct.calcsize(fmt)
        b = self.readn(sz)
        return unpack_ex(fmt, b, into_dict)

    def peek_fmt(self, fmt: str, into_dict: Optional[List[str]] = None) -> Any:
        """Peeks data using a struct format string."""
        fmt = self.fix_endian(fmt)
        sz = struct.calcsize(fmt)
        b = self.peekn(sz)
        return unpack_ex(fmt, b, into_dict)

    def write_fmt(self, fmt: str, *args):
        """Writes data using a struct format string."""
        fmt = self.fix_endian(fmt)
        return self.write(struct.pack(fmt, *args))

    def write_hex(self, hex_string: str) -> int:
        """Writes bytes from a hex string."""
        return self.write(bytes.fromhex(hex_string))

    def _read_single(self, fmt: str) -> Any:
        return self.read_fmt(fmt)

    def _write_single(self, fmt: str, val: Any) -> int:
        return self.write_fmt(fmt, val)

    def peek_byte(self) -> int:
        return self.peek_fmt("B")

    def read_byte(self) -> int: return self._read_single("B")
    def read_word(self) -> int: return self._read_single("H")
    def read_dword(self) -> int: return self._read_single("I")
    def read_qword(self) -> int: return self._read_single("Q")
    def read_sbyte(self) -> int: return self._read_single("b")
    def read_sword(self) -> int: return self._read_single("h")
    def read_sdword(self) -> int: return self._read_single("i")
    def read_sqword(self) -> int: return self._read_single("q")

    def write_byte(self, val: int): self._write_single("B", val)
    def write_word(self, val: int): self._write_single("H", val)
    def write_dword(self, val: int): self._write_single("I", val)
    def write_qword(self, val: int): self._write_single("Q", val)
    def write_sbyte(self, val: int): self._write_single("b", val)
    def write_sword(self, val: int): self._write_single("h", val)
    def write_sdword(self, val: int): self._write_single("i", val)
    def write_sqword(self, val: int): self._write_single("q", val)



##
## Structure reader stuff here
##


from dataclasses import dataclass, field

@dataclass
class StructItem:
    """Base class for all structural items."""
    pos: int = 0
    size: int = 0
    kind: str = "ABSTRACT"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "TYPE": self.kind,
            "POS": self.pos,
            "SIZE": self.size,
        }

    def __json__(self) -> Dict[str, Any]:
        return self.to_dict()

@dataclass
class DataItem(StructItem):
    """Represents a leaf node containing raw data."""
    raw: bytes = b""
    fmt: Optional[str] = None
    kind: str = "DATA"

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        if self.fmt:
            result["format"] = self.fmt
            try:
                unpacked = struct.unpack(self.fmt, self.raw)
                result["data_fmt"] = unpacked[0] if len(unpacked) == 1 else unpacked
            except (struct.error, TypeError):
                logger.warning(f"Failed to unpack data at {self.pos} with format {self.fmt}")
        
        result["data_hex"] = self.raw.hex()
        return result

@dataclass
class StructItemObject(StructItem):
    """Represents a collection of named fields."""
    items: List[Tuple[str, StructItem]] = field(default_factory=list)
    class_name: Optional[str] = None
    kind: str = "OBJECT"

    def add(self, name: str, item: StructItem):
        self.size += item.size
        self.items.append((name, item))

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        if self.class_name:
            result["CLASS"] = self.class_name
        result['FIELDS'] = self.items
        return result



@dataclass
class StructItemList(StructItem):
    """Represents a collection of ordered items."""
    items: List[StructItem] = field(default_factory=list)
    kind: str = "LIST"

    def add(self, item: StructItem):
        self.size += item.size
        self.items.append(item)

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result["ITEMS"] = self.items
        return result





class MagicStructReaderContextManager:
  """
  Used to provide context-manager for StructureReader
  """
  def __init__(self, parent, obj, comment=""):
    self.parent = parent
    self.obj = obj
    self.comment = type(obj).__name__
    if comment != "" :
      self.comment + " // " + comment

  def __enter__(self):
    logger.debug(f" >>>> {self.comment}")
    self.parent._struct_depth += 1

  def __exit__(self, *a, **kw):
    self.parent._struct_depth -= 1
    logger.debug(f" <<<< {self.comment}")
    self.parent.end_item(*a, **kw)


class MagicProxyObject:
  _parent = None

  def __init__(self, parent):
    self._parent = parent

  def __getattr__(self, __name: str):
    if __name.startswith("start_"):
      return getattr(self._parent,__name)
    return getattr(self._parent._wire,__name)

class StructureReader:
    """
    Tracks the structure of binary data as it is being read from a Wire.
    """
    def __init__(self, wire: Wire):
        self._wire = wire
        self._item_stack: List[StructItem] = []
        self._names_stack: List[str] = []
        self._struct_depth = 0
        self._last_format: Optional[str] = None
        self._current_item: Optional[DataItem] = None
        self._data = bytearray()
        
        # Start with a root object
        root = StructItemObject(pos=self._wire.get_pos())
        self._item_stack.append(root)

        wire.install_hook(wire.read, pre=self._hook_pre_read, post=self._hook_post_read)
        wire.install_hook(wire.read_fmt, pre=self._hook_pre_fmt_read, post=self._hook_post_fmt_read)

    def _hook_pre_read(self, size: int, *args, **kwargs):
        logger.debug(f"HOOK PRE-READ {size}")
        self._current_item = DataItem(pos=self._wire.get_pos(), size=size, fmt=self._last_format)
        self._last_format = None
        return None

    def _hook_post_read(self, result: bytes):
        if self._current_item is None:
            logger.error("current_item is None in post-read hook")
            return result
            
        logger.debug(f"HOOK POST-READ {len(result)} bytes")
        self._current_item.raw = result
        self._append_to_current(self._current_item)
        self._current_item = None
        self._data.extend(result)
        return result

    def _hook_pre_fmt_read(self, fmt: str, *args, **kwargs):
        logger.debug(f"HOOK PRE-FMT-READ {fmt}")
        self._last_format = fmt
        return None

    def _hook_post_fmt_read(self, result):
        logger.debug(f"HOOK POST-FMT-READ {result}")
        return result

    def will_read(self, *names: str) -> MagicProxyObject:
        """Queues names for the next items to be read."""
        for name in reversed(names):
            self._names_stack.append(name)
        return MagicProxyObject(self)

    def start_object(self, class_name: str = "", comment: str = "") -> MagicStructReaderContextManager:
        """Starts a new nested object context."""
        obj = StructItemObject(class_name=class_name, pos=self._wire.get_pos())
        self._push_item(obj)
        return MagicStructReaderContextManager(self, obj, comment)

    def start_list(self, comment: str = "") -> MagicStructReaderContextManager:
        """Starts a new nested list context."""
        obj = StructItemList(pos=self._wire.get_pos())
        self._push_item(obj)
        return MagicStructReaderContextManager(self, obj, comment)

    def _append_to_current(self, o: StructItem):
        top = self.last_item()
        if isinstance(top, StructItemObject):
            name = self._names_stack.pop() if self._names_stack else f"item_{len(top.items):05}"
            top.add(name, o)
        elif isinstance(top, StructItemList):
            top.add(o)
        else:
            raise TypeError(f"Cannot append to item of type {type(top)}")

    def _push_item(self, o: StructItem):
        self._append_to_current(o)
        self._item_stack.append(o)

    def last_item(self) -> StructItem:
        return self._item_stack[-1]

    def end_item(self, exc_type, exc_val, exc_tb):
        """Ends the current structural context."""
        top = self._item_stack.pop()
        self.last_item().size += top.size
        
        if exc_type:
            import traceback
            logger.error(f"Error ending item at depth {len(self._item_stack)}")
            logger.error(f"Exception: {exc_type.__name__}: {exc_val}")
            # traceback.print_tb(exc_tb)

    def get_root_element(self) -> StructItem:
        return self._item_stack[0]

    def get_data(self) -> bytes:
        return bytes(self._data)





    def output_imHex(self) -> str:
        """Generates imHex pattern language representation."""
        parts = []
        root_el = self.get_root_element()
        counter = IncrementalNameGenerator()
        
        # Simple mapping for imHex types
        IMHEX_TYPES = {
            ">H": "u16", ">I": "u32", ">Q": "u64", ">B": "u8",
            "<H": "u16", "<I": "u32", "<Q": "u64", "<B": "u8",
            "H": "u16", "I": "u32", "Q": "u64", "B": "u8",
        }

        def _parse(el) -> Tuple[str, int]:
            if isinstance(el, StructItemList):
                name = counter.next("ARRAY")
                struct_lines = [f"struct {name} {{"]
                for i, item in enumerate(el.items):
                    item_type, n = _parse(item)
                    suffix = f"[{n}]" if n > 1 else ""
                    struct_lines.append(f"  {item_type} ITEM_{i}{suffix};")
                struct_lines.append("};")
                parts.append("\n".join(struct_lines))
                return name, 1
            
            if isinstance(el, StructItemObject):
                name = counter.next("OBJECT")
                struct_lines = [f"struct {name} {{"]
                for prop, val in el.items:
                    item_type, n = _parse(val)
                    suffix = f"[{n}]" if n > 1 else ""
                    struct_lines.append(f"  {item_type} {prop}{suffix};")
                struct_lines.append("};")
                parts.append("\n".join(struct_lines))
                return name, 1
            
            if isinstance(el, DataItem):
                return IMHEX_TYPES.get(el.fmt, "u8"), el.size
            
            return "u8", 1

        root_name, _ = _parse(root_el)
        parts.append(f"{root_name} root @ 0x00;")
        return "\n\n".join(parts)

    def output_kaitai(self):
        """Placeholder for Kaitai Struct output."""
        pass


def structure_to_html_viewer(st: StructureReader, into_file=None):
    """Serializes the structure for the HTML viewer."""
    data = {
        "data_hex": st.get_data().hex(), 
        "struct": st.get_root_element()
    }
    return custom_json_serializer(data, into_file=into_file)


def custom_json_serializer(obj: Any, into_file=None):
    """JSON serializer that handles objects with __json__ methods."""
    import json

    def default_handler(o):
        if hasattr(o, "__json__"):
            return o.__json__()
        raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")
    
    if into_file is None:
        return json.dumps(obj, default=default_handler, indent=2)
    return json.dump(obj, into_file, default=default_handler, indent=2)


def structure_to_yaml(reader: StructureReader):
    """Serializes the structure to YAML."""
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML is required for YAML serialization. Please install it with 'pip install pyyaml'")
    root = reader.get_root_element()
    return yaml.dump(root.__json__(), default_flow_style=False)


if __name__ == "__main__":
    print("Bytewirez library loaded.")




