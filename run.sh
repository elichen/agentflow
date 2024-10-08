#!/bin/bash

# Function to start the script and handle logging and restart
run_script() {
    while true; do
        # Run the Python script in the background, with unbuffered output
        # Redirect stdout and stderr to log.txt
        python -u src/runner.py >> log.txt 2>&1
        # Wait for a second before restarting to avoid rapid restarts
        sleep 1
    done
}

# Remove log.txt if it exists
rm -f log.txt

# Start the script in the background
run_script &
