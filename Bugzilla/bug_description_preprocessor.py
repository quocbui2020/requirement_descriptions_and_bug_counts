# bug_description_preprocessor.py: Preprocess and clean mozilla bug descriptions
import pyodbc
import bleach # For HTML tag removal
import json
import re

# Connection string
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=QUOCBUI-PERSONA\\MSSQLSERVER01;' \
           'DATABASE=ResearchDatasets;' \
           'Connection Timeout=300;' \
           'Login Timeout=300;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

class BugDescriptionProcessor:
    def __init__(self, conn_str):
        self.conn_str = conn_str

    def fetch_bug_details(self):
        query = """
        SELECT TOP 2 ID, [Description]
        FROM FixFox_v2.dbo.Bug_Details
        WHERE ID = '1891349'
        ORDER BY ID DESC;
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
    
    def save_clean_description(self, bug_id, clean_description):
        """
        Saves the cleaned bug description into the database.
        :param bug_id: The ID of the bug.
        :param clean_description: The cleaned bug description.
        """
        query = """
        INSERT INTO [FixFox_v2].[dbo].[Clean_Bug_Description] ([ID], [Clean_Description])
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
        Removes all non-English words from the given bug description.
        :param bug_description: The bug description to process.
        :return: The cleaned description containing only English words.
        """
        # Load the English words dictionary
        try:
            with open(r'C:\Users\quocb\Quoc Bui\Study\phd_in_cs\Research\first_paper\Code\r_to_b_mapping\repos\requirement_descriptions_and_bug_counts\Bugzilla\words_dictionary.json', 'r') as file:
                english_words = set(json.load(file).keys())
        except Exception as e:
            print(f"Error loading words dictionary: {e}")
            return bug_description  # Return the original description if dictionary fails to load

        # Tokenize the description into words
        words = re.findall(r'\b\w+\b', bug_description)

        # Filter out non-English words
        filtered_words = [word for word in words if word.lower() in english_words]

        # Join the filtered words back into a single string
        clean_description = ' '.join(filtered_words)
        return clean_description
    

#################################################
# Main function to fetch and clean bug descriptions
#################################################
if __name__ == "__main__":
    processor = BugDescriptionProcessor(conn_str)
    bug_details = processor.fetch_bug_details()
    for bug in bug_details:
        cleaned_HTMLtags_description = processor.remove_html_tags(bug["Description"])
        cleaned_description = processor.remove_non_english_words(cleaned_HTMLtags_description)
        processor.save_clean_description(bug["ID"], cleaned_description)