#!/bin/bash

# Can be slow (the default) or fast
declare Speed=${1:-"slow"}

# Can be full (the default) or a number
# if Speed is slow, full = 14
# if Speed is fast, full = 4
declare Days=${2:-"full"}

# Can be default, all or selected
# if Speed is slow, default = all
# if Speed is fast, default = selected
declare Group=${3:-"default"}

# Optional offset defaults to 0
declare Offset=${4:-"0"}

# The MythTV sourceID's to fill.
# If you have only 1 source, set SourceID2=""
declare SourceID1=8
declare SourceID2=''

# The location for the output, config and log files
declare xml_path="/tmp/"
declare Conf_path="${HOME}/.xmltv/"
# Delete the output end config after use. Set to 0 to keep them
declare -i clean_xml=0
declare -i clean_Conf=0

declare Conf_file
declare xml_file
declare -i Chan_Cnt

# The actual grab and mythfilldatabase command
# If the selection contains no channels ($Chan_Cnt -eq 0) it does nothing
# Therefor you set the value to add in every add section below to 1 or 0 e.g.:
#	Chan_Cnt=$Chan_Cnt+1
#	Chan_Cnt=$Chan_Cnt+0
# It keeps running mythfilldatabase until it runs out of parameters
function Grab_And_Fill {
	if [ $Chan_Cnt -gt 0 -a "$1" != "" ]; then
		/usr/bin/tv_grab_nl_py --config-file ${Conf_file} --output ${xml_file}

		if [ $? == 0 ]; then

			while [ "$1" != "" ]; do
				/usr/bin/mythfilldatabase --syslog local5 --file --xmlfile ${xml_file} --sourceid $1
				shift
			done

		fi

		[ $clean_xml -gt 0 ] && rm -f ${xml_file}
	fi

	[ $clean_Conf -gt 0 ] && rm -f ${Conf_file}
}

# This contains the Configuration Settings
function Add_Header {
	echo "# encoding: utf-8" > $Conf_file
	echo "# configversion: 2.2" >> $Conf_file
	echo "" >> $Conf_file
	echo "[Configuration]" >> $Conf_file
	echo "log_level = 133" >> $Conf_file
	echo "quiet = False" >> $Conf_file
	echo "desc_length = 1000" >> $Conf_file
	echo "kijkwijzerstijl = single" >> $Conf_file
	echo "use_split_episodes = True" >> $Conf_file
	echo "disable_source = 3" >> $Conf_file

	if [ "$Speed" == "slow" ]; then
		echo "fast = False" >> $Conf_file
		echo "offset = $Offset" >> $Conf_file
		echo "days = $Days" >> $Conf_file
	elif [ "$Speed" == "fast" ]; then
		echo "fast = True" >> $Conf_file
		echo "offset = $Offset" >> $Conf_file
		echo "days = $Days" >> $Conf_file
	elif [ "$Speed" == "alt" ]; then
		echo "fast = False" >> $Conf_file
		echo "offset = 0" >> $Conf_file
		echo "days = 1" >> $Conf_file
	fi

	echo "" >> $Conf_file
	echo "[Channels]" >> $Conf_file
}

# These are the common Channels you want to grab always
function Add_Base_Channels {
	if [ "$1" == "" ]; then 
		Chan_Cnt=$Chan_Cnt+1
		echo "Nederland 1;1;0-1;1;nederland-1;;;1;24443942983;37;4;npo1.png" >> $Conf_file
		echo "Nederland 2;1;0-2;2;nederland-2;;;2;24443942987;35;4;npo2.png" >> $Conf_file
		echo "Nederland 3;1;0-3;3;nederland-3;;;3;24443943037;33;4;npo3.png" >> $Conf_file
		echo "RTL 4;1;0-4;4;rtl-4;RTL4;;;24443943096;141;4;rtl4_1.png" >> $Conf_file
		echo "RTL 5;1;0-31;31;rtl-5;RTL5;;;24443943146;143;4;rtl_5_1.png" >> $Conf_file
		echo "RTL 7;1;0-46;46;rtl-7;RTL7;;;24443943014;;4;rtl7.png" >> $Conf_file
		echo "RTL 8;1;0-92;92;rtl-8;RTL8;;;24443943182;;4;rtl_8_1.png" >> $Conf_file
		echo "SBS 6;1;0-36;36;sbs-6;;;;24443943184;145;4;sbs6_1.png" >> $Conf_file
		echo "NET 5;1;0-37;37;net-5;;;;24443943091;127;4;net5.png" >> $Conf_file
		echo "Veronica;1;0-34;34;veronica;;;;24443943190;;4;veronica_disney_xd.png" >> $Conf_file
		echo "Eén;2;0-5;5;een;;;;24443943058;7;6;img_145/1455480.jpg" >> $Conf_file
		echo "Canvas;2;0-6;6;ketnet-canvas;;;;555680807173;41;6;img_144/1448404.jpg" >> $Conf_file
		echo "BBC 1;3;0-7;7;bbc-1;;;;24443942999;275;2;18285/bbc-1-nl.jpg" >> $Conf_file
		echo "BBC 2;3;0-8;8;bbc-2;;;;560453158983;277;2;18287/bbc-2-nl.jpg" >> $Conf_file
	else
		echo "" >> $Conf_file
		# Nederland 1
		echo "[Channel 0-1]" >> $Conf_file
		echo "prime_source = 4" >> $Conf_file
		echo "append_tvgidstv = False" >> $Conf_file
		echo "prefered_description = 5" >> $Conf_file
		echo "add_hd_id = True" >> $Conf_file
		echo "" >> $Conf_file
		# Nederland 2
		echo "[Channel 0-2]" >> $Conf_file
		echo "prime_source = 4" >> $Conf_file
		echo "append_tvgidstv = False" >> $Conf_file
		echo "prefered_description = 5" >> $Conf_file
		echo "add_hd_id = True" >> $Conf_file
		echo "" >> $Conf_file
		# Nederland 3
		echo "[Channel 0-3]" >> $Conf_file
		echo "prime_source = 4" >> $Conf_file
		echo "append_tvgidstv = False" >> $Conf_file
		echo "prefered_description = 5" >> $Conf_file
		echo "add_hd_id = True" >> $Conf_file
		echo "" >> $Conf_file
		# Eén
		echo "[Channel 0-5]" >> $Conf_file
		echo "prime_source = 3" >> $Conf_file
		echo "prefered_description = 3" >> $Conf_file
		echo "" >> $Conf_file
		# Canvas
		echo "[Channel 0-6]" >> $Conf_file
		echo "prime_source = 3" >> $Conf_file
		echo "prefered_description = 3" >> $Conf_file
		echo "" >> $Conf_file
		# BBC 1
		#~ echo "[Channel 0-7]" >> $Conf_file
		#~ echo "disable_source = 1" >> $Conf_file
		#~ echo "" >> $Conf_file
		#BBC 2
		#~ echo "[Channel 0-8]" >> $Conf_file
		#~ echo "disable_source = 1" >> $Conf_file
		#~ echo "" >> $Conf_file
		# RTL 4
		echo "[Channel 0-4]" >> $Conf_file
		echo "prime_source = 2" >> $Conf_file
		echo "prefered_description = 2" >> $Conf_file
		echo "" >> $Conf_file
		# RTL 5
		echo "[Channel 0-31]" >> $Conf_file
		echo "prime_source = 2" >> $Conf_file
		echo "prefered_description = 2" >> $Conf_file
		echo "" >> $Conf_file
		# RTL 7
		echo "[Channel 0-46]" >> $Conf_file
		echo "prime_source = 2" >> $Conf_file
		echo "prefered_description = 2" >> $Conf_file
		echo "" >> $Conf_file
		# RTL 8
		echo "[Channel 0-92]" >> $Conf_file
		echo "prime_source = 2" >> $Conf_file
		echo "prefered_description = 2" >> $Conf_file
		echo "" >> $Conf_file
		# SBS 6
		echo "[Channel 0-36]" >> $Conf_file
		echo "append_tvgidstv = False" >> $Conf_file
		echo "prefered_description = 5" >> $Conf_file
		echo "" >> $Conf_file
		# NET 5
		echo "[Channel 0-37]" >> $Conf_file
		echo "append_tvgidstv = False" >> $Conf_file
		echo "prefered_description = 5" >> $Conf_file
		echo "" >> $Conf_file
		# Veronica
		echo "[Channel 0-34]" >> $Conf_file
		echo "append_tvgidstv = False" >> $Conf_file
		echo "prefered_description = 5" >> $Conf_file
		echo "" >> $Conf_file
	fi
}

# These are the Source1  Channels you want to grab always
function Add_BaseSource1_Channels {
	if [ "$1" == "" ]; then 
		Chan_Cnt=$Chan_Cnt+0
	else
		echo "" >> $Conf_file
	fi
}

# These are the Source2  Channels you want to grab always
function Add_BaseSource2_Channels {
	if [ "$1" == "" ]; then 
		Chan_Cnt=$Chan_Cnt+0
		echo "" >> $Conf_file
	else
		echo "" >> $Conf_file
	fi
}

# These are the rest of the common Channels
function Add_Common_Channels {
	if [ "$1" == "" ]; then 
		Chan_Cnt=$Chan_Cnt+1
		echo "CNN;3;0-26;26;cnn;;;;561138215261;15;4;cnn.png" >> $Conf_file
		echo "ARD;4;0-9;9;ard;;;;429332519216;109;4;ard.png" >> $Conf_file
		echo "RTV Utrecht;6;0-100;100;rtv-utrecht;;;19;24443943078;;4;rtvutrecht.png" >> $Conf_file
		echo "Comedy Central;7;0-91;91;comedy-central;;;;24443943012;;5;20/701/comedy_central_hd_65x104_53591108368.png" >> $Conf_file
		echo "Discovery Channel;7;0-29;29;discovery-channel;;;;24443943009;;5;17/259/discovery_hd_160x35_20784068.png" >> $Conf_file
		echo "Eurosport;7;0-19;19;eurosport;;;;24443943029;267;6;img_416/41655.jpg" >> $Conf_file
		echo "National Geographic;7;0-18;18;national-geographic;;;;24443943035;129;6;img_390/39067.jpg" >> $Conf_file
		echo "Nickelodeon;7;0-89;89;nickelodeon;;;;542836775318;281;6;img_416/41651.jpg" >> $Conf_file
		echo "MTV;7;0-25;25;mtv;;;;24443943006;378;6;img_391/39133.jpg" >> $Conf_file
		echo "TLC;7;0-438;438;tlc;;;;562458663437;389;6;img_132/1323415.jpg" >> $Conf_file
	else
		## ARD
		echo "[Channel 0-9]" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		## National Geographic
		echo "" >> $Conf_file
		echo "[Channel 0-18]" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		## Eurosport
		echo "[Channel 0-19]" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		## MTV
		echo "[Channel 0-25]" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		## CNN
		echo "[Channel 0-26]" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		# Discovery Channel
		#~ echo "[Channel 0-29]" >> $Conf_file
		#~ echo "disable_source = 1" >> $Conf_file
		#~ echo "" >> $Conf_file
		## Nickelodeon
		echo "[Channel 0-89]" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		## Comedy Central
		echo "[Channel 0-91]" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		echo "[Channel 0-100]" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		#	echo "fast = True" >> $Conf_file
		echo "" >> $Conf_file
	fi
}

# These are the rest of the Source2 Channels
function Add_Source2_Channels {
	if [ "$1" == "" ]; then 
		Chan_Cnt=$Chan_Cnt+0
		echo "" >> $Conf_file
	else
		echo "" >> $Conf_file
	fi
}

# These are the rest of the Source1 Channels
function Add_Source1_Channels {
	if [ "$1" == "" ]; then 
		Chan_Cnt=$Chan_Cnt+1
		echo "BBC World;3;0-86;86;bbc-world;;;;24443943049;17;4;bbc_world_news.png" >> $Conf_file
		echo "ZDF;4;0-10;10;zdf;;;;429332519214;19;4;zdf.png" >> $Conf_file
		echo "Brava NL;7;0-428;428;bravatv;;;;24443943156;;4;bravanl.png" >> $Conf_file
		echo "Disney Channel;7;0-424;424;disney-channel;;;;24443942993;179;4;disney_channel_2.png" >> $Conf_file
		echo "Ketnet;8;1-ketnet-canvas-2;;ketnet-canvas-2;;;;24443943087;39;2;39223/ketnet-nl.jpg" >> $Conf_file
		echo "AT 5;6;0-40;40;at-5;;;;24443943004;;4;at5.png" >> $Conf_file
		echo "RTV West;6;0-101;101;rtv-west;;;21;24443943071;;4;tv_west.png" >> $Conf_file
		echo "RTV Rijnmond;6;0-102;102;rtv-rijnmond;;;22;24443943075;;4;tv_rijnmond.png" >> $Conf_file
		echo "RTV Noord-Holland;6;0-103;103;rtv-noord-holland;;;20;24443943063;;4;rtv_nh.png" >> $Conf_file
		echo "RTV Noord;6;0-108;108;rtv-noord;;;13;24443943192;;4;rtv_noord.png" >> $Conf_file
		echo "Omrop Fryslân;6;0-109;109;omrop-fryslan;;;12;24443943144;;4;omroep_friesland.png" >> $Conf_file
		echo "RTV Drenthe;6;0-110;110;rtv-drenthe;;;14;24443943187;;4;rtv_drenthe.png" >> $Conf_file
		echo "RTV Oost;6;0-111;111;rtv-oost;;;15;24443943043;;4;rtv_oost.png" >> $Conf_file
		echo "Omroep Gelderland;6;0-112;112;omroep-gelderland;;;16;24443943141;;4;omroep_gelderland.png" >> $Conf_file
		echo "Omroep Flevoland;6;0-113;113;omroep-flevoland;;;17;24443943001;;4;omroep_flevoland.png" >> $Conf_file
		echo "Omroep Brabant;6;0-114;114;omroep-brabant;;;18;24443943069;;4;omroep_brabant.png" >> $Conf_file
		echo "L1 TV;6;0-115;115;l1-tv;;;23;24443943061;;4;omroep_limburg.png" >> $Conf_file
		echo "Omroep Zeeland;6;0-116;116;omroep-zeeland;;;24;24443943178;;4;omroep_zeeland.png" >> $Conf_file
		echo "RTL Z;1;0-465;465;rtl-z;RTLZ;;;660696615380;;5;848/351/rtl_z_160x53_578573380256.png" >> $Conf_file
		echo "Zender van de Maand;10;5-24443943085;;;;;;24443943085;;5;20/701/ziggo_zender_vd_maand_1_160x104_575014468008.png" >> $Conf_file
	else
		## ZDF
		echo "[Channel 0-10]" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		## BBC world
		echo "[Channel 0-86]" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		## Disney Channel
		echo "[Channel 0-424]" >> $Conf_file
		echo "disable_ttvdb = True" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		## Brava
		echo "[Channel 0-428]" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		echo "[Channel 1-ketnet-canvas-2]" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		# Local Channels
		echo "[Channel 0-40]" >> $Conf_file
	#	echo "fast = True" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		echo "[Channel 0-101]" >> $Conf_file
	#	echo "fast = True" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		echo "[Channel 0-102]" >> $Conf_file
	#	echo "fast = True" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		echo "[Channel 0-103]" >> $Conf_file
	#	echo "fast = True" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		echo "[Channel 0-108]" >> $Conf_file
	#	echo "fast = True" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		echo "[Channel 0-109]" >> $Conf_file
	#	echo "fast = True" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		echo "[Channel 0-110]" >> $Conf_file
	#	echo "fast = True" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		echo "[Channel 0-111]" >> $Conf_file
	#	echo "fast = True" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		echo "[Channel 0-112]" >> $Conf_file
	#	echo "fast = True" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		echo "[Channel 0-113]" >> $Conf_file
	#	echo "fast = True" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		echo "[Channel 0-114]" >> $Conf_file
	#	echo "fast = True" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		echo "[Channel 0-115]" >> $Conf_file
	#	echo "fast = True" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
		echo "[Channel 0-116]" >> $Conf_file
	#	echo "fast = True" >> $Conf_file
		echo "disable_source = 1" >> $Conf_file
		echo "" >> $Conf_file
	fi
}

# Set defaults depending on slow or fast mode
if [ "$Speed" == "slow" ]; then
	if [ "$Days" == "full" ]; then
		Days=14
	fi

	if [ "$Group" == "default" ]; then
		Group="all"
	fi

elif [ "$Speed" == "fast" ]; then
	if [ "$Days" == "full" ]; then
		Days=4
	fi

	if [ "$Group" == "default" ]; then
		Group="selected"
	fi

else
	exit
fi

# The actual commands
rm ${Conf_path}raw_output.${Speed}
if [ "$Group" == "all" ]; then
	Conf_file="${Conf_path}all_s2_${Speed}.conf"
	xml_file="${xml_path}all_s2_output.xml"
	Chan_Cnt=0
	Add_Header
	Add_BaseSource2_Channels
	Add_Source2_Channels
	Add_BaseSource2_Channels 1
	Add_Source2_Channels 1
	Grab_And_Fill $SourceID2
	cat ${Conf_path}raw_output >> ${Conf_path}raw_output.${Speed}

	Conf_file="${Conf_path}all_s1_${Speed}.conf"
	xml_file="${xml_path}all_s1_output.xml"
	Chan_Cnt=0
	Add_Header
	Add_BaseSource1_Channels
	Add_Source1_Channels
	Add_BaseSource1_Channels 1
	Add_Source1_Channels 1
	Grab_And_Fill $SourceID1
	cat ${Conf_path}raw_output >> ${Conf_path}raw_output.${Speed}

	Conf_file="${Conf_path}all_${Speed}.conf"
	xml_file="${xml_path}all_output.xml"
	Chan_Cnt=0
	Add_Header
	Add_Base_Channels
	Add_Common_Channels
	Add_Base_Channels 1
	Add_Common_Channels 1
	Grab_And_Fill $SourceID1 $SourceID2
	cat ${Conf_path}raw_output >> ${Conf_path}raw_output.${Speed}

	# An extra add hoc fill only for one day for the monthly changing "Zender van de Maand"
	# Set Chan_Cnt to 1 to enable it. There is an extra header in "Add_Header" for this one.
	Speed="alt"
	Conf_file="${Conf_path}extra_s2_${Speed}.conf"
	xml_file="${xml_path}extra_s2_output.xml"
	Chan_Cnt=0
	Add_Header
#	echo "NPO Best;7;316;best-24;;;4;npo_best.png" >> $Conf_file
#	Grab_And_Fill $SourceID1
	cat ${Conf_path}raw_output >> ${Conf_path}raw_output.${Speed}

elif [ "$Group" == "selected" ]; then
	Conf_file="${Conf_path}sel_s2_${Speed}.conf"
	xml_file="${xml_path}sel_s2_output.xml"
	Chan_Cnt=0
	Add_Header
	Add_BaseSource2_Channels
	Add_BaseSource2_Channels 1
	Grab_And_Fill $SourceID2
	cat ${Conf_path}raw_output >> ${Conf_path}raw_output.${Speed}

	Conf_file="${Conf_path}sel_s1_${Speed}.conf"
	xml_file="${xml_path}sel_s1_output.xml"
	Chan_Cnt=0
	Add_Header
	Add_BaseSource1_Channels
	Add_BaseSource1_Channels 1
	Grab_And_Fill $SourceID1
	cat ${Conf_path}raw_output >> ${Conf_path}raw_output.${Speed}

	Conf_file="${Conf_path}sel_${Speed}.conf"
	xml_file="${xml_path}sel_output.xml"
	Chan_Cnt=0
	Add_Header
	Add_Base_Channels
	Add_Base_Channels 1
	Grab_And_Fill $SourceID1 $SourceID2
	cat ${Conf_path}raw_output >> ${Conf_path}raw_output.${Speed}

fi

