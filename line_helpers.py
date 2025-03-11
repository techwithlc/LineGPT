"""
LINE API Helper functions for LineGPT application
"""
import json
import logging
import requests
from typing import Dict, Any, Union, Optional

# Set up logging
logger = logging.getLogger(__name__)

def prepare_text_message(text: str) -> str:
    """
    Prepare a text message for sending to LINE.
    Handles validation, encoding, and length checks.
    
    Args:
        text: The message text to prepare
        
    Returns:
        Properly validated and encoded text
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
    if not text or text.strip() == '':
        text = "I apologize for the inconvenience. Please try again later."
        logger.critical("Text is still empty after all processing! Using emergency fallback message")
    
    # Truncate if too long
    if len(text) > 5000:
        logger.warning(f"Message too long ({len(text)} chars), truncating to 5000 chars")
        text = text[:4997] + "..."
    
    return text

def send_push_message(
    user_id: str, 
    text: str, 
    access_token: str
) -> requests.Response:
    """
    Send a push message to a LINE user
    
    Args:
        user_id: LINE user ID to send message to
        text: Message text to send
        access_token: LINE channel access token
        
    Returns:
        API response
    
    Raises:
        Exception: If the API call fails
    """
    # Prepare the message text
    text = prepare_text_message(text)
    
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
    
    # Use requests library to directly call LINE API
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }
    
    # Verify the payload before sending
    if not payload["messages"][0]["text"] or payload["messages"][0]["text"].strip() == "":
        logger.critical("CRITICAL ERROR: Message text is empty right before sending!")
        payload["messages"][0]["text"] = "Emergency fallback message due to empty text."
    
    # Double check the payload is valid JSON
    json_payload = json.dumps(payload)
    
    try:
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

def send_reply_message(
    reply_token: str, 
    text: str, 
    access_token: str
) -> requests.Response:
    """
    Send a reply message to a LINE user
    
    Args:
        reply_token: LINE reply token
        text: Message text to send
        access_token: LINE channel access token
        
    Returns:
        API response
    
    Raises:
        Exception: If the API call fails
    """
    # Prepare the message text
    text = prepare_text_message(text)
    
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
    
    # Use requests library to directly call LINE API
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}'
    }
    
    # Verify the payload before sending
    if not payload["messages"][0]["text"] or payload["messages"][0]["text"].strip() == "":
        logger.critical("CRITICAL ERROR: Message text is empty right before sending!")
        payload["messages"][0]["text"] = "Emergency fallback message due to empty text."
    
    # Double check the payload is valid JSON
    json_payload = json.dumps(payload)
    
    try:
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
