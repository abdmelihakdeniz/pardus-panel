import ctypes
import gettext
import locale
import os
from importlib import resources

DOMAIN = "pardus-panel"


def configure() -> None:
    locale.setlocale(locale.LC_ALL, "")
    locale_dir = resources.files("pardus_panel").joinpath("locales")
    gettext.bindtextdomain(DOMAIN, str(locale_dir))
    gettext.textdomain(DOMAIN)
    libc = ctypes.CDLL(None)
    libc.bindtextdomain.argtypes = (ctypes.c_char_p, ctypes.c_char_p)
    libc.bindtextdomain.restype = ctypes.c_char_p
    libc.bind_textdomain_codeset.argtypes = (ctypes.c_char_p, ctypes.c_char_p)
    libc.bind_textdomain_codeset.restype = ctypes.c_char_p
    libc.bindtextdomain(DOMAIN.encode(), os.fsencode(locale_dir))
    libc.bind_textdomain_codeset(DOMAIN.encode(), b"UTF-8")


_ = gettext.gettext
