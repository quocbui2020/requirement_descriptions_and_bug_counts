# read_able_dot_com.py: Method to interact with read-able.com website.

import re
import requests


class ReadAbleDotComHelper:
    def __init__(self):
        pass

    ## Calculate the Readability Scores ##
    def post_url_readable_tool(self, text):
        html_entities = ''.join([f'&#{ord(char)};' for char in text])
        
        # Define the URL and payload
        url = 'https://www.webfx.com/tools/m/ra/check.php'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'accept-encoding': 'gzip, deflate, br',
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        payload = {
            'tab': 'Test by Direct Link',
            'input': html_entities
        }
        
        # Make the POST request
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            return None
        
        # Return the response content
        return response.content
    
    def extract_readability_values(self, byte_content):
        # Step 1: Decode byte content to string
        content = byte_content.decode('utf-8')
        
        # Step 2: Extract `card-percent` values
        card_percent_values = re.findall(r'class=\\"card-percent\\">([\d.-]+)<\\/p>', content)
        card_percent_values = card_percent_values[:6]  # Get only the first 6 values

        # Step 3: Extract `card-value` values
        card_value_values = re.findall(r'class=\\"card-value\\">([\d.-]+)<\\/p>', content)
        card_value_values = card_value_values[:6]  # Get only the first 6 values

        # Combine both lists
        values = card_percent_values + card_value_values

        return values