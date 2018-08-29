#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Python 3 compatibility
from __future__ import unicode_literals
# from __future__ import print_function

import codecs, locale, re, os, sys, io, shutil, difflib
import traceback, smtplib, sqlite3, argparse, pickle
import datetime, time, calendar, pytz
import tv_grab_channel, tv_grab_config, test_json_struct
from threading import Thread, Lock, RLock
from threading import enumerate as enumthreads
from Queue import Queue, Empty
from copy import deepcopy, copy
from email.mime.text import MIMEText
from xml.sax import saxutils
from DataTreeGrab import *


class Functions():
    """Some general IO functions"""

    def __init__(self, config):
        self.default_file_encoding = 'utf-8'
        self.encoding = None
        self.configversion = None
        self.config = config
        self.logging = config.logging

    # end init()

    def log(self, message, log_level = 1, log_target = 3):
        if self.logging == None:
            return

        # If logging not (jet) available, make sure important messages go to the screen
        if (self.logging.log_output == None) and (log_level < 2) and (log_target & 1):
            if isinstance(message, (str, unicode)):
                sys.stderr.write(message.encode(self.logging.local_encoding, 'replace'))

            elif isinstance(message, (list ,tuple)):
                for m in message:
                    sys.stderr.write(m.encode(self.logging.local_encoding, 'replace'))

            if log_target & 2:
                self.logging.log_queue.put([message, log_level, 2])

        else:
            self.logging.log_queue.put([message, log_level, log_target])

    # end log()

    def remove_file(self, fle):
        if os.path.isfile(fle) and os.access(fle, os.W_OK):
            try:
                os.remove(fle)

            except:
                pass

    # end remove_file()

    def save_oldfile(self, fle, save_ext='old'):
        """ save the old file to .old if it exists """
        save_fle = '%s.%s' % (fle, save_ext)
        if os.path.isfile(save_fle):
            os.remove(save_fle)

        if os.path.isfile(fle):
            os.rename(fle, save_fle)

    # end save_oldfile()

    def restore_oldfile(self, fle, save_ext='old'):
        """ restore the old file from .old if it exists """
        save_fle = '%s.%s' % (fle, save_ext)
        if os.path.isfile(fle):
            os.remove(fle)

        if os.path.isfile(save_fle):
            os.rename(save_fle, fle)

    # end save_oldfile()

    def open_file(self, file_name, mode = 'rb', encoding = None):
        """ Open a file and return a file handler if success """
        if encoding == None:
            encoding = self.default_file_encoding

        if 'r' in mode and not (os.path.isfile(file_name) and os.access(file_name, os.R_OK)):
            self.log(self.config.text('IO', 1, (file_name, )))
            return None

        if ('a' in mode or 'w' in mode):
            if os.path.isfile(file_name) and not os.access(file_name, os.W_OK):
                self.log(self.config.text('IO', 1, (file_name, )))
                return None

        try:
            if 'b' in mode:
                file_handler =  io.open(file_name, mode = mode)
            elif encoding == 'pickle':
                file_handler =  open(file_name, mode = mode)
            else:
                file_handler =  io.open(file_name, mode = mode, encoding = encoding)

        except IOError as e:
            if e.errno == 2:
                self.log(self.config.text('IO', 1, (file_name, )))
            else:
                self.log('File: "%s": %s.\n' % (file_name, e.strerror))
            return None

        return file_handler

    # end open_file ()

    def read_pickle(self, file_name):
        fle = self.open_file(file_name, 'r', 'pickle')
        if fle != None:
            data = pickle.load(fle)
            fle.close()
            return data

        else:
            return None

    # end read_pickle()

    def get_line(self, fle, byteline, isremark = False, encoding = None):
        """
        Check line encoding and if valid return the line
        If isremark is True or False only remarks or non-remarks are returned.
        If None all are returned
        """
        if encoding == None:
            encoding = self.default_file_encoding

        try:
            line = byteline.decode(encoding)
            line = line.lstrip()
            line = line.replace('\n','')
            if isremark == None:
                return line

            if len(line) == 0:
                return False

            if isremark and line[0:1] == '#':
                return line

            if not isremark and not line[0:1] == '#':
                return line

        except UnicodeError:
            self.log(self.config.text('IO', 2, (fle.name, encoding)))

        return False

    # end get_line()

    def check_encoding(self, fle, encoding = None, check_version = False):
        """
        Check file encoding. Return True or False
        Encoding is stored in self.encoding
        Optionally check for a version string
        and store it in self.configversion
        """
        # regex to get the encoding string
        reconfigline = re.compile(r'#\s*(\w+):\s*(.+)')

        self.encoding = None
        self.configversion = None

        if encoding == None:
            encoding = self.default_file_encoding

        for byteline in fle.readlines():
            line = self.get_line(fle, byteline, True, self.encoding)
            if not line:
                continue

            else:
                match = reconfigline.match(line)
                if match is not None and match.group(1) == "encoding":
                    encoding = match.group(2)

                    try:
                        codecs.getencoder(encoding)
                        self.encoding = encoding

                    except LookupError:
                        self.log(self.config.text('IO', 3, (fle.name, encoding)))
                        return False

                    if (not check_version) or self.configversion != None:
                        return True

                    continue

                elif match is not None and match.group(1) == "configversion":
                    self.configversion = float(match.group(2))
                    if self.encoding != None:
                        return True

                continue

        if check_version and self.configversion == None:
            fle.seek(0,0)
            for byteline in fle.readlines():
                line = self.get_line(fle, byteline, False, self.encoding)
                if not line:
                    continue

                else:
                    config_title = re.search('[(.*?)]', line)
                    if config_title != None:
                        self.configversion = float(2.0)
                        break

            else:
                self.configversion = float(1.0)

        if self.encoding == None:
            return False

        else:
            return True

    # end check_encoding()


# end Functions()

class Logging(Thread):
    """
    The tread that manages all logging.
    You put the messages in a queue that is sampled.
    So logging can start after the queue is opend when this class is called
    Before the fle to log to is known
    """
    def __init__(self, config):
        Thread.__init__(self, name = 'logging')
        self.quit = False
        self.config = config
        self.functions = Functions(config)
        self.log_queue = Queue()
        self.log_output = None
        self.log_string = []
        self.all_at_details = False
        self.check_threads = False
        self.print_live_threads = False
        self.log_thread_checks = False
        try:
            codecs.lookup(locale.getpreferredencoding())
            self.local_encoding = locale.getpreferredencoding()

        except LookupError:
            if os.name == 'nt':
                self.local_encoding = 'windows-1252'

            else:
                self.local_encoding = 'utf-8'

    # end init()

    def run(self):
        def close_all_threads():
            self.quit = True
            dbthread = None
            # Send the threads a quit signal
            self.writelog(self.config.text('IO', 2, type = 'other'))
            for t in enumthreads():
                try:
                    if t.is_alive() and t.thread_type == 'channel':
                        if t.state in (1, 2, 3):
                            t.quit = True

                        t.detail_return.put('quit')

                    if t.is_alive() and t.thread_type in ('lookup', 'source'):
                        t.detail_request.put({'task': 'quit'})

                    if t.is_alive() and t.thread_type == 'cache':
                        dbthread = t
                        t.cache_request.put({'task': 'quit'})

                except:
                    continue

            if dbthread != None:
                dbthread.join()

            # Re-check and send any living thread in state 8 a dummy DB return
            for t in enumthreads():
                try:
                    if t.is_alive() and t.thread_type in ('lookup', 'source', 'channel'):
                        t.quit = True
                        if t.is_alive() and t.thread_type == 'channel':
                            t.detail_return.put('quit')

                        if t.is_alive() and t.thread_type in ('lookup', 'source'):
                            t.detail_request.put({'task': 'quit'})

                        while t.state & 8:
                            t.cache_return.put('quit')
                            t.join(1)

                except:
                    continue

        self.log_output = self.config.log_output
        last_queuelog = self.config.in_output_tz('now')
        lastcheck = self.config.in_output_tz('now')
        checkinterfall = 60
        queueloginterfall = 300
        self.fatal_error = [self.config.text('IO', 10), \
                '     %s\n' % (self.config.opt_dict['config_file']), \
                '     %s\n' % (self.config.opt_dict['log_file'])]

        while True:
            try:
                if self.quit and self.log_queue.empty():
                    # We close down after mailing the log and seeing all threads closed
                    while True:
                        alive = False
                        for t in enumthreads():
                            tn = None
                            try:
                                tn = unicode(t.name)

                            except:
                                tn = None

                            if tn not in ('logging', 'MainThread') and t.is_alive():
                                alive = True
                                if self.print_live_threads:
                                    self.writelog('%s is still alive in state %s' % (t.name, t.state))

                                time.sleep(5)

                        if alive == False:
                            break

                    if self.config.opt_dict['mail_log']:
                        self.send_mail(self.log_string, self.config.opt_dict['mail_log_address'])

                    return(0)

                if not self.config.test_modus:
                    if (self.config.in_output_tz('now') - last_queuelog).total_seconds() > queueloginterfall:
                        last_queuelog = self.config.in_output_tz('now')
                        self.send_queue_log()

                    if self.check_threads and (self.config.in_output_tz('now') - lastcheck).total_seconds() > checkinterfall:
                        lastcheck = self.config.in_output_tz('now')
                        self.check_thread_sanity()

                try:
                    message = self.log_queue.get(True, 5)

                except Empty:
                    continue

                if message == None:
                    continue

                elif isinstance(message, dict) and 'fatal' in message:
                    # A fatal Error has been received, after logging we send all threads the quit signal
                    self.config.errorstate = 99
                    if 'name'in message and message['name'] != None:
                        mm =  ['\n', self.config.text('IO', 11, (message['name'], ))]

                    else:
                        mm = ['\n', self.config.text('IO', 12)]

                    if isinstance(message['fatal'], (str, unicode)):
                        mm.append(message['fatal'])

                    elif isinstance(message['fatal'], (list, tuple)):
                        mm.extend(list(message['fatal']))

                    mm.extend(self.fatal_error)
                    for m in mm:
                        if isinstance(m, (str, unicode)):
                            self.writelog(m, 0)

                    close_all_threads()
                    continue

                elif isinstance(message, (str, unicode)):
                    if message == 'Closing down\n':
                        close_all_threads()

                    elif message[:12].lower() == 'datatreegrab':
                        self.writelog(message, 256)

                    else:
                        self.writelog(message)

                    continue

                elif isinstance(message, (list ,tuple)):
                    llevel = message[1] if len(message) > 1 else 1
                    ltarget = message[2] if len(message) > 2 else 3
                    if message[0] == None:
                        continue

                    if message[0] == 'Closing down\n':
                        close_all_threads()

                    elif message[0][:12] == 'DataTreeGrab':
                        caller_id = llevel
                        severity = ltarget
                        ltarget = 3
                        if severity == 1:
                            # It's a serious warning
                            llevel = 1

                        elif severity == 2:
                            # It's a medium warning
                            if caller_id == -1:
                                # Comming from ttvdb
                                llevel = 128

                            else:
                                llevel = 256

                        elif caller_id == -1:
                            llevel = 32768

                        else:
                            llevel = 65536

                    if isinstance(message[0], (str, unicode)):
                        self.writelog(message[0], llevel, ltarget)
                        continue

                    elif isinstance(message[0], (list, tuple)):
                        for m in message[0]:
                            if isinstance(m, (str, unicode)):
                                self.writelog(m, llevel, ltarget)

                        continue

                self.writelog(self.config.text('IO', 13, (message, type(message))))

            except:
                sys.stderr.write((self.now() + u'An error occured while logging!\n').encode(self.local_encoding, 'replace'))
                traceback.print_exc()

    # end run()

    def now(self):
         return self.config.in_output_tz('now').strftime('%Y-%m-%d %H:%M:%S %Z: ')

    # end now()

    def check_thread_sanity(self):
        #Thread.state =                        Cache           Source          theTVdb         Channel
        #0: Thread not looping or waiting        x               x               x               x
        #1: Thread base page loop/Init           x               x               -               x
        #2: Thread child channel loop            -               -               -               x
        #3: Thread selecting/processing lookup   x               -               x               x
        #4: Thread detail pages loop             x               x               x               x
        #5: Thread waiting for ttvdb             -               -               -               x
        #8: Thread waiting on db return          -               x               x               x

        # The time the source may be idle before canceling
        idle_timeout = 180
        # The time since the last request ttvdb will quit
        idle_timeout2 = 1800
        chan_count = {}
        for t in range(-1, 6):
            chan_count[t] = 0

        for t in enumthreads():
            try:
                if t.thread_type == 'channel':
                    state = t.state & 7
                    chan_count[-1] += 1
                    chan_count[state] += 1
                    if state in (0, 3):
                        continue

                    elif state == 1:
                        # Waiting for a basepage from source
                        s = t.source
                        if not isinstance(s, int):
                            continue

                        sc = self.config.channelsource[s]
                        if sc.has_started and ((sc.state & 7) != 1 or not sc.is_alive()):
                            # The source already finished the basepages
                            t.source_data[s].set()
                            if self.log_thread_checks:
                                self.writelog('Setting source_data from %s (state %s) ready for %s.\n' % (sc.source, sc.state, t.chan_descr))

                    elif state == 2:
                        # Waiting for a child channel source
                        s = t.source
                        if not s in self.config.channels.keys():
                            continue

                        sc = self.config.channels[s]
                        if sc.has_started and ((sc.state & 7) > 2 or not sc.is_alive()):
                            # The child already produced the data
                            sc.child_data.set()
                            if self.log_thread_checks:
                                self.writelog('Setting child_data from %s (state %s) ready for %s.\n' % (sc.chan_descr, sc.state, t.chan_descr))

                    elif state == 4:
                        # Waiting for details
                        pass

            except:
                continue

        if not self.all_at_details and chan_count[-1] == chan_count[4] + chan_count[5]:
            self.all_at_details = True

        # All channels are at least waiting for details
        if self.all_at_details:
            for t in enumthreads():
                try:
                    if t.thread_type == 'source':
                        waittime = None
                        if isinstance(t.lastrequest, datetime.datetime):
                            waittime = (self.config.in_output_tz('now') - t.lastrequest).total_seconds()

                        if waittime == None or waittime < idle_timeout:
                            break

                except:
                    continue

            else:
                # All sources are waiting more then idle_timeout
                # So we tell all channels nothing more is coming
                for t in enumthreads():
                    try:
                        if t.thread_type == 'channel':
                            if t.state == 4:
                                d = 0
                                for s in self.config.detail_sources:
                                    d += self.functions.get_counter('queue', s, t.chanid)

                                if d > 0:
                                    self.config.log([self.config.text('fetch', 21, (channel.chan_descr, d)), self.config.text('fetch', 22)])

                                t.detail_data.set()
                                t.detail_return.put('last_detail')

                    except:
                        continue

            t = self.config.ttvdb
            waittime = -1
            if t != None and t.is_alive() and isinstance(t.lastrequest, datetime.datetime):
                 waittime = (self.config.in_output_tz('now') - t.lastrequest).total_seconds()
                 # And the same with ttvdb, but we let it wait longer
                 if waittime > idle_timeout2:
                    ttvdb_cnt = 0
                    if len(t.pending_tids) > 0:
                        for ttvdbid, queryid in t.pending_tids.items():
                            name = t.episodetrees[queryid].rundata['name']
                            self.config.log([self.config.text('fetch', 19, ('%s: %s' % (ttvdbid, name), ))])
                            if t.episodetrees[queryid].is_alive():
                                t.episodetrees[queryid].searchtree.quit = True

                    for t in enumthreads():
                        try:
                            if t.thread_type == 'channel':
                                if t.state == 5:
                                    ttvdb_cnt += t.ttvdb_counter
                                    if t.ttvdb_counter > 0:
                                        self.config.log([self.config.text('fetch', 20, (channel.chan_descr, t.ttvdb_counter)), self.config.text('fetch', 22)])

                                    t.ttvdb_counter = 0

                        except:
                            continue

                    #~ if ttvdb_cnt > 0:
                        #~ self.config.log('ttvdb has the following IDs pending: %s' % self.config.ttvdb.pending_tids.keys())

    # end check_thread_sanity()

    def send_queue_log(self):
        for m in self.config.log_queues():
            self.writelog(m, 512, 1)

        t = self.config.ttvdb
        if t != None and t.is_alive():
            for queryid in t.pending_tids.values():
                dtree = t.episodetrees[queryid]
                if dtree.is_alive() and not dtree.searchtree.progress_queue.empty():
                    name = dtree.rundata['name']
                    tid = dtree.rundata['tid']
                    while not dtree.searchtree.progress_queue.empty():
                        actkey, keycount = dtree.searchtree.progress_queue.get(True)

                    progress = actkey/keycount
                    self.writelog('ttvdb query for "%s" (%s) is at %3.0f%%' % (name, tid, progress), 512, 1)
    # send_queue_log()

    def writelog(self, message, log_level = 1, log_target = 3):
        try:
            if message == None:
                return

            # If output is not yet available
            if (self.log_output == None) and (log_target & 1):
                sys.stderr.write(('Error writing to log. Not (yet) available?\n').encode(self.local_encoding, 'replace'))
                sys.stderr.write(message.encode(self.local_encoding, 'replace'))
                return

            # Log to the Frontend. To set-up later.
            if self.config.opt_dict['graphic_frontend']:
                pass

            # Log to the screen
            elif log_level == 0 or ((not self.config.opt_dict['quiet']) and (log_level & self.config.opt_dict['log_level']) and (log_target & 1)):
                sys.stderr.write(message.encode(self.local_encoding, 'replace'))

            # Log to the log-file
            if (log_level == 0 or ((log_level & self.config.opt_dict['log_level']) and (log_target & 2))) and self.log_output != None:
                if '\n' in message:
                    message = re.split('\n', message)

                    for i in range(len(message)):
                        if message[i] != '':
                            self.log_output.write(self.now() + message[i] + u'\n')
                            if self.config.opt_dict['mail_log']:
                                self.log_string.append(self.now() + message[i] + u'\n')

                else:
                    self.log_output.write(self.now() + message + u'\n')
                    if self.config.opt_dict['mail_log']:
                        self.log_string.append(self.now() + message + u'\n')

                self.log_output.flush()

        except:
            sys.stderr.write((self.now() + 'An error ocured while logging!\n').encode(self.local_encoding, 'replace'))
            traceback.print_exc()

    # end writelog()

    def send_mail(self, message, mail_address, subject=None):
        try:
            if isinstance(message, (list,tuple)):
                msg = u''.join(message)

            elif isinstance(message, (str,unicode)):
                msg = unicode(message)

            else:
                return

            if subject == None:
                subject = 'Tv_grab_nl3_py %s' % self.config.in_output_tz('now').strftime('%Y-%m-%d %H:%M')

            msg = MIMEText(msg, _charset='utf-8')
            msg['Subject'] = subject
            msg['From'] = mail_address
            msg['To'] = mail_address
            try:
                mail = smtplib.SMTP(self.config.opt_dict['mailserver'], self.config.opt_dict['mailport'])

            except:
                sys.stderr.write(('Error mailing message: %s\n' % sys.exc_info()[1]).encode(self.local_encoding, 'replace'))
                return

            mail.sendmail(mail_address, mail_address, msg.as_string())

        except smtplib.SMTPRecipientsRefused:
            sys.stderr.write(('The mailserver at %s refused the message\n' % self.config.opt_dict['mailserver']).encode(self.local_encoding, 'replace'))

        except:
            sys.stderr.write('Error mailing message\n'.encode(self.local_encoding, 'replace'))
            sys.stderr.write(traceback.format_exc())

        mail.quit()
    # send_mail()

# end Logging

class ProgramCache(Thread):
    """
    A cache to hold program name and category info.
    TVgids and others stores the detail for each program on a separate
    URL with an (apparently unique) ID. This cache stores the fetched info
    with the ID. New fetches will use the cached info instead of doing an
    (expensive) page fetch.
    """
    def __init__(self, config, filename=None):
        Thread.__init__(self, name = 'caching')
        """
        Create a new ProgramCache object, optionally from file
        """
        self. print_data_structure = False
        self.config = config
        self.functions = self.config.IO_func
        self.current_date = self.config.in_fetch_tz(datetime.datetime.now(pytz.utc))
        sqlite3.register_adapter(list, self.adapt_list)
        sqlite3.register_converter(str('listing'), self.convert_list)
        sqlite3.register_adapter(bool, self.adapt_bool)
        sqlite3.register_converter(str('boolean'), self.convert_bool)
        sqlite3.register_adapter(datetime.datetime, self.adapt_datetime)
        sqlite3.register_converter(str('datetime'), self.convert_datetime)
        sqlite3.register_adapter(datetime.timedelta, self.adapt_timedelta)
        sqlite3.register_converter(str('timedelta'), self.convert_timedelta)
        sqlite3.register_adapter(datetime.date, self.adapt_date)
        sqlite3.register_converter(str('date'), self.convert_date)
        self.table_definitions = {
            "channels": {"name": "channels", "no rowid": True,
                "fields":{"chanid": {"type": "TEXT", "default": ""},
                                   "name": {"type": "TEXT", "default": ""},
                                   "cgroup": {"type": "INTEGER", "default": 99}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["chanid"]},
                    "cgroup": {"fields": ["cgroup"]},
                    "chan_name": {"fields": ["name"]}}},
            "sources": {"name": "sources", "no rowid": True,
                "fields":{"sourceid": {"type": "INTEGER", "default": 0},
                                   "name": {"type": "TEXT", "default": ""},
                                   "use_alt_url": {"type": "boolean", "default": "False"}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["sourceid"]}}},
            "channelsource": {"name": "channelsource", "no rowid": True,
                "fields":{"chanid": {"type": "TEXT", "default": ""},
                                   "sourceid": {"type": "INTEGER", "default": 0},
                                   "scid": {"type": "TEXT", "default": ""},
                                   "name": {"type": "TEXT", "default": ""},
                                   "fgroup": {"type": "TEXT", "null": True},
                                   "hd": {"type": "boolean", "default": "False"},
                                   "emptycount": {"type": "INTEGER", "default": 0}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["chanid", "sourceid"]},
                    "scid": {"fields": ["sourceid", "scid"]},
                    "fgroup": {"fields": ["sourceid", "fgroup"]}}},
            "iconsource": {"name": "iconsource", "no rowid": True,
                "fields":{"chanid": {"type": "TEXT", "default": ""},
                                   "sourceid": {"type": "INTEGER", "default": 0},
                                   "icon": {"type": "TEXT", "null": True}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["chanid", "sourceid"]}}},
            "fetcheddays": {"name": "fetcheddays", "no rowid": True,
                "fields":{"sourceid": {"type": "INTEGER", "default": 0},
                                   "channelid": {"type": "TEXT", "default": ""},
                                   "scandate": {"type": "date", "default": 0},
                                   "stored": {"type": "boolean", "default": "True"}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["sourceid", "channelid", "scandate"]}}},
            "fetcheddata": {"name": "fetcheddata", "no rowid": True,
                "fields":{"sourceid": {"type": "INTEGER", "default": 0},
                                   "channelid": {"type": "TEXT", "default": ""},
                                   "laststop": {"type": "datetime", "null": True}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["sourceid", "channelid"]}}},
            "sourceprograms": {"name": "sourceprograms", "no rowid": True,
                "fields":{"sourceid": {"type": "INTEGER", "default": 0},
                                   "channelid": {"type": "TEXT", "default": ""},
                                   "scandate": {"type": "date", "default": 0},
                                   "start-time": {"type": "datetime", "default": 0},
                                   "stop-time": {"type": "datetime", "default": 0},
                                   "prog_ID": {"type": "TEXT", "null": True},
                                   "gen_ID": {"type": "TEXT", "null": True},
                                   "group name": {"type": "TEXT", "null": True},
                                   "name": {"type": "TEXT", "default": ""},
                                   "episode title": {"type": "TEXT", "null": True},
                                   "genre": {"type": "TEXT", "null": True},
                                   "org-genre": {"type": "TEXT", "null": True},
                                   "org-subgenre": {"type": "TEXT", "null": True},
                                   "season": {"type": "INTEGER", "null": True},
                                   "episode": {"type": "INTEGER", "null": True}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["sourceid", "channelid", "start-time"]},
                    "scandate": {"fields": ["sourceid", "channelid", "scandate"]},
                    "progid": {"fields": ["sourceid", "channelid", "prog_ID"]},
                    "stoptime": {"fields": ["sourceid", "channelid", "stop-time"]},
                    "name": {"fields": ["sourceid", "channelid", "name", "episode title"]},
                    "episode": {"fields": ["sourceid", "channelid", "season", "episode"]}}},
            "credits": {"name": "credits", "no rowid": True,
                "fields":{"sourceid": {"type": "INTEGER", "default": 0},
                                   "channelid": {"type": "TEXT", "default": ""},
                                   "scandate": {"type": "date", "default": 0},
                                   "prog_ID": {"type": "TEXT", "null": True},
                                   "start-time": {"type": "datetime", "default": 0},
                                   "stop-time": {"type": "datetime", "default": 0},
                                   "title": {"type": "TEXT", "default": ""},
                                   "name": {"type": "TEXT", "default": ""},
                                   "role": {"type": "TEXT", "null": True}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["sourceid", "channelid", "start-time", "title", "name"]},
                    "scandate": {"fields": ["sourceid", "channelid", "scandate"]},
                    "progid": {"fields": ["sourceid", "channelid", "prog_ID"]},
                    "stoptime": {"fields": ["sourceid", "channelid", "stop-time"]}}},
            "programdetails": {"name": "programdetails", "no rowid": True,
                "fields":{"sourceid": {"type": "INTEGER", "default": 0},
                                   "channelid": {"type": "TEXT", "default": ""},
                                   "scandate": {"type": "date", "default": 0},
                                   "prog_ID": {"type": "TEXT", "default": ""},
                                   "start-time": {"type": "datetime", "default": 0},
                                   "stop-time": {"type": "datetime", "default": 0},
                                   "length": {"type": "timedelta", "null": True},
                                   "group name": {"type": "TEXT", "null": True},
                                   "name": {"type": "TEXT", "default": ""},
                                   "genre": {"type": "TEXT", "null": True}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["sourceid", "channelid", "prog_ID"]},
                    "starttime": {"fields": ["sourceid", "channelid", "start-time"]},
                    "stoptime": {"fields": ["sourceid", "channelid", "stop-time"]},
                    "name": {"fields": ["sourceid", "channelid", "name"]}}},
            "creditdetails": {"name": "creditdetails", "no rowid": True,
                "fields":{"sourceid": {"type": "INTEGER", "default": 0},
                                   "channelid": {"type": "TEXT", "default": ""},
                                   "scandate": {"type": "date", "default": 0},
                                   "prog_ID": {"type": "TEXT", "default": ""},
                                   "start-time": {"type": "datetime", "default": 0},
                                   "stop-time": {"type": "datetime", "default": 0},
                                   "title": {"type": "TEXT", "default": ""},
                                   "name": {"type": "TEXT", "default": ""},
                                   "role": {"type": "TEXT", "null": True}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["sourceid", "channelid", "prog_ID", "title", "name"]},
                    "starttime": {"fields": ["sourceid", "channelid", "start-time"]},
                    "stoptime": {"fields": ["sourceid", "channelid", "stop-time"]}}},
            "ttvdb_alias": {"name": "ttvdb_alias", "no rowid": True,
                "fields":{ "alias": {"type": "TEXT", "default": ""},
                                   "tid": {"type": "INTEGER", "default": 0},
                                   "name": {"type": "TEXT", "default": ""},
                                   "tdate": {"type": "date", "null": True}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["alias"]},
                    "ttvdbtitle": {"fields": ["name"]},
                    "ttvdbtid": {"fields": ["tid"]}}},
            "ttvdb": {"name": "ttvdb", "no rowid": True,
                "fields":{"name": {"type": "TEXT", "default": ""},
                                   "tid": {"type": "INTEGER", "default": 0},
                                   "tdate": {"type": "date", "default": 0},
                                   "airdate": {"type": "date", "null": True}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["tid"]},
                    "ttvdbtitle": {"fields": ["name"]},
                    "ttvdbdate": {"fields": ["tdate"]}}},
            "ttvdbint": {"name": "ttvdbint", "no rowid": True,
                "fields":{"tid": {"type": "INTEGER", "default": 0},
                                   "lang": {"type": "TEXT", "default": ""},
                                   "name": {"type": "TEXT", "default": ""},
                                   "description": {"type": "TEXT", "null": True}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["tid", "lang"]},
                    "ttvdbtitle": {"fields": ["name"]},
                    "ttvdbtid": {"fields": ["tid"]}}},
            "episodes": {"name": "episodes", "no rowid": True,
                "fields":{"tepid": {"type": "INTEGER", "default": -1},
                                   "tid": {"type": "INTEGER", "default": 0},
                                   "sid": {"type": "INTEGER", "default": -1},
                                   "eid": {"type": "INTEGER", "default": -1},
                                   "abseid": {"type": "INTEGER", "default": 0},
                                   "star-rating": {"type": "TEXT", "null": True},
                                   "airdate": {"type": "date", "null": True}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["tepid"]},
                    "tseid": {"fields": ["tid", "sid", "eid"]}}},
            "episodesint": {"name": "episodesint", "no rowid": True,
                "fields":{"tepid": {"type": "INTEGER", "default": -1},
                                   "lang": {"type": "TEXT", "default": ""},
                                   "episode title": {"type": "TEXT", "default": ""},
                                   "description": {"type": "TEXT", "null": True}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["tepid", "lang"]},
                    "eptitle": {"fields": ["episode title"]}}},
            "ttvdbcredits": {"name": "ttvdbcredits", "no rowid": True,
                "fields":{"tid": {"type": "INTEGER", "default": 0},
                                   "sid": {"type": "INTEGER", "default": -1},
                                   "eid": {"type": "INTEGER", "default": -1},
                                   "title": {"type": "TEXT", "default": ""},
                                   "name": {"type": "TEXT", "default": ""},
                                   "role": {"type": "TEXT", "null": True}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["tid", "sid", "eid", "title", "name"]},
                    "tid": {"fields": ["tid", "sid", "eid"]}}},
            "ttvdbmetadata": {"name": "ttvdbmetadata",
                "fields":{"tid": {"type": "INTEGER", "default": 0},
                                   "sid": {"type": "INTEGER", "default": -1},
                                   "eid": {"type": "INTEGER", "default": -1},
                                   "type": {"type": "TEXT", "default": "banner"},
                                   "url": {"type": "TEXT", "default": ""}},
                "indexes":{"tid": {"fields": ["tid", "sid", "eid"]}}},
            "epcount": {"name": "epcount", "no rowid": True,
                "fields":{"tid": {"type": "INTEGER", "default": 0},
                                   "sid": {"type": "INTEGER", "default": -1},
                                   "count": {"type": "INTEGER", "default": -1}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["tid", "sid"]}}}}

        for key in self.config.key_values['text']:
            if key not in self.get_fields("sourceprograms"):
                self.table_definitions["sourceprograms"]["fields"][key] = {"type": "TEXT", "null": True}

            if key in self.config.detail_keys['all'] and key not in self.get_fields("programdetails"):
                self.table_definitions["programdetails"]["fields"][key] = {"type": "TEXT", "null": True}

            if key in self.config.detail_keys['ttvdb'] and not \
              (key in self.get_fields("ttvdb") or key in self.get_fields("ttvdbint")):
                self.table_definitions["ttvdb"]["fields"][key] = {"type": "TEXT", "null": True}

            if key in self.config.detail_keys['episodes'] and not \
              (key in self.get_fields("episodes") or key in self.get_fields("episodesint")):
                self.table_definitions["episodes"]["fields"][key] = {"type": "TEXT", "null": True}

        for key in self.config.key_values['date']:
            if key not in self.get_fields("sourceprograms"):
                self.table_definitions["sourceprograms"]["fields"][key] = {"type": "date", "null": True}

            if key in self.config.detail_keys['all'] and key not in self.get_fields("programdetails"):
                self.table_definitions["programdetails"]["fields"][key] = {"type": "date", "null": True}

            if key in self.config.detail_keys['ttvdb'] and key not in self.get_fields("ttvdb"):
                self.table_definitions["ttvdb"]["fields"][key] = {"type": "date", "null": True}

            if key in self.config.detail_keys['episodes'] and key not in self.get_fields("episodes"):
                self.table_definitions["episodes"]["fields"][key] = {"type": "date", "null": True}

        for key in self.config.key_values['datetime']:
            if key not in self.get_fields("sourceprograms"):
                self.table_definitions["sourceprograms"]["fields"][key] = {"type": "datetime", "null": True}

            if key in self.config.detail_keys['all'] and key not in self.get_fields("programdetails"):
                self.table_definitions["programdetails"]["fields"][key] = {"type": "datetime", "null": True}

            if key in self.config.detail_keys['ttvdb'] and key not in self.get_fields("ttvdb"):
                self.table_definitions["ttvdb"]["fields"][key] = {"type": "datetime", "null": True}

            if key in self.config.detail_keys['episodes'] and key not in self.get_fields("episodes"):
                self.table_definitions["episodes"]["fields"][key] = {"type": "datetime", "null": True}

        for key in self.config.key_values['timedelta']:
            if key not in self.get_fields("sourceprograms"):
                self.table_definitions["sourceprograms"]["fields"][key] = {"type": "timedelta", "null": True}

            if key in self.config.detail_keys['all'] and key not in self.get_fields("programdetails"):
                self.table_definitions["programdetails"]["fields"][key] = {"type": "timedelta", "null": True}

        for key in self.config.key_values['bool']:
            if key not in self.get_fields("sourceprograms"):
                self.table_definitions["sourceprograms"]["fields"][key] = {"type": "boolean", "null": True}

            if key in self.config.detail_keys['all'] and key not in self.get_fields("programdetails"):
                self.table_definitions["programdetails"]["fields"][key] = {"type": "boolean", "null": True}

            if key in self.config.detail_keys['ttvdb'] and key not in self.get_fields("ttvdb"):
                self.table_definitions["ttvdb"]["fields"][key] = {"type": "boolean", "null": True}

            if key in self.config.detail_keys['episodes'] and key not in self.get_fields("episodes"):
                self.table_definitions["episodes"]["fields"][key] = {"type": "boolean", "null": True}

        for key in self.config.key_values['video']:
            if key not in self.get_fields("sourceprograms"):
                self.table_definitions["sourceprograms"]["fields"][key] = {"type": "boolean", "null": True}

            if key in self.config.detail_keys['all'] and key not in self.get_fields("programdetails"):
                self.table_definitions["programdetails"]["fields"][key] = {"type": "boolean", "null": True}

            if key in self.config.detail_keys['ttvdb'] and key not in self.get_fields("ttvdb"):
                self.table_definitions["ttvdb"]["fields"][key] = {"type": "boolean", "null": True}

            if key in self.config.detail_keys['episodes'] and key not in self.get_fields("episodes"):
                self.table_definitions["episodes"]["fields"][key] = {"type": "boolean", "null": True}

        for key in self.config.key_values['int']:
            if key not in self.get_fields("sourceprograms"):
                self.table_definitions["sourceprograms"]["fields"][key] = {"type": "INTEGER", "null": True}

            if key in self.config.detail_keys['all'] and key not in self.get_fields("programdetails"):
                self.table_definitions["programdetails"]["fields"][key] = {"type": "INTEGER", "null": True}

            if key in self.config.detail_keys['ttvdb'] and key not in self.get_fields("ttvdb"):
                self.table_definitions["ttvdb"]["fields"][key] = {"type": "INTEGER", "null": True}

            if key in self.config.detail_keys['episodes'] and key not in self.get_fields("episodes"):
                self.table_definitions["episodes"]["fields"][key] = {"type": "INTEGER", "null": True}

        for key in self.config.key_values['list']:
            if key not in self.get_fields("sourceprograms"):
                self.table_definitions["sourceprograms"]["fields"][key] = {"type": "listing", "null": True}

            if key in self.config.detail_keys['all'] and key not in self.get_fields("programdetails"):
                self.table_definitions["programdetails"]["fields"][key] = {"type": "listing", "null": True}

            if key in self.config.detail_keys['ttvdb'] and key not in self.get_fields("ttvdb"):
                self.table_definitions["ttvdb"]["fields"][key] = {"type": "listing", "null": True}

            if key in self.config.detail_keys['episodes'] and key not in self.get_fields("episodes"):
                self.table_definitions["episodes"]["fields"][key] = {"type": "listing", "null": True}

        self.field_list = {}
        for table, data in self.table_definitions.items():
            self.field_list[table] = data['fields'].keys()

        # where we store our info
        self.filename  = filename
        self.quit = False
        self.cache_request = Queue()
        self.config.queues['cache'] = self.cache_request
        self.thread_type = 'cache'
        self.state = 0
        self.config.threads.append(self)
        self.request_list = {}
        self.request_list['query'] = ('icon', 'chan_group', 'chan_scid', 'use_alt_url', 'laststop',
                                    'ttvdbid', 'ttvdbname', 'tdate',
                                    'ttvdb_aliasses', 'ttvdb_langs', 'ep_by_id', 'ep_by_title')
        self.request_list['add'] = ('channel', 'icon', 'laststop')
        self.request_list['update'] = ('toggle_alt_url')
        self.request_list['delete'] = tuple()
        self.request_list['clear'] = ('fetcheddays', 'fetcheddata', 'sourceprograms', 'credits',
                                    'programdetails', 'creditdetails')
        self.request_list['clearttvdb'] = ('ttvdb', 'ttvdbint', 'ttvdb_alias', 'episodes', 'episodesint',
                                    'ttvdbcredits', 'ttvdbmetadata', 'epcount')

    def offset_to_date(self, val):
        return (self.current_date + datetime.timedelta(days=val)).date()

    def date_to_offset(self, val):
        if isinstance(val, datetime.datetime):
            val = self.config.in_fetch_tz(val)
            return int(val.toordinal() - self.current_date.toordinal())

        if isinstance(val, datetime.date):
            return int(val.toordinal() - self.current_date.toordinal())

    def adapt_list(self, val):
        if isinstance(val, (str, unicode)):
            return val

        if not isinstance(val, (list, tuple, set)) or len(val) == 0:
            return ''

        ret_val = ''
        for k in val:
            ret_val += ';%s' % k

        return ret_val[1:]

    def convert_list(self, val):
        ret_val = []
        val = val.split(';')
        for k in val:
            ret_val.append(k)

        return ret_val

    def adapt_bool(self, val):
        if val:
            return 'True'

        elif val == None:
            return 'None'

        else:
            return 'False'

    def convert_bool(self, val):
        if val == 'True':
            return True

        elif val == 'False':
            return False

        else:
            return None

    def adapt_datetime(self, val):
        if isinstance(val, (datetime.datetime)):
            return int(calendar.timegm(val.utctimetuple()))

        else:
            return 0

    def convert_datetime(self, val):
        try:
            if int(val) == 0 or val == '':
                return None

            if len(str(val)) < 10:
                return datetime.date.fromordinal(int(val))

            return datetime.datetime.fromtimestamp(int(val), self.config.utc_tz)

        except:
            return None

    def adapt_timedelta(self, val):
        if isinstance(val, (datetime.timedelta)):
            return int(val.total_seconds())

        elif isinstance(val, (int, long)):
            return val

        else:
            return 0

    def convert_timedelta(self, val):
        try:
            return datetime.timedelta(0, int(val))

        except:
            return None

    def adapt_date(self, val):
        if isinstance(val, (datetime.date)):
            return val.toordinal()

        return 0

    def convert_date(self, val):
        try:
            if int(val) == 0 or val == '':
                return None

            return datetime.date.fromordinal(int(val))

        except:
            return None

    def get_tprop(self, table, tprop, default = None):
        if table in self.table_definitions.keys():
            if tprop in self.table_definitions[table].keys():
                return self.table_definitions[table][tprop]

        return default

    def get_fields(self, table):
        if table in self.table_definitions.keys():
            if 'fields' in self.table_definitions[table].keys():
                return list(self.table_definitions[table]['fields'].keys())

        return []

    def get_fprop(self, table, field, fprop, default = None):
        if table in self.table_definitions.keys():
            if 'fields' in self.table_definitions[table].keys():
                if field in self.table_definitions[table]['fields'].keys():
                    if fprop in self.table_definitions[table]['fields'][field].keys():
                        return self.table_definitions[table]['fields'][field][fprop]

        return default

    def get_column_string(self, table, field):
        ftype = self.get_fprop(table, field, 'type', 'TEXT')
        fdefault =  self.get_fprop(table, field, 'default')
        fnullable = self.get_fprop(table, field, 'null', False)
        dstring = u""
        if fdefault != None:
            if ftype.upper() in ('INTEGER', 'DATE', 'DATETIME'):
                if isinstance(fdefault, int):
                    dstring = " DEFAULT %s" % (fdefault)

                else:
                    try:
                        fdefault = int(fdefault)

                    except:
                        fdefault = 0

                    dstring = " DEFAULT %s" % (fdefault)

            elif isinstance(fdefault, (str,unicode)):
                dstring = " DEFAULT '%s'" % (fdefault)

        nstring = u"" if fnullable else " NOT NULL"
        return u"`%s` %s%s%s" % (field, ftype, nstring, dstring)

    def get_indexes(self, table):
        if table in self.table_definitions.keys():
            if 'indexes' in self.table_definitions[table].keys():
                return list(self.table_definitions[table]['indexes'].keys())

        return []

    def get_iprop(self, table, index, iprop, default = None):
        if table in self.table_definitions.keys():
            if 'indexes' in self.table_definitions[table].keys():
                if index in self.table_definitions[table]['indexes'].keys():
                    if iprop in self.table_definitions[table]['indexes'][index].keys():
                        return self.table_definitions[table]['indexes'][index][iprop]

        return default

    def get_ifields(self, table, index):
        if table in self.table_definitions.keys():
            if 'indexes' in self.table_definitions[table].keys():
                if index in self.table_definitions[table]['indexes'].keys():
                    if 'fields' in self.table_definitions[table]['indexes'][index].keys():
                        return self.table_definitions[table]['indexes'][index]['fields']

        return []

    def open_db(self):
        if self.filename == None:
            self.functions.log(self.config.text('IO', 20))
            return

        if os.path.isfile(self.filename +'.db'):
            # There is already a db file
            self.load_db()
            return

        elif os.path.isfile(self.filename +'.db.bak'):
            # Check for a backup
            try:
                shutil.copy(self.filename + '.db.bak', self.filename + '.db')
                self.load_db()
                return

            except:
                pass

        # Check the directory
        if not os.path.exists(os.path.dirname(self.filename)):
            try:
                os.makedirs(os.path.dirname(self.filename), 0755)
                self.load_db
                return

            except:
                self.functions.log(self.config.text('IO', 21))
                self.filename = None
                return

        self.load_db()

    def load_db(self):
        """
        Opens a sqlite cache db
        """
        # We try to open the DB,else we try the backup copy
        for try_loading in (0,1):
            try:
                self.pconn = sqlite3.connect(database=self.filename + '.db', isolation_level=None, detect_types=sqlite3.PARSE_DECLTYPES)
                self.pconn.row_factory = sqlite3.Row
                self.functions.log(self.config.text('IO', 1, type = 'other'))
                if self.fetchone("PRAGMA main.integrity_check")[0] == 'ok':
                    # Making a backup copy
                    self.pconn.close()
                    if os.path.isfile(self.filename +'.db.bak'):
                        os.remove(self.filename + '.db.bak')

                    shutil.copy(self.filename + '.db', self.filename + '.db.bak')
                    self.pconn = sqlite3.connect(database=self.filename + '.db', isolation_level=None, detect_types=sqlite3.PARSE_DECLTYPES)
                    self.pconn.row_factory = sqlite3.Row
                    break

                if try_loading == 0:
                    # The integrity check failed. We restore a backup
                    self.functions.log([self.config.text('IO', 22, (self.filename, )), self.config.text('IO', 23)])

            except:
                if try_loading == 0:
                    # Opening the DB failed. We restore a backup
                    self.functions.log([self.config.text('IO', 22, (self.filename, )), self.config.text('IO', 23), traceback.format_exc()])

            try:
                # Just in case it is still open
                self.pconn.close()

            except:
                pass

            try:
                # Trying to restore the backup
                if os.path.isfile(self.filename +'.db'):
                    os.remove(self.filename + '.db')

                if os.path.isfile(self.filename +'.db.bak'):
                    if try_loading == 0:
                        shutil.copy(self.filename + '.db.bak', self.filename + '.db')

                    else:
                        os.remove(self.filename + '.db.bak')

            except:
                # No luck so we disable all caching related functionality
                self.functions.log([self.config.text('IO', 24, (self.filename, )), traceback.format_exc(), self.config.text('IO', 25)])
                self.filename = None
                self.config.opt_dict['disable_ttvdb'] = True
                return

        try:
            self.execute("PRAGMA main.synchronous = OFF")
            self.execute("PRAGMA main.temp_store = MEMORY")
            if len(self.fetchall("PRAGMA main.table_info('ttvdbint')")) == 0:
                # Itś an old ttvdb table structure we clear it
                for t in self.request_list['clearttvdb']:
                    self.clear(t)

            # We Check all Tables, Columns and Indices
            for t in self.table_definitions.keys():
                if self. print_data_structure:
                    print t

                # (cid, Name, Type, Nullable = 0, Default, Pri_key index)
                trows = self.fetchall("PRAGMA main.table_info('%s')" % (t,))
                if len(trows) == 0:
                    # Table does not exist
                    self.create_table(t)
                    continue

                else:
                    clist = {}
                    for r in trows:
                        clist[r[1].lower()] = r
                        if self. print_data_structure:
                            print '  ', r

                    self.check_columns(t, clist)

                self.check_indexes(t)

            # We add if not jet there some defaults
            for a, t in self.config.ttvdb_ids.items():
                if self.query('ttvdb_alias', alias = a) == None:
                    self.add('ttvdb_alias',
                                    {'tid': t['tid'],
                                    'name': t['name'],
                                    'alias': a,
                                    'tdate': None})

        except:
            self.functions.log([self.config.text('IO', 24, (self.filename, )), traceback.format_exc(), self.config.text('IO', 25)])
            self.filename = None
            self.config.opt_dict['disable_ttvdb'] = True

    def create_table(self, table):
        if not table in self.table_definitions.keys():
            return

        if self. print_data_structure:
            print 'creating table', table

        create_string = u"CREATE TABLE IF NOT EXISTS %s" % table
        psplit = u" ("
        for fld in self.get_fields(table):
            create_string = u"%s%s%s" % (create_string, psplit, self.get_column_string(table, fld))
            psplit = u", "

        pkfields = self.get_ifields(table, 'PRIMARY')
        pkstring = u")"
        if len(pkfields) > 0:
            pkstring = u", PRIMARY KEY"
            psplit = u" ("
            for fld in pkfields:
                if not fld in self.get_fields(table):
                    continue

                pkstring += u"%s`%s`"% (psplit, fld)
                psplit = u", "

            if self.get_iprop(table, 'PRIMARY', "on conflict", '').upper() in ('ROLLBACK', 'ABORT', 'FAIL', 'IGNORE', 'REPLACE'):
                pkstring += u") ON CONFLICT %s)" % self.get_iprop(table, 'PRIMARY', "on conflict", '').upper()

            else:
                pkstring += u"))"

        create_string = u"%s%s"% (create_string, pkstring)
        if self.get_tprop(table, "no rowid") and sqlite3.sqlite_version_info >= (3, 8, 2):
            create_string += u" WITHOUT ROWID"

        self.execute(create_string)
        self.check_indexes(table)

    def check_columns(self, table, clist):
        if not table in self.table_definitions.keys():
            return

        for fld in self.get_fields(table):
            if fld.lower() not in clist.keys():
                if fld in self.get_ifields(table, 'PRIMARY'):
                    if self. print_data_structure:
                        print 'dropping table', table

                    self.execute(u"DROP TABLE IF EXISTS %s" % (table,))
                    self.create_table(table)
                    return

                else:
                    if self. print_data_structure:
                        print '  adding field',  fld, 'to', table

                    self.execute(u"ALTER TABLE %s ADD %s" % (table, self.get_column_string(table, fld)))

    def check_indexes(self, table):
        # (id, name, UNIQUE, c(reate)/u(nique)/p(rimary)k(ey), Partial)
        ilist = {}
        for r in self.fetchall("PRAGMA main.index_list(%s)" % (table,)):
            if (len(r) > 3 and r[3].lower() == 'pk') \
              or r[1][:17] == 'sqlite_autoindex_':
                ilist['%s_primary' % table.lower()] = r

            else:
                ilist[r[1].lower()] = r

        for index in self.get_indexes(table):
            iname = '%s_%s' % (table.lower(), index.lower())
            if iname not in ilist.keys():
                self.add_index(table, index)

            else:
                # Adding Index field test
                if self. print_data_structure:
                    print '    ', ilist[iname]
                    iflds = {}
                    for r in self.fetchall("PRAGMA main.index_info(%s)" % (ilist[iname][1],)):
                        print '      ', r

    def add_index(self, table, index):
        if not index in self.get_indexes(table):
            return

        if self. print_data_structure:
            print '    adding index',  index, 'to', table

        iname = '%s_%s' % (table.lower(), index.lower())
        ustring =u" UNIQUE" if self.get_iprop(table, index, "unique", False) else ""
        istring = u"CREATE%s INDEX IF NOT EXISTS '%s' ON %s" % (ustring, iname, table)
        psplit = u" ("
        for fld in self.get_ifields(table, index):
            istring += u"%s`%s`" % (psplit, fld)
            psplit = u", "

        self.execute(u"%s)" % (istring))

    def run(self):
        time.sleep(1)
        self.state = 1
        self.open_db()
        self.state = 4
        try:
            while True:
                if self.quit and self.cache_request.empty():
                    self.pconn.close()
                    self.state = 0
                    break

                try:
                    crequest = self.cache_request.get(True, 5)

                except Empty:
                    continue

                if (not isinstance(crequest, dict)) or (not 'task' in crequest):
                    continue

                if crequest['task'] == 'query':
                    if not ('parent' in crequest.keys() or 'queue' in crequest.keys()):
                        continue

                    if self.filename == None:
                        # there is no cache, but we have to return something
                        qanswer = None

                    else:
                        for t, v in crequest.items():
                            if t in self.request_list[crequest['task']] or t in self.table_definitions.keys():
                                self.state = 3
                                qanswer = self.query(t, **v)
                                # Because of queue count integrety you can do only one query per call
                                break

                            elif t not in ('task', 'parent', 'queue', 'confirm') and self.config.write_info_files:
                                self.config.infofiles.add_sql('Unknown request', crequest['task'], t, v)

                        else:
                            qanswer = None
                    if 'queue' in crequest.keys():
                        crequest['queue'].put(qanswer)

                    elif 'parent' in crequest.keys():
                        crequest['parent'].cache_return.put(qanswer)

                    self.state = 4
                    continue

                if self.filename == None:
                    # There is no cache
                    continue

                if crequest['task'] == 'add':
                    for t, v in crequest.items():
                        if t in self.request_list[crequest['task']] or t in self.table_definitions.keys():
                            self.state = 3
                            if isinstance(v, (list, tuple)):
                                self.add(t, *v)

                            else:
                                self.add(t, v)

                        elif t not in ('task', 'parent', 'queue', 'confirm') and self.config.write_info_files:
                            self.config.infofiles.add_sql('Unknown request', crequest['task'], t, v)

                if crequest['task'] == 'update':
                    for t, v in crequest.items():
                        if t in self.request_list[crequest['task']] or t in self.table_definitions.keys():
                            self.state = 3
                            self.update(t, **v)

                        elif t not in ('task', 'parent', 'queue', 'confirm') and self.config.write_info_files:
                            self.config.infofiles.add_sql('Unknown request', crequest['task'], t, v)

                if crequest['task'] == 'delete':
                    for t, v in crequest.items():
                        if t in self.request_list[crequest['task']] or t in self.table_definitions.keys():
                            self.state = 3
                            self.delete(t, **v)

                        elif t not in ('task', 'parent', 'queue', 'confirm') and self.config.write_info_files:
                            self.config.infofiles.add_sql('Unknown request', crequest['task'], t, v)

                if crequest['task'] == 'clear':
                    if 'table' in crequest:
                        if crequest['table'] == 'cttvdb':
                            for t in self.request_list['clearttvdb']:
                                self.state = 3
                                self.clear(t)

                        else:
                            for t in crequest['table']:
                                self.state = 3
                                self.clear(t)

                    else:
                        for t in self.request_list[crequest['task']]:
                            self.state = 3
                            self.clear(t)

                    continue

                if crequest['task'] == 'clean':
                    self.state = 3
                    self.clean()
                    continue

                if crequest['task'] == 'quit':
                    self.quit = True
                    continue

                if 'confirm' in crequest.keys():
                    if 'queue' in crequest.keys():
                        crequest['queue'].put(crequest['confirm'])

                    elif 'parent' in crequest.keys():
                        crequest['parent'].cache_return.put(crequest['confirm'])

                self.state = 4

        except:
            self.config.queues['log'].put({'fatal': [traceback.format_exc(), '\n'], 'name': 'ProgramCache'})
            self.ready = True
            self.state = 0
            return(98)

    def query(self, table, **item):
        """
        Updates/gets/whatever.
        """
        def get_ttvdbcredits(*data):
            pp = {}
            for i in data:
                for r in self.fetchall(*make_sql('ttvdbcredits',
                                tid = data_value('tid', i, int, 0),
                                sid = data_value(['sid'], i, int, -1),
                                eid = data_value(['eid'], i, int, -1))):
                    if not r[str('title')] in pp.keys():
                        pp[r[str('title')]] = []

                    if r[str('title')] in ('actor', 'guest'):
                        pp[r[str('title')]].append({'name': r[str('name')], 'role': r[str('role')]})

                    else:
                        pp[r[str('title')]].append( r[str('name')])

            return pp

        def make_sql(table, *select, **where):
            no_validation = where.pop('no_validation', False)
            if not (no_validation or table in self.table_definitions.keys()):
                return []

            if len(select) == 0:
                sqlstr = 'SELECT * FROM %s WHERE' % table

            else:
                sqlstr = 'SELECT'
                for f in select:
                    if no_validation or f in self.field_list[table]:
                        if isinstance(f, tuple):
                            if len(f) > 1:
                                sqlstr = '%s %s.`%s`,' % (sqlstr, f[1], f[0])

                            elif len(f) == 1:
                                sqlstr = '%s `%s`,' % (sqlstr, f[0])

                        else:
                            sqlstr = '%s `%s`,' % (sqlstr, f)

                    elif self.config.write_info_files:
                        self.config.infofiles.add_sql('Unknown select Field', table, f)

                if len(sqlstr) == 7:
                    sqlstr = 'SELECT * FROM %s WHERE' % table

                else:
                    sqlstr = '%s FROM %s WHERE' % (sqlstr[:-1], table)

            if len(where) == 0:
                return [sqlstr[:-6]]

            sqllist = []
            for k, v in where.items():
                if no_validation or k in self.field_list[table]:
                    if isinstance(v, tuple) and len(v) > 1:
                        t = '' if len(v) < 3 else '%s.' % v[2]
                        if v[0] == 'gt':
                            sqlstr = '%s %s`%s` > ? AND' % (sqlstr, t, k)
                            sqllist.append(v[1])

                        elif v[0] == 'ge':
                            sqlstr = '%s %s`%s` >= ? AND' % (sqlstr, t, k)
                            sqllist.append(v[1])

                        elif v[0] == 'lt':
                            sqlstr = '%s %s`%s` < ? AND' % (sqlstr, t, k)
                            sqllist.append(v[1])

                        elif v[0] == 'le':
                            sqlstr = '%s %s`%s` <= ? AND' % (sqlstr, t, k)
                            sqllist.append(v[1])

                        elif v[0] == 'lower':
                            sqlstr = '%s lower(%s`%s`) = ? AND' % (sqlstr, t, k)
                            sqllist.append(v[1])

                        elif v[0] == 'range' and len(v) == 4:
                            if v[1] != None:
                                sqlstr = '%s %s`%s` >= ? AND' % (sqlstr, t, k)
                                sqllist.append(v[1])

                            if v[3] != None:
                                sqlstr = '%s %s`%s` <= ? AND' % (sqlstr, t, k)
                                sqllist.append(v[3])

                        else:
                            sqlstr = '%s %s`%s` = ? AND' % (sqlstr, t, k)
                            sqllist.append(v[1])

                    else:
                        sqlstr = '%s `%s` = ? AND' % (sqlstr, k)
                        sqllist.append(v)

                elif self.config.write_info_files:
                    self.config.infofiles.add_sql('Unknown where Field', table, k, v)

            if len(sqllist) == 0:
                return [sqlstr[:-6]]

            sqlstr = [sqlstr[:-4]]
            sqlstr.extend(sqllist)
            return sqlstr

        if table == 'icon':
            if item.get('sourceid', None) != None and item.get('chanid', None) != None:
                r = self.fetchone(*make_sql('iconsource', 'icon',
                                sourceid = item['sourceid'],
                                chanid = item['chanid']))
                if r == None:
                    return

                return {'sourceid':  item['sourceid'], 'icon': r[0]}

            else:
                r = self.fetchall(*make_sql('iconsource', 'chanid', 'sourceid', 'icon'))
                icons = {}
                if r != None:
                    for g in r:
                        if not g[0] in icons:
                            icons[g[0]] ={}

                        icons[g[0]][g[1]] = g[2]

                return icons

        elif table == 'chan_group':
            if item.get('chanid', None) != None:
                r = self.fetchone(*make_sql('channels', 'cgroup', 'name',
                                chanid = item['chanid']))
                if r == None:
                    return

                return {'cgroup':r[0], 'name': r[1]}

            else:
                r = self.fetchall(*make_sql('channels', 'chanid', 'cgroup', 'name'))
                changroups = {}
                if r != None:
                    for g in r:
                        changroups[g[0]] = {'name': g[2],'cgroup': int(g[1])}

                return changroups

        elif table == 'chan_scid':
            if item.get('sourceid', None) != None:
                if item.get('chanid', None) != None:
                    g = self.fetchone(*make_sql('channelsource', 'scid', 'fgroup',
                                    sourceid = item['sourceid'],
                                    chanid = item['chanid']))
                    if g == None:
                        return

                    return {'channelid': g[0],'group': g[1]}

                elif item.get('fgroup', None) != None:
                    r = self.fetchall(*make_sql('channelsource', 'scid', 'chanid',
                                    sourceid = item['sourceid'],
                                    fgroup = item['fgroup']))
                    fgroup = []
                    if r != None:
                        for g in r:
                            fgroup.append({'chanid': g[1],'channelid': g[0]})

                    return fgroup

                else:
                    r = self.fetchall(*make_sql('channelsource', 'scid', 'chanid', 'name',
                                    sourceid = item['sourceid']))
                    scids = {}
                    if r != None:
                        for g in r:
                            if not g[0] in scids:
                                scids[g[0]] ={}

                            scids[g[0]] = {'chanid': g[1],'name': g[2]}

                    return scids

            elif item.get('chanid', None) != None:
                g = self.fetchone(*make_sql('channelsource', 'sourceid', 'scid', 'fgroup',
                                        chanid = item['chanid']))
                if g == None:
                    return

                return {'sourceid': g[0], 'channelid': g[1],'group': g[2]}

            else:
                r = self.fetchall(*make_sql('channelsource', 'chanid', 'sourceid', 'scid', 'name', 'hd'))
                scids = {}
                if r != None:
                    for g in r:
                        if not g[0] in scids:
                            scids[g[0]] ={}

                        scids[g[0]][g[1]] = {'channelid': g[2],'name': g[3], 'hd': g[4]}

                return scids

        elif table == 'use_alt_url':
            if not 'sourceid'in item.keys():
                return

            r = self.fetchone(*make_sql('sources', 'use_alt_url',
                            sourceid = item['sourceid']))
            if r == None:
                return

            return r[0]

        elif table == 'laststop':
            if item.get('sourceid', None) == None or item.get('channelid', None) == None:
                return

            r = self.fetchone(*make_sql('fetcheddata',
                            sourceid = item['sourceid'],
                            channelid = item['channelid']))
            if r != None:
                laststop = r[str('laststop')]
                if isinstance(laststop, datetime.datetime):
                    return {'laststop': laststop}

                else:
                    return {'laststop': None}

            return None

        elif table == 'ttvdb_aliasses':
            tid = item.get('tid', None)
            if tid == None:
                return []

            r = self.fetchall(*make_sql('ttvdb_alias', 'alias',
                            tid = tid))
            aliasses = []
            if r != None:
                for a in r:
                    aliasses.append( a[0])

            return aliasses

        elif table == 'is_ttvdb_alias':
            if item.get('alias', None) == None:
                return False

            r = self.fetchone(*make_sql('ttvdb_alias', 'tid', 'name',
                            alias = ('lower', item[ 'alias'].lower())))
            if r != None:
                if 'tid' in item.keys():
                    if item['tid'] == r[0]:
                        return True

                elif 'name' in item.keys():
                    if item['name'] == r[1]:
                        return True

                else:
                    return True

            return False

        elif table == 'ttvdb_langs':
            tid = item.get('tid', None)
            if tid == None:
                return []

            langs = []
            for r in self.fetchall(*make_sql('ttvdbint', 'lang',
                            tid = tid)):
                langs.append( r[str('lang')])

            return langs

        elif table == 'ttvdbid':
            if item.get('name', None) == None:
                return []

            tid = self.fetchone(*make_sql('ttvdb_alias', 'tdate', 'tid', 'name',
                            alias = ('lower', item[ 'name'].lower())))
            if tid == None:
                return []

            if tid[0] == 0:
                return [{'tid': 0, 'tdate': tid[1], 'name': tid[2], 'lang': None}]

            return self.query('ttvdbname', tid=tid[0])

        elif table == 'ttvdbname':
            if item.get('tid', None) == None:
                return []

            tlist = []
            for r in self.fetchall(*make_sql('ttvdb JOIN ttvdbint ON ttvdb.tid = ttvdbint.tid',
                    ('tid', 'ttvdb'), 'tdate', ('name', 'ttvdbint'), 'lang',
                            no_validation = True,
                            tid = ('', item['tid'], 'ttvdb'))):
                tlist.append({'tid': r[0], 'tdate': r[1], 'name': r[2], 'lang': r[3]})

            return tlist

        elif table == 'tdate':
            if item.get('date', None) == None:
                return

            r = self.fetchone(*make_sql('ttvdb', 'tdate',
                            tid = item['date']))
            if r == None:
                return

            return r[0]

        elif table == 'ep_by_id':
            tid = data_value('tid', item, int, 0)
            qvals = {'no_validation': True, 'tid': tid}
            if data_value(['sid'], item, int, -1) >= 0:
                qvals['sid'] = item['sid']

            if data_value(['eid'], item, int, -1) >= 0:
                qvals['eid'] = item['eid']

            if data_value(['abseid'], item, int, -1) >= 0:
                qvals['abseid'] = item['abseid']

            if 'lang' in item:
                qvals['lang'] = item['lang']

            r = self.fetchall(*make_sql('episodes JOIN episodesint ' + \
                    'ON episodes.tepid = episodesint.tepid', **qvals))
            if len(r) == 0  and data_value(['lang'], item, str) not in ('en', ''):
                # We try again for english
                qvals = {'no_validation': True, 'tid': tid, 'lang': 'en'}
                if data_value(['sid'], item, int, -1) >= 0:
                    qvals['sid'] = item['sid']

                if data_value(['eid'], item, int, -1) >= 0:
                    qvals['eid'] = item['eid']

                if data_value(['abseid'], item, int, -1) >= 0:
                    qvals['abseid'] = item['abseid']

                r = self.fetchall(*make_sql('episodes JOIN episodesint ' + \
                        'ON episodes.tepid = episodesint.tepid', **qvals))

            series = {tid:{}}
            for s in r:
                tepid = int(s[str('tepid')])
                lang = s[str('lang')]
                if not tepid in series[tid].keys():
                    sid = int(s[str('sid')])
                    eid = int(s[str('eid')])
                    series[tid][tepid] = {'tid': tid,
                                        'tepid': tepid,
                                        'sid': sid,
                                        'eid': eid,
                                        'abseid': int(s[str('abseid')]),
                                        'airdate': s[str('airdate')],
                                        'star-rating': s[str('star-rating')],
                                        'episode title': {},
                                        'description': {}}

                    for k, v in get_ttvdbcredits({'tid': tid},
                            {'tid': tid, 'sid': sid, 'eid': eid}).items():
                        series[tid][tepid][k] = v

                series[tid][tepid]['episode title'][lang] = s[str('episode title')]
                series[tid][tepid]['description'][lang] = s[str('description')]

            return series

        elif table == 'ep_by_title':
            tid = data_value('tid', item, int, 0)
            qvals = {'no_validation': True, 'tid': tid,
                'episode title': ('lower', item['episode title'].lower(), 'episodesint')}
            r = self.fetchall(*make_sql('episodes JOIN episodesint ' + \
                    'ON episodes.tepid = episodesint.tepid', **qvals))
            series = {tid:{}}
            for s in r:
                tepid = int(s[str('tepid')])
                lang = s[str('lang')]
                if not tepid in series[tid].keys():
                    sid = int(s[str('sid')])
                    eid = int(s[str('eid')])
                    series[tid][tepid] = {'tid': tid,
                                        'tepid': tepid,
                                        'sid': sid,
                                        'eid': eid,
                                        'abseid': int(s[str('abseid')]),
                                        'airdate': s[str('airdate')],
                                        'star-rating': s[str('star-rating')],
                                        'episode title': {},
                                        'description': {}}

                    for k, v in get_ttvdbcredits({'tid': tid},
                            {'tid': tid, 'sid': sid, 'eid': eid}).items():
                        series[tid][tepid][k] = v

                series[tid][tepid]['episode title'][lang] = s[str('episode title')]
                series[tid][tepid]['description'][lang] = s[str('description')]

            return series
        elif table == 'fetcheddays':
            if item.get('sourceid', None) == None or item.get('channelid', None) == None:
                return

            rval = {}
            if item.get('scandate', None) == None:
                for r in self.fetchall(*make_sql('fetcheddays', 'scandate', 'stored',
                                sourceid = item['sourceid'],
                                channelid = item['channelid'])):
                    offset = self.date_to_offset(r[str('scandate')])
                    rval[offset] = r[str('stored')]

                return rval

            if isinstance(item["scandate"], (datetime.date, int)):
                item["scandate"] = [item["scandate"]]

            if isinstance(item["scandate"], list):
                for sd in item["scandate"]:
                    if isinstance(sd, int):
                        offset = sd
                        sd = self.offset_to_date(sd)

                    elif isinstance(sd, datetime.date):
                        offset = self.date_to_offset(sd)

                    else:
                        continue

                    r = self.fetchone(*make_sql('fetcheddays', 'stored',
                                    scandate = sd,
                                    sourceid = item['sourceid'],
                                    channelid = item['channelid']))
                    if r == None:
                        rval[offset] = None

                    else:
                        rval[offset] = r[str('stored')]

                return rval

        elif table == 'sources':
            if item.get('sourceid', None) == None:
                return

            r = self.fetchone(*make_sql('sources',
                            sourceid = item['sourceid']))
            if r == None:
                self.add('sources', item)
                r = self.fetchone(*make_sql('sources',
                                sourceid = item['sourceid']))

            rv = {}
            for k in r.keys():
                rv[k] = r[k]

            return rv

        elif table == 'sourceprograms':
            if item.get('sourceid', None) == None or item.get('channelid', None) == None:
                return

            programs = []
            if "scandate" in item.keys():
                if isinstance(item["scandate"], (datetime.date, int)):
                    item["scandate"] = [item["scandate"]]

                if isinstance(item["scandate"], list):
                    for sd in item["scandate"]:
                        if isinstance(sd, int):
                            offset = sd
                            sd = self.offset_to_date(sd)

                        elif not isinstance(sd, datetime.date):
                            continue

                        programs.extend(self.fetchall(*make_sql('sourceprograms',
                                        scandate = sd,
                                        sourceid = item['sourceid'],
                                        channelid = item['channelid'])))

            elif "start-time" in item.keys():
                if isinstance(item["start-time"], datetime.datetime):
                    item["start-time"] = [item["start-time"]]

                if isinstance(item["start-time"], list):
                    for st in item["start-time"]:
                        if not isinstance(st, datetime.datetime):
                            continue

                        programs.extend(self.fetchall(*make_sql('sourceprograms',
                                        **{'start-time': st,
                                        'sourceid': item['sourceid'],
                                        'channelid': item['channelid']})))

            elif "prog_ID" in item.keys():
                if isinstance(item["prog_ID"], (str, unicode)):
                    item["prog_ID"] = [item["prog_ID"]]

                if isinstance(item["prog_ID"], list):
                    for pid in item["prog_ID"]:
                        programs.extend(self.fetchall(*make_sql('sourceprograms',
                                        prog_ID = pid,
                                        sourceid = item['sourceid'],
                                        channelid = item['channelid'])))

            elif "range" in item.keys():
                if isinstance(item['range'], dict):
                    item['range'] = [item['range']]

                if not isinstance(item['range'], (list, tuple)) or len(item['range']) ==0:
                    return programs

                for fr in item['range']:
                    if not isinstance(fr, dict):
                        continue

                    if 'start' in fr.keys() and isinstance(fr['start'], datetime.datetime) and \
                        'stop' in fr.keys() and  isinstance(fr['stop'], datetime.datetime):
                        programs.extend(self.fetchall(*make_sql('sourceprograms',
                                        **{'start-time': ('le',fr['start']),
                                        'stop-time': ('ge', fr['stop']),
                                        'sourceid': item['sourceid'],
                                        'channelid': item['channelid']})))

                    elif 'stop' in fr.keys() and isinstance(fr['stop'], datetime.datetime):
                        programs.extend(self.fetchall(*make_sql('sourceprograms',
                                        **{'stop-time': ('ge', fr['stop']),
                                        'sourceid': item['sourceid'],
                                        'channelid': item['channelid']})))

                    elif 'start' in fr.keys() and isinstance(fr['start'], datetime.datetime):
                        programs.extend(self.fetchall(*make_sql('sourceprograms',
                                        **{'start-time': ('le', fr['start']),
                                        'sourceid': item['sourceid'],
                                        'channelid': item['channelid']})))

            else:
                programs = self.fetchall(*make_sql('sourceprograms',
                                sourceid = item['sourceid'],
                                channelid = item['channelid']))

            programs2 = []
            for p in programs:
                pp = {}
                for key in p.keys():
                    if p[key] == None:
                        continue

                    elif key in self.config.key_values['text'] and isinstance(p[key], (str, unicode)):
                        pp[unicode(key)] = p[key].strip()

                    else:
                        pp[unicode(key)] = p[key]

                for r in self.fetchall(*make_sql('credits',
                                **{'start-time': pp['start-time'],
                                'sourceid': item['sourceid'],
                                'channelid': item['channelid']})):
                    if not r[str('title')] in pp.keys():
                        pp[r[str('title')]] = []

                    if r[str('title')] in ('actor', 'guest'):
                        pp[r[str('title')]].append({'name': r[str('name')], 'role': r[str('role')]})

                    else:
                        pp[r[str('title')]].append( r[str('name')])

                programs2.append(pp)

            return programs2

        elif table == 'programdetails':
            if item.get('sourceid', None) == None or item.get('channelid', None) == None:
                return

            programs = []
            if "prog_ID" in item.keys():
                if isinstance(item["prog_ID"], (str, unicode)):
                    item["prog_ID"] = [item["prog_ID"]]

                if isinstance(item["prog_ID"], list):
                    for sd in item["prog_ID"]:
                        if not isinstance(sd, (str, unicode)):
                            continue

                        p = self.fetchone(*make_sql('programdetails',
                                        prog_ID = sd,
                                        sourceid = item['sourceid'],
                                        channelid = item['channelid']))
                        if p != None:
                            programs.append(p)

            elif "start-time" in item.keys():
                if isinstance(item["start-time"], datetime.datetime):
                    item["start-time"] = [item["start-time"]]

                if isinstance(item["start-time"], list):
                    for st in item["start-time"]:
                        if not isinstance(st, datetime.datetime):
                            continue

                        p = self.fetchone(*make_sql('programdetails',
                                        **{'start-time': st,
                                        'sourceid': item['sourceid'],
                                        'channelid': item['channelid']}))
                        if p != None:
                            programs.append(p)

            else:
                programs = self.fetchall(*make_sql('programdetails',
                                sourceid = item['sourceid'],
                                channelid = item['channelid']))

            programs2 = []
            for p in programs:
                pp = {}
                for key in p.keys():
                    if p[key] == None:
                        continue

                    elif key in self.config.key_values['text'] and isinstance(p[key], (str, unicode)):
                        pp[unicode(key)] = p[key].strip()

                    else:
                        pp[unicode(key)] = p[key]

                for r in self.fetchall(*make_sql('creditdetails',
                                prog_ID = pp['prog_ID'],
                                sourceid = item['sourceid'],
                                channelid = item['channelid'])):

                    if not r[str('title')] in pp.keys():
                        pp[r[str('title')]] = []

                    if r[str('title')] in ('actor', 'guest'):
                        pp[r[str('title')]].append({'name': r[str('name')], 'role': r[str('role')]})

                    else:
                        pp[r[str('title')]].append( r[str('name')])

                programs2.append(pp)

            return programs2

        elif table == 'ttvdb_alias':
            if item.get('alias', None) == None:
                return

            r = self.fetchone(*make_sql('ttvdb_alias', 'tid', 'name',
                            alias = ('lower', item[ 'alias'].lower())))
            if r != None:
                items = self.query('ttvdbname',
                                tid = r[0])
                if len(items) == 0:
                    return [{'tid': r[0], 'tdate': None, 'name': r[1], 'lang': None}]

                else:
                    return items

            else:
                return None

        elif table == 'ttvdb':
            tid = item.get('tid', None)
            if tid == None:
                return []

            r = self.fetchone(*make_sql('ttvdb',
                            tid = tid))
            serie = {tid:{}}
            if r != None:
                for key in r.keys():
                    serie[tid][unicode(key)] = r[key]

                serie[tid]['name'] = {}
                serie[tid]['description'] = {}
                for r in self.fetchall(*make_sql('ttvdbint',
                                tid = tid)):
                    lang = r[str('lang')]
                    serie[tid]['name'][lang]  = r[str('name')]
                    serie[tid]['description'][lang]  = r[str('description')]

                for k, v in get_ttvdbcredits({'tid': tid}).items():
                    serie[tid][k] = v

            return serie

        elif table in self.table_definitions.keys():
            select = data_value(['select'], item, list)
            where = data_value(['where'], item, dict)
            r = self.fetchall(*make_sql(table, *select, **where))
            retvals = []
            if r != None:
                for rec in r:
                    rv = {}
                    for key in rec.keys():
                        rv[unicode(key)] = rec[key]

                    retvals.append(rv)

            return retvals

    def add(self, table, *item):
        def get_value(tbl, fld, **data):
            if fld in data.keys():
                return data[fld]

            elif self.get_fprop(tbl, fld, 'null', False):
                return None

            else:
                return self.get_fprop(tbl, fld, 'default', '')

        def make_add_string(tbl):
            if not tbl in self.field_list:
                return

            sql_flds = u"INSERT INTO %s (`%s`" % (tbl, self.field_list[tbl][0])
            sql_cnt = u"VALUES (?"
            for f in self.field_list[tbl][1:]:
                sql_flds = u"%s, `%s`" % (sql_flds, f)
                sql_cnt = u"%s, ?" % (sql_cnt)

            return u"%s) %s)" % (sql_flds, sql_cnt)

        def make_val_list(tbl, **data):
            if self.config.write_info_files:
                invalid = {}
                for f, v in data.items():
                    if f not in self.field_list[tbl] and f not in ('genres', 'from cache', 'title', 'source', 'channel'):
                        invalid[f] = v

                if len(invalid) > 0:
                    self.config.infofiles.add_sql('Unknown add Fields', tbl, invalid)

            sql_vals = []
            for f in self.field_list[tbl]:
                sql_vals.append(get_value(tbl, f, **data))

            return tuple(sql_vals)

        def get_credits(tbl, **values):
            keyvalues = {}
            credits = []
            for k in self.field_list[tbl]:
                if k in values.keys():
                    keyvalues[k] = values[k]

            for f in self.config.key_values['credits']:
                if f in values.keys():
                    for cr in values[f]:
                        crd = keyvalues.copy()
                        crd['title'] = f
                        crd['role'] = None
                        if isinstance(cr, (str, unicode)):
                            crd['name'] = cr

                        elif isinstance(cr, dict):
                            crd['name'] = cr['name']
                            if 'role' in cr:
                                crd['role'] = cr['role']

                        else:
                            continue

                        credits.append(make_val_list(tbl, **crd))

            return credits

        """
        Adds (or updates) a record
        """
        rec = []
        rec2 = []
        rec3 = []
        rec4 = []
        if table == 'laststop':
            if len(item) == 0:
                return

            item = item[0]
            if not isinstance(item, dict) or not "sourceid" in item.keys() or not "channelid" in item.keys() \
                or not "laststop" in item.keys() or not isinstance(item['laststop'], datetime.datetime):
                return

            laststop = self.query('laststop',
                            sourceid = item['sourceid'],
                            channelid = item['channelid'])
            if laststop == None:
                self.execute(make_add_string('fetcheddata'), make_val_list('fetcheddata', **item))

            elif laststop['laststop'] == None or item['laststop'] > laststop['laststop']:
                self.update('fetcheddata',
                        set={'laststop': item['laststop']},
                        where={'sourceid': item['sourceid'],
                                'channelid': item['channelid']})

        elif table == 'fetcheddays':
            if len(item) == 0:
                return

            item = item[0]
            if not isinstance(item, dict) or not "sourceid" in item.keys() or \
                not "channelid" in item.keys() or not "scandate" in item.keys():
                return

            sdate = self.query('fetcheddays',
                            sourceid = item['sourceid'],
                            channelid = item['channelid'])
            dval = True if not item.get('stored', None) in (True, False) else item['stored']
            if isinstance(item["scandate"], (int, datetime.date)):
                item["scandate"] = [item["scandate"]]

            if isinstance(item["scandate"], list):
                for sd in item["scandate"]:
                    if isinstance(sd, int):
                        sd = self.offset_to_date(sd)

                    if not isinstance(sd, datetime.date):
                        continue

                    if not sd in sdate.keys() or sdate[sd] == None:
                        values = item.copy()
                        values.update(scandate = sd, stored = dval)
                        rec.append(make_val_list('fetcheddays', **values))

                    elif sdate[item["scandate"]] != dval:
                        self.update('fetcheddays',
                                set = {'stored': dval},
                                where = {'scandate': sd,
                                        'sourceid': item['sourceid'],
                                        'channelid': item['channelid']})

                if len(rec) > 0:
                    self.execute(make_add_string('fetcheddays'), *rec)

        elif table == 'sourceprograms':
            for p in item:
                if not isinstance(p, dict):
                    continue

                rec.append(make_val_list('sourceprograms', **p))
                rec2.extend(get_credits('credits', **p))

            if len(rec) > 0:
                self.execute(make_add_string('sourceprograms'), *rec)
                if len(rec2) > 0:
                    self.execute(make_add_string('credits'), *rec2)

        elif table == 'programdetails':
            for p in item:
                if not isinstance(p, dict):
                    continue

                rec.append(make_val_list('programdetails', **p))
                rec2.extend(get_credits('creditdetails', **p))

            if len(rec) > 0:
                self.execute(make_add_string('programdetails'), *rec)
                if len(rec2) > 0:
                    self.execute(make_add_string('creditdetails'), *rec2)

        elif table == 'sources':
            if len(item) == 0:
                return

            item = item[0]
            if isinstance(item, dict) and "sourceid" in item.keys():
                self.execute(make_add_string('sources'), make_val_list('sources', **item))

        elif table == 'channel':
            g = self.query('chan_group')

            for c in item:
                if not c['chanid'] in g.keys():
                    rec.append(make_val_list('channels', **c))

                elif g[c['chanid']]['name'].lower() != c['name'].lower() or \
                        g[c['chanid']]['cgroup'] != c['cgroup'] or \
                        (g[c['chanid']]['cgroup'] == 10 and c['cgroup'] not in (-1, 0, 10)):
                    self.update('channels',
                            set={'cgroup': c['cgroup'],
                                    'name': c['name']},
                            where={'chanid': c['chanid']})

            if len(rec) > 0:
                self.execute(make_add_string('channels'), *rec)

        elif table == 'channelsource':
            scids = self.query('chan_scid')
            for c in item:
                if c['scid'] == '':
                    continue

                if c['chanid'] in scids and c['sourceid'] in scids[c['chanid']]:
                    self.update('channelsource',
                            set={'scid': c['scid'],
                                    'fgroup': c['fgroup'],
                                    'name': c['name'],
                                    'hd': c['hd']},
                            where={'chanid': c['chanid'],
                                    'sourceid': c['sourceid']})

                else:
                    rec.append(make_val_list('channelsource', **c))

            if len(rec) > 0:
                self.execute(make_add_string('channelsource'), *rec)

        elif table == 'icon':
            icons = self.query('icon')
            for ic in item:
                icon = icons.get(ic['chanid'], {}).get(ic['sourceid'], None)
                if icon == None:
                    rec.append(make_val_list('iconsource', **ic))

                elif icon != ic['icon']:
                    self.update('iconsource',
                            set={'icon': ic['icon']},
                            where={'chanid': ic['chanid'],
                                    'sourceid': ic['sourceid']})

            if len(rec) > 0:
                self.execute(make_add_string('iconsource'), *rec)

        elif table == 'ttvdb':
            added_tids = []
            for p in item:
                if not isinstance(p, dict) or not 'tid' in p.keys() or \
                    not 'lang' in p.keys() or not 'name' in p.keys():
                    continue

                p['tdate'] = datetime.date.today()
                if not p['tid'] in added_tids:
                    added_tids.append(p['tid'])
                    rec.append(make_val_list('ttvdb', **p))

                rec2.extend(get_credits('ttvdbcredits', **p))
                rec3.append(make_val_list('ttvdbint', **p))
                for f in self.config.key_values['metadata']:
                    if f in p.keys():
                        sql_vals = make_val_list('ttvdbmetadata',
                                        tid = p['tid'],
                                        type = f,
                                        url = p[f])
                        if not sql_vals in rec4:
                            rec4.append(sql_vals)

            if len(rec) > 0:
                self.execute(make_add_string('ttvdb'), *rec)
                if len(rec2) > 0:
                    self.execute(make_add_string('ttvdbcredits'), *rec2)
                if len(rec3) > 0:
                    self.execute(make_add_string('ttvdbint'), *rec3)
                if len(rec4) > 0:
                    self.execute(make_add_string('ttvdbmetadata'), *rec4)

        elif table == 'ttvdb_alias':
            if len(item) == 0:
                return

            item = item[0]
            if not isinstance(item, dict) or not 'tid' in item.keys():
                return

            if not 'tdate' in item.keys() or item[ 'tdate'] == None:
                item[ 'tdate'] = datetime.date.today()

            aliasses = self.query('ttvdb_aliasses',
                            tid = item['tid'])
            if isinstance(item['alias'], list) and len(item['alias']) > 0:
                for a in set(item['alias']):
                    values = item.copy()
                    values.update(alias = a)
                    rec.append(make_val_list('ttvdb_alias', **values))

            else:
                rec.append(make_val_list('ttvdb_alias', **item))

            if len(rec) > 0:
                self.execute(make_add_string('ttvdb_alias'), *rec)

        elif table == 'episodes':
            added_tepids = []
            for p in item:
                if not isinstance(p, dict) or not 'tid' in p.keys() or \
                    not 'lang' in p.keys() or not 'episode title' in p.keys():
                    continue

                p['tdate'] = datetime.date.today()
                if not p['tepid'] in added_tepids:
                    added_tepids.append(p['tepid'])
                    rec.append(make_val_list('episodes', **p))

                rec2.extend(get_credits('ttvdbcredits', **p))
                rec3.append(make_val_list('episodesint', **p))
                for f in self.config.key_values['metadata']:
                    if f in p.keys():
                        sql_vals = make_val_list('ttvdbmetadata',
                                        tid = p['tid'],
                                        sid = p['sid'],
                                        eid = p['eid'],
                                        type = f,
                                        url = p[f])
                        if not sql_vals in rec4:
                            rec4.append(sql_vals)

            if len(rec) > 0:
                self.execute(make_add_string('episodes'), *rec)
                if len(rec2) > 0:
                    self.execute(make_add_string('ttvdbcredits'), *rec2)
                if len(rec3) > 0:
                    self.execute(make_add_string('episodesint'), *rec3)
                if len(rec4) > 0:
                    self.execute(make_add_string('ttvdbmetadata'), *rec4)

        elif table == 'epcount':
            for p in item:
                if not isinstance(p, dict) or not 'tid' in p.keys() or not 'sid' in p.keys() or not 'count' in p.keys():
                    continue

                rec.append(make_val_list('epcount', **p))

            if len(rec) > 0:
                self.execute(make_add_string('epcount'), *rec)

    def update(self, table, **item):
        if table == 'toggle_alt_url':
            if not 'sourceid'in item.keys():
                return

            uau=self.query('use_alt_url',
                            sourceid = item['sourceid'])
            self.update('sources',
                            set = {'use_alt_url': not uau},
                            where = {'sourceid': item['sourceid']})

        else:
            wfields = item.get('where', None)
            sfields = item.get('set', None)
            if not (table in self.table_definitions.keys() and isinstance(wfields, dict) and isinstance(wfields, dict)):
                self.config.log([self.config.text('IO', 26), '%s:%s\n' % (table, item)])
                return

            w_string =  "WHERE "
            w_list = []
            for k, v in wfields.items():
                if k in self.field_list[table]:
                    w_string = '%s `%s` = ? AND ' % (w_string, k)
                    w_list.append(v)

            s_string = "UPDATE %s SET" % table
            s_list = []
            for k, v in sfields.items():
                if k in self.field_list[table]:
                    s_string = '%s `%s` = ?,' % (s_string, k)
                    s_list.append(v)

            if len(s_list) == 0:
                return

            s_string = '%s %s' % (s_string[:-1], w_string[:-5])
            s_list.extend(w_list)
            self.execute(s_string, tuple(s_list))

    def delete(self, table, **item):
        if table == 'sourceprograms':
            if "sourceid" in item.keys() and "channelid" in item.keys():
                if "scandate" in item.keys():
                    if isinstance(item["scandate"], (datetime.date, int)):
                        item["scandate"] = [item["scandate"]]

                    if isinstance(item["scandate"], list):
                        rec = []
                        for sd in item["scandate"]:
                            if isinstance(sd, int):
                                sd = self.offset_to_date(sd)

                            rec.append((item['sourceid'], item['channelid'], sd))

                        self.execute(u"DELETE FROM fetcheddays " + \
                            "WHERE sourceid = ? AND channelid = ? AND scandate = ?", *rec)
                        self.execute(u"DELETE FROM credits " + \
                            "WHERE sourceid = ? AND channelid = ? AND scandate = ?", *rec)
                        self.execute(u"DELETE FROM sourceprograms " + \
                            "WHERE sourceid = ? AND channelid = ? AND scandate = ?", *rec)

                elif "start-time" in item.keys():
                    if isinstance(item["start-time"], datetime.datetime):
                        item["start-time"] = [item["start-time"]]

                    if isinstance(item["start-time"], list):
                        rec = []
                        for sd in item["start-time"]:
                            if isinstance(sd, datetime.datetime):
                                rec.append((item['sourceid'], item['channelid'], sd))

                        self.execute(u"DELETE FROM credits " + \
                                "WHERE sourceid = ? AND channelid = ? AND `start-time` = ?", *rec)
                        self.execute(u"DELETE FROM sourceprograms " + \
                                "WHERE sourceid = ? AND channelid = ? AND `start-time` = ?", *rec)

                else:
                    self.execute(u"DELETE FROM fetcheddata WHERE sourceid = ? AND channelid = ?",
                        (item['sourceid'], item['channelid']))
                    self.execute(u"DELETE FROM fetcheddays WHERE sourceid = ? AND channelid = ?",
                        (item['sourceid'], item['channelid']))
                    self.execute(u"DELETE FROM credits WHERE sourceid = ? AND channelid = ?",
                        (item['sourceid'], item['channelid']))
                    self.execute(u"DELETE FROM sourceprograms WHERE sourceid = ? AND channelid = ?",
                        (item['sourceid'], item['channelid']))

            elif "sourceid" in item.keys():
                    self.execute(u"DELETE FROM fetcheddata WHERE sourceid = ?",
                        (item['sourceid'], ))
                    self.execute(u"DELETE FROM fetcheddays WHERE sourceid = ?",
                        (item['sourceid'], ))
                    self.execute(u"DELETE FROM credits WHERE sourceid = ?",
                        (item['sourceid'], ))
                    self.execute(u"DELETE FROM sourceprograms WHERE sourceid = ?",
                        (item['sourceid'], ))

            elif "chanid" in item.keys():
                rec = []
                for channelid in self.query('chan_scid',
                                chanid = item["chanid"]):
                    rec.append((channelid['sourceid'], channelid['channelid']))

                if len(rec) > 0:
                    self.execute(u"DELETE FROM fetcheddata WHERE sourceid = ? AND channelid = ?", *rec)
                    self.execute(u"DELETE FROM fetcheddays WHERE sourceid = ? AND channelid = ?", *rec)
                    self.execute(u"DELETE FROM credits WHERE sourceid = ? AND channelid = ?", *rec)
                    self.execute(u"DELETE FROM sourceprograms WHERE sourceid = ? AND channelid = ?", *rec)

        elif table == 'programdetails':
            if not ("sourceid" in item.keys() and "channelid" in item.keys()):
                return

            if "prog_ID" in item.keys():
                if isinstance(item["prog_ID"], (str, unicode)):
                    item["prog_ID"] = [item["prog_ID"]]

                if isinstance(item["prog_ID"], list):
                    rec = []
                    for sd in item["prog_ID"]:
                        rec.append((item['sourceid'], item['channelid'], sd))

                    self.execute(u"DELETE FROM creditdetails " + \
                        "WHERE sourceid = ? AND channelid = ? AND prog_ID = ?", *rec)
                    self.execute(u"DELETE FROM programdetails " + \
                        "WHERE sourceid = ? AND channelid = ? AND prog_ID = ?", *rec)

            elif "start-time" in item.keys():
                if isinstance(item["start-time"], datetime.datetime):
                    item["start-time"] = [item["start-time"]]

                if isinstance(item["start-time"], list):
                    rec = []
                    for sd in item["start-time"]:
                        if isinstance(sd, datetime.datetime):
                            rec.append((item['sourceid'], item['channelid'], sd))

                    self.execute(u"DELETE FROM creditdetails " + \
                        "WHERE sourceid = ? AND channelid = ? AND `start-time` = ?", *rec)
                    self.execute(u"DELETE FROM programdetails " + \
                        "WHERE sourceid = ? AND channelid = ? AND `start-time` = ?", *rec)

            else:
                self.execute(u"DELETE FROM creditdetails WHERE sourceid = ? AND channelid = ?",
                    (item['sourceid'], item['channelid']))
                self.execute(u"DELETE FROM programdetails WHERE sourceid = ? AND channelid = ?",
                    (item['sourceid'], item['channelid']))

        elif table == 'ttvdb':
            with self.pconn:
                self.pconn.execute(u"DELETE FROM ttvdb_alias WHERE tid = ?",  (int(item['tid']), ))
                self.pconn.execute(u"DELETE FROM ttvdb WHERE tid = ?",  (int(item['tid']), ))
                self.pconn.execute(u"DELETE FROM ttvdbint WHERE tid = ?",  (int(item['tid']), ))
                self.pconn.execute(u"DELETE FROM episodesint " + \
                        "WHERE tepid = (SELECT tepid FROM episodes WHERE tid = ?)",  (int(item['tid']), ))
                self.pconn.execute(u"DELETE FROM episodes WHERE tid = ?",  (int(item['tid']), ))
                self.pconn.execute(u"DELETE FROM epcount WHERE tid = ?",  (int(item['tid']), ))
                self.pconn.execute(u"DELETE FROM ttvdbcredits WHERE tid = ?",  (int(item['tid']), ))
                self.pconn.execute(u"DELETE FROM ttvdbmetadata WHERE tid = ?",  (int(item['tid']), ))

    def clear(self, table):
        """
        Clears the table (i.e. empties it)
        """
        self.execute(u"DROP TABLE IF EXISTS %s" % table)
        self.execute(u"VACUUM")
        self.create_table(table)
        self.check_indexes(table)

    def clean(self):
        """
        Removes all cached programming before today.
        And ttvdb ids older then 30 days
        """
        dnow = datetime.datetime.today() - datetime.timedelta(days = 1)
        dttvdb = dnow.date() - datetime.timedelta(days = 29)
        self.execute(u"DELETE FROM sourceprograms " + \
                        "WHERE `scandate` < ? OR `scandate` = ?", (dnow.date(), None))
        self.execute(u"DELETE FROM credits " + \
                        "WHERE `scandate` < ? OR `scandate` = ?", (dnow.date(), None))
        self.execute(u"DELETE FROM programdetails " + \
                        "WHERE `scandate` < ? OR `scandate` = ?", (dnow.date(), None))
        self.execute(u"DELETE FROM creditdetails " + \
                        "WHERE `scandate` < ? OR `scandate` = ?", (dnow.date(), None))
        self.execute(u"DELETE FROM fetcheddays " + \
                        "WHERE `scandate` < ? OR `scandate` = ?", (dnow.date(), None))
        #~ self.execute(u"DELETE FROM ttvdb WHERE tdate < ?", (dttvdb,))

        self.execute(u"VACUUM")

    def execute(self, qstring, *parameters):
        if self.config.write_info_files:
            self.config.infofiles.add_sql('executing', qstring, parameters)

        try:
            if len(parameters) == 0:
                with self.pconn:
                    self.pconn.execute(qstring)

            elif len(parameters) == 1:
                with self.pconn:
                    self.pconn.execute(qstring, parameters[0])

            else:
                with self.pconn:
                    self.pconn.executemany(qstring, parameters)

        except:
            self.config.log([self.config.text('IO', 26), traceback.format_exc(), qstring + '\n'])

    def fetchone(self, qstring, *parameters):
        if self.config.write_info_files:
            self.config.infofiles.add_sql('fetching one', qstring, parameters)

        try:
            pcursor = self.pconn.cursor()
            if len(parameters) == 0:
                pcursor.execute(qstring)

            else:
                pcursor.execute(qstring, parameters)

            return pcursor.fetchone()

        except:
            self.config.log([self.config.text('IO', 26), traceback.format_exc(), qstring + '\n'])

    def fetchall(self, qstring, *parameters):
        if self.config.write_info_files:
            self.config.infofiles.add_sql('fetching all', qstring, parameters)

        try:
            pcursor = self.pconn.cursor()
            if len(parameters) == 0:
                pcursor.execute(qstring)

            else:
                pcursor.execute(qstring, parameters)

            return pcursor.fetchall()

        except:
            self.config.log([self.config.text('IO', 26), traceback.format_exc(), qstring + '\n'])

# end ProgramCache

class InfoFiles():
    """used for gathering extra info to better the code"""
    def __init__(self, config, write_info_files = True):

        self.config = config
        self.functions = self.config.IO_func
        self.write_info_files = write_info_files
        self.info_lock = Lock()
        self.cache_return = Queue()
        self.detail_list = []
        self.raw_list = []
        self.raw_string = ''
        self.fetch_strings = {}
        self.lineup_changes = []
        self.url_failure = []
        self.sql_data = {}
        if self.write_info_files:
            self.fetch_list = self.functions.open_file(self.config.opt_dict['xmltv_dir'] + '/fetched-programs3','w')
            self.raw_output =  self.functions.open_file(self.config.opt_dict['xmltv_dir']+'/raw_output3', 'w')
            self.sqllog = self.functions.open_file('%s/sql.log' % self.config.opt_dict['xmltv_dir'], 'w')

    def check_new_channels(self, source, source_channels):
        if not self.write_info_files or self.config.opt_dict['only_cache'] \
          or source.proc_id in self.config.opt_dict['disable_source']:
            return

        if source.all_channels == {}:
            source.get_channels()

        for channelid, channel in source.all_channels.items():
            if not (channelid in source_channels[source.proc_id].values() or channelid in source.source_data['empty_channels']):
                self.lineup_changes.append( u'New channel on %s => %s (%s)\n' % (source.source, channelid, channel['name']))

        for chanid, channelid in source_channels[source.proc_id].items():
            if not (channelid in source.all_channels.keys() or channelid in source.source_data['empty_channels']):
                self.lineup_changes.append( u'Removed channel on %s => %s (%s)\n' % (source.source, channelid, chanid))

        for channelid in source.source_data['empty_channels']:
            if not channelid in source.all_channels.keys():
                self.lineup_changes.append( u"Empty channelID %s on %s doesn't exist\n" % (channelid, source.source))

        self.lineup_changes.extend(source.lineup_changes)

    def add_sql(self, stype, *data):
        if stype == 'executing':
             if data[0][:6] == 'INSERT':
                 stype = 'insert'

             if data[0][:6] == 'UPDATE':
                 stype = 'update'

             if data[0][:6] == 'DELETE':
                 stype = 'delete'

             #~ if data[0][:] == '':
                 #~ stype = ''

        if not stype in self.sql_data.keys():
            self.sql_data[stype] = []

        self.sql_data[stype].append(data)

    def add_url_failure(self, string):
        self.url_failure.append(string)

    def addto_raw_string(self, string):
        if self.write_info_files:
            with self.info_lock:
                self.raw_string = unicode(self.raw_string + string)

    def write_raw_string(self, string):
        if self.write_info_files:
            with self.info_lock:
                self.raw_string = unicode(self.raw_string + string)
                self.raw_output.write(self.raw_string + u'\n')
                self.raw_output.flush()
                self.raw_string = ''

    def addto_raw_list(self, raw_data = None):

        if self.write_info_files:
            with self.info_lock:
                if raw_data == None:
                    self.raw_list.append(self.raw_string)
                    self.raw_string = ''
                else:
                    self.raw_list.append(raw_data)

    def write_raw_list(self, raw_data = None):

        if (not self.write_info_files) or (self.raw_output == None):
            return

        with self.info_lock:
            if raw_data != None:
                self.raw_list.append(raw_data)

            self.raw_list.sort()
            for i in self.raw_list:
                i = re.sub('\n +?\n', '\n', i)
                i = re.sub('\n+?', '\n', i)
                if i.strip() == '\n':
                    continue

                self.raw_output.write(i + u'\n')

            self.raw_output.flush()
            self.raw_list = []
            self.raw_string = ''

    def addto_detail_list(self, detail_data):

        if self.write_info_files:
            with self.info_lock:
                self.detail_list.append(detail_data)

    def write_fetch_list(self, programs, chanid = None, source = None, chan_name = '', group_slots = None):
        def value(vname):
            if vname == 'ID':
                if 'prog_ID' in tdict:
                    return tdict['prog_ID']

                return '---'

            if vname == 'from cache':
                if 'from cache' in tdict and tdict['from cache']:
                    return '*'

                return ''

            if not vname in tdict.keys():
                return '--- '

            if isinstance(tdict[vname], datetime.datetime):
                if vname == 'start-time' and 'is_gs' in tdict:
                    return u'#%s' % self.config.in_output_tz(tdict[vname]).strftime('%d %b %H:%M')

                else:
                    return self.config.in_output_tz(tdict[vname]).strftime('%d %b %H:%M')

            if isinstance(tdict[vname], bool):
                if tdict[vname]:
                    return 'True '

                return 'False '

            return tdict[vname]

        if (not self.write_info_files) or (self.fetch_list == None):
            return

        with self.info_lock:
            if isinstance(programs, tv_grab_channel.ChannelNode):

                if source in self.config.channelsource.keys():
                    sname = self.config.channelsource[source].source

                else:
                    sname = source

                fstr = u' (%3.0f/%2.0f/%2.0f) after merging from: %s\n' % \
                    (programs.program_count(), len(programs.group_slots), \
                    len(programs.program_gaps),sname)

                for pnode in programs:
                    fstr += u'  %s: [%s][%s] [%s:%s/%s] %s; %s %s\n' % (\
                                    pnode.get_start_stop(), \
                                    pnode.get_value('ID').rjust(15), \
                                    pnode.get_value('genre')[0:10].rjust(10), \
                                    pnode.get_value('season'), \
                                    pnode.get_value('episode'), \
                                    pnode.get_value('episodecount'), \
                                    pnode.get_title(), \
                                    pnode.get_value('country'), \
                                    pnode.get_value('rating'))

                    if pnode.next_gap != None:
                        fstr += u'  %s: GAP %s minuten\n' % \
                            (pnode.next_gap.get_start_stop(), pnode.next_gap.length.total_seconds()/60)

            else:
                plist = deepcopy(programs)
                if group_slots != None:
                    pgs = deepcopy(group_slots)
                    fstr = u' (%3.0f/%2.0f) from: %s\n' % \
                        (len(plist), len(pgs), self.config.channelsource[source].source)
                    if len(pgs) > 0:
                        for item in pgs:
                            item['is_gs'] = True

                        plist.extend(pgs)

                else:
                    fstr = u' (%3.0f) from: %s\n' % (len(plist),  self.config.channelsource[source].source)

                plist.sort(key=lambda program: (program['start-time']))

                for tdict in plist:
                    extra = value('rerun') + value('teletext') + value('new') + value('last-chance') + value('premiere')
                    extra2 = value('HD') + value('widescreen') + value('blackwhite')

                    fstr += u'  %s%s - %s: [%s][%s] [%s:%s/%s] %s: %s; %s %s\n' % (\
                                    value('from cache'), value('start-time'), value('stop-time'), \
                                    value('ID').rjust(15), value('genre')[0:10].rjust(10), \
                                    value('season'), value('episode'), value('episodecount'), \
                                    value('name'), value('episode title'), \
                                    value('country'), value('rating'))

            if not chanid in  self.fetch_strings:
                 self.fetch_strings[chanid] = {}
                 self.fetch_strings[chanid]['name'] = u'Channel: (%s) %s\n' % (chanid, chan_name)

            if source in self.config.channelsource.keys():
                if not source in  self.fetch_strings[chanid]:
                    self.fetch_strings[chanid][source] = fstr

                else:
                    self.fetch_strings[chanid][source] += fstr

            elif not 'channels' in self.fetch_strings[chanid]:
                self.fetch_strings[chanid]['channels'] = fstr

            else:
                self.fetch_strings[chanid]['channels'] += fstr

    def write_xmloutput(self, xml):

        if self.write_info_files:
            xml_output =self.functions.open_file(self.config.opt_dict['xmltv_dir']+'/xml_output3', 'w')
            if xml_output == None:
                return

            xml_output.write(xml)
            xml_output.close()

    def close(self, channels, combined_channels, sources):
        if not self.write_info_files:
            return

        if self.config.opt_dict['mail_info_address'] == None:
            self.config.opt_dict['mail_info_address'] = self.config.opt_dict['mail_log_address']

        if self.config.opt_dict['mail_log'] and len(self.lineup_changes) > 0:
            self.config.logging.send_mail(self.lineup_changes, self.config.opt_dict['mail_info_address'], '%s lineup changes' % self.config.name)

        if self.config.opt_dict['mail_log'] and len(self.url_failure) > 0:
            self.url_failure.sort()
            self.config.logging.send_mail(self.url_failure, self.config.opt_dict['mail_info_address'],
                '%s url failures' % self.config.name)

        if self.fetch_list != None:
            chan_list = []
            combine_list = []
            for chanid in channels.keys():
                if (channels[chanid].active or channels[chanid].is_child) and chanid in self.fetch_strings:
                    if chanid in combined_channels.keys():
                        combine_list.append(chanid)

                    else:
                        chan_list.append(chanid)

            chan_list.extend(combine_list)
            for chanid in chan_list:
                self.fetch_list.write(self.fetch_strings[chanid]['name'])
                for s in channels[chanid].merge_order:
                    if s in self.fetch_strings[chanid].keys():
                        self.fetch_list.write(self.fetch_strings[chanid][s])

                if chanid in combined_channels.keys() and 'channels' in self.fetch_strings[chanid]:
                    self.fetch_list.write(self.fetch_strings[chanid]['channels'])

            self.fetch_list.close()

        if self.raw_output != None:
            self.raw_output.close()

        if self.sqllog != None:
            if 'Unknown request' in self.sql_data.keys():
                data = self.sql_data['Unknown request']
                data.sort()
                self.sqllog.write('Unknown requests\n')
                for d in data:
                    self.sqllog.write('    "%s": "%s": %s\n' % d)

            if 'Unknown select Field' in self.sql_data.keys():
                data = self.sql_data['Unknown select Field']
                data.sort()
                self.sqllog.write('Unknown select Field\n')
                for d in data:
                    self.sqllog.write('    "%s".%s\n' % d)

            if 'Unknown where Field' in self.sql_data.keys():
                data = self.sql_data['Unknown where Field']
                data.sort()
                self.sqllog.write('Unknown where Field\n')
                for d in data:
                    self.sqllog.write('    "%s"."%s" = %s\n' % d)

            if 'Unknown add Fields' in self.sql_data.keys():
                data = self.sql_data['Unknown add Fields']
                data.sort()
                self.sqllog.write('Unknown add Fields\n')
                for d in data:
                    for f, v in d[1].items():
                        self.sqllog.write('    "%s"."%s" = %s\n' % (d[0], f, v))

            if 'fetching one' in self.sql_data.keys():
                data = self.sql_data['fetching one']
                data.sort()
                self.sqllog.write('Query Single Records\n')
                for d in data:
                    self.sqllog.write('    "%s"\n        %s\n' % d)

            if 'fetching all' in self.sql_data.keys():
                data = self.sql_data['fetching all']
                data.sort()
                self.sqllog.write('Query All Record\n')
                for d in data:
                    self.sqllog.write('    "%s"\n        %s\n' % d)

            if 'insert' in self.sql_data.keys():
                data = self.sql_data['insert']
                data.sort()
                self.sqllog.write('Inserting Record\'s\n')
                for d in data:
                    try:
                        self.sqllog.write('    "%s"\n' % d[0])
                        for v in d[1]:
                            self.sqllog.write('        %s\n' % (v, ))

                    except:
                        self.sqllog.write('%s\n' % (traceback.format_exc(), ))

            if 'update' in self.sql_data.keys():
                data = self.sql_data['update']
                data.sort()
                self.sqllog.write('Updating Record\n')
                for d in data:
                    try:
                        self.sqllog.write('    "%s"\n' % d[0])
                        for v in d[1]:
                            self.sqllog.write('        %s\n' % (v, ))

                    except:
                        self.sqllog.write('%s\n' % (traceback.format_exc(), ))

            if 'delete' in self.sql_data.keys():
                data = self.sql_data['delete']
                data.sort()
                self.sqllog.write('Deleting Record(s)\'s\n')
                for d in data:
                    try:
                        self.sqllog.write('    "%s"\n' % d[0])
                        for v in d[1]:
                            self.sqllog.write('        %s\n' % (v, ))

                    except:
                        self.sqllog.write('%s\n' % (traceback.format_exc(), ))

            if 'executing' in self.sql_data.keys():
                data = self.sql_data['executing']
                data.sort()
                self.sqllog.write('Executing\n')
                for d in data:
                    self.sqllog.write('    "%s"\n        %s\n' % d)

            self.sqllog.close()

        if len(self.detail_list) > 0:
            f = self.functions.open_file(self.config.opt_dict['xmltv_dir']+'/detail_output3')
            if (f != None):
                f.seek(0,0)
                for byteline in f.readlines():
                    line = self.functions.get_line(f, byteline, False)
                    if line:
                        self.detail_list.append(line)

                f.close()

            f = self.functions.open_file(self.config.opt_dict['xmltv_dir']+'/detail_output3', 'w')
            if (f != None):
                ds = set(self.detail_list)
                ds = set(self.detail_list)
                tmp_list = []
                tmp_list.extend(ds)
                tmp_list.sort()
                for i in tmp_list:
                    f.write(u'%s\n' % i)

                f.close()

# end InfoFiles

class DD_Convert(DataDef_Convert):
    def __init__(self, config, data_def = None, warnaction = "default", warngoal = sys.stderr, caller_id = 0):
        self.config = config
        DataDef_Convert.__init__(self, data_def, warnaction, warngoal, caller_id)

    def convert_sourcefile(self, source_data, cattrans_type = None, file_name = None):
        with self.tree_lock:
            self.empty_values = data_value("empty-values", source_data, list, [None, "", "-"])
            self.csource_data = {}
            self.csource_data["dtversion"] = self.dtversion()
            self.csource_data["tvgversion"] = tuple(self.config.version(False, True)[1:4])
            efa = data_value("enable for api", source_data, list)
            self.csource_data["enable for api"] = []
            for av in efa:
                self.csource_data["enable for api"].append(tuple(av))

            efa = data_value("disable for api", source_data, list)
            self.csource_data["disable for api"] = []
            for av in efa:
                self.csource_data["disable for api"].append(tuple(av))

            self.csource_data["file-name"] = data_value("file-name", source_data, str)
            self.csource_data["name"] = data_value("name", source_data, str)
            self.csource_data["language"] = data_value("language", source_data, str, "en")
            try:
                self.csource_data["site-timezone"] = data_value("site-timezone", source_data, str, "utc")
                self.csource_data["site-tz"] = pytz.timezone(self.csource_data['site-timezone'])

            except:
                self.csource_data["site-timezone"] = "utc"
                self.csource_data["site-tz"] = pytz.utc

            self.csource_data["version"] = data_value("version", source_data, int)
            self.csource_data["api-version"] = tuple(data_value("api-version", source_data, list, [1,0,0]))
            if self.csource_data["name"] in ("thetvdb.v1", "thetvdb.v2"):
                for ptype in self.config.data_def_names[self.csource_data["name"]]:
                    if is_data_value([ptype, "data", "key-path"], source_data, list) or \
                      is_data_value([ptype, "data", "iter"], source_data, list):
                        source_data[ptype]["timezone"] = self.csource_data["site-timezone"]
                        self.convert_data_def(data_value(ptype, source_data, dict), include_url = True, include_links = True)
                        self.csource_data[ptype] = deepcopy(self.cdata_def)
                        self.csource_data[ptype]["empty-values"] = self.empty_values
                        self.csource_data[ptype]["default-item-count"]
                        self.csource_data["lang-list"] = data_value("lang-list", source_data, list)

            else:
                self.csource_data["detail_processor"] = data_value("detail_processor", source_data, bool, False)
                self.csource_data["is_virtual"] = data_value("is_virtual", source_data, bool, False)
                self.csource_data["without-full-timings"] = data_value("without-full-timings", source_data, bool, False)
                self.csource_data["night-date-switch"] = data_value("night-date-switch", source_data, int, 0)
                self.csource_data["no_genric_matching"] = data_value("no_genric_matching", source_data, list)
                self.csource_data["empty_channels"] = data_value("empty_channels", source_data, list)
                self.csource_data["alt-channels"] = data_value("alt-channels", source_data, dict)
                self.csource_data["rating"] = data_value("rating", source_data, dict)
                self.csource_data["cattrans"] = {}
                if cattrans_type == 1:
                    for k, v in data_value("cattrans", source_data, dict).items():
                        k = k.lower().strip()
                        if isinstance(v, dict):
                            self.csource_data["cattrans"][k] ={}
                            for k2, gg in v.items():
                                k2 = k2.lower().strip()
                                self.csource_data["cattrans"][k][k2] = gg

                elif cattrans_type == 2:
                    self.csource_data["cattrans_keywords"] = data_value("cattrans_keywords", source_data, dict)
                    for k, v in data_value("cattrans", source_data, dict).items():
                        k = k.lower().strip()
                        self.csource_data["cattrans"][k] = v

                self.csource_data["channel_list"] = {}
                self.csource_data["data_defs"] = []
                self.csource_data["channel_defs"] = []
                self.csource_data["base_defs"] = []
                self.csource_data["detail_defs"] = []
                self.csource_data["alt-url-code"] = data_value(['alt-url-code'], source_data, int, None)
                self.csource_data["base"] = {}
                self.csource_data["base"]["value-filters"] = {}
                for ptype, ddl in (("channels", "channel_defs"),
                        ("base-channels", "channel_defs"),
                        ("base", "base_defs"),
                        ("detail", "detail_defs"),
                        ("detail2", "detail_defs")):
                    if is_data_value([ptype, "data", "key-path"], source_data, list) or \
                      is_data_value([ptype, "data", "iter"], source_data, list):
                        source_data[ptype]["timezone"] = self.csource_data["site-timezone"]
                        self.convert_data_def(data_value(ptype, source_data, dict), include_url = True, include_links = True)
                        self.csource_data[ptype] = deepcopy(self.cdata_def)
                        self.csource_data[ddl].append(ptype)
                        self.csource_data["data_defs"].append(ptype)
                        self.csource_data[ptype]["empty-values"] = self.empty_values
                        del self.csource_data[ptype]["default-item-count"]
                        self.csource_data[ptype]['normal-url'] = self.csource_data[ptype]['url']
                        if is_data_value(['alt-url-code'], source_data) and is_data_value([ptype, 'alt-url'], source_data):
                            self.csource_data[ptype]['alt-url'] = source_data[ptype]['alt-url']

                        else:
                            self.csource_data[ptype]['alt-url'] = self.csource_data[ptype]['url']

                        if ptype == "base":
                            self.csource_data[ptype]["max days"] = data_value([ptype, "max days"], source_data, int, 14)
                            if self.cdata_def["url-type"] & 3 == 3:
                                self.csource_data[ptype]["url-channel-groups"] = \
                                    data_value([ptype, "url-channel-groups"], source_data, list)

                            if self.cdata_def["url-type"] & 12 == 0:
                                self.csource_data[ptype]["data"]["today"] = \
                                    self.convert_path_def(data_value([ptype, "data", "today"], \
                                    source_data, list), self.ddtype, self.dtc.pathWithValue)

                                self.csource_data[ptype]["data"]["date-check"] = \
                                    self.convert_path_def(data_value([ptype, "data", "date-check"], \
                                    source_data, list), self.ddtype, self.dtc.pathWithValue)

                            if self.cdata_def["url-type"] & 12 == 8:
                                self.csource_data[ptype]["url-date-range"] = \
                                    data_value([ptype, "url-date-range"], source_data, (str, int))

                                self.csource_data[ptype]["url-date-week-start"] = \
                                    data_value([ptype, "url-date-week-start"], source_data, (str, int))

                            if self.cdata_def["url-type"] & 12 == 12:
                                self.csource_data[ptype]["default-item-count"] = \
                                    data_value([ptype, "default-item-count"], source_data, int, 0)

                                self.csource_data[ptype]["data"]["total-item-count"] = \
                                    self.convert_path_def(data_value([ptype, "data", "total-item-count"], \
                                    source_data, list), self.ddtype, self.dtc.pathWithValue)

                                self.csource_data[ptype]["data"]["page-item-count"] = \
                                    self.convert_path_def(data_value([ptype, "data", "page-item-count"], \
                                    source_data, list), self.ddtype, self.dtc.pathWithValue)

                        if ptype in self.config.data_def_names["detail"]:
                            self.csource_data[ptype]["provides"] = data_value([ptype, "provides"], source_data, list)
                            self.csource_data[ptype]["update-base"] = data_value([ptype, "update-base"], source_data, list)

                if not "channels" in self.csource_data["channel_defs"] and is_data_value(["channels", "data"], source_data, dict):
                    self.csource_data["channel_list"] = data_value(["channels", "data"], source_data, dict)
                    self.csource_data["channel_defs"].append("channel_list")

                if len(self.csource_data["detail_defs"]) == 0:
                    self.csource_data["detail_processor"] = False

            if file_name != None:
                self.store_cdata_def(file_name, self.csource_data)

# end DD_Convert()

class test_JSON(test_json_struct.test_JSON):
    def __init__(self, name = 'tv_grab_test'):
        self.config = tv_grab_config.Configure(name)
        self.config.test_modus = True
        self.config.get_json_datafiles()
        test_json_struct.test_JSON.__init__(self)

    def log(self, text):
        self.config.log(text)

    def add_extra_lookup_lists(self, struct_name):
        if struct_name == 'struct-grabberfile':
            ilids = self.config.xml_output.logo_provider.keys()[:]
            slids = []
            for li in ilids:
                slids.append(unicode(li))

            if 'lst-logoid' in self.lookup_lists.keys():
                self.lookup_lists['lst-logoid'].extend(ilids)

            else:
                 self.lookup_lists['lst-logoid'] = ilids

            self.lookup_lists['lst-logoid'].extend(slids)
            if 'int-lst-logoid' in self.lookup_lists.keys():
                self.lookup_lists['int-lst-logoid'].extend(ilids)

            else:
                 self.lookup_lists['int-lst-logoid'] = ilids

            if 'str-lst-logoid' in self.lookup_lists.keys():
                self.lookup_lists['str-lst-logoid'].extend(slids)

            else:
                 self.lookup_lists['str-lst-logoid'] = slids
# end test_JSON

class test_Source():
    def __init__(self):
        self.test_json = test_JSON('tv_grab_test')
        self.config = self.test_json.config
        self.conv_dd = DD_Convert(self.config)
        self.cache_return = Queue()
        self.no_config = True
        self.lineup = None
        self.opt_dict = {}
        self.opt_dict['grabber_name'] = ''
        self.opt_dict['source_dir'] = u'%s/sources' % self.config.opt_dict['xmltv_dir']
        self.opt_dict['grabber_file_dir'] = ''
        self.opt_dict['report_dir'] = u'%s/tv_grab_output' % self.config.opt_dict['home_dir']
        self.opt_dict['tree_file'] = 'datatree.txt'
        self.opt_dict['parse_file'] = 'dataparse.txt'
        self.opt_dict['test_modus'] = 'channels'
        self.opt_dict['sourceid'] = 1
        self.opt_dict['chanid'] = ''
        self.opt_dict['offset'] = 0
        self.opt_dict['detailid'] = ''
        self.opt_dict['report_level'] = 511
        self.opt_dict[''] = ''

        self.config.write_info_files = True
        self.config.only_local_sourcefiles = True
        self.source = None

    def test_source(self):
        try:
            if self.read_commandline() != None:
                return(0)

            x = self.get_config()
            if x > 0:
                self.config.log('Errors were encountered. See %s/test-%s.txt and the log\n' % (self.opt_dict['report_dir'], self.opt_dict['grabber_name']))
                return(x)

            if self.args.config_file:
                self.config.log('Creating %s/.json_struct/tv_grab_test.conf\n' % self.config.opt_dict['home_dir'])
                return(self.make_config())

            if self.args.version:
                self.config.validate_option('version')
                return(0)

            self.config.opt_dict['log_level'] = self.config.opt_dict['log_level'] | 98304
            self.config.get_json_datafiles(self.opt_dict['grabber_name'], False, True)
            for (a, o) in ((self.args.show_sources, 'show_sources'), \
                                  (self.args.show_logo_sources, 'show_logo_sources'), \
                                  (self.args.show_detail_sources, 'show_detail_sources')):
                if a:
                    self.config.validate_option(o)
                    return(0)

            self.config.program_cache = ProgramCache(self.config, self.config.opt_dict['cache_file'])
            self.config.program_cache.start()
            if self.opt_dict['test_modus'] == 'lineup':
                pass

            else:
                sid = self.opt_dict['sourceid']
                if not sid in self.config.sources.keys():
                    self.config.log('Source %d is not defined!\n')
                    return(1)

                source_name = self.config.sources[sid]["json file"]
                x = self.test_jsonfile(self.opt_dict['source_dir'], source_name)
                if x > 0:
                    self.config.log('Errors were encountered. See %s/test-%s.txt\n' % (self.opt_dict['report_dir'], source_name))
                    return(x)

                # Load the source
                self.source = self.config.init_sources(sid)
                self.config.channelsource[sid] = self.source
                #~ self.source.print_tags = True
                self.source.print_roottree = True
                self.source.show_parsing = True
                self.source.print_searchtree = True
                self.source.show_result = True
                self.source.init_channel_source_ids()
                self.test_conversion()
                if self.opt_dict['test_modus'] == 'channels':
                    if not 'channels' in self.test_json.found_data_defs and not 'base-channels' in self.test_json.found_data_defs:
                        self.config.log('There is no "channels" or "base-channels" data_def found in %s to test with!\n' % source_name)
                        return(1)

                elif self.opt_dict['test_modus'] == 'base':
                    if not 'base' in self.test_json.found_data_defs and not 'base_detailed' in self.test_json.found_data_defs:
                        self.config.log('There is no "base" data_def found in %s to test with!\n' % source_name)
                        return(1)

                elif self.opt_dict['test_modus'] == 'detail':
                    if not sid in self.config.detail_sources:
                        self.config.log('You try to test a detail-page, but the %s source is not listed as a detailsource!\n' % source_name)
                        return(1)

                    elif not 'detail' in self.test_json.found_data_defs:
                        self.config.log('There is no "detail" data_def found in %s to test with!\n' % source_name)
                        return(1)

                elif self.opt_dict['test_modus'] not in ('lineup', ):
                    self.config.log('Please select a valid test_modus!')
                    return(0)

            self.open_output()
            if self.opt_dict['test_modus'] == 'channels':
                return self.test_channels()

            elif self.no_config:
                self.config.log(['If you want to run the %s test\n' % self.opt_dict['test_modus'],
                    '  you need an accessible configuration file in %s\n' % self.config.opt_dict['xmltv_dir']])
                return(1)

            elif self.opt_dict['test_modus'] == 'base':
                return self.test_base()

            elif self.opt_dict['test_modus'] == 'detail':
                return self.test_detail()

            elif self.opt_dict['test_modus'] == 'lineup':
                self.test_lineup()

        except:
            self.config.log(['Some unexpected error ocurred.\n', traceback.format_exc()])
            return(1)

    def test_conversion(self):
        fle = self.config.IO_func.open_file('%s/conv-%s.txt' % \
            (self.opt_dict['report_dir'], self.source.name), 'w')

        if is_data_value("dtversion", self.source.source_data, tuple):
            self.conv_dd.write_cdata_def(fle, self.source.source_data)

        else:
            self.conv_dd.convert_sourcefile(self.source.source_data, self.source.cattrans_type)
            self.conv_dd.write_cdata_def(fle)

        fle.close()

    def test_channels(self):
        self.source.init_channel_source_ids()
        self.source.get_channels()
        self.config.infofiles.check_new_channels(self.source, self.config.source_channels)
        for line in self.config.infofiles.lineup_changes:
            self.lineup.write(line)

        self.config.infofiles.lineup_changes = []
        self.config.log('See %s for the results.\n' % self.opt_dict['report_dir'])
        return(0)

    def test_base(self):
        self.config.opt_dict['days'] = 1
        maxdays = self.source.data_value(["base", "max days"], int, default = 14)
        if self.opt_dict['offset'] >= maxdays:
            self.config.log('The given offset is higher then the for the source set maximum.\n  Setting it to 0.\n')
            self.opt_dict['offset'] = 0
            self.config.opt_dict['offset'] = 0

        if self.opt_dict['chanid'] not in self.config.channels.keys():
            self.config.log('The requested chanid "%s" does not exist!\n' % self.opt_dict['chanid'])
            return(0)

        for chanid, channel in self.config.channels.items():
            if chanid == self.opt_dict['chanid']:
                channel.active = True
                channelid = channel.get_channelid(self.source.proc_id)
                if channelid == '':
                    self.config.log('The requested chanid "%s" does not exist on this source!\n' % self.opt_dict['chanid'])
                    return(0)

            else:
                channel.active = False

        self.source.init_channel_source_ids()
        self.config.queues['cache'].put({'task':'query', 'parent': self,
            'chan_scid': {'sourceid': self.source.proc_id, 'chanid': self.opt_dict['chanid']}})
        channelgrp = data_value('group',self.cache_return.get(True), str)
        pdata = {'channels': self.source.channels,
                    'channel': channelid,
                    'channelgrp': channelgrp,
                    'offset': self.opt_dict['offset'],
                    'start': self.opt_dict['offset'],
                    'end': self.opt_dict['offset'] + 1,
                    'back': -self.opt_dict['offset'],
                    'ahead': self.opt_dict['offset']}
        self.source.get_page_data('base', **pdata)
        self.source.parse_basepage(self.source.data, **pdata)
        self.config.log('See %s for the results.\n' % self.opt_dict['report_dir'])
        return(0)

    def test_detail(self):
        if self.opt_dict['detailid'] == '':
            self.config.log('You did not provide a detailid to test the detail-page with.\n Extracting a base-page.\n\n')
            if self.test_base() > 0 or self.source.data == None:
                return(1)

            self.config.log('\nSelect one of the programs to use for testing:\n', log_target = 1)
            counter = 0
            detailids = {}
            for p in self.source.data:
                for k in ('detail_url', 'name', 'start-time', 'channelid'):
                    if not k in p.keys():
                        break

                else:
                    if p['channelid'] != self.config.channels[self.opt_dict['chanid']].get_channelid(self.source.proc_id):
                        continue
                    counter += 1
                    detailids[counter] = p['detail_url']
                    self.config.log('[%3.0f] %s: %s\n' % (counter, self.config.in_output_tz(p['start-time']).strftime('%d %b %H:%M'), p['name']), log_target = 1)

            try:
                while True:
                    n = ''
                    k = ''
                    while k != '\n':
                        if k in '0123456789':
                            n+=k

                        k = sys.stdin.read(1)

                    try:
                        n = int(n)
                        if 0 < n <= counter:
                            break

                        self.config.log('Please give a valid value\n', log_target = 1)

                    except:
                        self.config.log('Please give a valid integer value\n', log_target = 1)

            except:
                return(1)

            self.opt_dict['detailid'] = detailids[n]
            self.close_output()
            self.open_output()

        pdata = {}
        pdata['chanid'] = self.opt_dict['chanid']
        pdata['channelid'] = pdata['chanid']
        if self.opt_dict['chanid'] in self.config.channels.keys():
            pdata['channelid'] = self.config.channels[self.opt_dict['chanid']].get_channelid(self.source.proc_id)

        pdata['detail_url'] = self.opt_dict['detailid']
        self.source.load_detailpage('detail', pdata)
        self.config.log('See %s for the results.\n' % self.opt_dict['report_dir'])
        return(0)

    def test_lineup(self):
        self.config.infofiles.lineup_changes = []
        for sid, source in self.config.sources.items():
            source_name = source["json file"]
            if self.test_jsonfile(self.opt_dict['source_dir'], source_name) > 0:
                self.config.log('Errors were encountered. See %s/test-%s.txt\n' % (self.opt_dict['report_dir'], source_name))
                continue

            self.source = self.config.init_sources(sid)
            self.config.channelsource[sid] = self.source
            self.source.init_channel_source_ids()
            self.source.get_channels()
            self.config.infofiles.check_new_channels(self.source, self.config.source_channels)

        for line in self.config.infofiles.lineup_changes:
            self.lineup.write(line)

        self.config.infofiles.lineup_changes = []
        self.config.log('See %s for the results.\n' % self.opt_dict['report_dir'])
        return(0)

    def get_config(self):
        f = self.config.IO_func.open_file('%s/.json_struct/tv_grab_test.conf' % self.config.opt_dict['home_dir'])
        if f != None:
            # Read the configuration into the self.config_dict dictionary
            for byteline in f.readlines():
                try:
                    line = self.config.IO_func.get_line(f, byteline)
                    if not line:
                        continue

                    a = re.split('=',line)
                    if len(a) != 2:
                        continue

                    cfg_option = a[0].lower().strip()
                    if cfg_option in ('source_dir', 'grabber_file_dir', 'grabber_name', 'test_modus', 'chanid', 'report_dir'):
                        self.opt_dict[cfg_option] = unicode(a[1]).strip()

                    if cfg_option in ('sourceid', 'offset'):
                        self.opt_dict[cfg_option] = int(a[1])

                except:
                    pass

            f.close()

        for (a, o) in ((self.args.source_dir, 'source_dir'), \
                              (self.args.grabber_name, 'grabber_name'), \
                              (self.args.test_modus, 'test_modus'), \
                              (self.args.report_dir, 'report_dir'), \
                              (self.args.report_level, 'report_level'), \
                              (self.args.offset, 'offset'), \
                              (self.args.sourceid, 'sourceid'), \
                              (self.args.detailid, 'detailid'), \
                              (self.args.chanid, 'chanid')):
            if a != None:
                self.opt_dict[o] = a

        if not os.path.exists(self.opt_dict['report_dir']):
            os.mkdir(self.opt_dict['report_dir'])

        if self.opt_dict['grabber_name'] in ('', None):
            return(1)

        if self.opt_dict['grabber_name'] == 'tv_grab_nl':
            self.config.opt_dict['config_file'] = u'%s/%s3_py.conf' % (self.config.opt_dict['xmltv_dir'], self.opt_dict['grabber_name'])

        else:
            self.config.opt_dict['config_file'] = u'%s/%s_py.conf' % (self.config.opt_dict['xmltv_dir'], self.opt_dict['grabber_name'])

        self.config.opt_dict['log_file'] = '%s/tv_grab_test.log' % (self.opt_dict['report_dir'])
        if self.config.validate_option('config_file') == None:
            self.no_config = False

        if self.opt_dict['grabber_file_dir'] == '':
            self.opt_dict['grabber_file_dir'] = self.opt_dict['source_dir']

        return self.test_jsonfile(self.opt_dict['grabber_file_dir'], self.opt_dict['grabber_name'])

    def make_config(self):
        try:
            # check for the config dir
            config_dir = '%s/.json_struct' % self.config.opt_dict['home_dir']
            if (config_dir != '') and not os.path.exists(config_dir):
                os.mkdir(config_dir)

            else:
                self.config.IO_func.save_oldfile('%s/tv_grab_test.conf' % config_dir)

        except:
            traceback.print_exc()
            return(2)

        try:
            f = self.config.IO_func.open_file('%s/tv_grab_test.conf' % config_dir, 'w')
            for n in ('source_dir', 'grabber_file_dir', 'grabber_name', 'test_modus',
                        'offset', 'sourceid', 'chanid', 'detailid', 'report_dir', 'report_level'):
                f.write(u'%s = %s\n' % (n, self.opt_dict[n]))

            f.close()

        except:
            traceback.print_exc()
            return(2)

    def read_commandline(self):
        description = u"%s: %s\n" % (self.config.country, self.config.version(True)) + \
                        u"The Netherlands: %s\n" % self.config.version(True, True) + \
                        self.config.text('config', 100, (self.config.opt_dict['home_dir'], ),  type = 'help')

        parser = argparse.ArgumentParser(description = description, formatter_class=argparse.RawTextHelpFormatter)

        parser.add_argument('-V', '--version', action = 'store_true', default = False, dest = 'version',
                        help = self.config.text('config', 5, type='help'))

        parser.add_argument('-C', '--config-file', action = 'store_true', default = False, dest = 'config_file',
                        help =self.config.text('config', 110, (self.config.opt_dict['home_dir'],), type='help'))

        parser.add_argument('-S', '--source-dir', type = str, default = None, dest = 'source_dir',
                        metavar = '<directory>', help =self.config.text('config', 103, (self.opt_dict['source_dir'], self.config.opt_dict['home_dir']), type='help'))

        parser.add_argument('-R', '--report-dir', type = str, default = None, dest = 'report_dir',
                        metavar = '<directory>', help =self.config.text('config', 104, (self.opt_dict['report_dir'], ), type='help'))

        parser.add_argument('-l', '--report-level', type = str, default = None, dest = 'report_level',
                        metavar = '<integer>', help =self.config.text('config', 109, type='help'))

        parser.add_argument('-g', '--grabber-name', type = str, default = None, dest = 'grabber_name',
                        metavar = '<name>', help =self.config.text('config', 101, type='help'))

        parser.add_argument('-m', '--test-modus', type = str, default = None, dest = 'test_modus',
                        metavar = '<name>', help =self.config.text('config', 106, type='help'))

        parser.add_argument('-s', '--source-id', type = int, default = None, dest = 'sourceid',
                        metavar = '<id>', help =self.config.text('config', 105, type='help'))

        parser.add_argument('-c', '--chanid', type = str, default = None, dest = 'chanid',
                        metavar = '<id>', help =self.config.text('config', 107, type='help'))

        parser.add_argument('-i', '--detailid', type = str, default = None, dest = 'detailid',
                        metavar = '<id>', help =self.config.text('config', 108, type='help'))

        parser.add_argument('-o', '--offset', type = int, default = None, dest = 'offset', choices=range(0, 14),
                        metavar = '<days>', help =self.config.text('config', 102, type='help'))

        parser.add_argument('--show-sources', action = 'store_true', default = False, dest = 'show_sources',
                        help =self.config.text('config', 10, type='help'))

        parser.add_argument('--show-detail-sources', action = 'store_true', default = False, dest = 'show_detail_sources',
                        help =self.config.text('config', 12, type='help'))

        parser.add_argument('--show-logo-sources', action = 'store_true', default = False, dest = 'show_logo_sources',
                        help =self.config.text('config', 13, type='help'))

        # Handle the sys.exit(0) exception on --help more gracefull
        try:
            self.args = parser.parse_args()

        except:
            return(0)

    def test_jsonfile(self, jdir, jname):
        self.test_json.report_file = self.config.IO_func.open_file('%s/test-%s.txt' % (self.opt_dict['report_dir'], jname), 'w')
        x = self.test_json.test_file('%s/%s.json' % (jdir, jname), report_level = self.opt_dict['report_level'])
        self.test_json.report_file.close()
        self.test_json.report_file = sys.stdout
        self.config.opt_dict['sources'] = jdir
        return x

    def open_output(self):
        if self.opt_dict['test_modus'] in ('channels', 'base', 'detail'):
            self.source.test_output = self.config.IO_func.open_file('%s/%s' % (self.opt_dict['report_dir'], self.opt_dict['parse_file']), 'w')
            self.source.roottree_output = self.config.IO_func.open_file('%s/%s' % (self.opt_dict['report_dir'], self.opt_dict['tree_file']), 'w')
            self.source.raw_output = self.config.IO_func.open_file('%s/rawdata.txt' % (self.opt_dict['report_dir']), 'w')
            self.source.data_output = self.config.IO_func.open_file('%s/output.txt' % (self.opt_dict['report_dir']), 'w')

        if self.opt_dict['test_modus'] in ('channels', 'lineup'):
            self.lineup = self.config.IO_func.open_file('%s/lineup_changes.txt' % (self.opt_dict['report_dir']), 'w')

    def close_output(self):
        if self.source != None:
            for f in (self.source.test_output, self.source.roottree_output, self.source.raw_output, self.source.data_output):
                try:
                    f.close()

                except:
                    pass

        if self.lineup != None:
            self.lineup.close()
            self.lineup = None

    def close(self):
        self.close_output()
        self.config.close()

# end test_Source()
