#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Python 3 compatibility
from __future__ import unicode_literals
# from __future__ import print_function

# Modules we need
#~ import sys, locale, traceback, json
#~ import time, datetime, pytz
import sys, locale
from tvgrabpyAPI import tv_grab_IO, version

try:
    unichr(42)
except NameError:
    unichr = chr    # Python 3

# check Python version
if sys.version_info[:3] < (2,7,9):
    sys.stderr.write("tv_grab_nl_API requires Pyton 2.7.9 or higher\n")
    sys.exit(2)

if sys.version_info[:2] >= (3,0):
    sys.stderr.write("tv_grab_nl_API does not yet support Pyton 3 or higher.\nExpect errors while we proceed\n")

locale.setlocale(locale.LC_ALL, '')

if version()[1:4] < (1,0,7):
    sys.stderr.write("tv_grab_nl3_py requires tv_grab_nl_API 1.0.7 or higher\n")
    sys.exit(2)

if __name__ == '__main__':
    test_source = tv_grab_IO.test_Source()
    x = test_source.test_source()

    test_source.close()
    sys.exit(x)
