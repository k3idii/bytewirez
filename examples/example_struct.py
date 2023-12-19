import bytewirez  


dummy_logger = bytewirez.DummyPrintLogger()
INPUT_DATA = b'test112233xx'

wire = bytewirez.Wire(from_bytes=INPUT_DATA)
r = bytewirez.StructureReader(wire, logger=dummy_logger)
with r.start_object(): 
  #^--- by using context manager, you don't need to manuall "end" objects 
  r.will_read("test_string")
  wire.readn(4)
  r.will_read("list_of_items")
  with r.start_list():
    wire.read_word()
    wire.read_dword()
  r.will_read("internal_struct")
  with r.start_object():
    #r.will_read('subObj_item1')
    wire.read_word()


print(" --- PASTE THAT TO HTML VIEWER --- ")

import json 
print( 
  json.dumps(
    bytewirez.structure_to_html_viewer( r ) 
  )
)

print(" --- --- --- --- ---")
