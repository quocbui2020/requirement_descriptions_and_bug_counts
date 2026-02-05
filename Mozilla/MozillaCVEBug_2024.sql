-- This file contains scripts to create [MozillaCVEBug_2024] (or [FixFox]) dataset:
-- database schema: https://dbdiagram.io/d/MozillaCVEBug_2024-674297dfe9daa85aca7f1e70
-- Create new database:
CREATE DATABASE MozillaCVEBug_2024;
USE MozillaCVEBug_2024;

-- Create new table 'Bugs':
CREATE TABLE Bugs (
    ID INT NOT NULL PRIMARY KEY,
    Title VARCHAR(1000) NULL,
    [Description] VARCHAR(MAX) NULL,
    CVE_ID VARCHAR(500) NULL,
    Product VARCHAR(100) NOT NULL,
    Component VARCHAR(100) NULL,
    Type VARCHAR(50) NOT NULL,
    Status VARCHAR(50) NOT NULL,
    Resolution VARCHAR(50) NOT NULL,
    Resolved_Comment_Datetime DATETIME NULL,
    User_Story VARCHAR(MAX) NULL,
    Inserted_On DATETIME NOT NULL
);

-- Migrate data over to new table [Bugs]
INSERT INTO MozillaCVEBug_2024.dbo.Bugs ( -- -- (2107 rows affected)
    ID, Title, [Description], CVE_ID, Product, Component, Type, 
    Status, Resolution, Resolved_Comment_Datetime, User_Story, Inserted_On
)
SELECT 
    [id] AS [ID],
    [bug_title] AS [Title],
    [bug_description] AS [Description],
    [alias] AS [CVE_IDs],
    [product] AS [Product],
    [component] AS [Component],
    [type] AS [Type],
    [status] AS [Status],
    [resolution] AS [Resolution],
    [resolved_comment_datetime] AS [Resolved_Comment_Datetime],
    [user_story] AS [User_Story],
	--,[potential_hashes]
    --,[changeset_links]
    [inserted_on] AS [Inserted_On]
FROM ResearchDatasets.dbo.Bugzilla
WHERE alias LIKE '%CVE%'
  AND resolution = 'FIXED'
  AND ([status] = 'VERIFIED' OR [status] = 'RESOLVED')
ORDER BY inserted_on DESC;

CREATE TABLE Changeset_BugMapping (
    Unique_Hash AS (hashbytes('SHA2_256', CONCAT(Changeset_Hash_ID, Bug_ID, Type))),
    Changeset_Hash_ID VARCHAR(40) NULL,
    Bug_ID VARCHAR(50) NULL,
    Type VARCHAR(50) NULL
) ON [PRIMARY];

INSERT INTO MozillaCVEBug_2024.dbo.Changeset_BugMapping (Changeset_Hash_ID, Bug_ID, Type) -- (14708 rows affected)
SELECT 
    bmcb.Changeset_Hash_ID,
    bmcb.Bug_ID,
    bmcb.Type
FROM ResearchDatasets.dbo.Bugzilla_Mozilla_Changeset_BugIds bmcb
INNER JOIN ResearchDatasets.dbo.Bugzilla b ON b.id = bmcb.Bug_ID
WHERE b.alias LIKE '%CVE%'
  AND b.resolution = 'FIXED'
  AND (b.[status] = 'VERIFIED' OR b.[status] = 'RESOLVED');


-- Create the new Changesets table
CREATE TABLE Changesets (
    Hash_Id VARCHAR(40) NOT NULL PRIMARY KEY, -- PK
    Changeset_Summary VARCHAR(MAX) NULL, -- Raw_Summary
    Mercurial_Type VARCHAR(1000) NOT NULL,
    Changeset_Datetime VARCHAR(1000) NOT NULL,
    Parent_Hashes VARCHAR(5000) NULL,
    Child_Hashes VARCHAR(5000) NULL,
    Inserted_On DATETIME NOT NULL
);

-- Migrate the data into the 'Changesets' table (6,746 records)
INSERT INTO Changesets (
    Hash_Id,
    Changeset_Summary,
    Mercurial_Type,
    Changeset_Datetime,
    Parent_Hashes,
    Child_Hashes,
    Inserted_On
)
SELECT DISTINCT
    bmc.Hash_Id AS Hash_Id,
    bmc.Changeset_Summary AS Changeset_Summary,
    bmc.Mercurial_Type AS Mercurial_Type,
    bmc.Changeset_Datetime AS Changeset_Datetime,
    bmc.Parent_Hashes AS Parent_Hashes,
    bmc.Child_Hashes AS Child_Hashes,
    bmc.Inserted_On AS Inserted_On
FROM ResearchDatasets.dbo.Bugzilla b
INNER JOIN ResearchDatasets.dbo.Bugzilla_Mozilla_Changeset_BugIds bmcb ON bmcb.Bug_ID = b.ID
INNER JOIN ResearchDatasets.dbo.Bugzilla_Mozilla_Changesets bmc ON bmc.Hash_Id = bmcb.Changeset_Hash_ID
WHERE b.alias LIKE '%CVE%'
  AND b.resolution = 'FIXED'
  AND (b.[status] = 'VERIFIED' OR b.[status] = 'RESOLVED')
  AND bmc.Backed_Out_By IS NULL
  AND bmc.Is_Backed_Out_Changeset = 0
  AND (bmc.Parent_Hashes IS NOT NULL AND CHARINDEX('|', bmc.Parent_Hashes) = 0);


-- Create table 'Changeset_Files':
CREATE TABLE Changeset_Files (
    Unique_Hash AS (HASHBYTES('SHA2_256', CONCAT(Changeset_Hash_ID, Previous_File_Name, Updated_File_Name))),
    Changeset_Hash_ID VARCHAR(40) NOT NULL,
    Previous_File_Name VARCHAR(1000) NOT NULL,
    Updated_File_Name VARCHAR(1000) NOT NULL,
    File_Status VARCHAR(100) NOT NULL,
    Previous_File_Link VARCHAR(2000) NULL,
    Updated_File_Link VARCHAR(2000) NULL,
    Inserted_On DATETIME NOT NULL,
    CONSTRAINT PK_Changeset_Files UNIQUE CLUSTERED (Unique_Hash) -- Use as clustered index
);

-- Migrate data over to 'Changeset_Files':
INSERT INTO Changeset_Files (
    Changeset_Hash_ID,
    Previous_File_Name,
    Updated_File_Name,
    File_Status,
    Previous_File_Link,
    Updated_File_Link,
    Inserted_On
)
SELECT DISTINCT
    cf.Changeset_Hash_ID,
    cf.Previous_File_Name,
    cf.Updated_File_Name,
    cf.File_Status,
    cf.Previous_File_Link,
    cf.Updated_File_Link,
    cf.Inserted_On
FROM MozillaCVEBug_2024.dbo.Changesets c
INNER JOIN ResearchDatasets.dbo.Bugzilla_Mozilla_Changeset_Files cf ON cf.Changeset_Hash_ID = c.Hash_Id
WHERE (
    (
        cf.Previous_File_Name LIKE '%.js'
        OR cf.Previous_File_Name LIKE '%.py'
        OR cf.Previous_File_Name LIKE '%.c'
        OR cf.Previous_File_Name LIKE '%.cpp'
    )
    OR 
    (
        cf.Updated_File_Name LIKE '%.js'
        OR cf.Updated_File_Name LIKE '%.py'
        OR cf.Updated_File_Name LIKE '%.c'
        OR cf.Updated_File_Name LIKE '%.cpp'
    )
);


-- Create table 'CVE_Datails':
CREATE TABLE CVE_Details (
    CVE_ID VARCHAR(200) NOT NULL,
    CWE_ID VARCHAR(200) NULL,
    [Description] VARCHAR(2000) NULL,
    [CVSS_Metric_BaseScores] VARCHAR(2000) NULL,
    [Published] VARCHAR(200) NULL,
    [Last_Modified] VARCHAR(200) NULL,
    [Vulnerability_Status] VARCHAR(200) NULL,
    [Source_Identifier] VARCHAR(200) NULL,
    [Inserted_On] DATETIME NULL,
    CONSTRAINT PK_CVE_Details PRIMARY KEY CLUSTERED (CVE_ID ASC)
);

-- Migrate data to 'CVE_Details' (2,070):
INSERT INTO CVE_Details (
    CVE_ID,
    CWE_ID,
    [Description],
    [CVSS_Metric_BaseScores],
    [Published],
    [Last_Modified],
    [Vulnerability_Status],
    [Source_Identifier],
    [Inserted_On]
)
SELECT DISTINCT
    v.CVE_ID,
    v.CWE_ID,
    v.[Description],
    v.CVSS_Metric_BaseScores,
    v.CVE_Published_On AS Published,
    v.CVE_Last_Modified AS Last_Modified,
    v.CVE_Vuln_Status AS Vulnerability_Status,
    v.Source_Identifier,
    v.Inserted_On
FROM MozillaCVEBug_2024.dbo.Bugs b
INNER JOIN ResearchDatasets.dbo.CVE_Vulnerabilities v
    ON v.CVE_ID = b.CVE_ID;


-- Get file type statistics:
SELECT 
    File_Type,
    Total_Count,
    ROUND((CAST(Total_Count AS FLOAT) / (SELECT COUNT(*) FROM Changeset_Files WHERE 
        (Previous_File_Name LIKE '%.js' OR Previous_File_Name LIKE '%.py' OR Previous_File_Name LIKE '%.c' OR Previous_File_Name LIKE '%.cpp')
        OR 
        (Updated_File_Name LIKE '%.js' OR Updated_File_Name LIKE '%.py' OR Updated_File_Name LIKE '%.c' OR Updated_File_Name LIKE '%.cpp')
    )) * 100, 2) AS Percentage
FROM (
    SELECT 
        'JavaScript (.js)' AS File_Type, 
        COUNT(*) AS Total_Count
    FROM Changeset_Files
    WHERE 
        (Previous_File_Name LIKE '%.js' OR Updated_File_Name LIKE '%.js')
    UNION ALL
    SELECT 
        'Python (.py)' AS File_Type, 
        COUNT(*) AS Total_Count
    FROM Changeset_Files
    WHERE 
        (Previous_File_Name LIKE '%.py' OR Updated_File_Name LIKE '%.py')
    UNION ALL
    SELECT 
        'C (.c)' AS File_Type, 
        COUNT(*) AS Total_Count
    FROM Changeset_Files
    WHERE 
        (Previous_File_Name LIKE '%.c' OR Updated_File_Name LIKE '%.c')
    UNION ALL
    SELECT 
        'C++ (.cpp)' AS File_Type, 
        COUNT(*) AS Total_Count
    FROM Changeset_Files
    WHERE 
        (Previous_File_Name LIKE '%.cpp' OR Updated_File_Name LIKE '%.cpp')
) AS File_Stats
ORDER BY Percentage DESC;


-- SQL Server Version
SELECT 
    @@VERSION AS [SQL Server Version],
    SERVERPROPERTY('Edition') AS [Edition],
    SERVERPROPERTY('ProductLevel') AS [Service Pack],
    SERVERPROPERTY('ProductVersion') AS [Product Version];

-- Compatibility Level
USE MozillaCVEBug_2024; -- Replace with your database name
SELECT 
    name AS [Database Name],
    compatibility_level AS [Compatibility Level]
FROM sys.databases
WHERE name = 'MozillaCVEBug_2024';

-- Collation
SELECT 
    name AS [Database Name],
    collation_name AS [Collation]
FROM sys.databases
WHERE name = 'MozillaCVEBug_2024';

-- Database Size
EXEC sp_spaceused;



/*
-- Objective Delete bugs that CVE Details No Found from NIST database:
select *
from Bugs b
left join CVE_Details c on c.CVE_ID = b.CVE_ID
where c.CVE_ID is null
order by b.CVE_ID desc;

delete from Changeset_BugMapping -- deleted 171 records
where Unique_Hash in(
	select m.Unique_Hash
	from Changeset_BugMapping m
	left join Bugs b on b.ID = m.Bug_ID
	where b.ID is null
)

delete from Changesets -- deleted 171 records
where Hash_ID IN(
	select c.Hash_ID
	from Changesets c
	left join Changeset_BugMapping m on m.Changeset_Hash_ID = c.Hash_ID
	where m.Unique_Hash is null
)

delete from Changeset_Files -- deleted 149 records
where Unique_Hash in(
	select cf.Unique_Hash
	from Changeset_Files cf
	left join changesets c on c.Hash_ID = cf.Changeset_Hash_ID
	where c.Hash_ID is null
)
--*/

/*
Order of filter:
- Firefox product
- associated to CVE
- RESOLVED OR VERIFIED
- resolution FIXED

Issues:
- "Bugzilla is a large
database containing over 1.7 million reported bug records,
and this number grows daily due to newly reported bugs"
--> Should be 1.7 million bugs of MOZILLA products. 

- Need to mention that we collected the changeset from Mercurial, ignore others such as Git links.

-elements are separated by the string “|” (Should be characters " | ",)
*/