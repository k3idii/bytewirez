import bytewirez

def _wr_fnc(*a,**kw):
  print("WRITE HOOK:",a,kw)
  return None

wire = bytewirez.Wire(from_bytes=b'')
wire.install_hook(wire.write, pre=_wr_fnc)
wire.write(b'test')
wire.write_word(0x1234)
wire.write_fmt("I",0x31337)

tmp = wire.dump()
print("Bytes : ", tmp)  
print(" -- HEX DUMP -- ")
print(wire.hexdump(start_at=0))

