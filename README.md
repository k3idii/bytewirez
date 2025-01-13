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
def _pre_read_hook(*a,**kw):
  n = a[0]
  print(f"I will read {n} bytes")
  return None

wire = Wire(from_bytes=b'test123')
wire.install_hook(wire.read, pre=_pre_read_hook)
wire.readn(4)
 ```

  
### Reading structures (and debugging stuff)

```python

wire = Wire(from_bytes=b'test112233')
r = StructureReader(wire)
r.will_read("test_string").readn(4)
r.will_read("items")
with r.start_list():
  wire.read_word()
  wire.read_dword()
 #...
 print(json.dumps(r.get_struct()))
 
 ```
 

 Aaand the (ugly) html viewer (seriously, if anyone can make this stuff looks better ... )
 
 ![image](https://user-images.githubusercontent.com/7603260/183519032-d46a3533-4750-4a33-b635-1a21f2e4cb19.png)

 
 
 
 
 
 
 
 
 
 
