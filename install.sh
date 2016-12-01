#!/bin/bash

if [[ ("$1" == '--not-ubuntu' ) || ( $(lsb_release -is | tr '[:upper:]' '[:lower:]') != "ubuntu" ) ]]; then
	printf "This installation script is for Ubuntu only...\n\n"
	printf "\033[2m#0 Choose between Python 2 (at source/) and Python 3 (at source3/) versions...\033[0m\n"
	printf "#1 Install Mutagen, pyexiv2, Kaa Metadata and pypdf (Python modules)\n"
	printf "#2 Install python-nautilus via your package manager\n"
	printf "#3 Check where python-nautilus extension must be placed in your system\n"
	printf "   and place a copy of the chosen \033[3m.py\033[0m there with execute permission\n\n"
	exit 1
	fi

# get the script's own path
if [[ "$0" != /* ]]; then
	if [[ "$0" == './'* ]]; then declare -r selfpath="$PWD/${0#.\/}"
	elif [[ -f "$PWD/$0" ]]; then declare -r selfpath="$PWD/$0"
	else declare -r selfpath=$(find /bin /sbin /usr/bin /usr/sbin -type f -name '$0' -print 2>/dev/null); fi
else
	declare -r selfpath="$0"
	fi

destination_folder="/usr/share/nautilus-python/extensions"

printf "\033[1mInstalling dependencies...\033[0m\n"
if [[ ( "$1" == 3* ) || (("$1" == "") && ( $(lsb_release -rs | head -c2) -ge 16 )) ]]; then
	sudo apt-get install python3-mutagen python-pyexiv2 python-kaa-metadata python-pypdf; status=$?
	proper_ver="source3"
else
	sudo apt-get install python-mutagen python-pyexiv2 python-kaa-metadata python-pypdf2; status=$?
	if [[ $status -ne 0 ]]; then
		sudo apt-get install python3-mutagen python-pyexiv2 python-kaa-metadata python-pypdf; status=$?
		fi
	proper_ver="source"
	fi
sudo apt-get install python-nautilus; end_status=$?
end_status=$((status + end_status))

if [[ $end_status -eq 0 ]]; then
	printf "\033[1mCopying the script to the nautilus-python folder...\033[0m\n"
	printf "<> $proper_ver/metadata-on-nautilus.py\n"
	sudo mkdir -p "$destination_folder"; status=$?
	end_status=$((status + end_status))
	fi

if [[ $end_status -eq 0 ]]; then
	sudo cp -i "${selfpath%/*}/$proper_ver/metadata-on-nautilus.py" "$destination_folder"; status=$?
	end_status=$((status + end_status))
	fi

if [[ $end_status -eq 0 ]]; then
	printf "\033[1mGiving \033[3mexecute permission\033[0;0m\033[1m to the script...\033[0m\n"
	sudo chmod +x "$destination_folder/metadata-on-nautilus.py"; status=$?
	end_status=$((status + end_status))
	fi

if [[ $end_status -eq 0 ]]; then
	printf "\n\033[2m[press any key to restart Nautilus]\033[0m "; read -n 1 -s; printf "\n\n"
	nautilus -q
	nautilus &> /dev/null &
	printf "\033[1;32mDONE!\033[0m\n"
else 
	printf "\033[1;31mFAILED!\033[0m\n"
	exit $end_status
	fi

