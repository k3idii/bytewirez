import bytewirez  

tmp = bytes.fromhex('74657374123400031337')

def _read_fnc(*a,**kw):
  print("HOOK PRE-READ ! args: ", *a, **kw)
  return None
  
wire = bytewirez.Wire(from_bytes=tmp)
wire.install_hook(wire.read, pre=_read_fnc)
assert b'test'  == wire.readn(4)
assert 0x1234   == wire.read_word()
assert 0x31337  == wire.read_fmt("I")
print("OK!")
  