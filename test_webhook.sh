#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}LineGPT Webhook Test Tool${NC}"
echo "This script will test if your webhook is properly configured."
echo ""

# Check if ngrok is running
if ! curl -s http://localhost:4040/api/tunnels > /dev/null; then
    echo -e "${RED}Error: ngrok is not running.${NC}"
    echo "Please run ./setup_webhook.sh in a separate terminal window first."
    exit 1
fi

# Get the ngrok URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | grep -o 'https://[^"]*')

if [ -z "$NGROK_URL" ]; then
    echo -e "${RED}Error: Could not retrieve ngrok URL.${NC}"
    echo "Please make sure ngrok is running properly."
    exit 1
fi

WEBHOOK_URL="${NGROK_URL}/callback"
echo -e "Testing webhook URL: ${YELLOW}${WEBHOOK_URL}${NC}"
echo ""

# Test 1: Check if the webhook verification endpoint is working
echo "Test 1: Webhook verification endpoint (GET request)"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X GET "${WEBHOOK_URL}")

if [ "$RESPONSE" == "200" ]; then
    echo -e "${GREEN}✓ Success: Webhook verification endpoint is working (HTTP 200)${NC}"
else
    echo -e "${RED}✗ Failed: Webhook verification endpoint returned HTTP ${RESPONSE}${NC}"
    echo "Please check if your Flask application is running and the route is correctly implemented."
fi

# Test 2: Check if the Flask app is running
echo ""
echo "Test 2: Flask application health check"
HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X GET "${NGROK_URL}/health")

if [ "$HEALTH_RESPONSE" == "200" ]; then
    echo -e "${GREEN}✓ Success: Flask application is running and healthy (HTTP 200)${NC}"
else
    echo -e "${RED}✗ Failed: Health check endpoint returned HTTP ${HEALTH_RESPONSE}${NC}"
    echo "Please check if your Flask application is running."
fi

echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Make sure your webhook URL is set in the LINE Developers Console"
echo "2. Verify the webhook in the LINE Developers Console"
echo "3. Enable the webhook in the LINE Developers Console"
echo "4. Try sending a message to your LINE bot"

echo ""
echo -e "${YELLOW}Troubleshooting:${NC}"
echo "- If tests failed, make sure your Flask app is running (./run.sh)"
echo "- Check that ngrok is running and properly configured (./setup_webhook.sh)"
echo "- Verify that your LINE channel credentials are correct in your .env file"
echo "- Check the Flask application logs for any errors" 