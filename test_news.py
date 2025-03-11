#!/usr/bin/env python3
import requests
import os
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
API_KEY = os.getenv("FINANCIAL_NEWS_API_KEY")

def test_crypto_endpoint():
    logger.info("Testing cryptocurrency endpoint...")
    url = f"https://financialmodelingprep.com/api/v3/quotes/crypto?apikey={API_KEY}"
    
    try:
        response = requests.get(url, timeout=10)
        logger.info(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list):
                logger.info(f"Success! Received {len(data)} cryptocurrency items")
                # Show first item as example
                if len(data) > 0:
                    logger.info(f"Example: {data[0]}")
                return True
            else:
                logger.error(f"Received invalid data format: {type(data)}")
        else:
            logger.error(f"API error: {response.status_code}")
            logger.error(f"Error message: {response.text}")
    except Exception as e:
        logger.error(f"Request error: {str(e)}")
    
    return False

def test_market_endpoint():
    logger.info("Testing market index endpoint...")
    url = f"https://financialmodelingprep.com/api/v3/quotes/index?apikey={API_KEY}"
    
    try:
        response = requests.get(url, timeout=10)
        logger.info(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list):
                logger.info(f"Success! Received {len(data)} market indices")
                # Show first item as example
                if len(data) > 0:
                    logger.info(f"Example: {data[0]}")
                return True
            else:
                logger.error(f"Received invalid data format: {type(data)}")
        else:
            logger.error(f"API error: {response.status_code}")
            logger.error(f"Error message: {response.text}")
    except Exception as e:
        logger.error(f"Request error: {str(e)}")
    
    return False

if __name__ == "__main__":
    print(f"API Key available: {bool(API_KEY)}")
    print(f"API Key length: {len(API_KEY) if API_KEY else 0}")
    
    print("\n=== Testing Crypto Endpoint ===")
    crypto_success = test_crypto_endpoint()
    
    print("\n=== Testing Market Endpoint ===")
    market_success = test_market_endpoint()
    
    print("\n=== Summary ===")
    print(f"Crypto endpoint: {'✅ WORKING' if crypto_success else '❌ NOT WORKING'}")
    print(f"Market endpoint: {'✅ WORKING' if market_success else '❌ NOT WORKING'}")
