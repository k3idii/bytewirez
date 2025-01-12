import bytewirez  

import logging
logging.basicConfig(level=logging.DEBUG)



INPUT_DATA = b'xxyyaaabbcc123'

wire = bytewirez.Wire(from_bytes=INPUT_DATA)
st = bytewirez.StructureReader(wire)

st.will_read("field01","field02") # legacy, 
wire.read(2)
wire.read(2)

st.field("field1") # new 
wire.read(4)

st.field("field2").read_word() # or chained 

with st.field("obj1").start_object(class_name='FooClass'):
  st.field("ob1_field1").read_word()
  with st.field("array1").start_list():
    for i in range(3):
      wire.read(1)


print(" --- PASTE THAT TO HTML VIEWER --- ")


import json 
print(
  bytewirez.structure_to_html_viewer( st ) 
)

print(" --- --- --- --- ---")
