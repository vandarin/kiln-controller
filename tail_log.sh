#!/bin/bash
tail -f /var/log/daemon.log|grep --color=auto -P '(<[^>]*>)|pid=[\d.]+|kiln must catch up'
