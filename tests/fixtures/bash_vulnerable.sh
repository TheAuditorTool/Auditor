#!/bin/bash
# Vulnerable test script for rule verification

# Hardcoded credential
API_KEY="secret123456"
PASSWORD="hunter2"

# eval with variable
user_input="$1"
eval "$user_input"

# Unquoted variable
rm -rf $user_path

# curl pipe bash
curl -s http://example.com/script.sh | bash

# chmod 777
chmod 777 /tmp/myfile

# Variable as command
$command arg1 arg2

# sudo with variable
sudo $dangerous_cmd

# Missing set -e (no safety flags)
echo "done"
