import pyodbc
import sys
import os
import pandas as pd
import numpy as np #numpy-1.24.3 (Aim for data manipulation and numerical operations)
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
    rdb.[Priority],
	rdb.[Severity],
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
INNER JOIN [ResearchDatasets].[dbo].Bugzilla rdb on rdb.id = r.Bug_ID
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
    rdb.[Priority],
	rdb.[Severity],
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
INNER JOIN [ResearchDatasets].[dbo].Bugzilla rdb on rdb.id = r.Bug_ID
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
                            "Priority": row.Priority,
                            "Severity": row.Severity,
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

# if __name__ == "__main__":
#     processor = BugDescReadabilityStatisticalAnalyzer(conn_str)

#     # Quoc Fetch
#     ## Fetch the data from the database
#     data = processor.fetch_readability_measures(
#         description_version='2',  # Replace with your description version
#         readability_version="original"  # Replace with your readability version
#     )

#     df = pd.DataFrame(data)

#     ## Data overview
#     StatisticalAnalysisHelper.data_overview(df)

#     cleaned_df = StatisticalAnalysisHelper.clean_categorical_column_v1(
#         data=df,
#         column_name='Priority',
#         missing_values=['--'],  # Replace '--' with NaN
#         category_order=['P1', # Fix in the current release cycle
#                         'P2', # Fix in the next release cycle or the following (nightly + 1 or nightly + 2)
#                         'P3', # Backlog
#                         'P4', # Do not use. This priority is for the Web Platform Test bot.
#                         'P5'], # Will not fix, but will accept a patch
#         encoding='ordinal'  # Perform ordinal encoding (used for categories have a meaningful, ranked relationship)
#     )

#     severity_mapping = {
#         'blocker': 'S1',
#         'critical': 'S2',
#         'major': 'S2',
#         'minor': 'S3',
#         'normal': 'S3',
#         'trivial': 'S4',
#         'enhancement': np.nan,  # treat as missing
#         'S1': 'S1',
#         'S2': 'S2',
#         'S3': 'S3',
#         'S4': 'S4',
#         np.nan: np.nan
#     }
#     cleaned_df['Severity'] = cleaned_df['Severity'].str.lower()
#     cleaned_df['Severity_Mapped'] = cleaned_df['Severity'].map(severity_mapping)

#     cleaned_df = StatisticalAnalysisHelper.clean_categorical_column_v1(
#         data=cleaned_df,
#         column_name='Severity_Mapped',
#         missing_values=['N/A'],  # Optional: treat N/A as missing
#         category_order=['S4', 'S3', 'S2', 'S1'],
#         encoding='ordinal'
#     )

#     # Convert 'Resolved_Comment_Datetime' to UNIX timestamp in seconds
#     cleaned_df['Resolved_Comment_Datetime'] = pd.to_datetime(cleaned_df['Resolved_Comment_Datetime']).astype('int64') // 10**9

#     ## Calculate the correlation analysis
#     columns=[
#             'Defect_Count',
#             'Resolved_Comment_Datetime',
#             'Character_Removal_Percentage',
#             'Flesch_Kincaid_Reading_Ease',
#             'Coleman_Liau_Index',
#             'Number_Of_Words',
#             'Severity_Mapped',
#             'Priority'
#         ]
#     correlation_matrix = StatisticalAnalysisHelper.calculate_correlation_analysis(
#         data=cleaned_df,
#         column_list=columns,
#         print_result=True,
#         correlation_threshold=0.0 # Set to 0.0 to not drop any features
#     )

#     independent_vars_columns=[
#         'Resolved_Comment_Datetime',
#         'Character_Removal_Percentage',
#         'Flesch_Kincaid_Reading_Ease',
#         'Coleman_Liau_Index',
#         'Number_Of_Words',
#         'Severity_Mapped',
#         'Priority'
#     ]

#     ## Poisson regression
#     print("Performing Poisson Regression...")
#     poisson_model = StatisticalAnalysisHelper.perform_poisson_regression(
#         df=cleaned_df,
#         dependent_var='Defect_Count',
#         independent_vars=independent_vars_columns
#     )


#     ## ANCOVA
#     print("Performing ANCOVA...")
#     ancova_model = StatisticalAnalysisHelper.perform_ANCOVA(
#         df=cleaned_df,
#         dependent_var='Defect_Count',
#         independent_vars=independent_vars_columns
#     )

#     ## ANCOVA 2
#     print("Performing ANCOVA 2...")
#     # 1️⃣ Create ANCOVA-specific columns without overwriting originals
#     cleaned_df['Severity_Mapped_For_ANCOVA'] = cleaned_df['Severity_Mapped'].replace('N/A', np.nan)
#     cleaned_df['Priority_For_ANCOVA'] = cleaned_df['Priority'].replace('--', np.nan)

#     # 2️⃣ Convert to ordered categorical for ANCOVA
#     cleaned_df['Severity_Mapped_For_ANCOVA'] = pd.Categorical(
#         cleaned_df['Severity_Mapped_For_ANCOVA'],
#         categories=['S4', 'S3', 'S2', 'S1'],
#         ordered=True
#     )

#     cleaned_df['Priority_For_ANCOVA'] = pd.Categorical(
#         cleaned_df['Priority_For_ANCOVA'],
#         categories=['P1', 'P2', 'P3', 'P4', 'P5'],
#         ordered=True
#     )

#     # 3️⃣ Convert covariates to numeric
#     covariates = [
#         "Character_Removal_Percentage",
#         "Flesch_Kincaid_Reading_Ease",
#         "Coleman_Liau_Index",
#         "Number_Of_Words"
#     ]

#     for col in covariates:
#         # Convert Decimal to float
#         cleaned_df[col] = pd.to_numeric(cleaned_df[col], errors='coerce')

#     # 4️⃣ Drop rows with missing data in DV, covariates, or factors
#     df_ancova = cleaned_df.dropna(subset=[
#         "Defect_Count",
#         *covariates,
#         "Severity_Mapped_For_ANCOVA",
#         "Priority_For_ANCOVA"
#     ])

#     print("Rows left for ANCOVA:", df_ancova.shape[0])
#     if df_ancova.shape[0] == 0:
#         raise ValueError("No rows left for ANCOVA after cleaning. Check factor and covariate values.")

#     # 5️⃣ Run ANCOVA
#     factors = ["Severity_Mapped_For_ANCOVA", "Priority_For_ANCOVA"]

#     model, anova_table = StatisticalAnalysisHelper.perform_ANCOVA2(
#         df=df_ancova,
#         dependent_var="Defect_Count",
#         covariates=covariates,
#         factors=factors,
#         output_file="ancova_results.txt"  # optional
#     )

#     # 6️⃣ Print ANOVA table to console
#     print("\n=== ANCOVA Table ===")
#     print(anova_table.to_string())

#     # ## Perform Multiple Linear Regression:
#     # # 'independent_vars' variable below include only the features mentioned in the research paper "Measuring Requirement Quality to Predict Testability" + extra features (Character_Removal_Percentage):
#     # independent_vars=[
#     #         'Resolved_Comment_Datetime',
#     #         'Character_Removal_Percentage',
#     #         'Flesch_Kincaid_Reading_Ease',
#     #         # 'Flesch_Kincaid_Grade_Level',
#     #         'Coleman_Liau_Index',
#     #         'Number_Of_Words',
#     #         # 'Number_Of_Complex_Words',
#     #         # 'Number_Of_Predicates',
#     #         # 'Description_Length',
#     #     ]
#     # regression_results = statistical_analysis_helper.perform_multiple_linear_regression_full_data(
#     #     dependent_var='Defect_Count',
#     #     independent_vars=independent_vars
#     # )
#     # print("Correlation analysis completed.")
    
#     print("Finished.")

# https://chatgpt.com/c/68cb6023-9df8-8329-90b3-fc5f884c7ec9
if __name__ == "__main__":
    processor = BugDescReadabilityStatisticalAnalyzer(conn_str)

    ## Fetch the data from the database
    data = processor.fetch_readability_measures(
        description_version='2',  # Replace with your description version
        readability_version="original"  # Replace with your readability version
    )

    # 1️⃣ Fetch data
    df = pd.DataFrame(data)

    # 2️⃣ Clean categorical variables (Priority & Severity)
    severity_mapping = {
        'blocker': 'S1',
        'critical': 'S2',
        'major': 'S2',
        'minor': 'S3',
        'normal': 'S3',
        'trivial': 'S4',
        'enhancement': np.nan,  # treat as missing
        'S1': 'S1',
        'S2': 'S2',
        'S3': 'S3',
        'S4': 'S4',
        np.nan: np.nan
    }

    # Normalize Severity → ensure lowercase before mapping
    df['Severity_Mapped_For_ANCOVA'] = (
        df['Severity']
        .astype(str)  # ensure string
        .str.lower()
        .map(severity_mapping)
    )

    valid_priorities = ['P1', 'P2', 'P3', 'P4', 'P5']
    df['Priority_For_ANCOVA'] = df['Priority'].where(df['Priority'].isin(valid_priorities), np.nan)

    # Convert to categorical (ordered for ANCOVA)
    df['Severity_Mapped_For_ANCOVA'] = pd.Categorical(
        df['Severity_Mapped_For_ANCOVA'],
        categories=['S4', 'S3', 'S2', 'S1'],
        ordered=True
    )

    df['Priority_For_ANCOVA'] = pd.Categorical(
        df['Priority_For_ANCOVA'],
        categories=['P1', 'P2', 'P3', 'P4', 'P5'],
        ordered=True
    )

    # Step 1: Parse string to datetime (if not already datetime)
    df['Resolved_Comment_Datetime'] = pd.to_datetime(
        df['Resolved_Comment_Datetime'], errors='coerce'
    )

    # Step 2: Convert datetime to numeric (seconds since epoch)
    df['Resolved_Timestamp'] = df['Resolved_Comment_Datetime'].astype('int64') // 10**9


    # 3️⃣ Convert covariates to numeric
    covariates = [
        "Resolved_Timestamp",
        "Character_Removal_Percentage",
        "Flesch_Kincaid_Reading_Ease",
        "Coleman_Liau_Index",
        "Number_Of_Words"
    ]
    for col in covariates:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # 5️⃣ Poisson Regression
    print("\n=== Poisson Regression ===")
    poisson_model = StatisticalAnalysisHelper.perform_poisson_regression(
        df, "Defect_Count", covariates
    )
    print(poisson_model.summary())

    # 6️⃣ ANCOVA — drop rows with missing DV, covariates, or factors
    df_ancova = df.dropna(subset=["Defect_Count", *covariates,
                                  "Severity_Mapped_For_ANCOVA", "Priority_For_ANCOVA"])

    print("\nRows left for ANCOVA:", df_ancova.shape[0])
    if df_ancova.shape[0] == 0:
        raise ValueError("No rows left for ANCOVA after cleaning. Check factor and covariate values.")

    # Run ANCOVA
    print("\n=== ANCOVA Results ===")
    model, anova_table = StatisticalAnalysisHelper.perform_ANCOVA2(
        df=df_ancova,
        dependent_var="Defect_Count",
        covariates=covariates,
        factors=["Severity_Mapped_For_ANCOVA", "Priority_For_ANCOVA"],
        output_file="ancova_results.txt"
    )

    print(anova_table.to_string())

    print("Finished.")