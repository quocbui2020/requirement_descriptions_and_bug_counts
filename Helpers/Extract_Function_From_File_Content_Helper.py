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
        Extract all Python functions.
        
        Parameters:
        content (str): The content of the file as a string.
        
        Returns:
        list: A list of tuples where each tuple contains the function name and entire function.
        """
        list_of_functions = []

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
        for block_index, block in enumerate(content_blocks):
            # Split the block by '\n'
            block_lines = block.split('\n')

            # Variables initialization
            function_lines = []
            keep_next_line = False # This flag indicates that the next line belongs to the function. Handle case when the line is a part of string.
            spaces_before_def_count = 999
            tracker = {
                "missing_closed_curly_brackets": 0,
                "missing_closed_squared_brackets": 0,
                "missing_closed_parentheses": 0,
                "missing_single_quote": False,
                "missing_double_quote": False,
            }
            function_def_line_tracker = {
                    "function_def_signature": '',
                    "is_part_of_function_def": None,
                    "func_def_start_line_index": -1,
                    "func_def_end_line_index": -1
            }
            
            # Iterate through each line of a block.
            for line_index in range(0, len(block_lines)):
                # If it is just a blank line, skip to the next line:
                if block_lines[line_index] == '':
                    continue
                
                # Variables initialization
                still_inside_leading_white_space_region = True
                leading_spaces_count = 0
                last_nonspace_character = ''
                

                # Count the leading white spaces of each line and track the bracket
                for char_index, c in enumerate(block_lines[line_index]):
                    # Check if the character is leading white space char
                    if still_inside_leading_white_space_region:
                        if c == ' ':
                            leading_spaces_count += 1
                        else:
                            still_inside_leading_white_space_region = False
                    else:
                        if c != ' ':
                            last_nonspace_character = c

                    is_inside_string = tracker['missing_single_quote'] or tracker['missing_double_quote']
                    
                    if c == '"' and not tracker['missing_single_quote']:
                        tracker['missing_double_quote'] = -tracker['missing_double_quote']
                    elif c == "'" and not tracker['missing_double_quote']:
                        tracker['missing_single_quote'] = -tracker['missing_single_quote']
                    elif not is_inside_string and c == '{':
                        tracker['missing_closed_curly_brackets'] += 1
                    elif not is_inside_string and c == '}':
                        tracker['missing_closed_curly_brackets'] -= 1
                    elif not is_inside_string and c == '[':
                        tracker['missing_closed_squared_brackets'] += 1
                    elif not is_inside_string and c == ']':
                        tracker['missing_closed_squared_brackets'] -= 1
                    elif not is_inside_string and c == '(':
                        tracker['missing_closed_parentheses'] += 1
                    elif not is_inside_string and c == ')':
                        tracker['missing_closed_parentheses'] -= 1
                
                # Decide if this line a part of the function or not:
                if (leading_spaces_count > spaces_before_def_count) or (keep_next_line == True) or (spaces_before_def_count == 999):
                    function_lines.append(block_lines[line_index])

                    # Determine `keep_next_line` flag:
                    if last_nonspace_character == '\\' or last_nonspace_character == '+' or tracker['missing_closed_curly_brackets'] or tracker['missing_closed_parentheses'] or tracker['missing_closed_squared_brackets'] or tracker['missing_single_quote'] or tracker['missing_double_quote']:
                        keep_next_line = True
                    else:
                        keep_next_line = False
                else:
                    break # The line is not the part of the function, break out of block line loop.
                
                # Case if the line is the first line of function def signature:
                if spaces_before_def_count == 999 and 'def' in block_lines[line_index]: 
                    spaces_before_def_count = leading_spaces_count
                    function_def_line_tracker['is_part_of_function_def'] = True
                    function_def_line_tracker['func_def_start_line_index'] = line_index

                # Case if the line is the last line of function def signature:
                if function_def_line_tracker['is_part_of_function_def'] == True and last_nonspace_character == ':' and not tracker['missing_closed_parentheses']:
                    function_def_line_tracker['is_part_of_function_def'] = False
                    function_def_line_tracker['func_def_end_line_index'] = line_index

            # Update content block to store entire function implementation
            content_blocks[block_index] = '\n'.join(function_lines)

            # Obtain function def signature:
            for x in range(function_def_line_tracker['func_def_start_line_index'], function_def_line_tracker['func_def_end_line_index'] + 1):
                if function_def_line_tracker['function_def_signature'] == '':
                    function_def_line_tracker['function_def_signature'] = block_lines[x]
                else:
                    function_def_line_tracker['function_def_signature'] += ' ' + block_lines[x].strip()
            
            # Append (function def signature, full function implementation) into `list_of_functions`
            list_of_functions.append((function_def_line_tracker['function_def_signature'].strip(), content_blocks[block_index]))

        return list_of_functions

    ## C++ ##

    def remove_cpp_comments(content):
        return
    def extract_cpp_functions(content):
        list_of_cpp_functions = []
        #TODO: finished it

        return list_of_cpp_functions
    
# Testing area
response = requests.get(f"https://hg.mozilla.org/mozilla-central/raw-file/000b7732d8f0996ab5c8e55a98514d592e9391d5/testing/web-platform/harness/wptrunner/browsers/firefox.py")
full_testing_content = '''
def functionA(arg_1,
    arg_2):   
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


helper = ExtractFunctionFromFileContentHelper()
response_text_without_comments = helper.remove_python_comments(response.text)
list_py_functions = helper.extract_python_functions(response_text_without_comments)