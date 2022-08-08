# bytewirez
Tools to read/write structures from stream of bytes 


### WRITE

```python
wire = Wire(from_bytes=b'')
wire.write(b'test')
wire.write_word(0x1234)
wire.write_fmt("I",0x31337)
wire.write_fmt("BBII", 1,2,33,44)
data = wire.dump()
  
```

### READ

```python
wire = Wire(from_bytes=b'test223333')
wire.readn(4)
wire.read_word()
wire.read_fmt("BBBB")
```

### Hooks : 
```python
def _pre_read_hook(n):
  print(f"I will read {n} bytes")
  return n

wire = Wire(from_bytes=b'test123')
wire.install_hook(HOOK_PRE_READ, _pre_read_hook)
wire.readn(4)
 ```

### Reading structures (and debugging stuff)

```python

wire = Wire(from_bytes=b'test112233')
r = StructureReader(wire)
with r.start_object():
  r.will_read("test_string")
  wire.readn(4)
  r.will_read("items")
  with r.start_list():
    wire.read_word()
    wire.read_dword()
 #...
 print(json.dumps(r.get_struct()))
 
 ```
 
 JSON output :
 ```json
 {"struct": {"$TYPE": "LIST", "$POS": 0, "$SIZE": 10, "items": [{"$TYPE": "OBJECT", "$POS": 0, "$SIZE": 10, "$NAME": "Unnamed", "test_string": {"$TYPE": "DATA", "$POS": 0, "$SIZE": 4, "data_hex": "74657374"}, "items": {"$TYPE": "LIST", "$POS": 4, "$SIZE": 6, "items": [{"$TYPE": "DATA", "$POS": 4, "$SIZE": 2, "format": ">H", "data_fmt": 12593, "data_hex": "3131"}, {"$TYPE": "DATA", "$POS": 6, "$SIZE": 4, "format": ">I", "data_fmt": 842150707, "data_hex": "32323333"}]}, "$ORDER": ["test_string", "items"]}]}, "data": "74657374313132323333"}
 ```
 Aaand the (ugly) html viewer :
 
 ![image](https://user-images.githubusercontent.com/7603260/183519032-d46a3533-4750-4a33-b635-1a21f2e4cb19.png)

 
 
 
 
 
 
 
 
 
 
