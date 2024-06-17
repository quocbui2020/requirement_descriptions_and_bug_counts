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
