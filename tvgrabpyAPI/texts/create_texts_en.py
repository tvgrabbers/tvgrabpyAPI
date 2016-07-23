#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import pickle, io, os, sys

# If you like to create a translation, you do the following.
# - copy this file to a file with the two letter short for that language replacing "en".
# - also fill this two letter short in the lang variable below
# - replace the text strings with your language version, but:
#       - keep the '%' (%s, %d, etc) markers in place as they get replaced by things like the name of a file
#       - if there is an EOL '\n' at the end, leave it also in place, but also do not add your own
#       - however in some situations you can spread the text over multiple lines
#       - keep any indentations at the start
# - run this new created script to create the langage file for your own use
# - send us this new created script and we probably include it with the language file in the package.
# - check regularily if you need to update the script, update the version and send us the updated version.

# There are a few special categories:
# -  In texts[u'config][u'help'] you should check that the output on the --help option does not excede a width of 80
#    Else use spaces and newlines to layout.
# -  In texts[u'config][u'confighelp'] there are several groups followed by empty lines. If empty they are not printed,
#    but you can use them if you need more space. e.g. 1 - 10, 11 - 16, 21 -  39, 41 - 52, 61 - 67, 71 - 77, 81 - 87, 91 - 139, ...

name = 'tv_grab_text'
version = (1, 0, 0)
lang = 'en'
language = 'English'

def load_texts():
    texts = {
        u'config':{
            u'error':{
                -2: u'Loaded the %s texts file\n' % (language),
                -1: u'Error creating message text! (%s, %s: %s)\n',
                0: u'Text message (%s, %s: %s) not Found!\n',
                1: u'No valid source description for %s found. Disableing it!\n',
                2: u'You can not run this script as root, except with --configure.\n' + \
                    'If you run --configure as root, the configuration is placed in\n' + \
                    '"/etc/tvgrabpyAPI/" and used as fall-back default configuration.\n',
                3: u'Error updating to new Config.\n',
                4: u'Please remove the old config and Re-run me with the --configure flag.\n',
                5: u'Updated the configfile %s!\n',
                6: u'Check if you are fine with the settings.\n',
                7: u'If this is a first install, you have to enable the desired channels!\n',
                8: u'Creating config file: %s\n',
                9: u'Error writing new Config. Trying to restore an old one.\n',
                10: u'Created the configfile %s!\n',
                11: u'Updated the options in the configfile %s!\n',
                12: u'An offset %s higher then the max is ridiculeous. We reset to %s',
                13: u'We can look a maximum of 14 days ahead. Resetting!\n',
                14: u'Creating %s directory,\n',
                15: u'Cannot write to outputfile: %s\n',
                16: u'Cannot access the config/log directory: %s\n',
                17: u'Cannot open the logfile: %s\n',
                18: u'Using config file: %s\n',
                19: u'Trying to fall back on %s.\n',
                20: u'Cannot write to cachefile: %s\n',
                21: u'Error accessing cachefile(directory): %s\n',
                22: u'Setting All to Fast Mode\n',
                23: u'Setting Channel: %s to Fast Mode\n',
                24: u'Using description length: %d for Channel: %s\n',
                25: u'Maximum overlap 0 means overlap strategy set to: "%s"\n',
                26: u'Maximum overlap 0 means overlap strategy for Channel: %s set to: "%s"\n',
                27: u'Using Maximum Overlap: %d for Channel %s\n',
                28: u'overlap strategy for Channel: %s set to: "%s"\n',
                31: u'Re-run me with the --configure flag.\n',
                32: u'Adding "legacy_xmltvids = True"\n',
                33: u'Run with "--configure" to make it permanent\n',
                34: u'Ignoring unknown section "%s"\n',
                35: u'Ignoring configuration line "%s". Outside any known section.\n',
                36: u'Error reading Config\n',
                37: u'Error while reading a line in the [Configuration] section of config file %s:',
                38: u'Error while reading a line in the [Channels] section of config file %s:',
                39: u'Channel section [%s] ignored. Unknown channel\n',
                40: u'Error while reading a line in the [%s] section of config file %s:',
                41: u'Error reading the Defaults file %s\n',
                43: u'Error reading the datafile on github.\n',
                44: u'Unable to continue with configure!\n',
                45: u'Invalid starttime for %s in combined channel: %s\n  Removing it!',
                46: u'Invalid endtime for %s in combined channel: %s\n  Removing it!',
                62: u'Not all channel info could be retrieved.\n',
                63: u'Try again in 15 minutes or so; or disable the failing source.\n',
                64: u'Source %s (%s) disabled',
                65: u'No detailfetches from Source %s (%s)',
                66: u'Channel specific settings other then the above (only for the active channels):',
                67: u'  prime_source setting: %s (%s) in sourcematching.json not used\n',
                68: u'  Source %s (%s) disabled\n',
                69: u'  Detail Source %s (%s) disabled\n',
                70: u'Error Opening the old config. Creating a new one.\n',
                71: u'Error reading the old config\n'
                },
            u'help':{
                1: u'  A grabber that grabs tvguide data from multiple sources,\n',
                2: u'  combining the data into one XMLTV compatible listing.',
                3: u'Show this text',
                5: u'display version',
                6: u'prints a short description of the grabber',
                7: u'prints a long description in english of the grabber',
                8: u'xmltv required option',
                9: u'returns the preferred method to be called',
                10: u'returns the available sources',
                11: u'disable a numbered source.\n' + \
                    'See "--show-sources" for a list.',
                12: u'returns the available detail sources',
                13: u'returns the available logo sources',
                15: u'disable a numbered source for detailfetches.\n' + \
                    'See "--show-detail-sources" for a list.',
                16: u'disable fetching extra data from ttvdb.com.',
                17: u'Query ttvdb.com for a series-title and optionally store\n' + \
                    'it with the ID in the DB. Enclose the title in quotes!\n' + \
                    'Optionally add a language code after the title.\n',
                18: u'append "%s" to the xmltv id\n',
                19: u'remove as in pre 2.2.8 for source 0 and 1 the sourceid\n' + \
                    'from the chanid to get the xmltvid.',
                20: u'generate all data in UTC time (use with timezone "auto"\n' + \
                    'in mythtv)',
                21: u'create configfile; rename an existing file to *.old.',
                22: u'After running configure, place all active channels in\n' + \
                    'a separate group on top of the list.\n' + \
                    'Only relevant together with the configure option.',
                23: u'name of the configuration file\n' + \
                    '<default = "%s">',
                24: u'save the currently defined options to the config file\n' + \
                    'add options to the command-line to adjust the file.',
                25: u'cache descriptions and use the file to store\n' + \
                    '<default = "%s">',
                26: u'clean the cache of outdated data before fetching',
                27: u'empties the program table before fetching data',
                28: u'empties the ttvdb table before fetching data',
                29: u'file where to send the output <default to the screen>',
                30: u'use for the outputfile Windows codeset (cp1252)\n' + \
                    'instead of utf-8',
                31: u'suppress all log output to the screen.',
                32: u'Sent log-info also to the screen.',
                33: u'do not grab details of programming from any of the\n' + \
                    'detail sources',
                34: u'<default> grab details of programming from one of the\n' + \
                    'detail sources',
                35: u'The day to start grabbing <defaults to 0 is today>',
                36: u'# number of days to grab from the several sources.\n' + \
                    '<max 14 = default>\n' + \
                    'Where every source has itś own max.\n',
                38: u'number of days to grab slow and the rest in fast mode\n' + \
                    'Defaults to all days possible',
                39: u'<default> insert urls to channel icons\n' + \
                    '(mythfilldatabase will then use these)',
                40: u'do not insert urls to channel icons',
                41: u'mark HD programs,\n' + \
                    'do not set if you only record analog SD',
                42: u'<default> translate the grabbed genres into\n' + \
                    'MythTV-genres. See the %s.set file',
                43: u'do not translate the grabbed genres into MythTV-genres.\n' + \
                    'It then only uses the basic genres without possibility\n' + \
                    'to differentiate on subgenre.',
                44: u'maximum allowed length of program descriptions in\n' + \
                    'characters.',
                45: u'what strategy to use to correct overlaps:\n' + \
                    '"avarage" use average of stop and start of next program.\n' + \
                    '          <default>\n' + \
                    '"stop"    keep stop time of current program and adjust\n' + \
                    '          start time.\n' + \
                    '"start"   keep start time of next program and adjust\n' + \
                    '          stop time.\n' + \
                    '"none"    do not use any strategy and see what happens.\n',
                46: u'maximum length of overlap between programming to correct\n' + \
                    '<default 10 minutes>',
                47: u'Give the language to use for system and log messages.\n' + \
                    'At present "en" (default) or "nl"',
                48: u'Only use data from the cache.'
                },
            u'confighelp':{
                0: u'# DO NOT CHANGE THIS VALUE!\n',
                1: u'# See: https://github.com/tvgrabbers/tvgrabnlpy/wiki/Over_de_configuratie\n',
                2: u'# This is a list with default options set on running with --configure (-C)\n',
                3: u'# Many can be overruled on the commandline.\n',
                4: u'# Be carefull with manually editing. Invalid options will be\n',
                5: u'# silently ignored. Boolean options can be set with True/False,\n',
                6: u'# On/Off or 1/0. Leaving it blank sets them on. Setting an invalid\n',
                7: u'# value sets them off. You can always check the log for the used values.\n',
                8: u'# Options not shown here can not be set this way.\n',
                9: u'',
                10: u'',
                11: u'# Set always_use_json to False to ignore Channelname, Channelgroup \n',
                12: u'# and prime_source set in the .json datafile if they are set different\n',
                13: u'# in this configuration file. If you do not have set any of those yourself\n',
                14: u'# leave the value to True to profite from all updates.\n',
                15: u'',
                16: u'',
                21: u'# The following are tuning parameters. You normally do not need to change them.\n',
                22: u'# global_timeout is the maximum time in seconds to wait for a fetch to complete\n',
                23: u'#    before calling it a time-out failure.\n',
                24: u'# max_simultaneous_fetches is the maximum number of simultaneous fetches\n',
                25: u'#    that are allowed.\n',
                26: u'#    With the growing number of sources it is possible that they all together\n',
                27: u'#    try to get their page. This could lead to congestion and failure.\n',
                28: u'#    If you see often "incomplete read failures" or "get_page timed out", you\n',
                29: u'#    can try raising the first or lowering the second.\n',
                30: u'#    This won\'t significantly alter the total runtime as this is mostley determined\n',
                31: u'#    by the highest number of fetches from a single source and the mandatory.\n',
                32: u'#    waittime in between those fetches to not overload their resources.\n',
                33: u'#    However all basepage fetches are retried on failure and a detailpagefailure\n',
                34: u'#    can triger a retry on one of the other detailsources. So a lot of failures\n',
                35: u'#    especially on detail source can increase the total runtime.\n',
                36: u'',
                37: u'',
                38: u'',
                39: u'',
                41: u'# This handles what goes to the log and screen\n',
                42: u'# 0 Nothing (use quiet mode to turns off screen output, but keep a log)\n',
                43: u'# 1 include Errors and Warnings\n',
                44: u'# 2 include page fetches\n',
                45: u'# 4 include (merge) summaries\n',
                46: u'# 8 include detail fetches and ttvdb lookups to the screen\n',
                47: u'# 16 include detail fetches and ttvdb lookups to the log\n',
                48: u'# 32 include matchlogging (see below)\n',
                49: u'# 64 Title renames\n',
                50: u'# 128 ttvdb failures\n',
                51: u'# 256 DataTreeGrab Warnings\n',
                52: u'',
                61: u'# What match results go to the log/screen (needs code 32 above)\n',
                62: u'# 0 = Log Nothing (just the overview)\n',
                63: u'# 1 = log not matched programs added\n',
                64: u'# 2 = log left over programs\n',
                65: u'# 4 = Log matches\n',
                66: u'# 8 = Log group slots\n',
                67: u'',
                71: u'# Set "mail_log" to True to send the log to the mailaddress below\n',
                72: u'# Also set the mailserver and port apropriate\n',
                73: u'# SSL/startTLS is NOT supported at present. Neither is authentication\n',
                74: u'# Make sure to first test on a console as mailing occures after \n',
                75: u'# closing of the logfile!\n',
                76: u'',
                77: u'',
                81: u'# Possible values for ratingstyle are:\n',
                82: u'#   long  : add the long descriptions and the icons\n',
                83: u'#   short : add the one word descriptions and the icons\n',
                84: u'#   single: add a single string (mythtv only reads the first item)\n',
                85: u'#   none  : don\'t add any\n',
                86: u'',
                87: u'',
                91: u'# These are the channeldefinitions. You can disable a channel by placing\n',
                92: u'# a "#" in front. Seperated by ";" you see on every line: The Name,\n',
                93: u'# the group, the chanID, the ID\'s for the sources in the order as\n',
                94: u'# returned by the "--show-sources" option (where source 0 does not exist)\n',
                95: u'# and finally the iconsource and name. You can change the names to suit \n',
                96: u'# your own preferences. A missing ID means the source doesn\'t supply the channel.\n',
                97: u'# Removing an ID disables fetching from that source, but keep the ";"s in place.\n',
                98: u'# But you better use the "disable_source" option as described below.\n',
                99: u'# Set iconsource to 99, to add your own full url.\n',
                100: u'#\n',
                101: u'# To specify further Channel settings you can add sections in the form of\n',
                102: u'# [Channel <channelID>], where <channelID> is the third item on the line.\n',
                103: u'# See the WIKI at https://github.com/tvgrabbers/tvgrabnlpy/wiki for further\n',
                104: u'# descriptions. You can use the following tags:\n',
                105: u'# Boolean values (True, 1, on or no value means True. Everything else False):\n',
                106: u'#   fast, compat, legacy_xmltvids, logos, cattrans, mark_hd, add_hd_id,\n',
                107: u'#   disable_ttvdb, use_split_episodes\n',
                108: u'#     legacy_xmltvids: is only valid for the Dutch/Flemish grabber\n',
                109: u'#     \n',
                110: u'#     add_hd_id: if set to True will create two listings for the given channel.\n',
                111: u'#     One normal one without HD tagging and one with \'-hd\' added to the ID\n',
                112: u'#     and with the HD tags. This will overrule any setting of mark_hd\n',
                113: u'# Integer values:\n',
                114: u'#   slowdays, max_overlap, desc_length, prime_source, prefered_description\n',
                115: u'#   disable_source, disable_detail_source\n',
                116: u'#     prime_source is the source whose timings and titles are dominant\n',
                117: u'#     It defaults to 2 for rtl channels, 4 for NPO channels, 5 for Dutch regional\n',
                118: u'#     and 6 for group 2 and 9 (Flemmisch) channels or else the first available\n',
                119: u'#     source as set in sourcematching.json (2, 4, 10, 12, 7, 3, 5, 1, 9, 6, 8, 11)\n',
                120: u'#     prefered_description (1-12) is the source whose description, if present,\n',
                121: u'#     is used. It defaults to the longest description found.\n',
                122: u'#     with disable_source and disable_detail_source you can disable a source\n',
                123: u'#     for that channel either al together or only for the detail fetches\n',
                124: u'#     disabling an unavailable source has no effect.\n',
                125: u'#     With the commandline options: "--show-sources" and "--show-detail-sources"\n',
                126: u'#     you can get a list of available sources and their ID\n',
                127: u'# String values:\n',
                128: u'#   overlap_strategy (With possible values): \n',
                129: u'#     average, stop, start; everything else sets it to none\n',
                130: u'#   xmltvid_alias: This is a string value to be used in place of the chanid\n',
                131: u'#     for the xmltvID. Be careful not to set it to an existing chanid.\n',
                132: u'#     It can get set by "--configure" on chanid changes! See also the WIKI\n',
                133: u'\n',
                134: u'',
                135: u'',
                136: u'',
                137: u'',
                138: u'',
                139: u'',
                140: u'',
                141: u'# This is a list of titles containing a ":" not to split\n',
                142: u'# in a title and a subtitle\n',
                143: u'# These will mainly be spin-off series like "NCIS: Los Angeles"\n',
                144: u'# Movies and programs already having a subtitle are automatically excluded.\n',
                145: u'',
                146: u'# This is a list of grouptitles in titles containing a ":"\n',
                147: u'# to remove from the title\n',
                148: u'# For instance "KRO detectives".\n',
                149: u'',
                150: u'# This is a list of titles to rename.\n',
                151: u'# For instance "navy NCIS" to "NCIS".\n',
                152: u'# This among others to cover diferent naming on separate sources.\n',
                153: u'',
                154: u'# This is a list of genres to include for detail page lookups.\n',
                155: u'# Any program without any of these genres are excluded from\n',
                156: u'# detail-page fetching. Use the pre-cattrans genres!\n',
                157: u'# Add "all" to this list to include all programs\n',
                158: u'# Add "none" to include programs without genre info\n',
                159: u'',
                160: u'# These are the translation lists for:\n',
                161: u'# to common genre:subgenre. If you have cattrans enabled, they will next\n',
                162: u'# be converted according to the list further down.\n',
                163: u'',
                164: u'# The genres from:\n',
                165: u'# %s are treated as subgenres\n',
                166: u'# These are lists of genres to add to these subgenres\n',
                167: u'# New found "subgenres" are automatically added and matched on generic rules\n',
                168: u'',
                169: u'# This is the "Genre:Subgenre" conversion table used by cattrans\n',
                170: u'# "Genre:Subgenre" will automatically be converted to lowercase\n',
                171: u'# and leading and following spaces will be removed\n',
                172: u'# It will automatically get sorted with the genres without\n',
                173: u'# a subgenre at the top.\n',
                174: u'# Also new found values will be added on every new scan\n',
                175: u'',
                176: u'# Behind the "=" you can supply the category to be used\n',
                177: u'# If a category value is empty the main category or an existing\n',
                178: u'# default will be used\n',
                179: u'# If a main category is empty the default will be supplied\n',
                180: u'# and used. If no default exists "Unknown" will be used.\n',
                181: u'# You should regualary check on new main categories\n',
                182: u'# so they don\'t get translated to "Unknown"\n',
                183: u'',
                184: u''
                },
            u'mergeinfo':{
                1: u'We merged %s into %s\n',
                2: u'Since both were active, we have not set an alias\n',
                3: u'If you want to use the old chanid %s as xmltvid\n',
                4: u'you have to add:\n',
                5: u'to the channel configuration for %s\n',
                6: u'Since the old chanid was active, we have set an alias\n',
                7: u'to the channel configuration for %s\n',
                8: u'Since %s already has an xmltvid_alias set\n',
                9: u'we have not changed this.\n',
                10: u'If you want to use the old chanid %s as xmltvid\n',
                11: u'you have to change:\n',
                12: u'to:',
                13: u'in the channel configuration for %s\n',
                14: u'We could not check for any selfset options on the old chanid: %s\n',
                15: u'So check the settings for the new chanid: %s\n'
                },
            u'stats':{
                72: u'Execution complete.\n',
                73: u'Fetch statistics for %s programms on %s channels:\n',
                74: u' Start time: %s\n',
                75: u'   End time: %s\n',
                76: u'   Duration: %s\n',
                77: u'%6.0f page(s) fetched, of which %s failed\n',
                78: u'%6.0f cache hits\n',
                79: u'%6.0f succesful ttvdb.com lookups\n',
                80: u'%6.0f    failed ttvdb.com lookups\n',
                81: u'  Time/page: %s seconds\n',
                82: u'%6.0f page(s) fetched from theTVDB.com\n',
                83: u'%6.0f failure(s) on theTVDB.com\n',
                84: u'%6.0f   base page(s) fetched from %s\n',
                85: u'%6.0f detail page(s) fetched from %s\n',
                86: u'%6.0f failure(s) on %s\n'
                },
            u'other':{
                0: u'Grabber API combining multiple sources.',
                1: u'The available sources are: ',
                2: u'The available detail sources are: ',
                3: u'The available logo sources are: ',
                4: u' 99: Your own full logo url',
                5: u'Start time of this run: %s\n',
                6: u'Version',
                7: u'Language',
                8: u'There is a newer stable API release available on github!\n',
                9: u'Goto: %s\n',
                10: u'There is a newer stable frontend release available!\n',
                11: u'The channel/source matching data is newer!\n',
                12: u'Run with "--configure" to implement it\n'
                }},
        u'IO':{
            u'error':{
                1: u'File: "%s" not found or could not be accessed.\n',
                2: u'%s is not encoded in %s.\n',
                3: u'%s has invalid encoding %s.\n',
                10: u'If you want assistence, please attach your configuration and log files!\n',
                11: u'An unexpected error has occured in the %s thread:\n',
                12: u'An unexpected error has occured:\n',
                13: u'Unrecognized log-message: %s of type %s\n',
                14: u'While fetching the base pages\n',
                15: u'The current detail url is: %s\n',
                16: u'While fetching the detail pages\n',
                20: u'No cachefile given. Cache function disabled!\n',
                21: u'The cache directory is not accesible. Cache function disabled!\n',
                22: u'Error loading the database: %s.db (possibly corrupt)\n',
                23: u'Trying to load a backup copy',
                24: u'Failed to load the database: %s.db\n',
                25: u'Disableing Cache function',
                26: u'Database Error\n'
                },
            u'other':{
                1: u'Verifying the database\n'}},
        u'fetch':{
            u'error':{
                1: u'get_page timed out on (>%s s): %s\n',
                2: u'An unexpected error "%s:%s" has occured while fetching page: %s\n',
                3: u'Cannot open url %s\n',
                4: u'Cannot parse url %s: code=%s\n',
                11: u'Error processing %s-function %s for source %s\n',
                12: u'The supplied data was: %s\n',
                21: u'Channel %s seems to be waiting for %s lost detail requests from %s.\n',
                22: u'Setting it to ready\n',
                23: u'Error processing the detailpage: %s\n',
                24: u'Error processing the detail2page: %s\n',
                25: u'Error retrieving the URL for source: %s from the json data_def\n',
                26: u'Error reading the %s-page: %s\n',
                27: u'Unable to veryfy the right offset for the basepage: %s.\n',
                28: u'Skip channel=%s on %s!, day=%d. Wrong date!\n',
                29: u'Unexpected Error retrieving a %s-page from: %s\n',
                30: u'Unable to get channel info from %s\n',
                31: u'Fatal Error processing the basepages from %s\n',
                32: u'Setting them all to being loaded, to let the other sources finish the job\n',
                33: u'Can not determine program title for "%s" on channel: %s, source: %s\n',
                34: u'Can not determine timings for "%s" on channel: %s, source: %s\n',
                35: u'Page %s returned no data\n',
                36: u'Removing "%s" from "%s"\n',
                37: u'Splitting title "%s"\n',
                38: u'Renaming "%s" to "%s"\n',
                51: u'No Data from %s for channel: %s\n',
                52: u'Detail sources: %s died.\n',
                53: u'So we stop waiting for the pending details for channel %s\n',
                },
            u'report':{
                1: u'Now fetching %s(xmltvid=%s%s) from %s\n',
                2: u'Now fetching %s channel(s) from %s\n',
                3: u'Now fetching the %s channelgroup from %s\n',
                4: u'    (channel %s of %s) for day %s of %s.\n',
                5: u'    (channel %s of %s) for %s days.\n',
                6: u'    (channel %s of %s) for periode %s of %s).\n',
                7: u'    (channel %s of %s) for %s days, page %s.\n',
                8: u'    for day %s of %s.\n',
                9: u'    for %s days.\n',
                10: u'    for periode %s of %s.',
                11: u'    for %s days, page %s.\n',
                12: u'\nRetrieving day %s for channel %s source %s from the cache.\n',
                15: u'Skip channel %s on %s, day=%d. No data\n',
                16: u'Skip channel %s on %s!. No data',
                17: u'Skip channel %s on %s!, periode=%d. No data\n',
                18: u'Skip channel %s on %s!, page=%d. No data\n',
                19: u'Skip day %d on %s. No data\n',
                20: u'Skip %s. No data\n',
                21: u'Skip periode %d on %s. No data\n',
                22: u'Skip page %d on %s. No data\n',
                23: u'Skip channelgroup %s on %s!, day=%d. No data\n',
                24: u'Skip channelgroup %s on %s!. No data',
                25: u'Skip channelgroup %s on %s!, periode=%d. No data\n',
                26: u'Skip channelgroup %s on %s!, page=%d. No data\n',
                31: u'[fetch failed or timed out] %s:(%3.0f%%) %s\n',
                32: u'[%s fetch] %s:(%3.0f%%) %s\n',
                33: u'      [cached] %s:(%3.0f%%) %s\n',
                34: u'    [no fetch] %s:(%3.0f%%) %s\n',
                41: u'Now Checking cache for %s programs on %s(xmltvid=%s%s)\n',
                42: u'Now fetching details for %s programs on %s(xmltvid=%s%s)\n',
                43: u'    (channel %s of %s) for %s days.\n',
                },
            u'stats':{
                1: u'Detail statistics for %s (channel %s of %s)\n',
                2: u'%6.0f cache hit(s)\n',
                3: u'%6.0f without details in cache\n',
                4: u'%6.0f succesful ttvdb lookups\n',
                5: u'%6.0f    failed ttvdb lookups\n',
                6: u'%6.0f detail fetch(es) from %s.\n',
                7: u'%6.0f failure(s)\n',
                8: u'%6.0f without detail info\n',
                9: u'%6.0f left in the %s queue to process\n',
                10: u'%6.0f excluded by genre\n'
                },
            u'other':{
                1: u'  Downloading %s.json...\n',
                u'': u''}},
        u'merge':{
            u'error':{
                },
            u'stats':{
                1: u'Now adding %s programs from %s to %s\n',
                2: u'Now merging %s programs from %s into %s programs from %s\n',
                3: u'    (channel %s of %s)\n',
                5: u'Add',
                6: u'Merge',
                7: u' source',
                8: u'channel',
                9: u'%s statistics for %s (channel %s of %s)\n        from %s %s\n',
                10: u'%7.0f programs in %s for range: %s - %s\n    (%2.0f groupslots),\n',
                11: u'%7.0f programs in %s for range: %s - %s\n    (%2.0f groupslots)\n',
                12: u'%7.0f programs matched on time and name\n',
                13: u'%7.0f programs added new\n',
                14: u'%7.0f programs added to group slots\n',
                15: u'%7.0f programs generically matched on name to get genre\n',
                16: u'%7.0f programs left unmatched in %s\n',
                17: u'Now%4.0f programs of which %2.0f groupslots\n',
                18: u'and%4.0f titles without associated genre.\n',
                19: u'Detail',
                31: u'Added from  %s:%s: %s Genre: %s.\n',
                32: u'Leftover in %s:%s: %s Genre: %s.\n',
                33: u'Match from  %s:%s: %s Genre: %s.\n',
                34: u'      from  %s:%s: %s Genre: %s.\n',
                35: u'Kept unmatched:            %s: %s Genre: %s.\n',
                36: u'      on time and title to:%s: %s Genre: %s.\n',
                37: u'Added to groupslot:        %s: %s Genre: %s.\n',
                38: u'',
                39: u'',
                }},
        u'ttvdb':{
            u'error':{
                1: u'Sorry, thetvdb.com lookup is disabled!\n',
                2: u'Please supply a series title!\n',
                3: u'Invalid language code: "%s" supplied falling back to "en"\n',
                11: u'Error retreiving an ID from theTVdb.com\n',
                12: u'Error retreiving episodes from theTVDB.com\n',
                13: u'  No ttvdb id for "%s" on channel %s\n',
                14: u'ttvdb lookup for "%s: %s"\n',
                15: u'ttvdb failure for "%s: %s" on channel %s\n',
                },
            u'frontend':{
                0: u'',
                1: u'The series "%s" is already saved under ttvdbID: %s -> %s',
                2: u'    for the languages: (%s)\n',
                3: u'The series "%s" is not jet known!\n',
                4: u'No match for %s is found on theTVDB.com',
                5: u'theTVDB Search Results:',
                6: u'Enter choice (first number, q to abort):',
                7: u'Removing old instance',
                8: u'Adding "%s" under aliasses "%s" and "%s" as ttvdbID: %s to the database for lookups!',
                9: u'Adding "%s" under alias "%s" as ttvdbID: %s to the database for lookups!',
                10: u'Adding "%s" ttvdbID: %s to the database for lookups!'
                }}}
    return texts

def create_pickle(texts):
    fle_name = u'%s/%s.%s' % (os.path.abspath(os.curdir), name, lang)

    if os.path.isfile(fle_name):
        print(u'The language file %s already exists.\nDo you want to overwrite it [Y|N]?' % fle_name)
        while True:
            x = sys.stdin.read(1)
            if x in ('n', 'N'):
                print(u'Exiting')
                sys.exit(0)

            elif x in ('Y', 'y'):
                break

        os.remove(fle_name)

    print(u'Writing %s language file' % language)
    fle = open(fle_name, 'w')
    text_dict = {}
    text_dict['lang'] = lang
    text_dict['language'] = language
    text_dict['version'] = version
    text_dict['texts'] = texts
    pickle.dump(text_dict, fle)

def main():
    texts = load_texts()
    create_pickle(texts)

# allow this to be a module
if __name__ == '__main__':
    sys.exit(main())
