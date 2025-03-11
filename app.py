from flask import Flask, request, abort, jsonify
from linebot.v3 import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.exceptions import InvalidSignatureError
import requests
import json
import threading
import time
import schedule
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from config import (
    LINE_CHANNEL_ACCESS_TOKEN,
    LINE_CHANNEL_SECRET,
    OPENAI_API_KEY,
    CHATGPT_CONFIG,
    SYSTEM_PROMPT,
    MAX_HISTORY_LENGTH,
    HOST,
    PORT,
    DEBUG,
    FINANCIAL_NEWS_API_KEY,
    USER_IDS
)
import sys
import logging
from line_helpers import send_push_message, send_reply_message
from openai_helpers import OpenAIChat

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure proper encoding for console output
if sys.stdout.encoding != 'utf-8':
    logger.warning(f"Console encoding is {sys.stdout.encoding}, not utf-8. This might cause issues with non-ASCII characters.")

# Initialize Flask app
app = Flask(__name__)

# Initialize LINE API client
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Initialize OpenAI client
openai_client = OpenAIChat(
    api_key=OPENAI_API_KEY,
    system_prompt=SYSTEM_PROMPT,
    model=CHATGPT_CONFIG.get("model", "gpt-3.5-turbo"),
    temperature=CHATGPT_CONFIG.get("temperature", 0.7),
    max_tokens=CHATGPT_CONFIG.get("max_tokens", 500),
    top_p=CHATGPT_CONFIG.get("top_p", 1.0) if "top_p" in CHATGPT_CONFIG else None,
    frequency_penalty=CHATGPT_CONFIG.get("frequency_penalty", 0.0) if "frequency_penalty" in CHATGPT_CONFIG else None,
    presence_penalty=CHATGPT_CONFIG.get("presence_penalty", 0.0) if "presence_penalty" in CHATGPT_CONFIG else None
)

# Store conversation history
conversation_history: Dict[str, List[Dict[str, str]]] = {}

@app.route("/", methods=['GET'])
def index():
    """
    Root endpoint with basic information
    """
    return jsonify({
        "status": "running",
        "service": "LineGPT Bot",
        "endpoints": {
            "webhook": "/callback",
            "health": "/health"
        }
    })

@app.route("/health", methods=['GET'])
def health():
    """
    Health check endpoint
    """
    return jsonify({
        "status": "healthy",
        "services": {
            "line_bot": "connected",
            "openai": "ready"
        }
    })

def get_financial_news() -> str:
    """
    Get the latest financial news from a financial news API
    
    Returns:
        Formatted financial news as a string
    """
    try:
        url = f"https://financialmodelingprep.com/api/v3/stock_news?limit=5&apikey={FINANCIAL_NEWS_API_KEY}"
        response = requests.get(url, timeout=10)  # Added timeout for better error handling
        response.raise_for_status()  # Raise an exception for bad responses
        news = response.json()
        
        if not news:
            return "No financial news available at the moment. Please try again later."
        
        # Format news for LINE message
        formatted_news = "📈 Today's Financial News 📉\n\n"
        for i, item in enumerate(news, 1):
            formatted_news += f"{i}. {item['title']}\n"
            formatted_news += f"   {item['site']} - {item['publishedDate']}\n"
            formatted_news += f"   {item['url']}\n\n"
        
        return formatted_news
    except requests.RequestException as e:
        logger.error(f"Error fetching financial news: {str(e)}", exc_info=True)
        return "Unable to fetch financial news at this time. Please try again later."
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Error parsing financial news data: {str(e)}", exc_info=True)
        return "Unable to parse financial news data. Please try again later."
    except Exception as e:
        logger.error(f"Unexpected error fetching financial news: {str(e)}", exc_info=True)
        return "Unable to fetch financial news at this time. Please try again later."

def send_financial_news_to_users() -> None:
    """
    Send financial news to all registered users
    """
    news = get_financial_news()
    
    for user_id in USER_IDS:
        try:
            logger.info(f"Sending financial news to user {user_id}")
            push_line_message(user_id, news)
            logger.info(f"Financial news sent to user {user_id}")
        except Exception as e:
            logger.error(f"Error sending news to user {user_id}: {str(e)}", exc_info=True)

def push_line_message(user_id: str, text: str) -> requests.Response:
    """
    Push a text message to a LINE user
    
    Args:
        user_id: LINE user ID to send message to
        text: Message text to send
        
    Returns:
        API response
    """
    return send_push_message(user_id, text, LINE_CHANNEL_ACCESS_TOKEN)

def send_line_message(reply_token: str, text: str) -> requests.Response:
    """
    Send a text message to a LINE user using the reply token
    
    Args:
        reply_token: LINE reply token
        text: Message text to send
        
    Returns:
        API response
    """
    return send_reply_message(reply_token, text, LINE_CHANNEL_ACCESS_TOKEN)

def schedule_news() -> None:
    """
    Schedule daily financial news updates
    """
    schedule.every().day.at("08:00").do(send_financial_news_to_users)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

def get_chatgpt_response(user_id: str, message: str) -> str:
    """
    Get a response from ChatGPT
    
    Args:
        user_id: User ID for conversation tracking
        message: User message to respond to
        
    Returns:
        ChatGPT response
    """
    # Get the user's conversation history if it exists
    user_history = conversation_history.get(user_id, [])
    
    # Get response from OpenAI
    response = openai_client.get_response(
        message=message,
        conversation_history=user_history,
        add_language_instruction=True
    )
    
    # Update conversation history
    openai_client.manage_conversation_history(
        user_id=user_id,
        message=message,
        response=response,
        conversation_history=conversation_history,
        max_history_length=MAX_HISTORY_LENGTH
    )
    
    return response

def reset_conversation(user_id: str) -> str:
    """
    Reset the conversation history for a user
    
    Args:
        user_id: User ID to reset conversation for
        
    Returns:
        Confirmation message
    """
    if user_id in conversation_history:
        conversation_history[user_id] = []
        return "Conversation history has been reset. You can start a new conversation now."
    return "No conversation history found. You can start a new conversation."

@app.route("/callback", methods=['POST'])
def callback():
    """
    Handle LINE webhook callbacks
    
    Returns:
        HTTP response
    """
    try:
        # Get X-Line-Signature header value
        signature = request.headers.get('X-Line-Signature')
        
        # Log the headers to help with debugging
        logger.info(f"Request headers: {dict(request.headers)}")
        
        # Get request body as text
        body = request.get_data(as_text=True)
        logger.info(f"Request body: {body}")
        
        # If signature is missing, log a warning and try to process as test request
        if not signature:
            logger.warning("X-Line-Signature header is missing. This request may not be from LINE.")
            logger.warning("This is expected for test requests but not for actual LINE webhooks.")
            
            # For testing purposes, we'll try to process the request anyway
            try:
                data = json.loads(body)
                logger.info(f"Trying to process test request: {data}")
                
                # Handle test events
                if 'events' in data and len(data['events']) > 0:
                    test_event = data['events'][0]
                    logger.info(f"Processing test event: {test_event}")
                    
                    # If it's a message event with a reply token, handle it
                    if test_event.get('type') == 'message' and 'replyToken' in test_event:
                        test_message = test_event.get('message', {}).get('text', 'No message')
                        user_id = test_event.get('source', {}).get('userId', 'test_user')
                        logger.info(f"Test message from {user_id}: {test_message}")
                        
                        # Process the message and get a response
                        try:
                            response = get_chatgpt_response(user_id, test_message)
                            logger.info(f"Response for test message: {response}")
                            
                            # Try to reply with the response
                            try:
                                send_line_message(test_event['replyToken'], response)
                                logger.info("Sent reply to test message")
                            except Exception as e:
                                logger.error(f"Error replying to test message: {str(e)}", exc_info=True)
                        except Exception as e:
                            logger.error(f"Error processing test message: {str(e)}", exc_info=True)
                return 'Test request processed'
            except Exception as e:
                logger.error(f"Error processing test request: {str(e)}", exc_info=True)
                return 'Error processing test request', 400
        
        # For real LINE requests, use the handler
        try:
            handler.handle(body, signature)
        except InvalidSignatureError:
            logger.error("Invalid signature")
            abort(400)
        except Exception as e:
            logger.error(f"Error handling webhook: {str(e)}", exc_info=True)
            abort(500)
        
        return 'OK'
    except Exception as e:
        logger.error(f"Unexpected error in callback: {str(e)}", exc_info=True)
        return 'Internal server error', 500

@app.route("/callback", methods=['GET'])
def verify_webhook():
    """
    Handle LINE webhook verification
    
    Returns:
        Verification message
    """
    return 'Webhook verification successful!'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    """
    Handle text messages from LINE
    
    Args:
        event: LINE message event
    """
    user_id = event.source.user_id
    message = event.message.text
    reply_token = event.reply_token
    
    logger.info(f"Received message from {user_id}: '{message}'")
    
    # Check if the message is empty
    if not message or message.strip() == "":
        logger.warning("Empty message received")
        send_line_message(reply_token, "I received an empty message. Please try again.")
        return
    
    try:
        # Process commands
        if message.startswith('/'):
            command_parts = message.split(' ', 1)
            command = command_parts[0].lower()
            logger.info(f"Processing command: {command}")
            
            if command == '/chat':
                # Extract the query (everything after "/chat ")
                query = command_parts[1].strip() if len(command_parts) > 1 else ""
                
                if query:
                    logger.info(f"Processing chat query: '{query}'")
                    # Use try/except to handle potential encoding issues
                    try:
                        response = get_chatgpt_response(user_id, query)
                        logger.debug(f"ChatGPT response for '{query}': '{response}'")
                        send_line_message(reply_token, response)
                    except Exception as e:
                        logger.error(f"Error getting ChatGPT response: {str(e)}", exc_info=True)
                        send_line_message(reply_token, "I encountered an error processing your request. Please try again.")
                else:
                    logger.info("Empty query after /chat command")
                    send_line_message(reply_token, "Please provide a message after /chat command.")
            
            elif command == '/reset':
                logger.info(f"Resetting conversation for user {user_id}")
                response = reset_conversation(user_id)
                send_line_message(reply_token, response)
            
            elif command == '/news':
                logger.info("Fetching financial news")
                news = get_financial_news()
                if news:
                    send_line_message(reply_token, news)
                else:
                    send_line_message(reply_token, "Sorry, I couldn't fetch financial news at the moment. Please try again later.")
            
            elif command == '/help':
                logger.info("Sending help information")
                help_text = (
                    "Available commands:\n"
                    "/chat [message] - Chat with the AI assistant\n"
                    "/reset - Reset your conversation history\n"
                    "/news - Get the latest financial news\n"
                    "/help - Show this help message"
                )
                send_line_message(reply_token, help_text)
            
            else:
                logger.warning(f"Unknown command: {command}")
                send_line_message(reply_token, f"Unknown command: {command}\nType /help to see available commands.")
        
        # Treat any non-command message as a regular chat message
        else:
            logger.info(f"Processing regular chat message: '{message}'")
            # Use try/except to handle potential encoding issues
            try:
                response = get_chatgpt_response(user_id, message)
                logger.debug(f"ChatGPT response: '{response}'")
                send_line_message(reply_token, response)
            except Exception as e:
                logger.error(f"Error getting ChatGPT response: {str(e)}", exc_info=True)
                send_line_message(reply_token, "I encountered an error processing your request. Please try again.")
    
    except Exception as e:
        logger.error(f"Error handling message: {str(e)}", exc_info=True)
        try:
            send_line_message(reply_token, "I apologize, but I encountered an error processing your request. Please try again later.")
        except Exception as inner_e:
            logger.error(f"Error sending error message: {str(inner_e)}", exc_info=True)

@app.route("/test_encoding", methods=['GET'])
def test_encoding():
    """
    Test endpoint for encoding issues
    
    Returns:
        JSON response with encoding test results
    """
    user_id = request.args.get('user_id', '')
    text = request.args.get('text', '测试中文编码 (Testing Chinese encoding)')
    
    logger.info(f"Testing encoding with text: '{text}'")
    
    # Test string encoding/decoding
    encoded = text.encode('utf-8')
    decoded = encoded.decode('utf-8')
    
    # Check if LINE API credentials are configured
    line_config_ok = bool(LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET)
    
    # Check if OpenAI API credentials are configured
    openai_config_ok = bool(OPENAI_API_KEY)
    
    # Information about the system
    import sys
    import locale
    
    result = {
        "message": "Encoding test results",
        "original_text": text,
        "encoded_length": len(encoded),
        "decoded_text": decoded,
        "text_equal": text == decoded,
        "non_ascii_chars": [c for c in text if ord(c) > 127],
        "system_info": {
            "python_version": sys.version,
            "default_encoding": sys.getdefaultencoding(),
            "locale": locale.getdefaultlocale(),
            "file_system_encoding": sys.getfilesystemencoding(),
        },
        "line_api_configured": line_config_ok,
        "openai_api_configured": openai_config_ok,
        "chatgpt_config": {k: v for k, v in CHATGPT_CONFIG.items() if k != "top_p"},  # Exclude top_p for compatibility
        "top_p_exists": "top_p" in CHATGPT_CONFIG
    }
    
    if user_id:
        try:
            # If user_id is provided, try to send a test message
            logger.info(f"Attempting to send test message to user {user_id}")
            
            # Get response from OpenAI using our helper
            response = openai_client.get_response(text)
            
            # Add test results to response
            result["openai_test"] = {
                "success": True,
                "input": text,
                "response": response
            }
            
            # Try to push message to user
            push_response = push_line_message(user_id, f"Encoding Test: {response}")
            result["line_push_test"] = {
                "success": True,
                "response": str(push_response)
            }
        except Exception as e:
            result["test_error"] = str(e)
    
    return jsonify(result)

if __name__ == "__main__":
    # Start the scheduler in a separate thread
    scheduler_thread = threading.Thread(target=schedule_news, daemon=True)
    scheduler_thread.start()
    
    # Run the Flask app
    app.run(host=HOST, port=PORT, debug=DEBUG)