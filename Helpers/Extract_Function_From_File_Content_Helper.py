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
    def __init__ (self): #`self` refers to the class object itself (every function in a class requires `self` as the 1st input parameter)
        return
    
    ##########################################
    ################# PYTHON #################
    ##########################################

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
        list: A list of tuples where each tuple contains the function name and entire function implementation.
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


    ##########################################
    ################## C++ ###################
    ##########################################
    # https://chatgpt.com/c/66dbc955-4f44-8004-beaf-3eb303f23477
    def remove_cpp_comments(self, content):
        return
    def extract_cpp_functions(self, content):
        """
        Extract all C++ functions.
        
        Parameters:
        content (str): The content of the file as a string.
        
        Returns:
        list: A list of tuples where each tuple contains the function name and entire function implementation.
        """
        list_of_cpp_functions = []
        #TODO: finished it

        return list_of_cpp_functions
    

    ##########################################
    ################### C ####################
    ##########################################
    # https://chatgpt.com/c/66dbc9d9-2b38-8004-9d53-90a97cb6d9b8
    def remove_c_comments(self, content):
        # Regular expression patterns to match C-style comments
        block_comment_pattern = re.compile(r'/\*.*?\*/', re.DOTALL)
        line_comment_pattern = re.compile(r'//.*?$' , re.MULTILINE)
        
        # Remove block comments
        file_content_without_comments = re.sub(block_comment_pattern, '', content)
        # Remove line comments
        file_content_without_comments = re.sub(line_comment_pattern, '', file_content_without_comments)
        
        return file_content_without_comments
    
    def extract_c_functions(self, content):
        """
        Extract all C functions.
        
        Parameters:
        content (str): The content of the file as a string.
        
        Returns:
        list: A list of tuples where each tuple contains the function name and entire function implementation.
        """

        list_of_c_functions = []
        function_names = []

        content = self.remove_c_comments(content)

        ## Explain of the regex in 'function_pattern':
        # (?: ...) : A non-capturing group that doesn't create a backreference.
        # [^a-zA-Z0-9\s*\r\n\{\(] : Matches any single character that is not a letter (a-zA-Z), digit (0-9), whitespace (\s*), newline (\r\n), or the characters {, (, #, _.
        # \s* : Matches zero or more spaces (whitespace).
        # \w+ : Matches one or more word characters (letters, digits, or underscore).
        # ([\w\s*]+) : Capturing group that matches one or more word characters (\w) or spaces (\s*).
        # \( : Matches an opening parenthesis (.
        # function_pattern = re.compile(r'(?:[^a-zA-Z0-9\s*\r\n\{\(#_])\s*\w+([\w\s*]+)\(')
        function_pattern = re.compile(r'(?:[^a-zA-Z0-9\s*\r\n\{\(#_])\s*([\w\s*]+)\(') # Work best for 'file_content1' in unit test function 'test_extract_c_functions'
        
        parenthesis_count = 0
        curly_bracket_count = 0
        keyword = ''
        implementation_start = 0
        
        def c_keywords():
            return {
                'if', 'else', 'while', 'for', 'do', 'switch', 'case', 'default',
                'break', 'continue', 'return', 'goto', 'typedef', 'struct', 'union',
                'enum', 'static', 'const', 'volatile', 'inline', 'extern', 'auto',
                'register', 'sizeof'
            }
        
        i = 0
        while i < len(content):
            if parenthesis_count == 0:
                match = function_pattern.search(content, i)
                if match:
                    # Attempt to get the potential class name.
                    keyword = match.group(1)
                    keyword_matches = re.findall(r'\b[a-zA-Z0-9_]+\b', keyword) # Regex explain: matches whole words that consist of alphanumeric characters and underscores.
                    if keyword_matches:
                        keyword = keyword_matches[-1]  # Get the last match as the function name
                    else:
                        keyword = ''  # Set keyword to an empty string if no matches are found

                    i = match.end()  # Set i to the end of the matched pattern
                    parenthesis_count += 1
                    implementation_start = match.start(1)  # Start of function implementation
                else:
                    i += 1
            else:
                if content[i] == '(':
                    parenthesis_count += 1
                elif content[i] == ')':
                    parenthesis_count -= 1
                    if parenthesis_count == 0 and curly_bracket_count == 0 and keyword:
                        # Skip whitespace and check for '{'
                        j = i + 1
                        while j < len(content) and content[j] in ' \t\n\r':
                            j += 1
                        if j < len(content) and content[j] == '{':
                            curly_bracket_count += 1
                            i = j + 1  # Move i to the position right after '{'
                            while i < len(content) and curly_bracket_count > 0:
                                if content[i] == '{':
                                    curly_bracket_count += 1
                                elif content[i] == '}':
                                    curly_bracket_count -= 1
                                i += 1
                            if curly_bracket_count == 0:
                                i -= 1 # set i index back to '}' character
                                function_implementation = content[implementation_start:i+1].strip()
                                if keyword not in c_keywords():
                                    function_names.append(keyword)
                                    list_of_c_functions.append((keyword, function_implementation))
                                    i -= 1 #set i index to character before '}'
                                keyword = ''
                        else:
                            keyword = ''
                i += 1
        return list_of_c_functions


    ##########################################
    ############### JavaScript ###############
    ##########################################

    def remove_js_comments(content):
        return
    def extract_js_functions(content):
        list_of_js_functions = []
        #TODO: finished it

        return list_of_js_functions


### End of class [ExtractFunctionFromFileContentHelper]

