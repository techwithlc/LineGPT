#!/bin/bash

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo "ngrok is not installed. Installing ngrok..."
    
    # Check if Homebrew is installed
    if command -v brew &> /dev/null; then
        brew install ngrok
    else
        echo "Homebrew is not installed. Please install ngrok manually from https://ngrok.com/download"
        exit 1
    fi
fi

# Check if ngrok is authenticated
NGROK_CONFIG_FILE="$HOME/.ngrok2/ngrok.yml"
if [ ! -f "$NGROK_CONFIG_FILE" ] || ! grep -q "authtoken" "$NGROK_CONFIG_FILE"; then
    echo "Ngrok requires authentication with an authtoken."
    echo "Please visit https://dashboard.ngrok.com/get-started/your-authtoken to get your authtoken."
    echo ""
    read -p "Enter your ngrok authtoken: " AUTHTOKEN
    
    if [ -z "$AUTHTOKEN" ]; then
        echo "No authtoken provided. Exiting."
        exit 1
    fi
    
    # Configure ngrok with the authtoken
    ngrok authtoken "$AUTHTOKEN"
    
    if [ $? -ne 0 ]; then
        echo "Failed to configure ngrok with the provided authtoken."
        exit 1
    fi
    
    echo "Ngrok successfully configured with your authtoken."
fi

# Start ngrok in the background
echo "Starting ngrok tunnel to port 8080..."
ngrok http 8080 > /dev/null &
NGROK_PID=$!

# Wait for ngrok to start
sleep 3

# Get the ngrok URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | grep -o 'https://[^"]*')

if [ -z "$NGROK_URL" ]; then
    echo "Failed to get ngrok URL. Please check if ngrok is running properly."
    echo "You may need to sign up for a free ngrok account at https://dashboard.ngrok.com/signup"
    echo "and configure your authtoken."
    
    # Kill the ngrok process if it's running
    if ps -p $NGROK_PID > /dev/null; then
        kill $NGROK_PID
    fi
    
    exit 1
fi

echo "========================================================"
echo "Ngrok tunnel established!"
echo "Your webhook URL is: ${NGROK_URL}/callback"
echo ""
echo "Please set this URL in your LINE Developers Console:"
echo "1. Go to https://developers.line.biz/console/"
echo "2. Select your provider and channel"
echo "3. Go to the 'Messaging API' tab"
echo "4. Scroll down to 'Webhook settings'"
echo "5. Enter '${NGROK_URL}/callback' as the Webhook URL"
echo "6. Click 'Update' and then 'Verify'"
echo "========================================================"
echo ""
echo "Press Ctrl+C to stop ngrok when you're done testing"

# Wait for user to press Ctrl+C
wait $NGROK_PID 