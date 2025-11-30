#!/bin/bash
# Test script for Bash extraction

MY_VAR="hello world"
readonly API_KEY="secret123"

function setup_env() {
    local config_dir="/etc/app"
    export PATH="$config_dir/bin:$PATH"
}

cleanup() {
    echo "Cleaning up..."
    rm -rf /tmp/app-*
}

source ./lib/helpers.sh
. ./config/settings.sh

# Pipeline example - note semicolon terminates this statement
curl -s "$API_URL/data" | jq '.items[]' | tee output.json;

# Command substitution
result=$(curl -s "$API_URL/status")
current_date=`date +%Y-%m-%d`

# Redirection
echo "Log entry" >> /var/log/app.log
cat < input.txt 2>&1

# Call functions
setup_env
cleanup
