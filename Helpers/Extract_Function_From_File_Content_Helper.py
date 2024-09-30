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
        
        return self.remove_comments(file_type='py', content=content)
    
    def extract_py_functions(self, content):
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
        """
        Remove all C++ comments from the given content.
        
        Parameters:
        content (str): The content of the file as a string.
        
        Returns:
        str: The content without comments.
        """
        
        return self.remove_comments(file_type='cpp', content=content)
    
    def extract_cpp_functions(self, content):
        """
        Extract all C++ functions.
        
        Parameters:
        content (str): The content of the file as a string.
        
        Returns:
        list: A list of tuples where each tuple contains the function name and entire function implementation.
        """
        content = "; \n" + self.remove_cpp_comments(content)
        
        return self.extract_functions_from_c_relatives(content)
    

    ##########################################
    ################### C ####################
    ##########################################
    # https://chatgpt.com/c/66dbc9d9-2b38-8004-9d53-90a97cb6d9b8
    def remove_c_comments(self, content):
        """
        Remove all C comments from the given content.
        
        Parameters:
        content (str): The content of the file as a string.
        
        Returns:
        str: The content without comments.
        """
        
        return self.remove_comments(file_type='c', content=content)
    
    def extract_c_functions(self, content):
        """
        Extract all C functions.
        
        Parameters:
        content (str): The content of the file as a string.
        
        Returns:
        list: A list of tuples where each tuple contains the function name and entire function implementation.
        """
        content = "; \n" + self.remove_c_comments(content)
        
        return self.extract_functions_from_c_relatives(content)


    ##########################################
    ############### JavaScript ###############
    ##########################################
    def remove_js_comments(self, content):
        """

        Remove all JavaScript comments from the given content.
        
        Parameters:
        content (str): The content of the file as a string.
        
        Returns:
        str: The content without comments.
        """
        
        return self.remove_comments(file_type='js', content=content)
    
    def extract_js_functions(self, content):
        # https://chatgpt.com/c/66dbc9d9-2b38-8004-9d53-90a97cb6d9b8

        content = self.remove_js_comments(content)
        
        # The function to determine if we are inside a string or not:
        def is_inside_string():
            if content[i] in {'`', '"', "'"}:
                # Case we're not already inside a string, enter one:
                if tracker['inside_string'] == False:
                    tracker['inside_string'] = True
                    tracker['string_delimiter'] = content[i]
                    return True
                # Case we're already inside a string and hit the character indicates the end of string:
                elif content[i] == tracker['string_delimiter']: # and content[i-1] != '\\': # Make sure it's not escaped (I don't think this condition is necessary)
                    tracker['inside_string'] = False
                    tracker['string_delimiter'] = ''
                    return False
            else:
                return tracker['inside_string']

        tracker = {
            "missing_closed_curly_brackets": 0,
            "missing_closed_squared_brackets": 0,
            "missing_closed_parentheses": 0,
            "missing_single_quote": False,
            "missing_double_quote": False,
            "begin_new_line_index": -1,
            "potential_begin_function_index": -1,
            "inside_string": False,
            "string_delimiter": '',
            "last_char_index": len(content) - 1,
        }
        
        function_signature = ''
        function_implementation = ''
        list_of_js_functions = []

        i = 0
        while i <= tracker['last_char_index']:
            if not is_inside_string():
                # Case we if character is '\n':
                if content[i] == '\n':
                    tracker['begin_new_line_index'] = i

                ## Handle cases:
                # var/let/const function_name = function(...) {...}
                # var/let/const function_name = async function(...) => {...}
                # var/let/const function_name = async (...) => {...}
                # var/let/const function_name = (...) => {...}
                elif content[i] in {'c', 'l', 'v'} and i-1 != -1 and (content[i-1].isspace()) and i+6 < tracker['last_char_index']:
                    if content[i:i+6] == 'const ' or content[i:i+4] in {'let ', 'var '}:
                        # Detect let or const
                        tracker['potential_begin_function_index'] = i

                        # Skip past 'const', 'let', or 'var':
                        i = i+6 if content[i:i+6] == 'const ' else i+4

                        # Skip spaces after 'const', 'let', or 'var':
                        while i <= tracker['last_char_index'] and content[i] == ' ':
                            i += 1

                        # Detect the variable (function name)
                        func_name_start = i
                        while i <= tracker['last_char_index'] and (content[i].isalnum() or content[i] == '_'):
                            i += 1
                        func_name_end = i
                        function_name = content[func_name_start:func_name_end]

                        # Skip to the equal sign '='
                        while i <= tracker['last_char_index'] and content[i] != '=':
                            i += 1
                        i += 1  # Skip '='

                        # Skip spaces after '='
                        while i <= tracker['last_char_index'] and content[i] == ' ':
                            i += 1

                        # Detect 'function' or 'async' keywords or '(...)' pattern:
                        if i+8 < tracker['last_char_index'] and ((content[i:i+8] == 'function' and not content[i+8].isalpha()) or (content[i:i+5] == 'async' and not content[i+5].isalpha()) or content[i] == '('):
                            # The flag to track the case when it could be a tuple, not a function like: `let tuple_name = (...);`
                            could_be_tuple = None

                            # keyword 'fucntion' and 'async' garantee they are function:
                            if content[i:i+8] == 'function':
                                i += 8  # Skip 'function'
                            elif content[i:i+5] == 'async':
                                i += 5  # Skip 'async'
                            elif content[i] == '(':
                                # Could be just `let tuple = (...)`, instead of `let func_name = (...) => {...}`
                                could_be_tuple = True

                            # Skip to the opening parenthesis '('. There could be spacing in between:
                            while i <= tracker['last_char_index'] and content[i] != '(':
                                i += 1

                            # Track parentheses to extract the full signature
                            saved_missing_closed_parentheses_inside_func_params = tracker['missing_closed_parentheses']
                            if content[i] == '(':
                                tracker['missing_closed_parentheses'] += 1

                            # Find the full function signature (including parameters)
                            param_start = i
                            while i <= tracker['last_char_index'] and tracker['missing_closed_parentheses'] > saved_missing_closed_parentheses_inside_func_params:
                                i += 1
                                # Assuming something, the parameters have string in it, so better have `is_inside_string()` here:
                                if not is_inside_string():
                                    if content[i] == '(' and not is_inside_string():
                                        tracker['missing_closed_parentheses'] += 1
                                    elif content[i] == ')' and not is_inside_string():
                                        tracker['missing_closed_parentheses'] -= 1

                            func_signature_end = i + 1
                            function_signature = content[tracker['potential_begin_function_index']:func_signature_end]

                            # Check for '=>' to confirm the case `let/const func_name = (...) => {...}`, not the tuple
                            while could_be_tuple and i <= tracker['last_char_index']:
                                i += 1
                                if (not content[i].isspace() and content [i:i+2] != '=>') or content[i] == '{':
                                    # We confirm that this is just a tuple, not a function. No need to continue
                                    i -= 1 # Move back one character
                                    break
                                elif content[i:i+2] == '=>':
                                    # We confirm that this is a function, not tuple.
                                    could_be_tuple = False
                                    break

                            if not could_be_tuple:
                                # Skip to the opening curly brace '{'.
                                while i <= tracker['last_char_index'] and content[i] != '{':
                                    i += 1

                                # Track curly braces to extract the full implementation
                                saved_missing_closed_curly_brackets_func_body = tracker['missing_closed_curly_brackets']
                                function_start = tracker['potential_begin_function_index']  # Start of function
                                while i <= tracker['last_char_index']:
                                    if not is_inside_string():
                                        if content[i] == '{':
                                            tracker['missing_closed_curly_brackets'] += 1
                                        elif content[i] == '}':
                                            tracker['missing_closed_curly_brackets'] -= 1
                                            if tracker['missing_closed_curly_brackets'] == saved_missing_closed_curly_brackets_func_body:
                                                function_end = i + 1
                                                function_implementation = content[function_start:function_end]
                                                list_of_js_functions.append((function_signature, function_implementation))

                                                # Reset flags
                                                tracker['potential_begin_function_index'] = -1
                                                break
                                    i += 1
                                else:
                                    # Reset the flag:
                                    tracker['potential_begin_function_index'] = -1

                        else:
                            is_inside_string()

                            # Reset flags:
                            tracker['potential_begin_function_index'] = -1

                ## Handle cases:
                # function function_name(...) {...}
                # function* function_name(...) {...}
                # asyn function function_name(...) {...}
                elif content[i] == 'f' and i-1 != -1 and content[i-1].isspace() and i+9 < tracker['last_char_index'] and (content[i:i+9] == 'function ' or content[i:i+9] == 'function*'):
                    tracker['potential_begin_function_index'] = i

                    # Check to see if we have 'async' keyword before 'function', then we update the flag 'potential_begin_function_index' to include 'async':
                    j = i-1
                    while j > 4:
                        if content[j] == 'c' and content[j-4:j+1] == 'async' and (j-5 == -1 or content[j-5] in {'\n', ' '}):
                            tracker['potential_begin_function_index'] = j-4
                            break
                        elif content[j] != ' ':
                            break
                        j -= 1

                    # Skip past the "function " keyword
                    i += 9

                    # Detect the function name
                    func_name_start = None
                    func_name_end = None
                    while i <= tracker['last_char_index'] and (content[i] == ' ' or content[i] == '*'):
                        i += 1  # Skip spaces to get to the function name

                    # Iterate through each char in function name:
                    if i <= tracker['last_char_index'] and (content[i].isalpha() or content[i] == '_'):  # Function name start
                        func_name_start = i
                        while i <= tracker['last_char_index'] and (content[i].isalnum() or content[i] == '_'):
                            i += 1
                        func_name_end = i

                    function_name = content[func_name_start:func_name_end]

                    # Skip to the opening parenthesis '('
                    while i <= tracker['last_char_index'] and content[i] != '(':
                        i += 1

                    # Now we're at the start of the parameters list
                    param_start = i

                    # Track the parentheses to extract the full signature
                    saved_missing_closed_parentheses_inside_func_params = tracker['missing_closed_parentheses']
                    if content[i] == '(':
                        tracker['missing_closed_parentheses'] += 1

                    # Find the full function signature (including parameters)
                    while i <= tracker['last_char_index'] and tracker['missing_closed_parentheses'] > saved_missing_closed_parentheses_inside_func_params:
                        i += 1
                        if content[i] == '(':
                            tracker['missing_closed_parentheses'] += 1
                        elif content[i] == ')':
                            tracker['missing_closed_parentheses'] -= 1

                    # Function signature (ends after the closing ')')
                    func_signature_end = i + 1
                    function_signature = content[tracker['potential_begin_function_index']:func_signature_end]

                    # Skip to the opening curly brace '{'
                    while i <= tracker['last_char_index'] and content[i] != '{':
                        i += 1

                    ## About to step through the function body:
                    saved_missing_closed_curly_brackets_func_body = tracker['missing_closed_curly_brackets']
                    function_start = tracker['potential_begin_function_index']  # Start of function (from 'function')
                    # Check inside string before enters func body, after that, I don't care what inside the func body:
                    while i <= tracker['last_char_index']:
                        if not is_inside_string():
                            if content[i] == '{':
                                tracker['missing_closed_curly_brackets'] += 1
                            elif content[i] == '}':
                                tracker['missing_closed_curly_brackets'] -= 1
                                if tracker['missing_closed_curly_brackets'] == saved_missing_closed_curly_brackets_func_body:
                                    # We reached the end of the function
                                    function_end = i + 1
                                    function_implementation = content[function_start:function_end]
                                    list_of_js_functions.append((function_signature, function_implementation))

                                    # Reset flags:
                                    tracker['potential_begin_function_index'] = -1
                                    break
                        i += 1
                    else:
                        # Reset the flag:
                        tracker['potential_begin_function_index'] = -1
                            
                
                ## Handle cases: Anonymous functions:
                # random_string(function (...) {...})
                # random_string(function* (...) {...})
                # random_string(async function (...)) {...})
                # random_string((...) => {...})
                # random_string(async (...) => {...})
                # (function(...) {...})(...);
                # (async function(...) {...})(...);
                # (function* (...) {...})(...);
                # ((...) => {...})(...);
                elif i+9 < tracker['last_char_index'] and i-1 != -1 and content[i] == '(':
                    interested_open_parenthesis_index = i
                    is_confirmed_function = False
                    saved_missing_closed_parentheses_inside_func_call = tracker['missing_closed_parentheses'] # This will be use to indicate we exit the parentheses. In case, it is string(string(function(...))) 
                    tracker['missing_closed_parentheses'] += 1

                    # Capture the first word before '(':
                    # Note that if the 'word_end_index' == 'word_end_index', it means no word before '(' such as the case if it is '\n'
                    i -= 1
                    word_end_index = -1
                    word_start_index = -1
                    while i > -1 and content[i].isspace() and content[i] != '\n':
                        i -= 1 
                    else:
                        word_end_index = i
                    while i > -1 and (content[i].isalnum() or content[i] == '_'):
                        i -= 1
                    else:
                        word_start_index = i+1
                    
                    if word_start_index > word_end_index:
                        word_start_index = interested_open_parenthesis_index
                        word_end_index = interested_open_parenthesis_index

                    i = interested_open_parenthesis_index + 1

                    # Skip spaces forward after '(':
                    while i <= tracker['last_char_index'] and content[i] == ' ':
                        i += 1

                    # Detect 'function' or 'async' keywords or '(...)' pattern:
                    if i+8 < tracker['last_char_index'] and ((content[i:i+8] == 'function' and not content[i+8].isalpha()) or (content[i:i+5] == 'async' and not content[i+5].isalpha()) or content[i] == '('):
                        missing_arrow_indicator = False # This flag indicates we are looking for "=>" to confirm it is a function

                        # keyword 'fucntion' and 'async' garantee they are function:
                        if content[i:i+8] == 'function':
                            i += 8  # Skip 'function'
                            is_confirmed_function = True
                        elif content[i:i+5] == 'async':
                            i += 5  # Skip 'async'
                            is_confirmed_function = True
                        # We need to look for "=>" to confirm it's a function:
                        elif content[i] == '(':
                            missing_arrow_indicator = True

                        # Skip to the opening parenthesis '('. There could be spacing in between:
                        while i <= tracker['last_char_index'] and content[i] != '(':
                            i += 1

                        # Track parentheses to extract the full signature
                        saved_missing_closed_parentheses_inside_func_params = tracker['missing_closed_parentheses']
                        if content[i] == '(':
                            tracker['missing_closed_parentheses'] += 1

                        # Stepping inside the paratheses of function parameters:
                        param_start = i
                        while i <= tracker['last_char_index'] and tracker['missing_closed_parentheses'] > saved_missing_closed_parentheses_inside_func_params:
                            i += 1
                            # Assuming something, the parameters have string in it, so better have `is_inside_string()` here:
                            if not is_inside_string():
                                if content[i] == '(' and not is_inside_string():
                                    tracker['missing_closed_parentheses'] += 1
                                elif content[i] == ')' and not is_inside_string():
                                    tracker['missing_closed_parentheses'] -= 1

                        func_signature_end = i + 1
                        # For the function_signature, we want to include the first word before '(' since anonymous function doesn't have the name
                        function_signature = content[word_start_index:func_signature_end]

                        # Check for '=>' to confirm it is a function if `missing_arrow_indicator` sets true:
                        while missing_arrow_indicator and i <= tracker['last_char_index']:
                            i += 1
                            if (not content[i].isspace() and content [i:i+2] != '=>') or content[i] == '{':
                                # We confirm that this is just a tuple, not a function. No need to continue
                                i -= 1 # Move back one character
                                break
                            elif content[i:i+2] == '=>':
                                # We confirm that this is a function, not tuple.
                                is_confirmed_function = True
                                break

                        if is_confirmed_function:
                            # Skip to the opening curly brace '{'.
                            while i <= tracker['last_char_index'] and content[i] != '{':
                                i += 1

                            # Stepping through the function body:
                            saved_missing_closed_curly_brackets_func_body = tracker['missing_closed_curly_brackets']
                            while i <= tracker['last_char_index']:
                                if not is_inside_string():
                                    if content[i] == '{':
                                        tracker['missing_closed_curly_brackets'] += 1
                                    elif content[i] == '}':
                                        tracker['missing_closed_curly_brackets'] -= 1
                                    elif content[i] == '(':
                                        tracker['missing_closed_parentheses'] += 1
                                    elif content[i] == ')':
                                        tracker['missing_closed_parentheses'] -= 1

                                        if tracker['missing_closed_parentheses'] == saved_missing_closed_parentheses_inside_func_call:
                                            # if this condition below is true, we have a problem:
                                            if tracker['missing_closed_curly_brackets'] > saved_missing_closed_curly_brackets_func_body:
                                                break

                                            function_end = i + 1
                                            function_implementation = content[word_start_index:function_end]
                                            list_of_js_functions.append((function_signature, function_implementation))

                                            # Reset flags
                                            tracker['potential_begin_function_index'] = -1
                                            break
                                i += 1
                            else:
                                # Reset the flag:
                                tracker['potential_begin_function_index'] = -1
                    else:
                        i -= 1 # Prevent it from skipping a character.
                else:
                    pass

            i += 1
        return list_of_js_functions


    ##########################################
    ########### Helper Functions #############
    ##########################################
    def remove_comments(self, file_type, content):
        match file_type:
            case 'cpp' | 'c' | 'js':
                # Problem: The regex above have issue because it remove the characters in http link as well since it is "https://.../"
                # # Regular expression patterns to match C-style comments
                # block_comment_pattern = re.compile(r'/\*.*?\*/', re.DOTALL)
                # line_comment_pattern = re.compile(r'//.*?$' , re.MULTILINE)
                # # Remove block comments
                # content = re.sub(block_comment_pattern, '', content)
                # # Remove line comments
                # content = re.sub(line_comment_pattern, '', content)
                
                regex_patterns = re.compile(r'''((?:(?:^[ \t]*)?(?:\/\*[^*]*\*+(?:[^\/*][^*]*\*+)*\/(?:[ \t]*\r?\n(?=[ \t]*(?:\r?\n|\/\*|\/\/)))?|\/\/(?:[^\\]|\\(?:\r?\n)?)*?(?:\r?\n(?=[ \t]*(?:\r?\n|\/\*|\/\/))|(?=\r?\n))))+)|("(?:\\[\S\s]|[^"\\])*"|'(?:\\[\S\s]|[^'\\])*'|(?:\r?\n|[\S\s])[^\/"'\\\s]*)''', re.MULTILINE)
                content = re.sub(regex_patterns, r'\2', content)
            case 'py':
                # Pattern to match single-line comments
                single_line_comment_pattern = r'#.*' # .*: zero or more of any characters (EXCEPT end line terminator '\n')
                
                # Pattern to match multi-line strings/comments
                multi_line_comment_pattern = r'\'\'\'[\s\S]*?\'\'\'|\"\"\"[\s\S]*?\"\"\"'   # \s: white space char; \S: non-white space char; |: or;
                
                # First remove multi-line comments
                content = re.sub(multi_line_comment_pattern, '', content)
                
                # Then remove single-line comments
                content = re.sub(single_line_comment_pattern, '', content)
        
        return content

    def extract_functions_from_c_relatives(self, content):
        """
        Extract all functions from C relative languges: C, C++.
        
        Parameters:
        content (str): The content of the file as a string. The content must not contains any comments.
        
        Returns:
        list: A list of tuples where each tuple contains the function name and entire function implementation.
        """
        # TODO: Need to update the function to capture function signature instead of just function name because there could be overloading functions. C code doesn't support overloading, but C++ does.

        list_of_c_functions = []
        function_names = []

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
                'break', 'continue', 'return', 'goto'
            }
        
        i = 0
        while i < len(content):
            if parenthesis_count == 0:
                match = function_pattern.search(content, i)
                if match:
                    # Attempt to get the potential class name.
                    match_group = match.group(1)
                    # Break the content in match_group into words:
                    match_group_words = re.findall(r'\b[a-zA-Z0-9_]+\b', match_group) # Regex explain: matches whole words that consist of alphanumeric characters and underscores.
                    if match_group_words:
                        # The last word is a potential class name:
                        potential_class_name = match_group_words[-1]  # Get the last match as the function name
                    else:
                        potential_class_name = ''  # Set keyword to an empty string if no matches are found

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
                    if parenthesis_count == 0 and curly_bracket_count == 0 and potential_class_name:
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
                                # 'potential_class_name' is potential class name, if it match with the keywords in c language, then do not consider it as a function name:
                                if potential_class_name not in c_keywords():
                                    function_names.append(potential_class_name)
                                    list_of_c_functions.append((potential_class_name, function_implementation))
                                    i -= 1 #set i index to character before '}'
                                potential_class_name = ''
                        else:
                            potential_class_name = ''
                i += 1
        return list_of_c_functions

### End of class [ExtractFunctionFromFileContentHelper]

