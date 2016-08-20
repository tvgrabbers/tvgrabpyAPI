#!/usr/bin/env python2
# -*- coding: utf-8 -*-

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
    sys.exit(testjson.test_file(cmd[1]))

else:
    # Adding options to test on sourceid
    pass
