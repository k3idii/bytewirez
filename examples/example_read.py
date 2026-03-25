import bytewirez  

tmp = b'test' + bytes.fromhex('1234 00031337')

print("Data: ", tmp)

def _read_fnc(*a,**kw):
  print("HOOK PRE-READ ! args: ", *a, **kw)
  return None

def _read_post(d):
  print("POST READ ",d)
  return d

wire = bytewirez.Wire.from_bytes(tmp)
wire.install_hook(wire.read, pre=_read_fnc, post=_read_post)
assert b'test'  == wire.readn(4)
assert 0x1234   == wire.read_word()
assert 0x31337  == wire.read_fmt("I")
print("OK!")
  