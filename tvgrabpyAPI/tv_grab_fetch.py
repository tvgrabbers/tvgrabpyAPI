#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Python 3 compatibility
from __future__ import unicode_literals
# from __future__ import print_function

import re, sys, traceback, difflib, os
import time, datetime, pytz, random
import requests, httplib, socket, json
from DataTreeGrab import *
from tv_grab_channel import ProgramNode
from tv_grab_IO import DD_Convert
from threading import Thread, RLock, Semaphore, Event
from xml.sax import saxutils
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

class dtError(dtErrorConstants):
    def __init__(self):
        self.dtWrongDate = 11
        self.dtErrorTexts[self.dtWrongDate] = 'Wrong Page Date!'

dte = dtError()

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
        self.cache_id = self.config.cache_id
        self.json_id = self.config.json_id
        self.ttvdb1_id = self.config.ttvdb1_id
        self.ttvdb2_id = self.config.ttvdb2_id
        self.imdb3_id = self.config.imdb3_id

    # end init()

    def update_counter(self, cnt_type, source_id=None, chanid=None, cnt_add=True, cnt_change=1):
        #source_id: -99 = cache, -98 = jsondata, -11 = ttvdb
        if source_id == None:
            source_id = self.ttvdb1_id

        if not isinstance(cnt_change, int) or cnt_change == 0:
            return

        if not cnt_type in ('base', 'detail', 'empty-base', 'empty-detail', 'fail',
            'lookup', 'lookup_fail', 'queue', 'jsondata', 'failjson', 'exclude'):
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
            if isinstance(source_id, int) and (source_id >= 0 or source_id == self.json_id):
                if cnt_type in self.source_counters['total'].keys():
                    self.source_counters['total'][cnt_type] += cnt_change

                else:
                    self.source_counters['total'][cnt_type] = cnt_change
    # end update_counter()

    def get_counter(self, cnt_type, source_id=None, chanid=None):
        if source_id == None:
            source_id = self.ttvdb1_id

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

            if isinstance(accept_header, dict):
                txtheaders = accept_header

            elif isinstance(accept_header, (str,unicode)) and accept_header!= '':
                txtheaders = {'Accept': accept_header}

            else:
                txtheaders = {}

            txtheaders['Keep-Alive']  = '300'
            txtheaders['User-Agent'] = self.config.user_agents[random.randint(0, len(self.config.user_agents)-1)]
            fu = FetchURL(self.config, url, txtdata, txtheaders, encoding, is_json)
            self.max_fetches.acquire()
            fu.start()
            fu.join(self.config.opt_dict['global_timeout']+1)
            page = fu.result
            self.max_fetches.release()
            if fu.page_status == dte.dtDataOK:
                if (page == None) or (page =={}) or (isinstance(page, (str, unicode)) and \
                    ((re.sub('\n','', page) == '') or (re.sub('\n','', page) =='{}'))):
                    if self.config.write_info_files:
                        self.config.infofiles.add_url_failure('No Data: %s\n' % url)

                    return (dte.dtEmpty, None, fu.status_code)

            return (fu.page_status, page, fu.status_code)

        except(socket.timeout):
            self.config.log(self.config.text('fetch', 1, (self.config.opt_dict['global_timeout'], url)), 1, 1)
            if self.config.write_info_files:
                self.config.infofiles.add_url_failure('Fetch timeout: %s\n' % url)

            self.max_fetches.release()
            return (dte.dtTimeoutError, None, fu.status_code)
    # end get_page()

    def get_json_data(self, name, version = None, source = None, url = None, fpath = None, ctype = None):
        if source == None:
            source = self.json_id

        conv_dd = DD_Convert(self.config, warngoal = self.config.logging.log_queue, caller_id = source)
        local_name = '%s.%s' % (name, version) if isinstance(version, int) and not self.config.test_modus else name
        self.raw_json[name] = ''
        # Try to find the source files locally
        if self.config.test_modus:
            try:
                if fpath != None:
                    fle = self.config.IO_func.open_file('%s/%s.json' % (fpath, name), 'r', 'utf-8')
                    if fle != None:
                        data = json.load(fle)
                        if isinstance(version, int):
                            conv_dd.convert_sourcefile(data, ctype)
                            return conv_dd.csource_data

                        return data

            except(ValueError) as e:
                self.config.log('  JSON error: %s\n' % e)

            except:
                self.config.log(traceback.print_exc())

        elif isinstance(version, int) or self.config.only_local_sourcefiles:
            # We try to get the converted pickle in the supplied location, but check that it is of the right dt version and date
            try:
                if fpath != None:
                    fn = '%s/%s.bin' % (fpath, local_name)
                    if os.path.isfile(fn) and datetime.date.fromtimestamp(os.stat(fn).st_mtime) >= self.config.dtdate:
                        fle = self.config.IO_func.read_pickle(fn)
                        if fle != None and data_value(["dtversion"], fle, tuple) == conv_dd.dtversion():
                            return fle

            except:
                self.config.log(traceback.print_exc())

        # We try to download unless the only_local_sourcefiles flag is set
        if not self.config.only_local_sourcefiles:
            try:
                txtheaders = {'Keep-Alive' : '300',
                              'User-Agent' : self.config.user_agents[random.randint(0, len(self.config.user_agents)-1)] }

                if url in (None, u''):
                    url = self.config.api_source_url

                url = '%s/%s.json' % (url, name)
                self.config.log(self.config.text('fetch', 1,(name, ), 'other'), 1)
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
                    if version == None:
                        return page

                    for v in range(1, version+1):
                        self.config.IO_func.remove_file('%s/%s.%s.json' % (fpath, name, v))
                        self.config.IO_func.remove_file('%s/%s.%s.bin' % (fpath, name, v))

                    conv_dd.convert_sourcefile(page, ctype, '%s/%s.bin' % (fpath, local_name))
                    return conv_dd.csource_data

            except:
                if isinstance(version, int):
                    return None

        # And for the two mainfiles we try to fall back to the library location
        if version == None:
            try:
                fle = self.config.IO_func.open_file('%s/%s.json' % (self.config.source_dir, name), 'r', 'utf-8')
                if fle != None:
                    return json.load(fle)

            except(ValueError) as e:
                self.config.log('  JSON error: %s\n' % e)

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
        Thread.__init__(self, name = 'fetching')
        self.thread_type = 'fetching'
        self.state = 0
        self.config = config
        self.func = self.config.fetch_func
        self.url = url
        self.txtdata = txtdata
        self.txtheaders = txtheaders
        self.encoding = encoding
        self.is_json = is_json
        self.raw = ''
        self.result = None
        self.page_status = dte.dtDataOK
        self.url_request = None
        self.status_code = None

    def run(self):
        self.result = self.get_page_internal()

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
            self.url_request = requests.get(self.url, headers = self.txtheaders, params = self.txtdata, timeout=self.config.opt_dict['global_timeout']/2, stream=True)
            self.status_code = self.url_request.status_code
            if self.url_request.status_code != requests.codes.ok:
                if self.status_code == 500 and len(self.url_request.text) > 0 and not self.url_request.text.strip()[0] in ("{", "["):
                    # This probably is an inclomplete read we possibly can fix
                    self.page_status = dte.dtIncompleteRead

                else:
                    self.url_request.raise_for_status()

            encoding = self.find_html_encoding()
            if encoding != None:
                self.url_request.encoding = encoding

            elif self.encoding != None:
                self.url_request.encoding = self.encoding

            self.raw = self.url_request.content
            self.url_text = self.url_request.text

            if 'content-type' in self.url_request.headers and 'json' in self.url_request.headers['content-type'] or self.is_json:
                try:
                    return self.url_request.json()

                except(ValueError) as e:
                    self.config.log(self.config.text('fetch', 5, (self.url, e)), 1, 1)
                    self.page_status = dte.dtJSONerror
                    if self.config.write_info_files:
                        self.config.infofiles.add_url_failure('JSONError: %s\n' % self.url)
                        self.config.infofiles.write_raw_string(self.url_text)

                return None

            else:
                return self.url_text

        except (requests.ConnectionError):
            self.config.log(self.config.text('fetch', 3, (self.url, )), 1, 1)
            self.page_status = dte.dtURLerror
            if self.config.write_info_files:
                self.config.infofiles.add_url_failure('URLError: %s\n' % self.url)

        except (requests.HTTPError) as e:
            self.config.log(self.config.text('fetch', 4, (self.url, '%s: %s' \
                % (e.response.status_code, e.response.reason))), 1, 1)
            self.page_status = dte.dtHTTPerror
            if self.config.write_info_files:
                self.config.infofiles.add_url_failure('HTTPError %s: %s: %s\n' \
                    % (e.response.status_code, e.response.reason, self.url))

        except (requests.Timeout):
            self.config.log(self.config.text('fetch', 1, (self.config.opt_dict['global_timeout'], self.url)), 1, 1)
            self.page_status = dte.dtTimeoutError
            if self.config.write_info_files:
                self.config.infofiles.add_url_failure('Fetch timeout: %s\n' % self.url)

        except:
            self.config.log(self.config.text('fetch', 2,  (sys.exc_info()[0], sys.exc_info()[1], self.url)), 0)
            self.page_status = dte.dtUnknownError
            if self.config.write_info_files:
                self.config.infofiles.add_url_failure('%s,%s:\n  %s\n' % (sys.exc_info()[0], sys.exc_info()[1], self.url))

# end FetchURL

class DataTree(DataTreeShell, Thread):
    def __init__(self, source, data_def, warnaction = "default", caller_id = 0):
        Thread.__init__(self, name = 'DataTree')
        self.thread_type = 'DataTree'
        self.source = source
        self.export = False
        self.rundata = {}
        self.state = 0
        self.config = self.source.config
        self.fetch_string_parts = re.compile("(.*?[.?!:]+ |.*?\Z)")
        DataTreeShell.__init__(self, data_def, warnaction = warnaction, warngoal = self.config.logging.log_queue, caller_id = caller_id)
        self.print_tags = source.print_tags
        self.show_result = source.show_parsing
        self.fle = source.test_output
        self.simplefilter("error", category = dtDataWarning, severity = 1)
        sys.modules['DataTreeGrab']._warnings.filterwarnings('ignore', category = dtLinkWarning, \
            message = 'Regex "\\\d\*/\?\(\\\d\*\)\.\*" in: .*?', caller_id = caller_id)
        sys.modules['DataTreeGrab']._warnings.filterwarnings('ignore', category = dtLinkWarning, \
            message = 'Regex "\(\\\d\*\)/\.\*" in: .*?', caller_id = caller_id)

    def run(self):
        try:
            if data_value('task',self.rundata, str) == 'epdata':
                tid = data_value('tid',self.rundata, int, 0)
                queryid = data_value('queryid',self.rundata, int, -1)
                self.searchtree.show_progress = True
                if self.extract_datalist():
                    if self.check_errorcode() == 7:
                        self.config.log(self.config.text('ttvdb', 16, ('%s: %s' % (tid, self.rundata['name']), )))

                    else:
                        self.config.log(self.config.text('fetch', 13, (self.check_errorcode(text_values = True)[0], )))

                    self.source.detail_request.put({'task': 'fail_ep_info', 'queryid': queryid})

                if self.export:
                    chanid = data_value('chanid',self.rundata, str)
                    if len(self.result) == 0:
                        self.source.functions.update_counter('fail', self.config.ttvdb1_id, chanid)
                        self.source.detail_request.put({'task': 'fail_ep_info', 'tid': tid, 'queryid': queryid})

                    else:
                        eps = self.source.process_data(self.result, tid, 'en')
                        self.init_data_def(self.source.data_value("seriesname", dict))
                        if not self.extract_datalist():
                            self.source.store_data('ttvdbid', self.result)

                        epc = []
                        for k, v in eps[1].items():
                            epc.append({'tid': tid,'sid': k, 'count': v})

                        self.source.store_data('episodes', eps[0])
                        self.source.store_data('epcount', epc, {'task': 'process_ep_info', 'tid': tid, 'queryid': queryid})

        except dtWarning as e:
            self.config.log(self.config.text('fetch', 13, (e.message, )))
            self.source.detail_request.put({'task': 'fail_ep_info', 'queryid': queryid})

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
        def link_warning(text, severity=4):
            self.warn('%s on function: "%s"\n   Using link_data: %s' % (text, fid, data), dtLinkWarning, severity, 3)

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

                # It's a single list of dicts created through the "name" keyword
                if is_data_value(0, data, list) and (len(data) == 1 or is_data_value(1, data, int)):
                    modus = data_value(1, data, int, 0)
                    for item in data[0]:
                        if not isinstance(item, dict):
                            continue

                        for k, v in item.items():
                            if k.lower() in self.config.roletrans.keys():
                                role = self.config.roletrans[k.lower()]
                                if modus == 1:
                                    for pp in v:
                                        cn = re.search('(.*?)\((.*?)\)',pp)
                                        if cn:
                                            add_person(role, cn.group(1).strip(), cn.group(2).strip())

                                        else:
                                            add_person(role, pp.strip())

                                else:
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

                # data[0] is a list of list of names
                # data[1] is a list of roles
                # data[2] is an optional list of characters matching data[0]
                if is_data_value(0, data, list) and is_data_value(1, data, list):
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

                # The same but with a single role
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
                            if len(cn[0].strip().split(' ')) > 4:
                                continue

                            if len(cn) > 1:
                                add_person(role, cn[0].strip(), cn[1].split(')')[0].strip())

                            else:
                                add_person(role, cn[0].strip())

                return credits

            # Process a rating item
            if fid == 104:
                rlist = []
                if is_data_value(0, data, str):
                    # We treat a string as a list of items with a maximum length
                    if data_value(1, data, str) == 'as_list':
                        item_length = data_value(2, data, int, 1)
                        unique_added = False
                        for index in range(len(data[0])):
                            code = None
                            for cl in range(item_length):
                                if index + cl >= len(data[0]):
                                    continue

                                tval = data[0][index: index + cl + 1]
                                if tval in self.source.source_data['rating'].keys():
                                    code = self.source.source_data['rating'][tval]
                                    break

                            if code != None:
                                if code in self.config.rating["unique_codes"].keys():
                                    if unique_added:
                                        continue

                                    rlist.append(code)
                                    unique_added = True

                                elif self.source.source_data['rating'][code] in self.config.rating["addon_codes"].keys():
                                    rlist.append(code)

                            elif self.config.write_info_files:
                                self.config.infofiles.addto_detail_list(u'new %s rating => %s' % (self.source.source, code))

                    else:
                        if data[0].lower() in self.source.source_data['rating'].keys():
                            v = self.source.source_data['rating'][data[0].lower()]
                            if v in self.config.rating["unique_codes"].keys():
                                rlist.append(v)

                            elif v in self.config.rating["addon_codes"].keys():
                                rlist.append(v)

                        elif self.config.write_info_files:
                            self.config.infofiles.addto_detail_list(u'new %s rating => %s' % (self.source.source, data[0]))

                elif is_data_value(0, data, list):
                    unique_added = False
                    for item in data[0]:
                        if item.lower() in self.source.source_data['rating'].keys():
                            v = self.source.source_data['rating'][item.lower()]
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
                if len(data) >= 2 and isinstance(data[0], dict):
                    for k, v in data[0].items():
                        kl = k.lower().strip()
                        for i in range(1, len(data)):
                            if isinstance(data[i], (str, unicode)) and kl in data[i].lower().strip():
                                return v

                return default

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
            if fid in (107, 201):
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
            if fid in (108, 202):
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

            # strip data[1] from the start of data[0] if present and make sure it's unicode
            elif fid == 109:
                return {"fid": 1}

        except:
            self.config.log([self.config.text('fetch', 11, ('link', fid, self.source.source)), traceback.format_exc()], 1)
            return default

# end DataTree()

class theTVDB_v1(Thread):
    def __init__(self, config, source_data):
        Thread.__init__(self, name = 'source-thetvdb')
        self.config = config
        self.functions = self.config.fetch_func
        self.proc_id = self.config.ttvdb1_id
        self.quit = False
        self.ready = False
        self.state = 0
        self.active = True
        self.lastrequest = None
        self.lastquery = None
        self.pending_tids = {}
        self.queried_titles = {}
        self.api_key = "0BB856A59C51D607"
        self.source_lock = RLock()
        # The queue to receive answers on database queries
        self.cache_return = Queue()
        # The queue to receive requests for detail fetches
        self.detail_request = Queue()
        self.config.queues['ttvdb'] = self.detail_request
        self.thread_type = 'lookup'
        self.test_output = sys.stdout
        self.print_tags = False
        self.print_searchtree = False
        self.show_parsing = False
        self.print_roottree = False
        self.roottree_output = self.test_output
        self.show_result = False
        self.config.threads.append(self)
        self.local_encoding = self.config.logging.local_encoding
        self.show_progres = False
        self.lookup_log = []
        try:
            self.source_data = source_data
            self.source = self.source_data['name']
            self.lang_list = self.source_data['lang-list']
            self.detail_keys = {}
            self.detail_keys['series'] = list(self.source_data["last_updated"]["values"].keys())
            self.detail_keys['episodes'] = list(self.source_data["episodes"]["values"].keys())
            self.config.detail_keys['ttvdb'] = self.detail_keys['series']
            self.config.detail_keys['episodes'] = self.detail_keys['episodes']
            self.site_tz = self.source_data["site-tz"]
            self.datatrees = {}
            self.episodetrees = {}
            self.queryid = 0
            for ptype in ("seriesid", "last_updated", "episodes"):
                self.datatrees[ptype] = DataTree(self, self.data_value(ptype, dict), 'always', self.proc_id)

        except:
            self.config.opt_dict['disable_ttvdb'] = True
            traceback.print_exc()

    def run(self):
        if self.config.opt_dict['disable_ttvdb']:
            return

        pending_requests = {}
        def make_se(data):
            return '(s%se%s) %r:%r' % (unicode(data['season']).rjust(2, '0'), unicode(data['episode']).rjust(2, '0'), data['stitle'], data['episode title'])

        try:
            self.state = 4
            while True:
                if self.quit and self.detail_request.empty():
                    self.state = 0
                    break

                try:
                    crequest = self.detail_request.get(True, 5)
                    self.lastrequest = datetime.datetime.now()
                    if self.quit:
                        if 'parent' in crequest:
                            crequest['parent'].detail_return.put('quit')

                        continue

                except Empty:
                    continue

                if (not isinstance(crequest, dict)) or (not 'task' in crequest):
                    continue

                if crequest['task'] == 'request_ep_info':
                    if not 'parent' in crequest:
                        continue

                    parent = crequest['parent']
                    if 'pn' in crequest:
                        pn = crequest['pn']
                        self.state = 3
                        qanswer = self.get_season_episode(parent, pn)
                        if not is_data_value('state', qanswer, int):
                            qanswer = {'state': 0, 'data': None}

                        if qanswer['state'] == -1:
                            parent.detail_return.put('quit')
                            self.quit = True
                            self.state = 4
                            continue

                        elif qanswer['state'] in (0, 1):
                            # Failed / Finished
                            d = qanswer['data']
                            parent.detail_return.put({'source': self.proc_id, 'data': d, 'pn': pn})
                            self.functions.update_counter('queue', self.proc_id,  parent.chanid, False)
                            if qanswer['state'] == 1:
                                self.functions.update_counter('lookup', self.proc_id, parent.chanid)
                                self.lookup_log.append('lookup %s(%s) <= %s: %s %s\n' % \
                                    (d['ttvdbid'], make_se(d), parent.chan_name, pn.get_start_stop(True, True), pn.get_title()))

                            else:
                                self.functions.update_counter('lookup_fail', self.proc_id, parent.chanid)
                                self.lookup_log.append('failed %s <= %s: %s %s\n' % \
                                    (qanswer['tid'], parent.chan_name, pn.get_start_stop(True, True), pn.get_title()))

                        elif qanswer['state'] == 2:
                            # Answer is pending
                            #{'state': 2, 'tid': tid, 'queryid':queryid,'name': series_name, 'tdate': datetime.date.today()}
                            queryid = qanswer['queryid']
                            tid = qanswer['tid']
                            chanid = parent.chanid
                            self.pending_tids[tid] = queryid
                            pending_requests[queryid] = {'tid': tid, 'requests': [{'pn': pn, 'parent': parent}]}

                        elif qanswer['state'] == 3:
                            # There is a request for this tid pending
                            #{'state': 3, 'tid': tid}
                            queryid = self.pending_tids[qanswer['tid']]
                            pending_requests[queryid]['requests'].append({'pn': pn, 'parent': parent})
                    self.state = 4
                    continue

                if crequest['task'] == 'process_ep_info':
                    queryid = crequest['queryid']

                    if queryid in pending_requests:
                        tid = pending_requests[queryid]['tid']
                        prequests = pending_requests[queryid]['requests']
                        self.state = 3
                        for r in prequests:
                            parent = r['parent']
                            pn = r['pn']
                            qanswer = self.get_season_episode(parent, pn, tid)
                            if not is_data_value('state', qanswer, int):
                                qanswer = {'state': 0, 'data': None}

                            if qanswer['state'] == -1:
                                parent.detail_return.put('quit')
                                self.quit = True
                                self.state = 4
                                continue

                            d = qanswer['data']
                            parent.detail_return.put({'source': self.proc_id, 'data': d, 'pn': pn})
                            self.functions.update_counter('queue', self.proc_id,  parent.chanid, False)
                            if qanswer['state'] == 1:
                                self.functions.update_counter('lookup', self.proc_id, parent.chanid)
                                self.lookup_log.append('lookup %s(%s) <= %s: %s %s\n' % \
                                    (d['ttvdbid'], make_se(d), parent.chan_name, pn.get_start_stop(True, True), pn.get_title()))

                            else:
                                self.functions.update_counter('lookup_fail', self.proc_id, parent.chanid)
                                self.lookup_log.append('failed %s <= %s: %s %s\n' % \
                                    (qanswer['tid'], parent.chan_name, pn.get_start_stop(True, True), pn.get_title()))

                        del self.pending_tids[tid]
                        del pending_requests[queryid]
                        self.state = 4
                    continue

                if crequest['task'] == 'fail_ep_info':
                    queryid = crequest['queryid']

                    if queryid in pending_requests:
                        tid = pending_requests[queryid]['tid']
                        prequests = pending_requests[queryid]['requests']
                        for r in prequests:
                            parent = r['parent']
                            pn = r['pn']
                            parent.detail_return.put({'source': self.proc_id, 'data': None, 'pn': pn})
                            self.functions.update_counter('queue', self.proc_id,  parent.chanid, False)
                            self.functions.update_counter('lookup_fail', self.proc_id, parent.chanid)
                            self.lookup_log.append('failed %s <= %s: %s %s\n' % \
                                (tid, parent.chan_name, pn.get_start_stop(True, True), pn.get_title()))

                        del self.pending_tids[tid]
                        del pending_requests[queryid]
                    continue

                if crequest['task'] == 'quit':
                    self.quit = True
                    for dt in self.datatrees.values():
                        try:
                            dt.searchtree.quit = True

                        except:
                            continue

                    for dt in self.episodetrees.values():
                        try:
                            dt.searchtree.quit = True

                        except:
                            continue

                    continue

            if self.config.ttvdb_log_output != None:
                self.lookup_log.sort()
                for line in self.lookup_log:
                    self.config.ttvdb_log_output.write(line)

                self.config.ttvdb_log_output.close()
                self.config.ttvdb_log_output = None

        except:
            self.config.queues['log'].put({'fatal': [traceback.format_exc(), '\n'], 'name': 'theTVDB'})
            self.ready = True
            self.state = 0
            return(98)

    def query_ttvdb(self, ptype, pdata, chanid = None, background = False):
        '''
        Make a request on theTVDB.com and return the queryID or any return data from DataTree
        '''
        if self.lastquery != None and datetime.datetime.now() - self.lastquery < datetime.timedelta(seconds = 1):
            time.sleep(random.randint(self.config.opt_dict['nice_time'][0], self.config.opt_dict['nice_time'][1]))

        self.lastquery = datetime.datetime.now()
        if not ptype in self.datatrees.keys() or not isinstance(pdata, dict) or self.config.args.only_cache:
            return

        # A request must either contain a name or an ID
        if not ('ttvdbid' in pdata or 'name' in pdata):
            return

        if is_data_value(['ttvdbid'], pdata, (int, str)):
            pdata['ttvdbid'] = unicode(pdata['ttvdbid'])

        if is_data_value(['name'], pdata, (int, str)):
            pdata['name'] = unicode(pdata['name'])

        pdata['api-key'] = self.api_key
        # A language must be valid
        if (not pdata['lang'] in self.lang_list) and not (pdata['lang'] == 'all' and ptype == 'seriesid'):
            pdata['lang'] = 'en'

        # Do we start an independent DataTree thread?
        if background:
            self.queryid += 1
            queryid = self.queryid
            self.episodetrees[queryid] = DataTree(self, self.data_value(ptype, dict), 'always', self.proc_id)
            dtree = self.episodetrees[queryid]
            dtree.rundata = {'task':'epdata',
                                        'queryid': queryid,
                                        'tid': int(pdata['ttvdbid']),
                                        'lang': pdata['lang'],
                                        'name': pdata['name'],
                                        'chanid': chanid}

        else:
            dtree = self.datatrees[ptype]

        # Get the page
        url = dtree.get_url(pdata, False)
        if self.print_searchtree:
            print '(url, encoding, accept_header, url_data, is_json)'
            print url

        self.functions.update_counter('detail', self.proc_id, chanid)
        pstate, page, pcode = self.functions.get_page(url)
        if pstate != dte.dtDataOK or page == None:
            self.functions.update_counter('fail', self.proc_id, chanid)
            return None

        try:
            if dtree.init_data(page):
                return None

            if background:
                dtree.start()
                return queryid

            if dtree.extract_datalist():
                self.functions.update_counter('fail', self.proc_id, chanid)
                # It failed
                return None

            data = copy(dtree.result)
            if len(data) == 0:
                self.functions.update_counter('fail', self.proc_id, chanid)
                return None

            # we extract the main series data
            if ptype == 'episodes':
                dtree.init_data_def(self.data_value("seriesname", dict))
                if not dtree.extract_datalist():
                    self.store_data('ttvdbid', dtree.result)

                dtree.init_data_def(self.data_value("episodes", dict))

            return data

        except dtWarning as e:
            self.functions.update_counter('fail', self.proc_id, chanid)
            self.config.log(self.config.text('fetch', 14, (e.message, ptype, 'theTVDB.com')))
            return None

    def process_data(self, data, tid, lang):
        eps = []
        abs_cnt = 0
        pre_eps = []
        pre_cnt = 0
        sep_cnt = {}
        data.sort(key=lambda p: (p['sid'], p['eid']))
        for ep in data:
            if not isinstance(ep, dict):
                continue

            sid = data_value('sid', ep, int, -1)
            eid = data_value('eid', ep, int, -1)
            abseid = data_value('abseid', ep, int, -1)
            tepid = data_value('tepid', ep, int, -1)
            if sid == -1 or eid == -1:
                continue

            if sid in sep_cnt.keys():
                sep_cnt[sid] += 1

            else:
                sep_cnt[sid] = 1

            title = data_value('episode title', ep, str, 'Episode %s' % eid)
            desc = data_value('description', ep, str, None)
            airdate = data_value('airdate', ep, datetime.date, None)
            rating = data_value('star-rating', ep, float, None)
            writer = data_value('writer', ep, list)
            guest = data_value('guest', ep, list)
            actor = data_value('actor', ep, list)
            director = data_value('director', ep, list)
            edata = {'tid': int(tid),
                    'sid': int(sid),
                    'eid': int(eid),
                    'abseid': int(abseid),
                    'tepid': int(tepid),
                    'episode title': title,
                    'airdate': airdate,
                    'writer': writer,
                    'guest': guest,
                    'director': director,
                    'lang': lang,
                    'star-rating': rating,
                    'description': desc}

            eps.append(edata)

        return [eps, sep_cnt]

    def store_data(self, task, data, confirm = None):
        '''
        Store any fetched data in the Database
        Optionally ask the database to confirm storing the data
        '''
        if isinstance(data, list) and len(data) == 0:
            return

        if task == 'ttvdbid':
            dbdata = {'task':'add', 'ttvdb': data}

        elif task == 'alias':
            dbdata = {'task':'add', 'ttvdb_alias': data}

        elif task == 'episodes':
            dbdata = {'task':'add', 'episodes': data}

        elif task == 'epcount':
            dbdata = {'task':'add', 'epcount': data}

        elif task == 'delete ttvdbid':
            dbdata ={'task':'delete', 'ttvdb': data}

        else:
            return

        if confirm != None:
            dbdata['queue'] = self.detail_request
            dbdata['confirm'] = confirm

        self.config.queues['cache'].put(dbdata)

    def get_cache_return(self, task = None, name = None, data = None):
        '''
        Wait for any returned data from the database
        If task is set perform the query
        '''
        if self.quit:
            return -1

        if task == 'ttvdbid':
            self.config.queues['cache'].put({'task':'query_id', 'parent': self, 'ttvdb': {'name': name}})

        elif task == 'ttvdbname':
            self.config.queues['cache'].put({'task':'query_id', 'parent': self, 'ttvdb': {'tid': name}})

        elif task == 'ttvdb_alias':
            self.config.queues['cache'].put({'task':'query_id', 'parent': self, 'ttvdb_alias': {'alias': name}})

        elif task == 'query':
            self.config.queues['cache'].put({'task':task, 'parent': self, name: data})

        elif task != None:
            # Unknown query
            return

        self.state += 8
        value = self.cache_return.get(True)
        self.state -= 8
        if value == 'quit':
            self.ready = True
            return -1

        return value

    def get_ttvdb_id(self, name, lang='en', chanid=None):
        '''
        Search the database and/or theTVDB for an ID
        If it is not found on theTVDB store it to not check again for a 30 days
        If it is found on the TVDB retrieve and store the episode data
        Check self.pending_tids and self.queried_titles for pending searches
        '''
        def get_tid(idsource = 'from db'):
            if idsource == 'from db':
                data = self.get_cache_return('ttvdb_alias', name)

            elif idsource == 'from ttvdb':
                data = self.query_ttvdb('seriesid', {'name': series_name, 'lang': lang}, chanid)

            else:
                return (0, None)

            if data == -1:
                # A quit request
                return (-1, None)

            elif not isinstance(data, list) or len(data) == 0:
                # Nothing found
                return (0, None)

            if len(data) == 1:
                return (data_value([0, 'tid'], data, int, 0), data_value([0, 'tdate'], data, datetime.date))

            tids = {}
            tidcnt = 0
            tindex = -1
            # Return the first unless another is more frequent
            for index in range(len(data)):
                rtid = data_value([index, 'tid'], data, int, 0)
                if rtid == 0:
                    continue

                if not rtid in tids.keys():
                    tids[rtid] = 1

                else:
                    tids[rtid] += 1

                if tids[rtid] > tidcnt:
                    tidcnt =  tids[rtid]
                    tindex = index

            if tindex > -1:
                rtid = data_value([tindex, 'tid'], data, int, 0)
                rtdate = data_value([tindex, 'tdate'], data, datetime.date)

                self.queried_titles[name.lower()] = rtid
                return (rtid, rtdate)

            return (0, None)

        def check_alias():
            alias = self.get_cache_return('ttvdb_alias', name)
            if alias == -1:
                return -1

            if alias == None or len(alias) == 0:
                return {'tid':0, 'tdate': None, 'name': name, 'lang': None}

            return alias[0]

        tid = 0
        last_updated = None
        new_fetch = True
        #First check if a request has been done or is pending
        if name.lower() in self.queried_titles:
            tid = self.queried_titles[name.lower()]
            if tid == 0:
                return {'state': 0, 'tid': None}

            if tid in self.pending_tids.keys():
                # There already is a lookup underway
                return {'state': 3, 'tid': tid}

            return {'state': 1, 'tid': tid, 'tdate': last_updated, 'name': name}

        if tid == 0:
            (tid, last_updated) = get_tid('from db')
            if not isinstance(last_updated, datetime.date):
                new_fetch = None

            else:
                new_fetch = bool((datetime.date.today() - last_updated).days > 30)

            if tid == -1:
                self.ready = True
                return {'state': -1, 'tid': None}

            elif tid == 0:
                if new_fetch == False:
                    return {'state': 0, 'tid': None}

            elif tid in self.pending_tids.keys():
                # There already is a lookup underway
                return {'state': 3, 'tid': tid}

            elif new_fetch == False:
                return {'state': 1, 'tid': tid, 'tdate': last_updated, 'name': name}

            elif new_fetch and not self.config.args.only_cache:
                data = self.query_ttvdb('last_updated', { 'ttvdbid': tid, 'lang': lang})
                if is_data_value([0, 'last updated'], data, datetime.datetime) and \
                    data_value([0, 'last updated'], data, datetime.datetime).date() < last_updated:
                        # No updates on theTVDB
                        return {'state': 1, 'tid': tid, 'tdate': last_updated, 'name': name}

        # First we look for a known alias
        series_name = check_alias()
        if series_name == -1:
            self.ready = True
            return {'state': -1, 'tid': None}

        if tid == 0:
            tid = series_name['tid']

        series_name = series_name['name']
        langs = self.config.ttvdb_langs
        if lang not in self.config.ttvdb_langs and lang in self.lang_list:
            langs.append(lang)

        try:
            aliasses = [series_name.lower(), name.lower()]
            if tid == 0 and not self.config.args.only_cache:
                (tid, lu) = get_tid('from ttvdb')

            if tid == 0:
                # No data
                self.store_data('alias', {'tid': 0, 'name': series_name, 'alias': aliasses})
                self.queried_titles[name.lower()] = 0
                self.queried_titles[series_name.lower()] = 0
                return {'state': 0, 'tid': None}

            if tid in self.pending_tids.keys():
                # There already is a lookup underway
                return {'state': 3, 'tid': tid}

            self.queried_titles[name.lower()] = tid
            if series_name.lower() != name.lower():
                self.queried_titles[series_name.lower()] = tid

            #We look for other languages
            data = self.query_ttvdb('seriesid', {'name': series_name, 'lang': 'all'}, chanid)
            if isinstance(data, list) and len(data) > 0:
                for index in range(len(data)):
                    if data_value([index, 'tid'], data, int) == tid and data_value([index, 'lang'], data, str) in langs:
                        if is_data_value([index, 'name'], data, str):
                            aname = data[index]['name'].lower()
                            if not aname in aliasses:
                                aliasses.append(aname)

                            if aname not in self.queried_titles.keys():
                                self.queried_titles[aname] = data_value([index, 'tid'], data, int, 0)

                self.store_data('alias', {'tid': tid, 'name': series_name, 'alias': aliasses})

        except:
            self.config.log([self.config.text('ttvdb', 11), traceback.format_exc()])
            return {'state': 0, 'tid': None}

        # And we retreive the episodes
        epdata = self.get_all_episodes(tid, lang, chanid, name)
        if epdata['state'] == -1:
            return {'state': -1, 'tid': None}

        epdata['tdate'] = datetime.date.today()
        epdata['name'] = series_name
        return epdata

    def get_all_episodes(self, tid, lang='en', chanid=None, name = None):
        try:
            eps = []
            langs = self.config.ttvdb_langs[:]
            if isinstance(lang, list):
                for l in lang:
                    if l not in self.config.ttvdb_langs and l in self.lang_list:
                        langs.append(l)

            elif lang not in self.config.ttvdb_langs and lang in self.lang_list:
                langs.append(lang)

            while 'en' in langs:
                langs.remove('en')

            # We first retrieve the english data in the background
            queryid = self.query_ttvdb('episodes', {'ttvdbid': tid, 'lang': 'en', 'name': name}, chanid, True)
            if queryid == None:
                return {'state': 0, 'tid': tid}

            dtree = self.episodetrees[queryid]
            actkey, keycount = dtree.searchtree.progress_queue.get(True)

            if self.show_progres:
                # It's a call through the commandline so we give feed-back
                dtree.export = True
                qi = []
                qi.append(queryid)
                self.config.log([self.config.text('ttvdb', 11, ('en', name, tid, keycount), type = 'frontend')])
                for i in range(keycount):
                    keyno = dtree.searchtree.progress_queue.get(True)
                    self.config.log([self.config.text('ttvdb', 12, keyno, type = 'frontend')],log_target = 1)

                for l in langs:
                    queryid = self.query_ttvdb('episodes', {'ttvdbid': tid, 'lang': l, 'name': name}, chanid, True)
                    qi.append(queryid)
                    dtree = self.episodetrees[queryid]
                    dtree.export = True
                    keyno = dtree.searchtree.progress_queue.get(True)
                    self.config.log([self.config.text('ttvdb', 11, (l, name, tid, keyno[1]), type = 'frontend')])
                    for i in range(keyno[1]):
                        keyno = dtree.searchtree.progress_queue.get(True)
                        self.config.log([self.config.text('ttvdb', 12, keyno, type = 'frontend')],log_target = 1)

                for queryid in qi:
                    self.episodetrees[queryid].join()

            else:
                dtree.searchtree.show_progress = False
                if keycount > 500:
                    # It's to big so we stay with only the English data collection in the background
                    dtree.export = True
                    return {'state': 2, 'tid': tid, 'queryid':queryid}

                for l in langs:
                    # Collect the other languages in this thread
                    data = self.query_ttvdb('episodes', {'ttvdbid': tid, 'lang': l}, chanid)
                    if not isinstance(data, list):
                        # No data
                        continue

                    ep = self.process_data(data, tid, l)
                    eps.extend(ep[0])

                dtree.join()
                # And collect the data from the first thread
                data = dtree.result
                if len(data) == 0:
                    self.functions.update_counter('fail', self.proc_id, chanid)

                else:
                    ep = self.process_data(data, tid, 'en')
                    eps.extend(ep[0])
                    epc = []
                    for k, v in ep[1].items():
                        epc.append({'tid': tid,'sid': k, 'count': v})

                    self.store_data('epcount', epc)

        except:
            self.config.log([self.config.text('ttvdb', 12), traceback.format_exc()])
            return {'state': 0, 'tid': tid}

        # We store the data and let the database tell when it's available
        self.store_data('episodes', eps, {'task': 'process_ep_info', 'queryid': queryid})
        return {'state': 2, 'tid': tid, 'queryid':queryid}

    def get_season_episode(self, parent = None, data = None, tid = None):
        def prepare_return(rdata, tid, lang):
            tepid = rdata.keys()[0]
            ept = data.get_value('episode title')
            if ept in ('', None):
                ept = data_value([tepid,'episode title', lang], rdata, str)

            if ept in ('', None):
                ept = data_value([tepid,'episode title', 'en'], rdata, str)

            if ept in ('', None):
                for k, v in data_value([tepid,'episode title'], rdata, dict):
                    if v not in ('', None):
                        ept = v
                        break

            return {'state': 1, 'data':{'ttvdbid': tid,
                    'ttvdbepid': tepid,
                    'season': data_value([tepid,'sid'], rdata, int, 0),
                    'episode': data_value([tepid,'eid'], rdata, int, 0),
                    'abs episode':data_value([tepid,'abseid'], rdata, int, 0),
                    'airdate': data_value([tepid,'airdate'], rdata, datetime.date, None),
                    'stitle': series_name,
                    'episode title': ept,
                    'description': data_value([tepid,'description',lang], rdata, str),
                    'star-rating': data_value([tepid,'star-rating'], rdata, float, None)}}

        if not isinstance(data, ProgramNode):
            return {'state': 0, 'tid': -1, 'data': None}

        if parent == None:
            parent = data.channel_config

        if parent.get_opt('disable_ttvdb') or parent.group in self.config.ttvdb_disabled_groups:
            # We do not lookup for regional channels and radio
            return {'state': 0, 'tid': -1, 'data': None}

        lang = self.config.group_language[parent.group]
        series_name = data.get_value('name')
        if tid == None:
            tid = self.get_ttvdb_id(series_name, lang, chanid = parent.chanid)
            if not isinstance(tid, dict) or tid['state'] == 0:
                self.config.log(self.config.text('ttvdb', 13, (series_name, parent.chan_name)), 128)
                # No ID
                return {'state': 0, 'tid': 0, 'data': None}

            elif tid['state'] == -1:
                # Quit signaled
                return {'state': -1, 'tid': -1, 'data': None}

            elif tid['state'] in (2, 3):
                # Request pending
                return tid

            series_name = tid['name']
            tid = tid['tid']

        eptitle = data.get_value('episode title')
        epno = data.get_value('episode')
        seno = data.get_value('season')
        # First if season and episode are known
        if data.is_set('episode') and data.is_set('season'):
            eps = self.get_cache_return('query', 'ep_by_id',  {'tid': tid, 'eid': epno, 'sid': seno})
            if eps == -1:
                return {'state': -1, 'tid': -1, 'data': None}

            if tid in eps.keys() and len(eps[tid]) == 1:
                # We only got one match so we return it
                self.config.log(self.config.text('ttvdb', 14, (data.get_value('name'), data.get_value('episode title'))), 24)
                return prepare_return(eps.values()[0], tid, lang)

        # Next we just look for a matching subtitle (if set)
        if data.is_set('episode title') and eptitle != '':
            eid = self.get_cache_return('query', 'ep_by_title', \
                                                        {'tid': tid,
                                                        'episode title': eptitle})

            if eid == -1:
                return {'state': -1, 'tid': -1, 'data': None}

            if tid in eid.keys() and len(eid[tid]) == 1:
                # We only got one match so we return it
                self.config.log(self.config.text('ttvdb', 14, (data.get_value('name'), data.get_value('episode title'))), 24)
                return prepare_return(eid.values()[0], tid, lang)

        # What can we find on season/episode
        qdict = {'tid': tid}
        if data.is_set('episode'):
            qdict['eid'] = epno

        if data.is_set('season'):
            qdict['sid'] = seno

        eps = self.get_cache_return('query', 'ep_by_id', qdict )
        if eps == -1:
            return {'state': -1, 'tid': -1, 'data': None}

        if tid in eps.keys() and len(eps[tid]) == 1:
            # We only got one match so we return it
            self.config.log(self.config.text('ttvdb', 14, (data.get_value('name'), data.get_value('episode title'))), 24)
            return prepare_return(eps.values()[0], tid, lang)

        # And on absolute episode numbers
        if data.is_set('episode'):
            absep = self.get_cache_return('query', 'ep_by_id', \
                                                        {'tid': tid,
                                                        'abseid': epno} )

            if absep == -1:
                return {'state': -1, 'tid': -1, 'data': None}

            if tid in absep.keys() and len(absep[tid]) == 1:
                # We only got one match so we return it
                self.config.log(self.config.text('ttvdb', 14, (data.get_value('name'), data.get_value('episode title'))), 24)
                return prepare_return(absep.values()[0], tid, lang)

        if data.is_set('episode title') and eptitle != '' and  tid in eps.keys() and len(eps[tid]) > 0:
            # Now we get a list of episodes matching what we already know and compare with confusing characters removed
            subt = re.sub('[-,. ]', '', self.functions.remove_accents(data.get_value('episode title')).lower())
            ep_dict = {}
            ep_list = []
            for ep in eps[tid].values():
                for l, ept in ep['episode title'].items():
                    if ept == '':
                        continue

                    s = re.sub('[-,. ]', '', self.functions.remove_accents(ept).lower())
                    ep_list.append(s)
                    ep_dict[s] = ep
                    if s == subt:
                        self.config.log(self.config.text('ttvdb', 14, (data.get_value('name'), data.get_value('episode title'))), 24)
                        return prepare_return(ep, tid, lang)

            # And finally we try a difflib match
            match_list = difflib.get_close_matches(subt, ep_list, 1, 0.7)
            if len(match_list) > 0:
                ep = ep_dict[match_list[0]]
                self.config.log(self.config.text('ttvdb', 14, (data.get_value('name'), data.get_value('episode title'))), 24)
                return prepare_return(ep, tid, lang)

        self.config.log(self.config.text('ttvdb', 15, (data.get_value('name'), data.get_value('episode title'), parent.chan_name)), 128)
        return {'state': 0, 'tid': tid, 'data': None}

    def check_ttvdb_title(self, series_name, lang=None, ttvdbid = 0):
        if self.config.opt_dict['disable_ttvdb']:
            return(-1)

        self.show_progres = True
        if lang == None:
            lang = self.config.xml_language

        langs = list(set(self.config.group_language.values()))
        langs.extend(self.config.ttvdb_langs)
        if not 'en' in langs:
            langs.append('en')

        if lang in self.lang_list and not lang in langs:
            langs.append(lang)

        # Check if a record exists
        tid = self.get_cache_return('ttvdb_alias', series_name)
        if tid == -1:
            return(-1)

        if ttvdbid != 0:
            data = self.query_ttvdb('last_updated', {'ttvdbid': ttvdbid, 'lang': 'en'})
            if data == None:
                print(self.config.text('ttvdb', 14, (ttvdbid, ), type = 'frontend').encode(self.local_encoding, 'replace'))
                return(0)

            else:
                new_name = data[0]['name']

        if tid != None and len(tid) > 0:
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
            # It's not jet in the database
            print(self.config.text('ttvdb', 3,(series_name, ) , type = 'frontend').encode(self.local_encoding, 'replace'))
            old_tid = -1

        if ttvdbid != 0:
            if old_tid == -1:
                print(self.config.text('ttvdb', 16, (ttvdbid, new_name), type = 'frontend').encode(self.local_encoding, 'replace'))

            elif ttvdbid != old_tid:
                print(self.config.text('ttvdb', 13, (ttvdbid, new_name), type = 'frontend').encode(self.local_encoding, 'replace'))

            else:
                return(0)

            while True:
                print(self.config.text('ttvdb', 15, type = 'frontend').encode(self.local_encoding, 'replace'))
                ans = raw_input()
                if ans in ('y', 'Y'):
                    tid = data[0]
                    break

                elif ans in ('n', 'N'):
                    return(0)

        else:
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

            except:
                traceback.print_exc()
                return(-1)

        try:
            # Get the English name and those for other languages
            langs = list(set(langs))
            aliasses = [series_name.lower()]
            ename = tid['name']
            for l in langs:
                data = self.query_ttvdb('last_updated', {'ttvdbid': tid['tid'], 'lang': l})
                aname = data_value([0, 'name'], data, str)
                if not aname.lower() in aliasses:
                    aliasses.append(aname.lower())

                if l == 'en'and not aname in (None, ''):
                    ename = aname

            if old_tid != int(tid['tid']):
                print(self.config.text('ttvdb', 7, type = 'frontend').encode(self.local_encoding, 'replace'))
                self.store_data('delete ttvdbid', {'tid': old_tid})

            if len(aliasses) > 0:
                # Add an alias record
                self.store_data('alias', {'tid': int(tid['tid']), 'name': ename, 'alias': aliasses})
                if len(aliasses) == 2:
                    print(self.config.text('ttvdb', 8, (ename, aliasses[0], aliasses[1],  tid['tid']), type = 'frontend').encode(self.local_encoding, 'replace'))

                else:
                    print(self.config.text('ttvdb', 9, (ename, aliasses[0],  tid['tid']), type = 'frontend').encode(self.local_encoding, 'replace'))

            else:
                print(self.config.text('ttvdb', 10, (ename,  tid['tid']), type = 'frontend').encode(self.local_encoding, 'replace'))

        except:
            traceback.print_exc()
            return(-1)

        epdata = self.get_all_episodes(int(tid['tid']), langs, name = ename)
        if epdata['state'] in (0,-1):
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
        self.source_data = source_data
        self.source = self.data_value('name', str)
        Thread.__init__(self, name = 'source-%s'% self.source)
        self.config = config
        self.functions = self.config.fetch_func
        # Flag to stop the thread
        self.quit = False
        self.ready = False
        self.has_started = False
        self.state = 0
        self.active = True
        self.lastrequest = None
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
        self.page_status = dte.dtDataOK

        self.all_channels = {}
        self.channels = {}
        self.chanids = {}
        self.all_chanids = {}
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
        self.print_searchtree = False
        self.show_parsing = False
        self.print_roottree = False
        self.roottree_output = self.test_output
        self.show_result = False
        self.raw_output = self.test_output
        self.data_output = self.test_output
        self.new_cattrans = None
        self.cattrans_type = cattrans_type
        self.detail_keys = []
        self.data = None
        self.rawdata = None

        self.datatrees = {}
        try:
            self.config.sourceid_by_name[self.source] = self.proc_id
            self.language = self.source_data['language']
            self.is_virtual = self.source_data['is_virtual']
            self.detail_processor = self.source_data['detail_processor']
            self.site_tz = self.source_data['site-tz']
            if self.detail_processor:
                if self.proc_id not in self.config.detail_sources:
                    self.detail_processor = False

                self.config.detail_keys[self.proc_id] = {}
                self.detail_processor = False
                if 'detail' in self.source_data["detail_defs"]:
                    self.detail_processor = True
                    self.detail_keys = self.source_data['detail']['provides']
                    self.config.detail_keys[self.proc_id]['detail'] = self.detail_keys
                    for k in self.detail_keys:
                        if k not in self.config.detail_keys['all']:
                            self.config.detail_keys['all'].append(k)

                if 'detail2' in self.source_data["detail_defs"]:
                    self.detail_processor = True
                    self.detail2_keys = self.source_data['detail2']['provides']
                    self.config.detail_keys[self.proc_id]['detail2'] = self.detail2_keys
                    for k in self.detail2_keys:
                        if k not in self.config.detail_keys['all']:
                            self.config.detail_keys['all'].append(k)

            if self.proc_id in self.config.detail_sources and not self.detail_processor:
                self.config.detail_sources.remove(self.proc_id)

        except:
            self.config.validate_option('disable_source', value = self.proc_id)
            traceback.print_exc()

    def run(self):
        """The grabing thread"""
        # First some generic initiation that couldn't be done earlier in __init__
        self.state = 1
        detail_ids = {}
        idle_timeout = 900
        self.lastrequest = None
        if self.detail_processor:
            detail_idx = self.config.detail_sources.index(self.proc_id)

        def check_queue():
            # If the queue is empty
            if self.detail_request.empty():
                time.sleep(random.randint(self.config.opt_dict['nice_time'][0], self.config.opt_dict['nice_time'][1]))
                # if one of the previous detail sources in the order is still alive we wait for potential followup requests
                for ds in range(detail_idx):
                    if self.config.channelsource[self.config.detail_sources[ds]].is_alive():
                        return 0

                # Check if all channels are ready
                for channel in self.config.channels.values():
                    if channel.is_alive() and not channel.ready:
                        return 0

                # All channels are ready, so if there is nothing in the queue
                self.ready = True
                return -1

            self.lastrequest = datetime.datetime.now()
            try:
                if self.quit:
                    return -1

                qval = self.detail_request.get()
                if qval['task'] == 'quit':
                    return -1

                # Is this the closing item for the channel?
                elif qval[ 'task'] == 'last_one':
                    for ds in range(detail_idx + 1, len(self.config.detail_sources)):
                        ds_id = self.config.detail_sources[ds]
                        if self.config.channelsource[ds_id].is_alive():
                            self.config.queues['source'][ds_id].put(qval)
                            break

                    else:
                        qval['parent'].detail_return.put('last_detail')
                        qval['parent'].detail_data.set()

                    return 0

                else:
                    return qval

            except Empty:
                return 0

        try:
            self.init_channel_source_ids()
            self.has_started = True
            # Check if the source is not deactivated and if so set them all loaded
            if not (self.proc_id in self.config.opt_dict['disable_source'] or self.is_virtual):
                # Load and proccess al the program pages
                self.load_pages()

            self.ready = True
            self.set_loaded('channel')
            self.state = 0
            if self.config.write_info_files:
                self.config.infofiles.check_new_channels(self, self.config.source_channels)

        except:
            self.config.queues['log'].put({'fatal': [self.config.text('IO', 14), \
                traceback.format_exc(), '\n'], 'name': self.source})

            self.set_loaded('channel')
            self.state = 0
            self.ready = True
            return(98)

        try:
            if self.detail_processor and  not self.proc_id in self.config.opt_dict['disable_detail_source']:
                # We process detail requests, so we loop till we are finished
                self.state = 4
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
                    #~ if detailed_program == None and 'detail2' in self.source_data["detail_defs"]:
                        #~ try:
                            #~ detailed_program = self.load_detailpage('detail2', detail_ids[self.proc_id], parent)

                        #~ except:
                            #~ detailed_program = None
                            #~ self.config.log([self.config.text('fetch', 24, (detail_ids[self.proc_id]['detail_url'], )), traceback.format_exc()], 1)

                    # It failed! We check for alternative detail sources
                    if detailed_program == None:
                        for ds in range(detail_idx + 1, len(self.config.detail_sources)):
                            ds_id = self.config.detail_sources[ds]
                            if self.config.channelsource[ds_id].is_alive() and ds_id in detail_ids.keys():
                                self.config.queues['source'][ds_id].put(queue_val)
                                self.functions.update_counter('queue', ds_id,  parent.chanid)
                                break

                        else:
                            self.config.log(self.config.text('fetch', 31, (self.source, parent.chan_name, tdict['counter'], logstring), type = 'report'), 8, 1)

                        self.functions.update_counter('queue', self.proc_id,  parent.chanid, False)
                        continue

                    # Success
                    self.config.log(self.config.text('fetch', 32, (self.source, parent.chan_name, tdict['counter'], logstring), type = 'report'), 8, 1)
                    detailed_program['sourceid'] = self.proc_id
                    detailed_program['name'] = detail_ids[self.proc_id]['name']
                    detailed_program['channelid'] = detail_ids[self.proc_id]['channelid']
                    detailed_program['prog_ID'] = detail_ids[self.proc_id]['prog_ID']
                    detailed_program['gen_ID'] = detail_ids[self.proc_id]['gen_ID']
                    parent.detail_return.put({'source': self.proc_id, 'data': detailed_program, 'counter': tdict['counter']})
                    self.functions.update_counter('queue', self.proc_id,  parent.chanid, False)

            self.state = 0
            self.ready = True

        except:
            if self.proc_id in detail_ids.keys() and 'detail_url' in detail_ids[self.proc_id].keys():
                self.config.queues['log'].put({'fatal': [self.config.text('IO', 15, (detail_ids[self.proc_id]['detail_url'])), \
                    traceback.format_exc(), '\n'], 'name': self.source})

            else:
                self.config.queues['log'].put({'fatal': [self.config.text('IO', 16), traceback.format_exc(), '\n'], 'name': self.source})

            self.state = 0
            self.ready = True
            return(98)

    # The fetching functions
    def init_channel_source_ids(self):
        """Get the list of requested channels for this source from the channel configurations"""
        def check_for_channelid(cid, chan = None, is_child = False):
            if chan == None:
                if cid in self.config.channels.keys():
                    chan = self.config.channels[cid]

                else:
                    return

            channelid = chan.get_source_id(self.proc_id)
            if channelid != '':
                self.groupitems[channelid] = 0
                self.program_data[channelid] = []
                # Unless it is in empty channels we add it else set it ready
                if channelid in self.source_data['empty_channels'] or self.proc_id in chan.opt_dict['disable_source']:
                    self.set_loaded('channel', channelid)

                else:
                    if is_child:
                        chan.is_child = True

                    self.channels[cid] = channelid
                    if not channelid in self.all_chanids.keys():
                        self.all_chanids[channelid] = [cid]

                    elif not cid in self.all_chanids[channelid]:
                        self.all_chanids[channelid].append(cid)

        self.current_date = datetime.datetime.now(pytz.utc)
        self.current_sitedate = self.config.in_tz(self.current_date, self.site_tz)
        self.current_fetchdate = self.config.in_fetch_tz(self.current_date)
        self.current_ordinal = self.current_fetchdate.toordinal()
        self.config.queues['cache'].put({
                    'task':'query_id',
                    'parent': self,
                    'sources': {
                        'sourceid': self.proc_id,
                        'name': self.source}})

        self.sourcedbdata = self.get_cache_return()
        if self.source_data['alt-url-code'] != None and self.sourcedbdata['use_alt_url']:
            for ptype in self.config.data_def_names["source"]:
                self.source_data[ptype]['url'] = self.source_data[ptype]['alt-url']

        for chanid, channel in self.config.channels.iteritems():
            # Is the channel active and this source for the channel not disabled
            if channel.active:
                # Is there a channelid for this channel
                check_for_channelid(chanid, channel)
                # Does the channel have child channels
                if chanid in self.config.combined_channels.keys():
                    # Then see if any of the childs has a sourceid for this source and does not have this source disabled
                    for c in self.config.combined_channels[chanid]:
                        check_for_channelid(c['chanid'], is_child = True)

        for channelid, chanidlist in self.all_chanids.items():
            if len(chanidlist) == 1:
                self.chanids[channelid] = chanidlist[0]

            else:
                for chanid in chanidlist:
                    if not self.config.channels[chanid].is_virtual_sub:
                        self.chanids[channelid] = chanid
                        break

                else:
                    self.chanids[channelid] = chanidlist[0]

        # To limit the output to the requested channels
        if "channelid" in self.source_data["base"]["value-filters"].keys() \
          and isinstance(self.source_data["base"]["value-filters"]["channelid"], list):
            self.source_data["base"]["value-filters"]["channelid"].extend(list(self.chanids.keys()))
            self.source_data["base"]["value-filters"]["channelid"].extend(list(self.source_data['alt-channels'].keys()))

    def get_page_data(self, ptype, pdata = None):
        """
        Here for every fetch, the url is gathered, the page retreived and
        together with the data definition inserted in the DataTree module
        The then by the DataTree extracted data is return
        """
        def switch_url():
            for ptype in self.config.data_def_names["source"]:
                if ptype in self.source_data.keys():
                    if self.sourcedbdata['use_alt_url']:
                        self.source_data[ptype]['url'] = self.source_data[ptype]['alt-url']
                        if ptype in self.datatrees.keys():
                            self.datatrees[ptype].data_def['url'] = self.source_data[ptype]['url']

                    else:
                        self.source_data[ptype]['url'] = self.source_data[ptype]['normal-url']
                        if ptype in self.datatrees.keys():
                            self.datatrees[ptype].data_def['url'] = self.source_data[ptype]['url']

        def update_counter(ptype, pstatus = "fail", tekst = None):
            if ptype in self.config.data_def_names["detail"]:
                c = pdata['channel'] if ('channel' in pdata.keys()) else None
                if pstatus == "fetched":
                    self.functions.update_counter('detail', self.proc_id, c)

                elif pstatus == "empty":
                    self.functions.update_counter('empty-detail', self.proc_id, c)

                else:
                    self.functions.update_counter(pstatus, self.proc_id, c)

            elif pstatus == "fetched":
                self.functions.update_counter('base', self.proc_id)

            elif pstatus == "empty":
                self.functions.update_counter('empty-base', self.proc_id)

            else:
                self.functions.update_counter(pstatus, self.proc_id)

            if tekst != None:
                if self.print_roottree:
                    self.roottree_output.write('%s\n' % tekst)

                if self.config.write_info_files:
                    u = url[0]
                    if len(url[3]) > 0:
                        u += '?'
                        for k, v in url[3].items():
                            u += '%s=%s&' % (k, v)

                        u = u[:-1]

                    self.config.infofiles.add_url_failure('%s: %s\n' % (tekst, u))

        self.page_status = dte.dtDataOK
        self.data = None
        incomplete = False
        try:
            if pdata == None:
                pdata = {}

            if not is_data_value(ptype, self.datatrees, DataTreeShell):
                self.datatrees[ptype] = DataTree(self, self.source_data[ptype], 'always', self.proc_id)

            # For the url we use the fetch timezone and date, not the site timezone and page date
            self.datatrees[ptype].set_timezone(self.config.fetch_tz)
            self.datatrees[ptype].set_current_date(self.current_ordinal)
            # Set the counter for the statistics and some other defaults
            if ptype in self.config.data_def_names["channel"]:
                pdata['start'] = 0
                pdata['end'] = 0
                pdata[ 'offset'] = 0
                counter = ['base', self.proc_id, None]

            elif ptype in self.config.data_def_names["detail"]:
                counter = ['detail', self.proc_id, pdata['channel']]

            else:
                counter = ['base', self.proc_id, None]

            url_type = self.source_data[ptype]["url-type"]
            for retry in (0, 1):
                # Get the URL
                url = self.datatrees[ptype].get_url(pdata, False)
                if url == None:
                    self.config.log([self.config.text('fetch', 25, (ptype, self.source))], 1)
                    update_counter(ptype)
                    self.page_status = dte.dtURLerror
                    return

                if self.print_roottree:
                    if self.roottree_output == sys.stdout:
                        self.roottree_output.write(u'pdata = %s' % pdata)
                        prtdata = ('url', 'encoding', 'accept_header', 'url_data', 'is_json')
                        for index in range(len(url)):
                            self.roottree_output.write(('%s = %s'% (prtdata[index], url[index])).encode('utf-8', 'replace'))

                    else:
                        self.roottree_output.write(u'pdata = %s\n' % pdata)
                        prtdata = ('url', 'encoding', 'accept_header', 'url_data', 'is_json')
                        for index in range(len(url)):
                            self.roottree_output.write((u'%s = %s\n'% (prtdata[index], url[index])))

                update_counter(ptype, "fetched")
                # Get the Page
                self.page_status, page, pcode = self.functions.get_page(url)
                # Do an URL swap if needed and try again
                if pcode != None and int(pcode) ==  self.source_data['alt-url-code']:
                    self.config.queues['cache'].put({'task':'update', 'parent': self,
                                                    'toggle_alt_url': {'sourceid': self.proc_id}})
                    self.sourcedbdata['use_alt_url'] = not self.sourcedbdata['use_alt_url']
                    switch_url()

                else:
                    break

            if self.page_status == dte.dtIncompleteRead:
                incomplete = True
                self.page_status = dte.dtDataOK

            if self.page_status == dte.dtEmpty:
                update_counter(ptype, "empty",u'No Data.')
                return

            if self.page_status == dte.dtDataOK:
                # Find the startnode
                if self.datatrees[ptype].init_data(page) or self.datatrees[ptype].searchtree == None:
                    self.config.log([self.config.text('fetch', 26, (ptype, url[0]))], 1)
                    self.page_status = dte.dtDataInvalid

            if self.page_status != dte.dtDataOK:
                if self.page_status in (dte.dtEmpty, dte.dtNoData):
                    update_counter(ptype, "empty",u'No Data.')

                else:
                    if incomplete:
                        self.page_status = dte.dtIncompleteRead

                    update_counter(ptype)
                    if self.print_roottree:
                        self.datatrees[ptype].print_datatree(fobj = self.roottree_output, from_start_node = False)
                        self.roottree_output.write(u'Data Error = %s: %s' % (self.page_status, dte.errortext(self.page_status)))

                return

            if self.print_roottree:
                self.datatrees[ptype].print_datatree(fobj = self.roottree_output, from_start_node = False)

            # We reset the timezone and check if needed on the right date
            self.datatrees[ptype].set_timezone()
            if ptype == 'base':
                # We set the current date
                if (url_type & 12) == 0:
                    cdate = self.current_sitedate.toordinal() + pdata['offset']
                    self.datatrees[ptype].set_current_date(cdate)
                    self.datatrees[ptype].searchtree.set_current_date(cdate)
                    # We check on the right offset
                    if len(self.source_data[ptype]["data"]["today"]) > 0:
                        cd = self.datatrees[ptype].searchtree.find_data_value(\
                            self.source_data[ptype]["data"]["today"], searchname = 'for the current date')
                        if not isinstance(cd, datetime.date):
                            self.config.log([self.config.text('fetch', 27, (url[0], )),])
                            update_counter(ptype)
                            self.page_status = dte.dtWrongDate
                            return

                        elif self.source_data['night-date-switch'] > 0 and \
                          self.current_fetchdate.hour < self.source_data['night-date-switch'] and \
                          (self.current_ordinal - cd.toordinal()) == 1:
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
                            update_counter(ptype)
                            self.page_status = dte.dtWrongDate
                            return

                # We extract the current _item_count and the total_item_count
                if (url_type & 12) == 12:
                    self.total_item_count = self.datatrees[ptype].searchtree.find_data_value(\
                        self.source_data[ptype]['data']["total-item-count"], searchname = 'for the total-item-count')
                    self.current_item_count = self.datatrees[ptype].searchtree.find_data_value(\
                        self.source_data[ptype]['data']["page-item-count"], searchname = 'for the page-item-count')

            # Extract the data
            dtcode = self.datatrees[ptype].extract_datalist()
            self.page_status = dtcode
            if dtcode != dte.dtDataOK:
                if incomplete:
                    self.page_status = dte.dtIncompleteRead
                    update_counter(ptype, tekst = 'Incomplete Read')

                elif dtcode == dte.dtNoData:
                    update_counter(ptype, "empty", 'No DataTree Data')

                else:
                    self.page_status = dte.dtDataInvalid
                    update_counter(ptype, tekst = 'DataTree Error %s' % (dtcode,))

                return

            self.data = self.datatrees[ptype].result[:]
            self.rawdata = self.datatrees[ptype].searchtree.result[:]
            if self.show_result:
                if self.raw_output == sys.stdout:
                    for p in self.rawdata:
                        if isinstance(p[0], (str, unicode)):
                            self.raw_output.write(p[0].encode('utf-8', 'replace'))
                        else:
                            self.raw_output.write(p[0])
                        for v in range(1,len(p)):
                            if isinstance(p[v], (str, unicode)):
                                self.raw_output.write('    "%s"' % p[v].encode('utf-8', 'replace'))
                            else:
                                self.raw_output.write('    %s' % p[v])

                else:
                    for p in self.rawdata:
                        self.raw_output.write(u'%s\n' % p[0])
                        for v in range(1,len(p)):
                            if isinstance(p[v], (str, unicode)):
                                self.raw_output.write(u'    "%s"\n' % p[v])
                            else:
                                self.raw_output.write(u'    %s\n' % p[v])

            # we extract a channel list if available
            if not self.config.test_modus and ptype == 'base' and \
              "base-channels"in self.source_data["base_defs"] and len(self.all_channels) == 0:
                self.datatrees[ptype].init_data_def(self.source_data["base-channels"])
                if not self.datatrees[ptype].extract_datalist():
                    self.get_channels(self.datatrees[ptype].result)

                self.datatrees[ptype].init_data_def(self.source_data["base"])

            if len(self.data) == 0:
                self.data = None
                self.page_status = dte.dtNoData
                update_counter(ptype, "empty", 'No DataTree Data')
                return

            return

        except dtWarning as e:
            self.config.log(self.config.text('fetch', 14, (e.message, ptype, self.source)))
            self.functions.update_counter('fail', self.proc_id)
            self.data = None
            self.page_status = dte.dtDataInvalid
            return

        except:
            self.config.log([self.config.text('fetch', 29, (ptype, self.source)), traceback.format_exc()], 1)
            self.functions.update_counter('fail', self.proc_id)
            self.data = None
            self.page_status = dte.dtUnknownError
            return

    def get_channels(self, data_list = None):
        """The code for the retreiving a list of supported channels"""
        self.all_channels ={}
        self.lineup_changes = []
        if data_list == None:
            if "channels" in self.source_data["channel_defs"]:
                ptype = "channels"

            elif "channel_list" in self.source_data["channel_defs"]:
                # The channels are defined in the datafile
                self.all_channels = self.source_data["channel_list"]
                return

            elif "base-channels" in self.source_data["channel_defs"]:
                ptype = "base-channels"

            else:
                return

            #extract the data
            for retry in (0, 1):
                self.get_page_data(ptype)
                if self.page_status in (dte.dtDataOK, dte.dtURLerror, dte.dtNoData, dte.dtEmpty):
                    channel_list = self.data
                    break

        else:
            # The list is extracted from a base page
            ptype = "base-channels"
            channel_list = data_list

        if isinstance(channel_list, list):
            empty_channels = copy(self.source_data['empty_channels'])
            chanids = {}
            for chanid, channel in self.config.channels.items():
                channelid = channel.get_source_id(self.proc_id)
                if channelid != '':
                    chanids[channelid] = chanid

            channelids = {}
            for chanid, channelid in self.config.source_channels[self.proc_id].items():
                channelids[channelid] = chanid

            for channel in channel_list:
                # link the data to the right variable, doing any defined adjustments
                if "inactive_channel" in channel.keys() and channel["inactive_channel"]:
                    continue

                if "channelid" in channel.keys():
                    channelid = unicode(channel["channelid"])
                    if channelid in self.source_data['alt-channels'].keys():
                        channel['channelid'] = self.source_data['alt-channels'][channelid][0]
                        channel['name'] = self.source_data['alt-channels'][channelid][1]
                        channelid = unicode(channel['channelid'])

                    self.all_channels[channelid] = channel
                    if self.show_result:
                        if self.data_output == sys.stdout:
                            self.data_output.write('%s: %s' % (channelid, channel['name']))
                            if channelid in empty_channels:
                                empty_channels.remove(channelid)
                                if channelid in channelids.keys():
                                    self.data_output.write('        Marked as empty but still present in "sourcechannels" as "%s"' % channelids[channelid])
                                    self.lineup_changes.append('Empty channelID "%s" on %s still present in "sourcechannels" as "%s"\n' \
                                        % (channelid, self.source, channelids[channelid]))

                                else:
                                    self.data_output.write('        Marked as empty')

                            elif channelid in chanids.keys():
                                self.data_output.write('        chanid: %s' % (chanids[channelid]))
                                del chanids[channelid]

                            else:
                                self.data_output.write('        Without a chanid set in "source_channels"')

                            for k, v in channel.items():
                                if isinstance(v, (str, unicode)):
                                    self.data_output.write('        %s: "%s"'.encode('utf-8', 'replace') % (k, v))
                                else:
                                    self.data_output.write('        %s: %s' % (k, v))

                        else:
                            self.data_output.write('%s: %s\n' % (channelid, channel['name']))
                            if channelid in empty_channels:
                                empty_channels.remove(channelid)
                                if channelid in channelids.keys():
                                    self.data_output.write('        Marked as empty but still present in "sourcechannels" as "%s"\n' % channelids[channelid])
                                    self.lineup_changes.append('Empty channelID "%s" on %s still present in "sourcechannels" as "%s"\n' \
                                        % (channelid, self.source, channelids[channelid]))

                                else:
                                    self.data_output.write('        Marked as empty\n')

                            elif channelid in chanids.keys():
                                self.data_output.write('        chanid: %s\n' % (chanids[channelid]))
                                del chanids[channelid]

                            else:
                                self.data_output.write('        Without a chanid set in "source_channels"\n')

                            for k, v in channel.items():
                                if isinstance(v, (str, unicode)):
                                    self.data_output.write('        %s: "%s"\n' % (k, v))
                                else:
                                    self.data_output.write('        %s: %s\n' % (k, v))

                    elif self.config.write_info_files:
                        if channelid in self.source_data['empty_channels'] and channelid in channelids.keys():
                            self.lineup_changes.append('Empty channelID "%s" on %s still present in "sourcechannels" as "%s"\n' \
                                % (channelid, self.source, channelids[channelid]))

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
                    (self.config.channels[chanid].get_opt('compat') and self.config.compat_text or ''), self.source), type = 'report')]

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
                    log_array.append(self.config.text('fetch', 9, (self.config.opt_dict['days'],), type = 'report'))

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

        def do_final_processing(channelid):
            chanid = self.chanids[channelid]
            if not chanid in self.config.channelprogram_rename.keys():
                self.config.channelprogram_rename[chanid] = {}

            good_programs = []
            pgaps = []
            # Some sanity Check
            if len(self.program_data[channelid]) > 0:
                self.program_data[channelid].sort(key=lambda program: (program['start-time']))
                plen = len(self.program_data[channelid])
                last_stop = None
                min_gap = datetime.timedelta(minutes = 30)
                for index in range(plen):
                    p = self.program_data[channelid][index]
                    if not 'name' in p.keys() or not isinstance(p['name'], (unicode, str)) or p['name'] == u'':
                        continue

                    p['name'] = unicode(p['name'])
                    pname = p['name'].lower().strip()
                    if pname in self.config.channelprogram_rename[chanid].keys():
                        p['name'] = self.config.channelprogram_rename[chanid][pname]

                    if index < plen - 1:
                        p2 = self.program_data[channelid][index + 1]
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
            cache_programs = self.get_cache_return()
            if cache_programs == -1:
                return -1

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
                        if cached[channelid][day] and not self.get_loaded('day', channelid, day):
                            self.config.log(self.config.text('fetch', 12,  (day, self.config.channels[chanid].chan_name, self.source), type = 'report'), 2)

                    for p in cache_programs:
                        p['source'] = self.source
                        p['chanid'] = chanid
                        p['channelid'] = channelid
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
                            self.groupitems[channelid] += 1

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
                    if self.get_loaded('day', channelid, day):
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
                    p['channelid'] = channelid
                    p['channel']  = self.config.channels[chanid].chan_name
                    p['length'] = p['stop-time'] - p['start-time']
                    p['from cache'] = True
                    if 'group' in p.keys() and not p['group'] in (None, ''):
                        self.groupitems[channelid] += 1

                    good_programs.append(p)

            # Add any repeat group
            if len(good_programs) > 0:
                good_programs.sort(key=lambda program: (program['start-time']))
                if self.groupitems[channelid] > 0:
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
                                    gdict['start-time'] += repeat*group_duur
                                    if gdict['start-time'] < group_eind:
                                        gdict['stop-time'] += repeat*group_duur
                                        if gdict['stop-time'] > group_eind:
                                            gdict['stop-time'] = group_eind

                                        gdict['length'] = gdict['stop-time'] - gdict['start-time']
                                        gdict['offset'] = self.functions.get_offset(gdict['start-time'])
                                        gdict['scandate'] = self.functions.get_fetchdate(gdict['start-time'])
                                        gdict['prog_ID'] = ''
                                        gdict['rerun'] = True
                                        good_programs.append(gdict)

                                    else:
                                        break

                                else:
                                    continue

                                break

            # And keep only the requested range
            self.program_data[channelid] = []
            for p in good_programs[:]:
                if p['offset'] in full_range:
                    self.program_data[channelid].append(p)

            self.set_loaded('channel', channelid)
            self.set_loaded('day', channelid)
        # end do_final_processing()

        if len(self.channels) == 0  or not "base" in self.source_data["base_defs"]:
            return

        tdd = datetime.timedelta(days=1)
        cached = {}
        laststop = {}
        first_day = self.config.opt_dict['offset']
        last_day = first_day + self.config.opt_dict['days']
        max_days = self.source_data["base"]["max days"]
        if first_day > max_days:
            self.set_loaded('channel')
            return

        full_range = range( first_day, last_day)
        site_range = range( first_day, min(max_days, last_day))
        step_start = first_day
        offset_step = 1
        fetch_range = site_range
        for channelid, chanid in self.chanids.items():
            self.program_data[channelid] = []
            self.config.queues['cache'].put({'task':'query', 'parent': self, 'fetcheddays': {'sourceid': self.proc_id, 'channelid': channelid, 'scandate': list(full_range)}})
            cached[channelid] = self.get_cache_return()
            if cached[channelid] == -1:
                return -1

            self.config.queues['cache'].put({'task':'query', 'parent': self, 'laststop': {'sourceid': self.proc_id, 'channelid': channelid}})
            ls = self.get_cache_return()
            if ls == -1:
                return -1

            laststop[channelid] = ls['laststop']  if isinstance(ls, dict) and isinstance(ls['laststop'], datetime.datetime) else None

        url_type = self.source_data["base"]["url-type"]
        # Check which groups contain requested channels
        if (url_type & 3) == 3:
            changroups = self.source_data["base"][ "url-channel-groups"]
            fgroup = {}
            for channelgrp in changroups:
                self.config.queues['cache'].put({'task':'query', 'parent': self, 'chan_scid': {'sourceid': self.proc_id, 'fgroup': channelgrp}})
                fgroup[channelgrp] = self.get_cache_return()
                if fgroup[channelgrp] == -1:
                    return -1

                for chan in fgroup[channelgrp][:]:
                    if not chan['channelid'] in self.chanids.keys():
                        fgroup[channelgrp].remove(chan)

        # Check which days and up to what date are available in the cache
        for channelid, chanid in self.chanids.items():
            self.program_data[channelid] = []
            self.config.queues['cache'].put({'task':'query', 'parent': self, 'fetcheddays': {'sourceid': self.proc_id, 'channelid': channelid, 'scandate': list(full_range)}})
            cached[channelid] = self.get_cache_return()
            if cached[channelid] == -1:
                return

            self.config.queues['cache'].put({'task':'query', 'parent': self, 'laststop': {'sourceid': self.proc_id, 'channelid': channelid}})
            ls = self.get_cache_return()
            if ls == -1:
                return -1

            laststop[channelid] = ls['laststop']  if isinstance(ls, dict) and isinstance(ls['laststop'], datetime.datetime) else None

        max_fetch_days = 6
        max_failure_count = 4
        # Just process the days retrieved from the cache
        if self.config.args.only_cache:
            for channelid, chanid in self.chanids.items():
                if do_final_processing(channelid) == -1:
                    return -1

            return

        # We fetch every day separate
        elif (url_type & 12) == 0:
            # vrt.be, tvgids.tv
            if (url_type & 3) == 1:
                fetch_range = {}
                for channelid, chanid in self.chanids.items():
                    fetch_range[channelid] = []
                    for day in site_range:
                        if day == 0 or cached[channelid][day] != True:
                            fetch_range[channelid].append(day)
                            if len(fetch_range[channelid]) == max_fetch_days:
                                break

            # tvgids.nl, vpro.nl, primo.eu, oorboekje.nl
            elif (url_type & 3) == 2:
                fetch_range = []
                for day in site_range:
                    for channelid, chanid in self.chanids.items():
                        if day == 0 or cached[channelid][day] != True:
                            fetch_range.append(day)
                            break

                    if len(fetch_range) == max_fetch_days:
                        break

            #humo.be, npo.nl
            elif (url_type & 3) == 3:
                fetch_range = {}
                for channelgrp in changroups:
                    fetch_range[channelgrp] = []
                    for day in site_range:
                        for chan in fgroup[channelgrp]:
                            if day == 0 or cached[chan['channelid']][day] != True:
                                fetch_range[channelgrp].append(day)
                                break

                        if len(fetch_range[channelgrp]) == max_fetch_days:
                            break

        # We fetch all days in one
        elif (url_type & 12) == 4:
            if (url_type & 3) == 1:
                fetch_range = {}
                for channelid, chanid in self.chanids.items():
                    fetch_range[channelid] = ['all']

            # rtl.nl
            elif (url_type & 3) == 2:
                fetch_range = ['all']

            elif (url_type & 3) == 3:
                # ToDo
                return

        # We fetch a set number of  days in one
        elif (url_type & 12) == 8:
            if self.source_data["base"]["url-date-range"] == 'week':
                sow = self.source_data["base"]["url-date-week-start"]
                offset_step = 7
                step_start = get_weekstart(self.current_ordinal, first_day, sow)
                if (url_type & 3) == 1:
                    fetch_range = {}
                    for channelid, chanid in self.chanids.items():
                        fetch_range[channelid] = []
                        for daygroup in range(step_start, last_day, offset_step):
                            for day in site_range:
                                if day in site_range and (day == 0 or cached[channelid][day] != True):
                                    fetch_range[channelid].append(daygroup)
                                    break

                elif (url_type & 3) == 2:
                    fetch_range = []
                    for daygroup in range(step_start, last_day, offset_step):
                        for day in site_range:
                            for channelid, chanid in self.chanids.items():
                                if day in site_range and (day == 0 or cached[channelid][day] != True):
                                    fetch_range.append(daygroup)
                                    break

                            else:
                                continue

                            break

                elif (url_type & 3) == 3:
                    # ToDo
                    return

            elif isinstance(self.source_data["base"]["url-date-range"], int):
                offset_step = self.source_data["base"]["url-date-range"]
                # nieuwsblad.be
                if (url_type & 3) == 1:
                    fetch_range = {}
                    for channelid, chanid in self.chanids.items():
                        fetch_range[channelid] = []
                        start = None
                        for day in site_range:
                            if day == 0 or cached[channelid][day] != True:
                                if start == None or day > start + offset_step:
                                    fetch_range[channelid].append(day)
                                    start = day

                elif (url_type & 3) == 2:
                    fetch_range = []
                    start = None
                    for day in site_range:
                        for channelid, chanid in self.chanids.items():
                            if day == 0 or cached[channelid][day] != True:
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
            self.item_count = self.source_data['base']['default-item-count']
            if (url_type & 3) == 1:
                fetch_range = {}
                for channelid, chanid in self.chanids.items():
                    fetch_range[channelid] = []
                    start = None
                    days = 0
                    for day in site_range:
                        if day == 0 or cached[channelid][day] != True:
                            days += 1
                            if start == None:
                                start = day

                        elif start != None:
                            fetch_range[channelid].append((start, days))
                            start = None
                            days = 0

                    if start != None:
                        fetch_range[channelid].append((start, days))

            elif (url_type & 3) == 2:
                fetch_range = []
                start = None
                days = 0
                for day in site_range:
                    for channelid, chanid in self.chanids.items():
                        if day == 0 or cached[channelid][day] != True:
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
                maxoffset = {}
                for retry in (0, 1):
                    channel_cnt = 0
                    for channelid, chanid in self.chanids.items():
                        channel_cnt += 1
                        failure_count = 0
                        empty_count = 0
                        fetch_count = 0
                        if not channelid in maxoffset.keys():
                            maxoffset[channelid] = None

                        if self.quit:
                            return

                        if self.get_loaded('channel', channelid):
                            continue

                        if (url_type & 12) == 12:
                            if self.item_count == 0:
                                return

                            base_count = 0
                            for fset in fetch_range[channelid]:
                                if fset == maxoffset[channelid]:
                                    self.config.log(self.config.text('fetch', 39, (self.source, self.config.channels[chanid].chan_descr)))
                                    break

                                self.current_item_count = self.item_count
                                page_count = 0
                                while self.current_item_count == self.item_count:
                                    if self.quit:
                                        return

                                    # Check if it is already loaded
                                    if self.get_loaded('page', channelid, base_count):
                                        page_count += 1
                                        base_count += 1
                                        fetch_count += 1
                                        continue

                                    log_fetch()
                                    if not first_fetch:
                                        # be nice to the source
                                        time.sleep(random.randint(self.config.opt_dict['nice_time'][0], self.config.opt_dict['nice_time'][1]))

                                    first_fetch = False
                                    self.get_page_data('base',{'channel': channelid,
                                                                'cnt-offset': page_count,
                                                                'start': fset[0],
                                                                'end': fset[0] + fset[1],
                                                                'back':-fset[0],
                                                                'ahead': fset[0] +fset[1]-1})

                                    if self.page_status == dte.dtDataOK:
                                        strdata = self.data

                                    elif self.page_status == dte.dtNoData:
                                        # We asume this is the last day with data
                                        maxoffset[channelid] = fset
                                        self.config.log(self.config.text('fetch', 39, (self.source, self.config.channels[chanid].chan_descr)))
                                        break

                                    else:
                                        if retry == 1:
                                            log_fail()

                                        failure_count += 1
                                        base_count += 1
                                        page_count += 1
                                        fetch_count += 1
                                        if failure_count > max_failure_count:
                                            break

                                        continue

                                    self.parse_basepage(strdata, {'url_type':url_type, 'channelid': channelid})
                                    self.set_loaded('page', channelid, base_count)
                                    page_count += 1
                                    base_count += 1
                                    fetch_count += 1

                                self.set_loaded('day', channelid, range(fset[0], fset[0] + fset[1]))

                        else:
                            page_idx = 0
                            for offset in fetch_range[channelid]:
                                if offset == maxoffset[channelid]:
                                    self.config.log(self.config.text('fetch', 39, (self.source, self.config.channels[chanid].chan_descr)))
                                    break

                                page_idx += 1
                                # Check if it is already loaded
                                if (url_type & 12) == 8:
                                    if self.get_loaded('page', channelid, offset):
                                        continue

                                else:
                                    if self.get_loaded('day', channelid, offset):
                                        continue

                                if not first_fetch:
                                    # be nice to the source
                                    time.sleep(random.randint(self.config.opt_dict['nice_time'][0], self.config.opt_dict['nice_time'][1]))

                                first_fetch = False
                                log_fetch()
                                self.get_page_data('base',{'channel': channelid,
                                                            'offset': offset,
                                                            'start': first_day,
                                                            'end': min(max_days, last_day),
                                                            'back':-first_day,
                                                            'ahead':min(max_days, last_day)-1})
                                if self.page_status == dte.dtDataOK:
                                    strdata = self.data

                                elif self.page_status == dte.dtNoData:
                                    # We asume this is the last page with data
                                    maxoffset[channelid] = offset
                                    self.config.log(self.config.text('fetch', 39, (self.source, self.config.channels[chanid].chan_descr)))
                                    break

                                else:
                                    if retry == 1:
                                        log_fail()

                                    failure_count += 1
                                    continue

                                self.parse_basepage(strdata, {'url_type':url_type, 'offset': offset, 'channelid': channelid})
                                if (url_type & 12) == 0:
                                    self.set_loaded('day', channelid, offset)

                                elif (url_type & 12) == 4:
                                    self.set_loaded('day', channelid)

                                elif (url_type & 12) == 8:
                                    self.set_loaded('day', channelid, range(offset, offset + offset_step))
                                    self.set_loaded('page', channelid, offset)


                        if failure_count == 0 or retry == 1:
                            if do_final_processing(channelid) == -1:
                                return -1

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
                            self.get_page_data('base',{'channels': self.chanids.keys(),
                                                        'offset': offset,
                                                        'start': first_day,
                                                        'end': min(max_days, last_day),
                                                        'back':-first_day,
                                                        'ahead':min(max_days, last_day)-1})
                            if self.page_status == dte.dtDataOK:
                                strdata = self.data

                            else:
                                if retry == 1:
                                    log_fail()

                                failure_count += 1
                                continue

                            self.set_loaded('day', 0, offset)
                            self.parse_basepage(strdata, {'url_type':url_type, 'offset':offset})

                    if failure_count == 0 or retry == 1:
                        for channelid, chanid in self.chanids.items():
                            if do_final_processing(channelid) == -1:
                                return -1

                        break

            # We fetch the channels in two or more groups
            if (url_type & 3) == 3:
                for retry in (0, 1):
                    for channelgrp in self.source_data["base"]["url-channel-groups"]:
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
                                    if not self.get_loaded('day', chan['channelid'], offset):
                                        break

                                else:
                                    continue

                                if not first_fetch:
                                    # be nice to the source
                                    time.sleep(random.randint(self.config.opt_dict['nice_time'][0], self.config.opt_dict['nice_time'][1]))

                                first_fetch = False
                                log_fetch()
                                self.get_page_data('base',{'channelgrp': channelgrp,
                                                            'offset': offset,
                                                            'start': first_day,
                                                            'end': min(max_days, last_day),
                                                            'back':-first_day,
                                                            'ahead':min(max_days, last_day)-1})
                                if self.page_status == dte.dtDataOK:
                                    strdata = self.data

                                else:
                                    if retry == 1:
                                        log_fail()

                                    failure_count += 1
                                    continue

                                channelids = self.parse_basepage(strdata, {'url_type':url_type, 'channelgrp': channelgrp, 'offset':offset})
                                if isinstance(channelids, list):
                                    self.set_loaded('day', channelids, offset)

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
                        for channelid, chanid in self.chanids.items():
                            if do_final_processing(channelid) == -1:
                                return -1

                        break

        except:
            self.config.log([self.config.text('fetch', 31, (self.source,)), self.config.text('fetch', 32), traceback.format_exc()], 0)
            self.set_loaded('channel')
            return None

    def parse_basepage(self, fdata, subset = {}):
        """Process the data retreived from DataTree for the base pages"""
        channelids = []
        last_start = {}
        tdd = datetime.timedelta(days=1)
        tdh = datetime.timedelta(hours=1)
        if isinstance(fdata, list):
            last_stop = None
            for program in fdata:
                if 'channelid' in program.keys():
                    channelid = unicode(program['channelid'])
                    if channelid in self.source_data['alt-channels'].keys():
                        program['channelid'] = self.source_data['alt-channels'][channelid][0]
                        channelid = unicode(program['channelid'])

                elif 'channelid' in subset.keys():
                    channelid = subset['channelid']

                else:
                    continue

                # it's not requested
                if not channelid in self.chanids.keys():
                    continue

                # A list of processed channels to send back
                if not channelid in channelids:
                    channelids.append(channelid)

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
                    #~ self.config.log(self.config.text('fetch', 33, (program['prog_ID'], self.config.channels[chanid].chan_descr, self.source)))
                    #~ continue

                if 'stop-time' in program.keys() and isinstance(program['stop-time'], datetime.datetime):
                    tdict['stop-time'] = program['stop-time']
                elif "alt-stop-time" in program and isinstance(program["alt-stop-time"], datetime.datetime):
                    tdict['stop-time'] = program["alt-stop-time"]

                plength = None
                if "length" in program and isinstance(program['length'], datetime.timedelta):
                    plength = program["length"]
                    tdict["length"] = plength

                if 'start-time' in program.keys() and isinstance(program['start-time'], datetime.datetime):
                    tdict['start-time'] = program['start-time']
                elif "alt-start-time" in program and isinstance(program["alt-start-time"], datetime.datetime):
                    tdict['start-time'] = program["alt-start-time"]
                elif plength != None and 'stop-time' in tdict.keys():
                    tdict['start-time'] = tdict['stop-time'] - plength
                    tdict['start from length'] = True
                elif self.source_data["base"]["data-format"] == "text/html" and isinstance(last_stop, datetime.datetime):
                    tdict['start-time'] = last_stop
                else:
                    # Unable to determin a Start Time
                    self.config.log(self.config.text('fetch', 34, (program['name'], tdict['channel'], self.source)))
                    continue

                if plength != None:
                    if not 'stop-time' in tdict.keys():
                        tdict['stop-time'] = tdict['start-time'] + plength
                        tdict['stop from length'] = True

                    else:
                        alength = tdict['stop-time'] - tdict['start-time']

                if self.source_data['without-full-timings'] and self.source_data["base"]["data-format"] == "text/html":
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
                if self.source_data["base"]["data-format"] == "text/html":
                    if 'stop-time' in tdict.keys():
                        last_stop = tdict['stop-time']
                    else:
                        last_stop = None

                # Add any known value that does not need further processing
                for k, v in self.process_values(program).items():
                    if k in ('channelid', 'video', 'start-time', 'stop-time', 'length'):
                        continue

                    tdict[k] = v

                if 'group' in program.keys() and not program['group'] in (None, ''):
                    self.groupitems[channelid] += 1
                    tdict['group'] = program['group']

                with self.source_lock:
                    self.program_data[channelid].append(tdict)

                #~ self.config.genre_list.append((tdict['genre'].lower(), tdict['subgenre'].lower()))

                if self.show_result:
                    self.print_result(tdict, channelid)

            if len(channelids) > 0:
                for channelid in channelids:
                    if len(self.program_data[channelid]) > 0:
                        self.program_data[channelid][-1]['last of the page'] = True

        return channelids

    def load_detailpage(self, ptype, pdata, parent = None):
        """The code for retreiving and processing a detail page"""
        if pdata['detail_url'] in (None, ''):
            return

        ddata = {'channel': pdata['chanid'], 'detailid': pdata['detail_url']}
        self.get_page_data(ptype, ddata)
        if self.page_status == dte.dtDataOK:
            strdata = self.data

        else:
            self.config.log(self.config.text('fetch', 35, (pdata['detail_url'], )), 1)
            return

        values = strdata[0]
        if not isinstance(values, dict):
            return

        if not 'genre' in values.keys() and 'org-genre' in pdata.keys():
            values['genre'] = pdata['org-genre']

        if not 'subgenre' in values.keys() and 'org-subgenre' in pdata.keys():
            values['subgenre'] = pdata['org-subgenre']

        tdict = self.process_values(values)
        if self.show_result:
            self.print_result(tdict, pdata['channelid'])

        return tdict

    # Helper functions
    def print_result(self, tdict, channelid):
        start = self.config.in_output_tz(tdict['start-time']).strftime('%d %b %H:%M')
        if self.data_output == sys.stdout:
            self.data_output.write('%s: %s' % (channelid, start))
            for k, v in tdict.items():
                if isinstance(v, (str, unicode)):
                    self.data_output.write('        %s: "%s"'.encode('utf-8', 'replace') % (k, v))
                else:
                    self.data_output.write('        %s: %s' % (k, v))

        else:
            self.data_output.write('%s: %s\n' % (channelid, start))
            for k, v in tdict.items():
                if isinstance(v, (str, unicode)):
                    self.data_output.write('        %s: "%s"\n' % (k, v))

                elif isinstance(v, list):
                    vv = '        %s: ' % (k, )
                    for item in v:
                        if isinstance(item, (str, unicode)):
                            vv = '%s"%s"\n                ' % (vv, item)

                        elif k == 'actor' and isinstance(item, dict):
                            vv = '%s%s: "%s"\n                ' % (vv, item['role'], item['name'])

                        else:
                            vv = '%s%s\n                ' % (vv, item)

                    self.data_output.write(vv.rstrip(' '))

                else:
                    self.data_output.write('        %s: %s\n' % (k, v))

    def get_cache_return(self):
        if self.quit:
            return -1

        self.state += 8
        cr = self.cache_return.get(True)
        self.state -= 8
        if cr == 'quit':
            self.quit = True
            return -1

        else:
            return cr

    def is_data_value(self, searchpath, dtype = None, empty_is_false = True):
        return is_data_value(searchpath, self.source_data, dtype, empty_is_false)

    def data_value(self, searchpath, dtype = None, default = None):
        return data_value(searchpath, self.source_data, dtype, default)

    def get_loaded(self, type='day', channelid = 0, day = None):
        chanlist = list(self.chanids.keys())
        chanlist.append(0)
        if type == 'day':
            if channelid in self.day_loaded.keys():
                if day in self.day_loaded[channelid].keys():
                    return self.day_loaded[channelid][day]

                elif day == 'all' and self.config.opt_dict['offset'] in self.day_loaded[channelid].keys():
                    return self.day_loaded[channelid][self.config.opt_dict['offset']]

            return False

        if type == 'channel':
            if channelid in self.channel_loaded.keys():
                return self.channel_loaded[channelid]

            return False

        if type == 'page':
            if channelid in self.page_loaded.keys() and day in self.page_loaded[channelid].keys():
                return self.page_loaded[channelid][day]

            return False

    def set_loaded(self, type='day', channelid = None, day = None, value=True):
        chanlist = list(self.chanids.keys())
        chanlist.append(0)
        daylist = range( self.config.opt_dict['offset'], (self.config.opt_dict['offset'] + self.config.opt_dict['days']))
        if isinstance(channelid, (list, tuple)):
            chanlist = channelid

        elif channelid not in (None, 'all', 0):
            chanlist = [channelid]

        if type == 'day':
            if isinstance(day, (list, tuple)):
                daylist = day

            elif day not in (None, 'all'):
                daylist = [day]

            for channelid in chanlist:
                if not channelid in self.day_loaded.keys():
                    self.day_loaded[channelid] = {}

                for day in daylist:
                    self.day_loaded[channelid][day] = value

        if type == 'channel':
            for channelid in chanlist:
                self.channel_loaded[channelid] = value
                if value and channelid in self.all_chanids.keys():
                    for chanid in self.all_chanids[channelid]:
                        self.config.channels[chanid].source_ready(self.proc_id).set()

        if type == 'page':
            if isinstance(day, (list, tuple)):
                pagelist = day

            elif isinstance(day, int):
                pagelist = [day]

            else:
                return

            for channelid in chanlist:
                if channelid in chanlist:
                    if not channelid in self.page_loaded.keys():
                        self.page_loaded[channelid] = {}

                    for day in pagelist:
                        self.page_loaded[channelid][day] = value

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

                else:
                    gg = ['']

                gs0 =gg[0].strip()
                gs1 = u''
                gg0 = gs0.lower()
                if len(gg) > 1:
                    gs1 = gg[1].strip()

                elif 'subgenre' in values and values['subgenre'] not in (None, ''):
                    gs1 = values['subgenre'].strip()

                gg1 = gs1.lower()
                if gg0 in self.source_data['cattrans'].keys():
                    if gg1 in self.source_data['cattrans'][gg0].keys():
                        genre = self.source_data['cattrans'][gg0][gg1][0].strip()
                        subgenre = self.source_data['cattrans'][gg0][gg1][1].strip()

                    elif gg1 not in (None, ''):
                        genre = self.source_data['cattrans'][gg0]['default'][0].strip()
                        subgenre = gs1
                        self.new_cattrans[(gg0, gg1)] = (self.source_data['cattrans'][gg0]['default'][0].strip().lower(), gg1)

                    else:
                        genre = self.source_data['cattrans'][gg0]['default'][0].strip()
                        subgenre = self.source_data['cattrans'][gg0]['default'][1].strip()
                        self.new_cattrans[(gg0,gg1)] = (self.source_data['cattrans'][gg0]['default'][0].strip().lower(),
                                                                             self.source_data['cattrans'][gg0]['default'][1].strip().lower())

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
                if values['subgenre'].lower().strip() in self.source_data['cattrans'].keys():
                    genre = self.source_data['cattrans'][values['subgenre'].lower().strip()]
                    subgenre = values['subgenre'].strip()

                else:
                    for k, v in self.source_data['cattrans_keywords'].items():
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
            if is_data_value('genre', values, str, True):
                genre = values['genre'].strip()

            if is_data_value('subgenre', values, str, True):
                subgenre = values['subgenre'].strip()

        return (genre, subgenre, genre, subgenre)

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

