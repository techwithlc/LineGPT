from typing import Dict, Any, List
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# LINE API credentials
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

# OpenAI API credentials
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Financial News API key
FINANCIAL_NEWS_API_KEY = os.getenv('FINANCIAL_NEWS_API_KEY')

# List of user IDs to send news to
USER_IDS: List[str] = []
# You can add static user IDs here or load from environment
if os.getenv('USER_IDS'):
    USER_IDS = os.getenv('USER_IDS').split(',')

# ChatGPT configuration
CHATGPT_CONFIG: Dict[str, Any] = {
    'model': os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'),
    'temperature': float(os.getenv('OPENAI_TEMPERATURE', '0.7')),
    'max_tokens': int(os.getenv('OPENAI_MAX_TOKENS', '500')),
    'presence_penalty': float(os.getenv('OPENAI_PRESENCE_PENALTY', '0')),
    'frequency_penalty': float(os.getenv('OPENAI_FREQUENCY_PENALTY', '0')),
    'top_p': float(os.getenv('OPENAI_TOP_P', '1.0')),
}

# System prompt for ChatGPT
SYSTEM_PROMPT = os.getenv('SYSTEM_PROMPT', """You are a helpful assistant in a LINE chat. 
You provide concise, accurate, and helpful responses.
You can engage in casual conversation while maintaining professionalism.
You should avoid any harmful, unethical, or inappropriate content.
You can also provide financial insights and analysis when asked.
You are capable of responding in multiple languages, including English, Chinese, Japanese, and others.
Always respond in the same language that the user used in their message.""")

# Conversation history settings
MAX_HISTORY_LENGTH = int(os.getenv('MAX_HISTORY_LENGTH', '10'))  # Maximum number of messages to keep in conversation history

# Flask server settings
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 8080))
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true' 