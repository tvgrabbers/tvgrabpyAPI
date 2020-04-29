# tvgrabpyAPI

[Goto the WIKI](https://github.com/tvgrabbers/tvgrabpyAPI/wiki)

## Sometime after October 1st 2017 TheTVDB API V1 will stop working.
At present we are working on support for the API V2. A beta release is expected soon.

## New [version 1.0.7](https://github.com/tvgrabbers/tvgrabpyAPI/releases/tag/stable-1.0.7) release based on [DataTreeGrab module v1.4.0](https://github.com/tvgrabbers/DataTree/releases/tag/stable-1.4.0)

**17-05-2017** (dtg 1.3.3) With a significant speed increase of in my use case 30% (from 68 minutes to 48 minutes)  
**10-07-2017** (dtg 1.4.0) With now an even larger speed increase of in my use case 65% to 23.5 minutes (1.72 sec/page)  

### Summary

tv_grab_py_API is an API for creating xmltv compatible tv grabbers. It is the succesor of [tv_grab_nl_py version 2.2](https://github.com/tvgrabbers/tvgrabnlpy) making all of its functionallity available to the rest of the world.

### Requirements

 * Python 2.7.9 or higher (currently not python 3.x)
 * The [pytz module](http://pypi.python.org/pypi/pytz)
 * The [requests module](https://pypi.python.org/pypi/requests)
 * The [DataTreeGrab module](https://github.com/tvgrabbers/DataTree/)
 * Connection with the Internet

#### Ubuntu Focal 20.04 Users ONLY ###

* The latest version of Ubuntu no longer provides the python2 versions of python-requests or its dependency python-urllib3
* You can download compatible .deb packages [here](https://github.com/tvgrabbers/tvgrabpyAPI/files/4534005/python-requests.zip)
* To install unpack the zip file into a directory
* Run the following commands from that directory
  * `sudo dpkg -i python-urllib3_1.25.8-1_all.deb`
  * `sudo dpkg -i python-requests_2.22.0-2build1_all.deb`
  * If you get an error about missing dependencies run the following command:
    * `sudo apt-get install python2 python2-dev python-tz python-certifi python-chardet python-idna python-cryptography python-socks python-six python-ipaddress ca-certificates`

### Installation

* Especially under Windows, make sure Python 2.7.9 or higher is installed 
* Make sure the above mentioned Python 2 packages are installed on your system
* Download the latest release and unpack it into a directory
* Run:
  * under Linux: `sudo ./setup.py install` from that directory
  * under Windows depending on how you installed Python:
    * `setup.py install` from that directory
    * Or: `Python setup.py install` from that directory

    (the frontend script(s) will install into `C:\Program Files\Python27\Scripts`)
* Run the frontend (presently only tv_grab_nl3.py) with --configure
* Check the created configuration file ~/.xmltv/tv_grab_nl3.conf and activate the desired channels.

### Some features

 * No need for anybody who wants to create a grabber to know much about Python. You mainly must write one or more json data_defs defining one or more sources. These are [DataTreeGrab data_defs](https://github.com/tvgrabbers/DataTree/wiki/data_def_language) with some specific extensions.
 * All retrieved data is stored in an sqlite database which:
  * speeds up data retrieval
  * makes it possible to repeatetly access the data again while off-line  
 
 * Extensive list of user-settable options to give a user maximum oportunity to adapt the program to his or her need.
 * User setable genre translation tables with developer settable defaults.
 * Multiple language support (currently English and Dutch).
 * data_def updates are automatic.
 * theTVDB.com lookup.
