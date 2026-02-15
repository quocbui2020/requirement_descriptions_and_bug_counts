"""
Mozilla Bug Scraper using Bugzilla REST API - Robust Overnight Mode

Scrapes ALL bugs directly from Bugzilla REST API (no filtering like bugbug) and stores in:
- [Bugs] table: Main bug information
- [Bug_Properties] table: List fields (regressions, regressed_by, depends_on, blocks)

ROBUST FEATURES FOR OVERNIGHT SCRAPING:
- Progressive retry with optimized backoff (5 attempts per batch)
- Faster sleep times: 15s -> 30s -> 45s -> 60s -> 75s (non-connection errors)
- Auto-halves batch limit on EVERY failure (1000 -> 500 -> 250 -> 125 -> 62 -> 50 min)
- Auto-resets batch limit to original value on success
- Continues scraping even after failed batches (skips and logs)
- Stops only after 10 consecutive failures
- Automatic commit after each batch
- Checkpoint logging every 10 batches
- Fast delay between successful batches (default: 1s, configurable)
- **Auto-resume**: START_OFFSET automatically set from database bug count

TYPICAL RUNTIME (OPTIMIZED):
- ~1.76M bugs total
- ~1000 bugs per batch
- ~1760 batches needed
- With 1s delay: ~30 minutes minimum
- With retries/delays: 1-2 hours estimated

AUTO-RESUME:
- START_OFFSET is automatically retrieved from database (SELECT COUNT(*) FROM [Bugs])
- Simply restart the script and it will resume where it left off
- No manual offset configuration needed!
"""

import requests
import pyodbc
from datetime import datetime
from typing import Dict, List, Any, Optional
from time import strftime, localtime
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bugzilla_api_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Connection string - Update these values for your environment
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=localhost\\SQLEXPRESS;' \
           'DATABASE=MozillaDataSet2026;' \
           'Connection Timeout=300;' \
           'Login Timeout=300;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'


class BugzillaAPIScraper:
    """Scrapes bugs from Bugzilla REST API and stores in SQL Server."""
    
    def __init__(self, connection_string: str, batch_limit: int = 1000):
        """
        Initialize the scraper.
        
        Args:
            connection_string: SQL Server connection string
            batch_limit: Number of bugs to fetch per API call (max 1000-1200)
        """
        self.connection_string = connection_string
        self.batch_limit = batch_limit
        self.original_batch_limit = batch_limit  # Store original to reset on success
        self.connection = None
        self.cursor = None
        
        # Bugzilla API base URL
        self.base_url = "https://bugzilla.mozilla.org/rest/bug"
        
        # Fields needed for Bugs table and Bug_Properties table
        self.include_fields = [
            'id',                    # Bug ID
            'summary',               # Bug_Title
            'alias',                 # Alias
            'product',               # Product
            'component',             # Component
            'type',                  # Type
            'status',                # Status
            'resolution',            # Resolution
            'cf_last_resolved',      # Resolved_Comment_DateTime
            'description',           # Bug_Description
            'cf_user_story',         # User_Story
            'severity',              # Severity
            'priority',              # Priority
            'last_change_time',      # Last_Change_Time
            'regressions',           # Bug_Properties
            'regressed_by',          # Bug_Properties
            'depends_on',            # Bug_Properties
            'blocks'                 # Bug_Properties
        ]
        
        # SQL queries
        self.insert_bug_query = """
            INSERT INTO [dbo].[Bugs] (
                [ID], [Bug_Title], [Alias], [Product], [Component], [Type],
                [Status], [Resolution], [Resolved_Comment_DateTime], [Bug_Description],
                [User_Story], [Severity], [Priority], [Last_Change_Time], [Inserted_On]
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        self.insert_property_query = """
            INSERT INTO [dbo].[Bug_Properties] ([Name], [Bug_ID], [Value])
            VALUES (?, ?, ?)
        """
    
    def connect(self):
        """Establish database connection."""
        try:
            self.connection = pyodbc.connect(self.connection_string)
            self.cursor = self.connection.cursor()
            logger.info("Database connection established")
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
    
    def build_api_url(self, offset: int) -> str:
        """
        Build Bugzilla API URL with pagination and field filters.
        
        Args:
            offset: Starting position for pagination
            
        Returns:
            Complete API URL
        """
        fields = ','.join(self.include_fields)
        url = (
            f"{self.base_url}?"
            f"offset={offset}&"
            f"limit={self.batch_limit}&"
            f"order=bug_id ASC&"
            f"bug_id_type=nowords&"
            f"bug_id=0&"
            f"include_fields={fields}"
        )
        return url
    
    def fetch_bugs_batch(self, offset: int, retry_count: int = 5) -> List[Dict]:
        """
        Fetch a batch of bugs from Bugzilla API with infinite retry logic.
        Uses a local batch limit that's reduced on failures without modifying self.batch_limit.
        NEVER GIVES UP - will retry indefinitely with 600s wait after each 5 attempts.
        
        Args:
            offset: Starting position for pagination
            retry_count: Number of retries before long wait (default: 5)
            
        Returns:
            List of bug dictionaries (never returns None, retries until success)
        """
        # Headers to identify the client
        headers = {
            'User-Agent': 'Mozilla Bug Research Scraper/1.0 (Educational Research)',
            'Accept': 'application/json'
        }
        
        # Use local batch limit for this fetch (don't modify self.batch_limit)
        current_limit = self.batch_limit
        retry_cycle = 1  # Track which 5-attempt cycle we're on
        
        while True:  # INFINITE RETRY - never give up!
            for attempt in range(retry_count):
                try:
                    # Build URL with current limit (may be reduced from previous attempts)
                    url = (
                        f"{self.base_url}?"
                        f"offset={offset}&"
                        f"limit={current_limit}&"
                        f"order=bug_id ASC&"
                        f"bug_id_type=nowords&"
                        f"bug_id=0&"
                        f"include_fields={','.join(self.include_fields)}"
                    )
                    
                    if attempt > 0:
                        logger.info(f"Retry attempt {attempt + 1}/{retry_count} (cycle {retry_cycle}) for offset {offset} (limit={current_limit})")
                    else:
                        if retry_cycle > 1:
                            logger.info(f"Starting retry cycle {retry_cycle} for offset {offset} (limit={current_limit})")
                        else:
                            logger.info(f"Fetching bugs from offset {offset} (limit={current_limit}) (url={url})...")
                    
                    response = requests.get(url, headers=headers, timeout=120)  # 2 minute timeout
                    
                    if response.status_code == 200:
                        data = response.json()
                        bugs = data.get('bugs', [])
                        if retry_cycle > 1:
                            logger.info(f"[OK] Successfully fetched {len(bugs)} bugs after {retry_cycle} retry cycles!")
                        else:
                            logger.info(f"[OK] Successfully fetched {len(bugs)} bugs")
                        return bugs  # SUCCESS - return bugs and exit
                        
                    elif response.status_code == 429:  # Rate limited
                        logger.warning(f"Rate limited (429). Reducing batch size.")
                        old_limit = current_limit
                        current_limit = max(50, current_limit // 2)
                        logger.info(f"Reduced limit from {old_limit} to {current_limit}")
                        sleep_time = 30  # Short wait for rate limit
                        logger.info(f"Waiting {sleep_time} seconds...")
                        time.sleep(sleep_time)
                        
                    else:
                        logger.warning(f"API returned status {response.status_code}")
                        # Halve batch limit on failure
                        old_limit = current_limit
                        current_limit = max(50, current_limit // 2)
                        logger.info(f"Reduced limit from {old_limit} to {current_limit}")
                        
                        # Short wait before retry
                        sleep_time = 15 * (attempt + 1)  # 15s, 30s, 45s, 60s, 75s
                        logger.info(f"Waiting {sleep_time} seconds before retry...")
                        time.sleep(sleep_time)
                        
                except requests.exceptions.Timeout:
                    logger.error(f"Request timeout at offset {offset} (exceeded 120 seconds)")
                    # Halve batch limit on timeout
                    old_limit = current_limit
                    current_limit = max(50, current_limit // 2)
                    logger.info(f"Reduced limit from {old_limit} to {current_limit}")
                    
                    sleep_time = 20 * (attempt + 1)  # 20s, 40s, 60s, 80s, 100s
                    logger.info(f"Waiting {sleep_time} seconds before retry...")
                    time.sleep(sleep_time)
                    
                except (requests.exceptions.ConnectionError, ConnectionResetError) as e:
                    logger.error(f"Connection error: {type(e).__name__}")
                    # Halve batch limit on connection error
                    old_limit = current_limit
                    current_limit = max(50, current_limit // 2)
                    logger.info(f"Reduced limit from {old_limit} to {current_limit}")
                    
                    # Moderate wait for connection errors
                    sleep_time = 30 * (attempt + 1)  # 30s, 60s, 90s, 120s, 150s
                    logger.info(f"Connection issue detected. Waiting {sleep_time} seconds before retry...")
                    time.sleep(sleep_time)
                    
                except Exception as e:
                    logger.error(f"Unexpected error fetching bugs: {type(e).__name__}: {e}")
                    # Halve batch limit on any error
                    old_limit = current_limit
                    current_limit = max(50, current_limit // 2)
                    logger.info(f"Reduced limit from {old_limit} to {current_limit}")
                    
                    sleep_time = 15 * (attempt + 1)
                    if attempt < retry_count - 1:
                        logger.info(f"Waiting {sleep_time} seconds before retry...")
                        time.sleep(sleep_time)
            
            # All 5 attempts failed - wait 600 seconds and start new retry cycle
            logger.error(f"[FAILED] Failed to fetch bugs after {retry_count} attempts (cycle {retry_cycle}) at offset {offset}")
            logger.info(f"[WAIT] Waiting 600 seconds (10 minutes) before starting new retry cycle...")
            time.sleep(600)
            retry_cycle += 1
            current_limit = self.batch_limit  # Reset batch limit for new cycle
            logger.info(f"[RETRY] Starting new retry cycle {retry_cycle} with fresh batch limit {current_limit}")

    
    def parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string to datetime object."""
        if not dt_str or dt_str == "---" or dt_str == "":
            return None
        try:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except Exception as e:
            logger.warning(f"Failed to parse datetime '{dt_str}': {e}")
            return None
    
    def extract_bug_data(self, bug: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract bug data for Bugs table.
        
        Args:
            bug: Bug dictionary from API
            
        Returns:
            Dictionary with bug data for insertion
        """
        # Handle description - convert empty string to None
        bug_description = bug.get('description')
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
                alias = ', '.join(str(a) for a in alias if a) if alias else None
            else:
                alias = str(alias)
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
            bug: Bug dictionary from API
            
        Returns:
            List of property dictionaries
        """
        properties = []
        bug_id = bug.get('id')
        
        # Map API field names to database Name values
        property_fields = {
            'regressions': 'Regressions',
            'regressed_by': 'regressed_by',
            'depends_on': 'depend_on',
            'blocks': 'blocks'
        }
        
        for api_field, db_name in property_fields.items():
            values = bug.get(api_field, [])
            if values and isinstance(values, list):
                for value in values:
                    if value:  # Skip empty/None values
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
            True if successful, False if already exists
        """
        try:
            self.cursor.execute(self.insert_bug_query, (
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
            if 'PRIMARY KEY' in str(e) or 'UNIQUE' in str(e):
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
        for prop in properties:
            try:
                self.cursor.execute(self.insert_property_query, (
                    prop['Name'],
                    prop['Bug_ID'],
                    prop['Value']
                ))
                inserted_count += 1
            except pyodbc.IntegrityError:
                # Skip duplicates (Unique_ID computed column will catch duplicates)
                logger.debug(f"Property already exists: {prop}")
            except Exception as e:
                logger.error(f"Error inserting property {prop}: {e}")
        
        return inserted_count
    
    def get_current_bug_count(self) -> int:
        """Get current number of bugs in database."""
        try:
            self.cursor.execute("SELECT COUNT(*) FROM [dbo].[Bugs]")
            return self.cursor.fetchone()[0]
        except:
            return 0
    
    def scrape_specific_bug_ids(self, bug_ids: List[int], batch_size: int = 100, delay_between_batches: int = 1):
        """
        Scrape specific bugs by their IDs.
        
        Args:
            bug_ids: List of bug IDs to fetch
            batch_size: Number of bugs to fetch per API call (default: 100)
            delay_between_batches: Seconds to wait between batches (default: 1)
        """
        total_bugs = len(bug_ids)
        total_bugs_inserted = 0
        total_bugs_skipped = 0
        total_properties_inserted = 0
        batch_number = 1
        
        logger.info("=" * 70)
        logger.info("Scraping Specific Bug IDs")
        logger.info(f"Total bugs to scrape: {total_bugs:,}")
        logger.info(f"Batch size: {batch_size}")
        logger.info("=" * 70)
        
        # Process bugs in batches
        for i in range(0, total_bugs, batch_size):
            batch_ids = bug_ids[i:i + batch_size]
            
            logger.info(f"\n{'='*70}")
            logger.info(f"Batch {batch_number}/{(total_bugs + batch_size - 1) // batch_size}")
            logger.info(f"Bug IDs: {batch_ids[0]} to {batch_ids[-1]} ({len(batch_ids)} bugs)")
            logger.info(f"Progress: {total_bugs_inserted:,}/{total_bugs:,} bugs inserted")
            logger.info(f"{'='*70}")
            
            # Build URL with specific bug IDs
            headers = {
                'User-Agent': 'Mozilla Bug Research Scraper/1.0 (Educational Research)',
                'Accept': 'application/json'
            }
            
            # Construct URL with bug IDs
            bug_id_params = ','.join(str(bid) for bid in batch_ids)
            fields = ','.join(self.include_fields)
            url = f"{self.base_url}?id={bug_id_params}&include_fields={fields}"
            
            # Fetch bugs with retry logic
            bugs = None
            for attempt in range(3):  # 3 retry attempts
                try:
                    logger.info(f"Fetching {len(batch_ids)} bugs...")
                    response = requests.get(url, headers=headers, timeout=120)
                    
                    if response.status_code == 200:
                        data = response.json()
                        bugs = data.get('bugs', [])
                        logger.info(f"[OK] Successfully fetched {len(bugs)} bugs")
                        break
                    else:
                        logger.warning(f"API returned status {response.status_code}")
                        if attempt < 2:
                            sleep_time = 15 * (attempt + 1)
                            logger.info(f"Waiting {sleep_time} seconds before retry...")
                            time.sleep(sleep_time)
                except Exception as e:
                    logger.error(f"Error fetching bugs: {type(e).__name__}: {e}")
                    if attempt < 2:
                        sleep_time = 20 * (attempt + 1)
                        logger.info(f"Waiting {sleep_time} seconds before retry...")
                        time.sleep(sleep_time)
            
            if bugs is None or len(bugs) == 0:
                logger.error(f"[FAILED] Could not fetch bugs for batch {batch_number}")
                batch_number += 1
                continue
            
            # Process each bug
            bugs_inserted = 0
            bugs_skipped = 0
            properties_inserted = 0
            
            for bug in bugs:
                try:
                    bug_data = self.extract_bug_data(bug)
                    success = self.insert_bug(bug_data)
                    
                    if success:
                        bugs_inserted += 1
                        
                        # Extract and insert properties
                        properties = self.extract_properties_data(bug)
                        props_count = self.insert_properties(properties)
                        properties_inserted += props_count
                    else:
                        bugs_skipped += 1
                        
                except Exception as e:
                    logger.error(f"Error processing bug {bug.get('id', 'unknown')}: {e}")
            
            # Commit the batch
            try:
                self.connection.commit()
                logger.info("[OK] Batch committed to database")
            except Exception as e:
                logger.error(f"Error committing batch: {e}")
                self.connection.rollback()
            
            # Update totals
            total_bugs_inserted += bugs_inserted
            total_bugs_skipped += bugs_skipped
            total_properties_inserted += properties_inserted
            
            # Log batch summary
            logger.info(f"Batch {batch_number} complete:")
            logger.info(f"  Bugs inserted: {bugs_inserted}")
            logger.info(f"  Bugs skipped: {bugs_skipped}")
            logger.info(f"  Properties inserted: {properties_inserted}")
            logger.info(f"TOTAL: {total_bugs_inserted:,}/{total_bugs:,} bugs | {total_properties_inserted:,} properties")
            
            batch_number += 1
            
            # Delay between batches
            if delay_between_batches > 0 and i + batch_size < total_bugs:
                time.sleep(delay_between_batches)
        
        # Final summary
        logger.info("\n" + "=" * 70)
        logger.info("SPECIFIC BUG ID SCRAPING COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Total bugs inserted: {total_bugs_inserted:,}")
        logger.info(f"Total bugs skipped: {total_bugs_skipped:,}")
        logger.info(f"Total properties inserted: {total_properties_inserted:,}")
        logger.info("=" * 70)
    
    def scrape_all_bugs(self, start_offset: int = 0, delay_between_batches: int = 3):
        """
        Scrape all bugs from Bugzilla API with infinite retry on failures.
        
        Args:
            start_offset: Starting offset (useful for resuming)
            delay_between_batches: Seconds to wait between successful batches (default: 3)
        """
        offset = start_offset
        total_bugs_inserted = 0
        total_bugs_skipped = 0
        total_properties_inserted = 0
        batch_number = 1
        
        logger.info("=" * 70)
        logger.info("Starting Bugzilla API scraping")
        logger.info(f"Start offset: {offset}")
        logger.info(f"Batch limit: {self.batch_limit}")
        logger.info(f"Delay between batches: {delay_between_batches}s")
        logger.info("=" * 70)
        
        while True:
            logger.info(f"\n{'='*70}")
            logger.info(f"Batch {batch_number} | Offset: {offset}")
            logger.info(f"Time: {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
            logger.info(f"Progress: {total_bugs_inserted:,} bugs inserted so far")
            logger.info(f"{'='*70}")
            
            # Fetch bugs from API (will retry infinitely until success)
            bugs = self.fetch_bugs_batch(offset)
            
            if len(bugs) == 0:
                logger.info("[OK] No more bugs to fetch, scraping complete!")
                break
            
            # Process each bug
            bugs_inserted = 0
            bugs_skipped = 0
            properties_inserted = 0
            
            for bug in bugs:
                try:
                    # Extract and insert bug data
                    bug_data = self.extract_bug_data(bug)
                    success = self.insert_bug(bug_data)
                    
                    if success:
                        bugs_inserted += 1
                        
                        # Extract and insert properties
                        properties = self.extract_properties_data(bug)
                        props_count = self.insert_properties(properties)
                        properties_inserted += props_count
                    else:
                        bugs_skipped += 1
                        
                except Exception as e:
                    logger.error(f"Error processing bug {bug.get('id', 'unknown')}: {e}")
            
            # Commit the batch
            try:
                self.connection.commit()
                logger.info("[OK] Batch committed to database")
            except Exception as e:
                logger.error(f"Error committing batch: {e}")
                self.connection.rollback()
            
            # Update totals
            total_bugs_inserted += bugs_inserted
            total_bugs_skipped += bugs_skipped
            total_properties_inserted += properties_inserted
            
            # Log batch summary
            logger.info(f"Batch {batch_number} complete:")
            logger.info(f"  Bugs inserted: {bugs_inserted}")
            logger.info(f"  Bugs skipped: {bugs_skipped}")
            logger.info(f"  Properties inserted: {properties_inserted}")
            logger.info(f"TOTAL: {total_bugs_inserted:,} bugs | {total_properties_inserted:,} properties")
            
            # Save checkpoint info
            if batch_number % 10 == 0:
                logger.info(f"[CHECKPOINT] Offset={offset} | Bugs={total_bugs_inserted:,} | Time={strftime('%Y-%m-%d %H:%M:%S', localtime())}")
            
            # Move to next batch - INCREMENT BY ACTUAL BUGS FETCHED, not batch_limit
            # This prevents skipping bugs when batch_limit was temporarily reduced
            actual_bugs_fetched = len(bugs)
            offset += actual_bugs_fetched
            batch_number += 1
            
            logger.info(f"Next offset will be: {offset} (moved by {actual_bugs_fetched} bugs)")
            
            # Delay between batches to avoid rate limiting
            if delay_between_batches > 0:
                time.sleep(delay_between_batches)
        
        # Final summary
        logger.info("\n" + "=" * 70)
        logger.info("SCRAPING COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Total bugs inserted: {total_bugs_inserted:,}")
        logger.info(f"Total bugs skipped: {total_bugs_skipped:,}")
        logger.info(f"Total properties inserted: {total_properties_inserted:,}")
        logger.info(f"Final database count: {self.get_current_bug_count():,}")
        logger.info("=" * 70)


def main():
    """Main execution function."""
    
    # ========== CONFIGURATION ==========
    BATCH_LIMIT = 1000   # Number of bugs per API call (max ~1200, recommended: 500-1000)
    DELAY_BETWEEN_BATCHES = 5  # Seconds to wait between successful batches (faster: 1-2, safer: 3-5)
    # ===================================
    
    logger.info("=" * 70)
    logger.info("Bugzilla API Scraper - Robust Overnight Mode")
    logger.info("=" * 70)
    logger.info(f"Start time: {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    
    scraper = BugzillaAPIScraper(conn_str, batch_limit=BATCH_LIMIT)
    
    try:
        # Connect to database
        scraper.connect()
        
        # Get current bug count from database to use as START_OFFSET
        START_OFFSET = scraper.get_current_bug_count()
        logger.info(f"Current bugs in database: {START_OFFSET:,}")
        logger.info(f"START_OFFSET automatically set to: {START_OFFSET:,}")
        
        logger.info(f"Configuration:")
        logger.info(f"  Batch limit: {BATCH_LIMIT}")
        logger.info(f"  Start offset: {START_OFFSET:,} (from database)")
        logger.info(f"  Delay between batches: {DELAY_BETWEEN_BATCHES}s")
        logger.info("=" * 70)
        
        # If resuming (START_OFFSET > 0), wait to avoid rate limiting
        if START_OFFSET > 0:
            initial_delay = 15  # Wait 15 seconds before resuming
            logger.info(f"[RESUME] Resuming from offset {START_OFFSET:,}")
            logger.info(f"[WAIT] Waiting {initial_delay} seconds to avoid rate limiting...")
            time.sleep(initial_delay)
            logger.info("[OK] Ready to resume scraping")
        
        # Scrape all bugs
        scraper.scrape_all_bugs(
            start_offset=START_OFFSET,
            delay_between_batches=DELAY_BETWEEN_BATCHES
        )
        
    except KeyboardInterrupt:
        logger.info("\n\n" + "=" * 70)
        logger.info("[WARNING] SCRAPING INTERRUPTED BY USER")
        logger.info("=" * 70)
        current_count = scraper.get_current_bug_count()
        logger.info(f"Bugs in database: {current_count:,}")
        logger.info("Check the log above for the last successful offset")
        logger.info("To resume, update START_OFFSET in main() and run again")
        logger.info("=" * 70)
    except Exception as e:
        logger.error(f"[FAILED] Scraping failed with error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
    finally:
        scraper.disconnect()
    
    logger.info(f"End time: {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    logger.info("Script completed")


def scrape_hardcoded_bugs():
    """Scrape specific bug IDs."""
    
    hardcoded_bug_ids = [
  376813, 376814, 376815, 376816, 376817, 376818, 376819, 376820,
  376821, 376822, 376823, 376824, 376825, 376826, 376827, 376828,
  376829, 376830, 376831, 376832, 376833, 376834, 376835, 376836,
  376837, 376838, 376839, 376840, 376841, 376842, 376843, 376844,
  376845, 376846, 376847, 376848, 376849, 376850, 376851, 376852,
  376853, 376854, 376855, 376856, 376857, 376858, 376859, 376860,
  376861, 376862, 376863, 376864, 376865, 376866, 376867, 376868,
  376869, 376870, 376871, 376872, 376873, 376874, 376875, 376876,
  376877, 376878, 376879, 376880, 376881, 376882, 376883, 376884,
  376885, 376886, 376887, 376888, 376889, 376890, 376891, 376892,
  376893, 376894, 376895, 376896, 376897, 376898, 376899, 376900,
  376901, 376902, 376903, 376904, 376905, 376906, 376907, 376908,
  376909, 376910, 376911, 376912, 376913, 376914
]
    
    logger.info(f"Total hardcoded bug IDs to scrape: {len(hardcoded_bug_ids):,}")
    
    scraper = BugzillaAPIScraper(conn_str, batch_limit=1000)
    
    try:
        scraper.connect()
        scraper.scrape_specific_bug_ids(hardcoded_bug_ids, batch_size=100, delay_between_batches=1)
    except KeyboardInterrupt:
        logger.info("\n\n" + "=" * 70)
        logger.info("[WARNING] SCRAPING INTERRUPTED BY USER")
        logger.info("=" * 70)
    except Exception as e:
        logger.error(f"[FAILED] Scraping failed with error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
    finally:
        scraper.disconnect()
    
    logger.info("Script completed")


if __name__ == "__main__":
    # To scrape hardcoded bugs, comment out main() and uncomment scrape_hardcoded_bugs()
    main()
    # scrape_hardcoded_bugs()
