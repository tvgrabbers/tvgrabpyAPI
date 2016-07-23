#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Python 3 compatibility
from __future__ import unicode_literals
# from __future__ import print_function

import codecs, locale, re, os, sys, io, shutil, difflib
import traceback, smtplib, sqlite3
import datetime, time, calendar, pytz
import tv_grab_channel
from threading import Thread, Lock, RLock
from Queue import Queue, Empty
from copy import deepcopy, copy
from email.mime.text import MIMEText
from xml.sax import saxutils
from DataTreeGrab import is_data_value, data_value


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
        Thread.__init__(self)
        self.quit = False
        self.config = config
        self.functions = Functions(config)
        self.log_queue = Queue()
        self.log_output = None
        self.log_string = []
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
        self.log_output = self.config.log_output
        self.fatal_error = [self.config.text('IO', 10), \
                '     %s\n' % (self.config.opt_dict['config_file']), \
                '     %s\n' % (self.config.opt_dict['log_file'])]

        while True:
            try:
                if self.quit and self.log_queue.empty():
                    # We close down after mailing the log
                    if self.config.opt_dict['mail_log']:
                        self.send_mail(self.log_string, self.config.opt_dict['mail_log_address'])

                    return(0)

                try:
                    message = self.log_queue.get(True, 5)

                except Empty:
                    continue

                if message == None:
                    continue

                elif isinstance(message, dict) and 'fatal' in message:
                    # A fatal Error has been received, after logging we send all threads the quit signal
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

                    for t in self.config.threads:
                        if t.is_alive():
                            if t.thread_type == 'cache':
                                t.cache_request.put({'task': 'quit'})

                            if t.thread_type in ('ttvdb', 'source', 'channel'):
                                t.cache_return.put('quit')

                            if t.thread_type in ('ttvdb', 'source'):
                                t.detail_request.put({'task': 'quit'})

                            if t.thread_type == 'channel':
                                t.detail_return.put('quit')

                            t.quit = True

                    self.log_queue.put('Closing down\n')
                    continue

                elif isinstance(message, (str, unicode)):
                    if message == 'Closing down\n':
                        self.quit=True

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
                        self.quit = True

                    elif message[0][:12] == 'DataTreeGrab':
                        if ltarget == 1:
                            llevel = 1
                            ltarget = 3

                        elif ltarget == 2:
                            ltarget = 3
                            if llevel == -1:
                                llevel = 128

                            else:
                                llevel = 256

                        elif llevel == -1:
                            llevel = 32768
                            ltarget = 3

                        else:
                            llevel = 65536
                            ltarget = 3

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
                sys.stderr.write((self.now() + u'An error ocured while logging!\n').encode(self.local_encoding, 'replace'))
                traceback.print_exc()

    # end run()

    def now(self):
         return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z') + ': '

    # end now()

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
                subject = 'Tv_grab_nl_py %s' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

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
        Thread.__init__(self)
        """
        Create a new ProgramCache object, optionally from file
        """
        self. print_data_structure = False
        self.config = config
        self.functions = self.config.IO_func
        self.current_date = self.config.in_fetch_tz(datetime.datetime.now(pytz.utc))
        self.field_list = []
        self.field_list.extend(self.config.key_values['text'])
        self.field_list.extend(self.config.key_values['date'])
        self.field_list.extend(self.config.key_values['datetime'])
        self.field_list.extend(self.config.key_values['bool'])
        self.field_list.extend(self.config.key_values['video'])
        self.field_list.extend(self.config.key_values['int'])
        self.field_list.extend(self.config.key_values['list'])
        sqlite3.register_adapter(list, self.adapt_list)
        sqlite3.register_converter(str('listing'), self.convert_list)
        sqlite3.register_adapter(bool, self.adapt_bool)
        sqlite3.register_converter(str('boolean'), self.convert_bool)
        sqlite3.register_adapter(datetime.datetime, self.adapt_datetime)
        sqlite3.register_converter(str('datetime'), self.convert_datetime)
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
                                   "prog_ID": {"type": "TEXT", "default": ""},
                                   "start-time": {"type": "datetime", "default": 0},
                                   "stop-time": {"type": "datetime", "default": 0},
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
            "ttvdb": {"name": "ttvdb", "no rowid": True,
                "fields":{"name": {"type": "TEXT", "default": ""},
                                   "tid": {"type": "INTEGER", "default": 0},
                                   "lang": {"type": "TEXT", "default": ""},
                                   "tdate": {"type": "date", "default": 0},
                                   "airdate": {"type": "date", "null": True},
                                   "description": {"type": "TEXT", "null": True},
                                   "banner": {"type": "TEXT", "null": True}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["name", "lang"]},
                    "ttvdbtitle": {"fields": ["name"]},
                    "ttvdbdate": {"fields": ["tdate"]},
                    "ttvdbtid": {"fields": ["tid", 'lang']}}},
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
            "ttvdb_alias": {"name": "ttvdb_alias", "no rowid": True,
                "fields":{ "alias": {"type": "TEXT", "default": ""},
                                   "name": {"type": "TEXT", "default": ""}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["alias"]},
                    "ttvdbtitle": {"fields": ["name"]}}},
            "episodes": {"name": "episodes", "no rowid": True,
                "fields":{"tid": {"type": "INTEGER", "default": 0},
                                   "sid": {"type": "INTEGER", "default": -1},
                                   "eid": {"type": "INTEGER", "default": -1},
                                   "lang": {"type": "TEXT", "default": ""},
                                   "episode title": {"type": "TEXT", "default": ""},
                                   "description": {"type": "TEXT", "null": True},
                                   "airdate": {"type": "date", "null": True}},
                "indexes":{"PRIMARY": {"unique": True, "on conflict": "REPLACE",
                                    "fields": ["tid", "sid", "eid", "lang"]},
                    "eptitle": {"fields": ["episode title"]}}}}

        for key in self.config.key_values['text']:
            if key not in self.get_fields("sourceprograms"):
                self.table_definitions["sourceprograms"]["fields"][key] = {"type": "TEXT", "null": True}

            if key in self.config.detail_keys['all'] and key not in self.get_fields("programdetails"):
                self.table_definitions["programdetails"]["fields"][key] = {"type": "TEXT", "null": True}

            if key in self.config.detail_keys['ttvdb'] and key not in self.get_fields("ttvdb"):
                self.table_definitions["ttvdb"]["fields"][key] = {"type": "TEXT", "null": True}

            if key in self.config.detail_keys['episodes'] and key not in self.get_fields("episodes"):
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

        # where we store our info
        self.filename  = filename
        self.quit = False
        self.cache_request = Queue()
        self.config.queues['cache'] = self.cache_request
        self.thread_type = 'cache'
        self.config.threads.append(self)
        self.request_list = {}
        self.request_list['query_id'] = ('chan_group', 'ttvdb', 'ttvdb_alias', 'tdate')
        self.request_list['query'] = ('icon', 'chan_group', 'chan_scid',
                                    'laststop', 'fetcheddays', 'sourceprograms', 'programdetails',
                                    'ttvdb', 'ttvdb_aliasses', 'ttvdb_langs',
                                    'ep_by_id', 'ep_by_title')
        self.request_list['add'] = ('channelsource', 'channel', 'icon',
                                    'laststop', 'fetcheddays', 'sourceprograms', 'programdetails',
                                    'ttvdb', 'ttvdb_alias', 'episodes')
        self.request_list['delete'] = ('sourceprograms', 'programdetails', 'ttvdb')
        self.request_list['clear'] = ('fetcheddays', 'fetcheddata', 'sourceprograms', 'credits', 'programdetails', 'creditdetails')

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
                pcursor = self.pconn.cursor()
                self.functions.log(self.config.text('IO', 1, type = 'other'))
                pcursor.execute("PRAGMA main.integrity_check")
                if pcursor.fetchone()[0] == 'ok':
                    # Making a backup copy
                    self.pconn.close()
                    if os.path.isfile(self.filename +'.db.bak'):
                        os.remove(self.filename + '.db.bak')

                    shutil.copy(self.filename + '.db', self.filename + '.db.bak')
                    self.pconn = sqlite3.connect(database=self.filename + '.db', isolation_level=None, detect_types=sqlite3.PARSE_DECLTYPES)
                    self.pconn.row_factory = sqlite3.Row
                    pcursor = self.pconn.cursor()
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
            pcursor.execute("PRAGMA main.synchronous = OFF")
            pcursor.execute("PRAGMA main.temp_store = MEMORY")
            # We Check all Tables, Columns and Indices
            for t in self.table_definitions.keys():
                if self. print_data_structure:
                    print t

                # (cid, Name, Type, Nullable = 0, Default, Pri_key index)
                pcursor.execute("PRAGMA main.table_info('%s')" % (t,))
                trows = pcursor.fetchall()
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
            for a, t in self.config.ttvdb_aliasses.items():
                if not self.query_id('ttvdb_alias', {'name': t, 'alias': a}):
                    self.add('ttvdb_alias', {'name': t, 'alias': a})

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
            #~ pkstring += u") ON CONFLICT REPLACE)" if self.get_iprop(table, 'PRIMARY', "replace on conflict", False) else u"))"

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
        pcursor = self.pconn.cursor()
        # (id, name, UNIQUE, c(reate)/u(nique)/p(rimary)k(ey), Partial)
        pcursor.execute("PRAGMA main.index_list(%s)" % (table,))
        ilist = {}
        for r in pcursor.fetchall():
            if r[3].lower() == 'pk':
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
                    pcursor.execute("PRAGMA main.index_info(%s)" % (ilist[iname][1],))
                    iflds = {}
                    for r in pcursor.fetchall():
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
            istring += u"%s`%s`"% (psplit, fld)
            psplit = u", "

        self.execute(u"%s)" % (istring))

    def run(self):
        time.sleep(1)
        self.open_db()
        try:
            while True:
                if self.quit and self.cache_request.empty():
                    self.pconn.close()
                    break

                try:
                    crequest = self.cache_request.get(True, 5)

                except Empty:
                    continue

                if (not isinstance(crequest, dict)) or (not 'task' in crequest):
                    continue

                if crequest['task'] in ('query', 'query_id'):
                    if not 'parent' in crequest:
                        continue

                    if self.filename == None:
                        # there is no cache, but we have to return something
                        qanswer = None

                    else:
                        for t in self.request_list[crequest['task']]:
                            if t in crequest:
                                if crequest['task'] == 'query':
                                    qanswer = self.query(t, crequest[t])

                                if crequest['task'] == 'query_id':
                                    qanswer = self.query_id(t, crequest[t])

                                # Because of queue count integrety you can do only one query per call
                                break

                            else:
                                qanswer = None

                    crequest['parent'].cache_return.put(qanswer)
                    continue

                if self.filename == None:
                    # There is no cache
                    continue

                if crequest['task'] == 'add':
                    for t in self.request_list[crequest['task']]:
                        if t in crequest:
                            self.add(t, crequest[t])

                if crequest['task'] == 'delete':
                    for t in self.request_list[crequest['task']]:
                        if t in crequest:
                            self.delete(t, crequest[t])

                if crequest['task'] == 'clear':
                    if 'table' in crequest:
                        for t in crequest['table']:
                            self.clear(t)

                    else:
                        for t in self.request_list[crequest['task']]:
                            self.clear(t)

                    continue

                if crequest['task'] == 'clean':
                    self.clean()
                    continue

                if crequest['task'] == 'quit':
                    self.quit = True
                    continue

        except:
            self.config.queues['log'].put({'fatal': [traceback.format_exc(), '\n'], 'name': 'ProgramCache'})
            self.ready = True
            return(98)

    def query(self, table='sourceprograms', item=None):
        """
        Updates/gets/whatever.
        """
        pcursor = self.pconn.cursor()
        if table == 'fetcheddays':
            if not isinstance(item, dict) or not "sourceid" in item.keys() or not "channelid" in item.keys():
                return

            rval = {}
            if not "scandate" in item.keys():
                pcursor.execute(u"SELECT `scandate`, `stored` FROM fetcheddays WHERE `sourceid` = ? AND `channelid` = ?", (item['sourceid'],item['channelid']))
                for r in pcursor.fetchall():
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

                    pcursor.execute(u"SELECT `stored` FROM fetcheddays WHERE `sourceid` = ? AND `channelid` = ? AND `scandate` = ?", (item['sourceid'],item['channelid'], sd))
                    r = pcursor.fetchone()
                    if r == None:
                        rval[offset] = None

                    else:
                        rval[offset] = r[str('stored')]

                return rval

        elif table == 'laststop':
            if not isinstance(item, dict) or not "sourceid" in item.keys() or not "channelid" in item.keys():
                return

            pcursor.execute(u"SELECT * FROM fetcheddata WHERE `sourceid` = ? AND `channelid` = ?", (item['sourceid'],item['channelid']))
            r = pcursor.fetchone()
            if r != None:
                laststop = r[str('laststop')]
                if isinstance(laststop, datetime.datetime):
                    return {'laststop': laststop}

                else:
                    return {'laststop': None}

            return None

        elif table == 'sourceprograms':
            if not isinstance(item, dict) or not "sourceid" in item.keys() or not "channelid" in item.keys():
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

                        pcursor.execute(u"SELECT * FROM sourceprograms WHERE `sourceid` = ? AND `channelid` = ? AND `scandate` = ?", (item['sourceid'], item['channelid'], sd))
                        programs.extend(pcursor.fetchall())

            elif "start-time" in item.keys():
                if isinstance(item["start-time"], datetime.datetime):
                    item["start-time"] = [item["start-time"]]

                if isinstance(item["start-time"], list):
                    for st in item["start-time"]:
                        if not isinstance(st, datetime.datetime):
                            continue

                        pcursor.execute(u"SELECT * FROM sourceprograms WHERE `sourceid` = ? AND `channelid` = ? AND `start-time` = ?", (item['sourceid'], item['channelid'], st))
                        programs.extend(pcursor.fetchall())

            elif "range" in item.keys():
                if isinstance(item['range'], dict):
                    item['range'] = [item['range']]

                if not isinstance(item['range'], (list, tuple)) or len(item['range']) ==0:
                    return programs

                for fr in item['range']:
                    if not isinstance(fr, dict):
                        continue

                    if 'start' in fr.keys() and isinstance(fr['start'], datetime.datetime) and 'stop' in fr.keys() and  isinstance(fr['stop'], datetime.datetime):
                        pcursor.execute(u"SELECT * FROM sourceprograms WHERE `sourceid` = ? AND `channelid` = ? AND `start-time` >= ? AND `stop-time` <= ?", \
                            (item['sourceid'], item['channelid'], fr['start'], fr['stop']))
                        programs.extend(pcursor.fetchall())

                    elif 'stop' in fr.keys() and isinstance(fr['stop'], datetime.datetime):
                        pcursor.execute(u"SELECT * FROM sourceprograms WHERE `sourceid` = ? AND `channelid` = ? AND `stop-time` <= ?", \
                            (item['sourceid'], item['channelid'],fr['stop']))
                        programs.extend(pcursor.fetchall())

                    elif 'start' in fr.keys() and isinstance(fr['start'], datetime.datetime):
                        pcursor.execute(u"SELECT * FROM sourceprograms WHERE `sourceid` = ? AND `channelid` = ? AND `start-time` >= ?", \
                            (item['sourceid'], item['channelid'], fr['start']))
                        programs.extend(pcursor.fetchall())

            else:
                pcursor.execute(u"SELECT * FROM sourceprograms WHERE `sourceid` = ? AND `channelid` = ?", (item['sourceid'], item['channelid']))
                programs = pcursor.fetchall()

            programs2 = []
            for p in programs:
                pp = {}
                for key in p.keys():
                    if p[key] != None:
                        pp[unicode(key)] = p[key]

                pp['offset'] = self.date_to_offset(pp['scandate'])
                pcursor.execute(u"SELECT * FROM credits WHERE `sourceid` = ? AND `channelid` = ? AND `start-time` = ?", \
                    (item['sourceid'], item['channelid'], pp['start-time']))
                for r in pcursor.fetchall():
                    if not r[str('title')] in pp.keys():
                        pp[r[str('title')]] = []

                    if r[str('title')] in ('actor', 'guest'):
                        pp[r[str('title')]].append({'name': r[str('name')], 'role': r[str('role')]})

                    else:
                        pp[r[str('title')]].append( r[str('name')])

                programs2.append(pp)

            return programs2

        elif table == 'programdetails':
            if not isinstance(item, dict) or not "sourceid" in item.keys() or not "channelid" in item.keys():
                return

            programs = []
            if "prog_ID" in item.keys():
                if isinstance(item["prog_ID"], (str, unicode)):
                    item["prog_ID"] = [item["prog_ID"]]

                if isinstance(item["prog_ID"], list):
                    for sd in item["prog_ID"]:
                        if not isinstance(sd, (str, unicode)):
                            continue

                        pcursor.execute(u"SELECT * FROM programdetails WHERE `sourceid` = ? AND `channelid` = ? AND `prog_ID` = ?", \
                            (item['sourceid'], item['channelid'], sd))
                        p = pcursor.fetchone()
                        if p != None:
                            programs.append(p)

            elif "start-time" in item.keys():
                if isinstance(item["start-time"], datetime.datetime):
                    item["start-time"] = [item["start-time"]]

                if isinstance(item["start-time"], list):
                    for st in item["start-time"]:
                        if not isinstance(st, datetime.datetime):
                            continue

                        pcursor.execute(u"SELECT * FROM programdetails WHERE `sourceid` = ? AND `channelid` = ? AND `start-time` = ?", \
                            (item['sourceid'], item['channelid'], st))
                        p = pcursor.fetchone()
                        if p != None:
                            programs.append(p)

            else:
                pcursor.execute(u"SELECT * FROM programdetails WHERE `sourceid` = ? AND `channelid` = ?", (item['sourceid'], item['channelid']))
                programs = pcursor.fetchall()

            programs2 = []
            for p in programs:
                pp = {}
                for key in p.keys():
                    if p[key] != None:
                        pp[unicode(key)] = p[key]

                pcursor.execute(u"SELECT * FROM creditdetails WHERE `sourceid` = ? AND `channelid` = ? AND `prog_ID` = ?", (item['sourceid'], item['channelid'], pp['prog_ID']))
                for r in pcursor.fetchall():
                    if not r[str('title')] in pp.keys():
                        pp[r[str('title')]] = []

                    if r[str('title')] in ('actor', 'guest'):
                        pp[r[str('title')]].append({'name': r[str('name')], 'role': r[str('role')]})

                    else:
                        pp[r[str('title')]].append( r[str('name')])

                programs2.append(pp)

            return programs2

        elif table == 'ttvdb':
            pcursor.execute(u"SELECT * FROM ttvdb WHERE `tid` = ?", (item,))
            slist = []
            for r in pcursor.fetchall():
                serie = {}
                serie['tid'] = r[str('tid')]
                serie['name'] = r[str('name')]
                serie['tdate'] = r[str('tdate')]
                serie['lang'] = r[str('lang')]
                serie['star-rating'] = r[str('star-rating')]
                serie['description'] = r[str('description')]
                serie['airdate'] = r[str('airdate')]
                slist.append(serie)

            return slist

        elif table == 'ttvdb_aliasses':
            pcursor.execute(u"SELECT `alias` FROM ttvdb_alias WHERE lower(name) = ?", (item.lower(), ))
            r = pcursor.fetchall()
            aliasses = []
            if r != None:
                for a in r:
                    aliasses.append( a[0])

            return aliasses

        elif table == 'ttvdb_langs':
            pcursor.execute(u"SELECT `lang` FROM ttvdb WHERE tid = ?", (item['tid'],))
            langs = []
            for r in pcursor.fetchall():
                langs.append( r[str('lang')])

            return langs

        elif table == 'ep_by_id':
            qstring = u"SELECT * FROM episodes WHERE tid = ?"
            qlist = [item['tid']]
            if data_value(['sid'], item, int, -1) >= 0:
                qstring += u" and sid = ?"
                qlist.append(item['sid'])

            if data_value(['eid'], item, int, -1) >= 0:
                qstring += u" and eid = ?"
                qlist.append(item['eid'])

            if 'lang' in item:
                qstring += u" and lang = ?"
                qlist.append(item['lang'])

            pcursor.execute(qstring, tuple(qlist))

            r = pcursor.fetchall()
            if len(r) == 0  and data_value(['lang'], item, str) != 'en':
                # We try again for english
                qstring = u"SELECT * FROM episodes WHERE tid = ?"
                qlist = [item['tid']]
                if data_value(['sid'], item, int, -1) >= 0:
                    qstring += u" and sid = ?"
                    qlist.append(item['sid'])

                if data_value(['eid'], item, int, -1) >= 0:
                    qstring += u" and eid = ?"
                    qlist.append(item['eid'])

                qstring += u" and lang = ?"
                qlist.append('en')

                pcursor.execute(qstring, tuple(qlist))

                r = pcursor.fetchall()

            series = []
            for s in r:
                series.append({'tid': int(s[str('tid')]),
                                          'sid': int(s[str('sid')]),
                                          'eid': int(s[str('eid')]),
                                          'episode title': s[str('episode title')],
                                          'airdate': s[str('airdate')],
                                          'lang': s[str('lang')],
                                          'star-rating': s[str('star-rating')],
                                          'description': s[str('description')]})
            return series

        elif table == 'ep_by_title':
            pcursor.execute(u"SELECT * FROM episodes WHERE tid = ? and lower(`episode title`) = ?", (item['tid'], item['episode title'].lower(), ))
            s = pcursor.fetchone()
            if s == None:
                return

            serie = {'tid': int(s[str('tid')]),
                                          'sid': int(s[str('sid')]),
                                          'eid': int(s[str('eid')]),
                                          'episode title': s[str('episode title')],
                                          'airdate': s[str('airdate')],
                                          'lang': s[str('lang')],
                                          'star-rating': s[str('star-rating')],
                                          'description': s[str('description')]}
            return serie
        elif table == 'icon':
            if item == None:
                pcursor.execute(u"SELECT chanid, sourceid, icon FROM iconsource")
                r = pcursor.fetchall()
                icons = {}
                if r != None:
                    for g in r:
                        if not g[0] in icons:
                            icons[g[0]] ={}

                        icons[g[0]][g[1]] = g[2]

                return icons

            else:
                pcursor.execute(u"SELECT icon FROM iconsource WHERE chanid = ? and sourceid = ?", (item['chanid'], item['sourceid']))
                r = pcursor.fetchone()
                if r == None:
                    return

                return {'sourceid':  item['sourceid'], 'icon': r[0]}

        elif table == 'chan_group':
            if item == None:
                pcursor.execute(u"SELECT chanid, cgroup, name FROM channels")
                r = pcursor.fetchall()
                changroups = {}
                if r != None:
                    for g in r:
                        changroups[g[0]] = {'name': g[2],'cgroup': int(g[1])}

                return changroups

            else:
                pcursor.execute(u"SELECT cgroup, name FROM channels WHERE chanid = ?", (item['chanid'],))
                r = pcursor.fetchone()
                if r == None:
                    return

                return {'cgroup':r[0], 'name': r[1]}

        elif table == 'chan_scid':
            if item == None:
                pcursor.execute(u"SELECT chanid, sourceid, scid, name, hd FROM channelsource")
                r = pcursor.fetchall()
                scids = {}
                if r != None:
                    for g in r:
                        if not g[0] in scids:
                            scids[g[0]] ={}

                        scids[g[0]][g[1]] = {'scid': g[2],'name': g[3], 'hd': g[4]}

                return scids

            elif 'chanid' in item and 'sourceid' in item:
                pcursor.execute(u"SELECT scid FROM channelsource WHERE chanid = ? and sourceid = ?", (item['chanid'], item['sourceid']))
                r = pcursor.fetchone()
                if r == None:
                    return

                return scid

            elif 'fgroup' in item and 'sourceid' in item:
                pcursor.execute(u"SELECT scid, chanid FROM channelsource WHERE fgroup = ? and sourceid = ?", (item['fgroup'], item['sourceid']))
                r = pcursor.fetchall()
                fgroup = []
                if r != None:
                    for g in r:
                        fgroup.append({'chanid': g[1],'channelid': g[0]})

                return fgroup

            elif 'sourceid' in item:
                pcursor.execute(u"SELECT scid, chanid, name FROM channelsource WHERE sourceid = ?", (item['sourceid']))
                r = pcursor.fetchall()
                scids = {}
                if r != None:
                    for g in r:
                        if not g[0] in scids:
                            scids[g[0]] ={}

                        scids[g[0]] = {'chanid': g[1],'name': g[2]}

                return scids

    def query_id(self, table='program', item=None):
        """
        Check which ID is used
        """
        pcursor = self.pconn.cursor()
        if table == 'ttvdb':
            tlist = []
            pcursor.execute(u"SELECT ttvdb.tid, tdate, ttvdb.name, ttvdb.lang FROM ttvdb JOIN ttvdb_alias " + \
                    "ON lower(ttvdb.name) = lower(ttvdb_alias.name) WHERE lower(alias) = ?", \
                    (item['name'].lower(), ))
            for r in pcursor.fetchall():
                tlist.append({'tid': r[0], 'tdate': r[1], 'name': r[2], 'lang': r[3]})

            pcursor.execute(u"SELECT tid, tdate, name, lang FROM ttvdb WHERE lower(name) = ?", (item['name'].lower(), ))
            for r in pcursor.fetchall():
                tlist.append({'tid': r[0], 'tdate': r[1], 'name': r[2], 'lang': r[3]})

            return tlist

        elif table == 'ttvdb_alias':
            pcursor.execute(u"SELECT name FROM ttvdb_alias WHERE lower(alias) = ?", (item['alias'].lower(), ))
            r = pcursor.fetchone()
            if r == None:
                if 'name' in item:
                    return False

                else:
                    return

            if 'name' in item:
                if item['name'].lower() == r[0].lower():
                    return True

                else:
                    return False

            else:
                return {'name': r[0]}

        elif table == 'tdate':
            pcursor.execute(u"SELECT tdate FROM ttvdb WHERE tid = ?", (item,))
            r = pcursor.fetchone()
            if r == None:
                return

            return r[0]

        elif table == 'chan_group':
            pcursor.execute(u"SELECT cgroup, name FROM channels WHERE chanid = ?", (item['chanid'],))
            r = pcursor.fetchone()
            if r == None:
                return

            return r[0]

    def add(self, table='sourceprograms', item=None):
        """
        Adds (or updates) a record
        """
        rec = []
        rec_upd = []
        rec2 = []
        if table == 'laststop':
            if not isinstance(item, dict) or not "sourceid" in item.keys() or not "channelid" in item.keys() \
              or not "laststop" in item.keys() or not isinstance(item['laststop'], datetime.datetime):
                return

            laststop = self.query(table, item)
            if laststop == None:
                add_string = u"INSERT INTO fetcheddata (`sourceid`, `channelid`, `laststop`) VALUES (?, ?, ?)"
                rec = [(item['sourceid'], item['channelid'], item['laststop'])]
                self.execute(add_string, rec)

            elif laststop['laststop'] == None or item['laststop'] > laststop['laststop']:
                add_string = u"UPDATE fetcheddata SET `laststop` = ? WHERE `sourceid` = ? AND `channelid` = ?"
                rec = [(item['laststop'], item['sourceid'], item['channelid'])]
                self.execute(add_string, rec)

        elif table == 'fetcheddays':
            if not isinstance(item, dict) or not "sourceid" in item.keys() or not "channelid" in item.keys() or not "scandate" in item.keys():
                return

            add_string = u"INSERT INTO fetcheddays (`sourceid`, `channelid`, `scandate`, `stored`) VALUES (?, ?, ?, ?)"
            update_string = u"UPDATE fetcheddays SET `stored` = ? WHERE `sourceid` = ? AND `channelid` = ? AND `scandate` = ?"
            sdate = self.query('fetcheddays', {'sourceid': item['sourceid'], 'channelid': item['channelid']})
            dval = True if not "stored" in item.keys() or not isinstance(item['stored'], bool) else item['stored']
            if isinstance(item["scandate"], (int, datetime.date)):
                item["scandate"] = [item["scandate"]]

            if isinstance(item["scandate"], list):
                for sd in item["scandate"]:
                    if isinstance(sd, int):
                        sd = self.offset_to_date(sd)

                    if not isinstance(sd, datetime.date):
                        continue

                    if not sd in sdate.keys() or sdate[sd] == None:
                        rec.append((item['sourceid'], item['channelid'], sd, dval))

                    elif sdate[item["scandate"]] != dval:
                        rec_upd.append((dval, item['sourceid'], item['channelid'], sd))

                self.execute(add_string, rec)
                self.execute(update_string, rec_upd)

        elif table == 'sourceprograms':
            if isinstance(item, dict):
                item = [item]

            sql_flds = u"INSERT INTO sourceprograms (`sourceid`, `channelid`, `scandate`"
            sql_cnt = u"VALUES (?, ?, ?"
            for f in self.field_list:
                sql_flds = u"%s, `%s`" % (sql_flds, f)
                sql_cnt = u"%s, ?" % (sql_cnt)

            add_string = u"%s) %s)" % (sql_flds, sql_cnt)
            add_string2 = u"INSERT INTO credits (`sourceid`, `channelid`, `scandate`, `prog_ID`, `start-time`, `title`, `name`, `role`) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            for p in item:
                if not isinstance(p, dict):
                    continue

                sql_vals = [p['sourceid'], p['channelid'], p['scandate']]
                for f in self.field_list:
                    if f in p.keys():
                        sql_vals.append(p[f])

                    else:
                        sql_vals.append(None)

                rec.append(tuple(sql_vals))
                for f in self.config.key_values['credits']:
                    if f in p.keys():
                        for cr in p[f]:
                            sql_vals = [p['sourceid'], p['channelid'], p['scandate'], p['prog_ID'], p['start-time'], f]
                            if isinstance(cr, dict):
                                sql_vals.append(cr['name'])
                                if 'role' in cr.keys():
                                    sql_vals.append(cr['role'])

                                else:
                                    sql_vals.append(None)

                            elif isinstance(cr, (str, unicode)):
                                sql_vals.append(cr)
                                sql_vals.append(None)

                            else:
                                continue

                            rec2.append(tuple(sql_vals))

            self.execute(add_string, rec)
            self.execute(add_string2, rec2)

        elif table == 'programdetails':
            if isinstance(item, dict):
                item = [item]

            sql_flds = u"INSERT INTO programdetails (`sourceid`, `channelid`, `prog_ID`, `start-time`, `stop-time`, `name`, `genre`"
            sql_cnt = u"VALUES (?, ?, ?, ?, ?, ?, ?"
            for f in self.config.detail_keys['all']:
                if f in self.field_list:
                    sql_flds = u"%s, `%s`" % (sql_flds, f)
                    sql_cnt = u"%s, ?" % (sql_cnt)

            add_string = u"%s) %s)" % (sql_flds, sql_cnt)
            add_string2 = u"INSERT INTO creditdetails (`sourceid`, `channelid`, `prog_ID`, `start-time`, `title`, `name`, `role`) VALUES (?, ?, ?, ?, ?, ?, ?)"
            for p in item:
                if not isinstance(p, dict):
                    continue

                sql_vals = [p['sourceid'], p['channelid'], p['prog_ID']]
                for f in ('start-time', 'stop-time', 'name', 'genre'):
                    if f in p.keys():
                        sql_vals.append(p[f])

                    elif self.get_fprop(table, f, 'null', False):
                        sql_vals.append(None)

                    else:
                        sql_vals.append(self.get_fprop(table, f, 'default', ''))

                for f in self.config.detail_keys['all']:
                    if f in self.field_list:
                        if f in p.keys():
                            sql_vals.append(p[f])

                        else:
                            sql_vals.append(None)

                rec.append(tuple(sql_vals))
                for f in self.config.key_values['credits']:
                    if f in p.keys():
                        for cr in p[f]:
                            sql_vals = [p['sourceid'], p['channelid'], p['prog_ID'], p['start-time'], f]
                            if isinstance(cr, dict):
                                sql_vals.append(cr['name'])
                                if 'role' in cr.keys():
                                    sql_vals.append(cr['role'])

                                else:
                                    sql_vals.append(None)

                            elif isinstance(cr, (str, unicode)):
                                sql_vals.append(cr)
                                sql_vals.append(None)

                            else:
                                continue

                            rec2.append(tuple(sql_vals))

            self.execute(add_string, rec)
            self.execute(add_string2, rec2)

        elif table == 'channel':
            add_string = u"INSERT INTO channels (`chanid`, `cgroup`, `name`) VALUES (?, ?, ?)"
            update_string = u"UPDATE channels SET `cgroup` = ?, `name` = ? WHERE chanid = ?"
            if isinstance(item, dict):
                item = [item]

            if isinstance(item, list):
                g = self.query('chan_group')

                for c in item:
                    if not c['chanid'] in g.keys():
                        rec.append((c['chanid'], c['cgroup'], c['name']))

                    elif g[c['chanid']]['name'].lower() != c['name'].lower() or g[c['chanid']]['cgroup'] != c['cgroup'] \
                      or (g[c['chanid']]['cgroup'] == 10 and c['cgroup'] not in (-1, 0, 10)):
                        rec_upd.append((c['cgroup'], c['name'] , c['chanid']))

                self.execute(update_string, rec_upd)
                self.execute(add_string, rec)

        elif table == 'channelsource':
            add_string = u"INSERT INTO channelsource (`chanid`, `sourceid`, `scid`, `fgroup`, `name`, `hd`) VALUES (?, ?, ?, ?, ?, ?)"
            update_string = u"UPDATE channelsource SET `scid`= ?, `fgroup`= ?, `name`= ?, `hd`= ? WHERE `chanid` = ? and `sourceid` = ?"
            if isinstance(item, dict):
                item = [item]

            if isinstance(item, list):
                scids = self.query('chan_scid')
                for c in item:
                    if c['scid'] == '':
                        continue

                    if c['chanid'] in scids and c['sourceid'] in scids[c['chanid']]:
                        rec_upd.append((c['scid'], c['fgroup'], c['name'], c['hd'], c['chanid'], c['sourceid']))

                    else:
                        rec.append((c['chanid'], c['sourceid'], c['scid'], c['fgroup'], c['name'], c['hd']))

                self.execute(update_string, rec_upd)
                self.execute(add_string, rec)

        elif table == 'icon':
            add_string = u"INSERT INTO iconsource (`chanid`, `sourceid`, `icon`) VALUES (?, ?, ?)"
            update_string = u"UPDATE iconsource SET `icon`= ? WHERE `chanid` = ? and `sourceid` = ?"
            if isinstance(item, dict):
                item = [item]

            if isinstance(item, list):
                icons = self.query('icon')
                for ic in item:
                    if ic['chanid'] in icons and ic['sourceid'] in icons[ic['chanid']] \
                      and icons[ic['chanid']][ic['sourceid']] != ic['icon']:
                        rec_upd.append((ic['icon'], ic['chanid'], ic['sourceid']))

                    else:
                        rec.append((ic['chanid'], ic['sourceid'], ic['icon']))

                self.execute(update_string, rec_upd)
                self.execute(add_string, rec)

        elif table == 'ttvdb':
            if isinstance(item, dict):
                item = [item]

            sql_flds = u"INSERT INTO ttvdb (`tid`, 'tdate'"
            sql_cnt = u"VALUES (?, ?"
            fld_list = self.get_fields(table)
            for f in fld_list:
                if f in ('tid', 'tdate'):
                    continue

                sql_flds = u"%s, `%s`" % (sql_flds, f)
                sql_cnt = u"%s, ?" % (sql_cnt)

            add_string = u"%s) %s)" % (sql_flds, sql_cnt)
            add_string2 = u"INSERT INTO ttvdbcredits (`tid`, `sid`, `eid`, `title`, `name`, `role`) VALUES (?, ?, ?, ?, ?, ?)"
            for p in item:
                if not isinstance(p, dict) or not 'tid' in p.keys() or not 'lang' in p.keys() or not 'name' in p.keys():
                    continue

                sql_vals = [p['tid'], datetime.date.today()]
                for f in fld_list:
                    if f in ('tid', 'tdate'):
                        continue

                    elif f in p.keys():
                        sql_vals.append(p[f])

                    else:
                        sql_vals.append(None)

                rec.append(tuple(sql_vals))
                for f in self.config.key_values['credits']:
                    if f in p.keys():
                        for cr in p[f]:
                            sql_vals = [p['tid'], -1, -1, f]
                            if isinstance(cr, dict):
                                sql_vals.append(cr['name'])
                                if 'role' in cr.keys():
                                    sql_vals.append(cr['role'])

                                else:
                                    sql_vals.append(None)

                            elif isinstance(cr, (str, unicode)):
                                sql_vals.append(cr)
                                sql_vals.append(None)

                            else:
                                continue

                            rec2.append(tuple(sql_vals))

            self.execute(add_string, rec)
            self.execute(add_string2, rec2)

        elif table == 'ttvdb_alias':
            add_string = u"INSERT INTO ttvdb_alias (`name`, `alias`) VALUES (?, ?)"
            aliasses = self.query('ttvdb_aliasses', item['name'])
            if isinstance(item['alias'], list) and len(item['alias']) > 0:
                for a in item['alias']:
                    if not a in aliasses:
                        rec.append((item['name'], a))

                self.execute(add_string, rec)

            elif not item['alias'] in aliasses:
                rec = (item['name'], item['alias'])
                self.execute(add_string, rec)

        elif table == 'episodes':
            if isinstance(item, dict):
                item = [item]

            sql_flds = u"INSERT INTO episodes (`tid`, `sid`, `eid`, `lang`, `episode title`"
            sql_cnt = u"VALUES (?, ?, ?, ?, ?"
            fld_list = self.get_fields(table)
            for f in fld_list:
                if f in ('tid', 'sid', 'eid', 'lang', 'episode title'):
                    continue

                sql_flds = u"%s, `%s`" % (sql_flds, f)
                sql_cnt = u"%s, ?" % (sql_cnt)

            add_string = u"%s) %s)" % (sql_flds, sql_cnt)
            add_string2 = u"INSERT INTO ttvdbcredits (`tid`, `sid`, `eid`, `title`, `name`, `role`) VALUES (?, ?, ?, ?, ?, ?)"
            for p in item:
                if not isinstance(p, dict) or not 'tid' in p.keys() or not 'lang' in p.keys() or not 'episode title' in p.keys():
                    continue

                sql_vals = [p['tid'], p['sid'], p['eid'], p['lang'], p['episode title'], ]
                for f in fld_list:
                    if f in ('tid', 'sid', 'eid', 'lang', 'episode title'):
                        continue

                    elif f in p.keys():
                        sql_vals.append(p[f])

                    else:
                        sql_vals.append(None)

                rec.append(tuple(sql_vals))
                for f in self.config.key_values['credits']:
                    if f in p.keys():
                        for cr in p[f]:
                            sql_vals = [p['tid'], p['sid'], p['eid'], f]
                            if isinstance(cr, dict):
                                sql_vals.append(cr['name'])
                                if 'role' in cr.keys():
                                    sql_vals.append(cr['role'])

                                else:
                                    sql_vals.append(None)

                            elif isinstance(cr, (str, unicode)):
                                sql_vals.append(cr)
                                sql_vals.append(None)

                            else:
                                continue

                            rec2.append(tuple(sql_vals))

            self.execute(add_string, rec)
            self.execute(add_string2, rec2)

    def delete(self, table='ttvdb', item=None):
        if table == 'sourceprograms':
            if not isinstance(item, dict) or not "sourceid" in item.keys() or not "channelid" in item.keys():
                return

            if not "scandate" in item.keys() and not 'start-time' in item.keys():
                self.execute(u"DELETE FROM fetcheddays WHERE sourceid = ? AND channelid = ?", (item['sourceid'], item['channelid']))
                self.execute(u"DELETE FROM credits WHERE sourceid = ? AND channelid = ?", (item['sourceid'], item['channelid']))
                self.execute(u"DELETE FROM sourceprograms WHERE sourceid = ? AND channelid = ?", (item['sourceid'], item['channelid']))

            if "scandate" in item.keys():
                if isinstance(item["scandate"], (datetime.date, int)):
                    item["scandate"] = [item["scandate"]]

                if isinstance(item["scandate"], list):
                    for sd in item["scandate"]:
                        if isinstance(sd, int):
                            sd = self.offset_to_date(sd)

                        self.execute(u"DELETE FROM fetcheddays WHERE sourceid = ? AND channelid = ? AND scandate = ?", (item['sourceid'], item['channelid'], sd))
                        self.execute(u"DELETE FROM credits WHERE sourceid = ? AND channelid = ? AND scandate = ?", (item['sourceid'], item['channelid'], sd))
                        self.execute(u"DELETE FROM sourceprograms WHERE sourceid = ? AND channelid = ? AND scandate = ?", (item['sourceid'], item['channelid'], sd))

            elif "start-time" in item.keys():
                if isinstance(item["start-time"], datetime.datetime):
                    item["start-time"] = [item["start-time"]]

                if isinstance(item["start-time"], list):
                    delete_string = u"DELETE FROM credits WHERE sourceid = ? AND channelid = ? AND `start-time` = ?"
                    delete_string2 = u"DELETE FROM sourceprograms WHERE sourceid = ? AND channelid = ? AND `start-time` = ?"
                    rec = []
                    for sd in item["start-time"]:
                        if isinstance(sd, datetime.datetime):
                            rec.append((item['sourceid'], item['channelid'], sd))

                    self.execute(delete_string, rec)
                    self.execute(delete_string2, rec)

        if table == 'programdetails':
            if not isinstance(item, dict) or not "sourceid" in item.keys() or not "channelid" in item.keys():
                return

            if not "prog_ID" in item.keys() and not 'start-time' in item.keys():
                self.execute(u"DELETE FROM creditdetails WHERE sourceid = ? AND channelid = ?", (item['sourceid'], item['channelid']))
                self.execute(u"DELETE FROM programdetails WHERE sourceid = ? AND channelid = ?", (item['sourceid'], item['channelid']))

            if "prog_ID" in item.keys():
                if isinstance(item["prog_ID"], (str, unicode)):
                    item["prog_ID"] = [item["prog_ID"]]

                if isinstance(item["prog_ID"], list):
                    for sd in item["prog_ID"]:
                        if isinstance(sd, int):
                            sd = self.offset_to_date(sd)

                        self.execute(u"DELETE FROM creditdetails WHERE sourceid = ? AND channelid = ? AND prog_ID = ?", (item['sourceid'], item['channelid'], sd))
                        self.execute(u"DELETE FROM programdetails WHERE sourceid = ? AND channelid = ? AND prog_ID = ?", (item['sourceid'], item['channelid'], sd))

            elif "start-time" in item.keys():
                if isinstance(item["start-time"], datetime.datetime):
                    item["start-time"] = [item["start-time"]]

                if isinstance(item["start-time"], list):
                    delete_string = u"DELETE FROM creditdetails WHERE sourceid = ? AND channelid = ? AND `start-time` = ?"
                    delete_string2 = u"DELETE FROM programdetails WHERE sourceid = ? AND channelid = ? AND `start-time` = ?"
                    rec = []
                    for sd in item["start-time"]:
                        if isinstance(sd, datetime.datetime):
                            rec.append((item['sourceid'], item['channelid'], sd))

                    self.execute(delete_string, rec)
                    self.execute(delete_string2, rec)

        elif table == 'ttvdb':
            with self.pconn:
                self.pconn.execute(u"DELETE FROM ttvdb WHERE tid = ?",  (int(item['tid']), ))
                self.pconn.execute(u"DELETE FROM episodes WHERE tid = ?",  (int(item['tid']), ))
                self.pconn.execute(u"DELETE FROM ttvdbcredits WHERE tid = ?",  (int(item['tid']), ))

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
        self.execute(u"DELETE FROM sourceprograms WHERE `stop-time` < ?", (dnow,))
        self.execute(u"DELETE FROM credits WHERE `stop-time` < ?", (dnow,))
        self.execute(u"DELETE FROM programdetails WHERE `stop-time` < ?", (dnow,))
        self.execute(u"DELETE FROM creditdetails WHERE `stop-time` < ?", (dnow,))
        self.execute(u"DELETE FROM fetcheddays WHERE `scandate` < ?", (dnow.date(),))
        #~ self.execute(u"DELETE FROM ttvdb WHERE tdate < ?", (dttvdb,))

        self.execute(u"VACUUM")

    def execute(self, qstring, parameters = None):
        try:
            if parameters == None:
                with self.pconn:
                    self.pconn.execute(qstring)

            elif not isinstance(parameters, (list, tuple)) or len(parameters) == 0:
                return

            elif isinstance(parameters, tuple):
                with self.pconn:
                    self.pconn.execute(qstring, parameters)

            elif len(parameters) == 1:
                with self.pconn:
                    self.pconn.execute(qstring, parameters[0])

            elif len(parameters) > 1:
                with self.pconn:
                    self.pconn.executemany(qstring, parameters)

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
        if self.write_info_files:
            self.fetch_list = self.functions.open_file(self.config.opt_dict['xmltv_dir'] + '/fetched-programs3','w')
            self.raw_output =  self.functions.open_file(self.config.opt_dict['xmltv_dir']+'/raw_output3', 'w')

    def check_new_channels(self, source, source_channels):
        if not self.write_info_files or self.config.args.only_cache:
            return

        if source.all_channels == {}:
            source.get_channels()

        for channelid, channel in source.all_channels.items():
            if not (channelid in source_channels[source.proc_id].values() or channelid in source.empty_channels):
                #~ print u'New channel on %s => %s (%s)\n' % (source.source, channelid, channel['name'])
                self.lineup_changes.append( u'New channel on %s => %s (%s)\n' % (source.source, channelid, channel['name']))

        for chanid, channelid in source_channels[source.proc_id].items():
            if not (channelid in source.all_channels.keys() or channelid in source.empty_channels):
                #~ print u'Removed channel on %s => %s (%s)\n' % (source.source, channelid, chanid)
                self.lineup_changes.append( u'Removed channel on %s => %s (%s)\n' % (source.source, channelid, chanid))

        for channelid in source.empty_channels:
            if not channelid in source.all_channels.keys():
                #~ print  u"Empty channelID %s on %s doesn't exist\n" % (channelid, source.source)
                self.lineup_changes.append( u"Empty channelID %s on %s doesn't exist\n" % (channelid, source.source))

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

                pnode = programs.first_node
                while isinstance(pnode, tv_grab_channel.ProgramNode):
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
                        fstr += u'  %s: GAP\n' % pnode.next_gap.get_start_stop()

                    pnode = pnode.next

            else:
                plist = deepcopy(programs)
                if group_slots != None:
                    pgs = deepcopy(group_slots)
                    fstr = u' (%3.0f/%2.0f) from: %s\n' % (len(plist), len(pgs), self.config.channelsource[source].source)
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
            self.config.logging.send_mail(self.lineup_changes, self.config.opt_dict['mail_info_address'], 'Tv_grab_nl_py lineup changes')

        if self.config.opt_dict['mail_log'] and len(self.url_failure) > 0:
            self.config.logging.send_mail(self.url_failure, self.config.opt_dict['mail_info_address'], 'Tv_grab_nl_py url failures')

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

