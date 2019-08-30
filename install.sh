#!/bin/bash

tryDoing()
{
    if ! $@; then
        status=$?
        printf "\033[1;31mFAILED!\033[0m\n"
        exit $status
        fi
}

# get the script's own path
if [[ "$0" != /* ]]; then
    if [[ "$0" == './'* ]]; then declare -r selfpath="$PWD/${0#.\/}"
    elif [[ -f "$PWD/$0" ]]; then declare -r selfpath="$PWD/$0"
    else declare -r selfpath=$(find /bin /sbin /usr/bin /usr/sbin -type f -name '$0' -print 2>/dev/null); fi
else
    declare -r selfpath="$0"
    fi

declare -r data_folder="/usr/share/metanautilus"
declare -r extensions_folder="/usr/share/nautilus-python/extensions"

if [[ $(lsb_release -rs | head -c2) -lt 16 ]]; then
    printf "\033[31;1mOld Ubuntu version (<16.04)...\033[0;0m\n"
    exit
    fi

printf "\033[1mInstalling dependencies...\033[0m\n"
if [[ ( "$#" -ge 1 ) && ( "$1" =~ ^-?-(python)?3$ ) ]]; then 
    tryDoing sudo apt -y install python3-pip; status=$?
    pip='pip3'
else
    tryDoing sudo apt -y install python-pip; status=$?
    pip='pip'
    fi
tryDoing sudo apt -y install python-nautilus
tryDoing sudo $pip install lxml
tryDoing sudo $pip install pymediainfo 
tryDoing sudo $pip install mutagen
tryDoing sudo $pip install pillow
if [[ "$pip" == 'pip3' ]]; then tryDoing sudo $pip install pyexiv2
else tryDoing sudo apt -y install python-pyexiv2
tryDoing sudo $pip install pypdf2
tryDoing sudo $pip install olefile
tryDoing sudo $pip install torrentool

printf "\033[1mCopying files to the (just created) data folder...\033[0m\n"
tryDoing sudo mkdir -p "$data_folder"
tryDoing sudo cp -i "${selfpath%/*}/suffixToMethod.map" "$data_folder"

printf "\033[1mCopying the script to the nautilus-python folder...\033[0m\n"
tryDoing sudo mkdir -p "$extensions_folder"
tryDoing sudo cp -i "${selfpath%/*}/metanautilus.py" "$extensions_folder"

printf "\033[1mGiving \033[3mexecute permission\033[0;0m\033[1m to the script...\033[0m\n"
tryDoing sudo chmod +x "$extensions_folder/metanautilus.py"

printf "\n\033[2m[press any key to restart Nautilus]\033[0m "; read -n 1 -s; printf "\n\n"
tryDoing sudo rm -fr "$HOME/.cache/metanautilus" &> /dev/null
tryDoing mkdir "$HOME/.cache/metanautilus"; fi
nautilus -q
nautilus &> /dev/null &
printf "\033[1;32mDONE!\033[0m\n"

