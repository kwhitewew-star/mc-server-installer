"""PyOpenGL returns GL strings in different types depending on version and platform."""

import ctypes

from mcsi.gfx.scene import gl_text


def test_all_shapes_of_gl_strings():
    assert gl_text(b"uTime\x00\x00") == "uTime"
    assert gl_text("uRect[0]") == "uRect[0]"
    assert gl_text((ctypes.c_byte * 10)(*b"uRect[0]\x00\x00")) == "uRect[0]"      # Windows, PyOpenGL 3.1.10
    assert gl_text((ctypes.c_char * 8)(*[bytes([c]) for c in b"uScale\x00\x00"])) == "uScale"
    assert gl_text((ctypes.c_ubyte * 4)(*b"abc\x00")) == "abc"
    assert gl_text(None) == ""
    assert gl_text(bytearray(b"llvmpipe")) == "llvmpipe"
    assert gl_text((ctypes.c_byte * 3)(-61, -87, 0)) == "é"
