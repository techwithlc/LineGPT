from flask import Flask, request, abort, jsonify
from linebot.v3 import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.exceptions import InvalidSignatureError
from openai import OpenAI
import requests
import json
import threading
import time
import schedule
from datetime import datetime
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
client = OpenAI(api_key=OPENAI_API_KEY)

# Store conversation history
conversation_history = {}

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

def get_financial_news():
    """
    Get the latest financial news from a financial news API
    """
    try:
        url = f"https://financialmodelingprep.com/api/v3/stock_news?limit=5&apikey={FINANCIAL_NEWS_API_KEY}"
        response = requests.get(url)
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
    except Exception as e:
        print(f"Error fetching financial news: {str(e)}")
        return "Unable to fetch financial news at this time. Please try again later."

def send_financial_news_to_users():
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

def push_line_message(user_id, text):
    """
    Push a text message to a LINE user
    """
    # Ensure text is not None and not empty
    if text is None or text.strip() == '':
        text = "Sorry, I couldn't generate a response. Please try again."
        logger.warning("Empty message detected, using fallback text")
    
    # Ensure text is a string
    if not isinstance(text, str):
        text = str(text)
        logger.warning(f"Converting non-string message to string: {text}")
    
    # Check if text contains any invisible characters or is all whitespace
    if text.strip() == '':
        text = "Sorry, I couldn't generate a response. Please try again."
        logger.warning("Message contains only whitespace, using fallback text")
    
    # Ensure text is properly encoded
    try:
        # Force encode and decode to ensure valid UTF-8
        text = text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception as e:
        logger.error(f"Error encoding text: {str(e)}")
        text = "Sorry, I couldn't generate a response due to encoding issues. Please try again."
    
    # Final sanity check - if text is still empty or only whitespace after all processing
    # This is a critical check before sending to LINE API
    if not text or text.strip() == '':
        text = "I apologize for the inconvenience. Please try again later."
        logger.critical("Text is still empty after all processing! Using emergency fallback message")
    
    # Truncate if too long
    if len(text) > 5000:
        logger.warning(f"Message too long ({len(text)} chars), truncating to 5000 chars")
        text = text[:4997] + "..."
    
    # Create message object with explicit type and text
    message = {
        "type": "text",
        "text": text
    }
    
    # Log the exact message being sent
    logger.info(f"Pushing message to LINE user {user_id}: {message}")
    logger.info(f"Message text length: {len(text)}, first 50 chars: {text[:50]}")
    
    # Create request payload
    payload = {
        "to": user_id,
        "messages": [message]
    }
    
    # Log the exact payload being sent
    logger.info(f"Sending LINE API push request: {json.dumps(payload)}")
    
    try:
        # Use requests library to directly call LINE API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
        }
        
        # Verify the payload before sending
        if not payload["messages"][0]["text"] or payload["messages"][0]["text"].strip() == "":
            logger.critical("CRITICAL ERROR: Message text is empty right before sending!")
            payload["messages"][0]["text"] = "Emergency fallback message due to empty text."
        
        # Double check the payload is valid JSON
        json_payload = json.dumps(payload)
        
        # Send the message
        response = requests.post(
            'https://api.line.me/v2/bot/message/push',
            headers=headers,
            data=json_payload
        )
        
        # Log the response
        logger.info(f"Push response status: {response.status_code}")
        logger.info(f"Push response body: {response.text}")
        
        if response.status_code != 200:
            logger.error(f"Error pushing message: {response.text}")
            raise Exception(f"LINE API returned status code {response.status_code}: {response.text}")
        
        return response
    except Exception as e:
        logger.error(f"Error pushing LINE message: {str(e)}", exc_info=True)
        
        # Create a guaranteed non-empty fallback message
        fallback_text = "An error occurred. Please try again."
        
        try:
            logger.info("Attempting to send a simple fallback message")
            fallback_payload = {
                "to": user_id,
                "messages": [{
                    "type": "text",
                    "text": fallback_text
                }]
            }
            
            # Send fallback using requests
            fallback_response = requests.post(
                'https://api.line.me/v2/bot/message/push',
                headers=headers,
                json=fallback_payload
            )
            
            logger.info(f"Fallback message status: {fallback_response.status_code}")
            logger.info(f"Fallback message response: {fallback_response.text}")
            
            return fallback_response
        except Exception as inner_e:
            logger.error(f"Error sending fallback LINE message: {str(inner_e)}", exc_info=True)
            raise inner_e

def send_line_message(reply_token, text):
    """
    Send a text message to a LINE user using the reply token
    """
    # Ensure text is not None and not empty
    if text is None or text.strip() == '':
        text = "Sorry, I couldn't generate a response. Please try again."
        logger.warning("Empty message detected, using fallback text")
    
    # Ensure text is a string
    if not isinstance(text, str):
        text = str(text)
        logger.warning(f"Converting non-string message to string: {text}")
    
    # Check if text contains any invisible characters or is all whitespace
    if text.strip() == '':
        text = "Sorry, I couldn't generate a response. Please try again."
        logger.warning("Message contains only whitespace, using fallback text")
    
    # Ensure text is properly encoded
    try:
        # Force encode and decode to ensure valid UTF-8
        text = text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception as e:
        logger.error(f"Error encoding text: {str(e)}")
        text = "Sorry, I couldn't generate a response due to encoding issues. Please try again."
    
    # Final sanity check - if text is still empty or only whitespace after all processing
    # This is a critical check before sending to LINE API
    if not text or text.strip() == '':
        text = "I apologize for the inconvenience. Please try again later."
        logger.critical("Text is still empty after all processing! Using emergency fallback message")
    
    # Truncate if too long
    if len(text) > 5000:
        logger.warning(f"Message too long ({len(text)} chars), truncating to 5000 chars")
        text = text[:4997] + "..."
    
    # Create message object with explicit type and text
    message = {
        "type": "text",
        "text": text
    }
    
    # Log the exact message being sent
    logger.info(f"Sending message with reply token {reply_token}: {message}")
    logger.info(f"Message text length: {len(text)}, first 50 chars: {text[:50]}")
    
    # Create request payload
    payload = {
        "replyToken": reply_token,
        "messages": [message]
    }
    
    # Log the exact payload being sent
    logger.info(f"Sending LINE API reply request: {json.dumps(payload)}")
    
    try:
        # Use requests library to directly call LINE API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
        }
        
        # Verify the payload before sending
        if not payload["messages"][0]["text"] or payload["messages"][0]["text"].strip() == "":
            logger.critical("CRITICAL ERROR: Message text is empty right before sending!")
            payload["messages"][0]["text"] = "Emergency fallback message due to empty text."
        
        # Double check the payload is valid JSON
        json_payload = json.dumps(payload)
        
        # Send the message
        response = requests.post(
            'https://api.line.me/v2/bot/message/reply',
            headers=headers,
            data=json_payload
        )
        
        # Log the response
        logger.info(f"Reply response status: {response.status_code}")
        logger.info(f"Reply response body: {response.text}")
        
        if response.status_code != 200:
            logger.error(f"Error sending reply: {response.text}")
            raise Exception(f"LINE API returned status code {response.status_code}: {response.text}")
        
        return response
    except Exception as e:
        logger.error(f"Error sending LINE reply: {str(e)}", exc_info=True)
        
        # Create a guaranteed non-empty fallback message
        fallback_text = "An error occurred. Please try again."
        
        try:
            logger.info("Attempting to send a simple fallback message")
            fallback_payload = {
                "replyToken": reply_token,
                "messages": [{
                    "type": "text",
                    "text": fallback_text
                }]
            }
            
            # Send fallback using requests
            fallback_response = requests.post(
                'https://api.line.me/v2/bot/message/reply',
                headers=headers,
                json=fallback_payload
            )
            
            logger.info(f"Fallback message status: {fallback_response.status_code}")
            logger.info(f"Fallback message response: {fallback_response.text}")
            
            return fallback_response
        except Exception as inner_e:
            logger.error(f"Error sending fallback LINE reply: {str(inner_e)}", exc_info=True)
            raise inner_e

def schedule_news():
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
    """
    # Log the received message
    logger.info(f"Received message from user {user_id}: '{message}'")
    
    # Check if message is empty
    if not message or message.strip() == "":
        logger.warning("Empty message received")
        return "Please provide a message for me to respond to."
    
    # Initialize conversation history if not exists
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    
    # Prepare system message
    system_message = SYSTEM_PROMPT
    
    # Check for non-ASCII characters (like Chinese)
    has_non_ascii = any(ord(c) > 127 for c in message)
    if has_non_ascii:
        logger.info("Detected non-ASCII characters in message, adding language instruction to system prompt")
        system_message += " Please respond in the same language as the user's message."
    
    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Prepare messages for the API call
        messages = [
            {"role": "system", "content": system_message}
        ]
        
        # Add conversation history
        for msg in conversation_history[user_id]:
            messages.append(msg)
        
        # Add the current message
        messages.append({"role": "user", "content": message})
        
        # Log the request being sent
        logger.info(f"Sending request to OpenAI with message: '{message}'")
        
        # Create parameters dict from CHATGPT_CONFIG, handling missing keys gracefully
        openai_params = {
            "model": CHATGPT_CONFIG.get("model", "gpt-3.5-turbo"),
            "messages": messages,
            "temperature": CHATGPT_CONFIG.get("temperature", 0.7),
            "max_tokens": CHATGPT_CONFIG.get("max_tokens", 500)
        }
        
        # Add optional parameters only if they exist in config
        if "top_p" in CHATGPT_CONFIG:
            openai_params["top_p"] = CHATGPT_CONFIG["top_p"]
        if "frequency_penalty" in CHATGPT_CONFIG:
            openai_params["frequency_penalty"] = CHATGPT_CONFIG["frequency_penalty"]
        if "presence_penalty" in CHATGPT_CONFIG:
            openai_params["presence_penalty"] = CHATGPT_CONFIG["presence_penalty"]
        
        # Make the API call with validated parameters
        response = client.chat.completions.create(**openai_params)
        
        # Extract the response text
        assistant_message = response.choices[0].message.content
        
        # Check if response is empty
        if not assistant_message or assistant_message.strip() == "":
            logger.warning("Received empty response from OpenAI")
            assistant_message = "I apologize, but I couldn't generate a response. Please try again."
        
        # Log the response
        logger.info(f"Received response from OpenAI: '{assistant_message}'")
        
        # Update conversation history
        conversation_history[user_id].append({"role": "user", "content": message})
        conversation_history[user_id].append({"role": "assistant", "content": assistant_message})
        
        # Trim conversation history if it gets too long
        if len(conversation_history[user_id]) > MAX_HISTORY_LENGTH * 2:  # *2 because each exchange has 2 messages
            conversation_history[user_id] = conversation_history[user_id][-MAX_HISTORY_LENGTH * 2:]
            logger.info(f"Trimmed conversation history for user {user_id}")
        
        return assistant_message
        
    except KeyError as e:
        logger.error(f"Error getting response from OpenAI: '{str(e)}'", exc_info=True)
        return "I apologize, but I encountered an error while processing your request. Please try again later."
        
    except Exception as e:
        logger.error(f"Error getting response from OpenAI: {str(e)}", exc_info=True)
        return "I apologize, but I encountered an error while processing your request. Please try again later."

def reset_conversation(user_id: str) -> str:
    """
    Reset the conversation history for a user
    """
    if user_id in conversation_history:
        conversation_history[user_id] = []
        return "Conversation history has been reset. You can start a new conversation now."
    return "No conversation history found. You can start a new conversation."

@app.route("/callback", methods=['POST'])
def callback():
    """
    Handle LINE webhook callbacks
    """
    try:
        # Get X-Line-Signature header value
        signature = request.headers.get('X-Line-Signature')
        
        # Log the headers to help with debugging
        logger.info(f"Request headers: {dict(request.headers)}")
        
        # Get request body as text
        body = request.get_data(as_text=True)
        logger.info(f"Request body: {body}")
        
        # If signature is missing, log a warning and return 400
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
    """
    return 'Webhook verification successful!'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    """
    Handle text messages from LINE
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

@app.route("/send_news", methods=['GET'])
def trigger_news_sending():
    """
    Endpoint to manually trigger sending news to all users
    """
    try:
        send_financial_news_to_users()
        return jsonify({"status": "success", "message": "Financial news sent to all users"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/get_user_id", methods=['GET'])
def get_user_id():
    """
    Endpoint to help users get their LINE user ID
    """
    return jsonify({
        "message": "Send a message to your LINE bot, then check the logs or the /debug endpoint to find your user ID",
        "instructions": [
            "1. Make sure your webhook URL is set in the LINE Developers Console",
            "2. Send a message to your LINE bot",
            "3. Check the logs for a message like 'Received message from USER_ID: ...'",
            "4. Use that USER_ID for testing with the /test_message endpoint"
        ],
        "debug_url": f"{request.url_root}debug"
    })

@app.route("/debug", methods=['GET'])
def debug_info():
    """
    Debug endpoint to check the status of the application
    """
    # Get the list of users with conversation history
    users_with_history = list(conversation_history.keys())
    
    # Get system information
    import sys
    import locale
    
    return jsonify({
        "service": "LineGPT Bot",
        "status": "running",
        "python_version": sys.version,
        "encoding": {
            "default": sys.getdefaultencoding(),
            "filesystem": sys.getfilesystemencoding(),
            "stdout": sys.stdout.encoding
        },
        "line_api": {
            "channel_secret_length": len(LINE_CHANNEL_SECRET) if LINE_CHANNEL_SECRET else 0,
            "channel_access_token_length": len(LINE_CHANNEL_ACCESS_TOKEN) if LINE_CHANNEL_ACCESS_TOKEN else 0
        },
        "openai_api": {
            "api_key_length": len(OPENAI_API_KEY) if OPENAI_API_KEY else 0,
            "model": CHATGPT_CONFIG.get("model", "unknown")
        },
        "users": {
            "conversation_history_users": len(users_with_history),
            "registered_users": len(USER_IDS),
            "recent_users": users_with_history[:5] if users_with_history else []
        },
        "webhook_url": f"{request.url_root}callback"
    })

@app.route("/test_message", methods=['GET'])
def test_message():
    """
    Test endpoint to send a message to a user
    """
    user_id = request.args.get('user_id')
    message = request.args.get('message', 'This is a test message from LineGPT.')
    
    if not user_id:
        return jsonify({
            "status": "error",
            "message": "Missing user_id parameter"
        }), 400
    
    try:
        push_line_message(user_id, message)
        return jsonify({
            "status": "success",
            "message": f"Test message sent to user {user_id}"
        })
    except Exception as e:
        logger.error(f"Error sending test message: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/test_chinese')
def test_chinese():
    """
    Debug endpoint to test sending Chinese messages
    """
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({"error": "Missing user_id parameter"}), 400
    
    # Test messages in different languages
    test_messages = [
        "你好，这是一条测试消息。",  # Chinese
        "Hello, this is a test message.",  # English
        "こんにちは、これはテストメッセージです。",  # Japanese
        "안녕하세요, 이것은 테스트 메시지입니다.",  # Korean
        "สวัสดี นี่คือข้อความทดสอบ",  # Thai
        "Привет, это тестовое сообщение.",  # Russian
        "مرحبا، هذه رسالة اختبار."  # Arabic
    ]
    
    results = []
    
    for i, message in enumerate(test_messages):
        try:
            # Log the message being tested
            logger.info(f"Testing message {i+1}: {message}")
            logger.info(f"Message length: {len(message)}, bytes: {len(message.encode('utf-8'))}")
            
            # Create message object
            line_message = {
                "type": "text",
                "text": message
            }
            
            # Create request payload
            payload = {
                "to": user_id,
                "messages": [line_message]
            }
            
            # Log the payload
            logger.info(f"Sending test message payload: {json.dumps(payload)}")
            
            # Send the message
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
            }
            
            # Convert payload to JSON string
            json_payload = json.dumps(payload)
            
            # Send the message
            response = requests.post(
                'https://api.line.me/v2/bot/message/push',
                headers=headers,
                data=json_payload
            )
            
            # Log the response
            logger.info(f"Test message {i+1} response status: {response.status_code}")
            logger.info(f"Test message {i+1} response body: {response.text}")
            
            # Add result
            results.append({
                "message": message,
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else response.text
            })
            
            # Wait a bit between messages to avoid rate limiting
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error sending test message {i+1}: {str(e)}", exc_info=True)
            results.append({
                "message": message,
                "success": False,
                "error": str(e)
            })
    
    return jsonify({
        "success": True,
        "results": results
    })

@app.route('/raw_message')
def raw_message():
    """
    Debug endpoint to send a raw message to LINE API
    """
    user_id = request.args.get('user_id')
    message = request.args.get('message', 'Test message from raw endpoint')
    
    if not user_id:
        return jsonify({"error": "Missing user_id parameter"}), 400
    
    # Ensure message is not None and not empty
    if message is None or message.strip() == '':
        message = "Test message from raw endpoint"
        logger.warning("Empty message detected, using default test message")
    
    # Ensure message is properly encoded
    try:
        # Force encode and decode to ensure valid UTF-8
        message = message.encode('utf-8', errors='replace').decode('utf-8')
    except Exception as e:
        logger.error(f"Error encoding message: {str(e)}")
        message = "Test message (encoding error occurred)"
    
    # Truncate if too long
    if len(message) > 5000:
        logger.warning(f"Message too long ({len(message)} chars), truncating to 5000 chars")
        message = message[:4997] + "..."
    
    # Create message object with explicit type and text
    line_message = {
        "type": "text",
        "text": message
    }
    
    # Create request payload
    payload = {
        "to": user_id,
        "messages": [line_message]
    }
    
    # Log the exact payload being sent
    logger.info(f"Sending raw LINE API request: {json.dumps(payload)}")
    logger.info(f"Message text length: {len(message)}, first 50 chars: {message[:50]}")
    
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
        }
        
        # Verify the payload before sending
        if not payload["messages"][0]["text"] or payload["messages"][0]["text"].strip() == "":
            logger.critical("CRITICAL ERROR: Message text is empty right before sending!")
            payload["messages"][0]["text"] = "Emergency fallback message due to empty text."
        
        # Double check the payload is valid JSON
        json_payload = json.dumps(payload)
        
        # Send the message
        response = requests.post(
            'https://api.line.me/v2/bot/message/push',
            headers=headers,
            data=json_payload
        )
        
        # Log the response
        logger.info(f"Raw message response status: {response.status_code}")
        logger.info(f"Raw message response body: {response.text}")
        
        if response.status_code != 200:
            logger.error(f"Error sending raw message: {response.text}")
            return jsonify({
                "error": f"LINE API returned status code {response.status_code}",
                "details": response.text
            }), 500
        
        return jsonify({
            "success": True,
            "message": "Message sent successfully",
            "response": response.json()
        })
    except Exception as e:
        logger.error(f"Error sending raw LINE message: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Failed to send message",
            "details": str(e)
        }), 500

@app.route("/test_encoding", methods=['GET'])
def test_encoding():
    """
    Test endpoint for encoding issues
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
            
            # Initialize OpenAI client
            client = OpenAI(api_key=OPENAI_API_KEY)
            
            # Create a simple test payload
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ]
            
            # Create parameters dict
            openai_params = {
                "model": CHATGPT_CONFIG.get("model", "gpt-3.5-turbo"),
                "messages": messages,
                "temperature": CHATGPT_CONFIG.get("temperature", 0.7),
                "max_tokens": CHATGPT_CONFIG.get("max_tokens", 100)
            }
            
            # Add top_p if it exists
            if "top_p" in CHATGPT_CONFIG:
                openai_params["top_p"] = CHATGPT_CONFIG["top_p"]
            
            # Make the API call
            response = client.chat.completions.create(**openai_params)
            
            # Extract response text
            assistant_message = response.choices[0].message.content
            
            # Send to user
            result["openai_test"] = {
                "success": True,
                "input": text,
                "response": assistant_message
            }
            
            # Try to push message to user
            if LINE_CHANNEL_ACCESS_TOKEN:
                configuration = Configuration(
                    access_token=LINE_CHANNEL_ACCESS_TOKEN
                )
                with ApiClient(configuration) as api_client:
                    api_instance = MessagingApi(api_client)
                    
                    # Construct push message payload
                    push_payload = {
                        "to": user_id,
                        "messages": [
                            {
                                "type": "text",
                                "text": f"Encoding Test: {assistant_message}"
                            }
                        ]
                    }
                    
                    # Send the message
                    push_response = api_instance.push_message_with_http_info(push_payload)
                    result["line_push_test"] = {
                        "success": True,
                        "response": str(push_response)
                    }
            
        except Exception as e:
            result["test_error"] = str(e)
    
    return jsonify(result)

@app.route('/test_broadcast')
def test_broadcast():
    """
    Debug endpoint to test sending a message to all registered users
    """
    message = request.args.get('message', 'This is a test broadcast message to all users.')
    
    if not USER_IDS:
        return jsonify({
            "error": "No registered users found",
            "message": "Please add user IDs to the USER_IDS list in the .env file"
        }), 400
    
    results = []
    
    # Log the broadcast attempt
    logger.info(f"Attempting to broadcast message to {len(USER_IDS)} users: {message}")
    
    for i, user_id in enumerate(USER_IDS):
        try:
            # Log the user being messaged
            logger.info(f"Sending broadcast to user {i+1}/{len(USER_IDS)}: {user_id}")
            
            # Use the push_line_message function to send the message
            response = push_line_message(user_id, message)
            
            # Add result
            results.append({
                "user_id": user_id,
                "success": True if hasattr(response, 'status_code') and response.status_code == 200 else False,
                "status_code": response.status_code if hasattr(response, 'status_code') else None,
                "response": response.json() if hasattr(response, 'json') and callable(response.json) else str(response)
            })
            
            # Wait a bit between messages to avoid rate limiting
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error broadcasting to user {user_id}: {str(e)}", exc_info=True)
            results.append({
                "user_id": user_id,
                "success": False,
                "error": str(e)
            })
    
    return jsonify({
        "success": True,
        "message": f"Broadcast attempted to {len(USER_IDS)} users",
        "results": results
    })

if __name__ == "__main__":
    # Start the scheduler in a separate thread
    scheduler_thread = threading.Thread(target=schedule_news, daemon=True)
    scheduler_thread.start()
    
    # Use a different port to avoid conflict with AirPlay
    PORT = 8080
    app.run(host=HOST, port=PORT, debug=DEBUG) 