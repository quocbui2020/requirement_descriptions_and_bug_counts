/*
FireFoxDB:
- Similar tables + 2.
- 1) Table 'Changeset_Git_Mapping':
		- C1: Changeset_ID (unique)
		- C2: Git_Commit_ID
		- Relationship: one-to-one
- 2) Table 'Git_Commit_Details':
		- C1: Git_Commit_ID (Foreign key)
		- C2: Modified_File
		- C3: Modified_Function
- Exclude commits associates with CVE.
- Only consider 'Mozilla Central'.
	- Look at the 'Mercurial_Type'
*/

-- Populate data for [Bug_Details]:
insert into FireFixDB_v2.dbo.Bug_Details
           ([ID]
           ,[Title]
           ,[Description]
           ,[Product]
           ,[Component]
           ,[Status]
           ,[Resolution]
           ,[Resolved_Comment_Datetime]
           ,[User_Story]
           ,[Inserted_On])
select distinct
	b.id,
	b.bug_title,
	b.bug_description,
	b.product,
	b.component,
	b.status,
	b.resolution,
	b.resolved_comment_datetime,
	b.user_story,
	b.inserted_on
from ResearchDatasets.dbo.Bugzilla b
inner join ResearchDatasets.dbo.Bugzilla_Mozilla_Changeset_BugIds cb on cb.Bug_ID = b.id
inner join ResearchDatasets.dbo.Bugzilla_Mozilla_Changesets c on cb.Changeset_Hash_ID = c.Hash_Id
where (b.alias not like 'CVE%' or b.alias is null)
	and c.Mercurial_Type like '%mozilla-central%'
    and b.status is in('VERIFIED','RESOLVED');

-- Populate data for [Changeset_Bug_Mapping]:
INSERT INTO [FireFixDB_v2].[dbo].[Changeset_Bug_Mapping]
    ([Changeset_Hash_ID]
    ,[Bug_ID])
select distinct
	m.Changeset_Hash_ID,
	m.Bug_ID
from ResearchDatasets.dbo.Bugzilla_Mozilla_Changeset_BugIds m
inner join [FireFixDB_v2].[dbo].Bug_Details b on b.ID = m.Bug_ID
where m.[Type] = 'InTitle';

-- Populate data for [Changeset_Details]:
INSERT INTO [FireFixDB_v2].[dbo].[Changeset_Details]
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
inner join [FireFixDB_v2].dbo.Changeset_Bug_Mapping m on m.Changeset_Hash_ID = c.Hash_Id
where c.Is_Backed_Out_Changeset = 0
	and c.Backed_Out_By is null
	and c.Backout_Hashes is null
	and c.Parent_Hashes not like '%|%';

-- Populate data for [Changeset_Files]:
INSERT INTO [FireFixDB_v2].[dbo].[Changeset_Files]
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
FROM [FireFixDB_v2].[dbo].[Changeset_Details] c
INNER JOIN ResearchDatasets.dbo.Bugzilla_Mozilla_Changeset_Files f ON f.Changeset_Hash_ID = c.Hash_ID
WHERE (
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
INSERT INTO [FireFixDB_v2].[dbo].[Changeset_Git_Mapping]
	([Changeset_Hash_ID]
	,[Git_Commit_ID])
select distinct
	c.Hash_ID,
	NULL
from [FireFixDB_v2].dbo.Changeset_Details c;