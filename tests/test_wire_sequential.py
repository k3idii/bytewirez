import unittest
from bytewirez import Wire

class TestWireSequential(unittest.TestCase):
    def test_write_read_sequential(self):
        """
        Creates an empty Wire, writes values, and reads them back in order.
        """
        wire = Wire()
        
        # Test values
        v_byte = 0xAA
        v_word = 0x1234
        v_dword = 0xDEADBEEF
        v_qword = 0xCAFEBABE12345678
        v_sbyte = -127
        v_sword = -32767
        
        # 1. Write values in order
        wire.write_byte(v_byte)
        wire.write_word(v_word)
        wire.write_dword(v_dword)
        wire.write_qword(v_qword)
        wire.write_sbyte(v_sbyte)
        wire.write_sword(v_sword)
        
        # 2. Go to the beginning to start reading
        wire.goto_begin()
        
        # 3. Read back in the same order
        self.assertEqual(wire.read_byte(), v_byte)
        self.assertEqual(wire.read_word(), v_word)
        self.assertEqual(wire.read_dword(), v_dword)
        self.assertEqual(wire.read_qword(), v_qword)
        self.assertEqual(wire.read_sbyte(), v_sbyte)
        self.assertEqual(wire.read_sword(), v_sword)

    def test_byte_available(self):
        """Verify that bytes_available correctly calculates remaining size."""
        wire = Wire(from_bytes=b"\x00" * 10)
        self.assertEqual(wire.bytes_available(), 10)
        wire.read(4)
        self.assertEqual(wire.bytes_available(), 6)

if __name__ == "__main__":
    unittest.main()
