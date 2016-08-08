#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import json, io, sys, os, re, pytz, datetime
from DataTreeGrab import is_data_value, data_value
import tv_grab_config

class test_JSON():
    def __init__(self):
        self.config = tv_grab_config.Configure('tv_grab_test_json')
        #~ fpath = self.config.opt_dict['sources']
        self.config.only_local_sourcefiles = True
        fpath = '/home/hika/Git/git/sourcematching/'
        self.config.get_json_datafiles()
        self.keyfile = self.config.fetch_func.get_json_data('tv_grab_keys', fpath = fpath)
        if not isinstance(self.keyfile, dict):
            self.config.log( 'We could not acces the "tv_grab_keys.json" file\n')
            self.keyfile = None
            return

        raw_json = self.config.fetch_func.raw_json['tv_grab_keys']
        if raw_json != '':
            fle = self.config.IO_func.open_file('%s/%s.json' % (self.config.opt_dict['sources'], 'tv_grab_keys'), 'w', 'utf-8')
            if fle != None:
                fle.write(raw_json)
                fle.close()

        for k, v in self.keyfile.items():
            self.keyfile[k] = self.add_type_key(v)

        self.dkey_errors = {}
        self.errors = {}
        self.sources = []
        self.chanids = []
        self.channel_groups = []
        self.check_data_lists = False
        self.check_on_grabber_datafile = False
        self.logo_sources = self.config.xml_output.logo_source_preference
        self.testfile = None
        self.jsontypes = {0: 'unkown',
                                     1: 'grabberfile',
                                     2: 'sourcefile',
                                     3: 'virtualsource'}

    def test_file_syntax(self, file_name):
        j_file = self.config.IO_func.open_file(file_name, 'r', 'utf-8')
        if j_file == None:
            sys.exit(-1)

        self.testfile = json.load(j_file)
        if not isinstance(self.testfile, dict):
            self.config.log(['The file %s is a correct JSON file\n' % file_name,'  but is not recognized.\n'])
            sys.exit(-1)

        elif file_name.split('/')[-1][:8] == 'tv_grab_' and "sources" in self.testfile.keys() and "source_channels" in self.testfile.keys():
            self.config.log( 'The file %s is a grabber-JSON file\n' % file_name)
            self.load_data_lists()
            self.test(1)

        elif file_name.split('/')[-1][:7] == 'source-' and "name" in self.testfile.keys():
            if data_value("is_virtual", self.testfile, bool, False):
                self.config.log( 'The file %s is a virtual-source-JSON file\n' % file_name)
                self.test(3)

            else:
                self.config.log( 'The file %s is a source-JSON file\n' % file_name)
                self.test(2)

        else:
            self.config.log(['The file %s is a correct JSON file\n' % file_name,'  but is not recognized.\n'])
            sys.exit(-1)

    def load_data_lists(self):
        # Load reference lists from the grabber_datafile
        for s in data_value(["sources"], self.testfile, dict).keys():
            try:
                s = int(s)

            except:
                self.config.log('Invalid sourceID %s encountered. Should be a number.\n')
                continue

            if s < 1:
                self.config.log('Invalid sourceID %s encountered. Should be a bigger then 0.\n')
                continue

            self.sources.append(s)

        for s, v in data_value(["source_channels"], self.testfile, dict).items():
            if not is_data_value(["source_channels", s], self.testfile, dict):
                continue

            for c in v.keys():
                if not c in self.chanids:
                    self.chanids.append(c)

        for s in data_value(["channel_groups"], self.testfile, dict).keys():
            try:
                s = int(s)

            except:
                self.config.log('Invalid groupID %s encountered. Should be a number.\n')
                continue

            if s < 0:
                self.config.log('Invalid groupID %s encountered. Should be a positive number.\n')
                continue

            self.channel_groups.append(s)

        for k in data_value(["logo_provider"], self.testfile, dict).keys():
            try:
                if int(k) not in logo_sources:
                    self.logo_sources.append(int(k))

            except:
                continue

        self.check_data_lists = True

    def add_type_key(self, tval):
        # Fix missing 'type' keyword in the json test file
        if isinstance(tval, list):
            tmplist = []
            for v in tval:
                tmplist.append(self.add_type_key(v))

            tval = tmplist

        if isinstance(tval, dict):
            for k, v in tval.items():
                if k == "types":
                    tmplist = []
                    for item in range(len(v)):
                        if isinstance(v[item], dict):
                            tmplist.append(v[item])

                        else:
                           tmplist.append({'type': v[item]})

                    tval[k] = tmplist

                else:
                    tval[k] = self.add_type_key(v)

        return tval

    def test_type(self, dkey, dtypes, val, vpath = None):
        # On succes return the type else None or 0
        def importance():
            if importancenlevel == 1:
                return 'required '

            elif importancenlevel == 2:
                return 'sugested '

            elif importancenlevel == 3:
                return 'optional '

            return ''

        def set_error(err, testkey = None, default = None):
            # if testkey is set it is a internal key test
            # if vpath is None it's a one time test error setting is done by the requester
            if vpath == None and testkey == None:
                return None

            if not is_data_value([dkey], self.errors, list):
                self.errors[dkey] = []

            if testkey == None:
                self.errors[dkey].append({'path': vpath,
                                'error': err,
                                'type': dtype,
                                'value': val,
                                'length':data_value("length", dtypes, int, 0),
                                'not-in':data_value("in", dtypes, list),
                                'default':default,
                                'importance': importance()})
                return 0

            else:
                self.errors[dkey].append({'path': lpath,
                                'error': err,
                                'type': ktype,
                                'value': testkey,
                                'length':data_value("length", dtypes, int, 0),
                                'not-in':data_value("in", dtypes, list),
                                'default':default,
                                'importance': importance()})
                return 0

        dtype = data_value("type", dtypes)
        importancenlevel = 0
        if isinstance(dtype, list):
            if len(dtype) < 1:
                return True

            else:
                rvals = []
                for dt in dtype:
                    dts = dtypes.copy()
                    dts['type'] = dt
                    if self.test_type(dkey, dts, val) not in (None, 0):
                        return self.test_type(dkey, dts, val, vpath)

                set_error(3)
                return

        if dtype == 'list':
            if not isinstance(val, list):
                # Wrong type
                return set_error(3)

            if  vpath == None:
                return dtype

            if is_data_value("length", dtypes, int) and len(val) != dtypes["length"]:
                # wrong length
                return set_error(6)

            if is_data_value("items", dtypes, list):
                for index in range(len(dtypes["items"])):
                    ltype = dtypes["items"][index]
                    if index < len(val) and ltype not in (None, ''):
                        lpath = [] if vpath in (dkey, None) else vpath[:]
                        lpath.append(index)
                        # Test the sub-type
                        self.test_type(dkey, {'type': ltype}, val[index], lpath)

        elif dtype in ('dict', 'numbered dict'):
            if not isinstance(val, dict):
                # Wrong type
                return set_error(3)

            ktype = data_value("keys", dtypes, str)
            lpath = None if vpath in (dkey, None) else vpath[:]
            if is_data_value("keys", dtypes, str, True):
                for k in val.keys():
                    if re.match('--.*?--', k):
                        continue

                    if dtype == 'numbered dict':
                        try:
                            k = int(k)

                        except:
                            ktype = 'numeric (integer enclosed in double quotes)'
                            set_error(5, k)
                            ktype = data_value("keys", dtypes, str)

                    if ktype != '' and self.test_type(dkey, {'type': ktype}, k) == None:
                        # Wrong key-type
                        set_error(5, k)

            if  vpath == None:
                return dtype

            test_unknown = False
            test_keys = []
            for sdset in ("required", "sugested", "optional"):
                # Are there further sub-key/value restraints
                importancenlevel += 1
                knames = data_value(sdset, dtypes, list)
                for kn in knames:
                    test_unknown = True
                    if is_data_value('name', kn, str):
                        test_keys.append(kn['name'])
                        ktype = data_value("keys", kn, str)
                        vtype = data_value("types", kn, str)
                        if not kn['name'] in val.keys():
                            # The sub-key is missing
                            set_error(1, kn['name'], data_value("default", kn))

                        else:
                            # Is there a value restrained
                            spath = [] if vpath in (dkey, None) else vpath[:]
                            spath.append(kn['name'])
                            if is_data_value('type', kn, str) or is_data_value('in', kn, list):
                                # Test the value
                                self.test_type(dkey, kn , val[kn['name']], spath)

                            if isinstance(val[kn['name']], dict):
                                # If the sub-value is a dict
                                for k, v in val[kn['name']].items():
                                    if re.match('--.*?--', k):
                                        continue

                                    lpath = spath[:]
                                    if is_data_value("keys", kn, str, True) and self.test_type(dkey, {'type': ktype}, k) == None:
                                        # Wrong key-type in the dict
                                        set_error(5, k)

                                    if is_data_value("types", kn, str, True):
                                        # Test the sub-dict values
                                        lpath.append(k)
                                        self.test_type(dkey, {'type': vtype}, v, lpath)

                            if isinstance(val[kn['name']], list):
                                # If the sub-value is a list
                                if is_data_value("types", kn, str, True):
                                    for index in range(len(val[kn['name']])):
                                        # Test the sub-list values
                                        lpath = spath[:]
                                        lpath.append(k)
                                        self.test_type(dkey, {'type': vtype}, v, lpath)

            if test_unknown and data_value("allowed", dtypes, str) != 'all':
                ktype = data_value("keys", dtypes, str)
                lpath = None if vpath in (dkey, None) else vpath[:]
                for k in  val.keys():
                    if not k in test_keys:
                        # Unknown key
                        set_error(2, k)

        elif dtype == 'integer':
            if not isinstance(val, int):
                # Wrong type
                return set_error(3)

        elif dtype == 'sourceid':
            if not isinstance(val, int):
                # Wrong type
                return set_error(3)

            if self.check_data_lists and not val in self.sources:
                # Wrong type
                return set_error(3)

        elif dtype == 'groupid':
            if not isinstance(val, int):
                # Wrong type
                return set_error(3)

            if self.check_data_lists and not val in self.channel_groups:
                # Wrong type
                return set_error(3)

        elif dtype == 'logoid':
            try:
                val = int(val)

            except:
                # Wrong type
                return set_error(3)

            if self.check_data_lists and not val in self.logo_sources:
                # Wrong type
                return set_error(3)

        elif dtype == 'string':
            if not isinstance(val, (str, unicode)):
                # Wrong type
                return set_error(3)

            if is_data_value("length", dtypes, int) and len(val) != dtypes["length"]:
                # wrong length
                return set_error(6)

        elif dtype == 'tz-string':
            if not isinstance(val, (str, unicode)):
                # Wrong type
                return set_error(3)

            try:
                tz = pytz.timezone(val)

            except:
                # Wrong type
                return set_error(3)

        elif dtype == 'chanid':
            if self.check_data_lists and not val in self.chanids:
                # Wrong type
                return set_error(3)

        elif dtype == 'url':
            if not isinstance(val, (str, unicode)):
                # Wrong type
                return set_error(3)

        elif dtype == 'boolean':
            if not isinstance(val, bool):
                # Wrong type
                return set_error(3)

        elif dtype == 'time':
            try:
                st = val.split(':')
                st = datetime.time(int(st[0]), int(st[1]))
            except:
                # Wrong type
                return set_error(3)

        elif dtype == 'date':
            pass

        elif dtype == 'none':
            if val != None:
                # Wrong type
                return set_error(3)

        elif is_data_value("in", dtypes, list):
            if not val in dtypes['in']:
                return set_error(4)

        else:
            #~ self.config.log('unknown dtype: %s\n' % dtype)
            pass

        return dtype

    def test(self, f_type):
        def test_sub(dkey, sdata, level, otype, vpath = None):
            nlist = []
            if otype == 'list':
                for item in range(len(sdata)):
                    pkey = [] if vpath in (dkey, None) else vpath[:]
                    pkey.append(item)
                    vt = self.test_type(dkey, tlist[level], sdata[item], pkey)
                    if vt == None:
                        self.config.log('The value: %s in the %s list is not of type %s.\n' % \
                            (sdata[item], dkey, tlist[level]['type']))
                        continue

                    if len(tlist) > level +1:
                        nlist.extend(test_sub(dkey, sdata[item], level + 1, vt, pkey))

                    else:
                        nlist.append(sdata[item])

            elif otype in ('dict', 'numbered dict'):
                for k, v in sdata.items():
                    if re.match('--.*?--', k):
                        continue

                    pkey = [] if vpath in (dkey, None) else vpath[:]
                    pkey.append(k)
                    vt = self.test_type(dkey, tlist[level], v, pkey)
                    if vt == None:
                        self.config.log('The value: %s in the %s dict is not of type %s.\n' % \
                            (v, dkey, tlist[level]['type']))
                        continue

                    if len(tlist) > level +1:
                        nlist.extend(test_sub(dkey, v, level + 1, vt, pkey))

                    else:
                        nlist.append(v)

            return nlist

        def test_data_def(name):
            # 1 missing
            # 2 missing data
            # 4 missing values
            # 8 missing or empty data-keys
            # 16 both iter and key-path or values
            # 32 invalid iter
            # 64 fatal channel-data errors
            self.ddefs[name] = {}
            self.ddefs[name]['err'] = 0
            if not is_data_value([name], self.testfile, dict):
                self.ddefs[name]['err'] |= 1
                return

            url_type = data_value([name,"url-type"], self.testfile, int, 0)
            if not is_data_value([name,"data"], self.testfile, dict):
                self.ddefs[name]['type'] = -1
                self.ddefs[name]['err'] |= 2

            else:
                # We check on the data subkeys
                data_dict = self.testfile[name]["data"]
                data_OK = []
                data_empty = []
                data_wrong = []
                data_other = {}
                for k, v in data_dict.items():
                    if k in ('init-path', 'iter', 'key-path', 'values'):
                        if isinstance(v, list):
                            if len(v) == 0:
                                data_empty.append(k)

                            else:
                                data_OK.append(k)

                        else:
                            data_wrong.append(k)

                    elif k in data_value(['data_def_keys', name, 'data_keys'], self.keyfile, dict).keys():
                        # it is a value_def in data
                        pass

                    else:
                        data_other[k] = v

                if name == "channels" and len(data_OK) == 0 and len(data_wrong) == 0 and len(data_empty) == 0:
                    # It seems to be a channels list
                    known_chan_keys = []
                    for dset in ("required", "optional"):
                        if is_data_value(['channel_keys', dset], self.keyfile, dict):
                            known_chan_keys.extend(self.keyfile['channel_keys'][dset].keys())

                    rep = {}
                    c_err = 0
                    for k, v in data_other.items():
                        rep[k] = {}
                        rep[k]['missing'] = {}
                        rep[k]['wrong_type'] = {}
                        for dset in ("required", "optional"):
                            rep[k]['missing'][dset] = []
                            rep[k]['wrong_type'][dset] = {}
                            if is_data_value(['channel_keys', dset], self.keyfile, dict):
                                test_dict = self.keyfile['channel_keys'][dset]
                                for dkey in test_dict.keys():
                                    if not dkey in v.keys():
                                        rep[k]['missing'][dset].append(dkey)
                                        if dset == "required":
                                            c_err = 64
                                        continue

                                    tlist = data_value([dkey,"types"], test_dict, list)
                                    if len(tlist) == 0:
                                        print 'no types'
                                        continue

                                    vt = self.test_type(dkey, tlist[0], v[dkey])
                                    if vt == None:
                                        rep[k]['wrong_type'][dset][dkey] = tlist[0]['type']
                                        if dset == "required":
                                            c_err = 64

                        rep[k]['unknown'] = []
                        for ck in v.keys():
                            if not ck in known_chan_keys:
                                rep[k]['unknown'].append(ck)

                    self.ddefs[name]['type'] = 1
                    self.ddefs[name]['err'] |= c_err
                    self.ddefs[name]['rep'] = rep
                    self.ddefs['found'][name] = self.ddefs[name]['err']
                    return

                self.ddefs[name]['type'] = 0
                self.ddefs[name]['data'] = {}
                self.ddefs[name]['data']['wrong_type'] = data_wrong
                self.ddefs[name]['data']['empty'] = data_empty
                self.ddefs[name]['data']['unknown'] = data_other.keys()
                if not (('key-path' in data_OK and 'values' in data_OK) or 'iter' in data_OK):
                    self.ddefs[name]['err'] |= 8

                if 'iter' in data_dict.keys() and ('key-path' in data_dict.keys() or 'values' in data_dict.keys()):
                    self.ddefs[name]['err'] |= 16

                if 'iter' in data_OK:
                    for item in data_dict['iter']:
                        if not (isinstance(item, dict) and len(item) == 2 \
                          and is_data_value('key-path', item, list) and len(item['key-path']) > 0 \
                          and is_data_value('values', item, list) and len(item['values']) > 0):
                            self.ddefs[name]['err'] |= 32

            if not is_data_value([name,"values"], self.testfile, dict):
                self.ddefs[name]['type'] = -1
                self.ddefs[name]['err'] |= 4

            else:
                self.ddefs[name]['values'] = {}
                self.ddefs[name]['values']['missing'] = {}
                self.ddefs[name]['values']['set'] = {}
                self.ddefs[name]['values']['wrong_type'] = []
                self.ddefs[name]['values']['unknown'] = []
                self.ddefs[name]['values']['not_provided'] = []
                known_value_keys = []
                for dset in ("required", "optional", "detail"):
                    self.ddefs[name]['values']['missing'][dset] = []
                    self.ddefs[name]['values']['set'][dset] = []
                    if is_data_value(['data_def_keys', name, 'value_keys', dset], self.keyfile, list):
                        known_value_keys.extend(data_value(['data_def_keys', name, 'value_keys', dset], self.keyfile, list))
                        for k in data_value(['data_def_keys', name, 'value_keys', dset], self.keyfile, list):
                            if not k in data_value([name,"values"], self.testfile, dict).keys():
                                self.ddefs[name]['values']['missing'][dset].append(k)

                            elif is_data_value([name,"values", k], self.testfile, dict):
                                self.ddefs[name]['values']['set'][dset].append(k)

                for k, v in data_value([name,"values"], self.testfile, dict).items():
                    if not isinstance(v, dict):
                        self.ddefs[name]['values']['wrong_type'].append(k)

                    if not k in known_value_keys:
                        self.ddefs[name]['values']['unknown'].append(k)

                    if name in ('detail','detail2'):
                        if k in ("start-time","stop-time","name","channelid","prog_ID",
                            "detail_url","length","alt-start-time","alt-stop-time","gen_ID"):
                                continue

                        elif not k in data_value([name,"provides"], self.testfile, list):
                            self.ddefs[name]['values']['not_provided'].append(k)

            # To add check on ["data_def_keys"] and ["data_def_keys"]["data_keys"]
            self.ddefs['found'][name] = self.ddefs[name]['err']

        if not f_type in self.jsontypes.keys():
            return

        known_keys = []
        self.keydef = self.keyfile[self.jsontypes[f_type]]
        # First see what known keys are present and if they are of the right type
        for dset in ("required", "sugested", "optional"):
            self.errors = {}
            self.dkey_errors[dset] = {}
            self.dkey_errors[dset]['missing'] = []
            self.dkey_errors[dset]['wrong_type'] = {}
            if is_data_value([dset], self.keydef, dict):
                known_keys.extend(self.keydef[dset].keys())
                for dkey in self.keydef[dset].keys():
                    if not dkey in self.testfile.keys():
                        self.dkey_errors[dset]['missing'].append(dkey)
                        continue

                    tlist = data_value([dset, dkey,"types"], self.keydef, list)
                    if len(tlist) == 0:
                        print 'no types'
                        continue

                    vt = self.test_type(dkey, tlist[0], self.testfile[dkey])
                    if vt == None:
                        self.dkey_errors[dset]['wrong_type'][dkey] = tlist[0]['type']
                        continue

                    if len(tlist) > 1:
                        # And test any defined subkeys
                        end_node_list = test_sub(dkey, self.testfile[dkey], 1, vt)

                    else:
                        end_node_list = [self.testfile[dkey]]

            self.dkey_errors[dset]['errors'] = self.errors.copy()
            self.errors = {}
            self.report_key_errors(dset)

        # Report on found data_defs
        if f_type in (2, 3):
            self.ddefs = {}
            self.ddefs['found'] = {}
            known_keys.extend(data_value(["data_defs"], self.keyfile, list))
            for dkey in data_value(["data_defs"], self.keyfile, list):
                test_data_def(dkey)

            if len(self.ddefs['found']) > 0:
                self.config.log(['\n', 'The following data_defs were found (we can not jet test them):\n'])
                for dkey, derr in self.ddefs['found'].items():
                    self.config.log('  %s Of type: %s With Status: %s\n' % (dkey.ljust(15), self.ddefs[dkey]['type'], derr))

            else:
                self.config.log(['\n', 'No data_defs were found.\n'])

            if f_type == 2:
                if not 'base'in self.ddefs['found'].keys() and \
                  not ('channels' in self.ddefs['found'].keys() or 'base-channels'in self.ddefs['found'].keys()):
                    self.config.log(['A source file minimal needs either a "channels""\n', \
                            '    or a "base-channels data_def and a "base" data_def!'])

                if data_value("detail_processor", self.testfile, bool, False) and not 'detail' in self.ddefs['found'].keys():
                    self.config.log(['This source is set to process detail-pages,\n', \
                            '    but no "detail" data_def is set!\n'])

                if ('detail' in self.ddefs['found'].keys() or 'detail2' in self.ddefs['found'].keys()) \
                  and not data_value("detail_processor", self.testfile, bool, False):
                    self.config.log(['A "detail" data_def is precent but "detail_processor"\n', \
                            '    is not set. The data_def will not be used.\n'])

            if f_type == 3:
                if ((not 'channels' in self.ddefs['found'].keys()) or len(self.ddefs['found'])> 1):
                    self.config.log('A virtual-source must have a "channels" data_def!\n    Any other is not used.\n')

                if not data_value(['channels','type'], self.ddefs, int, 0) == 1:
                    self.config.log(['The "channels" data_def for a virtual-source must must be type 1!\n', \
                            '    (A dict with channelids with minimal their names)\n'])

        # Report on unknown main keys
        unknown = []
        unused = []
        known_keys.extend(data_value([self.jsontypes[f_type], "ignore_keys"], self.keyfile, list))
        for k in self.testfile.keys():
            if not k in known_keys and not re.match('--.*?--', k):
                if k in data_value([self.jsontypes[f_type], "unused_keys"], self.keyfile, list):
                    unused.append(k)

                else:
                    unknown.append(k)

        self.config.log('\n')
        if len(unused) > 0:
            self.config.log('The following keys were found but are not used:\n')
            for k in unused:
                self.config.log('  %s\n' % k)

        self.config.log('\n')
        if len(unknown) > 0:
            self.config.log('The following keys are unknown:\n')
            for k in unknown:
                self.config.log('  %s\n' % k)

        self.config.log('\n')

    def report_key_errors(self, dset):
        # Report on found inconsistancies
        if len(self.dkey_errors[dset]['missing']) > 0:
            self.config.log('The following %s main-keys are not set:\n' % dset)
            for dkey in self.dkey_errors[dset]['missing']:
                if is_data_value([dset, dkey,"default"], self.keydef):
                    self.config.log('  "%s": It will default to: %s\n' % \
                        (dkey.ljust(25), data_value([dset, dkey,"default"], self.keydef)))

                else:
                    self.config.log('  "%s": Without default\n' % dkey.ljust(25))

        else:
            self.config.log('All %s keys are present.\n' % dset)

        if len(self.dkey_errors[dset]['wrong_type']) > 0:
            self.config.log('The following %s main-keys have a wrong value type:\n' % dset)
            for dkey, dtype in self.dkey_errors[dset]['wrong_type'].items():
                self.config.log('  "%s": Must be of type: %s\n' % (dkey.ljust(25), dtype))

        else:
            self.config.log('All set %s keys are of the right type.\n' % dset)

        if len(self.dkey_errors[dset]['errors']) > 0:
            self.config.log('The following (potential) errors were found in %s main-keys:\n' % dset)
            for key, v in self.dkey_errors[dset]['errors'].items()[:]:
                del(self.dkey_errors[dset]['errors'][key])
                v.sort(key=lambda err: (err['error'], err['path']))
                act_err = 0
                for err in v:
                    if err['error'] > act_err:
                        act_err = err['error']
                        if act_err == 1:
                            self.config.log('  Missing sub-keys in main-key "%s":\n' % (key))

                        elif act_err == 2:
                            self.config.log('  Unrecognized sub-keys in main-key "%s":\n' % (key))

                        elif act_err == 3:
                            self.config.log('  Wrong value-types in main-key "%s":\n' % (key))

                        elif act_err == 4:
                            self.config.log('  Wrong value in main-key "%s":\n' % (key))

                        elif act_err == 5:
                            self.config.log('  Wrong sub-key-types in main-key "%s":\n' % (key))

                        elif act_err == 6:
                            self.config.log('  Wrong string or list length in main-key "%s":\n' % (key))

                        else:
                            break

                    if act_err == 1:
                        self.config.log('    %s"%s" is not set in "%s". It will default to "%s"\n' % \
                            (err['importance'].capitalize(), err['value'], err['path'], err['default']))

                    elif act_err == 2:
                        self.config.log('    key-value "%s" in %s is not recognized.\n' % (err['value'], err['path']))

                    elif act_err == 3:
                        self.config.log('    %svalue in %s should be of type: "%s".\n' % \
                            (err['importance'].capitalize(), err['path'], err['type']))

                    elif act_err == 4:
                        self.config.log('    value "%s" in %s should be one of %s.\n' % \
                            (err['importance'].capitalize(), err['value'], err['path'], err['not-in']))

                    elif act_err == 5:
                        self.config.log('    %ssub-key in %s should be of type: "%s".\n' % \
                            (err['importance'].capitalize(), err['path'], err['type']))

                    elif act_err == 6:
                        self.config.log('    %sList/String in %s should have length: %s.\n' % \
                        (err['importance'].capitalize(), err['path'], err['length']))

                    else:
                        break

#
