import bytewirez  

import logging
logging.basicConfig(level=logging.DEBUG)



INPUT_DATA = b'xxyyaaabbcc123'
INPUT_DATA = bytes.fromhex('11223344 2222 2222 fefe 1234 12345678 88 99 f1 f2 f3')

wire = bytewirez.Wire(from_bytes=INPUT_DATA)

st = bytewirez.StructureReader(wire)

st.will_read("field1") #
_ = wire.read(4)

st.will_read("field01","field02") 
_ = wire.read(2)
_ = wire.read(2)

_ = st.will_read("field2").read_word() # or chained 

with st.will_read("obj1").start_object(class_name='FooClass'):
  _ = st.will_read("ob1_field1").read_word()
  _ = st.will_read("many_fields").read_fmt("IBB")
  with st.will_read("array1").start_list():
    for i in range(3):
      wire.read(1)


print(" --- PASTE THAT TO HTML VIEWER --- ")

print(
  bytewirez.structure_to_html_viewer( st ) 
)

print(" --- --- --- --- ---")
