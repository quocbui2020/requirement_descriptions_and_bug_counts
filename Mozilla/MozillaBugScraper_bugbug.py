"""
Mozilla Bug Importer - Import bugs.json into SQL Server database

IMPORTANT: Before running this script, verify your Bug_Properties table has
the PRIMARY KEY on [Unique_ID] column (NOT on [Name] column).

To verify: Run verify_database.py
To fix if needed:
    ALTER TABLE [dbo].[Bug_Properties] DROP CONSTRAINT [PK_Bug_Properties];
    ALTER TABLE [dbo].[Bug_Properties] 
        ADD CONSTRAINT [PK_Bug_Properties] PRIMARY KEY CLUSTERED ([Unique_ID]);

Field Mappings (from bugs.json → SQL Server):
    id → ID
    summary → Bug_Title
    alias → Alias
    product → Product
    component → Component
    type → Type
    status → Status
    resolution → Resolution
    cf_last_resolved → Resolved_Comment_DateTime
    description → Bug_Description (or first comment if description is empty)
    cf_user_story → User_Story
    severity → Severity
    priority → Priority
    last_change_time → Last_Change_Time

Bug_Properties table stores these list fields (one row per value):
    regressions → Name='Regressions'
    regressed_by → Name='regressed_by'
    depends_on → Name='depend_on'
    blocks → Name='blocks'
"""

# from bugbug import bugzilla, db
# from bugbug import repository, db

# # Download the latest version if the data set if it is not already downloaded
# db.download(bugzilla.BUGS_DB)
# db.download(repository.COMMITS_DB)

######################################################
######################################################
######################################################

# Connection string - Update these values for your environment
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=localhost\\SQLEXPRESS;' \
           'DATABASE=MozillaDataSet2026;' \
           'Connection Timeout=300;' \
           'Login Timeout=300;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

import json
import pyodbc
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging
from tqdm import tqdm
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bug_import.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BugImporter:
    """Handles importing bugs from JSON file to SQL Server database."""
    
    def __init__(self, connection_string: str, batch_size: int = 1000):
        """
        Initialize the bug importer.
        
        Args:
            connection_string: SQL Server connection string
            batch_size: Number of records to process in each batch
        """
        self.connection_string = connection_string
        self.batch_size = batch_size
        self.connection = None
        self.cursor = None
        
    def connect(self):
        """Establish database connection."""
        try:
            self.connection = pyodbc.connect(self.connection_string)
            self.cursor = self.connection.cursor()
            logger.info("Database connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def disconnect(self):
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("Database connection closed")
    
    def parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """
        Parse ISO datetime string to datetime object.
        
        Args:
            dt_str: ISO format datetime string
            
        Returns:
            datetime object or None
        """
        if not dt_str or dt_str == "---":
            return None
        try:
            # Handle ISO format with 'Z' suffix
            if dt_str.endswith('Z'):
                dt_str = dt_str[:-1] + '+00:00'
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except Exception as e:
            logger.warning(f"Failed to parse datetime '{dt_str}': {e}")
            return None
    
    def extract_bug_data(self, bug: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract bug data for Bugs table.
        Matches field mappings from Bugzilla_mozilla.py
        
        Args:
            bug: Bug dictionary from JSON
            
        Returns:
            Dictionary with bug data for insertion
        """
        # Get bug description - try 'description' field first, then first comment
        # This matches the pattern in Bugzilla_mozilla.py
        bug_description = bug.get('description')
        if not bug_description or bug_description == "":
            # Fall back to first comment if description is empty
            if bug.get('comments') and len(bug['comments']) > 0:
                bug_description = bug['comments'][0].get('text') or bug['comments'][0].get('raw_text')
        
        # Convert empty string to None (matching Bugzilla_mozilla.py pattern)
        if bug_description == "":
            bug_description = None
        
        # Handle user_story - convert empty string to None
        user_story = bug.get('cf_user_story')
        if user_story == "":
            user_story = None
        
        # Handle alias - can be None, string, or list
        alias = bug.get('alias')
        if alias:
            if isinstance(alias, list):
                # Join list elements, filter out empty values
                alias = ', '.join(str(a) for a in alias if a) if alias else None
            else:
                alias = str(alias)
            # Truncate if needed
            if alias:
                alias = alias[:500]
        else:
            alias = None
        
        return {
            'ID': bug.get('id'),
            'Bug_Title': (bug.get('summary') or '')[:1000],
            'Alias': alias,
            'Product': (bug.get('product') or 'Unknown')[:100],
            'Component': (bug.get('component') or '')[:100],
            'Type': (bug.get('type') or 'defect')[:50],
            'Status': (bug.get('status') or '')[:50],
            'Resolution': (bug.get('resolution') or '')[:50],
            'Resolved_Comment_DateTime': self.parse_datetime(bug.get('cf_last_resolved')),
            'Bug_Description': bug_description,
            'User_Story': user_story,
            'Severity': (bug.get('severity') or '')[:100],
            'Priority': (bug.get('priority') or '')[:100],
            'Last_Change_Time': self.parse_datetime(bug.get('last_change_time')),
            'Inserted_On': datetime.now()
        }
    
    def extract_properties_data(self, bug: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract bug properties for Bug_Properties table.
        
        Args:
            bug: Bug dictionary from JSON
            
        Returns:
            List of dictionaries with property data for insertion
        """
        properties = []
        bug_id = bug.get('id')
        
        # Define the fields we want to extract
        property_fields = {
            'regressions': 'Regressions',
            'regressed_by': 'regressed_by',
            'depends_on': 'depend_on',
            'blocks': 'blocks'
        }
        
        for json_field, db_name in property_fields.items():
            values = bug.get(json_field, [])
            if values and isinstance(values, list):
                for value in values:
                    if value:  # Skip empty values
                        properties.append({
                            'Name': db_name,
                            'Bug_ID': bug_id,
                            'Value': str(value)
                        })
        
        return properties
    
    def insert_bug(self, bug_data: Dict[str, Any]) -> bool:
        """
        Insert a single bug into Bugs table.
        
        Args:
            bug_data: Dictionary with bug data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            sql = """
                INSERT INTO [dbo].[Bugs] (
                    [ID], [Bug_Title], [Alias], [Product], [Component], [Type],
                    [Status], [Resolution], [Resolved_Comment_DateTime], [Bug_Description],
                    [User_Story], [Severity], [Priority], [Last_Change_Time], [Inserted_On]
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            self.cursor.execute(sql, (
                bug_data['ID'],
                bug_data['Bug_Title'],
                bug_data['Alias'],
                bug_data['Product'],
                bug_data['Component'],
                bug_data['Type'],
                bug_data['Status'],
                bug_data['Resolution'],
                bug_data['Resolved_Comment_DateTime'],
                bug_data['Bug_Description'],
                bug_data['User_Story'],
                bug_data['Severity'],
                bug_data['Priority'],
                bug_data['Last_Change_Time'],
                bug_data['Inserted_On']
            ))
            return True
        except pyodbc.IntegrityError as e:
            if 'PRIMARY KEY' in str(e):
                logger.debug(f"Bug {bug_data['ID']} already exists, skipping...")
                return False
            else:
                logger.error(f"Integrity error inserting bug {bug_data['ID']}: {e}")
                raise
        except Exception as e:
            logger.error(f"Error inserting bug {bug_data['ID']}: {e}")
            raise
    
    def insert_properties(self, properties: List[Dict[str, Any]]) -> int:
        """
        Insert bug properties into Bug_Properties table.
        
        Args:
            properties: List of property dictionaries
            
        Returns:
            Number of properties inserted
        """
        if not properties:
            return 0
        
        inserted_count = 0
        sql = """
            INSERT INTO [dbo].[Bug_Properties] ([Name], [Bug_ID], [Value])
            VALUES (?, ?, ?)
        """
        
        for prop in properties:
            try:
                self.cursor.execute(sql, (
                    prop['Name'],
                    prop['Bug_ID'],
                    prop['Value']
                ))
                inserted_count += 1
            except pyodbc.IntegrityError as e:
                # Skip duplicates
                logger.debug(f"Property already exists: {prop}")
            except Exception as e:
                logger.error(f"Error inserting property {prop}: {e}")
                # Continue with other properties
        
        return inserted_count
    
    def count_lines(self, file_path: str) -> int:
        """
        Count the number of lines in a file efficiently.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Number of lines
        """
        logger.info("Counting total bugs in file...")
        count = 0
        with open(file_path, 'r', encoding='utf-8') as f:
            for _ in f:
                count += 1
        logger.info(f"Total bugs to process: {count}")
        return count
    
    def process_file(self, file_path: str, skip_existing: bool = True):
        """
        Process the bugs.json file line by line.
        
        Args:
            file_path: Path to bugs.json file
            skip_existing: If True, skip bugs that already exist in database
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        logger.info(f"Starting to process file: {file_path}")
        logger.info(f"File size: {os.path.getsize(file_path) / (1024**3):.2f} GB")
        
        # Count total lines for progress bar
        total_lines = self.count_lines(file_path)
        
        bugs_processed = 0
        bugs_inserted = 0
        bugs_skipped = 0
        properties_inserted = 0
        errors = 0
        
        batch_bugs = []
        batch_properties = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                with tqdm(total=total_lines, desc="Processing bugs") as pbar:
                    for line_num, line in enumerate(f, 1):
                        try:
                            # Parse JSON line
                            line = line.strip()
                            if not line:
                                continue
                            
                            bug = json.loads(line)
                            
                            # Extract bug data
                            bug_data = self.extract_bug_data(bug)
                            properties_data = self.extract_properties_data(bug)
                            
                            batch_bugs.append(bug_data)
                            batch_properties.extend(properties_data)
                            
                            # Process batch when it reaches batch_size
                            if len(batch_bugs) >= self.batch_size:
                                inserted, skipped, props = self._process_batch(
                                    batch_bugs, batch_properties, skip_existing
                                )
                                bugs_inserted += inserted
                                bugs_skipped += skipped
                                properties_inserted += props
                                
                                batch_bugs = []
                                batch_properties = []
                                
                                # Commit the transaction
                                self.connection.commit()
                                
                            bugs_processed += 1
                            pbar.update(1)
                            
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error at line {line_num}: {e}")
                            errors += 1
                        except Exception as e:
                            logger.error(f"Error processing line {line_num}: {e}")
                            errors += 1
                            # Rollback on error
                            self.connection.rollback()
                    
                    # Process remaining bugs in the last batch
                    if batch_bugs:
                        inserted, skipped, props = self._process_batch(
                            batch_bugs, batch_properties, skip_existing
                        )
                        bugs_inserted += inserted
                        bugs_skipped += skipped
                        properties_inserted += props
                        self.connection.commit()
        
        except Exception as e:
            logger.error(f"Critical error during file processing: {e}")
            self.connection.rollback()
            raise
        
        # Log summary
        logger.info("=" * 60)
        logger.info("Processing Summary:")
        logger.info(f"Total bugs processed: {bugs_processed}")
        logger.info(f"Bugs inserted: {bugs_inserted}")
        logger.info(f"Bugs skipped (already exist): {bugs_skipped}")
        logger.info(f"Properties inserted: {properties_inserted}")
        logger.info(f"Errors: {errors}")
        logger.info("=" * 60)
    
    def _process_batch(self, bugs: List[Dict], properties: List[Dict], skip_existing: bool) -> tuple:
        """
        Process a batch of bugs and properties.
        
        Args:
            bugs: List of bug data dictionaries
            properties: List of property data dictionaries
            skip_existing: If True, skip existing bugs
            
        Returns:
            Tuple of (inserted_count, skipped_count, properties_count)
        """
        inserted = 0
        skipped = 0
        props_inserted = 0
        
        for bug_data in bugs:
            success = self.insert_bug(bug_data)
            if success:
                inserted += 1
            else:
                skipped += 1
        
        # Only insert properties if we're not skipping existing bugs
        # or if we actually inserted new bugs
        if properties and inserted > 0:
            props_inserted = self.insert_properties(properties)
        
        return inserted, skipped, props_inserted


def main():
    """Main execution function."""
    
    # Configuration - Update these values for your environment
    CONNECTION_STRING = conn_str  # Use the connection string defined at the top
    BUGS_FILE = r'C:\Users\quocb\quocbui\Studies\research\GithubRepo\requirement_descriptions_and_bug_counts\Mozilla\data\bugs.json'
    BATCH_SIZE = 1000  # Adjust based on your system memory
    SKIP_EXISTING = True  # Set to False to retry all bugs
    
    logger.info("="*60)
    logger.info("Bug Import Configuration:")
    logger.info(f"File: {BUGS_FILE}")
    logger.info(f"Batch size: {BATCH_SIZE}")
    logger.info(f"Skip existing: {SKIP_EXISTING}")
    logger.info("="*60)
    
    # Create importer instance
    importer = BugImporter(CONNECTION_STRING, batch_size=BATCH_SIZE)
    
    try:
        # Connect to database
        importer.connect()
        
        # Process the file
        importer.process_file(BUGS_FILE, skip_existing=SKIP_EXISTING)
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise
    finally:
        # Always disconnect
        importer.disconnect()
    
    logger.info("Import process completed!")


if __name__ == "__main__":
    main()
