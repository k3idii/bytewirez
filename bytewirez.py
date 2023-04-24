
import dataclasses
import io 
import os 
import struct
from typing import OrderedDict

from urllib3 import Retry


ENDIAN_BIG    = ">"
ENDIAN_LITTLE = "<"



def unpack_ex(fmt, data, into=None):
  parts = struct.unpack(fmt, data)
  if not parts:
    return None
  if not into:
    if len(parts) == 1:
      return parts[0]
    return parts
  if len(parts) > len(into):
    raise Exception("unpack_ex: too many values unpacked !")
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
  
  _obj = None
  _pos_stack = None
  _endian = '>'
  _hooks = {}
  
  def __init__(self, from_fd=None, from_bytes=None, from_string=None):
    if from_fd : 
      self._obj = from_fd
    elif from_bytes:
      self._obj = io.BytesIO(from_bytes)
    elif from_string:
      self._obj = io.BytesIO(from_string.decode())
    else:
      self._obj = io.BytesIO(b"")
    self.initialize()
      
  def initialize(self): # to make override less painfull 
    self._pos_stack = list()
      
  def install_hook(self, where, fnc):
    assert callable(fnc), "need callable argument !"
    if where not in self._hooks:
      self._hooks[where] = []
    self._hooks[where].append(fnc)
  
  def _exec_hook(self, where, nargs, *arg,):
    if nargs == 1:
      a = arg[0]
    for fnc in self._hooks.get(where, []):
      val = fnc(a)
      a = val
    return a
  
 
    
    
      
  def dump(self):
    return self._obj.getvalue()
  
  def set_endian(self, e):
    assert e in '><', "Endian should be > or <"
    self._endian = e
      
  def pushd(self):
    self._pos_stack.append(self.get_pos())
  
  def popd(self):
    self._obj.seek(self._pos_stack.pop(), os.SEEK_SET)
  
  def peekn(self, n):
    b = self.peek(n)
    if len(b) != n:
      raise Exception(f"Fail to peek {n} bytes , got {len(b)}")
    return b  
  
  def readn(self, n):
    b = self.read(n)
    if len(b) != n:
      raise Exception(f"Fail to read {n} bytes , got {len(b)}")
    return b
  
  def read_fmt(self, fmt, into_dict=None):
    fmt = self._exec_hook(HOOK_FMT_READ, 1, fmt)
    sz = struct.calcsize(fmt)
    b = self.readn(sz)
    return unpack_ex(fmt, b, into_dict)

  def peek_fmt(self, fmt, into_dict=None):
    sz = struct.calcsize(fmt)
    b = self.peekn(sz)
    return unpack_ex(fmt, b, into_dict)

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
    p1 = self.get_pos()
    self.pushd()
    self.goto_end()
    p2 = self.get_pos()
    self.popd()
    return p2-p1 

  def get_pos(self):
    return self._obj.tell()
    
  def goto(self, p):
    self._obj.seek(p, os.SEEK_SET)
    
  def goto_begin(self):
    self.goto(0)
  
  def goto_end(self):
    self._obj.seek(0, os.SEEK_END)
    

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
    return self._peek_single('B')
  
  _read_single  = lambda s, f: s.read_fmt(s._endian + f)
  
  def read_byte(self):
    return self._read_single('B')
  
  def read_word(self):
    return self._read_single("H")
    
  def read_dword(self):
    return self._read_single('I')
  
  def read_qword(self):
    return self._read_single('Q')
  
  def read_sbyte(self):
    return self._read_single('b')
  
  def read_sword(self):
    return self._read_single("h")
    
  def read_sdword(self):
    return self._read_single('i')
  
  def read_sqword(self):
    return self._read_single('q')
  
  _write_single = lambda s, f, v: s.write_fmt(s._endian + f, v)

  
  def write_byte(self, val):
    return self._write_single('B', val)
  
  def write_word(self, val):
    return self._write_single("H", val)
    
  def write_dword(self, val):
    return self._write_single('I', val)
  
  def write_qword(self, val):
    return self._write_single('Q', val)
  
  
  def write_sbyte(self, val):
    return self._write_single('b', val)
  
  def write_sword(self, val):
    return self._write_single("h", val)
    
  def write_sdword(self, val):
    return self._write_single('i', val)
  
  def write_sqword(self, val):
    return self._write_single('q', val)
  
    



class BaseItemInterface:
  pos :int = 0
  size :int = 0
  kind = None

  def __init__(self, **kwargs) -> None:
    for k,v in kwargs.items():
      setattr(self, k, v)
  
  def _dump_basic(self):
    result = OrderedDict()
    result['$TYPE'] = self.kind
    result['$POS'] = self.pos
    result['$SIZE'] = self.size
    return result


class ObjectItem(BaseItemInterface):
  _items = None
  name = 'UNNAMED'
  info = None
  kind = 'OBJECT'
  
  def __init__(self, **kwargs) -> None:
    super().__init__(**kwargs)
    self._items = []
    
  def add(self, name, item):
    self.size += item.size
    self._items.append([name, item])
    
  def dump(self):
    result = self._dump_basic()
    result['$NAME'] = self.name
    if self.info:
      result['$INFO'] = self.info
    f = []
    for item in self._items:
      f.append(item[0])
      result[item[0]]=item[1].dump()
    result['$ORDER'] = f
    return result 
    #return OrderedDict( [x.name, x.dump()] for  x in src )



class ListOfItems(BaseItemInterface):
  _items = None
  kind = 'LIST'


  def __init__(self, **kwargs) -> None:
    super().__init__(**kwargs)
    self._items = []
    
  def add(self, item):
    self.size += item.size
    self._items.append(item)
    
  def dump(self):
    result = self._dump_basic()
    result['items'] = [item.dump() for item in self._items]
    return result
  
  
  
  
class DataItem(BaseItemInterface):
  raw = b''
  fmt = None
  kind = 'DATA'
  
  def dump(self):
    result = self._dump_basic()
    if self.fmt is not None:
      result['format'] = self.fmt
      tmp =struct.unpack(self.fmt, self.raw)
      if len(tmp)==1:
        tmp = tmp[0]
      result['data_fmt'] = tmp
    result['data_hex'] = self.raw.hex()
    return result




class MagicStructReaderScope:
  def __init__(self, parent, obj, comment=''):
    self.parent = parent
    self.obj = obj
    self.comment = type(obj).__name__ 
    if comment != '' :
      self.comment + " // " + comment
  
  def __enter__(self):
    self.parent.ctx_logger.log_dbg(f" >BEGIN> {self.comment}")
    self.parent._struct_depth += 1
    
  def __exit__(self, *a, **kw):
    self.parent._struct_depth -= 1
    self.parent.ctx_logger.log_dbg(f" <END< {self.comment}")
    self.parent.end_item(*a, **kw)
    
    
class DummyPrintLogger:
  def __getattribute__(self, __name: str):
    def _dummy(*a,**kw):
      print(f"{__name:10} : ",*a,**kw)
    return _dummy

class StructureContextLogger:
  """ 
  another abstraction layer.
  will log current position of cursor while paring  binary data
  `logger` object need to have info,debug and warning methods 
  if `logger` is None -> no logging 
  
  """
  stay_silent = False
  do_indent = True 
  
  def __init__(self, struct_reader, logger=None):
    self.parent = struct_reader
    if logger:
      self.logger = logger 
    else:
      self.logger = DummyPrintLogger()
    
  def position_as_string(self):
    return f"0x{self.parent._wire.get_pos():08X} : "  

  def indent_str(self):
    if self.do_indent:
      return '  ' * self.parent._struct_depth
    else:
      return ' '
  
  def log_inf(self, msg):
    if self.logger and not self.stay_silent:
      self.logger.info( self.position_as_string() + self.indent_str() + msg)

  def log_dbg(self, msg):
    if self.logger and not self.stay_silent:
      self.logger.debug( self.position_as_string() + self.indent_str()  + msg)

  def log_wrn(self, msg):
    if self.logger and not self.stay_silent:
      self.logger.warning( self.position_as_string() + self.indent_str()  + msg)

  def log_err(self, msg):
    if self.logger and not self.stay_silent:
      self.logger.error( self.position_as_string() + self.indent_str()  + msg)


class StructureReader:
  """
    Implements reading of basic nested structures/collections such as :
      - objects/dicts 
      - lists/arrays 
    

  """
  _bytes_so_far = 0
  _item_stack = None
  _struct_depth = 0
  _names_stack = None
  _last_format = None
  _current_item = None
  _silent = False
  ctx_logger = None
  main = None
  
  def __init__(self, wire: Wire):
    self._wire = wire
    self._item_stack = list()
    self._names_stack = list()
    self._item_stack.append(ListOfItems(pos=self._wire.get_pos())) # root element
    self.ctx_logger = StructureContextLogger(struct_reader=self)
    
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
    self._current_item.raw = data
    self._append_to_current(self._current_item)
    self._current_item = None
    return data
    
  def will_read(self, item_name):
    self._names_stack.append(item_name)
    
  def _try_get_name(self):
    if len(self._names_stack) > 0:
      return self._names_stack[-1]
    else:
      return ''


  def start_object(self, name='Unnamed', info='', comment=''):
    obj = ObjectItem(name=name, pos=self._wire.get_pos(), info=info)
    self._push_item(obj)
    self.ctx_logger.log_inf(f"START object : {name} ")
    return MagicStructReaderScope(self, obj, comment)
 
  def start_list(self, comment=''):
    obj = ListOfItems(pos=self._wire.get_pos())
    self._push_item(obj)
    self.ctx_logger.log_inf(f"START list")
    return MagicStructReaderScope(self, obj, comment)
  
  def _append_to_current(self, o):
    top = self.last_item()
    if type(top) == ObjectItem:
      assert len(self._names_stack)>0, f"Need field name for property (object:{top.name})!"
      name = self._names_stack.pop()
      self.ctx_logger.log_inf(f"[+] field: {name}")
      top.add( name, o)
    elif type(top) == ListOfItems:
      top.add( o )
    else:
      raise Exception("OMG !")
      
  def _push_item(self, o):
    self._append_to_current(o)
    self._item_stack.append(o)
    
  def last_item(self):
    return self._item_stack[-1]
  
  def end_item(self, exception_type, exception_value, exception_traceback): 
    # called when exiting scope
    top = self._item_stack.pop()
    self.last_item().size += top.size
    
    if exception_type is not None:
      import traceback
      self.ctx_logger.log_err(f"  ** EXCEPTION ** ")
      self.ctx_logger.log_err(f"ERROR at {self.last_item().__class__.__name__}")
      for item in self._item_stack:
        self.ctx_logger.log_err(item.__class__.__name__)
    
      self.ctx_logger.log_err(f"-> type:{exception_type} : value:{exception_value}")
      self.ctx_logger.log_err(f"==> REASON:{0}",traceback.extract_tb(exception_traceback))
      
      raise Exception('DIE')
    
    

  def get_struct(self):
    # dump root element
    s = self._item_stack[0].dump()
    return dict(
      struct = s,
      data = self._wire.dump().hex()
    )

  def output_imHex(self):
    """ plceholder """
    pass 

  def output_kaitai(self):
    """ plceholder """
    pass



def yaml_dump(self,obj):
  import yaml
  yaml.add_representer(OrderedDict, lambda dumper, data: dumper.represent_mapping('tag:yaml.org,2002:map', data.items()))
  return yaml.dump(obj, default_flow_style=False)






if __name__ == '__main__':
  
  def _read_fnc(args):
    print("HOOK PRE-READ ! :", args)
    return args
  
  def _wr_fnc(arg):
    print("WRITE HOOK:",arg)
    return arg
  
  wire = Wire(from_bytes=b'')
  wire.install_hook(HOOK_PRE_WRITE, _wr_fnc)
  wire.write(b'test')
  wire.write_word(0x1234)
  wire.write_fmt("I",0x31337)
  
  tmp = wire.dump()
  
  wire = Wire(from_bytes=tmp)
  wire.install_hook(HOOK_PRE_READ, _read_fnc )
  assert b'test'  == wire.readn(4)
  assert 0x1234   == wire.read_word()
  assert 0x31337  == wire.read_fmt("I")
  print("OK!")
  
  
  wire = Wire(from_bytes=b'test112233')
  r = StructureReader(wire)
  with r.start_object():
    r.will_read("test_string")
    wire.readn(4)
    r.will_read("items")
    with r.start_list():
      wire.read_word()
      wire.read_dword()
  print(" --- PASTE THAT TO HTML VIEWER --- ")
  import json
  print(
    json.dumps(
      r.get_struct()
    )
  )
  