/*
Notes:
-changeset hashes need to combined with either github url or bugzilla url.
-For github commit url. Add .patch after the hashes enable us to view raw file.
-View raw github files:
	https://raw.githubusercontent.com/.../<commit_hash_id>/<file_path>

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
--3f6036fb9dca03914f3c6466e34d70d231487108 | 1323452 | 904bf9addd03b03d4cad11b82f19f43d875b7f27 | 8834370 | b180354560dd | 8811210 | 791597 | 1296837 | 20161208153507 | 1313759 | b52932a0811b | 3f6036fb9dca | 20170220070057 | FINISHED_CHANGESET_HASHES_CRAWLING |
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
--AND (id >= 0 AND id <= 1000)
ORDER BY id desc; 






--------------------------------------------------
--------------------------------------------------
/* CRAWLING FOR COMMIT LISTS (ONLY MOZILLA CENTRAL FOR NOW) */
--------------------------------------------------
--------------------------------------------------

select count(*) from Bugzilla_Mozilla_ShortLog;
--delete from Bugzilla_Mozilla_ShortLog;


-- Get all back out commits with at least some bug ids:
-- Divide 6 processes (each handles 5888 records):
	-- [6606, 12536], [12537, 18435], [18436, 24505], [24506, 30437], [30438, 36782], [36783, 42177]
WITH Q1 AS(
	SELECT ROW_NUMBER() OVER(ORDER BY Hash_Id ASC) AS Row_Num, Hash_Id, Commit_Link, Backout_Hashes FROM Bugzilla_Mozilla_ShortLog
	WHERE Is_Backed_Out_Commit = 1
	AND Bug_Ids <> ''
)
SELECT Hash_Id, Commit_Link, Row_Num, Backout_Hashes from Q1
WHERE 1=1 
AND Backout_Hashes IS NULL -- Include records have not been processes
--AND Backout_Hashes IS NOT NULL -- Include records have been processes
--AND Row_Num BETWEEN 6606 AND 6608
ORDER BY Row_Num ASC; 





--------------------------------------------------
--------------------------------------------------
/* CRAWLING FOR CHANGESET PARENT CHILD HASHES IN EACH CHANGESET (IGNORE BACKED OUT BUGS AND BACKED OUT CHANGESETS */
--------------------------------------------------
--------------------------------------------------
--TODO: Process of changeset links found in the comments as well (Blocker: Rayhan set up crawlers to crawl for changeset links first)
--TODO: Another way to find backout hashes is in the [Commit_Summary], no need to make any external API requests.
--TODO: After updated Backout_Hashes, for any records that doesn't have at least one back out hash, manually check it

-- Obtains list of changeset record to process from Bugzilla_Mozilla_ShortLog:
	-- Each 'hash_id' could have multiple bug ids. So, if the bug is not 'fixed', then don't consider.
SELECT hash_id, Bug_Ids 
FROM Bugzilla_Mozilla_ShortLog
--JOIN Bugzilla ON
WHERE (Backed_Out_By IS NULL OR Backed_Out_By = '')
	AND (Bug_Ids IS NOT NULL AND Bug_Ids <> '' AND Bug_Ids <> '0')
	--AND Bug_Ids like '%1799002%'
	--AND Hash_Id='b9a4318d5c1f7c10d48cd0f49849fbd159ae623d'
	AND Is_Backed_Out_Commit = 1
ORDER BY Bug_Ids ASC
OFFSET 0 ROWS --offset
FETCH NEXT 5 ROWS ONLY; --limit





--------------------------------------------------------------------------------------- -------
----------------------------------------------------------------------------------------------
/* WORKING AREA */

/*
select * from bugzilla where id=61;
update Bugzilla
set changeset_links = 'https://just_for_testing.com/ | FINISHED_CHANGESET_LINKS_CRAWLING |'
where id='61' and (changeset_links is null or changeset_links not like '%FINISHED_CHANGESET_LINKS_CRAWLING |')
*/



-- Check error log:
SELECT inserted_on AS Bugzilla_Error_Log,* FROM Bugzilla_Error_Log
WHERE inserted_on > '2024-06-10 02:53:35.143' -- Anything before this datetime belongs to `Bugzilla_legacy`
ORDER BY inserted_on DESC;
