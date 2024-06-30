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
        pattern = re.compile(r'^(\s*def .*)$', re.MULTILINE) # ^: beginning of the line; $: end of the line.

        # Find all matches for lines starting with "def"
        matches = list(pattern.finditer(py_content_without_comment))

        # Get the start and end positions of each match
        positions = [match.start() for match in matches]
        positions.append(len(py_content_without_comment))  # Add the end position of the last block

        # Split the content into sections based on the positions
        content_blocks = [py_content_without_comment[positions[i]:positions[i+1]] for i in range(len(positions)-1)]
        
        # For each content block, determine the end of the function:
        for block in content_blocks:
            # Split the block by '\n'
            block_lines = block.split('\n')

            # Collect all lines associates to the functions:
            function_lines = []
            keep_next_line = False # This flag indicates that the next line belongs to the function. Handle case when the line is a part of string.
            spaces_before_def_count = -1

            tracker = {
                "missing_closed_curly_brackets": 0,
                "missing_closed_squared_brackets": 0,
                "missing_closed_parentheses": 0,
                "missing_single_quote": False,
                "missing_double_quote": False,
                "last_char_backward_slash": False,
            }

            # Iterate through each line of a block. Skip i=0 because it is just ''
            for i in range(1, len(block_lines)):
                inside_leading_white_space_region = True
                # Count the leading white spaces of each line and track te bracket
                leading_spaces_count = 0
                for index, c in enumerate(block_lines[i]):
                    # Check if the character is leading white space
                    if inside_leading_white_space_region and c == ' ':
                        leading_spaces_count += 1
                    elif inside_leading_white_space_region and c != '':
                        inside_leading_white_space_region = False

                    inside_comment = tracker['missing_single_quote'] or tracker['missing_double_quote']
                    
                    if c == '"' and not tracker['missing_single_quote']:
                        tracker['missing_double_quote'] = -tracker['missing_double_quote']
                    elif c == "'" and not tracker['missing_doubl_quote']:
                        tracker['missing_single_quote'] = -tracker['missing_single_quote']
                    elif not inside_comment and c == '{':
                        tracker['missing_closed_curly_brackets'] += 1
                    elif not inside_comment and c == '}':
                        tracker['missing_closed_curly_brackets'] -= 1
                    elif not inside_comment and c == '[':
                        tracker['missing_closed_squared_brackets'] += 1
                    elif not inside_comment and c == ']':
                        tracker['missing_closed_squared_brackets'] -= 1
                    elif not inside_comment and c == '(':
                        tracker['missing_closed_parentheses'] += 1
                    elif not inside_comment and c == ')':
                        tracker['missing_closed_parentheses'] -= 1
                    elif not inside_comment and index == len(block_lines[i]) - 1 and c == '\\':  # last character in the line is backward slash
                        tracker['last_char_backward_slash'] = True
                    else:
                        break
                
                # Decide if this line a part of the function or not:
                if i >= 2:
                    if (leading_spaces_count > spaces_before_def_count) or (keep_next_line == True):
                        function_lines.append(block_lines[i])

                        # Determine `keep_next_line` flag:
                        if tracker['missing_closed_curly_brackets'] or tracker['missing_closed_parentheses'] or tracker['missing_closed_squared_brackets'] or tracker['last_char_backward_slash'] or tracker['missing_single_quote'] or tracker['missing_double_quote']:
                            keep_next_line = True
                        else:
                            keep_next_line = False
                    else:
                        break # The line is not the part of the function, break out of block line loop.

                elif i == 1: # Assuming if i=1, it contains keyword `def` to define a python function.
                    function_lines.append(block_lines[i])
                    spaces_before_def_count = leading_spaces_count

                
            
            # Set block = all function lines.
            block = '\n'.join(function_lines)



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