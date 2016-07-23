#!/bin/sh

# This is a small script to call tv_grab_nl.py and subsequently feed the result to EyeTV.
# You will need to customize with the paths where you store the script and the data.

# To automatically run this script every day, see LaunchAgent configuration update_eyetv_guid.plist

cd /Users/user/Scripts/tvgrabnlpy
basename=`date '+%A%Hh'`
mkdir -p "data"
xmlfile="data/$basename.xml"
logfile="data/$basename.log"

# Fetch TV guide from www.tvgids.nl
./tv_grab_nl.py --config-file tvgrab.conf --days 6 --slowdays 2 --output $xmlfile --cache tvgrab.cache 2> $logfile

# open EyeTV with XMLTV file
open -a EyeTV $xmlfile
