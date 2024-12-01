-- This file contains scripts to create [FixFoxDB] dataset:
-- database schema: used drawio
-- Create new database:
CREATE DATABASE FixFoxDB;
USE FixFoxDB;

-- Create new table 'Defect_Bugs':
CREATE TABLE Defect_Bugs (
    ID INT NOT NULL PRIMARY KEY,
    Title VARCHAR(1000) NULL,
    [Description] VARCHAR(MAX) NULL,
    Product VARCHAR(100) NOT NULL,
    Component VARCHAR(100) NULL,
    [Type] VARCHAR(50) NOT NULL,
    [Status] VARCHAR(50) NOT NULL,
    Resolution VARCHAR(50) NOT NULL,
    Resolved_Comment_Datetime DATETIME NULL,
    User_Story VARCHAR(MAX) NULL,
    Inserted_On DATETIME NOT NULL
);

-- Migrate data over to new table [Defect_Bugs]: (530070 rows affected)
INSERT INTO FixFoxDB.dbo.Defect_Bugs (
    ID, Title, [Description], Product, Component, [Type], 
    [Status], Resolution, Resolved_Comment_Datetime, User_Story, Inserted_On
)
SELECT DISTINCT
    [id] AS [ID],
    [bug_title] AS [Title],
    [bug_description] AS [Description],
    [product] AS [Product],
    [component] AS [Component],
    [type] AS [Type],
    [status] AS [Status],
    [resolution] AS [Resolution],
    [resolved_comment_datetime] AS [Resolved_Comment_Datetime],
    [user_story] AS [User_Story],
    [inserted_on] AS [Inserted_On]
FROM ResearchDatasets.dbo.Bugzilla
WHERE [type] = 'defect'
  AND resolution = 'FIXED'
  AND ([status] = 'VERIFIED' OR [status] = 'RESOLVED')
ORDER BY inserted_on DESC;

----------------------------------------------------------------------------------------
----------------------------------------------------------------------------------------

-- Create table [Changeset_DefectBugMapping]
CREATE TABLE Changeset_DefectBugMapping (
    Unique_Hash AS (hashbytes('SHA2_256', CONCAT(Changeset_Hash_ID, Defect_Bug_ID, Type))),
    Changeset_Hash_ID VARCHAR(40) NULL,
    Defect_Bug_ID VARCHAR(50) NULL,
    Type VARCHAR(50) NULL
) ON [PRIMARY];

-- Create unique index for Changeset_DefectBugMapping.Unique_Hash:
CREATE UNIQUE INDEX UQ_Changeset_DefectBugMapping_UniqueHash 
ON Changeset_DefectBugMapping (Unique_Hash);

-- Migrate data over to Changeset_DefectBugMapping: (1,076,030 rows affected)
INSERT INTO FixFoxDB.dbo.Changeset_DefectBugMapping (Changeset_Hash_ID, Defect_Bug_ID, Type)
SELECT 
    bmcb.Changeset_Hash_ID,
    bmcb.Bug_ID,
    bmcb.Type
FROM ResearchDatasets.dbo.Bugzilla_Mozilla_Changeset_BugIds bmcb
INNER JOIN ResearchDatasets.dbo.Bugzilla b ON b.id = bmcb.Bug_ID
WHERE b.type = 'defect'
  AND b.resolution = 'FIXED'
  AND (b.[status] = 'VERIFIED' OR b.[status] = 'RESOLVED');


----------------------------------------------------------------------------------------
----------------------------------------------------------------------------------------

-- Create the new [Changesets]
CREATE TABLE Changesets (
    Hash_Id VARCHAR(40) NOT NULL PRIMARY KEY, -- PK
    Changeset_Summary VARCHAR(MAX) NULL, -- Raw_Summary
    Mercurial_Type VARCHAR(1000) NOT NULL,
    Changeset_Datetime VARCHAR(1000) NOT NULL,
    Parent_Hashes VARCHAR(5000) NULL,
    Child_Hashes VARCHAR(5000) NULL,
    Inserted_On DATETIME NOT NULL
);
-- Migrate the data into the 'Changesets' table: (459,458 rows affected)
INSERT INTO FixFoxDB.dbo.Changesets (
    Hash_Id,
    Changeset_Summary,
    Mercurial_Type,
    Changeset_Datetime,
    Parent_Hashes,
    Child_Hashes,
    Inserted_On
)
SELECT DISTINCT -- Ensure uniqueness
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
WHERE b.type = 'defect'
  AND b.resolution = 'FIXED'
  AND (b.[status] = 'VERIFIED' OR b.[status] = 'RESOLVED')
  AND bmc.Backed_Out_By IS NULL
  AND bmc.Is_Backed_Out_Changeset = 0
  AND (bmc.Parent_Hashes IS NOT NULL AND CHARINDEX('|', bmc.Parent_Hashes) = 0); -- Ensure only one parent hash.


----------------------------------------------------------------------------------------
----------------------------------------------------------------------------------------

-- Create table [Changeset_Files]:
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

-- Create unique index for Changeset_Files.Unique_Hash:
CREATE UNIQUE INDEX UQ_Changeset_Files_UniqueHash 
ON Changeset_Files (Unique_Hash);

-- Migrate data over to 'Changeset_Files': (1,036,216 rows affected)
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
FROM FixFoxDB.dbo.Changesets c
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

------------------------------------------------------
-- Remove the records those are not related to Firefox
------------------------------------------------------
delete from Defect_Bugs  -- (239086 rows affected)
WHERE product IN (
    'Security Assurance',
    'Mozilla VPN',
    'Plugins Graveyard',
    'Testing',
    'Toolkit Graveyard',
    'Firefox Health Report Graveyard',
    'MailNews Core',
    'Release Engineering',
    'Lockwise Graveyard',
    'Emerging Markets Graveyard',
    'Bugzilla',
    'Thunderbird',
    'Firefox for Android Graveyard',
    'Add-on SDK Graveyard',
    'Firefox OS Graveyard',
    'Fenix',
    'Chat Core',
    'Focus',
    'Remote Protocol',
    'Firefox Graveyard',
    'Cloud Services',
    'Core Graveyard',
    'Calendar',
	'Testopia',
	'Eliot',
	'Conduit',
	'Snippets',
	'bugzilla.mozilla.org',
	'Directory',
	'Mozilla Labs',
	'support.mozilla.org',
	'developer.mozilla.org',
	'L20n',
	'support.mozilla.org - Lithium',
	'Pocket',
	'Data & BI Services Team',
	'SeaMonkey',
	'addons.mozilla.org',
	'www.mozilla.org',
	'Invalid Bugs',
	'Data Science',
	'Air Mozilla',
	'Mozilla China',
	'quality.mozilla.org',
	'Mozilla QA',
	'Developer Ecosystem',
	'CA Program',
	'Tecken'
)
or product like '%Graveyard'


delete from Changeset_DefectBugMapping -- (276,180 rows affected)
where Unique_Hash in(
	select m.Unique_Hash
	from Changeset_DefectBugMapping m
	left join Defect_Bugs b on b.ID = m.Defect_Bug_ID
	where b.ID is null
)


delete from Changesets -- (118631 rows affected)
where Hash_ID in(
	select c.Hash_ID
	from Changesets c
	left join Changeset_DefectBugMapping m on m.Changeset_Hash_ID = c.Hash_ID
	where m.Unique_Hash is null
)


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
WHERE name = 'FixFoxDB';

-- Collation
SELECT 
    name AS [Database Name],
    collation_name AS [Collation]
FROM sys.databases
WHERE name = 'FixFoxDB';

-- Database Size
EXEC sp_spaceused;
