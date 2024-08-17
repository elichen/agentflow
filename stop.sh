#!/bin/bash

# Find all PIDs of the running python script using the name "runner.py"
PYTHON_PIDS=$(pgrep -f "python -u runner.py")

# Find all PIDs of the running "run.sh" script
RUNSH_PIDS=$(pgrep -f "/bin/bash ./run.sh")

# Check if there are any running "runner.py" processes
if [ -n "$PYTHON_PIDS" ]; then
    # Kill all the found "runner.py" processes
    kill $PYTHON_PIDS
    echo "Stopped runner.py instances with PIDs: $PYTHON_PIDS."
else
    echo "No instances of runner.py are running."
fi

# Check if there are any running "run.sh" scripts
if [ -n "$RUNSH_PIDS" ]; then
    # Kill all the found "run.sh" scripts
    kill $RUNSH_PIDS
    echo "Stopped run.sh instances with PIDs: $RUNSH_PIDS."
else
    echo "No instances of run.sh are running."
fi
