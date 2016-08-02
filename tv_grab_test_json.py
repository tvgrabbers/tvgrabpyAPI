#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import json, io, sys, os, tvgrabpyAPI, pytz, datetime
from DataTreeGrab import is_data_value, data_value

def load_data_lists():
    for s in j_file["sources"].keys():
        try:
            s = int(s)

        except:
            config.log('Invalid sourceID %s encountered. Should be a number.\n')
            continue

        if s < 1:
            config.log('Invalid sourceID %s encountered. Should be a bigger then 0.\n')
            continue

        sources.append(s)

    for s, v in j_file["source_channels"].items():
        if not is_data_value(["source_channels", s], j_file, dict):
            continue

        for c in v.keys():
            if not c in chanids:
                chanids.append(c)

    for s in data_value(["channel_groups"], j_file, dict).keys():
        try:
            s = int(s)

        except:
            config.log('Invalid groupID %s encountered. Should be a number.\n')
            continue

        if s < 0:
            config.log('Invalid groupID %s encountered. Should be a positive number.\n')
            continue

        channel_groups.append(s)

    for k in data_value(["logo_provider"], j_file, dict).keys():
        try:
            if int(k) not in logo_sources:
                logo_sources.append(int(k))

        except:
            continue

def test_type_key(tval):
    if isinstance(tval, list):
        for v in tval:
            test_type_key(v)

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
                test_type_key(v)

def test_type(dkey, dtypes, val, skey = None):
    def set_error(err, testkey = None):
        if skey == None and testkey == None:
            return None

        if not is_data_value(dkey, dkey_errors, list):
            dkey_errors[dkey] = []

        if testkey == None:
            dkey_errors[dkey].append({'path': skey,
                                                        'error': err,
                                                        'type': dtype,
                                                        'value': val,
                                                        'length':data_value("length", dtypes, int, 0),
                                                        'not-in':data_value("in", dtypes, list),
                                                        'default':data_value("default", dtypes, default: None),
                                                        'importance': importance})
            return 0

        else:
            dkey_errors[dkey].append({'path': skey,
                                                        'error': err,
                                                        'type': ktype,
                                                        'value': testkey,
                                                        'length':data_value("length", dtypes, int, 0),
                                                        'not-in':data_value("in", dtypes, list),
                                                        'default':data_value("default", dtypes, default: None),
                                                        'importance': importance})
            return 0

    dtype = data_value("type", dtypes)
    importance = 0
    if isinstance(dtype, list):
        if len(dtype) < 1:
            return True

        else:
            rvals = []
            for dt in dtype:
                dts = dtypes.copy()
                dts['type'] = dt
                vt = test_type(dkey, dts, val, skey)
                if vt != None:
                    return vt

            return

    if dtype == 'list':
        if not isinstance(val, list):
            return set_error(2)

        if is_data_value("length", dtypes, int) and len(val) != dtypes["length"]:
            return set_error(6)

        if is_data_value("items", dtypes, list):
            for index in range(len(dtypes["items"])):
                ltype = dtypes["items"][index]
                if index < len(val) and ltype not in (None, ''):
                    lkey = str(index) if skey in (dkey, None) else '%s:%s' % (skey, index)
                    test_type(dkey, {'type': ltype}, val[index], lkey)
                    #~ if test_type(dkey, {'type': ltype}, val[index]) == None:
                        #~ if skey == None:
                            #~ config.log("list item %s in %s is not of type %s!\n" % (index, val, ltype))

                        #~ else:
                            #~ config.log('list item %s in %s from "%s" is not of type %s!\n' % (index, val, skey, ltype))

    elif dtype == 'dict':
        if not isinstance(val, dict):
            return set_error(2)

        if is_data_value("keys", dtypes, str, True):
            ktype = data_value("keys", dtypes, str)
            for k in val.keys():
                if k in ("--description--", "--example--"):
                    continue

                if test_type(dkey, {'type': ktype}, k) == None:
                    set_error(5, k)
                    #~ if skey == None:
                        #~ config.log('Key value "%s" in "%s" is not of type %s!\n' % (k, dkey, ktype))

                    #~ else:
                        #~ config.log('Key value "%s" in "%s" from %s is not of type %s!\n' % \
                            #~ (k, skey, dkey, ktype))

        for sdset in ("required", "sugested", "optional"):
            importance += 1
            knames = data_value(sdset, dtypes, list)
            for kn in knames:
                if is_data_value('name', kn, str):
                    if not kn['name'] in val.keys():
                        set_error(1, kn['name'])
                        #~ if skey == None:
                            #~ config.log('%s key value "%s" in %s is not set!\n' % \
                                #~ (sdset.capitalize(), kn['name'], dkey))

                        #~ else:
                            #~ config.log('%s key value "%s" in the "%s" item from %s is not set!\n' % \
                                #~ (sdset.capitalize(), kn['name'], skey, dkey))

                    else:
                        if is_data_value('type', kn, str) or is_data_value('in', kn, list):
                            lkey = kn['name'] if skey in (dkey, None) else '%s:%s' % (skey, kn['name'])
                            test_type(dkey, kn , val[kn['name']], lkey)
                            #~ if skey == None:
                                #~ config.log('The %s "%s" value: "%s" from %s is not of type %s!\n' % \
                                    #~ (sdset, kn['name'], val[kn['name']], dkey, kn['type']))

                            #~ else:
                                #~ config.log('The %s "%s" value: "%s" in the "%s" item from %s is not of type %s!\n' % \
                                    #~ (sdset, kn['name'], val[kn['name']], skey, dkey, kn['type']))

                        #~ elif is_data_value('in', kn, list) and val[kn['name']] not in kn['in']:
                            #~ if skey == None:
                                #~ config.log('The %s "%s" value: "%s" from %s is not of in %s!\n' % \
                                    #~ (sdset, kn['name'], val[kn['name']], dkey, kn['in']))

                            #~ else:
                                #~ config.log('The %s "%s" value: "%s" in the "%s" item from %s is not in %s!\n' % \
                                    #~ (sdset, kn['name'], val[kn['name']], skey, dkey, kn['in']))

                        if isinstance(val[kn['name']], dict) and is_data_value("keys", kn, str, True):
                            ktype = data_value("keys", kn, str)
                            for k in val[kn['name']].keys():
                                if k in ("--description--", "--example--"):
                                    continue

                                if test_type(dkey, {'type': ktype}, k) == None:
                                    if skey == None:
                                        config.log('Key value "%s" in "%s" is not of type %s!\n' % (k, dkey, ktype))

                                    else:
                                        config.log('Key value "%s" in "%s" from %s is not of type %s!\n' % \
                                            (k, skey, dkey, ktype))

                        if isinstance(val[kn['name']], (dict, list)) and is_data_value("types", kn, str, True):
                            vtype = data_value("types", kn, str)
                            for k, v in val[kn['name']].values():
                                if k in ("--description--", "--example--"):
                                    continue

                                if test_type(dkey, {'type': vtype}, v) == None:
                                    if skey == None:
                                        config.log('"%s" value "%s" in "%s" is not of type %s!\n' % (k, v, dkey, vtype))

                                    else:
                                        config.log('"%s" value "%s" in "%s" from %s is not of type %s!\n' % \
                                            (k, v, skey, dkey, vtype))

    elif dtype == 'numbered dict':
        if not isinstance(val, dict):
            return set_error(2)

        ktype = data_value("keys", dtypes, str, None)
        for k in val.keys():
            if k in ("--description--", "--example--"):
                continue

            try:
                k = int(k)
                if ktype not in (None, '') and test_type(dkey, {'type': ktype}, k) == None:
                    if skey == None:
                        config.log('Key value "%s" in the "%s" dict is not of type %s!\n' % (k, dkey, ktype))

                    else:
                        config.log('Key value "%s" in the "%s" dict from %s is not of type %s!\n' % \
                            (k, skey, dkey, ktype))

            except:
                if skey == None:
                    config.log('Key value "%s" in the "%s" dict is not numeric!\n' % (k, dkey))

                else:
                    config.log('Key value "%s" in the "%s" dict from %s is not numeric!\n' % \
                        (k, skey, dkey))

    elif dtype == 'integer':
        if not isinstance(val, int):
            return set_error(2)

    elif dtype == 'sourceid':
        if not isinstance(val, int):
            return set_error(2)

        if not val in sources:
            return set_error(2)

    elif dtype == 'groupid':
        if not isinstance(val, int):
            return set_error(2)

        if not val in channel_groups:
            return set_error(2)

    elif dtype == 'logoid':
        try:
            val = int(val)

        except:
            return set_error(2)

        if not val in logo_sources:
            return set_error(2)

    elif dtype == 'string':
        if not isinstance(val, (str, unicode)):
            return set_error(2)

        if is_data_value("length", dtypes, int) and len(val) != dtypes["length"]:
            return set_error(6)

    elif dtype == 'tz-string':
        if not isinstance(val, (str, unicode)):
            return set_error(2)

        try:
            tz = pytz.timezone(val)

        except:
            return set_error(2)

    elif dtype == 'chanid':
        if not val in chanids:
            return set_error(2)

    elif dtype == 'url':
        if not isinstance(val, (str, unicode)):
            return set_error(2)

    elif dtype == 'boolean':
        if not isinstance(val, bool):
            return set_error(2)

    elif dtype == 'time':
        try:
            st = val.split(':')
            st = datetime.time(int(st[0]), int(st[1]))
        except:
            return set_error(2)

    elif dtype == 'date':
        pass

    elif dtype == 'none':
        if val != None:
            return set_error(2)

    elif is_data_value("in", dtypes, list:):
        if not val in dtypes['in']:
            return set_error(3)

    else:
        #~ config.log('unknown dtype: %s\n' % dtype)
        pass
        #~ return set_error(2)

    return dtype

def test_file(data, f_type):
    def test_sub(dkey, sdata, level, otype, skey = None):
        nlist = []
        if otype == 'list':
            for item in range(len(sdata)):
                pkey = str(item) if skey in (dkey, None) else '%s:%s' % (skey, item)
                vt = test_type(dkey, tlist[level], sdata[item], pkey )
                if vt == None:
                    config.log('The value: %s in the %s list is not of type %s.\n' % \
                        (sdata[item], dkey, tlist[level]['type']))
                    continue

                if len(tlist) > level +1:
                    nlist.extend(test_sub(dkey, sdata[item], level + 1, vt, pkey))

                else:
                    nlist.append(sdata[item])

        elif otype in ('dict', 'numbered dict'):
            for k, v in sdata.items():
                if k in ("--description--", "--example--"):
                    continue

                if skey in (dkey, None):
                    pkey = k

                else:
                    pkey = '%s:%s' % (skey, k)

                vt = test_type(dkey, tlist[level], v, pkey)
                if vt == None:
                    config.log('The value: %s in the %s dict is not of type %s.\n' % \
                        (v, dkey, tlist[level]['type']))
                    continue

                if len(tlist) > level +1:
                    nlist.extend(test_sub(dkey, v, level + 1, vt, pkey))

                else:
                #~ elif vt in ('list', 'dict', 'numbered dict'):
                    nlist.append(v)

        return nlist

    known_keys = ["--description--", "--example--"]
    testdict = t_file[f_type]
    # First see what known keys are present and if they are of the right type
    for dset in ("required", "sugested", "optional"):
        dkey_errors = {}
        dkey_errors['missing'] = []
        dkey_errors['wrong_type'] = {}
        if is_data_value([dset], testdict, dict):
            known_keys.extend(testdict[dset].keys())
            for dkey in testdict[dset].keys():
                if not dkey in data.keys():
                    dkey_errors['missing'].append(dkey)
                    continue

                tlist = data_value([dset, dkey,"types"], testdict, list)
                if len(tlist) == 0:
                    #~ config.log('No type set for %s' % dkey)
                    continue

                vt = test_type(dkey, tlist[0], data[dkey])
                if vt == None:
                    #~ dkey_errors['wrong_type'][dkey] = tlist[0]['type']
                    config.log('The data under key %s is not of type %s.\n' % (dkey, tlist[0]['type']))
                    continue

                if len(tlist) > 1:
                    # And test any defined subkeys
                    end_node_list = test_sub(dkey, data[dkey], 1, vt)

                else:
                    end_node_list = [data[dkey]]

        # Report on unset main keys
        if len(dkey_errors['missing']) > 0:
            config.log('The following %s main-keys are not set:\n' % dset)
            for dkey in dkey_errors['missing']:
                if is_data_value([dset, dkey,"default"], testdict):
                    config.log('  %s: It will default to: %s\n' % (dkey.ljust(25), data_value([dset, dkey,"default"], testdict)))

                else:
                    config.log('  %s: Without default\n' % dkey.ljust(25))

        else:
            config.log('All %s keys are present\n' % dset)

    # Report on found data_defs
    if is_data_value(["data_defs"], testdict, list):
        ddefs = []
        known_keys.extend(testdict["data_defs"])
        for dkey in testdict["data_defs"]:
            if dkey in data.keys():
                ddefs.append(dkey)

        if len(ddefs) > 0:
            config.log('The following data_defs were found:\n')
            for dkey in ddefs:
                config.log('  %s\n' % dkey)

        else:
            config.log('No data_defs were found.\n')

    # Report on unknown main keys
    unknown = []
    known_keys.extend(data_value([f_type, "extra_keys"], t_file, list))
    for k in data.keys():
        if not k in known_keys:
            unknown.append(k)

    if len(unknown) > 0:
        config.log('The following keys are unknown:\n')
        for k in unknown:
            config.log('  %s\n' % k)

    config.log('\n')

config = tvgrabpyAPI.Configure('tv_grab_test_json')
cmd = sys.argv
if len(cmd) < 2:
    config.log('Please give the name of the json file to test.\n')
    sys.exit(-1)

config.get_json_datafiles()
logo_sources = config.xml_output.logo_source_preference
sources = []
chanids = []
channel_groups = []
file_name = cmd[1]
fle = config.IO_func.open_file(file_name, 'r', 'utf-8')
if fle == None:
    sys.exit(-1)

j_file = json.load(fle)
#~ t_file = self.fetch_func.get_json_data('tv_grab_keys', fpath = self.opt_dict['sources'])
fle = config.IO_func.open_file('../sourcematching/tv_grab_keys.json', 'r', 'utf-8')
if fle == None:
    sys.exit(-1)

t_file = json.load(fle)
for v in t_file.values():
    test_type_key(v)

if not isinstance(j_file, dict):
    config.log(['The file %s is a correct JSON file\n' % file_name,'  but is not recognized.\n'])
    sys.exit(-1)

elif file_name.split('/')[-1][:8] == 'tv_grab_' and "sources" in j_file.keys() and "source_channels" in j_file.keys():
    config.log( 'The file %s is a correct grabber-JSON file\n' % file_name)
    load_data_lists()
    test_file(j_file, 'grabberfile')

elif file_name.split('/')[-1][:7] == 'source-' and "name" in j_file.keys():
    config.log( 'The file %s is a correct source-JSON file\n' % file_name)
    test_file(j_file, 'sourcefile')

else:
    config.log(['The file %s is a correct JSON file\n' % file_name,'  but is not recognized.\n'])
    sys.exit(-1)

