#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys
from tvgrabpyAPI import tv_grab_test, version
if version()[1:4] != (1,0,1):
    sys.stderr.write("This instance of tv_grab_test_json_py requires tv_grab_py_API 1.0.1\n")
    sys.exit(1)

testjson = tv_grab_test.test_JSON()
if testjson.keyfile == None:
    sys.exit(2)

cmd = sys.argv
if len(cmd) < 2:
    testjson.config.log('Please give the name of the json file to test.\n')
    sys.exit(-1)

testjson.test_file_syntax(cmd[1])
