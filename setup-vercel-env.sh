#!/bin/bash

# Script to set up environment variables in Vercel from .env file
# Usage: ./setup-vercel-env.sh

echo "Setting up Vercel environment variables from .env file..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    exit 1
fi

# Read .env file and set each variable
while IFS='=' read -r key value; do
    # Skip comments and empty lines
    if [[ $key =~ ^#.*$ ]] || [[ -z $key ]]; then
        continue
    fi
    
    # Skip empty values
    if [[ -z $value ]]; then
        echo "Skipping $key (empty value)"
        continue
    fi
    
    echo "Setting $key..."
    vercel env add "$key" "$value"
done < .env

echo "Environment variables setup complete!"
echo "Run 'vercel --prod' to deploy with the new environment variables."
