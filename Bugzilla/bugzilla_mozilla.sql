/*
Notes:
- changeset hashes need to combined with either github url or hg url (focus on hg for now) -- Done
- For github commit url. Add .patch after the hashes enable us to view raw file. -- Done
- View raw github files:
	https://raw.githubusercontent.com/.../<commit_hash_id>/<file_path>
- What if the function name changed? What if 


Potential improvement of the crawlers:
1. Better capture of changeset links [Completed]
	- Current: Collect all the links from the last resolved comments.
	- Improvement: Collect all the hash ids from every comments. After that, when processing each changesets, just validate to make sure the Bug id in changeset matched with the bug id in the database that contains this hash ids.
2. Automatically toggle modes between 'Regular' <-> 'History Mode' (Only at the earlier stage. Like if offset value is less than 13708) [Not Started - Low priority]
	- Current: This requires human intervention.
	- Improvement: If failed, reduce limit to 200 and continue, if failed again, switch to 'History' mode with limit=200 for 3 iterations and switch back to 'Regular' mode.
3. Add ticket open datetime.
*/

/*
Current max bug id at 6/9/2024: 1,901,449
Crawler 1: from 0 to 475,362 (Offset: 0 - 464886)
Crawler 2: from 475,363 to 950,725 (Offset: 464887 - 887441)
Crawler 3: from 950,726 to 1,426,088 (Offset: 887442 - 1316182)
Crawler 4: from 1,426,089 to The End (Offset: 1316183 - End)
*/
--Good example of a specific bugzilla:
select * from Bugzilla where id='1507218';

SELECT top 1000* FROM Bugzilla order by id desc;
SELECT * FROM Bugzilla where alias like '%CVE%' and potential_hashes like '%FINISHED_CHANGESET_HASHES_CRAWLING |' and product='Firefox';

SELECT top 1 id AS Crawler1_TOP1_0_475362 FROM Bugzilla WHERE id <= 475362 order by id desc;
SELECT top 1 id AS Crawler2_TOP1_475363_950725 FROM Bugzilla WHERE id >= 475363 and id <= 950725 order by id desc;
SELECT top 1 id AS Crawler3_TOP1_950726_1426088 FROM bugzilla where id >= 950726 and id <= 1426088 order by id desc;
SELECT top 1 id AS Crawler4_TOP1_1426089_End FROM bugzilla where id >= 1426089 order by id desc;

--Count total number of records has been done for each crawlers:

-- Check error log:
SELECT inserted_on AS Bugzilla_Error_Log,* FROM Bugzilla_Error_Log
WHERE inserted_on > '2024-06-10 02:53:35.143' -- Anything before this datetime belongs to `Bugzilla_legacy`
ORDER BY inserted_on DESC;

/*
CHANGESET_HASHES_CRAWLING:
	- Current unprocessed records: 715,878 / 8 = 89485
	- Divided by 8: ids = 481297, 695640, 893283, 1078513, 1271095, 1479057, 1675789
*/
-- Get ids for all the unprocessed hashes crawling:
SELECT count(id) FROM Bugzilla
WHERE (
		potential_hashes NOT LIKE '%FINISHED_CHANGESET_HASHES_CRAWLING |'
		OR potential_hashes IS NULL
		)
	AND resolution = 'FIXED'




--------------------------------------------------
--------------------------------------------------
/* CRAWLING FOR CHANGESET_LINKS (ONLY HG LINKS) */
--------------------------------------------------
--------------------------------------------------

--TODO: Divide into 8 processes
/* Get unprocessed records of crawling for changeset links */
--SELECT count(id)
SELECT id, potential_hashes, changeset_links
FROM Bugzilla
--UPDATE Bugzilla set changeset_links=null
WHERE resolution = 'FIXED'
AND (
	potential_hashes <> ' | FINISHED_CHANGESET_HASHES_CRAWLING |'
	AND potential_hashes IS NOT NULL
	AND potential_hashes LIKE '%FINISHED_CHANGESET_HASHES_CRAWLING |'
	)
AND (changeset_links is null OR changeset_links not like '%FINISHED_CHANGESET_LINKS_CRAWLING |')
AND id BETWEEN 38 AND 42
ORDER BY id asc; 

SELECT id, potential_hashes, changeset_links
FROM Bugzilla where changeset_links like '% | FINISHED_CHANGESET_LINKS_CRAWLING |'






--------------------------------------------------
--------------------------------------------------
/* CRAWLING FOR COMMIT LISTS (ONLY MOZILLA CENTRAL FOR NOW) */
--------------------------------------------------
--------------------------------------------------
--TODO: Process of changeset links found in the comments as well (Blocker: Rayhan set up crawlers to crawl for changeset links first)
--TODO: Another way to find backout hashes is in the [Changeset_Summary], no need to make any external API requests.
--TODO: After updated Backout_Hashes, for any records that doesn't have at least one back out hash, manually check it

select count(*) from Bugzilla_Mozilla_Changesets;
--delete from Bugzilla_Mozilla_Changesets;


-- Get all back out commits with at least some bug ids:
-- Divide 6 processes (each handles 5888 records):
	-- [6606, 12536], [12537, 18435], [18436, 24505], [24506, 30437], [30438, 36782], [36783, 42177]
WITH Q1 AS(
	SELECT ROW_NUMBER() OVER(ORDER BY Hash_Id ASC) AS Row_Num, Hash_Id, Changeset_Link, Backout_Hashes FROM Bugzilla_Mozilla_Changesets
	WHERE Is_Backed_Out_Changeset = 1
	AND Bug_Ids <> ''
)
SELECT Row_Num, Hash_Id, Changeset_Link, Backout_Hashes from Q1
WHERE 1=1 
AND Backout_Hashes IS NULL -- Include records have not been processes
--AND Backout_Hashes IS NOT NULL -- Include records have been processes
--AND Row_Num BETWEEN 6606 AND 6608
ORDER BY Row_Num ASC; 



--------------------------------------------------
--------------------------------------------------
/* CRAWLING FOR ALL THE PROPERTIES/CONTENTS IN EACH CHANGESET (IGNORE BACKED OUT BUGS AND BACKED OUT CHANGESETS) */
--------------------------------------------------
--------------------------------------------------
-- Blocker: (1) Wait until the crawlers finished processing Backout_Hashes. (2) going through records that [Does_Required_Human_Inspection] = 1.
-- TODO: Get parent hashes in [Bugzilla].[changeset_links].
-- TODO: Get parent child hashes in [Bugzilla_Mozilla_Changesets].
-- Algorithm note: 
	-- Double check to ensure the commit isn't backed out.
	-- Check if the bug related to this commit is fixed and resolved.

-- Obtains list of changeset in [Bugzilla_Mozilla_Changesets]:
/*
Total unprocessed records: 520014 / 8 = 65001
	1. [22754, 34123]
	2. [34124, 45454]
	3. [45455, 56826]
	4. [56827, 68247]
	5. [68248, 102219]
	6. [102220, 113591]
	7. [113592, 124900]
	8. [124901, 136281]
	9. [136282, 147593]
   10. [147594, 181750]
*/
WITH Q1 AS (
	SELECT ROW_NUMBER() OVER(ORDER BY Hash_Id ASC) AS Row_Num
		,Hash_Id
		,Bug_Ids
		,Changeset_Link
		,Parent_Hashes
		,Child_Hashes
		,Backed_Out_By
		,Task_Group
	FROM Bugzilla_Mozilla_Changesets
	WHERE (Bug_Ids IS NOT NULL AND Bug_Ids <> '' AND Bug_Ids <> '0') -- No association to any bugs.
		AND Is_Backed_Out_Changeset = '0' -- Already been processed
)
SELECT Row_Num, Hash_Id, Bug_Ids, Changeset_Link, Parent_Hashes, Child_Hashes, Backed_Out_By, Task_Group
FROM Q1
WHERE 1=1
AND (Backed_Out_By IS NULL OR Backed_Out_By = '')
AND Parent_Hashes IS NOT NULL -- Include records have been processed.
--AND Parent_Hashes IS NULL -- Include records have not been processed.
AND Task_Group = 4
--AND Row_Num BETWEEN 0 AND 4000000
ORDER BY Row_Num asc;

-- Get top 2 changeset that have the most count of file changes:
SELECT top 2 Changeset_Hash_ID, COUNT(*) AS RecordCount
FROM Bugzilla_Mozilla_Changeset_Files
GROUP BY Changeset_Hash_ID
order by RecordCount desc;

select * from Bugzilla_Mozilla_Changesets where Hash_Id='000bf107254d873d4a1d1d0401274b97b5ce9ac8'
select * from Bugzilla_Mozilla_Changeset_Files where Changeset_Hash_ID='000bf107254d873d4a1d1d0401274b97b5ce9ac8'

select count(*) from Bugzilla_Mozilla_Changeset_Files;
select count(distinct changeset_hash_id) from bugzilla_mozilla_changeset_files;






--------------------------------------------------
--------------------------------------------------
/* Extract data from [Bugzilla].[changeset_links] column into [Bugzilla_Mozilla_Comment_Changeset_Links] table */
--------------------------------------------------
--------------------------------------------------
--query to break and extract data from changeset_links column and insert into `Bugzilla_Mozilla_Comment_Changeset_Links`
WITH ChangesetLinks AS (
    SELECT changeset_links
    FROM [ResearchDatasets].[dbo].[Bugzilla]
    WHERE changeset_links LIKE '%hg.mozilla%'
),
ParsedLinks AS (
    SELECT
        changeset_links,
        CAST(NULL AS VARCHAR(MAX)) AS hash_id,
        CAST(NULL AS VARCHAR(MAX)) AS mercurial_type,
        CAST(NULL AS VARCHAR(MAX)) AS full_hg_link,
        changeset_links + '|' AS remaining_links -- Add delimiter to the end to simplify parsing
    FROM ChangesetLinks
    UNION ALL
    SELECT
        pl.changeset_links,
        CASE
            WHEN CHARINDEX('hg.mozilla.org/', pl.remaining_links) > 0 AND CHARINDEX('/rev/', pl.remaining_links) > CHARINDEX('hg.mozilla.org/', pl.remaining_links) + 15
            THEN LEFT(
                SUBSTRING(
                    pl.remaining_links,
                    CHARINDEX('/rev/', pl.remaining_links) + 5,
                    LEN(pl.remaining_links)
                ),
                PATINDEX('%[^a-zA-Z0-9]%', SUBSTRING(
                    pl.remaining_links,
                    CHARINDEX('/rev/', pl.remaining_links) + 5,
                    LEN(pl.remaining_links)
                )) - 1
            )
            ELSE NULL
        END AS hash_id,
        CASE
            WHEN CHARINDEX('hg.mozilla.org/', pl.remaining_links) > 0 AND CHARINDEX('/rev/', pl.remaining_links) > CHARINDEX('hg.mozilla.org/', pl.remaining_links) + 15
            THEN SUBSTRING(
                pl.remaining_links,
                CHARINDEX('hg.mozilla.org/', pl.remaining_links) + 15,
                CHARINDEX('/rev/', pl.remaining_links) - (CHARINDEX('hg.mozilla.org/', pl.remaining_links) + 15)
            )
            ELSE NULL
        END AS mercurial_type,
        CASE
            WHEN CHARINDEX('http', pl.remaining_links) > 0 AND CHARINDEX(' |', pl.remaining_links, CHARINDEX('http', pl.remaining_links)) > CHARINDEX('http', pl.remaining_links)
            THEN LEFT(
                SUBSTRING(
                    pl.remaining_links,
                    CHARINDEX('http', pl.remaining_links),
                    LEN(pl.remaining_links)
                ),
                PATINDEX('%[^a-zA-Z0-9:/._-]%', SUBSTRING(
                    pl.remaining_links,
                    CHARINDEX('http', pl.remaining_links),
                    LEN(pl.remaining_links)
                )) - 1
            )
            ELSE NULL
        END AS full_hg_link,
        CASE
            WHEN CHARINDEX(' |', pl.remaining_links, CHARINDEX('/rev/', pl.remaining_links) + 5) > 0
            THEN SUBSTRING(
                pl.remaining_links,
                CHARINDEX(' |', pl.remaining_links, CHARINDEX('/rev/', pl.remaining_links) + 5) + 2,
                LEN(pl.remaining_links)
            )
            ELSE ''
        END AS remaining_links
    FROM ParsedLinks pl
    WHERE CHARINDEX('/rev/', pl.remaining_links) > 0 AND CHARINDEX('hg.mozilla.org/', pl.remaining_links) > 0
)
INSERT INTO [dbo].[Bugzilla_Mozilla_Comment_Changeset_Links] (Hash_ID, Changeset_Links, Mercurial_Type, Full_Link)
SELECT
    hash_id,
    changeset_links,
    mercurial_type,
    full_hg_link
FROM ParsedLinks
WHERE hash_id IS NOT NULL
ORDER BY changeset_links, hash_id
OPTION (MAXRECURSION 0);


with q1 as (
SELECT Hash_ID, COUNT(hash_id) as [count]
FROM [dbo].[Bugzilla_Mozilla_Comment_Changeset_Links]
group by Hash_ID
)
select * from q1
where [count] > 1
order by [count] desc

----------------------------------------------------------------------------------------------
----------------------------------------------------------------------------------------------
/* WORKING AREA */


-- TODO: Check error log:
SELECT inserted_on AS Bugzilla_Error_Log,* FROM Bugzilla_Error_Log
WHERE inserted_on > '2024-06-10 02:53:35.143' -- Anything before this datetime belongs to `Bugzilla_legacy`
ORDER BY inserted_on DESC;

-- TODO: Go through each of the changeset that have the keyword backed out in the summary but Backout_Hashes is empty
select hash_id, changeset_summary, Backout_Hashes from Bugzilla_Mozilla_Changesets where bug_ids = '' and changeset_summary like '%back%out%';

-- TODO: Handle cases when the filename is renamed (compare with the same filename at the 'tip' changeset, if different, backtracking until we find the match fileName.


-- Testing records:
select * from Bugzilla_Mozilla_Changesets where Hash_Id='26cce0d3e1030a3ede35b55e257dcf1e36539153' -- Test case for deleted, new, renamed, copied file names
select * from Bugzilla_Mozilla_Changesets where Hash_Id='4b02380c0bbb5151f1a1f4606c29f2a1cbb70225' -- Test case for 'backed out by' changeset (4b02380c0bbb5151f1a1f4606c29f2a1cbb70225)


select * from Bugzilla_Mozilla_Changeset_Files --cpp, py, js, cc?
where Updated_File_Name like '%.py'

select * from Bugzilla_Mozilla_Changesets where hash_id='0f16abb82c08d5033af4caea5f21a48fb5c267b2'

select * from Bugzilla_Mozilla_Changesets where hash_id like '6cb490697a27%'

select * from Bugzilla_Mozilla_Changeset_Files where Changeset_Hash_ID='18bb5c07a3b7402ff1263f8ecd47f07fd86052d0'


