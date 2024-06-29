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
    
    # https://chatgpt.com/share/4e907564-606b-4766-a1a9-05b1c709ec64
    def extract_python_functions(self, content):
        """
        Extract all Python functions.
        
        Parameters:
        content (str): The content of the file as a string.
        
        Returns:
        list: A list of tuples where each tuple contains the function name and entire function.
        """
        
        # Remove comments from the content
        py_content_without_comment = self.remove_python_comments(content)
        
        # Regular expression to match lines starting with optional spaces followed by "def"
        pattern = re.compile(r'^(\s*def .*)$', re.MULTILINE)

        # Find all matches for lines starting with "def"
        matches = list(pattern.finditer(py_content_without_comment))

        # Get the start and end positions of each match
        positions = [match.start() for match in matches]
        positions.append(len(py_content_without_comment))  # Add the end position of the last block

        # Split the content into sections based on the positions
        content_blocks = [py_content_without_comment[positions[i]:positions[i+1]] for i in range(len(positions)-1)]
        
        return content_blocks

    ## C++ ##

    def remove_cpp_comments(content):
        return
    def extract_cpp_functions(content):
        list_of_cpp_functions = []
        #TODO: finished it

        return list_of_cpp_functions
    
# Testing area
# response = requests.get(f"https://hg.mozilla.org/mozilla-central/raw-file/000b7732d8f0996ab5c8e55a98514d592e9391d5/testing/web-platform/harness/wptrunner/browsers/firefox.py")
full_testing_content = '''
def functionA():
    inside function A.
        inside function A.
    inside function A.

statement outside of the function.

def functionB(arg_1, arg_2):
    inside function B.

class A:
    def functionC(arg_1, arg_2):
        inside function C.

def functionD(arg_1, arg_2):
    inside function D.
'''
testing_content = '''
def functionA():
    inside function A.
        inside function A.
    inside function A.

statement outside of the function.
'''

helper = ExtractFunctionFromFileContentHelper()
list_py_functions = helper.extract_python_functions(testing_content)