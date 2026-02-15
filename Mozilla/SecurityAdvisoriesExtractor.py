# Extract vulnerabilities from Mozilla Foundation Security Advisories (MFSA). All vulnerabilities in the file: C:\Users\quocb\quocbui\Studies\research\GithubRepo\requirement_descriptions_and_bug_counts\Mozilla\announce\

import os
import re
import json
import yaml
from pathlib import Path

# Database import dependencies (optional)
try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False

# Database connection string (same format as HgGitMapper.py)
# Update SERVER and DATABASE if different from defaults
CONN_STR = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=localhost\\SQLEXPRESS;' \
           'DATABASE=MozillaDataSet2026;' \
           'Connection Timeout=300;' \
           'Login Timeout=300;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

def extract_yaml_frontmatter(content):
    """Extract YAML frontmatter from markdown content"""
    match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if match:
        yaml_content = match.group(1)
        try:
            frontmatter = yaml.safe_load(yaml_content)
            return frontmatter if frontmatter else {}
        except Exception as e:
            print(f"Error parsing YAML frontmatter: {e}")
            return {}
    return {}

def extract_cve_codes(content):
    """Extract all CVE codes from the content"""
    cve_pattern = r'CVE-\d{4}-\d{4,}'
    cves = re.findall(cve_pattern, content)
    return list(set(cves))  # Remove duplicates

def extract_bug_ids(content):
    """Extract bug IDs from bugzilla links"""
    bug_ids = []
    
    # Pattern for bug_id parameter in URLs
    bug_id_pattern = r'bug_id=([0-9,]+)'
    matches = re.findall(bug_id_pattern, content)
    for match in matches:
        # Split by comma and add individual bug IDs
        ids = [bid.strip() for bid in match.split(',') if bid.strip()]
        bug_ids.extend(ids)
    
    # Pattern for show_bug.cgi?id=
    show_bug_pattern = r'show_bug\.cgi\?id=(\d+)'
    matches = re.findall(show_bug_pattern, content)
    bug_ids.extend(matches)
    
    # Pattern for bugzilla.mozilla.org links in href attributes (References section)
    href_pattern = r'href=["\']https?://bugzilla\.mozilla\.org/show_bug\.cgi\?id=(\d+)["\']'
    matches = re.findall(href_pattern, content)
    bug_ids.extend(matches)
    
    # Pattern for plain bugzilla URLs
    bugzilla_url_pattern = r'bugzilla\.mozilla\.org/show_bug\.cgi\?id=(\d+)'
    matches = re.findall(bugzilla_url_pattern, content)
    bug_ids.extend(matches)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_bug_ids = []
    for bid in bug_ids:
        if bid not in seen:
            seen.add(bid)
            unique_bug_ids.append(bid)
    
    return unique_bug_ids

def extract_description(content):
    """Extract description from the HTML content"""
    # Look for description section
    desc_match = re.search(r'<h3>Description</h3>\s*\n(.*?)(?=<h3>|$)', content, re.DOTALL)
    if desc_match:
        description = desc_match.group(1).strip()
        # Remove HTML tags for cleaner text
        description = re.sub(r'<p[^>]*>', '', description)
        description = re.sub(r'</p>', '\n', description)
        description = re.sub(r'<[^>]+>', '', description)
        description = re.sub(r'\n\s*\n', '\n', description)
        description = description.strip()
        return description if description else None
    return None

def process_file(file_path):
    """Process a single markdown file and extract vulnerability information"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None, None
    
    # Extract MFSA version from filename
    filename = os.path.basename(file_path)
    mfsa_version = os.path.splitext(filename)[0]
    
    # Extract frontmatter
    frontmatter = extract_yaml_frontmatter(content)
    
    # Extract MFSA metadata
    mfsa_metadata = {
        'mfsa_version': mfsa_version,
        'title': frontmatter.get('title', ''),
        'announced': frontmatter.get('announced', None),
        'impact': frontmatter.get('impact', ''),
        'product': frontmatter.get('product', None),
        'fixed_in': frontmatter.get('fixed_in', []) if isinstance(frontmatter.get('fixed_in'), list) else []
    }
    
    # Extract CVE codes
    cve_codes = extract_cve_codes(content)
    
    # Extract bug IDs
    bug_ids = extract_bug_ids(content)
    
    # Extract description
    description = extract_description(content)
    
    # Get title and impact from frontmatter
    title = frontmatter.get('title', '')
    impact = frontmatter.get('impact', '')
    
    # Create entries for each CVE or one entry if no CVE
    vulnerabilities = []
    
    if cve_codes:
        for cve in cve_codes:
            vuln = {
                'mfsa_version': mfsa_version,
                'cve_code': cve,
                'title': f"{cve}: {title}" if title else cve,
                'impact': impact,
                'description': description,
                'bug_ids': bug_ids
            }
            vulnerabilities.append(vuln)
    else:
        # No CVE, create one entry with the MFSA
        vuln = {
            'mfsa_version': mfsa_version,
            'cve_code': None,
            'title': title,
            'impact': impact,
            'description': description,
            'bug_ids': bug_ids
        }
        vulnerabilities.append(vuln)
    
    return mfsa_metadata, vulnerabilities

def process_yml_file(file_path):
    """Process a YAML file and extract vulnerability information"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None, None
    
    # Extract MFSA version from filename
    filename = os.path.basename(file_path)
    mfsa_version = os.path.splitext(filename)[0]
    
    # Extract MFSA metadata
    mfsa_metadata = {
        'mfsa_version': mfsa_version,
        'title': data.get('title', ''),
        'announced': data.get('announced', None),
        'impact': data.get('impact', ''),
        'product': data.get('product', None),
        'fixed_in': data.get('fixed_in', [])
    }
    
    vulnerabilities = []
    
    # Get overall impact (may be overridden per CVE)
    overall_impact = data.get('impact', '')
    
    # Process advisories (each CVE)
    advisories = data.get('advisories', {})
    
    for cve_code, cve_data in advisories.items():
        # Extract bug IDs from bugs list
        bug_ids = []
        bugs = cve_data.get('bugs', [])
        for bug in bugs:
            if isinstance(bug, dict):
                bug_url = bug.get('url', '')
            else:
                bug_url = bug
            
            # Convert to string to handle integers or other types
            bug_url = str(bug_url) if bug_url else ''
            
            # Extract bug IDs from the URL or comma-separated list
            if bug_url:
                # Handle comma-separated bug IDs
                bug_id_matches = re.findall(r'\d+', bug_url)
                bug_ids.extend(bug_id_matches)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_bug_ids = []
        for bid in bug_ids:
            if bid not in seen:
                seen.add(bid)
                unique_bug_ids.append(bid)
        
        title = cve_data.get('title', '')
        impact = cve_data.get('impact', overall_impact)
        description = cve_data.get('description', '')
        
        # Clean up description (remove extra whitespace)
        if description:
            description = description.strip()
        else:
            description = None
        
        vuln = {
            'mfsa_version': mfsa_version,
            'cve_code': cve_code if cve_code.startswith('CVE-') else None,
            'title': f"{cve_code}: {title}" if title else cve_code,
            'impact': impact,
            'description': description,
            'bug_ids': unique_bug_ids
        }
        vulnerabilities.append(vuln)
    
    return mfsa_metadata, vulnerabilities

def main():
    """Main function to process all files"""
    announce_dir = Path(r'C:\Users\quocb\quocbui\Studies\research\GithubRepo\requirement_descriptions_and_bug_counts\Mozilla\announce')
    
    all_vulnerabilities = []
    all_mfsa_metadata = []
    
    # Process all .md and .yml files in all subdirectories
    for year_dir in sorted(announce_dir.iterdir()):
        if year_dir.is_dir():
            print(f"\nProcessing {year_dir.name}...")
            # Process .md files
            for md_file in sorted(year_dir.glob('*.md')):
                mfsa_meta, vulns = process_file(md_file)
                if mfsa_meta:
                    all_mfsa_metadata.append(mfsa_meta)
                if vulns:
                    print(f"  Processing {md_file.stem}... Captured {len(vulns)} vulnerabilities.")
                    all_vulnerabilities.extend(vulns)
                else:
                    print(f"  Processing {md_file.stem}... No vulnerabilities found.")
            # Process .yml files
            for yml_file in sorted(year_dir.glob('*.yml')):
                mfsa_meta, vulns = process_yml_file(yml_file)
                if mfsa_meta:
                    all_mfsa_metadata.append(mfsa_meta)
                if vulns:
                    print(f"  Processing {yml_file.stem}... Captured {len(vulns)} vulnerabilities.")
                    all_vulnerabilities.extend(vulns)
                else:
                    print(f"  Processing {yml_file.stem}... No vulnerabilities found.")
    
    # Write vulnerabilities to JSON file
    output_file = announce_dir.parent / 'vulnerabilities.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_vulnerabilities, f, indent=2, ensure_ascii=False)
    
    # Write MFSA metadata to JSON file
    mfsa_output_file = announce_dir.parent / 'mfsa_metadata.json'
    with open(mfsa_output_file, 'w', encoding='utf-8') as f:
        json.dump(all_mfsa_metadata, f, indent=2, ensure_ascii=False)
    
    print(f"\nExtracted {len(all_vulnerabilities)} vulnerability entries")
    print(f"Extracted {len(all_mfsa_metadata)} MFSA metadata entries")
    print(f"Vulnerabilities output saved to: {output_file}")
    print(f"MFSA metadata output saved to: {mfsa_output_file}")

def import_to_sql():
    """Import extracted JSON data to SQL Server tables"""
    if not PYODBC_AVAILABLE:
        print("Error: pyodbc is not installed. Run: pip install pyodbc")
        return
    
    base_dir = Path(r'C:\Users\quocb\quocbui\Studies\research\GithubRepo\requirement_descriptions_and_bug_counts\Mozilla')
    mfsa_metadata_path = base_dir / 'mfsa_metadata.json'
    vulnerabilities_path = base_dir / 'vulnerabilities.json'
    
    if not mfsa_metadata_path.exists() or not vulnerabilities_path.exists():
        print("Error: JSON files not found. Run extraction first.")
        return
    
    print("\n" + "="*70)
    print("Importing MSFA Data to SQL Server")
    print("="*70)
    
    try:
        # Connect to database
        print("\nConnecting to SQL Server...")
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        print("✓ Connected successfully!")        
        # Clear existing data from all tables
        print("\n⚠ WARNING: Clearing all existing data from tables...")
        cursor.execute("DELETE FROM dbo.Bugs_MSFA_Mappings;")
        cursor.execute("DELETE FROM dbo.MSFA_Vulnerabilities;")
        cursor.execute("DELETE FROM dbo.MSFA_Details;")
        conn.commit()
        print("✓ All tables cleared")        
        # Load JSON files
        with open(mfsa_metadata_path, 'r', encoding='utf-8') as f:
            mfsa_data = json.load(f)
        with open(vulnerabilities_path, 'r', encoding='utf-8') as f:
            vulns_data = json.load(f)
        
        # Import MSFA_Details
        print(f"\nImporting {len(mfsa_data)} MSFA Details...")
        insert_mfsa_sql = """
            INSERT INTO dbo.MSFA_Details (MSFA_version, Title, Announced, Impact, Fixed_In)
            VALUES (?, ?, ?, ?, ?);
        """
        
        imported_mfsa = 0
        for mfsa in mfsa_data:
            try:
                fixed_in_json = json.dumps(mfsa.get('fixed_in', []))
                cursor.execute(
                    insert_mfsa_sql,
                    mfsa.get('mfsa_version'),
                    mfsa.get('title'),
                    mfsa.get('announced'),
                    mfsa.get('impact'),
                    fixed_in_json
                )
                imported_mfsa += 1
                if imported_mfsa % 100 == 0:
                    print(f"  Progress: {imported_mfsa}/{len(mfsa_data)}")
            except pyodbc.IntegrityError:
                pass  # Skip duplicates
        conn.commit()
        print(f"✓ Imported {imported_mfsa} MSFA Details")
        
        # Import MSFA_Vulnerabilities and Bugs_MSFA_Mappings
        print(f"\nImporting {len(vulns_data)} Vulnerabilities...")
        print("WARNING: MSFA_Vulnerabilities PK is MFSA_Version - only first vulnerability per MFSA will be imported!")
        
        insert_vuln_sql = """
            INSERT INTO dbo.MSFA_Vulnerabilities (MFSA_Version, Impact, CVE, Title, Description)
            VALUES (?, ?, ?, ?, ?);
        """
        insert_bug_sql = """
            INSERT INTO dbo.Bugs_MSFA_Mappings (Bug_Id, MFSA_version)
            VALUES (?, ?);
        """
        
        imported_vulns = 0
        imported_bugs = 0
        skipped_vulns = 0
        
        for vuln in vulns_data:
            try:
                cursor.execute(
                    insert_vuln_sql,
                    vuln.get('mfsa_version'),
                    vuln.get('impact'),
                    vuln.get('cve_code'),
                    vuln.get('title'),
                    vuln.get('description')
                )
                imported_vulns += 1
                
                # Import bug mappings
                if vuln.get('bug_ids'):
                    for bug_id in vuln['bug_ids']:
                        try:
                            cursor.execute(insert_bug_sql, int(bug_id), vuln.get('mfsa_version'))
                            imported_bugs += 1
                        except (pyodbc.IntegrityError, ValueError):
                            pass  # Skip duplicates or invalid bug IDs
                
                if imported_vulns % 500 == 0:
                    print(f"  Progress: {imported_vulns}/{len(vulns_data)}")
            
            except pyodbc.IntegrityError:
                skipped_vulns += 1  # Duplicate MFSA_Version (PK violation)
        
        conn.commit()
        print(f"✓ Imported {imported_vulns} vulnerabilities")
        print(f"  Skipped {skipped_vulns} (duplicate MFSA_Version - table PK limitation)")
        print(f"✓ Imported {imported_bugs} bug-MSFA mappings")
        
        # Summary
        cursor.execute("SELECT COUNT(*) FROM dbo.MSFA_Details")
        mfsa_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM dbo.MSFA_Vulnerabilities")
        vuln_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM dbo.Bugs_MSFA_Mappings")
        mapping_count = cursor.fetchone()[0]
        
        print("\n" + "="*70)
        print("Database Summary:")
        print(f"  - MSFA_Details: {mfsa_count} records")
        print(f"  - MSFA_Vulnerabilities: {vuln_count} records")
        print(f"  - Bugs_MSFA_Mappings: {mapping_count} records")
        print("="*70)
        
        cursor.close()
        conn.close()
        
    except pyodbc.Error as e:
        print(f"\nDatabase error: {e}")
        print("Check CONN_STR settings and ensure tables are created.")
    except Exception as e:
        print(f"\nError: {e}")
        raise

if __name__ == '__main__':
    import sys
    
    # Check for command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == '--import-sql':
        print("=" * 70)
        print("SQL Import Mode")
        print("=" * 70)
        import_to_sql()
    else:
        # Default: Extract data from MFSA files
        main()
        
        # Ask if user wants to import to SQL
        print("\n" + "=" * 70)
        response = input("Import extracted data to SQL Server? (yes/no): ").lower()
        if response == 'yes':
            print("\n⚠ WARNING: This will DELETE ALL existing data from these tables:")
            print("  - MSFA_Details")
            print("  - MSFA_Vulnerabilities")
            print("  - Bugs_MSFA_Mappings")
            confirm = input("\nAre you sure you want to continue? (yes/no): ").lower()
            if confirm == 'yes':
                import_to_sql()
            else:
                print("Import cancelled.")