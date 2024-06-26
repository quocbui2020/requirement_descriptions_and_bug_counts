import requests
from datetime import datetime
#from prettytable import PrettyTable
from bs4 import BeautifulSoup
import logging
from logging import info
from time import strftime, localtime
import pyodbc
import traceback
import re
import time
import argparse

class ExtractFunctionFromFileContentHelper:
    # Constructor
    def __init__ (self):
        return
    
    ## PYTHON ## 
    def remove_python_comments(self, content):
        """
        Remove all Python comments from the given content.
        
        Parameters:
        content (str): The content of the file as a string.
        
        Returns:
        str: The content without comments.
        """

        # Pattern to match single-line comments
        single_line_comment_pattern = r'#.*' # .*: zero or more of any characters (EXCEPT end line terminator '\n')
        
        # Pattern to match multi-line strings/comments
        multi_line_comment_pattern = r'\'\'\'[\s\S]*?\'\'\'|\"\"\"[\s\S]*?\"\"\"'   # \s: white space char; \S: non-white space char; |: or;
        
        # First remove multi-line comments
        content = re.sub(multi_line_comment_pattern, '', content)
        
        # Then remove single-line comments
        content = re.sub(single_line_comment_pattern, '', content)
        
        return content
    def extract_python_functions(self, content):
        """
        Extract all Python function names and their implementations.
        
        Parameters:
        content (str): The content of the file as a string.
        
        Returns:
        list: A list of tuples where each tuple contains the function name and its implementation.
        """
        
        # Remove comments from the content
        content = remove_python_comments(content)
        
        # Pattern to match function definitions
        function_pattern = re.compile(r'def\s+(\w+)\s*\(.*?\):\s*(.*?)\n(?=def|\Z)', re.DOTALL)
        
        # Find all function definitions and implementations
        matches = function_pattern.findall(content)
        
        # Create the list of tuples
        list_of_py_functions = [(match[0], 'def ' + match[0] + match[1]) for match in matches]
        
        return list_of_py_functions
    

    ## C++ ##

    def remove_cpp_comments(content):
        return
    def extract_cpp_functions(content):
        list_of_cpp_functions = []
        #TODO: finished it

        return list_of_cpp_functions
    
# Testing area
response = requests.get(f"https://hg.mozilla.org/mozilla-central/raw-file/000b7732d8f0996ab5c8e55a98514d592e9391d5/testing/web-platform/harness/wptrunner/browsers/firefox.py")
helper = ExtractFunctionFromFileContentHelper()
print(helper.remove_python_comments(response.text))