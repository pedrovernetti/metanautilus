#!/bin/bash

tryDoing()
{
    if ! $@; then
        status=$?
        printf "\033[1;31mFAILED!\033[0m\n"
        exit $status
        fi
}

declare -r metanautilus_data_folder="/usr/share/metanautilus"
declare -r extensions_folder="/usr/share/nautilus-python/extensions"

# get the script's own path
if [[ "$0" != /* ]]; then
    if [[ "$0" == './'* ]]; then declare -r selfpath="$PWD/${0#.\/}"
    elif [[ -f "$PWD/$0" ]]; then declare -r selfpath="$PWD/$0"
    else declare -r selfpath=$(find /bin /sbin /usr/bin /usr/sbin -type f -name '$0' -print 2>/dev/null); fi
else
    declare -r selfpath="$0"
    fi

# take command line arguments
MODE=1
if [[ "$#" -gt 1 ]]; then 
    printf "Usage: '$0' [--reinstall|--uninstall|--full-uninstall]\n"
    exit 1
elif [[ "$#" -gt 0 ]]; then
    if [[ "$1" == "--reinstall" ]]; then MODE=2
    elif [[ "$1" == "--full-uninstall" ]]; then MODE=3
    elif [[ "$1" == "--uninstall" ]]; then MODE=4
    else printf "Usage: '$0' [--reinstall|--uninstall|--full-uninstall]\n"; fi
    fi

# default mode's first step (installing dependencies)
if [[ "$MODE" -lt 2 ]]; then
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
    else tryDoing sudo apt -y install python-pyexiv2; fi
    tryDoing sudo $pip install pypdf2
    tryDoing sudo $pip install olefile
    tryDoing sudo $pip install torrentool
    
# non-default modes' first step (removing old files)
else
    sudo rm -vfr "$metanautilus_data_folder"
    sudo rm -vf "$extensions_folder/metanautilus.py"
    if [[ "$MODE" -lt 4 ]]; then rm -vfr "$HOME/.cache/metanautilus"; fi
    if [[ "$MODE" -gt 2 ]]; then 
        # finishing
        printf "\n\033[2m[press any key to restart Nautilus]\033[0m "; read -n 1 -s; printf "\n\n"
        sudo -u "${HOME##*/}" nautilus -q &> /dev/null &
        sudo killall nautilus &> /dev/null
        sudo -u "${HOME##*/}" nautilus &> /dev/null &
        printf "\033[1;32mDONE!\033[0m\n"
        exit
        fi
    fi

# self-explainatory steps
printf "\033[1mCopying mapping files to the (just created) data folder...\033[0m\n"
tryDoing sudo mkdir -p "$metanautilus_data_folder"
tryDoing sudo cp -n "${selfpath%/*}/"*.map "$metanautilus_data_folder"

printf "\033[1mCopying the script to the nautilus-python folder...\033[0m\n"
tryDoing sudo mkdir -p "$extensions_folder"
tryDoing sudo cp -n "${selfpath%/*}/metanautilus.py" "$extensions_folder"

printf "\033[1mGiving \033[3mexecute permission\033[0;0m\033[1m to the script...\033[0m\n"
tryDoing sudo chmod +x "$extensions_folder/metanautilus.py"

# finishing
tryDoing sudo -u "${HOME##*/}" mkdir -p "$HOME/.cache/metanautilus"
tryDoing sudo chown -R "${HOME##*/}":"${HOME##*/}" "$HOME/.cache/metanautilus"
printf "\n\033[2m[press any key to restart Nautilus]\033[0m "; read -n 1 -s; printf "\n\n"
sudo -u "${HOME##*/}" nautilus -q &> /dev/null &
sudo killall nautilus &> /dev/null
sudo -u "${HOME##*/}" nautilus &> /dev/null &
printf "\033[1;32mDONE!\033[0m\n"

