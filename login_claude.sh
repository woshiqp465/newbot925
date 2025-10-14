#!/bin/bash
export ANTHROPIC_API_KEY=$(cat ~/.bashrc | grep ANTHROPIC_AUTH_TOKEN | cut -d"'" -f2)
echo "API Key: ${ANTHROPIC_API_KEY:0:20}..."
claude login --api-key "$ANTHROPIC_API_KEY"
