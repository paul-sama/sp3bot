#!/usr/bin/env bash

BASEDIR=$(cd $(dirname "$0") && pwd)
SCRIPT_PATH=$BASEDIR/service.py


pid=$(ps -ef | grep "$SCRIPT_PATH" | grep -v grep | awk '{print $2}')

if [ -n "$pid" ]; then
    echo "service is running, pid is $pid, restart it"
    kill -9 "$pid"
    nohup python3 "$SCRIPT_PATH" &
    exit 0
else
    echo "service is not running"
    echo "python3 $SCRIPT_PATH"
    nohup python3 "$SCRIPT_PATH" &
    exit 1
fi


# nohup python3 "$SCRIPT_PATH" > /dev/null 2>&1 &

