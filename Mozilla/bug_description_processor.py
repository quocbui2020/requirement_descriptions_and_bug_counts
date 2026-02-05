# bug_description_preprocessor.py: Preprocess, clean, and compute readability scores in mozilla bug descriptions
# [Clean_Description_1]: Descriptions without HTML tags and links
# [Clean_Description_2]: Descriptions without HTML tags, links, and non-English words and punctuation marks except for commas and periods

import pyodbc
import bleach # For HTML tag removal
import json
import re
from time import strftime, localtime
import sys
import os
import spacy # For extracting predicates
import argparse
from collections import Counter
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Helpers.read_able_dot_com import ReadAbleDotComHelper

# Connection string
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=QUOCBUI-PERSONA\\MSSQLSERVER01;' \
           'DATABASE=master;' \
           'Connection Timeout=300;' \
           'Login Timeout=300;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

class BugDescriptionProcessor:
    def __init__(self, conn_str):
        self.conn_str = conn_str

    def fetch_bug_description_original(self, database_name):
        query = f"""
        SELECT
            [ID]
            ,[Description]
        FROM [{database_name}].[dbo].[Bug_Details]
        WHERE [Description] IS NOT NULL
        ORDER BY [ID] DESC;
        """
        try:
            with pyodbc.connect(self.conn_str) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    results = cursor.fetchall()
                    return [{"ID": row.ID, "Description": row.Description} for row in results]
        except Exception as e:
            print(f"An error occurred: {e}")
            return []

    def remove_html_tags(self, description):
        """
        Removes all HTML tags from the given bug description using bleach.
        :param description: The bug description containing HTML tags.
        :return: The cleaned description without HTML tags.
        """
        clean_description = bleach.clean(description, tags=[], strip=True)
        return clean_description
    
    def remove_html_tags_and_links(self, description):
        """
        Removes all HTML tags and links from the given bug description.
        :param description: The bug description containing HTML tags and links.
        :return: The cleaned description without HTML tags and links.
        """
        # Remove all HTML tags
        no_html = bleach.clean(description, tags=[], strip=True)
        # Remove URLs using regex
        clean_description = re.sub(r'http[s]?://\S+', '', no_html)
        return clean_description
    
    def save_clean_description_1(self, bug_id, clean_description, datanbase_name):
        """
        Saves the cleaned bug description into the database.
        :param bug_id: The ID of the bug.
        :param clean_description: The cleaned bug description.

        [Clean_Description_1]: Descriptions without HTML tags and links
        """
        query = f"""
        INSERT INTO [{datanbase_name}].[dbo].[Clean_Bug_Description] ([Bug_ID], [Clean_Description_1])
        VALUES (?, ?)
        """
        try:
            with pyodbc.connect(self.conn_str) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (bug_id, clean_description))
                    conn.commit()
        except Exception as e:
            print(f"An error occurred while saving the clean description: {e}")
    
    def remove_non_english_words(self, bug_description):
        """
        Removes all non-English words from the given bug description while keeping only commas and periods as punctuation marks.
        :param bug_description: The bug description to process.
        :return: The cleaned description containing only English words, commas, and periods.
        """
        # Load the English words dictionary
        try:
            with open(r'C:\Users\quocb\Quoc Bui\Study\phd_in_cs\Research\first_paper\Code\r_to_b_mapping\repos\requirement_descriptions_and_bug_counts\Bugzilla\words_dictionary.json', 'r') as file:
                english_words = set(json.load(file).keys())
        except Exception as e:
            print(f"Error loading words dictionary: {e}")
            return bug_description  # Return the original description if dictionary fails to load

        # Tokenize the description into words and punctuation
        tokens = re.findall(r'\b\w+\b|[^\w\s]', bug_description)
        
        # Filter out non-English words, keeping only commas and periods as punctuation marks
        filtered_tokens = [
            token for token in tokens 
            if (token.isalpha() and token.lower() in english_words) or token in {',', '.'}
        ]

        # Join the filtered tokens back into a single string
        clean_description = ''.join(
            token if token in {',', '.'} else f' {token}' for token in filtered_tokens
        ).strip()
        return clean_description
    
    def fetch_clean_description_1(self, database_name):
        """
        Fetches bug descriptions from the database with [Clean_Description_1].
        :return: A list of dictionaries containing bug IDs and their cleaned descriptions.
        """
        query = f"""
        SELECT
            d.[Bug_ID]
            ,d.[Clean_Description_1]
            ,r.[Description_Version]
        FROM [{database_name}].[dbo].[Clean_Bug_Description] d
        LEFT JOIN [{database_name}].[dbo].[Bug_Description_Readability] r ON r.[Bug_ID] = d.[Bug_ID]
            AND r.[Description_Version] = '1'
        WHERE r.[Description_Version] IS NULL -- Eliminate the records that already have readability measures
        ORDER BY d.[Bug_ID] DESC;
        """
        try:
            with pyodbc.connect(self.conn_str) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    results = cursor.fetchall()
                    return [{"Bug_ID": row.Bug_ID, "Clean_Description_1": row.Clean_Description_1, "Description_Version": row.Description_Version} for row in results]
        except Exception as e:
            print(f"An error occurred: {e}")
            return []
        
    def fetch_clean_description_2(self, database_name, where_clause=None):
        """
        Fetches bug descriptions from the database with [Clean_Description_2].
        :return: A list of dictionaries containing bug IDs and their cleaned descriptions.
        """
        query = f"""
        SELECT
            d.[Bug_ID]
            ,d.[Clean_Description_2]
            ,r.[Description_Version]
        FROM [{database_name}].[dbo].[Clean_Bug_Description] d
        Inner JOIN [{database_name}].[dbo].[Bug_Details] b ON d.[Bug_ID] = b.[ID]
        LEFT JOIN [{database_name}].[dbo].[Bug_Description_Readability] r ON r.[Bug_ID] = d.[Bug_ID]
            AND r.[Description_Version] = '2'
        WHERE {where_clause if where_clause else '1=1'} -- Eliminate the records that already processed
        ORDER BY d.[Bug_ID] DESC;
        """
        try:
            with pyodbc.connect(self.conn_str) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    results = cursor.fetchall()
                    return [{"Bug_ID": row.Bug_ID, "Clean_Description_2": row.Clean_Description_2, "Description_Version": row.Description_Version} for row in results]
        except Exception as e:
            print(f"An error occurred: {e}")
            return []

    def save_clean_description_2(self, bug_id, clean_description, database_name):
        """
        Updates the cleaned bug description [Clean_Description_2] in the database.
        :param bug_id: The ID of the bug.
        :param clean_description: The cleaned bug description.

        [Clean_Description_2]: Descriptions without HTML tags, links, and non-English words and punctuation marks except for commas and periods
        """
        query = f"""
        UPDATE [{database_name}].[dbo].[Clean_Bug_Description]
        SET [Clean_Description_2] = ?
        WHERE [Bug_ID] = ?
        """
        try:
            with pyodbc.connect(self.conn_str) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (clean_description, bug_id))
                    conn.commit()
        except Exception as e:
            print(f"An error occurred while saving the clean description: {e}")

    def compute_readability_scores(self, clean_description):
        # Compute readability scores using ReadAbleDotComHelper
        try:
            readable_helper = ReadAbleDotComHelper()
            request_content = readable_helper.post_url_readable_tool(text=clean_description)
            if request_content:
                # Extract the result list from the response
                readability_scores = readable_helper.extract_readability_values(byte_content=request_content)
                return readability_scores
        except Exception as e:
            print(f"An error occurred while computing readability scores: {e}")

    def save_readability_measures_to_db(self, database_name, bug_id, description_version, readability_scores):
        try:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()
            
            # Extract values from the result list
            flesch_kincaid_reading_ease = float(readability_scores[0])
            flesch_kincaid_grade_level = float(readability_scores[1])
            gunning_fog_score = float(readability_scores[2])
            smog_index = float(readability_scores[3])
            coleman_liau_index = float(readability_scores[4])
            automated_readability_index = float(readability_scores[5])
            number_of_words = int(readability_scores[7])
            number_of_complex_words = int(readability_scores[8])
            
            # Calculate average grade level
            average_grade_level = (
                flesch_kincaid_grade_level + 
                coleman_liau_index + 
                smog_index + 
                automated_readability_index + 
                gunning_fog_score
            ) / 5.0

            save_query = f"""
            INSERT INTO [{database_name}].[dbo].[Bug_Description_Readability]
                ([Bug_ID]
                ,[Description_Version]
                ,[Flesch_Kincaid_Reading_Ease]
                ,[Flesch_Kincaid_Grade_Level]
                ,[Gunning_Fog_Score]
                ,[SMOG_Index]
                ,[Coleman_Liau_Index]
                ,[Automated_Readability_Index]
                ,[Number_Of_Words]
                ,[Number_Of_Complex_Words]
                ,[Average_Grade_Level]
                ,[Number_Of_Predicates])
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            
            # Insert the values into the database
            cursor.execute(save_query, 
                        bug_id, description_version, flesch_kincaid_reading_ease, flesch_kincaid_grade_level, gunning_fog_score, 
                        smog_index, coleman_liau_index, automated_readability_index, number_of_words, 
                        number_of_complex_words, average_grade_level, None)

            # Commit the transaction
            conn.commit()
            
        except pyodbc.Error as e:
            print(f"Database error: {e}")
        finally:
            # Close the cursor and connection
            cursor.close()
            conn.close()

    def extract_predicates(self, text):
        nlp = spacy.load('en_core_web_md')
        # Process the text
        doc = nlp(text)
        predicates = []

        for sent in doc.sents:
            subject = ""
            predicate = ""
            for token in sent:
                if token.dep_ == 'nsubj':
                    subject = token.text
                    predicate = ' '.join([tok.text for tok in token.head.subtree if tok.dep_ != 'nsubj'])
                    break
            if predicate:
                predicates.append((subject, predicate))

        return predicates

    # count_predicates: count number of predicates.
    def count_predicates(self, predicates):
        # Extract just the predicates from the subject-predicate pairs
        predicate_list = [predicate for subject, predicate in predicates]
        # Use Counter to count the occurrences of each predicate
        predicate_counts = Counter(predicate_list)
        # Return the number of unique predicates
        num_of_predicates = len(predicate_counts)
        return num_of_predicates

    def save_num_of_predicates_to_db(self, database_name, bug_id, description_version, number_of_predicate):
        """
        Updates the number of predicates in the database.
        :param bug_id: The ID of the bug.
        :param description_version: The version of the description.
        :param number_of_predicate: The number of predicates extracted from the description.
        """
        query = f"""
        UPDATE [{database_name}].[dbo].[Bug_Description_Readability]
        SET [Number_Of_Predicates] = ?
        WHERE [Bug_ID] = ? AND [Description_Version] = ?
        """
        try:
            with pyodbc.connect(self.conn_str) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (number_of_predicate, bug_id, description_version))
                    conn.commit()
        except Exception as e:
            print(f"An error occurred while saving the number of predicates: {e}")

#################################################
# Main function to fetch and clean bug descriptions
#################################################
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="")
    parser.add_argument('arg_1', type=str, help='Argument 1')
    parser.add_argument('arg_2', type=str, help='Argument 2')
    args = parser.parse_args()
    arg_1 = args.arg_1
    arg_2 = args.arg_2

    processor = BugDescriptionProcessor(conn_str)

    ## Steps to create [Clean_Description_1]
    # bug_details = processor.fetch_bug_description_original("FireFixDB_v2")
    # total_records = len(bug_details)
    # for bug in bug_details:
    #     print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}]({total_records}) Processing Bug ID: {bug['ID']}...", end="", flush=True)
    #     # Clean the bug description by removing HTML tags and links:
    #     clean_HTMLtags_description = processor.remove_html_tags_and_links(bug["Description"])
    #     processor.save_clean_description_1(bug["ID"], clean_HTMLtags_description, "FireFixDB_v2")
    #     total_records -= 1
    #     print(" Done.")


    ## Steps to create [Clean_Description_2]
    # bug_details = processor.fetch_clean_description_1("FireFixDB_v2")
    # total_records = len(bug_details)
    # for bug in bug_details:
    #     print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}]({total_records}) Processing Bug ID: {bug['Bug_ID']}...", end="", flush=True)
    #     ultimate_clean_description = processor.remove_non_english_words(bug["Clean_Description_1"])
    #     processor.save_clean_description_2(bug["Bug_ID"], ultimate_clean_description, "FireFixDB_v2")
    #     total_records -= 1
    #     print(" Done.")

    ## Compute readability scores for [Clean_Description_1]
    # clean_description_1_list = processor.fetch_clean_description_1("FireFixDB_v2")
    # total_records = len(clean_description_1_list)
    # for record in clean_description_1_list:
    #     print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}]({total_records}) Processing Bug ID: {record['Bug_ID']}...", end="", flush=True)
    #     readability_scores = processor.compute_readability_scores(record["Clean_Description_1"])
    #     if readability_scores:
    #         processor.save_readability_measures_to_db("FireFixDB_v2", record["Bug_ID"], "1", readability_scores)
    #         print(" Done.")
    #     else:
    #         print(" Failed to compute readability scores.")
    #     total_records -= 1

    ## Compute readability scores for [Clean_Description_2] -- Currently running
    # clean_description_2_list = processor.fetch_clean_description_2(
    #     database_name="FireFixDB_v2",
    #     # r.[Description_Version] is null: # Eliminate the records that already have readability measures (already processed)
    #     # d.[Clean_Description_2] is not null: # Eliminate the records that have null [Clean_Description_2] b/c we can't compute readability scores for empty descriptions
    #     where_clause=f"(d.[Clean_Description_2] is not null AND d.[Clean_Description_2] <> '') AND r.[Description_Version] is null AND b.[Type] <> 'defect'")
    # total_records = len(clean_description_2_list)
    # for record in clean_description_2_list:
    #     print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}]({total_records}) Processing Bug ID: {record['Bug_ID']}...", end="", flush=True)
    #     readability_scores = processor.compute_readability_scores(record["Clean_Description_2"])
    #     if readability_scores:
    #         processor.save_readability_measures_to_db("FireFixDB_v2", record["Bug_ID"], "2", readability_scores)
    #         print(" Done.")
    #     else:
    #         print(" Failed to compute readability scores.")
    #     total_records -= 1

    ## Compute number of predicates for [Clean_Description_2]:
    # clean_description_2_list = processor.fetch_clean_description_2(
    #     database_name="FireFixDB_v2",
    #     where_clause=f"d.Bug_ID between '{arg_1}' and '{arg_2}' AND r.[Number_Of_Predicates] is null AND (d.[Clean_Description_2] is not null AND d.[Clean_Description_2] <> '') AND b.[Type] <> 'defect'")
    # total_records = len(clean_description_2_list)
    # for record in clean_description_2_list:
    #     print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}]({total_records}) Processing Bug ID: {record['Bug_ID']}...", end="", flush=True)
    #     predicates = processor.extract_predicates(record["Clean_Description_2"])
    #     num_of_predicates = processor.count_predicates(predicates)
    #     if num_of_predicates:
    #         processor.save_num_of_predicates_to_db("FireFixDB_v2", record["Bug_ID"], "2", num_of_predicates)
    #         print(" Done.")
    #     else:
    #         print(" Failed to compute readability scores.")
    #     total_records -= 1
    

print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] PROGRAM FINISHED. EXIT!")

# TODO:
# After running Compute readability scores for [Clean_Description_2] for "FireFixDB_v2", then run Compute readability scores for [Clean_Description_1] as well.