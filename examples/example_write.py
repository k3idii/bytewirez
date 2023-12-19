import bytewirez

def _wr_fnc(arg):
  print("WRITE HOOK:",arg)
  return arg

wire = bytewirez.Wire(from_bytes=b'')
wire.install_hook(bytewirez.HOOK_PRE_WRITE, _wr_fnc)
wire.write(b'test')
wire.write_word(0x1234)
wire.write_fmt("I",0x31337)

tmp = wire.dump()

print(tmp)

print(tmp.hex())  
