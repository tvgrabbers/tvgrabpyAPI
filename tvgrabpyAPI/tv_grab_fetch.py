#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Python 3 compatibility
from __future__ import unicode_literals
# from __future__ import print_function

import re, sys, traceback, difflib
import time, datetime, pytz, random
import requests, httplib, socket, json
from DataTreeGrab import DataTreeShell, is_data_value, data_value, dtWarning, dtDataWarning, dtdata_defWarning, dtParseWarning, dtCalcWarning, dtUrlWarning, dtLinkWarning
from tv_grab_channel import ProgramNode
from threading import Thread, RLock, Semaphore, Event
from xml.sax import saxutils
from xml.etree import cElementTree as ET
from Queue import Queue, Empty
from copy import deepcopy, copy
try:
    from html.entities import name2codepoint
except ImportError:
    from htmlentitydefs import name2codepoint

try:
    unichr(42)
except NameError:
    unichr = chr    # Python 3

class Functions():
    """Some general Fetch functions"""

    def __init__(self, config):
        self.config = config
        self.max_fetches = Semaphore(self.config.opt_dict['max_simultaneous_fetches'])
        self.count_lock = RLock()
        self.progress_counter = 0
        self.channel_counters = {}
        self.source_counters = {}
        self.source_counters['total'] = {}
        self.raw_json = {}

    # end init()

    def update_counter(self, cnt_type, source_id=-1, chanid=None, cnt_add=True, cnt_change=1):
        #source_id: -99 = cache, -98 = jsondata, -1 = ttvdb
        if not isinstance(cnt_change, int) or cnt_change == 0:
            return

        if not cnt_type in ('base', 'detail', 'fail', 'lookup', 'lookup_fail', 'queue', 'jsondata', 'failjson', 'exclude'):
            return

        if not isinstance(cnt_change, int) or cnt_change == 0:
            return

        with self.count_lock:
            if not cnt_add:
                cnt_change = -cnt_change

            if chanid != None and isinstance(chanid, (str, unicode)):
                if not chanid in self.channel_counters.keys():
                    self.channel_counters[chanid] = {}

                if not cnt_type in self.channel_counters[chanid].keys():
                    self.channel_counters[chanid][cnt_type] = {}

                if not source_id in self.channel_counters[chanid][cnt_type].keys():
                    self.channel_counters[chanid][cnt_type][source_id] = 0

                self.channel_counters[chanid][cnt_type][source_id] += cnt_change

            if not source_id in self.source_counters.keys():
                self.source_counters[source_id] = {}

            if not cnt_type in self.source_counters[source_id].keys():
                self.source_counters[source_id][cnt_type] = 0

            self.source_counters[source_id][cnt_type] += cnt_change
            if isinstance(source_id, int) and (source_id >= 0 or source_id == -98):
                if cnt_type in self.source_counters['total'].keys():
                    self.source_counters['total'][cnt_type] += cnt_change

                else:
                    self.source_counters['total'][cnt_type] = cnt_change
    # end update_counter()

    def get_counter(self, cnt_type, source_id=-1, chanid=None):
        if chanid == None:
            if not source_id in self.source_counters.keys():
                return 0

            if not cnt_type in self.source_counters[source_id].keys():
                return 0

            return self.source_counters[source_id][cnt_type]

        elif not chanid in self.channel_counters.keys():
            return 0

        elif not cnt_type in self.channel_counters[chanid].keys():
            return 0

        elif not source_id in self.channel_counters[chanid][cnt_type].keys():
            return 0

        return self.channel_counters[chanid][cnt_type][source_id]
    # end get_counter()

    def get_page(self, url, encoding = None, accept_header = None, txtdata = None, is_json = False):
        """
        Wrapper around get_page_internal to catch the
        timeout exception
        """
        try:
            if isinstance(url, (list, tuple)) and len(url) > 0:
                encoding = url[1] if len(url) > 1 else None
                accept_header = url[2] if len(url) > 2 else None
                txtdata = url[3] if len(url) > 3 else None
                is_json = url[4] if len(url) >4 else False
                url = url[0]

            txtheaders = {'Keep-Alive' : '300',
                          'User-Agent' : self.config.user_agents[random.randint(0, len(self.config.user_agents)-1)] }

            if not accept_header in (None, ''):
                txtheaders['Accept'] = accept_header

            fu = FetchURL(self.config, url, txtdata, txtheaders, encoding, is_json)
            self.max_fetches.acquire()
            fu.start()
            fu.join(self.config.opt_dict['global_timeout']+1)
            page = fu.result
            self.max_fetches.release()
            if (page == None) or (page =={}) or (isinstance(page, (str, unicode)) and ((re.sub('\n','', page) == '') or (re.sub('\n','', page) =='{}'))):
                return None

            else:
                return page

        except(socket.timeout):
            self.config.log(self.config.text('fetch', 1, (self.config.opt_dict['global_timeout'], url)), 1, 1)
            if self.config.write_info_files:
                self.config.infofiles.add_url_failure('Fetch timeout: %s\n' % url)

            self.max_fetches.release()
            return None
    # end get_page()

    def get_json_data(self, name, version = None, source = -98, url = None, fpath = None):
        self.raw_json[name] = ''
        local_name = '%s.%s.json' % (name, version) if isinstance(version, int) else '%s.json' % (name)
        # Try to find the source files locally
        if isinstance(version, int) or self.config.only_local_sourcefiles:
            # First we try to get it in the supplied location
            try:
                if fpath != None:
                    fle = self.config.IO_func.open_file('%s/%s' % (fpath, local_name), 'r', 'utf-8')
                    if fle != None:
                        return json.load(fle)

            except:
                traceback.print_exc()
                pass

            # And then in the library location if that is not the same
            try:
                if fpath != self.config.source_dir:
                    fle = self.config.IO_func.open_file('%s\%s' % (self.config.source_dir, local_name), 'r', 'utf-8')
                    if fle != None:
                        return json.load(fle)

            except:
                pass

        # Finaly we try to download unless the only_local_sourcefiles flag is set
        if not self.config.only_local_sourcefiles:
            try:
                txtheaders = {'Keep-Alive' : '300',
                              'User-Agent' : self.config.user_agents[random.randint(0, len(self.config.user_agents)-1)] }

                if url in (None, u''):
                    url = self.config.api_source_url

                url = '%s/%s.json' % (url, name)
                self.config.log(self.config.text('fetch', 1,(name, ), 'other'), 2)
                fu = FetchURL(self.config, url, None, txtheaders, 'utf-8', True)
                self.max_fetches.acquire()
                self.update_counter('jsondata', source)
                fu.start()
                fu.join(self.config.opt_dict['global_timeout']+1)
                page = fu.result
                self.max_fetches.release()
                if (page == None) or (page =={}) or (isinstance(page, (str, unicode)) and ((re.sub('\n','', page) == '') or (re.sub('\n','', page) =='{}'))):
                    self.update_counter('failjson', source)
                    if isinstance(version, int):
                        return None

                else:
                    self.raw_json[name] = fu.url_text
                    return page

            except:
                if isinstance(version, int):
                    return None

        # And for the two mainfiles we try to fall back to the library location
        if version == None:
            try:
                fle = self.config.IO_func.open_file('%s/%s' % (self.config.source_dir, local_name), 'r', 'utf-8')
                if fle != None:
                    return json.load(fle)

            except:
                return None

    # end get_json_data()

    def remove_accents(self, name):
        name = re.sub('á','a', name)
        name = re.sub('é','e', name)
        name = re.sub('í','i', name)
        name = re.sub('ó','o', name)
        name = re.sub('ú','u', name)
        name = re.sub('ý','y', name)
        name = re.sub('à','a', name)
        name = re.sub('è','e', name)
        name = re.sub('ì','i', name)
        name = re.sub('ò','o', name)
        name = re.sub('ù','u', name)
        name = re.sub('ä','a', name)
        name = re.sub('ë','e', name)
        name = re.sub('ï','i', name)
        name = re.sub('ö','o', name)
        name = re.sub('ü','u', name)
        name = re.sub('ÿ','y', name)
        name = re.sub('â','a', name)
        name = re.sub('ê','e', name)
        name = re.sub('î','i', name)
        name = re.sub('ô','o', name)
        name = re.sub('û','u', name)
        name = re.sub('ã','a', name)
        name = re.sub('õ','o', name)
        name = re.sub('@','a', name)
        return name
    # end remove_accents()

    def get_offset(self, date):
        """Return the offset from today"""
        cd = self.config.in_fetch_tz(datetime.datetime.now(pytz.utc))
        rd = self.config.in_fetch_tz(date)
        return int(rd.toordinal() -  cd.toordinal())
    # end get_offset()

    def get_fetchdate(self, date):
        """Return the date from today"""
        cd = self.config.in_fetch_tz(datetime.datetime.now(pytz.utc))
        rd = self.config.in_fetch_tz(date)
        return rd.date()
    # end get_fetchdate()

    def merge_date_time(self, date_ordinal, date_time, tzinfo = None, as_utc = True):
        if tzinfo == None:
            tzinfo = self.config.utc_tz

        try:
            rtime = datetime.datetime.combine(datetime.date.fromordinal(date_ordinal), date_time)
            rtime = tzinfo.localize(rtime)
            if as_utc:
                rtime = self.config.in_utc(rtime)

            return rtime

        except:
            return None
    # end merge_date_time()
# end Functions()

class FetchURL(Thread):
    """
    A simple thread to fetch a url with a timeout
    """
    def __init__ (self, config, url, txtdata = None, txtheaders = None, encoding = None, is_json = False):
        Thread.__init__(self)
        self.config = config
        self.url = url
        self.txtdata = txtdata
        self.txtheaders = txtheaders
        self.encoding = encoding
        self.is_json = is_json
        self.raw = ''
        self.result = None

    def run(self):
        try:
            self.result = self.get_page_internal()

        except:
            self.config.log(self.config.text('fetch', 2,  (sys.exc_info()[0], sys.exc_info()[1], self.url)), 0)
            if self.config.write_info_files:
                self.config.infofiles.add_url_failure('%s,%s:\n  %s\n' % (sys.exc_info()[0], sys.exc_info()[1], self.url))

            return None

    def find_html_encoding(self):
        # look for the text '<meta http-equiv="Content-Type" content="application/xhtml+xml; charset=UTF-8" />'
        # in the first 600 bytes of the HTTP page
        m = re.search(r'<meta[^>]+\bcharset=["\']?([A-Za-z0-9\-]+)\b', self.raw[:512].decode('ascii', 'ignore'))
        if m:
            return m.group(1)

    def get_page_internal(self):
        """
        Retrieves the url and returns a string with the contents.
        Optionally, returns None if processing takes longer than
        the specified number of timeout seconds.
        """
        try:
            url_request = requests.get(self.url, headers = self.txtheaders, params = self.txtdata, timeout=self.config.opt_dict['global_timeout']/2)
            self.raw = url_request.content
            encoding = self.find_html_encoding()
            if encoding != None:
                url_request.encoding = encoding

            elif self.encoding != None:
                url_request.encoding = self.encoding

            self.url_text = url_request.text

            if 'content-type' in url_request.headers and 'json' in url_request.headers['content-type'] or self.is_json:
                try:
                    return url_request.json()

                except:
                    return self.url_text

            else:
                return self.url_text

        except (requests.ConnectionError) as e:
            self.config.log(self.config.text('fetch', 3, (self.url, )), 1, 1)
            if self.config.write_info_files:
                self.config.infofiles.add_url_failure('URLError: %s\n' % self.url)

            return None

        except (requests.HTTPError) as e:
            self.config.log(self.config.text('fetch', 4, (self.url, e.code)), 1, 1)
            if self.config.write_info_files:
                self.config.infofiles.add_url_failure('HTTPError: %s\n' % self.url)

            return None

        except (requests.Timeout) as e:
            self.config.log(self.config.text('fetch', 1, (self.config.opt_dict['global_timeout'], self.url)), 1, 1)
            if self.config.write_info_files:
                self.config.infofiles.add_url_failure('Fetch timeout: %s\n' % self.url)

            return None

# end FetchURL

class DataTree(DataTreeShell):
    def __init__(self, source, data_def, warnaction = "default", caller_id = 0):
        self.source = source
        self.config = self.source.config
        self.fetch_string_parts = re.compile("(.*?[.?!:]+ |.*?\Z)")
        DataTreeShell.__init__(self, data_def, warnaction = warnaction, warngoal = self.config.logging.log_queue, caller_id = caller_id)
        self.print_tags = source.print_tags
        self.print_searchtree = source.print_searchtree
        self.show_result = source.show_parsing
        self.fle = source.test_output
        #~ sys.modules['DataTreeGrab']._warnings.filterwarnings('ignore', category = dtLinkWarning, message = 'Regex "\\\d\*/\?\(\\\d\*\)\.\*" in: .*?', caller_id = caller_id)
        #~ sys.modules['DataTreeGrab']._warnings.filterwarnings('ignore', category = dtLinkWarning, message = 'Regex "\(\\\d\*\)/\.\*" in: .*?', caller_id = caller_id)

    def get_string_parts(self, sstring, header_items = None):
        if not isinstance(header_items, (list, tuple)):
            header_items = []

        test_items = []
        for hi in header_items:
            if isinstance(hi, (str, unicode)):
                test_items.append((hi.lower(), hi))

            elif isinstance(hi, (list, tuple)):
                if len(hi) > 0 and isinstance(hi[0], (str, unicode)):
                    hi0 = hi[0].lower()
                    if len(hi) > 1 and isinstance(hi[1], (str, unicode)):
                        hi1 = hi[1]

                    else:
                        hi1 = hi[0]

                    test_items.append((hi0, hi1))

        string_parts = self.fetch_string_parts.findall(sstring)
        string_items = {}
        act_item = 'start'
        string_items[act_item] = []
        for dp in string_parts:
            if dp.strip() == '':
                continue

            if dp.strip()[-1] == ':':
                act_item = dp.strip()[0:-1].lower()
                string_items[act_item] = []

            else:
                for ti in test_items:
                    if dp.strip().lower()[0:len(ti[0])] == ti[0]:
                        act_item = ti[1]
                        string_items[act_item] = []
                        string_items[act_item].append(dp[len(ti[0]):].strip())
                        break

                else:
                    string_items[act_item].append(dp.strip())

        return string_items

    def add_on_link_functions(self, fid, data = None, default = None):
        def split_kommastring(dstring):

            return re.sub('\) ([A-Z])', '), \g<1>', \
                re.sub(self.config.language_texts['and'], ', ', \
                re.sub(self.config.language_texts['and others'], '', dstring))).split(',')

        def add_person(prole, pname, palias = None):
            if pname in ('', None):
                return

            if pname[-1] in '\.,:;-':
                pname = pname[:-1].strip()

            if not prole in credits:
                credits[prole] = []

            if prole in ('actor', 'guest'):
                p = {'name': pname, 'role': palias}
                credits[prole].append(p)

            else:
                credits[prole].append(pname)

        try:
            # split logo name and logo provider
            if fid == 101:
                if is_data_value(0, data, str):
                    d = data[0].split('?')[0]
                    for k, v in self.config.xml_output.logo_provider.items():
                        if d[0:len(v)] == v:
                            return (d[len(v):], k)

                return ('',-1)

            # Extract roles from a set of lists or named dicts
            if fid == 102:
                credits = {}
                if len(data) == 0:
                    return default

                if len(data) == 1 and isinstance(data[0], (list,tuple)):
                    for item in data[0]:
                        if not isinstance(item, dict):
                            continue

                        for k, v in item.items():
                            if k.lower() in self.config.roletrans.keys():
                                role = self.config.roletrans[k.lower()]
                                for pp in v:
                                    pp = pp.split(',')
                                    for p in pp:
                                        cn = p.split('(')
                                        if len(cn) > 1:
                                            add_person(role, cn[0].strip(), cn[1].split(')')[0].strip())

                                        else:
                                            add_person(role, cn[0].strip())

                    return credits

                if len(data) < 2:
                    return default

                if isinstance(data[1], (list,tuple)):
                    for item in range(len(data[0])):
                        if item >= len(data[1]):
                            continue

                        if data[1][item].lower() in self.config.roletrans.keys():
                            role = self.config.roletrans[data[1][item].lower()]
                            if isinstance(data[0][item], (str, unicode)):
                                cast = split_kommastring(data[0][item])

                            else:
                                cast = data[0][item]

                            if isinstance(cast, (list, tuple)):
                                for person in cast:
                                    if len(data) > 2 and isinstance(data[2],(list, tuple)) and len(data[2]) > item:
                                        add_person(role, person.strip(), data[2][item])

                                    else:
                                        add_person(role, person.strip())

                elif isinstance(data[1], (str,unicode)) and data[1].lower() in self.config.roletrans.keys():
                    role = self.config.roletrans[data[1].lower()]

                    if isinstance(data[0], (str, unicode)):
                        cast = split_kommastring(data[0])

                    else:
                        cast = data[0]

                    if isinstance(cast, (list, tuple)):
                        for item in range(len(cast)):
                            if len(data) > 2 and isinstance(data[2],(list, tuple)) and len(data[2]) > item:
                                add_person(role, cast[item].strip(), data[2][item])

                            else:
                                add_person(role, cast[item].strip())

                return credits

            # Extract roles from a string
            if fid == 103:
                if len(data) == 0 or data[0] == None:
                    return {}

                if isinstance(data[0], (str, unicode)) and len(data[0]) > 0:
                    tstr = unicode(data[0])
                elif isinstance(data[0], list) and len(data[0]) > 0:
                    tstr = unicode(data[0][0])
                    for index in range(1, len(data[0])):
                        tstr = u'%s %s' % (tstr, unicode(data[0][index]))
                else:
                    return {}

                if len(data) == 1:
                    cast_items = self.get_string_parts(tstr)

                else:
                    cast_items = self.get_string_parts(tstr, data[1])

                credits = {}
                for crole, cast in cast_items.items():
                    if len(cast) == 0:
                        continue

                    elif crole.lower() in self.config.roletrans.keys():
                        role = self.config.roletrans[crole.lower()]
                        cast = split_kommastring(cast[0])

                        for cn in cast:
                            cn = cn.split('(')
                            if len(cn) > 1:
                                add_person(role, cn[0].strip(), cn[1].split(')')[0].strip())

                            else:
                                add_person(role, cn[0].strip())

                return credits

            # Process a rating item
            if fid == 104:
                rlist = []
                if is_data_value(0, data, str):
                    # We treat a string as a list of items with a maximaum length
                    if data_value(1, data, str) == 'as_list':
                        item_length = data_value(2, data, int, 1)
                        unique_added = False
                        for index in range(len(data[0])):
                            code = None
                            for cl in range(item_length):
                                if index + cl >= len(data[0]):
                                    continue

                                tval = data[0][index: index + cl + 1]
                                if tval in self.source.rating.keys():
                                    code = self.source.rating[tval]
                                    break

                            if code != None:
                                if code in self.config.rating["unique_codes"].keys():
                                    if unique_added:
                                        continue

                                    rlist.append(code)
                                    unique_added = True

                                elif self.source.rating[code] in self.config.rating["addon_codes"].keys():
                                    rlist.append(code)

                            elif self.config.write_info_files:
                                self.config.infofiles.addto_detail_list(u'new %s rating => %s' % (self.source.source, code))

                    else:
                        if data[0].lower() in self.source.rating.keys():
                            v = self.source.rating[data[0].lower()]
                            if v in self.config.rating["unique_codes"].keys():
                                rlist.append(v)

                            elif v in self.config.rating["addon_codes"].keys():
                                rlist.append(v)

                        elif self.config.write_info_files:
                            self.config.infofiles.addto_detail_list(u'new %s rating => %s' % (self.source.source, data[0]))

                elif is_data_value(0, data, list):
                #~ elif isinstance(data[0], (list,tuple)):
                    unique_added = False
                    for item in data[0]:
                        if item.lower() in self.source.rating.keys():
                            v = self.source.rating[item.lower()]
                            if v in self.config.rating["unique_codes"].keys():
                                if unique_added:
                                    continue

                                rlist.append(v)
                                unique_added = True

                            elif v in self.config.rating["addon_codes"].keys():
                                rlist.append(v)

                        elif self.config.write_info_files:
                            self.config.infofiles.addto_detail_list(u'new %s rating => %s' % (self.source.source, data[0]))

                return rlist

            # Check the text in data[1] for the presence of keywords to determine genre
            if fid == 105:
                if len(data) < 2 or not isinstance(data[0], dict):
                    return default

                for k, v in data[0].items():
                    for i in range(1, len(data)):
                        if isinstance(data[i], (str, unicode)) and k in data[i]:
                            return v

            # split a genre code in a generic part of known length and a specific part
            if fid == 106:
                if len(data) == 0 or not isinstance(data[0],(str, unicode, list)):
                    return []

                if len(data) == 1:
                    if isinstance(data[0], list):
                        return data[0]

                    else:
                        return [data[0]]


                if isinstance(data[0], list):
                    if len(data[0]) == 0:
                        return []

                    data[0] = data[0][0]

                if not isinstance(data[1], int) or len(data[0]) <= data[1]:
                    return [data[0]]

                return [data[0][:data[1]], data[0][data[1]:]]

            # Return unlisted values to infofiles in a fid 11 dict
            if fid == 107:
                if len(data) < 2 or not isinstance(data[0], (list, tuple)):
                    return default

                if not isinstance(data[1], (list,tuple)):
                    data[1] = [data[1]]

                for index in range(len(data[1])):
                    data[1][index] = data[1][index].lower().strip()

                for sitem in data[0]:
                    for k, v in sitem.items():
                        if k.lower().strip() in data[1]:
                            continue

                        if k.lower().strip() in self.config.roletrans.keys():
                            continue

                        if self.config.write_info_files:
                            self.config.infofiles.addto_detail_list(u'new %s dataitem %s => %s' % (self.source.source, k, v))

            # Return unlisted values to infofiles in a fid 10 list set
            if fid == 108:
                if not self.config.write_info_files:
                    return

                if len(data) < 3 or not isinstance(data[0], (list,tuple)) or not isinstance(data[1], (list,tuple)) or not isinstance(data[2], (list,tuple)):
                    return

                for index in range(len(data[2])):
                    data[2][index] = data[2][index].lower().strip()

                for index in range(len(data[0])):
                    data[0][index] = data[0][index].lower().strip()

                for index in range(len(data[0])):
                    if data[0][index].lower() in data[2]:
                        continue

                    if data[0][index].lower() in self.config.roletrans.keys():
                        continue

                    if index >= len(data[1]):
                        self.config.infofiles.addto_detail_list(u'new %s dataitem %s' % (self.source.source, data[0][index]))

                    else:
                        self.config.infofiles.addto_detail_list(u'new %s dataitem %s => %s' % (self.source.source, data[0][index], data[1][index]))

        except:
            self.config.log([self.config.text('fetch', 11, ('link', fid, self.source.source)), traceback.format_exc()], 1)
            #~ self.config.log([self.config.text('fetch', 11, ('link', fid, source.source)), self.config.text('fetch', 12, (data,)), traceback.format_exc()], 1)
            return default

# end DataTree()

class theTVDB_v1(Thread):
    def __init__(self, config, source_data):
        Thread.__init__(self)
        self.config = config
        self.functions = self.config.fetch_func
        self.quit = False
        self.ready = False
        self.active = True
        self.api_key = "0BB856A59C51D607"
        self.source_lock = RLock()
        # The queue to receive answers on database queries
        self.cache_return = Queue()
        # The queue to receive requests for detail fetches
        self.detail_request = Queue()
        self.config.queues['ttvdb'] = self.detail_request
        self.thread_type = 'ttvdb'
        self.test_output = sys.stdout
        self.print_tags = False
        self.print_roottree = False
        self.print_searchtree = False
        self.show_parsing = False
        self.show_result = False
        self.config.threads.append(self)
        self.local_encoding = self.config.logging.local_encoding
        try:
            self.source_data = source_data
            self.source = self.data_value('name', str)
            self.lang_list = self.data_value('lang-list', list)
            self.detail_keys = {}
            self.detail_keys['series'] = list(self.data_value(["seriesname", "values"], dict).keys())
            self.detail_keys['episodes'] = list(self.data_value(["episodes", "values"], dict).keys())
            self.config.detail_keys['ttvdb'] = self.detail_keys['series']
            self.config.detail_keys['episodes'] = self.detail_keys['episodes']
            self.site_tz = pytz.timezone(self.data_value('site-timezone', str, default = 'utc'))
            self.datatrees = {}
            for ptype in ("seriesid", "seriesname", "episodes"):
                if not self.is_data_value([ptype, 'timezone'], str):
                    self.source_data[ptype]['timezone'] = self.data_value('site-timezone', str, default = 'utc')

                self.datatrees[ptype] = DataTree(self, self.data_value(ptype, dict), 'always', -1)

        except:
            self.config.opt_dict['disable_ttvdb'] = True
            traceback.print_exc()

    def run(self):
        if self.config.opt_dict['disable_ttvdb']:
            return
        try:
            while True:
                if self.quit and self.detail_request.empty():
                    break

                try:
                    crequest = self.detail_request.get(True, 5)

                except Empty:
                    continue

                if (not isinstance(crequest, dict)) or (not 'task' in crequest):
                    continue

                if crequest['task'] == 'update_ep_info':
                    if not 'parent' in crequest:
                        continue

                    if 'pn' in crequest:
                        qanswer = self.get_season_episode(crequest['parent'], crequest['pn'])
                        if qanswer == -1:
                            crequest['parent'].detail_return.put('quit')
                            self.quit = True
                            continue

                        crequest['parent'].detail_return.put({'source': -1, 'data': qanswer, 'pn': crequest['pn']})

                    self.functions.update_counter('queue', -1,  crequest['parent'].chanid, False)
                    continue

                if crequest['task'] == 'last_one':
                    crequest['parent'].detail_data.set()

                if crequest['task'] == 'quit':
                    self.quit = True
                    continue

        except:
            self.config.queues['log'].put({'fatal': [traceback.format_exc(), '\n'], 'name': 'theTVDB'})
            self.ready = True
            return(98)

    def query_ttvdb(self, ptype, pdata, chanid = None):
        if not ptype in self.datatrees.keys() or not isinstance(pdata, dict) or self.config.args.only_cache:
            return

        if 'ttvdbid' in pdata:
            if isinstance(pdata['ttvdbid'], (int, str)):
                pdata['ttvdbid'] = unicode(pdata['ttvdbid'])

        elif 'name' in pdata:
            if isinstance(pdata['name'], (int, str)):
                pdata['name'] = unicode(pdata['name'])

        else:
            return

        pdata['api-key'] = self.api_key
        if (not pdata['lang'] in self.lang_list) and not (pdata['lang'] == 'all' and ptype == 'seriesid'):
             pdata['lang']  = 'en'

        url = self.datatrees[ptype].get_url(pdata)
        if self.print_searchtree:
            print '(url, encoding, accept_header, url_data, is_json)'
            print url


        self.functions.update_counter('detail', -1, chanid)
        page = self.functions.get_page(url)
        if page == None:
            self.functions.update_counter('fail', -1, chanid)
            return None

        self.datatrees[ptype].init_data(page)
        self.datatrees[ptype].extract_datalist()
        data = self.datatrees[ptype].result
        if len(data) == 0:
            self.functions.update_counter('fail', -1, chanid)
            return None

        if self.show_result:
            for p in self.datatrees[ptype].searchtree.result:
                if isinstance(p[0], (str, unicode)):
                    print p[0].encode('utf-8', 'replace')
                else:
                    print p[0]
                for v in range(1,len(p)):
                    if isinstance(p[v], (str, unicode)):
                        print '    ', p[v].encode('utf-8', 'replace')
                    else:
                        print '    ', p[v]

            #~ for p in data:
                #~ for k, v in p.item():
                    #~ if isinstance(v, (str, unicode)):
                        #~ print '    %s = %s'.encode('utf-8', 'replace') % (k, v)
                    #~ else:
                        #~ print '    %s = %s' % (k, v))

        # be nice to the source site
        time.sleep(random.randint(self.config.opt_dict['nice_time'][0], self.config.opt_dict['nice_time'][1]))
        return data

    def get_cache_return(self):
        value = self.cache_return.get(True)
        if value == 'quit':
            self.ready = True
            return -1

        return value

    def get_ttvdb_id(self, name, lang='en', search_db=True, chanid=None):
        def get_id_from_db():
            self.config.queues['cache'].put({'task':'query_id', 'parent': self, 'ttvdb': {'name': name}})
            data = self.get_cache_return()
            if data == -1:
                return -1

            tids = {}
            tidcnt = 0
            tid = 0
            for index in range(len(data)):
                rtdate = data_value([index, 'tdate'], data, datetime.date)
                if self.last_updated == None or (rtdate != None and rtdate < self.last_updated):
                    self.last_updated = rtdate

                rtid = data_value([index, 'tid'], data, int, 0)
                if not rtid in tids.keys() and rtid != 0:
                    tids[rtid] = 1

                else:
                    tids[rtid] += 1

                if tids[rtid] > tidcnt:
                    tidcnt =  tids[rtid]
                    tid = rtid

            return tid

        def check_alias():
            self.config.queues['cache'].put({'task':'query_id', 'parent': self, 'ttvdb_alias': {'alias': name}})
            alias = self.get_cache_return()
            if alias == -1:
                return -1

            if alias == None:
                return name

            return alias

        def get_id_from_ttvdb():
            data = self.query_ttvdb('seriesid', {'name': series_name, 'lang': lang}, chanid)
            if data == None:
                return 0

            tids = {}
            tidcnt = 0
            tid = 0
            for index in range(len(data)):
                rtdate = data_value([index, 'tdate'], data, datetime.date)
                if self.last_updated == None or (rtdate != None and rtdate < self.last_updated):
                    self.last_updated = rtdate

                rtid = data_value([index, 'tid'], data, int, 0)
                if not rtid in tids.keys() and rtid != 0:
                    tids[rtid] = 1

                else:
                    tids[rtid] += 1

                if tids[rtid] > tidcnt:
                    tidcnt =  tids[rtid]
                    tid = rtid

            return tid

        self.last_updated = None
        if search_db:
            tid = get_id_from_db()
            if tid == -1:
                self.ready = True
                return -1

            if isinstance(self.last_updated, datetime.date) and (datetime.date.today() - self.last_updated).days <= 30:
                # The last check is less then 30 days old
                # We'll  use the episode info in the database (or signal not found if tid == 0)
                if tid == 0:
                    return 0

                return {'tid': tid, 'tdate': self.last_updated, 'name': name}

            elif tid > 0 and isinstance(self.last_updated, datetime.date) and (datetime.date.today() - self.last_updated).days > 30 and not self.config.args.only_cache:
                data = self.query_ttvdb('seriesname', { 'ttvdbid': tid, 'lang': lang})
                if is_data_value([0, 'last updated'], data, datetime.date) and \
                    data_value([0, 'last updated'], data, datetime.date) < self.last_updated:
                        # No updates on theTVDB
                        return {'tid': tid, 'tdate': self.last_updated, 'name': name}

        # First we look for a known alias
        series_name = check_alias()
        langs = self.config.ttvdb_langs
        if lang not in self.config.ttvdb_langs and lang in self.lang_list:
            langs.append(lang)

        try:
            if tid == 0 and not self.config.args.only_cache:
                tid = get_id_from_ttvdb()

            if tid == 0:
                # No data
                return 0

            #We look for other languages
            data = self.query_ttvdb('seriesid', {'name': series_name, 'lang': 'all'}, chanid)
            db_update = []
            if isinstance(data, list):
                for index in range(len(data)):
                    if data_value([index, 'tid'], data, int) == tid and data_value([index, 'lang'], data, str) in langs:
                        db_update.append(data[index])

                if len(db_update) > 0:
                    self.config.queues['cache'].put({'task':'add', 'ttvdb': db_update})

        except:
            self.config.log([self.config.text('ttvdb', 11), traceback.format_exc()])
            return 0

        # And we retreive the episodes
        if self.get_all_episodes(tid, lang, chanid) == -1:
            return -1

        return {'tid': int(tid), 'tdate': datetime.date.today(), 'name': series_name}

    def get_all_episodes(self, tid, lang='en', chanid=None):
        try:
            eps = []
            langs = self.config.ttvdb_langs
            if lang not in self.config.ttvdb_langs and lang in self.lang_list:
                langs.append(lang)

            for l in langs:
                data = self.query_ttvdb('episodes', {'ttvdbid': tid, 'lang': l}, chanid)
                if not isinstance(data, list):
                    # No data
                    continue

                for ep in data:
                    if not isinstance(ep, dict):
                        continue

                    sid = data_value('sid', ep, int, -1)
                    eid = data_value('eid', ep, int, -1)
                    if sid == -1 or eid == -1:
                        continue

                    title = data_value('episode title', ep, str, 'Episode %s' % eid)
                    desc = data_value('description', ep, str, None)
                    airdate = data_value('airdate', ep, datetime.date, None)
                    rating = data_value('star-rating', ep, float, None)
                    eps.append({'tid': int(tid),
                                        'sid': int(sid),
                                        'eid': int(eid),
                                        'episode title': title,
                                        'airdate': airdate,
                                        'lang': l,
                                        'star-rating': rating,
                                        'description': desc})

        except:
            self.config.log([self.config.text('ttvdb', 12), traceback.format_exc()])
            return

        self.config.queues['cache'].put({'task':'add', 'episodes': eps})

    def get_season_episode(self, parent = None, data = None):
        def prepare_return(rdata, tid, lang):
            if data_value('lang', rdata, str) != lang:
                self.config.queues['cache'].put({'task':'query', 'parent': self, \
                        'ep_by_id': {'tid': tid, 'sid': data_value('sid', rdata, int, 0), 'eid':data_value('eid', rdata, int, 0) , 'lang': lang}})
                r = self.get_cache_return()
                if r == -1:
                    return -1

                if is_data_value(0, r, dict):
                    rdata = r[0]

            return {'season': data_value('sid', rdata, int, 0),
                    'episode': data_value('eid', rdata, int, 0),
                    'airdate': data_value('airdate', rdata, datetime.date, None),
                    'episode title': data_value('episode title', rdata, str),
                    'description': data_value('description', rdata, str),
                    'star-rating': data_value('star-rating', rdata, float, None)}

        if self.config.opt_dict['disable_ttvdb'] or parent.opt_dict['disable_ttvdb'] or not isinstance(data, ProgramNode):
            return 0

        if parent == None:
            parent = data.channel_config

        if parent.group in self.config.ttvdb_disabled_groups:
            # We do not lookup for regional channels and radio
            return 0

        lang = self.config.group_language[parent.group]
        tid = self.get_ttvdb_id(data.get_value('name'), lang, chanid = parent.chanid)
        if tid == -1:
            return -1

        if tid in (None, 0) or not isinstance(tid, dict):
            self.functions.update_counter('lookup_fail', -1, parent.chanid)
            self.config.log(self.config.text('ttvdb', 13, (data.get_value('name'), parent.chan_name)), 128)
            return 0

        # First we just look for a matching subtitle
        tid = tid['tid']
        self.config.queues['cache'].put({'task':'query', 'parent': self, \
                'ep_by_title': {'tid': tid, 'episode title': data.get_value('episode title')}})
        eid = self.get_cache_return()
        if eid == -1:
            return -1

        if eid != None:
            self.functions.update_counter('lookup', -1, parent.chanid)
            self.config.log(self.config.text('ttvdb', 14, (data.get_value('name'), data.get_value('episode title'))), 24)
            return prepare_return(eid, tid, lang)

        # Now we get a list of episodes matching what we already know and compare with confusing characters removed
        self.config.queues['cache'].put({'task':'query', 'parent': self, \
                'ep_by_id': {'tid': tid, 'sid': data.get_value('season'), 'eid': data.get_value('episode')}})
        eps = self.get_cache_return()
        if eps == -1:
            return -1

        subt = re.sub('[-,. ]', '', self.functions.remove_accents(data.get_value('episode title')).lower())
        ep_dict = {}
        ep_list = []
        for ep in eps:
            s = re.sub('[-,. ]', '', self.functions.remove_accents(ep['episode title']).lower())
            ep_list.append(s)
            ep_dict[s] = ep
            if s == subt:
                self.functions.update_counter('lookup', -1, parent.chanid)
                self.config.log(self.config.text('ttvdb', 14, (data.get_value('name'), data.get_value('episode title'))), 24)
                return prepare_return(ep, tid, lang)

        # And finally we try a difflib match
        match_list = difflib.get_close_matches(subt, ep_list, 1, 0.7)
        if len(match_list) > 0:
            self.functions.update_counter('lookup', -1, parent.chanid)
            ep = ep_dict[match_list[0]]
            self.config.log(self.config.text('ttvdb', 14, (data.get_value('name'), data.get_value('episode title'))), 24)
            return prepare_return(ep, tid, lang)

        self.functions.update_counter('lookup_fail', -1, parent.chanid)
        self.config.log(self.config.text('ttvdb', 15, (data.get_value('name'), data.get_value('episode title'), parent.chan_name)), 128)
        return 0

    def check_ttvdb_title(self, series_name, lang=None):
        if self.config.opt_dict['disable_ttvdb']:
            return(-1)

        if lang == None:
            lang = self.config.xml_language

        langs = list(set(self.config.group_language.values()))
        langs.extend(self.config.ttvdb_langs)
        if not 'en' in langs:
            langs.append('en')

        if lang in self.lang_list and not lang in langs:
            langs.append(lang)

        # Check if a record exists
        self.config.queues['cache'].put({'task':'query_id', 'parent': self, 'ttvdb': {'name': series_name}})
        tid = self.get_cache_return()
        if tid == -1:
            return(-1)

        if len(tid) > 0:
            # It 's already in the DB
            elangs = []
            for ep in tid:
                elangs.append(data_value('lang', ep, str))

            elangs = list(set(elangs))
            langlist = u''
            for l in elangs:
                langlist = u'%s, %s' % (langlist, l)
            print(self.config.text('ttvdb', 1, (series_name,  tid[0]['tid'], tid[0]['name']), type = 'frontend').encode(self.local_encoding, 'replace'))
            print(self.config.text('ttvdb', 2, (langlist[2:], ), type = 'frontend').encode(self.local_encoding, 'replace'))
            old_tid = int(tid[0]['tid'])
            for l in elangs:
                langs.append(l)

        else:
            # Invalid language
            print(self.config.text('ttvdb', 3,(series_name, ) , type = 'frontend').encode(self.local_encoding, 'replace'))
            old_tid = -1

        try:
            # Print what was found
            series_list = self.query_ttvdb('seriesid', {'name': series_name, 'lang': lang})
            if not isinstance(series_list, list):
                series_list = [series_list]

            if not is_data_value([0, 'tid'], series_list, int):
                print(self.config.text('ttvdb', 4, (series_name, ), type = 'frontend').encode(self.local_encoding, 'replace'))
                return(0)

            print(self.config.text('ttvdb', 5, type = 'frontend').encode(self.local_encoding, 'replace'))
            for s in range(len(series_list)):
                print("%3.0f -> %9.0f: (%s) %s".encode(self.local_encoding, 'replace') % (s+1, data_value([s, 'tid'], series_list, int), \
                                                                        data_value([s, 'lang'], series_list, str), \
                                                                        data_value([s, 'name'], series_list, str)))

            # Ask to select the right one
            while True:
                try:
                    print(self.config.text('ttvdb', 6, type = 'frontend').encode(self.local_encoding, 'replace'))
                    ans = raw_input()
                    selected_id = int(ans)-1
                    if 0 <= selected_id < len(series_list):
                        break

                except ValueError:
                    if ans.lower() == "q":
                        return(0)

            tid = series_list[selected_id]
            clist = []
            # Get the English name and those for other languages
            langs = list(set(langs))
            for l in langs:
                data = self.query_ttvdb('seriesname', {'ttvdbid': tid['tid'], 'lang': l})
                clist.extend(data)
                if l == 'en':
                    ename = data_value([0, 'name'], data, str)
                    if ename in (None, ''):
                        ename = tid['name']

            if old_tid != int(tid['tid']):
                print(self.config.text('ttvdb', 7, type = 'frontend').encode(self.local_encoding, 'replace'))
                self.config.queues['cache'].put({'task':'delete', 'ttvdb': {'tid': old_tid}})

            self.config.queues['cache'].put({'task':'add', 'ttvdb': clist})
            aliasses = []
            if ename.lower() != tid['name'].lower():
                aliasses.append(tid['name'])

            if ename.lower() != series_name.lower() and tid['name'].lower() != series_name.lower():
                aliasses.append(series_name)

            if len(aliasses) > 0:
                # Add an alias record
                self.config.queues['cache'].put({'task':'add', 'ttvdb_alias': {'tid': int(tid['tid']), 'name': ename, 'alias': aliasses}})
                if len(aliasses) == 2:
                    print(self.config.text('ttvdb', 8, (ename, aliasses[0], aliasses[1],  tid['tid']), type = 'frontend').encode(self.local_encoding, 'replace'))

                else:
                    print(self.config.text('ttvdb', 9, (ename, aliasses[0],  tid['tid']), type = 'frontend').encode(self.local_encoding, 'replace'))

            else:
                print(self.config.text('ttvdb', 10, (ename,  tid['tid']), type = 'frontend').encode(self.local_encoding, 'replace'))

        except:
            traceback.print_exc()
            return(-1)

        if self.get_all_episodes(int(tid['tid']), langs) == -1:
            return(-1)

        return(0)
    def is_data_value(self, searchpath, dtype = None, empty_is_false = True):
        return is_data_value(searchpath, self.source_data, dtype, empty_is_false)

    def data_value(self, searchpath, dtype = None, default = None):
        return data_value(searchpath, self.source_data, dtype, default)

# end theTVDB

class FetchData(Thread):
    """
    Generic Class to fetch the data

    The output is a list of programming in order where each row
    contains a dictionary with program information.
    It runs as a separate thread for every source
    """
    def __init__(self, config, proc_id, source_data, cattrans_type = None):
        Thread.__init__(self)
        self.config = config
        self.functions = self.config.fetch_func
        # Flag to stop the thread
        self.quit = False
        self.ready = False
        self.active = True
        # The ID of the source
        self.proc_id = proc_id
        self.source_lock = RLock()
        # The queue to receive answers on database queries
        self.cache_return = Queue()
        # The queue to receive requests for detail fetches
        self.detail_request = Queue()
        self.config.queues['source'][self.proc_id] = self.detail_request
        self.thread_type = 'source'
        self.config.threads.append(self)

        self.all_channels = {}
        self.channels = {}
        self.chanids = {}
        self.channel_loaded = {}
        self.day_loaded = {}
        self.page_loaded = {}
        self.program_data = {}
        self.chan_count = 0
        self.fetch_ordinal = None
        self.site_tz = self.config.utc_tz
        self.item_count = 0
        self.current_item_count = 0
        self.total_item_count = 0
        self.groupitems = {}

        self.test_output = sys.stdout
        self.print_tags = False
        self.print_roottree = False
        self.print_searchtree = False
        self.show_parsing = False
        self.show_result = False
        self.cattrans = {}
        self.new_cattrans = None
        self.cattrans_type = cattrans_type

        self.datatrees = {}

        try:
            self.source_data = source_data
            self.source = self.data_value('name', str)
            self.name = self.source
            self.is_virtual = self.data_value('is_virtual', bool, default = False)
            self.config.sourceid_by_name[self.source] = self.proc_id
            self.detail_processor = self.data_value('detail_processor', bool, default = False)
            self.detail_check = self.data_value('detail_check', str)
            self.without_full_timings = self.data_value('without-full-timings', bool, default = False)
            self.no_genric_matching = self.data_value('no_genric_matching', list)
            self.empty_channels = self.data_value('empty_channels', list)
            self.alt_channels = self.data_value('alt-channels', dict)
            cattrans = self.data_value('cattrans', dict)
            for k, v in cattrans.items():
                if isinstance(v, dict):
                    self.cattrans[k.lower().strip()] ={}
                    for k2, gg in v.items():
                        self.cattrans[k.lower().strip()][k2.lower().strip()] = gg

                else:
                    self.cattrans[k.lower().strip()] = v

            self.cattrans_keywords = self.data_value('cattrans_keywords', dict)
            self.rating = self.data_value('rating',dict)
            self.site_tz = pytz.timezone(self.data_value('site-timezone', str, default = 'utc'))
            self.night_date_switch = self.data_value('night-date-switch', int, default = 0)
            self.item_count = self.data_value(['base', 'default-item-count'], int, default=0)
            if self.detail_processor:
                if self.proc_id not in self.config.detail_sources:
                    self.detail_processor = False

                if self.is_data_value('detail', dict) or self.is_data_value('detail2', dict):
                    self.config.detail_keys[self.proc_id] = {}
                    self.detail_keys = self.data_value(['detail', 'provides'], list)
                    self.config.detail_keys[self.proc_id]['detail'] = self.detail_keys
                    for k in self.detail_keys:
                        if k not in self.config.detail_keys['all']:
                            self.config.detail_keys['all'].append(k)

                    self.detail2_keys = self.data_value(['detail2', 'provides'], list)
                    self.config.detail_keys[self.proc_id]['detail2'] = self.detail2_keys
                    for k in self.detail2_keys:
                        if k not in self.config.detail_keys['all']:
                            self.config.detail_keys['all'].append(k)

                else:
                    self.detail_processor = False

            elif self.proc_id in self.config.detail_sources:
                self.config.detail_sources.remove(self.proc_id)

        except:
            self.config.validate_option('disable_source', value = self.proc_id)
            #~ traceback.print_exc()

    def run(self):
        """The grabing thread"""
        def check_queue():
            # If the queue is empty
            if self.detail_request.empty():
                time.sleep(random.randint(self.config.opt_dict['nice_time'][0], self.config.opt_dict['nice_time'][1]))
                # and if we are not the last detail source we wait for followup requests from other sources failing
                for q_no in testlist:
                    if (self.proc_id == q_no[0]) and self.config.channelsource[q_no[1]].is_alive():
                        return 0

                # Check if all channels are ready
                for channel in self.config.channels.values():
                    if channel.is_alive() and not channel.ready:
                        break

                # All channels are ready, so if there is nothing in the queue
                else:
                    self.ready = True
                    return -1

                # OK we have been sitting idle for 30 minutes, So we tell all channels they won get anything more!
                if (datetime.datetime.now() - self.lastrequest).total_seconds() > idle_timeout:
                    if self.proc_id == self.config.detail_sources[-1]:
                        for chanid, channel in self.config.channels.items():
                            if channel.is_alive() and not channel.ready:
                                d = 0
                                for s in self.config.detail_sources:
                                    d += self.functions.get_counter('queue', s, chanid)

                                channel.detail_return.put({'source': self.proc_id,'last_one': True})
                                self.config.log([self.config.text('fetch', 21, (channel.chan_name, d, self.source)), self.config.text('fetch', 22)])

                    self.ready = True
                    return -1

                else:
                    return 0

            self.lastrequest = datetime.datetime.now()
            try:
                return self.detail_request.get()

            except Empty:
                return 0

        # First some generic initiation that couldn't be done earlier in __init__
        detail_ids = {}
        idle_timeout = 1800
        try:
            self.init_channel_source_ids()
            # Check if the source is not deactivated and if so set them all loaded
            if self.proc_id in self.config.opt_dict['disable_source']:
                for chanid in self.channels.keys():
                    self.set_loaded('channel', chanid)
                    self.config.channels[chanid].source_ready(self.proc_id).set()

                self.ready = True

            else:
                # Load and proccess al the program pages
                self.load_pages()

            if self.config.write_info_files:
                self.config.infofiles.check_new_channels(self, self.config.source_channels)

        except:
            self.config.queues['log'].put({'fatal': [self.config.text('IO', 14), \
                traceback.format_exc(), '\n'], 'name': self.source})

            self.ready = True
            return(98)

        try:
            if self.detail_processor and  not self.proc_id in self.config.opt_dict['disable_detail_source']:
                detail_idx = self.config.detail_sources.index(self.proc_id)
                testlist = []
                for s1 in range(len(self.config.detail_sources) -1):
                    for s0 in range(len(self.config.detail_sources) -1, s1, -1):
                        testlist.append((self.config.detail_sources[s0], self.config.detail_sources[s1]))

                rev_testlist = testlist[:]
                rev_testlist.reverse()
                # We process detail requests, so we loop till we are finished
                self.lastrequest = datetime.datetime.now()
                while True:
                    if self.quit:
                        self.ready = True
                        break

                    queue_val = check_queue()
                    if queue_val == -1:
                        # We Quit
                        break

                    if queue_val == 0 or not isinstance(queue_val, dict):
                        # We check again
                        continue

                    tdict = queue_val
                    parent = tdict['parent']
                    # Is this the closing item for the channel?
                    if ('last_one' in tdict) and tdict['last_one']:
                        for q_no in rev_testlist:
                            if self.proc_id == q_no[1] and self.config.channelsource[q_no[0]].is_alive():
                                self.config.queues['source'][q_no[0]].put(tdict)
                                break

                        else:
                            parent.detail_return.put({'source': self.proc_id,'last_one': True})

                        continue

                    detail_ids = tdict['detail_ids']
                    logstring = tdict['logstring']
                    # be nice to the source site
                    time.sleep(random.randint(self.config.opt_dict['nice_time'][0], self.config.opt_dict['nice_time'][1]))
                    try:
                        detailed_program = self.load_detailpage('detail', detail_ids[self.proc_id], parent)

                    except:
                        detailed_program = None
                        self.config.log([self.config.text('fetch', 23, (detail_ids[self.proc_id]['detail_url'], )), traceback.format_exc()], 1)

                    # It failed! Check for a detail2 page
                    #~ if detailed_program == None and self.is_data_value('detail2', dict):
                        #~ try:
                            #~ detailed_program = self.load_detailpage('detail2', detail_ids[self.proc_id], parent)

                        #~ except:
                            #~ detailed_program = None
                            #~ self.config.log([self.config.text('fetch', 24, (detail_ids[self.proc_id]['detail_url'], )), traceback.format_exc()], 1)

                    # It failed! We check for alternative detail sources
                    if detailed_program == None:
                        for q_no in rev_testlist:
                            if self.proc_id == q_no[1] and q_no[0] in detail_ids.keys():
                                self.config.queues['source'][q_no[0]].put(queue_val)
                                self.functions.update_counter('queue', q_no[0],  parent.chanid)
                                break

                        else:
                            self.config.log(self.config.text('fetch', 31, (self.source, parent.chan_name, tdict['counter'], logstring), type = 'report'), 8, 1)

                        self.functions.update_counter('queue', self.proc_id,  parent.chanid, False)
                        continue

                    # Success
                    detailed_program[self.config.channelsource[self.proc_id].detail_check] = True
                    self.config.log(self.config.text('fetch', 32, (self.source, parent.chan_name, tdict['counter'], logstring), type = 'report'), 8, 1)
                    detailed_program['sourceid'] = self.proc_id
                    detailed_program['channelid'] = detail_ids[self.proc_id]['channelid']
                    detailed_program['prog_ID'] = detail_ids[self.proc_id]['prog_ID']
                    detailed_program['gen_ID'] = detail_ids[self.proc_id]['gen_ID']
                    parent.detail_return.put({'source': self.proc_id, 'data': detailed_program, 'counter': tdict['counter']})
                    self.functions.update_counter('queue', self.proc_id,  parent.chanid, False)

            else:
                self.ready = True

        except:
            if self.proc_id in detail_ids.keys() and 'detail_url' in detail_ids[self.proc_id].keys():
                self.config.queues['log'].put({'fatal': [self.config.text('IO', 15, (detail_ids[self.proc_id]['detail_url'])), \
                    traceback.format_exc(), '\n'], 'name': self.source})

            else:
                self.config.queues['log'].put({'fatal': [self.config.text('IO', 16), traceback.format_exc(), '\n'], 'name': self.source})

            self.ready = True
            return(98)

    # The fetching functions
    def init_channel_source_ids(self):
        """Get the list of requested channels for this source from the channel configurations"""
        self.current_date = datetime.datetime.now(pytz.utc)
        self.current_sitedate = self.config.in_tz(self.current_date, self.site_tz)
        self.current_fetchdate = self.config.in_fetch_tz(self.current_date)
        self.current_ordinal = self.current_date.toordinal()
        for chanid, channel in self.config.channels.iteritems():
            self.groupitems[chanid] = 0
            self.program_data[chanid] = []
            # Is the channel active and this source for the channel not disabled
            if channel.active and not self.proc_id in channel.opt_dict['disable_source']:
                # Is there a sourceid for this channel
                if channel.get_source_id(self.proc_id) != '':
                    # Unless it is in empty channels we add it else set it ready
                    if channel.get_source_id(self.proc_id) in self.config.channelsource[self.proc_id].empty_channels:
                        self.set_loaded('channel', chanid)
                        self.config.channels[chanid].source_ready(self.proc_id).set()

                    else:
                        self.channels[chanid] = channel.get_source_id(self.proc_id)

                # Does the channel have child channels
                if chanid in self.config.combined_channels.keys():
                    # Then see if any of the childs has a sourceid for this source and does not have this source disabled
                    for c in self.config.combined_channels[chanid]:
                        if c['chanid'] in self.config.channels.keys() and self.config.channels[c['chanid']].get_source_id(self.proc_id) != '' \
                          and not self.proc_id in self.config.channels[c['chanid']].opt_dict['disable_source']:
                            # Unless it is in empty channels we add and mark it as a child else set it ready
                            if self.config.channels[c['chanid']].get_source_id(self.proc_id) in self.config.channelsource[self.proc_id].empty_channels:
                                self.set_loaded('channel', chanid)
                                self.config.channels[c['chanid']].source_ready(self.proc_id).set()

                            else:
                                self.channels[c['chanid']] = self.config.channels[c['chanid']].get_source_id(self.proc_id)
                                self.config.channels[c['chanid']].is_child = True

        for chanid, channelid in self.channels.items():
            self.chanids[channelid] = chanid

        # To limit the output to the requested channels
        if self.is_data_value(["base", "value-filters", "channelid"], list, False):
            self.source_data["base"]["value-filters"]["channelid"].extend(list(self.chanids.keys()))
            self.source_data["base"]["value-filters"]["channelid"].extend(list(self.alt_channels.keys()))

    def get_page_data(self, ptype, pdata = None):
        """
        Here for every fetch, the url is gathered, the page retreived and
        together with the data definition inserted in the DataTree module
        The then by the DataTree extracted data is return
        """
        try:
            if pdata == None:
                pdata = {}

            if not ptype in self.datatrees.keys() or not isinstance(self.datatrees[ptype], DataTreeShell):
                if not self.is_data_value([ptype, 'timezone'], str):
                    self.source_data[ptype]['timezone'] = self.data_value('site-timezone', str, default = 'utc')
                    self.source_data[ptype]['empty-values'] = self.data_value('empty-values', list, default = [None, "", "-"])

                self.datatrees[ptype] = DataTree(self, self.data_value(ptype, dict), 'always', self.proc_id)

            # For the url we use the fetch timezone and not the site timezone
            self.datatrees[ptype].set_timezone(self.config.fetch_tz)
            self.datatrees[ptype].set_current_date(self.current_ordinal + data_value('offset', pdata, int, default=0))
            # Set the counter for the statistics
            if ptype in ('channels', 'base-channels'):
                pdata['start'] = 0
                pdata['end'] = 0
                pdata[ 'offset'] = 0
                counter = ['base', self.proc_id, None]

            elif ptype in ('detail', 'detail2'):
                counter = ['detail', self.proc_id, pdata['channel']]

            else:
                counter = ['base', self.proc_id, None]

            url_type = self.datatrees[ptype].data_value(["url-type"], int, default = 2)
            url = self.datatrees[ptype].get_url(pdata)
            if url == None:
                self.config.log([self.config.text('fetch', 25, (ptype, self.source))], 1)
                return

            if self.print_searchtree:
                print '(url, encoding, accept_header, url_data, is_json)'
                print url

            self.functions.update_counter(counter[0], counter[1], counter[2])
            page = self.functions.get_page(url)
            if page in (None, '', '{}'):
                self.config.log([self.config.text('fetch', 26, (ptype, url[0]))], 1)
                self.functions.update_counter('fail', counter[1], counter[2])
                if self.print_searchtree:
                    print 'No Data'
                return None

            self.datatrees[ptype].init_data(page)
            if self.datatrees[ptype].searchtree == None:
                self.config.log([self.config.text('fetch', 26, (ptype, url[0]))], 1)
                self.functions.update_counter('fail', counter[1], counter[2])
                if self.print_searchtree:
                    print 'No Data'

                return None

            # We reset the timezone
            self.datatrees[ptype].set_timezone()
            if ptype == 'base':
                # We set the current date
                if (url_type & 12) == 0:
                    cdate = self.current_sitedate.toordinal() + pdata['offset']
                    self.datatrees[ptype].set_current_date(cdate)
                    self.datatrees[ptype].searchtree.set_current_date(cdate)

                # We extract the current _item_count and the total_item_count
                if (url_type & 12) == 12:
                    self.total_item_count = self.datatrees[ptype].searchtree.find_data_value(self.datatrees[ptype].data_value(['data',"total-item-count"],list))
                    self.current_item_count = self.datatrees[ptype].searchtree.find_data_value(self.datatrees[ptype].data_value(['data',"page-item-count"],list))

                # We check on the right offset
                if self.datatrees[ptype].is_data_value(['data',"today"],list):
                    cd = self.datatrees[ptype].searchtree.find_data_value(self.datatrees[ptype].data_value(['data',"today"],list))
                    if not isinstance(cd, datetime.date):
                        self.config.log([self.config.text('fetch', 27, (url[0], )),])
                        #~ return None

                    elif self.night_date_switch > 0 and self.current_fetchdate.hour < self.night_date_switch and (self.current_ordinal - cd.toordinal()) == 1:
                        # This page switches date at a later time so we allow
                        pass

                    elif cd.toordinal() != self.current_ordinal:
                        if url_type == 1:
                            self.config.log(self.config.text('fetch', 28, (pdata['channel'], self.source, pdata['offset'])))
                        elif (url_type & 3) == 1:
                            # chanid
                            pass
                        elif (url_type & 12) in (0, 8):
                            # offset
                            pass
                        self.functions.update_counter('fail', counter[1], counter[2])
                        return None

            self.datatrees[ptype].extract_datalist()
            data = self.datatrees[ptype].result
            if self.show_result:
                for p in self.datatrees[ptype].searchtree.result:
                    if isinstance(p[0], (str, unicode)):
                        print p[0].encode('utf-8', 'replace')
                    else:
                        print p[0]
                    for v in range(1,len(p)):
                        if isinstance(p[v], (str, unicode)):
                            print '    ', p[v].encode('utf-8', 'replace')
                        else:
                            print '    ', p[v]

            # we extract a channel list if available
            if ptype == 'base' and self.is_data_value("base-channels", dict) and len(self.all_channels) == 0:
                self.datatrees[ptype].init_data_def(self.data_value("base-channels", dict))
                self.datatrees[ptype].extract_datalist()
                self.get_channels(self.datatrees[ptype].result)
                self.datatrees[ptype].init_data_def(self.data_value("base", dict))

            if len(data) == 0:
                self.functions.update_counter('fail', counter[1], counter[2])
                return None

            return data

        except:
            self.config.log([self.config.text('fetch', 29, (ptype, self.source)), traceback.format_exc()], 1)
            # Reset the counter!
            return None

    def get_channels(self, data_list = None):
        """The code for the retreiving a list of supported channels"""
        self.all_channels ={}
        if data_list == None:
            ptype = "channels"
            if not self.is_data_value([ptype], dict):
                ptype = "base-channels"
                if not self.is_data_value([ptype], dict):
                    return

            if not self.is_data_value([ptype, "data"]):
                return

            if not self.is_data_value([ptype, "url"]):
                # The channels are defined in the datafile
                self.all_channels = self.data_value([ptype, "data"], dict)
                return

            #extract the data
            channel_list = self.get_page_data(ptype)

        else:
            # The list is extracted from a base page
            ptype = "base-channels"
            channel_list = data_list

        if isinstance(channel_list, list):
            for channel in channel_list:
                # link the data to the right variable, doing any defined adjustments
                if "inactive_channel" in channel.keys() and channel["inactive_channel"]:
                    continue

                if "channelid" in channel.keys():
                    channelid = unicode(channel["channelid"])
                    if channelid in self.alt_channels.keys():
                        channel['channelid'] = self.alt_channels[channelid][0]
                        channel['name'] = self.alt_channels[channelid][1]
                        channelid = unicode(channel['channelid'])
                    #~ if channelid in self.empty_channels:
                        #~ continue

                    self.all_channels[channelid] = channel

        else:
            self.config.log(self.config.text('fetch', 30, (self.source, )))
            return 69

    def load_pages(self):
        """The code for the actual Grabbing and dataprocessing of the base pages"""
        def log_fetch():
            log_array = []
            if (url_type & 3) == 1:
                log_array =['\n', self.config.text('fetch', 1, \
                    (self.config.channels[chanid].chan_name, self.config.channels[chanid].xmltvid , \
                    (self.config.channels[chanid].opt_dict['compat'] and self.config.compat_text or ''), self.source), type = 'report')]

                if (url_type & 12) == 0:
                    log_array.append(self.config.text('fetch', 4, (channel_cnt, len(self.channels), offset, self.config.opt_dict['days']), type = 'report'))

                elif (url_type & 12) == 4:
                    log_array.append(self.config.text('fetch', 5, (channel_cnt, len(self.channels), '6'), type = 'report'))

                elif (url_type & 12) == 8:
                    log_array.append(self.config.text('fetch', 6, (channel_cnt, len(self.channels), page_idx, len(fetch_range)), type = 'report'))

                elif (url_type & 12) == 12:
                    log_array.append(self.config.text('fetch', 7, (channel_cnt, len(self.channels), self.config.opt_dict['days'], base_count), type = 'report'))

            else:
                if (url_type & 3) == 2:
                    log_array =['\n', self.config.text('fetch', 2, (len(self.channels), self.source), type = 'report')]

                elif (url_type & 3) == 3:
                    log_array =['\n', self.config.text('fetch', 3, (channelgrp, self.source), type = 'report')]

                else:
                    return

                if (url_type & 12) == 0:
                    log_array.append(self.config.text('fetch', 8, (offset, self.config.opt_dict['days']), type = 'report'))

                elif (url_type & 12) == 4:
                    log_array.append(self.config.text('fetch', 9, (self.config.opt_dict['days']), type = 'report'))

                elif (url_type & 12) == 8:
                    log_array.append(self.config.text('fetch', 10, (page_idx, len(fetch_range)), type = 'report'))

                elif (url_type & 12) == 12:
                    log_array.append(self.config.text('fetch', 11, (self.config.opt_dict['days'], base_count), type = 'report'))

            self.config.log(log_array, 2)
        # end log_fetch()

        def log_fail():
            if url_type == 1:
                self.config.log(self.config.text('fetch', 15, (self.config.channels[chanid].chan_name, self.source, offset), type = 'report'))

            elif url_type == 2:
                self.config.log(self.config.text('fetch', 19, (offset, self.source), type = 'report'))

            elif url_type == 3:
                self.config.log(self.config.text('fetch',23 , (channelgrp, self.source, offset), type = 'report'))

            elif url_type == 5:
                self.config.log(self.config.text('fetch', 16, (self.config.channels[chanid].chan_name, self.source), type = 'report'))

            elif url_type == 6:
                self.config.log(self.config.text('fetch', 20, (self.source, ), type = 'report'))

            elif url_type == 7:
                self.config.log(self.config.text('fetch',24 , (channelgrp, self.source), type = 'report'))

            elif url_type == 9:
                self.config.log(self.config.text('fetch', 17, (self.config.channels[chanid].chan_name, self.source, page_idx), type = 'report'))

            elif url_type == 10:
                self.config.log(self.config.text('fetch', 21, (page_idx, self.source), type = 'report'))

            elif url_type == 11:
                self.config.log(self.config.text('fetch',25 , (channelgrp, self.source, page_idx), type = 'report'))

            elif url_type == 13:
                self.config.log(self.config.text('fetch', 18, (self.config.channels[chanid].chan_name, self.source, base_count), type = 'report'))

            elif url_type == 14:
                self.config.log(self.config.text('fetch', 22, (base_count, self.source), type = 'report'))

            elif url_type == 15:
                self.config.log(self.config.text('fetch',26 , (channelgrp, self.source, base_count), type = 'report'))
        # end log_fail()

        def get_weekstart(ordinal = None, offset = 0, sow = None):
            if sow == None:
                return offset

            if ordinal == None:
                ordinal = self.current_ordinal

            weekday = int(datetime.date.fromordinal(ordinal + offset).strftime('%w'))
            first_day = offset + sow - weekday
            if weekday < sow:
                first_day -= 7

            return first_day
        # end get_weekstart()

        def do_final_processing(chanid):
            channelid = self.channels[chanid]
            good_programs = []
            pgaps = []
            # Some sanity Check
            if len(self.program_data[chanid]) > 0:
                self.program_data[chanid].sort(key=lambda program: (program['start-time']))
                plen = len(self.program_data[chanid])
                last_stop = None
                min_gap = datetime.timedelta(minutes = 30)
                for index in range(plen):
                    p = self.program_data[chanid][index]
                    if not 'name' in p.keys() or not isinstance(p['name'], (unicode, str)) or p['name'] == u'':
                        continue

                    p['name'] = unicode(p['name'])
                    if index < plen - 1:
                        p2 = self.program_data[chanid][index + 1]
                        if 'stop from length' in p.keys() and p['stop from length'] and not 'last of the page' in p.keys():
                            if p['stop-time'] > p2['start-time']:
                                p['stop-time'] = copy(p2['start-time'])

                        if not 'stop-time' in p.keys() or not isinstance(p['stop-time'], datetime.datetime):
                            if 'last of the page' in p.keys():
                                continue

                            p['stop-time'] = copy(p2['start-time'])

                        if not 'length' in p.keys() or not isinstance(p['length'], datetime.timedelta):
                            p['length'] = p['stop-time'] - p['start-time']

                        if 'last of the page' in p.keys():
                            # Check for a program split by the day border
                            if p[ 'name'].lower() == p2[ 'name'].lower() and p['stop-time'] >= p2['start-time'] \
                              and ((not 'episode title' in p and not 'episode title' in p2) \
                                or ('episode title' in p and 'episode title' in p2 \
                                and p[ 'episode title'].lower() == p2[ 'episode title'].lower())):
                                    p2['start-time'] = copy(p['start-time'])
                                    continue

                    elif index == plen - 1 and'stop-time' in p.keys() and isinstance(p['stop-time'], datetime.datetime):
                        if not 'length' in p.keys() or not isinstance(p['length'], datetime.timedelta):
                            p['length'] = p['stop-time'] - p['start-time']

                        while p['length'] > tdd:
                            p['length'] -= tdd

                        p['stop-time'] = p['start-time'] + p['length']

                    else:
                        continue

                    if p['stop-time'] <= p['start-time']:
                        continue

                    if last_stop != None and (p['start-time'] - last_stop) > min_gap:
                        pgaps.append((last_stop, copy(p['start-time']), last_name, p['name'].lower()))

                    last_stop = copy(p['stop-time'])
                    last_name = p['name'].lower()
                    good_programs.append(p)

            # Retrieve what is in the cache with a day earlier and later added
            cache_range = range( first_day - 1 , min(max_days, last_day) +1)
            self.config.queues['cache'].put({'task':'query', 'parent': self, 'sourceprograms': {'sourceid': self.proc_id, 'channelid': channelid, 'scandate': cache_range}})
            cache_programs = self.cache_return.get(True)
            if cache_programs =='quit':
                self.ready = True
                return

            # And add in the cached programs
            if len(good_programs) > 0:
                good_programs.sort(key=lambda program: (program['start-time']))
                fetch_start = good_programs[0]['start-time']
                fetch_end = good_programs[-1]['stop-time']
                cache_delete = []
                cache_add = []
                if len(cache_programs) > 0:
                    # Retrieve those days from the cache
                    for day in site_range:
                        if cached[chanid][day] and not self.get_loaded('day', chanid, day):
                            self.config.log(self.config.text('fetch', 12,  (day, self.config.channels[chanid].chan_name, self.source), type = 'report'), 2)

                    for p in cache_programs:
                        p['source'] = self.source
                        p['chanid'] = chanid
                        p['channel']  = self.config.channels[chanid].chan_name
                        p['length'] = p['stop-time'] - p['start-time']
                        p['from cache'] = True
                        gn = '' if not 'group name' in p or p['group name'] == None else p['group name']
                        et = '' if not 'episode title' in p or p['episode title'] == None else p['episode title']
                        p['title'] = (gn, p['name'], et)
                        g = '' if not 'genre' in p or p['genre'] == None else p['genre']
                        sg = '' if not 'subgenre' in p or p['subgenre'] == None else p['subgenre']
                        p['genres'] = (g, sg)
                        if 'group' in p.keys() and not p['group'] in (None, ''):
                            self.groupitems[chanid] += 1

                        if p['stop-time'] <= fetch_start or p['start-time'] >= fetch_end:
                            cache_add.append(p)
                            continue

                        elif p['start-time'] <= fetch_start and (fetch_start - p['start-time']) > (p['stop-time'] - fetch_start) and p['name'].lower() != good_programs[0]['name'].lower():
                            cache_add.append(p)
                            continue

                        elif p['stop-time'] >= fetch_end and (fetch_end - p['start-time']) < (p['stop-time'] - fetch_end) and p['name'].lower() != good_programs[-1]['name'].lower():
                            cache_add.append(p)
                            continue

                        for pg in pgaps:
                            if pg[0] <= p['start-time'] <= pg[1] and pg[0] <= p['stop-time'] <= pg[1]:
                                cache_add.append(p)
                                break

                            elif pg[0] <= p['start-time'] <= pg[1] and (pg[1] - p['start-time']) > (p['stop-time'] - pg[1]) and p['name'].lower() != pg[3]:
                                cache_add.append(p)
                                break

                            elif pg[0] <= p['stop-time'] <= pg[1] and (p['stop-time'] - pg[0]) > (pg[0] - p['start-time']) and p['name'].lower() != pg[2]:
                                cache_add.append(p)
                                break

                        else:
                            cache_delete.append(p['start-time'])

                    # Delete the new fetched programs from the cache
                    if len(cache_delete) > 0:
                        self.config.queues['cache'].put({'task':'delete', 'parent': self, 'sourceprograms': {'sourceid': self.proc_id, 'channelid': channelid, 'start-time': cache_delete}})

                # Update the cache
                new_ranges= []
                for day in site_range:
                    if self.get_loaded('day', chanid, day):
                        new_ranges.append(day)

                self.config.queues['cache'].put({'task':'add', 'parent': self, \
                        'sourceprograms': deepcopy(good_programs), \
                        'laststop': {'sourceid': self.proc_id, 'channelid': channelid, 'laststop': fetch_end}, \
                        'fetcheddays': {'sourceid': self.proc_id, 'channelid': channelid, 'scandate': new_ranges}})
                good_programs.extend(cache_add)

            elif len(cache_programs) > 0:
                for p in cache_programs:
                    p['source'] = self.source
                    p['chanid'] = chanid
                    p['channel']  = self.config.channels[chanid].chan_name
                    p['length'] = p['stop-time'] - p['start-time']
                    p['from cache'] = True
                    if 'group' in p.keys() and not p['group'] in (None, ''):
                        self.groupitems[chanid] += 1

                    good_programs.append(p)

            # Add any repeat group
            if len(good_programs) > 0:
                good_programs.sort(key=lambda program: (program['start-time']))
                if self.groupitems[chanid] > 0:
                    group_start = False
                    for p in good_programs[:]:
                        if 'group' in p.keys():
                            # Collecting the group
                            if not group_start:
                                group = []
                                start = p['start-time']
                                group_start = True

                            if 'proc_ID' in p:
                                p['gen_ID'] = p['proc_ID']
                            group.append(p.copy())
                            group_duur = p['stop-time'] - start

                        elif group_start:
                            # Repeating the group
                            group_start = False
                            group_eind = p['start-time']
                            group_length = group_eind - start
                            if group_length > datetime.timedelta(hours = 12):
                                # Probably a week was not grabbed
                                group_eind -= datetime.timedelta(days = int(group_length.days))

                            repeat = 0
                            while True:
                                repeat+= 1
                                for g in group[:]:
                                    gdict = g.copy()
                                    gdict['prog_ID'] = ''
                                    gdict['rerun'] = True
                                    gdict['start-time'] += repeat*group_duur
                                    gdict['stop-time'] += repeat*group_duur
                                    if gdict['start-time'] < group_eind:
                                        if gdict['stop-time'] > group_eind:
                                            gdict['stop-time'] = group_eind

                                        good_programs.append(gdict)

                                    else:
                                        break

                                else:
                                    continue

                                break

            # And keep only the requested range
            self.program_data[chanid] = []
            for p in good_programs[:]:
                if p['offset'] in full_range:
                    self.program_data[chanid].append(p)

            self.config.channels[chanid].source_ready(self.proc_id).set()
            self.set_loaded('channel', chanid)
            self.set_loaded('day', chanid)
        # end do_final_processing()

        if len(self.channels) == 0  or not self.is_data_value(["base", "url"]):
            return

        tdd = datetime.timedelta(days=1)
        cached = {}
        laststop = {}
        first_day = self.config.opt_dict['offset']
        last_day = first_day + self.config.opt_dict['days']
        max_days = self.data_value(["base", "max days"], int, default = 14)
        if first_day > max_days:
            self.set_loaded('channel')
            for chanid in self.channels.keys():
                self.config.channels[chanid].source_ready(self.proc_id).set()

            return

        full_range = range( first_day, last_day)
        site_range = range( first_day, min(max_days, last_day))
        step_start = first_day
        offset_step = 1
        fetch_range = site_range
        for chanid, channelid in self.channels.items():
            self.program_data[chanid] = []
            self.config.queues['cache'].put({'task':'query', 'parent': self, 'fetcheddays': {'sourceid': self.proc_id, 'channelid': channelid, 'scandate': list(full_range)}})
            cached[chanid] = self.cache_return.get(True)
            self.config.queues['cache'].put({'task':'query', 'parent': self, 'laststop': {'sourceid': self.proc_id, 'channelid': channelid}})
            ls = self.cache_return.get(True)
            laststop[chanid] = ls['laststop']  if isinstance(ls, dict) and isinstance(ls['laststop'], datetime.datetime) else None

        url_type = self.data_value(["base", "url-type"], int, default = 2)
        # Check which groups contain requested channels
        if (url_type & 3) == 3:
            if not self.is_data_value(["base", "url-channel-groups"], list):
                return

            changroups = self.data_value(["base", "url-channel-groups"], list)
            fgroup = {}
            for channelgrp in changroups:
                self.config.queues['cache'].put({'task':'query', 'parent': self, 'chan_scid': {'sourceid': self.proc_id, 'fgroup': channelgrp}})
                fgroup[channelgrp] = self.cache_return.get(True)
                for chan in fgroup[channelgrp][:]:
                    if not chan['chanid'] in self.channels.keys():
                        fgroup[channelgrp].remove(chan)

        # Check which days and up to what date are available in the cache
        for chanid, channelid in self.channels.items():
            self.program_data[chanid] = []
            self.config.queues['cache'].put({'task':'query', 'parent': self, 'fetcheddays': {'sourceid': self.proc_id, 'channelid': channelid, 'scandate': list(full_range)}})
            cached[chanid] = self.cache_return.get(True)
            self.config.queues['cache'].put({'task':'query', 'parent': self, 'laststop': {'sourceid': self.proc_id, 'channelid': channelid}})
            ls = self.cache_return.get(True)
            laststop[chanid] = ls['laststop']  if isinstance(ls, dict) and isinstance(ls['laststop'], datetime.datetime) else None

        # Determine which days to fetch
        if self.config.args.only_cache:
            for chanid in self.channels.keys():
                do_final_processing(chanid)

            return

        # We fetch every day separate
        elif (url_type & 12) == 0:
            # vrt.be, tvgids.tv
            if (url_type & 3) == 1:
                fetch_range = {}
                for chanid in self.channels.keys():
                    fetch_range[chanid] = []
                    for day in site_range:
                        if day == 0 or cached[chanid][day] != True:
                            fetch_range[chanid].append(day)

            # tvgids.nl, npo.nl, vpro.nl, primo.eu, oorboekje.nl
            elif (url_type & 3) == 2:
                fetch_range = []
                for day in site_range:
                    for chanid in self.channels.keys():
                        if day == 0 or cached[chanid][day] != True:
                            fetch_range.append(day)
                            break

            #humo.be
            elif (url_type & 3) == 3:
                fetch_range = {}
                for channelgrp in changroups:
                    fetch_range[channelgrp] = []
                    for day in site_range:
                        for chan in fgroup[channelgrp]:
                            if day == 0 or cached[chan['chanid']][day] != True:
                                fetch_range[channelgrp].append(day)
                                break

        # We fetch all days in one
        elif (url_type & 12) == 4:
            if (url_type & 3) == 1:
                fetch_range = {}
                for chanid in self.channels.keys():
                    fetch_range[chanid] = ['all']

            # rtl.nl
            elif (url_type & 3) == 2:
                fetch_range = ['all']

            elif (url_type & 3) == 3:
                # ToDo
                return

        # We fetch a set number of  days in one
        elif (url_type & 12) == 8:
            if not self.is_data_value(["base", "url-date-range"]):
                return

            if self.data_value(["base", "url-date-range"]) == 'week':
                sow = self.data_value(["base", "url-date-week-start"], int, default = 1)
                offset_step = 7
                step_start = get_weekstart(self.current_ordinal, first_day, sow)
                if (url_type & 3) == 1:
                    fetch_range = {}
                    for chanid in self.channels.keys():
                        fetch_range[chanid] = []
                        for daygroup in range(step_start, last_day, offset_step):
                            for day in site_range:
                                if day in site_range and (day == 0 or cached[chanid][day] != True):
                                    fetch_range[chanid].append(daygroup)
                                    break

                elif (url_type & 3) == 2:
                    fetch_range = []
                    for daygroup in range(step_start, last_day, offset_step):
                        for day in site_range:
                            for chanid in self.channels.keys():
                                if day in site_range and (day == 0 or cached[chanid][day] != True):
                                    fetch_range.append(daygroup)
                                    break

                            else:
                                continue

                            break

                elif (url_type & 3) == 3:
                    # ToDo
                    return

            elif self.is_data_value(["base", "url-date-range"], int):
                offset_step = self.data_value(["base", "url-date-range"])
                # nieuwsblad.be
                if (url_type & 3) == 1:
                    fetch_range = {}
                    for chanid in self.channels.keys():
                        fetch_range[chanid] = []
                        start = None
                        for day in site_range:
                            if day == 0 or cached[chanid][day] != True:
                                if start == None or day > start + offset_step:
                                    fetch_range[chanid].append(day)
                                    start = day

                elif (url_type & 3) == 2:
                    fetch_range = []
                    start = None
                    for day in site_range:
                        for chanid in self.channels.keys():
                            if day == 0 or cached[chanid][day] != True:
                                if start == None or day > start + offset_step:
                                    fetch_range.append(day)
                                    start = day
                                    break

                elif (url_type & 3) == 3:
                    # ToDo
                    return

            else:
                return

        # We fetch a set number of  records per page
        elif (url_type & 12) == 12:
            # horizon.nl
            if (url_type & 3) == 1:
                fetch_range = {}
                for chanid in self.channels.keys():
                    fetch_range[chanid] = []
                    start = None
                    days = 0
                    for day in site_range:
                        if day == 0 or cached[chanid][day] != True:
                            days += 1
                            if start == None:
                                start = day

                        elif start != None:
                            fetch_range[chanid].append((start, days))
                            start = None
                            days = 0

                    if start != None:
                        fetch_range[chanid].append((start, days))

            elif (url_type & 3) == 2:
                fetch_range = []
                start = None
                days = 0
                for day in site_range:
                    for chanid in self.channels.keys():
                        if day == 0 or cached[chanid][day] != True:
                            days += 1
                            if start == None:
                                start = day

                            break

                    else:
                        continue

                    if start != None:
                        fetch_range.append((start, days))
                        start = None
                        days = 0

                if start != None:
                    fetch_range.append((start, days))


            elif (url_type & 3) == 3:
                # ToDo
                return

        try:
            first_fetch = True
            # We fetch every channel separate
            if (url_type & 3) == 1:
                for retry in (0, 1):
                    channel_cnt = 0
                    for chanid in self.channels.keys():
                        channel_cnt += 1
                        failure_count = 0
                        if self.quit:
                            return

                        if self.config.channels[chanid].source_ready(self.proc_id).is_set():
                            continue

                        channel = self.channels[chanid]
                        if (url_type & 12) == 12:
                            if self.item_count == 0:
                                return

                            base_count = 0
                            for fset in fetch_range[chanid]:
                                self.current_item_count = self.item_count
                                page_count = 0
                                while self.current_item_count == self.item_count:
                                    if self.quit:
                                        return

                                    # Check if it is already loaded
                                    if self.get_loaded('page', chanid, base_count):
                                        page_count += 1
                                        base_count += 1
                                        continue

                                    log_fetch()
                                    if not first_fetch:
                                        # be nice to the source
                                        time.sleep(random.randint(self.config.opt_dict['nice_time'][0], self.config.opt_dict['nice_time'][1]))

                                    first_fetch = False
                                    strdata = self.get_page_data('base',{'channel': channel,
                                                                                            'cnt-offset': page_count,
                                                                                            'start': fset[0],
                                                                                            'end': fset[0] + fset[1],
                                                                                            'back':-fset[0],
                                                                                            'ahead': fset[0] +fset[1]-1})

                                    if strdata == None:
                                        if retry == 1:
                                            log_fail()

                                        failure_count += 1
                                        base_count += 1
                                        page_count += 1
                                        if failure_count > 10:
                                            break

                                        continue

                                    self.parse_basepage(strdata, {'url_type':url_type, 'channelid': channel})
                                    self.set_loaded('page', chanid, base_count)
                                    page_count += 1
                                    base_count += 1

                                self.set_loaded('day', chanid, range(fset[0], fset[0] + fset[1]))

                        else:
                            page_idx = 0
                            for offset in fetch_range[chanid]:
                                page_idx += 1
                                # Check if it is already loaded
                                if (url_type & 12) == 8:
                                    if self.get_loaded('page', chanid, offset):
                                        continue

                                else:
                                    if self.get_loaded('day', chanid, offset):
                                        continue

                                if not first_fetch:
                                    # be nice to the source
                                    time.sleep(random.randint(self.config.opt_dict['nice_time'][0], self.config.opt_dict['nice_time'][1]))

                                first_fetch = False
                                log_fetch()
                                strdata = self.get_page_data('base',{'channel': channel,
                                                                                        'offset': offset,
                                                                                        'start': first_day,
                                                                                        'end': min(max_days, last_day),
                                                                                        'back':-first_day,
                                                                                        'ahead':min(max_days, last_day)-1})
                                if strdata == None:
                                    if retry == 1:
                                        log_fail()

                                    failure_count += 1
                                    continue

                                self.parse_basepage(strdata, {'url_type':url_type, 'offset': offset, 'channelid': channel})
                                if (url_type & 12) == 0:
                                    self.set_loaded('day', chanid, offset)

                                elif (url_type & 12) == 4:
                                    self.set_loaded('day', chanid)

                                elif (url_type & 12) == 8:
                                    self.set_loaded('day', chanid, range(offset, offset + offset_step))
                                    self.set_loaded('page', chanid, offset)


                        if failure_count == 0 or retry == 1:
                            do_final_processing(chanid)

            # We fetch all channels in one
            if (url_type & 3) == 2:
                for retry in (0, 1):
                    failure_count = 0
                    if self.quit:
                        return

                    if (url_type & 12) == 8:
                        # We fetch a set number of  days in one
                        return

                    elif (url_type & 12) == 12:
                        # We fetch a set number of  records in one
                        return

                    else:
                        for offset in fetch_range:
                            if self.quit:
                                return

                            # Check if it is already loaded
                            if self.get_loaded('day', 0, offset):
                                continue

                            if not first_fetch:
                                # be nice to the source
                                time.sleep(random.randint(self.config.opt_dict['nice_time'][0], self.config.opt_dict['nice_time'][1]))

                            first_fetch = False
                            log_fetch()
                            strdata = self.get_page_data('base',{'channels': self.channels,
                                                                                    'offset': offset,
                                                                                    'start': first_day,
                                                                                    'end': min(max_days, last_day),
                                                                                    'back':-first_day,
                                                                                    'ahead':min(max_days, last_day)-1})
                            if strdata == None:
                                if retry == 1:
                                    log_fail()

                                failure_count += 1
                                continue

                            self.set_loaded('day', 0, offset)
                            self.parse_basepage(strdata, {'url_type':url_type, 'offset':offset})

                    if failure_count == 0 or retry == 1:
                        for chanid in self.channels.keys():
                            do_final_processing(chanid)

                        break

            # We fetch the channels in two or more groups
            if (url_type & 3) == 3:
                for retry in (0, 1):
                    for channelgrp in self.data_value(["base", "url-channel-groups"], list):
                        failure_count = 0
                        if self.quit:
                            return

                        if len(fgroup[channelgrp]) == 0:
                            continue

                        # We fetch every day separate
                        #humo.be
                        if (url_type & 12) == 0:
                            for offset in fetch_range[channelgrp]:
                                if self.quit:
                                    return

                                for chan in fgroup[channelgrp]:
                                    if not self.get_loaded('day', chan['chanid'], offset):
                                        break

                                else:
                                    continue

                                if not first_fetch:
                                    # be nice to the source
                                    time.sleep(random.randint(self.config.opt_dict['nice_time'][0], self.config.opt_dict['nice_time'][1]))

                                first_fetch = False
                                log_fetch()
                                strdata = self.get_page_data('base',{'channelgrp': channelgrp,
                                                                                        'offset': offset,
                                                                                        'start': first_day,
                                                                                        'end': min(max_days, last_day),
                                                                                        'back':-first_day,
                                                                                        'ahead':min(max_days, last_day)-1})
                                if strdata == None:
                                    if retry == 1:
                                        log_fail()

                                    failure_count += 1
                                    continue

                                chanids = self.parse_basepage(strdata, {'url_type':url_type, 'channelgrp': channelgrp, 'offset':offset})
                                if isinstance(chanids, list):
                                    self.set_loaded('day', chanids, offset)

                        elif (url_type & 12) == 4:
                            # We fetch all days in one
                            return

                        elif (url_type & 12) == 8:
                            # We fetch a set number of  days in one
                            return

                        elif (url_type & 12) == 12:
                            # We fetch a set number of  records in one
                            return


                    if failure_count == 0 or retry == 1:
                        for chanid in self.channels.keys():
                            do_final_processing(chanid)

                        break

        except:
            self.config.log([self.config.text('fetch', 31, (self.source,)), self.config.text('fetch', 32), traceback.format_exc()], 0)
            self.set_loaded('channel')
            for chanid in self.channels.keys():
                self.config.channels[chanid].source_ready(self.proc_id).set()

            return None

    def parse_basepage(self, fdata, subset = {}):
        """Process the data retreived from DataTree for the base pages"""
        chanids = []
        last_start = {}
        tdd = datetime.timedelta(days=1)
        tdh = datetime.timedelta(hours=1)
        if isinstance(fdata, list):
            last_stop = None
            for program in fdata:
                if 'channelid' in program.keys():
                    channelid = unicode(program['channelid'])
                    if channelid in self.alt_channels.keys():
                        program['channelid'] = self.alt_channels[channelid][0]
                        channelid = unicode(program['channelid'])

                elif 'channelid' in subset.keys():
                    channelid = subset['channelid']

                else:
                    continue

                # it's not requested
                if not channelid in self.chanids.keys():
                    continue

                # A list of processed channels to send back
                if not self.chanids[channelid] in chanids:
                    chanids.append(self.chanids[channelid])

                if not channelid in last_start.keys():
                    last_start[channelid] = None

                chanid = self.chanids[channelid]
                if not 'prog_ID' in program.keys():
                    program['prog_ID'] = ''

                tdict = {}
                tdict['sourceid'] = self.proc_id
                tdict['source'] = self.source
                tdict['channelid'] = channelid
                tdict['chanid'] = chanid
                tdict['prog_ID'] = ''
                tdict['channel']  = self.config.channels[chanid].chan_name
                tdict['from cache'] = False
                if  not 'name' in program.keys() or program['name'] == None or program['name'] == '':
                    # Give it the Unknown Program Title Name, to mark it as a groupslot.
                    program['name'] = self.config.unknown_program_title
                    tdict['is_gap'] = True
                    #~ self.config.log(self.config.text('fetch', 33, (program['prog_ID'], self.config.channels[chanid].chan_name, self.source)))
                    #~ continue

                if 'stop-time' in program.keys() and isinstance(program['stop-time'], datetime.datetime):
                    tdict['stop-time'] = program['stop-time']
                elif "alt-stop-time" in program and isinstance(program["alt-stop-time"], datetime.datetime):
                    tdict['stop-time'] = program["alt-stop-time"]

                if 'start-time' in program.keys() and isinstance(program['start-time'], datetime.datetime):
                    tdict['start-time'] = program['start-time']
                elif "alt-start-time" in program and isinstance(program["alt-start-time"], datetime.datetime):
                    tdict['start-time'] = program["alt-start-time"]
                elif "length" in program and isinstance(program['length'], datetime.timedelta) and 'stop-time' in tdict.keys():
                    tdict['start-time'] = tdict['stop-time'] - program['length']
                    tdict['start from length'] = True
                elif self.data_value(["base", "data-format"], str) == "text/html" and isinstance(last_stop, datetime.datetime):
                    tdict['start-time'] = last_stop
                else:
                    # Unable to determin a Start Time
                    self.config.log(self.config.text('fetch', 34, (program['name'], tdict['channel'], self.source)))
                    continue

                if not 'stop-time' in tdict.keys() and "length" in program and isinstance(program['length'], datetime.timedelta):
                    tdict['stop-time'] = tdict['start-time'] + program['length']
                    tdict['stop from length'] = True

                if self.without_full_timings and self.data_value(["base", "data-format"], str) == "text/html":
                    # This is to catch the midnight date change for HTML pages with just start(stop) times without date
                    # don't enable it on json pages where the programs are in a dict as they will not be in chronological order!!!
                    if last_start[channelid] == None:
                        last_start[channelid] = tdict['start-time']

                    while tdict['start-time'] < last_start[channelid] - tdh:
                        tdict['start-time'] += tdd

                    last_start[channelid] = tdict['start-time']
                    if 'stop-time' in tdict.keys():
                        while tdict['stop-time'] < tdict['start-time']:
                            tdict['stop-time'] += tdd

                tdict['offset'] = self.functions.get_offset(tdict['start-time'])
                tdict['scandate'] = self.functions.get_fetchdate(tdict['start-time'])
                if self.data_value(["base", "data-format"], str) == "text/html":
                    if 'stop-time' in tdict.keys():
                        last_stop = tdict['stop-time']
                    else:
                        last_stop = None

                # Add any known value that does not need further processing
                for k, v in self.process_values(program).items():
                    if k in ('channelid', 'video', 'start-time', 'stop-time'):
                        continue

                    tdict[k] = v

                if 'group' in program.keys() and not program['group'] in (None, ''):
                    self.groupitems[chanid] += 1
                    tdict['group'] = program['group']

                with self.source_lock:
                    self.program_data[chanid].append(tdict)

                #~ self.config.genre_list.append((tdict['genre'].lower(), tdict['subgenre'].lower()))

                if self.show_result:
                    print '    ', channelid, tdict['start-time']
                    for k, v in tdict.items():
                        if isinstance(v, (str, unicode)):
                            vv = ': "%s"' % v
                            print '        ', k, vv.encode('utf-8', 'replace')
                        else:
                            print '        ', k, v

            if len(chanids) > 0:
                for chanid in chanids:
                    if len(self.program_data[chanid]) > 0:
                        self.program_data[chanid][-1]['last of the page'] = True

        return chanids

    def load_detailpage(self, ptype, tdict, parent = None):
        """The code for retreiving and processing a detail page"""
        if tdict['detail_url'] in (None, ''):
            return

        ddata = {'channel': tdict['chanid'], 'detailid': tdict['detail_url']}
        strdata = self.get_page_data(ptype, ddata)
        if not isinstance(strdata, (list,tuple)) or len(strdata) == 0:
            #~ self.functions.update_counter('fail', self.proc_id, tdict['chanid'])
            self.config.log(self.config.text('fetch', 35, (tdict['detail_url'], )), 1)
            return

        values = strdata[0]
        if not isinstance(values, dict):
            return

        if not 'genre' in values.keys() and 'org-genre' in tdict.keys():
            values['genre'] = tdict['org-genre']

        if not 'subgenre' in values.keys() and 'org-subgenre' in tdict.keys():
            values['subgenre'] = tdict['org-subgenre']

        #~ print
        #~ print 'Resulting values'
        #~ for k, v in values.items():
            #~ if isinstance(v, (str, unicode)):
                #~ vv = ': "%s"' % v
                #~ print '        ', k, vv.encode('utf-8', 'replace')
            #~ else:
                #~ print '        ', k, ': ', v

        tdict = self.process_values(values)
        if self.show_result:
        #~ if True:
            print
            print 'Resulting tdict'
            for k, v in tdict.items():
                if isinstance(v, (str, unicode)):
                    vv = ': "%s"' % v
                    print '        ', k, vv.encode('utf-8', 'replace')
                else:
                    print '        ', k, ': ', v

        return tdict

    # Helper functions
    def is_data_value(self, searchpath, dtype = None, empty_is_false = True):
        return is_data_value(searchpath, self.source_data, dtype, empty_is_false)

    def data_value(self, searchpath, dtype = None, default = None):
        return data_value(searchpath, self.source_data, dtype, default)

    def get_loaded(self, type='day', chanid = 0, day = None):
        chanlist = list(self.channels.keys())
        chanlist.append(0)
        if type == 'day':
            if chanid in self.day_loaded.keys():
                if day in self.day_loaded[chanid].keys():
                    return self.day_loaded[chanid][day]

                elif day == 'all' and self.config.opt_dict['offset'] in self.day_loaded[chanid].keys():
                    return self.day_loaded[chanid][self.config.opt_dict['offset']]

            return False

        if type == 'channel':
            if chanid in self.self.channel_loaded.keys():
                return self.self.channel_loaded[chanid]

            return False

        if type == 'page':
            if chanid in self.page_loaded.keys() and day in self.page_loaded[chanid].keys():
                return self.page_loaded[chanid][day]

            return False


    def set_loaded(self, type='day', chanid = None, day = None, value=True):
        chanlist = list(self.channels.keys())
        chanlist.append(0)
        daylist = range( self.config.opt_dict['offset'], (self.config.opt_dict['offset'] + self.config.opt_dict['days']))
        if isinstance(chanid, (list, tuple)):
            chanlist = chanid

        elif chanid not in (None, 'all', 0):
            chanlist = [chanid]

        if type == 'day':
            if isinstance(day, (list, tuple)):
                daylist = day

            elif day not in (None, 'all'):
                daylist = [day]

            for chanid in chanlist:
                if chanid in chanlist:
                    if not chanid in self.day_loaded.keys():
                        self.day_loaded[chanid] = {}

                    for day in daylist:
                        self.day_loaded[chanid][day] = value

        if type == 'channel':
            for chanid in chanlist:
                if chanid in chanlist:
                    self.channel_loaded[chanid] = value

        if type == 'page':
            if isinstance(day, (list, tuple)):
                pagelist = day

            elif isinstance(day, int):
                pagelist = [day]

            else:
                return

            for chanid in chanlist:
                if chanid in chanlist:
                    if not chanid in self.page_loaded.keys():
                        self.page_loaded[chanid] = {}

                    for day in pagelist:
                        self.page_loaded[chanid][day] = value

    def process_values(self, values):
        tdict = {}
        # Add any known value that does not need further processing
        for k, v in values.items():
            if k in ('video', 'genre', 'subgenre'):
                continue

            if k in self.config.key_values['text'] and not v in (None, ''):
                tdict[k] = v

            elif (k in self.config.key_values['bool'] or k in self.config.key_values['video']) and  isinstance(v, bool):
                tdict[k] = v

            elif k in self.config.key_values['int'] and isinstance(v, int):
                #~ if k == 'episode' and v > 1000:
                    #~ continue

                tdict[k] = v

            elif k in self.config.key_values['list'] and isinstance(v, list) and len(v) > 0:
                tdict[k] = v

            elif k in self.config.key_values['timedelta'] and isinstance(v, datetime.timedelta):
                tdict[k] = v

            elif k in self.config.key_values['datetime'] and isinstance(v, datetime.datetime):
                tdict[k] = v

            elif k in self.config.key_values['date'] and isinstance(v, datetime.date):
                tdict[k] = v

            elif k in self.config.roletrans.keys() and isinstance(v, (list, tuple)) and len(v) > 0:
                if not self.config.roletrans[k] in tdict.keys() or len(tdict[self.config.roletrans[k]]) == 0:
                    tdict[self.config.roletrans[k]] = v

                for item in v:
                    if not item in tdict[self.config.roletrans[k]]:
                        tdict[self.config.roletrans[k]].append(item)

            elif k in self.config.credit_keys and isinstance(v, dict):
                for k2, v2 in v.items():
                    if k2 in self.config.roletrans.keys() and isinstance(v2, (list, tuple)) and len(v2) > 0:
                        if not self.config.roletrans[k2] in tdict.keys() or len(tdict[self.config.roletrans[k2]]) == 0:
                            tdict[self.config.roletrans[k2]] = v2

                        for item in v2:
                            if not item in tdict[self.config.roletrans[k2]]:
                                tdict[self.config.roletrans[k2]].append(item)

        if 'genre' in values.keys() or 'subgenre' in values.keys() or 'genres' in values.keys():
            gg = self.get_genre(values)
            tdict['genre'] = gg[0]
            tdict['subgenre'] = gg[1]
            tdict['genres'] =(gg[0], gg[1])
            if len(gg) > 2:
                tdict['org-genre'] = gg[2]

            if len(gg) > 3:
                tdict['org-subgenre'] = gg[3]

        if 'name' in tdict:
            tdict = self.check_title_name(tdict)
        return tdict

    def get_genre(self, values):
        """Sub process for parse_basepage"""
        genre = ''
        subgenre = ''
        if 'genres'in values:
            # It is return as a set of genre/subgenre so we split them
            if isinstance(values['genres'], (str,unicode)):
                values['genre'] = values['genres']

            if isinstance(values['genres'], (list,tuple)):
                if len(values['genres'])> 0:
                    values['genre'] = values['genres'][0]

                if len(values['genres'])> 1:
                    values['subgenre'] = values['genres'][1]

        if self.cattrans_type == 1:
            if self.new_cattrans == None:
                self.new_cattrans = {}

            if 'genre' in values:
                # Just in case it is a comma seperated list
                if isinstance(values['genre'], (str, unicode)):
                    gg = values['genre'].split(',')

                elif isinstance(values['genre'], list):
                    gg = values['genre']

                gs0 =gg[0].strip()
                gs1 = u''
                gg0 = gs0.lower()
                if len(gg) > 1:
                    gs1 = gg[1].strip()

                elif 'subgenre' in values and values['subgenre'] not in (None, ''):
                    gs1 = values['subgenre'].strip()

                gg1 = gs1.lower()
                if gg0 in self.cattrans.keys():
                    if gg1 in self.cattrans[gg0].keys():
                        genre = self.cattrans[gg0][gg1][0].strip()
                        subgenre = self.cattrans[gg0][gg1][1].strip()

                    elif gg1 not in (None, ''):
                        genre = self.cattrans[gg0]['default'][0].strip()
                        subgenre = gs1
                        self.new_cattrans[(gg0, gg1)] = (self.cattrans[gg0]['default'][0].strip().lower(), gg1)

                    else:
                        genre = self.cattrans[gg0]['default'][0].strip()
                        subgenre = self.cattrans[gg0]['default'][1].strip()
                        self.new_cattrans[(gg0,gg1)] = (self.cattrans[gg0]['default'][0].strip().lower(), self.cattrans[gg0]['default'][1].strip().lower())

                elif gg0 not in (None, ''):
                    if gg1 not in (None, ''):
                        self.new_cattrans[(gg0,gg1)] = [self.config.cattrans_unknown.lower().strip(),'']

                    else:
                        self.new_cattrans[(gg0,'')] = [self.config.cattrans_unknown.lower().strip(),'']

                    if self.config.write_info_files:
                        if 'subgenre' in values and values['subgenre'] not in (None, ''):
                            self.config.infofiles.addto_detail_list(u'unknown %s genre/subgenre => ["%s", "%s"]' % (self.source, values['genre'], values['subgenre']))

                        else:
                            self.config.infofiles.addto_detail_list(u'unknown %s genre => %s' % (self.source, values['genre']))

                return (genre, subgenre, gs0, gs1)

        elif self.cattrans_type == 2:
            if self.new_cattrans == None:
                self.new_cattrans = []
            if 'subgenre' in values and values['subgenre'] not in (None, ''):
                if values['subgenre'].lower().strip() in self.cattrans.keys():
                    genre = self.cattrans[values['subgenre'].lower().strip()]
                    subgenre = values['subgenre'].strip()

                else:
                    for k, v in self.cattrans_keywords.items():
                        if k.lower() in values['subgenre'].lower():
                            genre = v.strip()
                            subgenre = values['subgenre'].strip()
                            self.new_cattrans.append((subgenre.lower(), genre.lower()))
                            break

                    else:
                        self.new_cattrans.append((values['subgenre'].lower().strip(), self.config.cattrans_unknown.lower().strip()))

                    if self.config.write_info_files:
                        self.config.infofiles.addto_detail_list(u'unknown %s subgenre => "%s"' % (self.source, values['subgenre']))

        else:
            if 'genre' in values.keys():
                genre = values['genre'].strip()

            if 'subgenre' in values.keys():
                subgenre = values['subgenre'].strip()

        return (genre, subgenre)

    def check_title_name(self, values):
        """
        Process Title names on Grouping issues and apply the rename table
        Return the updated Progam dict
        """
        pgroup = ''
        ptitle = data_value('name', values, str, '').strip()
        psubtitle = data_value('episode title', values, str, '').strip()
        if  ptitle == None or ptitle == '':
            return values

        if re.sub('[-,. ]', '', ptitle).lower() == re.sub('[-,. ]', '', psubtitle).lower():
            del(values['episode title'])
            psubtitle = ''

        # Remove a groupname if in the list
        for group in self.config.groupnameremove:
            if (len(ptitle) > len(group) + 3) and (ptitle[0:len(group)].lower() == group):
                p = ptitle.split(':', 1)
                if len(p) >1:
                    self.config.log(self.config.text('fetch', 36,  (group, ptitle)), 64)
                    if self.config.write_info_files:
                        self.config.infofiles.addto_detail_list(unicode('Group removing = \"%s\" from \"%s\"' %  (group, ptitle)))

                    ptitle = p[1].strip()

        if ptitle.lower() == psubtitle.lower() and not ('genre'in values and values['genre'] == 'serie/soap'):
            psubtitle = ''

        lent = len(ptitle)
        lenst = len(psubtitle)
        lendif = abs(lent - lenst)
        # Fixing subtitle both named and added to the title
        if  0 < lenst < lent and psubtitle.lower() == ptitle[lendif:].lower().strip():
            ptitle = ptitle[:lendif].strip()
            if (ptitle[-1] == ':') or (ptitle[-1] == '-'):
                ptitle = ptitle[:-1].strip()

        # It also happens that the title is both and the subtitle only the title
        elif 0 < lenst < lent and psubtitle.lower() == ptitle[:lendif].lower():
            p = psubtitle
            psubtitle = ptitle[lendif:].lower().strip()
            ptitle = p
            if (psubtitle[0] == ':') or (psubtitle[0] == '-'):
                psubtitle = psubtitle[1:].strip()

        # And the other way around
        elif  lent < lenst and ptitle.lower() == psubtitle[:lent].lower():
            psubtitle = psubtitle[lent:].strip()
            if (psubtitle[0] == ':') or (psubtitle[0] == '-'):
                psubtitle = psubtitle[1:].strip()

        # exclude certain programs
        if  not (ptitle.lower() in self.config.notitlesplit) and not ('genre' in values and values['genre'].lower() in ['movies','film']):
            # and do the title split test
            p = ptitle.split(':', 1)
            if len(p) >1:
                self.config.log(self.config.text('fetch', 37, (ptitle, )), 64)
                # We for now put the first part in 'group name' to compare with other sources
                pgroup = p[0].strip()
                ptitle = p[1].strip()
                if self.config.write_info_files:
                    self.config.infofiles.addto_detail_list(unicode('Name split = %s + %s' % (pgroup, ptitle)))

        # Check the Title rename list
        if ptitle.lower() in self.config.titlerename:
            self.config.log(self.config.text('fetch', 38, (ptitle, self.config.titlerename[ptitle.lower()])), 64)
            if self.config.write_info_files:
                self.config.infofiles.addto_detail_list(unicode('Title renaming %s to %s\n' % (ptitle, self.config.titlerename[ptitle.lower()])))

            ptitle = self.config.titlerename[ptitle.lower()]

        if ptitle.lower() in self.config.titlerename:
            self.config.log(self.config.text('fetch', 38, (ptitle, self.config.titlerename[ptitle.lower()])), 64)
            if self.config.write_info_files:
                self.config.infofiles.addto_detail_list(unicode('Title renaming %s to %s\n' % (ptitle, self.config.titlerename[ptitle.lower()])))

            ptitle = self.config.titlerename[ptitle.lower()]

        values['name'] = ptitle
        values['title'] = (pgroup, ptitle, psubtitle)
        if pgroup != '':
            values['group name'] = pgroup

        if psubtitle != '':
            values['episode title'] = psubtitle

        elif 'episode title' in values.keys():
            del(values['episode title'])

        return values

# end FetchData()

