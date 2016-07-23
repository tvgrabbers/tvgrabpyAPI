#!/bin/sh

# Je kunt dit script met verschillende configuraties draaien
# die je met de onderstaande code op de command line mee kunt geven
# pas alle andere optie in het configuratie bestand aan
# Wanneer je niets ingeeft dan wordt: $HOME/.xmltv/tv_grab_py.conf gebruikt
# Als het goed is dan verwijst $HOME naar je homedirectory

conffile=${1:-"$HOME/.xmltv/tv_grab_py.conf"}
xmlfile="/tmp/tvgrabnl-xmlout.xml"

if [ ! -f $conffile ]; then
    echo "Ik kan het configuratie bestand: $conffile niet vinden"
    exit
fi

# Pas het pad aan naar waar je tv_grab_nl.py hebt neergezet
/usr/local/bin/tv_grab_nl.py --config-file $conffile --output $xmlfile

errorcode=$?
if [ $errorcode -ne 0 ]; then
    echo "tv_grab_nl.py is met errorcode $errorcode afgesloten"
    echo "Controleer je logbestand ${conffile}.log"
    exit
fi

# Import into mythTV
# controleer of het pad klopt 'which mythfilldatabase' zou dit moeten geven
# Bij Gentoo is dit bijv. /usr/bin/
# pas ook eventueel sourceid aan naar het juiste id
# met '--syslog local5' log je naar het systeemlog onder het id 'local5'
# alternatief kun je met '--logpath <pathname>' een log directory ingeven

/usr/local/bin/mythfilldatabase --syslog local5 --file --xmlfile $xmlfile --sourceid 1

# Draai dit script als een cron job, bij voorkeur na 04:00 's nachts. E.g.
# 24 05 * * * /home/user/bin/update_epg.sh
# Wanneer je tv_grab_nl.py in verbose modus laat staan (quiet = False)
# en je cron ingesteld hebt om het resultaat te mailen dan krijg je het
# resultaat log toegemaild.
# Stel het log level dan bijvoorbeeld in op 5 (errors en sammenvattingen)
