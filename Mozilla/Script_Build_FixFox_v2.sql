/*
FixFox:
	- Similar tables (2 more tables discuss later)
	- 1) Table 'Changeset_Git_Mapping':
		- C1: Changeset_ID (unique)
		- C2: Git_Commit_ID
		- Relationship: one-to-one
	- 2) Table 'Git_Commit_Details':
		- C1: Git_Commit_ID (Foreign key)
		- C2: Modified_File
		- C3: Modified_Function
    - Collect commits associates with CVE
	- Only consider 'Mozilla Central'.
	    - Look at the 'Mercurial_Type'
		
When submitting the paper in 2024 (First attempt), we do not apply filter (Only consider 'Mozilla Central')
*/

-- Populate data for [Bug_Details]:
insert into FixFox_v2.dbo.Bug_Details
           ([ID]
           ,[Title]
           ,[Description]
		   ,[CVE_ID]
           ,[Product]
           ,[Component]
		   ,[type]
           ,[Status]
           ,[Resolution]
           ,[Resolved_Comment_Datetime]
           ,[User_Story]
           ,[Inserted_On])
select distinct
	b.id,
	b.bug_title,
	b.bug_description,
	b.alias,
	b.product,
	b.component,
	b.[type],
	b.status,
	b.resolution,
	b.resolved_comment_datetime,
	b.user_story,
	b.inserted_on
from ResearchDatasets.dbo.Bugzilla b
inner join ResearchDatasets.dbo.Bugzilla_Mozilla_Changeset_BugIds cb on cb.Bug_ID = b.id
inner join ResearchDatasets.dbo.Bugzilla_Mozilla_Changesets c on cb.Changeset_Hash_ID = c.Hash_Id
where b.alias like 'CVE%'
	and (
		Mercurial_Type like 'mozilla-central'
		or Mercurial_Type like '% mozilla-central' -- Example: '... | mozilla-central'
		or Mercurial_Type like 'mozilla-central %' -- Example: 'mozilla-central | ...'
		or Mercurial_Type like '% mozilla-central %' -- Example: '... | mozilla-central | ...'
			-- Exclude cases: '...mozilla-central-cvs' or 'something/mozilla-central'
		)
    and b.status in('VERIFIED','RESOLVED');

-- Populate data for [CVE_Details]:
INSERT INTO [FixFox_v2].[dbo].[CVE_Details]
	([CVE_ID]
	,[CWE_ID]
	,[Description]
	,[CVSS_Metric_BaseScores]
	,[Published]
	,[Last_Modified]
	,[Vulnerability_Status]
	,[Source_Identifier]
	,[Inserted_On])
select distinct
	cve.CVE_ID,
	cve.CWE_ID,
	cve.[Description],
	cve.CVSS_Metric_BaseScores,
	cve.CVE_Published_On,
	cve.CVE_Last_Modified,
	cve.CVE_Vuln_Status,
	cve.Source_Identifier,
	cve.Inserted_On
from ResearchDatasets.dbo.CVE_Vulnerabilities cve
inner join FixFox_v2.dbo.Bug_Details b on b.CVE_ID = cve.CVE_ID;

-- Populate data for [Changeset_Bug_Mapping]:
INSERT INTO [FixFox_v2].[dbo].[Changeset_Bug_Mapping]
    ([Changeset_Hash_ID]
    ,[Bug_ID])
select distinct
	m.Changeset_Hash_ID,
	m.Bug_ID
from ResearchDatasets.dbo.Bugzilla_Mozilla_Changeset_BugIds m
inner join [FixFox_v2].[dbo].Bug_Details b on b.ID = m.Bug_ID
inner join ResearchDatasets.dbo.Bugzilla_Mozilla_Changesets c on c.Hash_Id = m.Changeset_Hash_ID
where m.[Type] = 'InTitle'
	-- One 'b' can have multiple 'm' (with Type='InTitle') records, and each of those records can have different mercurial type (could be other tthan 'mozilla-central'). Therefore, we need to filter it again here:
	and (
			c.Mercurial_Type like 'mozilla-central'
			or c.Mercurial_Type like '% mozilla-central'
			or c.Mercurial_Type like 'mozilla-central %'
			or c.Mercurial_Type like '% mozilla-central %'
		);

-- Populate data for [Changeset_Details]:
INSERT INTO [FixFox_v2].[dbo].[Changeset_Details]
    ([Hash_ID]
    ,[Changeset_Summary]
    ,[Mercurial_Type]
    ,[Changeset_Datetime]
    ,[Parent_Hashes]
    ,[Child_Hashes]
    ,[Inserted_On])
select distinct
	c.Hash_Id,
	c.Changeset_Summary,
	c.Mercurial_Type,
	c.Changeset_Datetime,
	c.Parent_Hashes,
	c.Child_Hashes,
	c.Inserted_On
from ResearchDatasets.dbo.Bugzilla_Mozilla_Changesets c
inner join [FixFox_v2].dbo.Changeset_Bug_Mapping m on m.Changeset_Hash_ID = c.Hash_Id
where c.Is_Backed_Out_Changeset = 0
	and c.Backed_Out_By is null
	and c.Backout_Hashes is null
	and c.Parent_Hashes not like '%|%';

-- Populate data for [Changeset_Files]:
INSERT INTO [FixFox_v2].[dbo].[Changeset_Files]
    ([Changeset_Hash_ID]
    ,[Previous_File_Name]
    ,[Updated_File_Name]
    ,[File_Status]
    ,[Previous_File_Links]
    ,[Updated_File_Links]
    ,[Inserted_On])
SELECT DISTINCT
	f.Changeset_Hash_ID,
	f.Previous_File_Name,
	f.Updated_File_Name,
	f.File_Status,
	f.Previous_File_Link,
	f.Updated_File_Link,
	f.Inserted_On
FROM [FixFox_v2].[dbo].[Changeset_Details] c
INNER JOIN ResearchDatasets.dbo.Bugzilla_Mozilla_Changeset_Files f ON f.Changeset_Hash_ID = c.Hash_ID
WHERE (
	-- Apply the filter to ensure we consider only js, py, c, and cpp files.
	f.Previous_File_Name = '/dev/null'
	AND (
		f.Updated_File_Name LIKE '%.js'
		OR f.Updated_File_Name LIKE '%.py'
		OR f.Updated_File_Name LIKE '%.c'
		OR f.Updated_File_Name LIKE '%.cpp'
	)
)
OR (
	f.Updated_File_Name = '/dev/null'
	AND (
		f.Previous_File_Name LIKE '%.js'
		OR f.Previous_File_Name LIKE '%.py'
		OR f.Previous_File_Name LIKE '%.c'
		OR f.Previous_File_Name LIKE '%.cpp'
	)
)
OR (
	(f.Previous_File_Name LIKE '%.js' AND f.Updated_File_Name LIKE '%.js')
	OR (f.Previous_File_Name LIKE '%.py' AND f.Updated_File_Name LIKE '%.py')
	OR (f.Previous_File_Name LIKE '%.c' AND f.Updated_File_Name LIKE '%.c')
	OR (f.Previous_File_Name LIKE '%.cpp' AND f.Updated_File_Name LIKE '%.cpp')
);

-- Populate data for [Changeset_Git_Mapping]:
INSERT INTO [FixFox_v2].[dbo].[Changeset_Git_Mapping]
	([Changeset_Hash_ID]
	,[Git_Commit_ID])
select distinct
	c.Hash_ID,
	NULL
from [FixFox_v2].dbo.Changeset_Details c;


-- Populate data for [Changeset_Modified_Functions]:
INSERT INTO FixFox_v3.dbo.Changeset_Modified_Functions (Changeset_File_Unique_Hash, Function_Name)
SELECT DISTINCT
    cf.Unique_Hash AS Changeset_File_Unique_Hash,
    gcd.Modified_Function AS Function_Name
FROM FixFox_v3.dbo.Changeset_Files cf
INNER JOIN FixFox_v3.dbo.Changeset_Git_Mapping cgm 
    ON cgm.Changeset_Hash_ID = cf.Changeset_Hash_ID
INNER JOIN FixFox_v3.dbo.git_commit_details gcd 
    ON gcd.Git_Commit_ID = cgm.Git_Commit_ID
WHERE REPLACE(
        SUBSTRING(
            CASE 
                WHEN cf.Updated_File_Name = '/dev/null' THEN cf.Previous_File_Name
                ELSE cf.Updated_File_Name
            END,
            CASE 
                WHEN (cf.Updated_File_Name LIKE 'a/%' OR cf.Updated_File_Name LIKE 'b/%' 
                      OR cf.Previous_File_Name LIKE 'a/%' OR cf.Previous_File_Name LIKE 'b/%') 
                THEN 3 ELSE 1 
            END,
            LEN(
                CASE 
                    WHEN cf.Updated_File_Name = '/dev/null' THEN cf.Previous_File_Name
                    ELSE cf.Updated_File_Name
                END
            )
        ),
        '/', '\'
    ) = gcd.Modified_File;

