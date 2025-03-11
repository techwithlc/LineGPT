"""
OpenAI API Helper functions for LineGPT application
"""
import logging
from typing import Dict, List, Any, Optional
from openai import OpenAI

# Set up logging
logger = logging.getLogger(__name__)

class OpenAIChat:
    """
    Helper class for interacting with OpenAI's chat API
    """
    
    def __init__(
        self, 
        api_key: str, 
        system_prompt: str, 
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 500,
        **additional_params
    ):
        """
        Initialize the OpenAI chat client
        
        Args:
            api_key: OpenAI API key
            system_prompt: System prompt to use for all conversations
            model: Model to use for chat completions
            temperature: Temperature for generating responses
            max_tokens: Maximum tokens for response generation
            additional_params: Additional parameters to pass to OpenAI API
        """
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.additional_params = additional_params
        self.client = OpenAI(api_key=api_key)
    
    def get_response(
        self, 
        message: str, 
        conversation_history: List[Dict[str, str]] = None,
        add_language_instruction: bool = False,
    ) -> str:
        """
        Get a response from the OpenAI API
        
        Args:
            message: User message to respond to
            conversation_history: Previous conversation history
            add_language_instruction: Whether to add an instruction to respond in the same language
            
        Returns:
            Generated response from OpenAI
            
        Raises:
            Exception: If there's an error getting a response
        """
        try:
            # Check if message is empty
            if not message or message.strip() == "":
                logger.warning("Empty message received")
                return "Please provide a message for me to respond to."
            
            # Initialize conversation history if not provided
            if conversation_history is None:
                conversation_history = []
            
            # Prepare system message
            system_message = self.system_prompt
            
            # Add language instruction if needed
            if add_language_instruction and any(ord(c) > 127 for c in message):
                logger.info("Detected non-ASCII characters in message, adding language instruction")
                system_message += " Please respond in the same language as the user's message."
            
            # Prepare messages for the API call
            messages = [
                {"role": "system", "content": system_message}
            ]
            
            # Add conversation history
            for msg in conversation_history:
                messages.append(msg)
            
            # Add the current message
            messages.append({"role": "user", "content": message})
            
            # Log the request being sent
            logger.info(f"Sending request to OpenAI with message: '{message}'")
            
            # Create parameters dict from init params
            openai_params = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                **self.additional_params
            }
            
            # Make the API call with validated parameters
            response = self.client.chat.completions.create(**openai_params)
            
            # Extract the response text
            assistant_message = response.choices[0].message.content
            
            # Check if response is empty
            if not assistant_message or assistant_message.strip() == "":
                logger.warning("Received empty response from OpenAI")
                assistant_message = "I apologize, but I couldn't generate a response. Please try again."
            
            # Log the response
            logger.info(f"Received response from OpenAI: '{assistant_message}'")
            
            return assistant_message
            
        except Exception as e:
            logger.error(f"Error getting response from OpenAI: {str(e)}", exc_info=True)
            return "I apologize, but I encountered an error while processing your request. Please try again later."
    
    def manage_conversation_history(
        self,
        user_id: str,
        message: str, 
        response: str,
        conversation_history: Dict[str, List[Dict[str, str]]],
        max_history_length: int
    ) -> None:
        """
        Update conversation history with new messages and trim if needed
        
        Args:
            user_id: User ID for conversation tracking
            message: User message
            response: Assistant response
            conversation_history: The conversation history dictionary to update
            max_history_length: Maximum number of conversation turns to keep
        """
        # Initialize conversation history if not exists
        if user_id not in conversation_history:
            conversation_history[user_id] = []
        
        # Update conversation history
        conversation_history[user_id].append({"role": "user", "content": message})
        conversation_history[user_id].append({"role": "assistant", "content": response})
        
        # Trim conversation history if it gets too long
        if len(conversation_history[user_id]) > max_history_length * 2:  # *2 because each exchange has 2 messages
            conversation_history[user_id] = conversation_history[user_id][-max_history_length * 2:]
            logger.info(f"Trimmed conversation history for user {user_id}")
