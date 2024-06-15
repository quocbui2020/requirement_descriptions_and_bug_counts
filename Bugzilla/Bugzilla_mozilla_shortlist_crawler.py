import requests
from datetime import datetime
from prettytable import PrettyTable
from bs4 import BeautifulSoup
import logging
from logging import info
from time import strftime, localtime
import pyodbc
import traceback
import re
import time

# Connect to the database
conn = pyodbc.connect('DRIVER={ODBC Driver 18 for SQL Server};'
                        'SERVER=QUOCBUI\SQLEXPRESS;'
                        'DATABASE=ResearchDatasets;'
                        'LongAsMax=yes;'
                        'TrustServerCertificate=yes;'
                        'Trusted_Connection=yes;')

# Prepare the SQL queries:
insert_bugzilla_mozilla_shortlog_query = '''INSERT INTO [dbo].[Bugzilla_Mozilla_ShortLog]
            ([Hash_Id]
           ,[Commit_Title]
           ,[Bug_Ids]
           ,[Changeset_Links]
           ,[Mercurial_Type]
           ,[Is_Backed_Out_Commit]
           ,[Backed_Out_By]
           ,[Does_Required_Human_Inspection]
           ,[Inserted_On])
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())'''

create_bugzilla_error_log_query = '''INSERT INTO [dbo].[Bugzilla_Error_Log]
            ([ID]
           ,[Bug_ID]
           ,[Request_Url]
           ,[Error_Messages]
           ,[Detail_Error_Message]
           ,[Offset]
           ,[Limit]
           ,[Completed]
           ,[inserted_on])
        VALUES
            (NEWID(), ?, ?, ?, ?, ?, ?, 0, SYSUTCDATETIME())'''

