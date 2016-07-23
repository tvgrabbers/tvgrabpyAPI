#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import pickle, io, os, sys

# If you like to create a translation, you do the following.
# - copy this file to a file with the two letter short for that language replacing "en".
# - also fill this two letter short in the lang variable below
# - replace the text strings with your language version, but:
#       - keep the '%' (%s, %d, etc) markers in place as they get replaced by things like the name of a file
#       - if there is an EOL '\n' at the end, leave it also in place, but also do not add your own
#       - however in some situations you can spread the text over multiple lines
#       - keep any indentations at the start
# - run this new created script to create the langage file for your own use
# - send us this new created script and we probably include it with the language file in the package.
# - check regularily if you need to update the script, update the version and send us the updated version.

# There are a few special categories:
# -  In texts[u'config][u'help'] you should check that the output on the --help option does not excede a width of 80
#    Else use spaces and newlines to layout.
# -  In texts[u'config][u'confighelp'] there are several groups followed by empty lines. If empty they are not printed,
#    but you can use them if you need more space. e.g. 1 - 10, 11 - 16, 21 -  39, 41 - 52, 61 - 67, 71 - 77, 81 - 87, 91 - 139, ...

name = 'tv_grab_text'
version = (1, 0, 0)
lang = 'nl'
language = 'Nederlands'

def load_texts():
    texts = {
        u'config':{
            u'error':{
                -2: u'Het %se tekst bestand is geladen\n' % (language),
                -1: u'Fout bij het maken van de bericht tekst! (%s, %s: %s)\n',
                0: u'De bericht tekst (%s, %s: %s) is niet gevonden!\n',
                1: u'Geen valide bron beschrijving voor %s gevonden. De bron wordt uitgeschakeld!\n',
                2: u'Je kunt dit script niet als "root" draaien behalve met de --configure optie.\n' + \
                    'Wanneer je --configure als "root" draait, dan wordt de configuratie in\n' + \
                    '"/etc/tvgrabpyAPI/" geplaatst en als reserve configuratie gebruikt.\n',
                3: u'Fout bij het bijwerken van de nieuwe configuratie.\n',
                4: u'Verwijder ajb het oude configuratie bestand en draai opnieuw met de --configure flag.\n',
                5: u'Het configuratie bestand %s is bijgewerkt!\n',
                6: u'Controleer of je tevreden bent met de instellingen.\n',
                7: u'Wanneer dit een nieuwe installatie is, activeer dan nu eerst de gewenste zenders!\n',
                8: u'Het configuratiebestand: %s wordt aangemaakt\n',
                9: u'Fout bij het maken van de nieuwe configuratie. Probeer de oude terug te zetten.\n',
                10: u'Het configuratie bestand %s is aangemaakt!\n',
                11: u'De opties in het configuratiebestand %s zijn bijgewerkt!\n',
                12: u'Een offset %s hoger dan het maximum is belachelijk. We zetten het op %s',
                13: u'We kunnen maximaal 14 dagen vooruit kijken. Resetting!\n',
                14: u'De folder %s wordt aangemaakt,\n',
                15: u'Er kan niet naar het uitvoer bestand: %s geschreven worden.\n',
                16: u'Er is geen toegang tot de configuratie/log folder: %s\n',
                17: u'Het logbestand: %s kan niet worden geopend\n',
                18: u'Het configuratie bestand: %s wordt gebruikt\n',
                19: u'Het alternatief configuratie bestand %s wordt geprobeerd.\n',
                20: u'Er kan niet naar het cache bestand: %s geschreven worden.\n',
                21: u'Fout bij de toegang tot de cache (folder): %s\n',
                22: u'Alles wordt in snelle modus gezet\n',
                23: u'De zender: %s wordt in snelle modus gezet\n',
                24: u'Een maximale beschrijving van %d tekens wordt voor zender %s ingesteld\n',
                25: u'Een maximale overlap van 0 betekent een overlap strategy van: "%s"\n',
                26: u'Een maximale overlap van 0 betekent voor zender %s een overlap strategy van: "%s"\n',
                27: u'Een maximale overlap van: %d wordt voor zender %s gebruikt.\n',
                28: u'overlap strategy voor zender: %s is ingesteld op: "%s"\n',
                31: u'Draai het script opnieuw met de --configure flag.\n',
                32: u'"legacy_xmltvids = True" wordt toegevoegd\n',
                33: u'Draai het script met "--configure" om het permanent te maken.\n',
                34: u'De onbekende afdeling "%s" wordt genegeerd.\n',
                35: u'De configuratie regel "%s" wordt genegeerd. Deze bevindt zich buiten een bekende afdeling.\n',
                36: u'Fout bij het lezen van de configuratie.\n',
                37: u'Fout bij het lezen van een regel van de [Configuration] afdeling in %s:',
                38: u'Fout bij het lezen van een regel van de [Channels] afdeling in %s:',
                39: u'De zender afdeling [%s] wordt genegeerd. Onbekende zender.\n',
                40: u'Fout bij het lezen van een regel van de [%s] afdeling in %s:',
                41: u'Fout bij het lezen van het standaarden bestand: %s\n',
                43: u'Fout bij het lezen van het instellingenbestand op github.\n',
                44: u'Het is onmogelijk de configuratie voort te zetten!\n',
                45: u'Een ongeldige start tijd voor %s in de gecombineerde zender: %s\n  Het wordt verwijderd!',
                46: u'Een ongeldige eind tijd voor %s in de gecombineerde zender: %s\n  Het wordt verwijderd!',
                62: u'Niet alle zender informatie kon worden binnen gehaald.\n',
                63: u'Probeer opnieuw over 15 minuten of zo; of schakel de falende bron uit.\n',
                64: u'De Bron %s (%s) is uitgeschakeld',
                65: u'Er worden geen detail pagina\'s van %s (%s) gehaald.',
                66: u'Zender specifieke instellinge anders dan de bovenstaande (uitsluitend voor de actieve zenders!):',
                67: u'  de prime_source instelling: %s (%s) in het .json bestand wordt niet gebruikt\n',
                68: u'  De Bron %s (%s) is uitgeschakeld\n',
                69: u'  De detail Bron %s (%s) is uitgeschakeld\n',
                70: u'Fout bij het openen van het oude configuratie bestand. Er wordt een nieuwe aangemaakt.\n',
                71: u'Fout bij het lezen van de oude configuratie\n'
                },
            u'help':{
                1: u'  Een verzamelaar van TV programmagegevens vanuit meerdere bronnen,\n',
                2: u'  die vervolgens die gegevens combineert in één XMLTV compatibele lijst.',
                3: u'Toon deze tekst',
                5: u'Toon de versie',
                6: u'Geeft een korte beschrijving van het programma',
                7: u'Geeft een uitgebreide beschrijving van het programma\n' + \
                    'in het engels',
                8: u'xmltv vereiste optie',
                9: u'Geeft de gewenste methode om aangeroepen te worden',
                10: u'Geeft de beschikbare bronnen',
                11: u'Schakel een genummerde bron uit. Zie "--show-sources"\n' + \
                    'voor een lijst van de beschikbare bronnen.',
                12: u'Geeft de beschikbare detail bronnen',
                13: u'Geeft de beschikbare logo bronnen',
                15: u'Schakel een genummerde bron uit voor detail pagina\'s.\n' + \
                    'Zie "--show-detail-sources" voor een lijst van de\n' + \
                    'beschikbare bronnen.',
                16: u'Schakel het ophalen van extra gegevens van ttvdb.com uit',
                17: u'Zoek op ttvdb.com naar een serie titel en sla hem\n' + \
                    'eventueel met het ID op in de database.\n' + \
                    'Plaats aanhalingstekens om de titel! Voeg eventueel\n' + \
                    'achter de titel een tweeletterige taalcode toe.\n',
                18: u'Voeg"%s" toe achter het xmltv id\n',
                19: u'Verwijder zoals voor versie 2.2.8 voor bron 0 en 1 het\n' + \
                    'bronid van het chanid om het xmltvid te krijgen.',
                20: u'Gebruik UTC tijd voor de uitvoer',
                21: u'Maak een nieuw configuratie bestand aan en\n' + \
                    'hernoem een bestaand bestand naar *.old.',
                22: u'Plaats alle actieve zender in het nieuwe bestand\n' + \
                    'in een aparte groep boben aan de lijst.\n' + \
                    'Alleen relevant samen met de configure optie.',
                23: u'Naam van het configuratie bestand\n' + \
                    '<standaard = "%s">',
                24: u'Sla de op dit moment gedefinieerde opties op in het\n' + \
                    'configuratie bestand. Voeg opties toe aan de commando\n' + \
                    'regel om ze toe te voegen of te wijzigen.',
                25: u'Gebruik dit bestand voor de cache functie\n' + \
                    '<standaard = "%s">',
                26: u'Verwijder achterhaalde programmagegevens uit de cache',
                27: u'Verwijder alle programmagegevens uit de cache',
                28: u'Verwijder alle ttvdb gegevens uit de cache',
                29: u'Betand waarnaartoe de uitvoer te sturen.\n' + \
                    '<standaard naar het scherm>',
                30: u'Gebruik voor de uitvoer de Windows codeset (cp1252)\n' + \
                    'in plaats van utf-8',
                31: u'Onderdruk alle log uitvoer naar het scherm.',
                32: u'Zend de log uitvoer ook naar het scherm.',
                33: u'Haal geen detail pagina\'s van één van de bronnen op.\n',
                34: u'<standaard> Haal de beschikbare detail pagina\'s van de\n' + \
                    'bronnen op',
                35: u'De eerste dag waarvan programma gegevens op te halen\n' + \
                    '<standaard is 0 is vandaag>',
                36: u'Het aantal dagen waarvoor programmagegevens op te halen.\n' + \
                    '<max 14 = standaard>\n' + \
                    'Elke bron heeft zijn eigen maximum, dat lager kan zijn.\n',
                38: u'Het aantal dagen om "traag" (met details) gegevens op\n' + \
                    'te halen.\n' + \
                    'Standaard alle dagen',
                39: u'<standaard> Voeg url\'s van de zender iconen toe\n' + \
                    '(mythfilldatabase zal deze dan gebruiken)',
                40: u'Voeg geen url\'s van de zender iconen toe',
                41: u'Markeer de HD programma\'s,\n' + \
                    'gebruik dit niet als je alleen maar analoge SD opneemt',
                42: u'<standaard> Vertaal de genre\'s van de bronnen naar\n' + \
                    'MythTV-genre\'s. Zie het %s.set bestand\n' + \
                    'voor de vertaal tabellen',
                43: u'Vertaal de genre\'s van de bronnen niet naar\n' + \
                    'MythTV-genres.',
                44: u'Het maximaal toegelaten aantal karakters voor de\n' + \
                    'beschrijvingen.De rest wordt weggeknipt.',
                45: u'Wat te doen wanneer programma\'s niet goed aansluiten:\n' + \
                    '"avarage" Neem het gemiddelde van de eindtijd en de\n' + \
                    '          begintijd van het volgende programma.\n' + \
                    '          <standaard>\n' + \
                    '"stop"    Pas de begintijd van het volgende programma\n' + \
                    '          aan aan de eindtijd.\n' + \
                    '"start"   Pas de eindtijd aan aan de begintijd van het \n' + \
                    '          volgende programma.\n' + \
                    '"none"    Doe niets.\n',
                46: u'De maximale afwijking tussen eindtijd en begintijd van\n' + \
                    'het volgende programma dat gecorrigeerd mag worden.\n' + \
                    '<standaard 10 minuten>',
                47: u'Geef de taal voor de systeem en log berichten.\n' + \
                    'Op dit moment "en" (standaard) of "nl"',
                48: u'Gebruik alleen data uit de cache.'
                },
            u'confighelp':{
                0: u'# VERANDER DE ONDERSTAANDE WAARDE NIET!\n',
                1: u'# Zie: https://github.com/tvgrabbers/tvgrabnlpy/wiki/Over_de_configuratie\n',
                2: u'# Dit is een lijst met de standaard opties ingesteld met --configure (-C)\n',
                3: u'# Velen kun je op de commandregel met opties veranderen.\n',
                4: u'# Wees voorzichtig met handmatig bewerken. Ongeldige waarden worden\n',
                5: u'# stilzwijgend genegeerd. Voor boolean waarden kun je True/False, On/Off\n',
                6: u'# of 0/1 gebruiken. Geen waarde schakeld ze aan, een ongeldige waarde uit.\n',
                7: u'# Je kunt altijd je log bestand controleren voor de feitelijk gebruikte\n',
                8: u'# waarden. Alleen hier getoonde opties kun je hier instellen.\n',
                9: u'',
                10: u'',
                11: u'# Zet always_use_json op False om door het .json databestand voorgestelde\n',
                12: u'# waarden voor zendernaam, zendergroep en prime_source te negeren.\n',
                13: u'# Wanneer je hier zelf niets aan veranderd hebt, laat je hem het best\n',
                14: u'# op True staan om maximaal van alle updates te kunnen profiteren.\n',
                15: u'',
                16: u'',
                21: u'# De volgende zijn tunning parameters. Normaal gesproken behoef je hier niets\n',
                22: u'# aan te veranderen.\n',
                23: u'# global_timeout is de maximum tijd in secondes om op een pagina te wachten.\n',
                24: u'# max_simultaneous_fetches is het maximum aantal pagina\'s dat tegelijkertijd\n',
                25: u'#    opgehaald kan worden. Bij meer verzoeken worden deze in de wacht gezet.\n',
                26: u'#    Met het toenemend aantal bronnen is het mogelijk dat zij allemaal tegelijk\n',
                27: u'#    hun pagina op proberen te halen. Dit kan tot verstopping van je internet\n',
                28: u'#    verbinding leiden en dus tot mislukkingen.\n',
                29: u'#    Wanneer je regelmatig "incomplete read failures" of "get_page timed out"\n',
                30: u'#    fouten ziet kun je proberen de eerste op te hogen of de tweede te verlagen.\n',
                31: u'#    Dit zal de totale duur niet belangrijk beinvloeden, want dit wordt voornamelijk\n',
                32: u'#    bepaald door de bron met de meeste detail pagina\'s en de verplichte wachttijd\n',
                33: u'#    tussen de pagina\'s om de bronnen niet te overbelasten.\n',
                34: u'#    Maar mislukte basis pagina\'s worden opnieuw geprobeerd en een mislukte\n',
                35: u'#    detail pagina kan betekenen, dat deze van een andere bron geprobeerd wordt.\n',
                36: u'#    Dus veel mislukkingen, met name bij de detail pagina\'s kan de totale duur\n',
                37: u'#    verlengen.\n',
                38: u'',
                39: u'',
                41: u'# Dit bepaalt wat er naar het log en het scherm gaat.\n',
                42: u'# 0 Niets (gebruik quiet mode om alleen uitvoer naar het scherm uit te schakelen)\n',
                43: u'# 1 Geef Fouten en waarschuwingen\n',
                44: u'# 2 Geef Welke pagina\'s opgehaald worden\n',
                45: u'# 4 Statistieken van onder andere het samenvoegen van de bronnen\n',
                46: u'# 8 Zend alle detail en ttvdb verzoeken naar het scherm\n',
                47: u'# 16 Zend alle detail en ttvdb verzoeken naar het log bestand\n',
                48: u'# 32 Geef details van het samenvoegen van de bronnen (zie hieronder)\n',
                49: u'# 64 Toon alle titel hernoemingen\n',
                50: u'# 128 Toon alle TTVDB mislukkingen\n',
                51: u'# 256 DataTreeGrab Warnings\n',
                52: u'',
                61: u'# Welke samenvoeg resultaten gaan naar het log/scherm (heeft log_level 32 nodig)\n',
                62: u'# 0 = Log niets\n',
                63: u'# 1 = log niet gekoppelde programma\'s, die toegevoegd worden\n',
                64: u'# 2 = log overgebleven, niet toegevoegd programma\'s\n',
                65: u'# 4 = Log gekoppelde programma\'s\n',
                66: u'# 8 = Log groepslots\n',
                67: u'',
                71: u'# Zet "mail_log" op True om het log naar het onderstaande mail-adres te sturen.\n',
                72: u'# Stel ook je mailserver en poort juist in.\n',
                73: u'# SSL/startTLS wordt niet ondersteund, evenmin als een login om te verzenden.\n',
                74: u'# Test dit eerst vanaf de console, want het versturen gebeurt na het sluiten van\n',
                75: u'# het log en je ziet daarin dus geen fouten!\n',
                76: u'',
                77: u'',
                81: u'# Mogelijke waarden voor ratingstyle (kijkwijzerstijl) zijn:\n',
                82: u'#   long  : Voeg de lange beschrijving en de iconen toe\n',
                83: u'#   short : Voeg een enkel woord en de iconen toe\n',
                84: u'#   single: Voeg een enkele regel toe (mythtv gebruikt alleen het eerste item)\n',
                85: u'#   none  : Voeg niets toe\n',
                86: u'',
                87: u'',
                91: u'# Dit zijn de zender definities. Je kan een zender uitschakelen door aan het \n',
                92: u'# begin van de regel een "#" te plaatsen. Gescheiden door ";" zie je op elke\n',
                93: u'# regel: De naam, de groep, het chanID, de ID\'s voor de verschillende bronnen\n',
                94: u'# in de volgorde zoals door de "--show-sources" optie weergegeven (waarbij bron 0\n',
                95: u'# niet bestaat, tvgids.nl is van 0 naar 3 verhuisd!!) en de logo bron en naam.\n',
                96: u'# Je kunt de naam naar behoefte aanpassen.\n',
                97: u'# Een ontbrekend ID betekent dat die bron deze zender niet levert.\n',
                98: u'# Het verwijderen van een ID schakelt de zender voor die bron uit, maar zorg dat\n',
                99: u'# de ";"s blijven staan! Je kunt echter beter de "disable_source" optie gebruiken.\n',
                100: u'# Zet de logo bron op 99 om zelf een volledige URL naar een logo te leveren.\n',
                101: u'#\n',
                102: u'# Om per zender opties in te stellen, kun je onderaan een sectie zoals: \n',
                103: u'# [Channel <channelID>] toevoegen, waarbij <channelID> het derde item is.\n',
                104: u'# Zie de WIKI op https://github.com/tvgrabbers/tvgrabnlpy/wiki voor verdere\n',
                105: u'# beschrijvingen. Je kunt de volgende opties instellen:\n',
                106: u'# Boolean waarden (True, 1, on of geen waarde betekent True. De rest False):\n',
                107: u'#   fast, compat, legacy_xmltvids, logos, cattrans, mark_hd, add_hd_id,\n',
                108: u'#   disable_ttvdb, use_split_episodes\n',
                109: u'#   legacy_xmltvids: is only valid for the Dutch/Flemish grabber\n',
                110: u'#   add_hd_id: Wanneer deze op True gezet wordt, worden er twee programma\n',
                111: u'#     lijsten voor de zender gemaakt één gewone en één met "-hd" achter het\n',
                112: u'#     xmltv ID. en met HD markering. "mark_hd" wordt dan voor deze zender genegeerd.\n',
                113: u'# Integer waarden:\n',
                114: u'#   slowdays, max_overlap, desc_length, prime_source, prefered_description\n',
                115: u'#   disable_source, disable_detail_source\n',
                116: u'#   prime_source is de bron waarvan de tijden en titel dominant zijn.\n',
                117: u'#     Standaard is dit voor RTL zenders 2, voor NPO zenders 4, voor nederlandse\n',
                118: u'#     regionale zenders 5, voor groep 2 en 9 (Vlaams) 6. Verder de eerst\n',
                119: u'#     beschikbare bron in de volgorde (2, 4, 10, 12, 7, 3, 5, 1, 9, 6, 8, 11)\n',
                120: u'#   prefered_description (1-12) is de bron die, wanneer beschikbaar de \n',
                121: u'#     omschrijving levert. Standaard is dit de langst beschikbare.\n',
                122: u'#   Met disable_source en disable_detail_source kun je een bron voor deze\n',
                123: u'#     zender uitschakelen. Voor alles of alleen voor de detail pagina\'s\n',
                124: u'#     Een niet beschikbare bron uitschakelen heeft geen effect.\n',
                125: u'#     Met de commando regel opties: "--show-sources" en "--show-detail-sources"\n',
                126: u'#     kun je een lijst tonen van de beschikbare bronnen en hun ID\n',
                127: u'# String waarden:\n',
                128: u'#   overlap_strategy (met als mogelijke waarden): \n',
                129: u'#     average, stop, start; iets anders levert de waarde none\n',
                130: u'#   xmltvid_alias: Standaard wordt het chanid gebruikt als xmltvID.\n',
                131: u'#     Hiermee kun je een andere tekst waarde instellen. Wees voorzichtig niet een\n',
                132: u'#     al bestaande waarde te kiezen. Het kan door "--configure"ingesteld worden\n',
                133: u'#     om chanid veranderingen te ondervangen. Zie verder de WIKI\n',
                134: u'\n',
                135: u'',
                136: u'',
                137: u'',
                138: u'',
                139: u'',
                140: u'',
                141: u'# Dit is een lijst van titels met een ":" die niet in een titel en\n',
                142: u'# een afleverings titel gesplitst moeten worden. Dit zijn met name\n',
                143: u'# spin-off series zoals: "NCIS: Los Angeles". Films en programma\'s\n',
                144: u'# die al een afleverings titel hebben, zijn al uitgesloten.\n',
                145: u'',
                146: u'# Dit is een lijst van groepstitels voor de ":", die verwijderd moeten\n',
                147: u'# worden. Bijvoorbeeld: "KRO detectives".\n',
                148: u'',
                149: u'',
                150: u'# Dit is een lijst van titels die hernoemd moeten worden.\n',
                151: u'# Bijvoorbeeld "navy NCIS" naar "NCIS". Dit onder anderen om\n',
                152: u'# verschillende titels bij verschillende bronnen op te vangen.\n',
                153: u'',
                154: u'# Dit is een lijst van genres waarvoor detail pagina\'s opgehaald moeten\n',
                155: u'# worden. Voor programma\'s zonder deze genres worden geen detailpagina\'s\n',
                156: u'# opgehaald. Gebruik de genres van voor de toepassing van cattrans.\n',
                157: u'# Voeg "all" toe om, wanneer beschikbaar altijd details op te halen.\n',
                158: u'# Voeg "none" toe om voor programma\'s zonder genre details op te halen.\n',
                159: u'',
                160: u'# Dit zijn de vertaallijsten voor:\n',
                161: u'# naar een gemeenschappelijk genre:subgenre. Wanneer cattrans is ingeschakeld\n',
                162: u'# dan worden deze vervolgens volgens de lijst verder naar beneden omgezet.\n',
                163: u'',
                164: u'# De genres van:\n',
                165: u'# %s worden als subgenres gezien.\n',
                166: u'# Dit zijn lijsten van genres om hieraan toe te voegen. Nieuwe "subgenres"\n',
                167: u'# worden automatisch gekoppeld en toegevoegd op basis van algemene regels.\n',
                168: u'',
                169: u'# Dit is de "Genre:Subgenre" conversie tabel die door cattrans wordt gebruikt.\n',
                170: u'# "Genre:Subgenre" wordt automatisch naar kleine letters omgezet\n',
                171: u'# en begin en eind spaties worden verwijderd.\n',
                172: u'# De lijst wordt gesorteerd met de genres zonder subgenre aan het begin.\n',
                173: u'# Nieuwe waarden worden continu toegevoegd\n',
                174: u'',
                175: u'',
                176: u'# achter het "=" teken geef je de te gebruiken categorie\n',
                177: u'# Als een categorie leeg is dan wordt de hoofd categorie of een bestaande\n',
                178: u'# standaard gebruikt\n',
                179: u'# Als een hoofd categorie leeg is, dan wordt een standaard waarde aangeleverd.\n',
                180: u'# en gebruikt. Wanneer er geen standaard bekent is, dan wordt "Unknown"\n',
                181: u'# gebruikt. Het is verstandig om regelmatig op nieuwe hoofd categorieën\n',
                182: u'# te controleren, zodat deze niet naar "Unknown" vertaald worden.\n',
                183: u'',
                184: u''
                },
            u'mergeinfo':{
                1: u'%s is samengevoegd met %s\n',
                2: u'Omdat ze allebij actief zijn, hebben we geen Alias ingesteld.\n',
                3: u'Wanneer je het oude chanid %s als xmltvid\n',
                4: u'wilt gebruiken, moet je:\n',
                5: u'toevoegen aan de zender configuratie voor %s\n',
                6: u'Omdat het oude chanid actief was, hebben we een Alias ingesteld\n',
                7: u'voor de zender configuratie van %s\n',
                8: u'Omdat %s al een xmltvid_alias heeft\n',
                9: u'hebben we dit niet aangepast.\n',
                10: u'Wanneer je het oude chanid %s als xmltvid\n',
                11: u'wilt gebruiken moet je:\n',
                12: u'veranderen in:',
                13: u'in de zender configuratie van %s\n',
                14: u'We konden niet controleren op zelf aangepaste opties voor het oude chanid: %s\n',
                15: u'Dus controleer de nieuwe instellingen van het nieuwe chanid: %s\n'
                },
            u'stats':{
                72: u'Uitvoering gereed.\n',
                73: u'Verzamel statistieken van %s programma\'s voor %s zenders:\n',
                74: u'  Start tijd: %s\n',
                75: u'   Eind tijd: %s\n',
                76: u'        Duur: %s\n',
                77: u'%6.0f pagina(\'s) opgehaald, waarvan %s faalden\n',
                78: u'%6.0f cache vonst(en)\n',
                79: u'%6.0f succesvolle ttvdb.com verwijzingen\n',
                80: u'%6.0f   misluktte ttvdb.com verwijzingen\n',
                81: u' Tijd/pagina: %s seconds\n',
                82: u'%6.0f pagina(\'s) opgehaald van theTVDB.com\n',
                83: u'%6.0f mislukking(en) op theTVDB.com\n',
                84: u'%6.0f  basis pagina(\'s) opgehaald van%s\n',
                85: u'%6.0f detail pagina(\'s) opgehaald van %s\n',
                86: u'%6.0f mislukking(en) op %s\n'
                },
            u'other':{
                0: u'Verzamel API die meerdere bronnen samenvoegt.',
                1: u'De beschikbare bronnen zijn:',
                2: u'De beschikbare detail bronnen zijn:',
                3: u'De beschikbare logo bronnen zijn:',
                4: u' 99: Je eigen volledige logo url',
                5: u'De begintijd van deze verzamelronde is %s\n',
                6: u'Versie',
                7: u'Taal',
                8: u'Er is een nieuwere stabiele API release bescikbaar op github!\n',
                9: u'Ga naar: %s\n',
                10: u'Er is een nieuwere stabiele frontend release beschikbaar!\n',
                11: u'Het zender/bron data bestand is nieuwer!\n',
                12: u'Draai met "--configure" om dit te implementeren\n'
                }},
        u'IO':{
            u'error':{
                1: u'Het bestand: "%s" is niet gevonden of kon niet worden geopend.\n',
                2: u'%s is niet met %s gecodeerd.\n',
                3: u'%s heeft een ongeldige codering %s.\n',
                10: u'Wanneer je hulp wilt, voeg dan ajb je configuratie en log bestanden bij!\n',
                11: u'Een onverwachte fout is opgetreden in de %s thread:\n',
                12: u'Een onverwachte fout is opgetreden:\n',
                13: u'Een onbekend log-bericht: %s van type %s\n',
                14: u'bij het verzamelen van de basis-pagina\'s\n',
                15: u'De huidige detail url is: %s\n',
                16: u'bij het ophalen van de detail pagina\'s\n',
                20: u'Er is geen cache bestand opgegeven. De cache functionaliteit wordt uitgeschakeld!\n',
                21: u'De cache folder is niet toegankelijk. De cache functionaliteit wordt uitgeschakeld!\n',
                22: u'Een fout bij het laden van de database: %s.db (mogelijke corruptie)\n',
                23: u'We proberen de backup te laden',
                24: u'Het laden van de database: %s.db is mislukt\n',
                25: u'De cache functionaliteit wordt uitgeschakeld',
                26: u'Database Fout\n'
                },
            u'other':{
                1: u'De Database controleren.\n'}},
        u'fetch':{
            u'error':{
                1: u'get_page duurt te lang (>%s s): %s\n',
                2: u'Een onverwachte fout "%s:%s" is opgetreden bij het ophalen van: %s\n',
                3: u'Kan de url %s niet openen.\n',
                4: u'Kan de pagina niet lezen. %s: code=%s\n',
                11: u'Fout bij het verwerken van de %s-functie %s voor bron %s\n',
                12: u'De geleverde data was: %s\n',
                21: u'Zender %s lijkt op %s verloren detail verzoeken van %s te wachten.\n',
                22: u'We annuleren en stellen het als klaar\n',
                23: u'Fout bij het verwerken van de detail-pagina: %s\n',
                24: u'Fout bij het verwerken van de detail2-pagina: %s\n',
                25: u'Fout bij het ophalen van de URL voor bron: %s uit de json data_def\n',
                26: u'Fout bij het lezen van de %s-pagina: %s\n',
                27: u'De juiste datum van de: %s pagina kan niet worden vastgesteld.\n',
                28: u'Sla zender %s op %s!, dag=%d over. Verkeerde datum!\n',
                29: u'Een onverwachte fout bij het ophalen van de %s-pagina van: %s\n',
                30: u'Het is onmogelijk om zender informatie van %s te verkrijgen\n',
                31: u'Een fatale fout bij het verwerken van de basis-pagina\'s van %s\n',
                32: u'We stellen dat ze allemaal binnen zijn en laten de andere bronnen de taak voltooien.\n',
                33: u'Kan de programma titel van "%s" op zender: %s, van bron: %s niet bepalen.\n',
                34: u'Kan de programma tijd van "%s" op zender: %s, van bron: %s niet bepalen.\n',
                35: u'De pagina %s leverde geen data op\n',
                36: u'Verwijder "%s" van "%s"\n',
                37: u'De titel "%s" wordt gesplitst\n',
                38: u'Hernoem "%s" naar "%s"\n',
                51: u'Geen data van %s voor zender: %s\n',
                52: u'De detail bron: %s is gestopt.\n',
                53: u'Dus we stoppen met wachten voor de onderhanden detailverzoeken voor %s\n',
                },
            u'report':{
                1: u'Nu wordt %s(xmltvid=%s%s) van %s opgehaald\n',
                2: u'Nu word(t/en) %s zender(s) van %s opgehaald\n',
                3: u'Nu wordt de %s zendergroep van %s opgehaald\n',
                4: u'    (zender %s van %s) voor dag %s van %s.\n',
                5: u'    (zender %s van %s) voor %s dagen.\n',
                6: u'    (zender %s van %s) voor periode %s van %s).\n',
                7: u'    (zender %s van %s) voor %s dagen, pagina %s.\n',
                8: u'    voor dag %s van %s.\n',
                9: u'    voor %s dagen.\n',
                10: u'    voor periode %s van %s.',
                11: u'    voor %s dagen, pagina %s.\n',
                12: u'\nDag %s voor %s van %s wordt uit de cache gehaald.\n',
                15: u'Sla zender %s op %s, dag=%d over. Geen data\n',
                16: u'Sla zender %s op %s over!. Geen data',
                17: u'Sla zender %s op %s over!, periode=%d. Geen data\n',
                18: u'Sla zender %s op %s over!, pagina=%d. Geen data\n',
                19: u'Sla dag %d op %s over. Geen data\n',
                20: u'Sla %s over. Geen data\n',
                21: u'Sla periode %d op %s over. Geen data\n',
                22: u'Sla pagina %d op %s over. Geen data\n',
                23: u'Sla zendergroep %s op %s over!, dag=%d. Geen data\n',
                24: u'Sla zendergroep %s op %s over!. Geen data',
                25: u'Sla zendergroep %s op %s over!, periode=%d. Geen data\n',
                26: u'Sla zendergroep %s op %s over!, pagina=%d. Geen data\n',
                31: u'[ophalen mislukt] %s:(%3.0f%%) %s\n',
                32: u'[%s verzoek] %s:(%3.0f%%) %s\n',
                33: u'      [cached] %s:(%3.0f%%) %s\n',
                34: u'[geen verzoek] %s:(%3.0f%%) %s\n',
                41: u'Nu wordt de cache gecontrolleerd op %s programmadetails voor %s(xmltvid=%s%s)\n',
                42: u'Nu worden de details voor %s programma\'s op %s(xmltvid=%s%s) opgehaald\n',
                43: u'    (zender %s van %s) voor %s dagen.\n',
                },
            u'stats':{
                1: u'Detail statistieken voor %s (zender %s van %s)\n',
                2: u'%6.0f cache vonst(en)\n',
                3: u'%6.0f zonder details in de cache\n',
                4: u'%6.0f succesvolle ttvdb.com verwijzingen\n',
                5: u'%6.0f   misluktte ttvdb.com verwijzingen\n',
                6: u'%6.0f detail pagina(\'s) opgehaald van %s.\n',
                7: u'%6.0f mislukking(en)\n',
                8: u'%6.0f zonder detail info\n',
                9: u'%6.0f resterend in de %s queue om te verwerken\n',
                10: u'%6.0f uitgesloten door het genre filter\n'
                },
            u'other':{
                1: u'  %s.json wordt gedownload ...\n',
                u'': u''}},
        u'merge':{
            u'error':{
                },
            u'stats':{
                1: u'Nu worden %s programma\'s van %s aan %s toegevoegd\n',
                2: u'Nu worden %s programma\'s van %s met %s programma\'s van %s samengevoegd\n',
                3: u'    (zender %s van %s)\n',
                5: u'Toevoeg',
                6: u'Samenvoeg',
                7: u'  bron',
                8: u'zender',
                9: u'%s statistieken voor %s (zender %s van %s)\n        van %s %s\n',
                10: u'%7.0f programma\'s op  %s voor: %s - %s\n    (%2.0f groepslots),\n',
                11: u'%7.0f programma\'s van %s voor: %s - %s\n    (%2.0f groepslots)\n',
                12: u'%7.0f programma\'s gekoppeld op tijd en naam\n',
                13: u'%7.0f programma\'s nieuw toegevoegd\n',
                14: u'%7.0f programma\'s toegevoegd aan een groepslots\n',
                15: u'%7.0f programma\'s generiek gekoppeld op naam om een genre te verkrijgen\n',
                16: u'%7.0f programma\'s ongekoppeld overgebleven in %s\n',
                17: u'Nu %4.0f programma\'s waarvan %2.0f groepslots\n',
                18: u'en %4.0f titels zonder geassocieerd genre.\n',
                19: u'Detail',
                31: u'Toegevoegd van  %s:%s: %s Genre: %s.\n',
                32: u'Overgebleven in %s:%s: %s Genre: %s.\n',
                33: u'Gekoppeld van   %s:%s: %s Genre: %s.\n',
                34: u'            van %s:%s: %s Genre: %s.\n',
                35: u'Ongekoppeld:                   %s: %s Genre: %s.\n',
                36: u'          op tijd en titel met:%s: %s Genre: %s.\n',
                37: u'Toegevoegd aan groepslot:      %s: %s Genre: %s.\n',
                38: u'',
                39: u'',
                }},
        u'ttvdb':{
            u'error':{
                1: u'Sorry, thetvdb.com is uitgeschakeld!\n',
                2: u'Svp geef een serie titel!\n',
                3: u'Ongeldige taalcode: "%s" gegeven. "en" wordt gebruikt\n',
                11: u'Fout bij het ophalen van een ID van theTVdb.com\n',
                12: u'Fout bij het ophalen van de afleveringen van theTVDB.com\n',
                13: u'  Geen ttvdb id voor "%s" op zender %s\n',
                14: u'ttvdb verwijzing voor "%s: %s"\n',
                15: u'ttvdb mislukking voor "%s: %s" op zender %s\n',
                },
            u'frontend':{
                0: u'',
                1: u'De serie "%s" is al opgeslagen met ttvdbID: %s -> %s',
                2: u'    voor de talen: (%s)\n',
                3: u'De serie "%s" is nog niet bekend!\n',
                4: u'Er is geen verwijzing voor %s gevonden op theTVDB.com',
                5: u'theTVDB Zoek resultaten:',
                6: u'Geef een keuze (eerste nummer, q om te annuleren):',
                7: u'Verwijder het oude record',
                8: u'"%s" met de aliassen "%s" en "%s" wordt onder ttvdbID: %s aan de database toegevoegd!',
                9: u'"%s" met alias "%s" wordt onder ttvdbID: %s aan de database toegevoegd!',
                10: u'"%s" wordt onder ttvdbID: %s aan de database toegevoegd!',
                }}}
    return texts

def create_pickle(texts):
    fle_name = u'%s/%s.%s' % (os.path.abspath(os.curdir), name, lang)

    if os.path.isfile(fle_name):
        print(u'The language file %s already exists.\nDo you want to overwrite it [Y|N]?' % fle_name)
        while True:
            x = sys.stdin.read(1)
            if x in ('n', 'N'):
                print(u'Exiting')
                sys.exit(0)

            elif x in ('Y', 'y'):
                break

        os.remove(fle_name)

    print(u'Writing %s language file' % language)
    fle = open(fle_name, 'w')
    text_dict = {}
    text_dict['lang'] = lang
    text_dict['language'] = language
    text_dict['version'] = version
    text_dict['texts'] = texts
    pickle.dump(text_dict, fle)

def main():
    texts = load_texts()
    create_pickle(texts)

# allow this to be a module
if __name__ == '__main__':
    sys.exit(main())
