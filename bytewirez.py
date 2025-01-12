"""
 TODO: docstring here 
"""
import io
import os
import struct
from typing import OrderedDict

import logging
logger = logging.getLogger(__name__)

ENDIAN_BIG    = ">"
ENDIAN_LITTLE = "<"


class IncrementalNameGenerator:
  count = 0
  item_format = "{name}__{self.count}"
  def __init__(self, start=0, item_format=None):
    self.count = start
    if item_format:
      self.item_format = item_format

  def next(self, name="ITEM"):
    self.count += 1
    return self.item_format.format(name=name, self=self)


def unpack_ex(fmt, data, into=None):
  parts = struct.unpack(fmt, data)
  if not parts:
    return None
  if not into:
    if len(parts) == 1:
      return parts[0]
    return parts
  if len(parts) > len(into):
    raise struct.error("unpack_ex: too many values unpacked !")
  return dict((into[i], parts[i]) for i in range(len(parts)))


HOOK_PRE_READ   = "pre_read"
HOOK_POST_READ  = "post_read"
HOOK_FMT_READ   = "fmt_read"

HOOK_PRE_WRITE  = "pre_write"
HOOK_POST_WRITE = "post_write"
HOOK_FMT_WRITE  = "fmt_write"

HOOK_PRE_PEEK   = "pre_peek"
HOOK_POST_PEEK  = "post_peek"



class Wire:
  """
  Class that delivers interface for comfortable reading/writing bytes.
  This is overlay for already opened file (from_fd), BytesIO() or bytes().
  """
  _obj = None
  _pos_stack = None
  _endian = ">"
  _hooks = {}

  def __init__(self, from_fd=None, from_bytes=None, from_string=None):
    if from_fd is not None:
      self._obj = from_fd
    elif from_bytes is not None:
      self._obj = io.BytesIO(from_bytes)
    elif from_string is not None:
      self._obj = io.BytesIO(from_string.decode())
    else:
      print("Initialized with empty bytesIO")
      self._obj = io.BytesIO(b"")
    self.initialize()

  def initialize(self): # to make override less painfull without super()
    self._pos_stack = list()

  def install_hook(self, where, fnc):
    assert callable(fnc), "need callable argument !"
    if where not in self._hooks:
      self._hooks[where] = []
    self._hooks[where].append(fnc)

  def _exec_hook(self, where, nargs, *arg):
    if nargs == 1:
      a = arg[0]
    for fnc in self._hooks.get(where, []):
      val = fnc(a)
      a = val
    return a





  def dump(self):
    return self._obj.getvalue()

  def set_endian(self, e):
    assert e in "><", "Endian should be > or <"
    self._endian = e

  def pushd(self):
    """ push current position on stack """
    self._pos_stack.append(self.get_pos())

  def popd(self):
    """ pop position from stack and set it """
    self._obj.seek(self._pos_stack.pop(), os.SEEK_SET)

  def peekn(self, n):
    """ Peek exacly n-bytes """
    b = self.peek(n)
    if len(b) != n:
      raise Exception(f"Fail to peek {n} bytes , got {len(b)}")
    return b

  def readn(self, n):
    """ Read exacly n-bytes """
    b = self.read(n)
    if len(b) != n:
      raise Exception(f"Fail to read {n} bytes , got {len(b)}")
    return b

  def peek(self, n):
    self.pushd()
    n = self._exec_hook(HOOK_PRE_PEEK, 1, n)
    value = self._obj.read(n)
    value = self._exec_hook(HOOK_POST_PEEK, 1, value)
    self.popd()
    return value

  def write(self, b):
    b = self._exec_hook(HOOK_PRE_WRITE, 1, b)
    retval = self._obj.write(b)
    retval = self._exec_hook(HOOK_POST_WRITE, 1, retval)
    return retval

  def read(self, n=None):
    n = self._exec_hook(HOOK_PRE_READ, 1, n)
    value = self._obj.read(n)
    value = self._exec_hook(HOOK_POST_READ, 1, value)
    return value

  def bytes_available(self):
    """ Try to check how many bytes are still to read in the stream"""
    p1 = self.get_pos()
    self.pushd()
    self.goto_end()
    p2 = self.get_pos()
    self.popd()
    return p2-p1

  ## POSTITION

  def get_pos(self):
    return self._obj.tell()

  def goto(self, p):
    self._obj.seek(p, os.SEEK_SET)

  def goto_begin(self):
    self.goto(0)

  def goto_end(self):
    self._obj.seek(0, os.SEEK_END)

  ## READING

  def read_fmt(self, fmt, into_dict=None):
    """ Read using struct format """
    fmt = self._exec_hook(HOOK_FMT_READ, 1, fmt)
    sz = struct.calcsize(fmt)
    b = self.readn(sz)
    return unpack_ex(fmt, b, into_dict)

  def peek_fmt(self, fmt, into_dict=None):
    """ Peek using struct format """
    sz = struct.calcsize(fmt)
    b = self.peekn(sz)
    return unpack_ex(fmt, b, into_dict)

  ## WRITING

  def write_fmt(self, fmt, *a):
    return self.write(struct.pack(fmt, *a))

  def write_hex(self, stuff):
    return self.write(bytes.fromhex(stuff))


  def _peek_single(self, fmt):
    self.pushd()
    val = self.peek_fmt(self._endian + fmt)
    self.popd()
    return val

  def peek_byte(self):
    return self._peek_single("B")


  _read_single = lambda self, fmt: self.read_fmt(self._endian + fmt)

  def read_byte(self):
    return self._read_single("B")

  def read_word(self):
    return self._read_single("H")

  def read_dword(self):
    return self._read_single("I")

  def read_qword(self):
    return self._read_single("Q")

  def read_sbyte(self):
    return self._read_single("b")

  def read_sword(self):
    return self._read_single("h")

  def read_sdword(self):
    return self._read_single("i")

  def read_sqword(self):
    return self._read_single("q")


  _write_single = lambda self, fmt, val: self.write_fmt(self._endian + fmt, val)

  def write_byte(self, val):
    return self._write_single("B", val)

  def write_word(self, val):
    return self._write_single("H", val)

  def write_dword(self, val):
    return self._write_single("I", val)

  def write_qword(self, val):
    return self._write_single("Q", val)

  def write_sbyte(self, val):
    return self._write_single("b", val)

  def write_sword(self, val):
    return self._write_single("h", val)

  def write_sdword(self, val):
    return self._write_single("i", val)

  def write_sqword(self, val):
    return self._write_single("q", val)







class StructItemAbstract:
  pos :int = 0
  size :int = 0
  kind = None

  def __init__(self, **kwargs) -> None:
    for k,v in kwargs.items():
      setattr(self, k, v)

  def _dump_basic(self):
    result = dict()
    result["$TYPE"] = self.kind
    result["$POS"] = self.pos
    result["$SIZE"] = self.size
    return result

class DataItem(StructItemAbstract):
  raw = b""
  fmt = None
  kind = "DATA"

  def __json__(self):
    result = self._dump_basic()
    if self.fmt is not None:
      result["format"] = self.fmt
      tmp =struct.unpack(self.fmt, self.raw)
      if len(tmp)==1:
        tmp = tmp[0]
      result["data_fmt"] = tmp
    result["data_hex"] = self.raw.hex()
    return result
  

class StructItemOBJECT(StructItemAbstract):
  _items = None
  class_name = None
  kind = "OBJECT"

  def __init__(self, **kwargs) -> None:
    super().__init__(**kwargs)
    self._items = []

  def add(self, name, item):
    self.size += item.size
    self._items.append({name: item})

  def __json__(self):
    result = self._dump_basic()
    if self.class_name:
      result["$CLASS"] = self.name
    result['$FIELDS'] = self._items
    return result



class StructItemLIST(StructItemAbstract):
  _items = None
  kind = "LIST"

  def __init__(self, **kwargs) -> None:
    super().__init__(**kwargs)
    self._items = []

  def add(self, item):
    self.size += item.size
    self._items.append(item)

  def __json__(self):
    result = self._dump_basic()
    result["items"] =  self._items 
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
  main = None


  def __init__(self, wire: Wire):
    self._wire = wire
    self._item_stack = list()
    self._names_stack = list()
    #self._item_stack.append(
    #  StructItemLIST(
    #    pos=self._wire.get_pos()
    #  )
    #) # root element

    self._item_stack.append(
      StructItemOBJECT(name="MAIN", pos=self._wire.get_pos())
    )

    # install hooks ;
    wire.install_hook(HOOK_PRE_READ,  self._pre_read)
    wire.install_hook(HOOK_POST_READ, self._post_read)
    wire.install_hook(HOOK_FMT_READ,  self._fmt_read)

  def _fmt_read(self, fmt):
    self._last_format = fmt
    return fmt

  def _pre_read(self, n):
    self._current_item = DataItem(pos=self._wire.get_pos(), size=n, fmt=self._last_format)
    self._last_format = None
    return n

  def _post_read(self, data):
    logger.debug("DataItem read")
    self._current_item.raw = data
    self._append_to_current(self._current_item)
    self._current_item = None
    # TODO: make conditional flag to not to save raw data stream
    self._data += data
    return data


  def field(self, name):
    self.will_read(name)
    return MagicProxyObject(self)
  

  # that is low leve API
  def will_read(self, *names):
    # TODO: this could take list of strings and add the to the stack of names
    for item in names[::-1]:
      self._names_stack.append(item)

  def _try_get_name(self):
    # TODO: should stack-of-names be FIFO or LIFO  ?
    if len(self._names_stack) > 0:
      return self._names_stack[-1]
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
      name = f"item_{len(top._items):05}"
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
    # called when exiting scope
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
      name = internal_counter.next("OBJECT") + "__" + el.name
      tmp=[]
      tmp.append(f"struct {name} {{ // at {el.pos}")
      for prop, val in el._items:
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
      for i,item in enumerate(el._items):
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


def structure_to_html_viewer(st):
  return custom_json_serializer(
      dict(
      data_hex = st.get_data().hex(),
      struct = st.get_root_element(),
    )
  )


def custom_json_serializer(st,f=None):
  import json
  def custom_dumper(obj):
      try:
          return obj.__json__()
      except:
          return obj.__dict__
  if f is None:
    return json.dumps(st, default=custom_dumper)
  else:
    return json.dump(st, f, default=custom_dumper)


def structure_to_yaml(reader):
  import yaml
  root = reader.get_root_element()
  yaml.add_representer(OrderedDict, lambda dumper, data: dumper.represent_mapping("tag:yaml.org,2002:map", data.items()))
  return yaml.dump(root.dump(), default_flow_style=False)



if __name__ == "__main__":
  print("Hello there")




