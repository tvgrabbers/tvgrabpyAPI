#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Python 3 compatibility
from __future__ import unicode_literals
# from __future__ import print_function

# Modules we need
import sys, locale, traceback, json
import time, datetime, pytz
import tvgrabpyAPI
import tvgrabpyAPI.tv_grab_fetch as tv_grab_fetch

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

if tvgrabpyAPI.version()[1:4] < (1,0,0):
    sys.stderr.write("tv_grab_nl3_py requires tv_grab_nl_API 1.0.0 or higher\n")
    sys.exit(2)

class Configure(tvgrabpyAPI.Configure):
    def __init__(self):
        self.name ='tv_grab_nl3_py'
        self.datafile = 'tv_grab_nl'
        tvgrabpyAPI.Configure.__init__(self)
        # Version info from the frontend as returned by the version function
        self.country = 'The Netherlands'
        self.description = 'Dutch/Flemish grabber combining multiple sources.'
        self.major = 3
        self.minor = 0
        self.patch = 0
        self.patchdate = u'20160619'
        self.alfa = True
        self.beta = True
        # The default timezone to use in the xmltv output file
        self.opt_dict['output_tz'] = 'Europe/Amsterdam'
        # Where to get the json datafile and updates (if different from the API location)
        self.source_url = 'https://raw.githubusercontent.com/tvgrabbers/sourcematching/master'
        self.update_url = 'https://github.com/tvgrabbers/tvgrabnlpy/releases/latest'

# end Configure()
config = Configure()

def read_commandline(self):
    description = u"%s: %s\n" % (self.country, self.version(True)) + \
                    u"The Netherlands: %s\n" % self.version(True, True) + \
                    self.text('config', 29) + self.text('config', 30)

    parser = argparse.ArgumentParser(description = description, formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-V', '--version', action = 'store_true', default = False, dest = 'version',
                    help = self.text('config', 5, type='other'))

    parser.add_argument('-C', '--config-file', type = str, default = self.opt_dict['config_file'], dest = 'config_file',
                    metavar = '<file>', help =self.text('config', 23, (self.opt_dict['config_file'], ), type='other'))

def main():
    # We want to handle unexpected errors nicely. With a message to the log
    try:
        config.validate_option('config_file')
        config.opt_dict['log_level'] = config.opt_dict['log_level'] | 98304
        config.get_json_datafiles()

        channel ='een'
        channel = 'npo1'
        # virtual.nl
        #~ source = config.init_sources(11)

        # rtl.nl
        #~ channel = 'RTL4'
        #~ source = config.init_sources(2)

        # humo.be
        #~ source = config.init_sources(6)

        # horizon.tv
        #~ channel ='24443943146'
        #~ source = config.init_sources(5)

        # vrt.be
        #~ channel ='O8'
        #~ source = config.init_sources(10)

        # npo.nl
        #~ channel = '263'
        #~ source = config.init_sources(4)

        # vpro.nl
        #~ source = config.init_sources(7)

        # oorboekje.nl
        #~ channel = 'npo-radio-1'
        #~ source = config.init_sources(12)

        # nieuwsblad.be
        #~ channel ='een'
        #~ source = config.init_sources(8)

        # tvgids.nl
        #~ channel = '5'
        #~ source = config.init_sources(3)

        # tvgids.tv
        channel ='nederland-1'
        source = config.init_sources(1)

        # primo.eu
        #~ channel ='een'
        #~ channel = 'npo1'
        #~ source = config.init_sources(9)

        source.test_output = sys.stdout
        #~ source.print_tags = True
        source.print_roottree = True
        source.show_parsing = True
        source.print_searchtree = True
        source.show_result = True

        sid = source.proc_id
        config.channelsource[sid] = source
        source.init_channel_source_ids()
        tdict = {}
        tdict['detail_url'] = {}
        tdict['chanid'] = source.chanids[channel]

        #~ source.get_channels()

        offset = 1
        first_day = 0
        max_days = 4
        last_day = 1
        data = source.get_page_data('base',{'channels': source.channels,
                                                                'channel': channel,
                                                                'channelgrp': 'main',
                                                                'offset': offset,
                                                                'start': first_day,
                                                                'end': min(max_days, last_day),
                                                                'back':-first_day,
                                                                'ahead':min(max_days, last_day)-1})
        source.parse_basepage(data, {'offset': 1, 'channel': channel, 'channelgrp': 'main'})

        #~ tdict['detail_url'] = '20741005'
        #~ tdict['detail_url'][sid] = '20629464'
        #~ tdict['detail_url'][sid] = 'death-in-paradise/15885235'
        #~ tdict['detail_url'][sid] = "7892935" #'7875065'
        #~ tdict['detail_url'][sid] = "7897702" #'7879295'
        #~ tdict['detail_url'][sid] = "20822296" #'7875063'
        #~ source.load_detailpage('detail', tdict)

    except:
        traceback.print_exc()
        #~ config.logging.log_queue.put({'fatal': [traceback.format_exc(), '\n'], 'name': None})
        return(99)

    # and return success
    return(0)
# end main()

# allow this to be a module
if __name__ == '__main__':
    x = main()
    config.close()
    sys.exit(x)
