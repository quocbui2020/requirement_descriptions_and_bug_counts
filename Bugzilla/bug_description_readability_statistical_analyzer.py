import pyodbc
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Helpers.statistical_analyzer import StatisticalAnalysisHelper

# Connection string
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=QUOCBUI-PERSONA\\MSSQLSERVER01;' \
           'DATABASE=master;' \
           'Connection Timeout=300;' \
           'Login Timeout=300;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

class BugDescReadabilityStatisticalAnalyzer:
    def __init__(self, conn_str):
        self.conn_str = conn_str

    def fetch_readability_measures(self, description_version, readability_version):
        """
        Fetches readability measures from the database for statistical analysis.
        :return: A list of dictionaries containing bug IDs and their readability measures.
        """

        # This is the main query to fetch the data for statistical analysis
        # The query joins the Defect_Counts, Bug_Description_Readability, Bug_Details, and Clean_Bug_Description tables
        query = f"""
SELECT 
    dc.Defect_Count,
    bd.Resolved_Comment_Datetime,
    CASE 
        WHEN LEN(cbd.Clean_Description_1) = 0 AND LEN(cbd.Clean_Description_2) = 0 THEN 0 -- Avoid division by zero when both lengths are 0
        WHEN LEN(cbd.Clean_Description_1) = 0 THEN 100 -- If Clean_Description_1 is empty, the difference is 100%
        WHEN LEN(cbd.Clean_Description_2) = 0 THEN 100 -- If Clean_Description_2 is empty, the difference is 100%
        ELSE ABS(LEN(cbd.Clean_Description_1) - LEN(cbd.Clean_Description_2)) * 100.0 / NULLIF(LEN(cbd.Clean_Description_1), 0)
    END AS Character_Removal_Percentage,
    r.Bug_ID,
    r.Description_Version,
    r.Flesch_Kincaid_Reading_Ease,
    r.Flesch_Kincaid_Grade_Level,
    r.Gunning_Fog_Score,
    r.SMOG_Index,
    r.Coleman_Liau_Index,
    r.Automated_Readability_Index,
    r.Number_Of_Words,
    r.Number_Of_Complex_Words,
    r.Average_Grade_Level,
	r.Description_Length,
    COALESCE(r.Number_Of_Predicates, 0) as Number_Of_Predicates
FROM FireFixDB_v2.[dbo].Defect_Counts dc
INNER JOIN FireFixDB_v2.[dbo].Bug_Description_Readability r ON r.Bug_ID = dc.Enhancement_Ticket_ID
    AND Description_Version = '{description_version}'
INNER JOIN FireFixDB_v2.[dbo].Bug_Details bd ON bd.ID = r.Bug_ID
INNER JOIN FireFixDB_v2.[dbo].Clean_Bug_Description cbd ON cbd.Bug_ID = r.Bug_ID
WHERE 
    dc.[Version] = '{readability_version}' -- other version such as 'defect datetime fall between enhancement datetime + 6 months'
    --AND r.Number_Of_Words > 10
	--AND r.Number_Of_Predicates is not null
    /*
    AND (
        LEN(cbd.Clean_Description_1) = 0 AND LEN(cbd.Clean_Description_2) = 0 -- Special case for both being empty
        OR LEN(cbd.Clean_Description_1) = 0 -- Special case for Clean_Description_1 being empty
        OR LEN(cbd.Clean_Description_2) = 0 -- Special case for Clean_Description_2 being empty
        OR ABS(LEN(cbd.Clean_Description_1) - LEN(cbd.Clean_Description_2)) * 100.0 / NULLIF(LEN(cbd.Clean_Description_1), 0) <= 50 -- Removed records that have percentage_difference > 50 b/c the non-natural language components are too great
    )
    */

UNION

SELECT 
    dc.Defect_Count,
    bd.Resolved_Comment_Datetime,
    CASE 
        WHEN LEN(cbd.Clean_Description_1) = 0 AND LEN(cbd.Clean_Description_2) = 0 THEN 0 -- Avoid division by zero when both lengths are 0
        WHEN LEN(cbd.Clean_Description_1) = 0 THEN 100 -- If Clean_Description_1 is empty, the difference is 100%
        WHEN LEN(cbd.Clean_Description_2) = 0 THEN 100 -- If Clean_Description_2 is empty, the difference is 100%
        ELSE ABS(LEN(cbd.Clean_Description_1) - LEN(cbd.Clean_Description_2)) * 100.0 / NULLIF(LEN(cbd.Clean_Description_1), 0)
    END AS Character_Removal_Percentage,
    r.Bug_ID,
    r.Description_Version,
    r.Flesch_Kincaid_Reading_Ease,
    r.Flesch_Kincaid_Grade_Level,
    r.Gunning_Fog_Score,
    r.SMOG_Index,
    r.Coleman_Liau_Index,
    r.Automated_Readability_Index,
    r.Number_Of_Words,
    r.Number_Of_Complex_Words,
    r.Average_Grade_Level,
	r.Description_Length,
    COALESCE(r.Number_Of_Predicates, 0) as Number_Of_Predicates
FROM FireFixDB_v2.[dbo].Defect_Counts dc
INNER JOIN FixFox_v2.[dbo].Bug_Description_Readability r ON r.Bug_ID = dc.Enhancement_Ticket_ID
    AND Description_Version = '{description_version}'
INNER JOIN FixFox_v2.[dbo].Bug_Details bd ON bd.ID = r.Bug_ID
INNER JOIN FixFox_v2.[dbo].Clean_Bug_Description cbd ON cbd.Bug_ID = r.Bug_ID
WHERE 
    dc.[Version] = '{readability_version}' -- other version such as 'defect datetime fall between enhancement datetime + 6 months'
    --AND r.Number_Of_Words > 10
	--AND r.Number_Of_Predicates is not null
    /*
    AND (
        LEN(cbd.Clean_Description_1) = 0 AND LEN(cbd.Clean_Description_2) = 0 -- Special case for both being empty
        OR LEN(cbd.Clean_Description_1) = 0 -- Special case for Clean_Description_1 being empty
        OR LEN(cbd.Clean_Description_2) = 0 -- Special case for Clean_Description_2 being empty
        OR ABS(LEN(cbd.Clean_Description_1) - LEN(cbd.Clean_Description_2)) * 100.0 / NULLIF(LEN(cbd.Clean_Description_1), 0) <= 50 -- Removed records that have percentage_difference > 50 b/c the non-natural language components are too great
    )
    */
        """
        try:
            with pyodbc.connect(self.conn_str) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    results = cursor.fetchall()
                    return [{"Bug_ID": row.Bug_ID,
                            "Defect_Count": row.Defect_Count,
                            "Resolved_Comment_Datetime": row.Resolved_Comment_Datetime,
                            "Character_Removal_Percentage": row.Character_Removal_Percentage,
                            "Description_Version": row.Description_Version, 
                            "Flesch_Kincaid_Reading_Ease": row.Flesch_Kincaid_Reading_Ease,
                            "Flesch_Kincaid_Grade_Level": row.Flesch_Kincaid_Grade_Level,
                            "Gunning_Fog_Score": row.Gunning_Fog_Score,
                            "SMOG_Index": row.SMOG_Index,
                            "Coleman_Liau_Index": row.Coleman_Liau_Index,
                            "Automated_Readability_Index": row.Automated_Readability_Index,
                            "Number_Of_Words": row.Number_Of_Words,
                            "Number_Of_Complex_Words": row.Number_Of_Complex_Words,
                            "Average_Grade_Level": row.Average_Grade_Level,
                            "Description_Length": row.Description_Length,
                            "Number_Of_Predicates": row.Number_Of_Predicates} for row in results]
        except Exception as e:
            print(f"An error occurred: {e}")
            return []
        
#################################################
# Main function to run the script
#################################################
if __name__ == "__main__":
    processor = BugDescReadabilityStatisticalAnalyzer(conn_str)

    # Fetch the data from the database
    data = processor.fetch_readability_measures(
        description_version='2',  # Replace with your description version
        readability_version="defect datetime fall between enhancement datetime + 12 months"  # Replace with your readability version
    )

    statistical_analysis_helper = StatisticalAnalysisHelper(data)

    ## Calculate the correlation analysis
    # 'columns' variable below include only the features mentioned in the research paper "Measuring Requirement Quality to Predict Testability" + extra features (Character_Removal_Percentage):
    columns=[
            'Defect_Count',
            'Resolved_Comment_Datetime',
            'Character_Removal_Percentage',
            'Flesch_Kincaid_Reading_Ease',
            # 'Flesch_Kincaid_Grade_Level',
            'Coleman_Liau_Index',
            'Number_Of_Words',
            # 'Number_Of_Complex_Words',
            # 'Number_Of_Predicates',
            # 'Description_Length',
            #'Gunning_Fog_Score',
            # 'SMOG_Index',
            #'Automated_Readability_Index',
            #'Average_Grade_Level',
        ]
    correlation_matrix = statistical_analysis_helper.calculate_correlation_analysis(
        columns=columns,
        print_result=True,
        correlation_threshold=0.0 # Set to 0.0 to not drop any features
    )


    ## Perform Multiple Linear Regression:
    # 'independent_vars' variable below include only the features mentioned in the research paper "Measuring Requirement Quality to Predict Testability" + extra features (Character_Removal_Percentage):
    independent_vars=[
            'Resolved_Comment_Datetime',
            'Character_Removal_Percentage',
            'Flesch_Kincaid_Reading_Ease',
            # 'Flesch_Kincaid_Grade_Level',
            'Coleman_Liau_Index',
            'Number_Of_Words',
            # 'Number_Of_Complex_Words',
            # 'Number_Of_Predicates',
            # 'Description_Length',
        ]
    regression_results = statistical_analysis_helper.perform_multiple_linear_regression_full_data(
        dependent_var='Defect_Count',
        independent_vars=independent_vars
    )
    print("Correlation analysis completed.")
    
