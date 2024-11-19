#!/bin/bash
set -e

python3 login_to_twitter.py
echo "Logged in to Twitter"

while true; do
    # run main.py with a 180-minute timeout
    timeout 10800 python3 -u main.py 2>&1 | tee -a main_output.txt
    echo "Restarting main.py after 180 minutes..."
done