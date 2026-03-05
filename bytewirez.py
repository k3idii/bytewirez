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


class StructItemAbstract:
  pos :int = 0
  size :int = 0
  kind = None

  def __init__(self, **kwargs) -> None:
    for k,v in kwargs.items():
      setattr(self, k, v)

  def _dump_basic(self):
    result = {}
    result["TYPE"] = self.kind
    result["POS"] = self.pos
    result["SIZE"] = self.size
    return result

class DataItem(StructItemAbstract):
  raw = b""
  fmt = None
  kind = "DATA"

  def __json__(self):
    result = self._dump_basic()
    if self.fmt is not None:
      print(f"FORMAT {self.fmt} << {self.raw}")
      result["format"] = self.fmt
      tmp =struct.unpack(self.fmt, self.raw)
      if len(tmp)==1:
        tmp = tmp[0]
      result["data_fmt"] = tmp
    result["data_hex"] = self.raw.hex()
    return result

class StructItemOBJECT(StructItemAbstract):
  items = None
  class_name = None
  kind = "OBJECT"

  def __init__(self, **kwargs) -> None:
    super().__init__(**kwargs)
    self.items = []

  def add(self, name, item):
    self.size += item.size
    self.items.append([name, item])

  def __json__(self):
    result = self._dump_basic()
    if self.class_name:
      result["CLASS"] = self.class_name
    result['FIELDS'] = self.items
    return result



class StructItemLIST(StructItemAbstract):
  items = None
  kind = "LIST"

  def __init__(self, **kwargs) -> None:
    super().__init__(**kwargs)
    self.items = []

  def add(self, item):
    self.size += item.size
    self.items.append(item)

  def __json__(self):
    result = self._dump_basic()
    result["ITEMS"] =  self.items
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
    Implements reading of basic (nested) structures/collections such as :
      - objects/dicts
      - lists/arrays


  """
  ## TODO: add structure writer. same stuff
  _bytes_so_far = 0
  _item_stack = None
  _struct_depth = 0
  _names_stack = None
  _last_format = None
  _current_item = None
  _data = b""
  _waiting_for_fmt = False
  main = None


  def __init__(self, wire: Wire):
    self._wire = wire
    self._item_stack = []   # queue ?
    self._names_stack = []  # queue ?

    # TODO: should we start with list or object ?
    self._item_stack.append(
      StructItemOBJECT(pos=self._wire.get_pos())
    )

    wire.install_hook(
      wire.read,
      pre=self._hook_pre_read,
      post=self._hook_post_read,
    )
    wire.install_hook(
      wire.read_fmt,
      pre=self._hook_pre_fmt_read,
      post=self._hook_post_fmt_read,
    )

  def _hook_pre_read(self, *a, **kw):
    size = a[0] # unpack args
    logger.debug(f"HOOK PRE-READ {size}")
    self._current_item = DataItem(pos=self._wire.get_pos(), size=size, fmt=self._last_format)
    self._last_format = None
    return None

  def _hook_post_read(self, result):
    ''' raw read bytes '''
    assert self._current_item is not None, "current_item is none. that should not happend (check pre-read hook)"
    logger.debug(f"HOOK POST-READ {result}")
    self._current_item.raw = result
    self._append_to_current(self._current_item)
    self._current_item = None
    self._data += result
    return result


  def _hook_pre_fmt_read(self, *a, **kw):
    self._waiting_for_fmt = True
    fmt = a[0]
    logger.debug(f"HOOK PRE-FMT-READ {fmt}")
    self._last_format = fmt
    return None

  def _hook_post_fmt_read(self, result):
    self._waiting_for_fmt = False
    logger.debug(f"HOOK POST-FMT-READ {result}")
    return result

  def will_read(self, *names):
    for item in names[::-1]:
      self._names_stack.append(item)
    return MagicProxyObject(self)

  def _try_get_name(self):
    # TODO: should stack-of-names be FIFO or LIFO  ?
    if len(self._names_stack) > 0:
      return self._names_stack.pop(0)
    #else:
    return ""


  def start_object(self, class_name="", comment=""):
    obj = StructItemOBJECT(class_name=class_name, pos=self._wire.get_pos())
    self._push_item(obj)
    logger.debug(f"START object")
    return MagicStructReaderContextManager(self, obj, comment)

  def start_list(self, comment=""):
    obj = StructItemLIST(pos=self._wire.get_pos())
    self._push_item(obj)
    logger.debug("START list")
    return MagicStructReaderContextManager(self, obj, comment)

  def _append_to_current(self, o):
    top = self.last_item()
    parent_type = type(top)
    assert parent_type in [StructItemLIST, StructItemOBJECT], "This should not be possible"
    #print(parent_type)
    if parent_type == StructItemOBJECT:
      # Object - requred item name OR will be automatically generated
      name = f"item_{len(top.items):05}"
      if len(self._names_stack)>0:
        name = self._names_stack.pop()
      else:
        logger.warning(f"!!! No names on stack ! will auto-generate one : {name}")
      #assert len(self._names_stack)>0, f"Need field name for property (object:{top.name})!"
      logger.debug(f"[+] object field: {name}")
      top.add( name, o)
    if parent_type == StructItemLIST:
      logger.debug("[+] list item ")
      top.add( o )
    #else:
    #  raise Exception("OMG !")

  def _push_item(self, o):
    self._append_to_current(o)
    self._item_stack.append(o)

  def last_item(self):
    return self._item_stack[-1]

  def end_item(self, exception_type, exception_value, exception_traceback):
    # called when exiting scope (Object OR List)
    logger.debug("END item")
    top = self._item_stack.pop()
    self.last_item().size += top.size
    if exception_type is None:
      return

    ## HANDLE un-clean end
    import traceback
    logger.error("  ** EXCEPTION ** ")
    logger.error(f"ERROR at {self.last_item().__class__.__name__}")
    for item in self._item_stack:
      logger.error(item.__class__.__name__)

    logger.error(f"-> type:{exception_type} : value:{exception_value}")
    logger.error(f"==> REASON:{0}",traceback.extract_tb(exception_traceback))

    raise exception_value # re-raise


  def get_root_element(self):
    return self._item_stack[0]

  def get_data(self):
    # or self._wire.dump()
    return self._data





  def output_imHex(self):
    parts = []
    tmp = self._item_stack[0]

    internal_counter = IncrementalNameGenerator()
    imhex_translate = {
      ">h" : "u16",
    }

    def _imhex_obj(el):
      name = internal_counter.next("OBJECT")
      tmp=[]
      tmp.append(f"struct {name} {{ // at {el.pos}")
      for prop, val in el.items:
        item_type,n = _imhex_parse(val)
        if n == 1:
          tmp.append(f"  {item_type} {prop} ; ")
        else:
          tmp.append(f"  {item_type} {prop}[{n}] ; ")
      tmp.append(" }; // obj ")
      parts.append( "\n".join( tmp ) )
      return name, 1

    def _imhex_list(el):
      name = internal_counter.next("ARRAY")
      tmp = []
      tmp.append(f"struct {name} {{ // at {el.pos}")
      for i,item in enumerate(el.items):
        item_type,n = _imhex_parse(item)
        if n == 1:
          tmp.append(f"  {item_type}  ITEM_{i};")
        else:
          tmp.append(f"  {item_type}  ITEM_{i}[{n}];")
      tmp.append(" }; // end " )
      parts.append( "\n".join( tmp ) )
      return name, 1

    def _imhex_data(el):
      if el.fmt and el.fmt in imhex_translate:
        return imhex_translate[el.fmt], 1
      n = el.size
      return "u8", n

    def _imhex_parse(el):
      if el.kind == "LIST":
        return _imhex_list(el)
      if el.kind == "OBJECT":
        return _imhex_obj(el)
      if el.kind == "DATA":
        return _imhex_data(el)
      raise Exception("BAD NODE")

    root,_  = _imhex_parse(tmp)
    parts.append(f"{root} rootItem @ 0x00;\n")
    return "\n\n".join(parts[:])

  def output_kaitai(self):
    """ plceholder """
    pass


def structure_to_html_viewer(st, into_file=None):
  return custom_json_serializer(
    {
      "data_hex": st.get_data().hex(), 
      "struct": st.get_root_element()
    }, 
    into_file=into_file
  )


def custom_json_serializer(st,into_file=None):
  import json

  def custom_dumper(obj):
    print("DUMP", obj)
    return obj.__json__()
  
  if into_file is None:
    return json.dumps(st, default=custom_dumper)
  return json.dump(st, into_file, default=custom_dumper)


def structure_to_yaml(reader):
  import yaml
  root = reader.get_root_element()
  #yaml.add_representer(OrderedDict, lambda dumper, data: dumper.represent_mapping("tag:yaml.org,2002:map", data.items()))
  return yaml.dump(root.dump(), default_flow_style=False)



if __name__ == "__main__":
  print("Hello there")




