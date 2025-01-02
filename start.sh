#!/bin/bash
set -e

echos login
echo "Logged in to Twitter"

# use the passed arguments or default to "echos start" if none are provided
start_command=${@:-"echos start"}

while true; do
    # run main.py with a 24-hr timeout
    timeout 86400 $start_command 2>&1 | tee -a main_output.txt
    echo "Restarting main.py after 24 hours..."
done