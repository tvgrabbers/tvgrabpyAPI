#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# testjson.test_file accepts 3 parameters
# file_name: The file, including a path to it, to test
# struct_name: See the structfiles in ~/.json_struct for available names
# report_level: Add the desired ones or substract the undesired ones from -1
#
# Report Levels (default is -1 or all):
#   1: Missing required keys
#   2: Errors on required values and on either selection
#   4: Errors on not required keys
#   8: Missing sugested keys without a default
#  16: Missing sugested keys
#  32: Missing optional keys without a default
#  64: Missing optional keys
# 128: Unused keys
# 256: Unknown keys
# 512: Report on either selection (without errors)

import sys
from tvgrabpyAPI import tv_grab_IO

testjson = tv_grab_IO.test_JSON()
if testjson.struct_tree in (None, []):
    sys.exit(3)

cmd = sys.argv
if len(cmd) < 2:
    testjson.log('Please give the name of the json file to test.\n')
    sys.exit(1)

if len(cmd) == 2:
    sys.exit(testjson.test_file(cmd[1], report_level = (1+2+4+8+16+128+256)))

if len(cmd) > 2:
    sys.exit(testjson.test_file(cmd[1], report_level = int(cmd[2])))

else:
    # Adding options to test on sourceid
    pass
