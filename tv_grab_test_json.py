#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import json, io, sys, os, tvgrabpyAPI, pytz, datetime
if tvgrabpyAPI.version()[1:4] != (1,0,1):
    sys.stderr.write("This instance of tv_grab_test_json_py requires tv_grab_py_API 1.0.1\n")
    sys.exit(2)

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

def test_type(dkey, dtypes, val, vpath = None):
    def importance():
        if importancenlevel == 1:
            return 'required '

        elif importancenlevel == 2:
            return 'sugested '

        elif importancenlevel == 3:
            return 'optional '

        return ''

    def set_error(err, testkey = None, default = None):
        if vpath == None and testkey == None:
            return None

        if not is_data_value(dkey, dkey_errors, list):
            dkey_errors[dkey] = []

        if testkey == None:
            dkey_errors[dkey].append({'path': vpath,
                                                        'error': err,
                                                        'type': dtype,
                                                        'value': val,
                                                        'length':data_value("length", dtypes, int, 0),
                                                        'not-in':data_value("in", dtypes, list),
                                                        'default':default,
                                                        'importance': importance()})
            return 0

        else:
            dkey_errors[dkey].append({'path': lpath,
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
                if test_type(dkey, dts, val) not in (None, 0):
                    return test_type(dkey, dts, val, vpath)

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
                    test_type(dkey, {'type': ltype}, val[index], lpath)

    elif dtype in ('dict', 'numbered dict'):
        if not isinstance(val, dict):
            # Wrong type
            return set_error(3)

        ktype = data_value("keys", dtypes, str)
        lpath = None if vpath in (dkey, None) else vpath[:]
        if is_data_value("keys", dtypes, str, True):
            for k in val.keys():
                if k in ("--description--", "--example--"):
                    continue

                if dtype == 'numbered dict':
                    try:
                        k = int(k)

                    except:
                        ktype = 'numeric (integer enclosed in double quotes)'
                        set_error(5, k)
                        ktype = data_value("keys", dtypes, str)

                if ktype != '' and test_type(dkey, {'type': ktype}, k) == None:
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
                            test_type(dkey, kn , val[kn['name']], spath)

                        if isinstance(val[kn['name']], dict):
                            # If the sub-value is a dict
                            for k, v in val[kn['name']].items():
                                if k in ("--description--", "--example--"):
                                    continue

                                lpath = spath[:]
                                if is_data_value("keys", kn, str, True) and test_type(dkey, {'type': ktype}, k) == None:
                                    # Wrong key-type in the dict
                                    set_error(5, k)

                                if is_data_value("types", kn, str, True):
                                    # Test the sub-dict values
                                    lpath.append(k)
                                    test_type(dkey, {'type': vtype}, v, lpath)

                        if isinstance(val[kn['name']], list):
                            # If the sub-value is a list
                            if is_data_value("types", kn, str, True):
                                for index in range(len(val[kn['name']])):
                                    # Test the sub-list values
                                    lpath = spath[:]
                                    lpath.append(k)
                                    test_type(dkey, {'type': vtype}, v, lpath)

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

        if not val in sources:
            # Wrong type
            return set_error(3)

    elif dtype == 'groupid':
        if not isinstance(val, int):
            # Wrong type
            return set_error(3)

        if not val in channel_groups:
            # Wrong type
            return set_error(3)

    elif dtype == 'logoid':
        try:
            val = int(val)

        except:
            # Wrong type
            return set_error(3)

        if not val in logo_sources:
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
        if not val in chanids:
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
        #~ config.log('unknown dtype: %s\n' % dtype)
        pass

    return dtype

def test_file(data, f_type):
    def test_sub(dkey, sdata, level, otype, vpath = None):
        nlist = []
        if otype == 'list':
            for item in range(len(sdata)):
                pkey = [] if vpath in (dkey, None) else vpath[:]
                pkey.append(item)
                vt = test_type(dkey, tlist[level], sdata[item], pkey)
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

                pkey = [] if vpath in (dkey, None) else vpath[:]
                pkey.append(k)
                vt = test_type(dkey, tlist[level], v, pkey)
                if vt == None:
                    config.log('The value: %s in the %s dict is not of type %s.\n' % \
                        (v, dkey, tlist[level]['type']))
                    continue

                if len(tlist) > level +1:
                    nlist.extend(test_sub(dkey, v, level + 1, vt, pkey))

                else:
                    nlist.append(v)

        return nlist

    known_keys = ["--description--", "--example--"]
    testdict = t_file[f_type]
    for dset in ("required", "sugested", "optional"):
        # First see what known keys are present and if they are of the right type
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
                    continue

                vt = test_type(dkey, tlist[0], data[dkey])
                if vt == None:
                    dkey_errors['wrong_type'][dkey] = tlist[0]['type']
                    continue

                if len(tlist) > 1:
                    # And test any defined subkeys
                    end_node_list = test_sub(dkey, data[dkey], 1, vt)

                else:
                    end_node_list = [data[dkey]]

        # Report on found inconsistancies
        if len(dkey_errors['missing']) > 0:
            config.log('The following %s main-keys are not set:\n' % dset)
            for dkey in dkey_errors['missing']:
                if is_data_value([dset, dkey,"default"], testdict):
                    config.log('  "%s": It will default to: %s\n' % \
                        (dkey.ljust(25), data_value([dset, dkey,"default"], testdict)))

                else:
                    config.log('  "%s": Without default\n' % dkey.ljust(25))

        else:
            config.log('All %s keys are present.\n' % dset)

        if len(dkey_errors['wrong_type']) > 0:
            config.log('The following %s main-keys have a wrong value type:\n' % dset)
            for dkey, dtype in dkey_errors['wrong_type'].items():
                config.log('  "%s": Must be of type: %s\n' % (dkey.ljust(25), dtype))

        else:
            config.log('All set %s keys are of the right type.\n' % dset)

        del(dkey_errors['missing'])
        del(dkey_errors['wrong_type'])

        if len(dkey_errors) > 0:
            config.log('The following (potential) errors were found in %s main-keys:\n' % dset)
            for key, v in dkey_errors.items()[:]:
                del(dkey_errors[key])
                v.sort(key=lambda err: (err['error'], err['path']))
                act_err = 0
                for err in v:
                    if err['error'] > act_err:
                        act_err = err['error']
                        if act_err == 1:
                            config.log('  Missing sub-keys in main-key "%s":\n' % (key))

                        elif act_err == 2:
                            config.log('  Unrecognized sub-keys in main-key "%s":\n' % (key))

                        elif act_err == 3:
                            config.log('  Wrong value-types in main-key "%s":\n' % (key))

                        elif act_err == 4:
                            config.log('  Wrong value in main-key "%s":\n' % (key))

                        elif act_err == 5:
                            config.log('  Wrong sub-key-types in main-key "%s":\n' % (key))

                        elif act_err == 6:
                            config.log('  Wrong string or list length in main-key "%s":\n' % (key))

                        else:
                            break

                    if act_err == 1:
                        config.log('    %s"%s" is not set in "%s". It will default to "%s"\n' % \
                            (err['importance'].capitalize(), err['value'], err['path'], err['default']))

                    elif act_err == 2:
                        config.log('    key-value "%s" in %s is not recognized.\n' % (err['value'], err['path']))

                    elif act_err == 3:
                        config.log('    %svalue in %s should be of type: "%s".\n' % \
                            (err['importance'].capitalize(), err['path'], err['type']))

                    elif act_err == 4:
                        config.log('    value "%s" in %s should be one of %s.\n' % \
                            (err['importance'].capitalize(), err['value'], err['path'], err['not-in']))

                    elif act_err == 5:
                        config.log('    %ssub-key in %s should be of type: "%s".\n' % \
                            (err['importance'].capitalize(), err['path'], err['type']))

                    elif act_err == 6:
                        config.log('    %sList/String in %s should have length: %s.\n' % \
                        (err['importance'].capitalize(), err['path'], err['length']))

                    else:
                        break

    # Report on found data_defs
    if is_data_value(["data_defs"], testdict, list):
        ddefs = []
        known_keys.extend(testdict["data_defs"])
        for dkey in testdict["data_defs"]:
            if dkey in data.keys():
                ddefs.append(dkey)

        if len(ddefs) > 0:
            config.log('The following data_defs were found (we can not jet test them):\n')
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

dkey_errors = {}
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

