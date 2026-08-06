import unittest
import struct
import io
from bytewirez import (
    Wire, StructureReader, hexdump, unpack_ex,
    ENDIAN_BIG, ENDIAN_LITTLE,
)


class TestWireConstruction(unittest.TestCase):
    def test_empty(self):
        w = Wire.empty()
        self.assertEqual(w.dump(), b'')

    def test_from_bytes(self):
        w = Wire.from_bytes(b'\x01\x02')
        self.assertEqual(w.dump(), b'\x01\x02')

    def test_from_string(self):
        w = Wire.from_string("hi")
        self.assertEqual(w.dump(), b'hi')

    def test_from_fd(self):
        fd = io.BytesIO(b'abc')
        w = Wire.from_fd(fd)
        self.assertEqual(w.dump(), b'abc')

    def test_default_constructor_empty(self):
        w = Wire()
        self.assertEqual(w.dump(), b'')


class TestWireReadWrite(unittest.TestCase):
    def test_write_and_dump(self):
        w = Wire.empty()
        w.write(b'hello')
        self.assertEqual(w.dump(), b'hello')

    def test_readn_exact(self):
        w = Wire(from_bytes=b'abcdef')
        self.assertEqual(w.readn(3), b'abc')
        self.assertEqual(w.readn(3), b'def')

    def test_readn_underflow(self):
        w = Wire(from_bytes=b'ab')
        with self.assertRaises(EOFError):
            w.readn(5)

    def test_write_read_fmt(self):
        w = Wire.empty()
        w.write_fmt("I", 0xDEADBEEF)
        w.goto_begin()
        self.assertEqual(w.read_fmt("I"), 0xDEADBEEF)

    def test_write_read_fmt_multiple(self):
        w = Wire.empty()
        w.write_fmt("BHI", 1, 2, 3)
        w.goto_begin()
        self.assertEqual(w.read_fmt("BHI"), (1, 2, 3))

    def test_write_hex(self):
        w = Wire.empty()
        w.write_hex("DEADBEEF")
        self.assertEqual(w.dump(), b'\xDE\xAD\xBE\xEF')

    def test_all_typed_write_read(self):
        w = Wire.empty()
        w.write_byte(0xFF)
        w.write_word(0x1234)
        w.write_dword(0xAABBCCDD)
        w.write_qword(0x1122334455667788)
        w.write_sbyte(-1)
        w.write_sword(-1000)
        w.write_sdword(-100000)
        w.write_sqword(-9999999999)

        w.goto_begin()
        self.assertEqual(w.read_byte(), 0xFF)
        self.assertEqual(w.read_word(), 0x1234)
        self.assertEqual(w.read_dword(), 0xAABBCCDD)
        self.assertEqual(w.read_qword(), 0x1122334455667788)
        self.assertEqual(w.read_sbyte(), -1)
        self.assertEqual(w.read_sword(), -1000)
        self.assertEqual(w.read_sdword(), -100000)
        self.assertEqual(w.read_sqword(), -9999999999)


class TestWirePosition(unittest.TestCase):
    def test_goto_begin_end(self):
        w = Wire(from_bytes=b'12345')
        w.goto_end()
        self.assertEqual(w.get_pos(), 5)
        w.goto_begin()
        self.assertEqual(w.get_pos(), 0)

    def test_goto(self):
        w = Wire(from_bytes=b'abcde')
        w.goto(3)
        self.assertEqual(w.readn(1), b'd')

    def test_pushd_popd(self):
        w = Wire(from_bytes=b'abcde')
        w.goto(2)
        w.pushd()
        w.goto(4)
        self.assertEqual(w.get_pos(), 4)
        w.popd()
        self.assertEqual(w.get_pos(), 2)

    def test_popd_empty_raises(self):
        w = Wire.empty()
        with self.assertRaises(IndexError):
            w.popd()

    def test_bytes_available(self):
        w = Wire(from_bytes=b'abcdefgh')
        self.assertEqual(w.bytes_available(), 8)
        w.readn(3)
        self.assertEqual(w.bytes_available(), 5)


class TestWirePeek(unittest.TestCase):
    def test_peek_no_advance(self):
        w = Wire(from_bytes=b'abcde')
        self.assertEqual(w.peek(3), b'abc')
        self.assertEqual(w.get_pos(), 0)

    def test_peekn_exact(self):
        w = Wire(from_bytes=b'ab')
        self.assertEqual(w.peekn(2), b'ab')
        self.assertEqual(w.get_pos(), 0)

    def test_peekn_underflow(self):
        w = Wire(from_bytes=b'a')
        with self.assertRaises(EOFError):
            w.peekn(5)

    def test_peek_at_offset(self):
        w = Wire(from_bytes=b'abcde')
        self.assertEqual(w.peek(2, at=3), b'de')
        self.assertEqual(w.get_pos(), 0)

    def test_peek_byte(self):
        w = Wire(from_bytes=b'\x42rest')
        self.assertEqual(w.peek_byte(), 0x42)
        self.assertEqual(w.get_pos(), 0)

    def test_peek_fmt(self):
        w = Wire.empty()
        w.write_fmt("H", 0x1234)
        w.goto_begin()
        self.assertEqual(w.peek_fmt("H"), 0x1234)
        self.assertEqual(w.get_pos(), 0)


class TestWireEndian(unittest.TestCase):
    def test_default_big_endian(self):
        w = Wire.empty()
        self.assertEqual(w.get_endian(), ENDIAN_BIG)

    def test_set_little_endian(self):
        w = Wire.empty()
        w.set_endian(ENDIAN_LITTLE)
        w.write_word(0x0102)
        self.assertEqual(w.dump(), b'\x02\x01')

    def test_set_big_endian(self):
        w = Wire.empty()
        w.set_endian(ENDIAN_BIG)
        w.write_word(0x0102)
        self.assertEqual(w.dump(), b'\x01\x02')

    def test_invalid_endian(self):
        w = Wire.empty()
        with self.assertRaises(AssertionError):
            w.set_endian("X")

    def test_fix_endian_preserves_explicit(self):
        w = Wire.empty()
        w.set_endian(ENDIAN_BIG)
        self.assertEqual(w.fix_endian("<H"), "<H")
        self.assertEqual(w.fix_endian(">I"), ">I")


class TestWireHooks(unittest.TestCase):
    def test_pre_hook_called(self):
        calls = []
        def pre(*a, **kw):
            calls.append(('pre', a))
            return None

        w = Wire(from_bytes=b'\x01\x02\x03')
        w.install_hook(w.read, pre=pre)
        w.readn(2)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], (2,))

    def test_post_hook_transforms(self):
        def post(result):
            return result.upper()

        w = Wire(from_bytes=b'hello')
        w.install_hook(w.read, post=post)
        self.assertEqual(w.read(5), b'HELLO')


class TestUnpackEx(unittest.TestCase):
    def test_single_value(self):
        data = struct.pack(">I", 42)
        self.assertEqual(unpack_ex(">I", data), 42)

    def test_multiple_values(self):
        data = struct.pack(">BH", 1, 2)
        self.assertEqual(unpack_ex(">BH", data), (1, 2))

    def test_into_dict(self):
        data = struct.pack(">BH", 10, 20)
        result = unpack_ex(">BH", data, into=["a", "b"])
        self.assertEqual(result, {"a": 10, "b": 20})

    def test_into_dict_too_few_names(self):
        data = struct.pack(">BHI", 1, 2, 3)
        with self.assertRaises(struct.error):
            unpack_ex(">BHI", data, into=["a", "b"])


class TestHexdump(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(hexdump(b''), "")

    def test_basic(self):
        out = hexdump(b'\x41\x42\x43')
        self.assertIn("414243", out)
        self.assertIn("ABC", out)

    def test_nonprintable(self):
        out = hexdump(b'\x00\x01\x02', subst='.')
        self.assertIn("...", out)


class TestStructureReader(unittest.TestCase):
    def test_basic_read_tracking(self):
        w = Wire(from_bytes=b'\x00\x01\x00\x02')
        r = StructureReader(w)
        r.will_read("field_a").read_word()
        r.will_read("field_b").read_word()
        root = r.get_root_element()
        d = root.to_dict()
        self.assertEqual(d["TYPE"], "OBJECT")
        self.assertEqual(len(d["FIELDS"]), 2)
        self.assertEqual(d["FIELDS"][0][0], "field_a")
        self.assertEqual(d["FIELDS"][1][0], "field_b")

    def test_nested_list(self):
        w = Wire(from_bytes=b'\x00\x01\x00\x02\x00\x03')
        r = StructureReader(w)
        r.will_read("items")
        with r.start_list():
            w.read_word()
            w.read_word()
            w.read_word()
        root = r.get_root_element()
        d = root.to_dict()
        items_field = d["FIELDS"][0]
        self.assertEqual(items_field[0], "items")
        list_item = items_field[1]
        self.assertEqual(list_item.to_dict()["TYPE"], "LIST")
        self.assertEqual(len(list_item.to_dict()["ITEMS"]), 3)

    def test_nested_object(self):
        w = Wire(from_bytes=b'\x00\x01\x00\x02')
        r = StructureReader(w)
        r.will_read("header")
        with r.start_object(class_name="Header"):
            r.will_read("version").read_word()
            r.will_read("flags").read_word()
        root = r.get_root_element()
        d = root.to_dict()
        header = d["FIELDS"][0][1]
        hd = header.to_dict()
        self.assertEqual(hd["CLASS"], "Header")
        self.assertEqual(len(hd["FIELDS"]), 2)

    def test_get_data(self):
        w = Wire(from_bytes=b'\xAA\xBB\xCC\xDD')
        r = StructureReader(w)
        w.read(4)
        self.assertEqual(r.get_data(), b'\xAA\xBB\xCC\xDD')


class TestBackwardCompatProxy(unittest.TestCase):
    def test_import_from_proxy(self):
        import importlib
        mod = importlib.import_module("bytewirez")
        self.assertTrue(hasattr(mod, "Wire"))
        self.assertTrue(hasattr(mod, "StructureReader"))


if __name__ == "__main__":
    unittest.main()
