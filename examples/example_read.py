import bytewirez  

tmp = bytes.fromhex('74657374123437130300')

def _read_fnc(args):
  print("HOOK PRE-READ ! size=", args)
  return args
  
wire = bytewirez.Wire(from_bytes=tmp)
wire.install_hook(bytewirez.HOOK_PRE_READ, _read_fnc )
assert b'test'  == wire.readn(4)
assert 0x1234   == wire.read_word()
assert 0x31337  == wire.read_fmt("I")
print("OK!")
  