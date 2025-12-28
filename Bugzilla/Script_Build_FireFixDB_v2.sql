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

/*
Populate data for [Defect_Counts]
Note: This query combine the database from FireFixDB_v2 and FixFox_v2 together.
*/
with EnhacementTaskTickets AS (
	select distinct b.ID
		,b.[Type]
		,b.[Resolved_Comment_Datetime]
		,gd.Modified_File
		,gd.Modified_Function
	from FireFixDB_v2.dbo.Bug_Details b
	inner join FireFixDB_v2.dbo.Changeset_Bug_Mapping bm on bm.Bug_ID = b.ID
	inner join FireFixDB_v2.dbo.Changeset_Git_Mapping gm on gm.Changeset_Hash_ID = bm.Changeset_Hash_ID
	inner join FireFixDB_v2.dbo.Git_Commit_Details gd on gd.Git_Commit_ID = gm.Git_Commit_ID
		AND (gd.Modified_File LIKE '%.js'
			OR gd.Modified_File LIKE '%.py'
			OR gd.Modified_File LIKE '%.c'
			OR gd.Modified_File LIKE '%.cpp'
		)
	where b.[Type] in('enhancement','task')
		and b.Resolution='FIXED'

	UNION

	select distinct b.ID
		,b.[Type]
		,b.[Resolved_Comment_Datetime]
		,gd.Modified_File
		,gd.Modified_Function
	from FixFox_v2.dbo.Bug_Details b
	inner join FixFox_v2.dbo.Changeset_Bug_Mapping bm on bm.Bug_ID = b.ID
	inner join FixFox_v2.dbo.Changeset_Git_Mapping gm on gm.Changeset_Hash_ID = bm.Changeset_Hash_ID
	inner join FixFox_v2.dbo.Git_Commit_Details gd on gd.Git_Commit_ID = gm.Git_Commit_ID
		AND (gd.Modified_File LIKE '%.js'
			OR gd.Modified_File LIKE '%.py'
			OR gd.Modified_File LIKE '%.c'
			OR gd.Modified_File LIKE '%.cpp'
		)
	where b.[Type] in('enhancement','task')
		and b.Resolution='FIXED'
),
DefectTickets as (
	select distinct b.ID
		,b.[Type]
		,b.[Resolved_Comment_Datetime]
		,gd.Modified_File
		,gd.Modified_Function
	from FireFixDB_v2.dbo.Bug_Details b
	inner join FireFixDB_v2.dbo.Changeset_Bug_Mapping bm on bm.Bug_ID = b.ID
	inner join FireFixDB_v2.dbo.Changeset_Git_Mapping gm on gm.Changeset_Hash_ID = bm.Changeset_Hash_ID
	inner join FireFixDB_v2.dbo.Git_Commit_Details gd on gd.Git_Commit_ID = gm.Git_Commit_ID
		AND (gd.Modified_File LIKE '%.js'
			OR gd.Modified_File LIKE '%.py'
			OR gd.Modified_File LIKE '%.c'
			OR gd.Modified_File LIKE '%.cpp'
		)
	where b.[Type] = 'defect'
		and b.Resolution='FIXED'

	UNION

	select distinct b.ID
		,b.[Type]
		,b.[Resolved_Comment_Datetime]
		,gd.Modified_File
		,gd.Modified_Function
	from FixFox_v2.dbo.Bug_Details b
	inner join FixFox_v2.dbo.Changeset_Bug_Mapping bm on bm.Bug_ID = b.ID
	inner join FixFox_v2.dbo.Changeset_Git_Mapping gm on gm.Changeset_Hash_ID = bm.Changeset_Hash_ID
	inner join FixFox_v2.dbo.Git_Commit_Details gd on gd.Git_Commit_ID = gm.Git_Commit_ID
		AND (gd.Modified_File LIKE '%.js'
			OR gd.Modified_File LIKE '%.py'
			OR gd.Modified_File LIKE '%.c'
			OR gd.Modified_File LIKE '%.cpp'
		)
	where b.[Type] = 'defect'
		and b.Resolution='FIXED'
)
SELECT distinct
    e.ID as 'enhacement ticket ID',
	e.Resolved_Comment_Datetime as 'ehancement resolved datetime',
	d.ID as 'defect ticket ID',
	d.Resolved_Comment_Datetime as 'defect resolved datetime',
	CAST(d.Resolved_Comment_Datetime AS DATETIME) - CAST(e.Resolved_Comment_Datetime AS DATETIME) as 'Time Diff'
FROM EnhacementTaskTickets e
LEFT JOIN DefectTickets d ON d.Modified_File = e.Modified_File
    AND e.Modified_Function = d.Modified_Function
    AND CAST(e.Resolved_Comment_Datetime AS DATETIME) < CAST(d.Resolved_Comment_Datetime AS DATETIME)
	AND CAST(d.Resolved_Comment_Datetime AS DATETIME) <= DATEADD(MONTH, 6, CAST(e.Resolved_Comment_Datetime AS DATETIME)) -- comment this line for version='original'
where e.ID is not null and d.ID is not null
order by [enhacement ticket ID] desc, [defect ticket ID] desc;

-- Give me 50 random numbers from 1 to 136,928 (Make sure those random points are spread out. For example, divide each section into the length of 50, and randomly pick one from each section.