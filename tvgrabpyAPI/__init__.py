#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Python 3 compatibility
from __future__ import unicode_literals
# from __future__ import print_function

from tv_grab_config import *

__version__  = '%s.%s.%s' % (api_major,api_minor,api_patch)
if api_alfa:
    __version__ = '%s-alfa' % (__version__)

elif api_beta:
    __version__ = '%s-beta' % (__version__)

def version():
    return (api_name, api_major, api_minor, api_patch, api_patchdate, api_beta, api_alfa)

