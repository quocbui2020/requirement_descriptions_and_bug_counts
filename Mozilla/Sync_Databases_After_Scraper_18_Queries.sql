-- Create unique identifier for Bugzilla_Mozilla_Changeset_Files by SHA_256, should have done this earlier:
IF NOT EXISTS (SELECT TOP 1 1 FROM INFORMATION_SCHEMA.COLUMNS where TABLE_NAME='Bugzilla_Mozilla_Changeset_Files' AND COLUMN_NAME = 'Unique_Hash')
BEGIN
	ALTER TABLE ResearchDatasets.dbo.Bugzilla_Mozilla_Changeset_Files
	ADD Unique_Hash AS HASHBYTES('SHA2_256', 
		CONCAT(Changeset_Hash_ID, Previous_File_Name, Updated_File_Name));

	CREATE UNIQUE INDEX UX_Bugzilla_Mozilla_Changeset_Files_Hash
	ON ResearchDatasets.dbo.Bugzilla_Mozilla_Changeset_Files (Unique_Hash);
END


-------------------------------------------------------------------------------------------------------
-------------------------------------------------------------------------------------------------------
-------------------------------------------------------------------------------------------------------


-- Check [Bugzilla_Mozilla_Comment_Changeset_Links] that have not been processed in 'ResearchDatasets'
SELECT rd_tccfp.Task_Group, count(rd_tccfp.id) as [Temp_Comment_Changesets_For_Process Count], count(rd_bmccl.id) as [Bugzilla_Mozilla_Comment_Changeset_Links Count]
FROM ResearchDatasets.dbo.Bugzilla_Mozilla_Comment_Changeset_Links rd_bmccl
INNER JOIN ResearchDatasets.dbo.Temp_Comment_Changesets_For_Process rd_tccfp on rd_tccfp.Q1_ID = rd_bmccl.ID
where 1=1
and rd_tccfp.Process_Status is null
and rd_bmccl.Is_Processed = 0
group by rd_tccfp.Task_Group
order by rd_tccfp.Task_Group asc;

-- Check [Bugzilla_Mozilla_Comment_Changeset_Links] that have been processed in 'ResearchDatasets_Lab'
SELECT rdl_tccfp.Task_Group, count(rdl_tccfp.id) as [Temp_Comment_Changesets_For_Process Count], count(rdl_bmccl.id) as [Bugzilla_Mozilla_Comment_Changeset_Links Count]
FROM ResearchDatasets_Lab.dbo.Bugzilla_Mozilla_Comment_Changeset_Links rdl_bmccl
INNER JOIN ResearchDatasets_Lab.dbo.Temp_Comment_Changesets_For_Process rdl_tccfp on rdl_tccfp.Q1_ID = rdl_bmccl.ID
where 1=1
and rdl_tccfp.Process_Status is not null
and rdl_bmccl.Is_Processed = 1 
group by rdl_tccfp.Task_Group
order by rdl_tccfp.Task_Group asc;


-- Check [Bugzilla_Mozilla_Changesets] that have been processed in 'ResearchDatasets':
select count(*)
from ResearchDatasets.dbo.Bugzilla_Mozilla_Changesets c
inner join ResearchDatasets.dbo.Temp_Comment_Changesets_For_Process t on t.Q2_Hash_Id = c.Hash_Id and t.Task_Group between 9 and 13
where 1=1
--and c.Bug_Ids like '%:%'
and c.Bug_Ids not like '%:%'
and (c.Bug_Ids = '' or c.Bug_Ids is null) 
;
-- Check [Bugzilla_Mozilla_Changesets] that have been processed in 'ResearchDatasets_Lab':
select count(*)
from ResearchDatasets_Lab.dbo.Bugzilla_Mozilla_Changesets c
inner join ResearchDatasets_Lab.dbo.Temp_Comment_Changesets_For_Process t on t.Q2_Hash_Id = c.Hash_Id and t.Task_Group between 9 and 13
where 1=1
and c.Bug_Ids like '%:%'
--and c.Bug_Ids not like '%:%'
;

-- Queries to check the total records of Bugzilla_Mozilla_Changeset_Files for ResearchDatasets
select distinct rdl_f.* 
from ResearchDatasets.dbo.Bugzilla_Mozilla_Changeset_Files rdl_f
inner join ResearchDatasets.dbo.Bugzilla_Mozilla_Changesets rdl_c on rdl_f.Changeset_Hash_ID = rdl_c.Hash_Id
inner join ResearchDatasets.dbo.Temp_Comment_Changesets_For_Process rdl_t on rdl_t.Q2_Hash_Id = rdl_c.Hash_Id AND rdl_t.Task_Group between 9 and 13
order by rdl_f.Changeset_Hash_ID;
-- (distinct 1,411,303 records - Before the merge. After the merge, expected to have same records as query below)

-- Queries to check the total records of Bugzilla_Mozilla_Changeset_Files for ResearchDatasets_Lab
select distinct rdl_f.* 
from ResearchDatasets_Lab.dbo.Bugzilla_Mozilla_Changeset_Files rdl_f
inner join ResearchDatasets_Lab.dbo.Bugzilla_Mozilla_Changesets rdl_c on rdl_f.Changeset_Hash_ID = rdl_c.Hash_Id
inner join ResearchDatasets_Lab.dbo.Temp_Comment_Changesets_For_Process rdl_t on rdl_t.Q2_Hash_Id = rdl_c.Hash_Id AND rdl_t.Task_Group between 9 and 13
order by rdl_f.Changeset_Hash_ID;
-- (distinct 1,751,789 records)


-- Query check to see if any records has not been merged:
select *
from ResearchDatasets_Lab.dbo.Temp_Comment_Changesets_For_Process t
inner join ResearchDatasets_Lab.dbo.Bugzilla_Mozilla_Changesets c on c.Hash_Id = t.Q2_Hash_Id
where t.Task_Group between 9 and 13
and Complete_Merge is null;
--------------------------------------------------------------------------------------------------------
--------------------------------------------------------------------------------------------------------
--------------------------------------------------------------------------------------------------------
--------------------------------------------------------------------------------------------------------

--/*
begin transaction; --rollback;

-- 1. Merge [Temp_Comment_Changesets_For_Process]:
update ResearchDatasets.dbo.Temp_Comment_Changesets_For_Process
set Process_Status = rdl.Process_Status,
	Is_Finished_Process = rdl.Is_Finished_Process,
	Q2_Hash_Id = rdl.Q2_Hash_Id
FROM ResearchDatasets.dbo.Temp_Comment_Changesets_For_Process AS main
INNER JOIN ResearchDatasets_Lab.dbo.Temp_Comment_Changesets_For_Process as rdl ON main.ID = rdl.ID
where rdl.Task_Group between 9 and 13;

-- 2. Merge [Temp_Comment_Changesets_For_Process]:
UPDATE ResearchDatasets.dbo.Bugzilla_Mozilla_Comment_Changeset_Links
SET Hash_ID = rdl_bmccl.Hash_ID
	,Is_Valid_Link = rdl_bmccl.Is_Valid_Link
	,Is_Processed = rdl_bmccl.Is_Processed
FROM ResearchDatasets.dbo.Bugzilla_Mozilla_Comment_Changeset_Links main
INNER JOIN ResearchDatasets_Lab.dbo.Bugzilla_Mozilla_Comment_Changeset_Links rdl_bmccl ON rdl_bmccl.ID = main.ID
INNER JOIN ResearchDatasets_Lab.dbo.Temp_Comment_Changesets_For_Process rdl_tccfp ON rdl_tccfp.Q1_ID = rdl_bmccl.ID
WHERE rdl_tccfp.Task_Group BETWEEN 9 AND 13;

-- 3.Merge [Bugzilla_Mozilla_Changesets]:
-- Update [Complete_Merge]=1 from query above:
update ResearchDatasets_Lab.dbo.Bugzilla_Mozilla_Changesets
set [Complete_Merge]=1
FROM ResearchDatasets_Lab.dbo.Bugzilla_Mozilla_Changesets rdl_bmc
INNER JOIN ResearchDatasets_Lab.dbo.Temp_Comment_Changesets_For_Process rdl_tccfp ON rdl_tccfp.Q2_Hash_Id = rdl_bmc.Hash_Id
LEFT JOIN ResearchDatasets.dbo.Bugzilla_Mozilla_Changesets main ON rdl_bmc.Hash_Id = main.Hash_Id
WHERE main.Hash_Id IS NULL
;
-- 3.1. Merge records that exist in [ResearchDatasets_Lab], but don't exists in [ResearchDatasets]:
INSERT INTO [ResearchDatasets].[dbo].[Bugzilla_Mozilla_Changesets]
    ([Hash_Id]
    ,[Changeset_Summary]
    ,[Bug_Ids]
    ,[Changeset_Link]
    ,[Mercurial_Type]
    ,[Changeset_Datetime]
    ,[Is_Backed_Out_Changeset]
    ,[Backed_Out_By]
    ,[Backout_Hashes]
    ,[Parent_Hashes]
    ,[Child_Hashes]
    ,[Inserted_On]
    ,[Task_Group]
    ,[Modified_On])
SELECT DISTINCT
    rdl_bmc.Hash_Id,
    rdl_bmc.Changeset_Summary,
    rdl_bmc.Bug_Ids,
    rdl_bmc.Changeset_Link, -- Empty string
    rdl_bmc.Mercurial_Type,
    rdl_bmc.Changeset_Datetime,
    rdl_bmc.Is_Backed_Out_Changeset,
    rdl_bmc.Backed_Out_By,
    rdl_bmc.Backout_Hashes,
    rdl_bmc.Parent_Hashes,
    rdl_bmc.Child_Hashes,
    rdl_bmc.Inserted_On,
    rdl_bmc.Task_Group,
    rdl_bmc.Modified_On
FROM ResearchDatasets_Lab.dbo.Bugzilla_Mozilla_Changesets rdl_bmc
INNER JOIN ResearchDatasets_Lab.dbo.Temp_Comment_Changesets_For_Process rdl_tccfp ON rdl_tccfp.Q2_Hash_Id = rdl_bmc.Hash_Id
LEFT JOIN ResearchDatasets.dbo.Bugzilla_Mozilla_Changesets main ON rdl_bmc.Hash_Id = main.Hash_Id
WHERE main.Hash_Id IS NULL
;


-- 3.2. Transform Bug_Ids to include ":InTitle" after each bug ids in [ResearchDatasets]:
WITH q1 AS (
    SELECT DISTINCT q2_hash_id
    FROM ResearchDatasets.dbo.Temp_Comment_Changesets_For_Process
    WHERE Task_Group BETWEEN 9 AND 13
)
UPDATE main_bmc
SET Bug_Ids = (
    SELECT STRING_AGG(CONCAT(LTRIM(RTRIM(value)), ':InTitle'), ' | ') 
    FROM STRING_SPLIT(main_bmc.Bug_Ids, '|') -- Split on just the pipe character
)
FROM ResearchDatasets.dbo.Bugzilla_Mozilla_Changesets main_bmc
INNER JOIN q1 ON q1.q2_hash_id = main_bmc.Hash_Id
WHERE main_bmc.Bug_Ids IS NOT NULL 
  AND main_bmc.Bug_Ids <> '';
-- (216563 rows affected)


-- 3.3. Merge records that exist in [ResearchDatasets_Lab] and exists in [ResearchDatasets]:
WITH RecordsNeedToBeMerged
AS (
	SELECT DISTINCT rdl_bmc.Hash_Id
		,rdl_bmc.Bug_Ids AS [Rdl_Bug_Ids]
		,rdl_bmc.Mercurial_Type AS [Rdl_Mercurial_Type]
		,rdl_bmc.Modified_On AS [Rdl_Modified_On]
	FROM ResearchDatasets_Lab.dbo.Bugzilla_Mozilla_Changesets rdl_bmc
	INNER JOIN ResearchDatasets_Lab.dbo.Temp_Comment_Changesets_For_Process rdl_tccfp ON rdl_tccfp.Q2_Hash_Id = rdl_bmc.Hash_Id
		AND rdl_tccfp.Task_Group BETWEEN 9
			AND 13
		AND rdl_tccfp.Q2_Hash_Id IS NOT NULL -- Cases when process status='Failed Url - Human Intervention' or 'Processed: 404'
	WHERE rdl_bmc.Complete_Merge IS NULL
	)
	,CombinedTable
AS (
	SELECT DISTINCT main_bmc.Hash_Id
		,main_bmc.Bug_Ids AS [Main_Bug_Ids]
		,main_bmc.Mercurial_Type AS [Main_Mercurial_Type]
		,main_bmc.Modified_On AS [Main_Modified_On]
		,RecordsNeedToBeMerged.Rdl_Bug_Ids
		,RecordsNeedToBeMerged.Rdl_Mercurial_Type
		,RecordsNeedToBeMerged.Rdl_Modified_On
	FROM ResearchDatasets.dbo.Bugzilla_Mozilla_Changesets main_bmc
	INNER JOIN RecordsNeedToBeMerged ON RecordsNeedToBeMerged.Hash_Id = main_bmc.Hash_Id
	WHERE 1 = 1
	)
UPDATE ResearchDatasets.dbo.Bugzilla_Mozilla_Changesets
SET Bug_Ids = (
	SELECT STUFF((
		SELECT DISTINCT ' | ' + LTRIM(RTRIM(value))
		FROM (
			-- Split Main_Bug_Ids and Rdl_Bug_Ids and combine them
			SELECT LTRIM(RTRIM(value)) AS value
			FROM STRING_SPLIT(CombinedTable.Main_Bug_Ids, '|')
						
			UNION
						
			SELECT LTRIM(RTRIM(value)) AS value
			FROM STRING_SPLIT(CombinedTable.Rdl_Bug_Ids, '|')
			) AS combined_values
		FOR XML PATH('')
			,TYPE
		).value('.', 'NVARCHAR(MAX)'), 1, 3, '')
	)
FROM CombinedTable
WHERE ResearchDatasets.dbo.Bugzilla_Mozilla_Changesets.Hash_Id = CombinedTable.Hash_Id
	--AND CombinedTable.Rdl_Bug_Ids IS NOT NULL;
-- (218956 rows affected)
;

-- Update Complete_Merge=1 for all the records processed from the query above:
WITH RecordsNeedToBeMerged
AS (
	SELECT DISTINCT rdl_bmc.Hash_Id
		,rdl_bmc.Bug_Ids AS [Rdl_Bug_Ids]
		,rdl_bmc.Mercurial_Type AS [Rdl_Mercurial_Type]
		,rdl_bmc.Modified_On AS [Rdl_Modified_On]
	FROM ResearchDatasets_Lab.dbo.Bugzilla_Mozilla_Changesets rdl_bmc
	INNER JOIN ResearchDatasets_Lab.dbo.Temp_Comment_Changesets_For_Process rdl_tccfp ON rdl_tccfp.Q2_Hash_Id = rdl_bmc.Hash_Id
		AND rdl_tccfp.Task_Group BETWEEN 9
			AND 13
		AND rdl_tccfp.Q2_Hash_Id IS NOT NULL -- Cases when process status='Failed Url - Human Intervention' or 'Processed: 404'
	WHERE rdl_bmc.Complete_Merge IS NULL
	)
	,CombinedTable
AS (
	SELECT DISTINCT main_bmc.Hash_Id
		,main_bmc.Bug_Ids AS [Main_Bug_Ids]
		,main_bmc.Mercurial_Type AS [Main_Mercurial_Type]
		,main_bmc.Modified_On AS [Main_Modified_On]
		,RecordsNeedToBeMerged.Rdl_Bug_Ids
		,RecordsNeedToBeMerged.Rdl_Mercurial_Type
		,RecordsNeedToBeMerged.Rdl_Modified_On
	FROM ResearchDatasets.dbo.Bugzilla_Mozilla_Changesets main_bmc
	INNER JOIN RecordsNeedToBeMerged ON RecordsNeedToBeMerged.Hash_Id = main_bmc.Hash_Id
	WHERE 1 = 1
	)
UPDATE ResearchDatasets_Lab.dbo.Bugzilla_Mozilla_Changesets
SET Complete_Merge = 1
FROM CombinedTable
WHERE ResearchDatasets_Lab.dbo.Bugzilla_Mozilla_Changesets.Hash_Id = CombinedTable.Hash_Id
-- (218956 rows affected)


-- 4. Merge 'Bugzilla_Mozilla_Changeset_Files':
INSERT INTO ResearchDatasets.dbo.Bugzilla_Mozilla_Changeset_Files
    (Changeset_Hash_ID, Previous_File_Name, Updated_File_Name, File_Status, Inserted_On)
SELECT 
    rdl_f.Changeset_Hash_ID,
    rdl_f.Previous_File_Name,
    rdl_f.Updated_File_Name,
    rdl_f.File_Status,
    rdl_f.Inserted_On
FROM ResearchDatasets_Lab.dbo.Bugzilla_Mozilla_Changeset_Files rdl_f
WHERE NOT EXISTS (
    SELECT 1
    FROM ResearchDatasets.dbo.Bugzilla_Mozilla_Changeset_Files main_f
    WHERE main_f.Changeset_Hash_ID = rdl_f.Changeset_Hash_ID
    AND main_f.Previous_File_Name = rdl_f.Previous_File_Name
    AND main_f.Updated_File_Name = rdl_f.Updated_File_Name
);

rollback; --commit; --begin transaction;
--*/

--------------------------------------------------------------------------------------------------------
--------------------------------------------------------------------------------------------------------
--------------------------------------------------------------------------------------------------------
--------------------------------------------------------------------------------------------------------
