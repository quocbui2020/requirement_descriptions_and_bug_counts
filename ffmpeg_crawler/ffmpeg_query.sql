/* Note(s):
- Code messages are embedded in {{{ }}}. Removed the records or just remove the non-english words?
- What about descriptions contains links? Removed records or just remove non-english words?
- Note, at the moment, no commit has .c file with `File_Index`=='0000000000', which means no .c file has been deleted
- Only include on .c files, not yet other files.
- Not include .c file with weird function names.
- We need to consider that the bug fixes datetime must be greater than the 'enhancement' tickets.

** Dev issues:
	- Query:
		select ff.*
		FROM FFmpeg_Commit_Diff cd
		INNER JOIN FFmpeg_Functions ff ON ff.File_Prev_Index = cd.File_Prev_Index
			AND ff.File_Index = cd.File_Index
		WHERE 1 = 1
			and cd.File_Name='libavfilter/vsrc_testsrc.c' and Ticket_Id='10989' and Function_Name='zoneplate_fill_picture'
	- Didn't capture all the function name and wrong name sometimes.

Useful web links:
- https://trac.ffmpeg.org/query?max=655&order=id&status=closed&col=id&col=description&resolution=fixed&type=enhancement&format=csv
- https://git.ffmpeg.org/gitweb/ffmpeg.git/commitdiff/{hash_id}
- https://git.ffmpeg.org/gitweb/ffmpeg.git/blob_plain/{file_index}
*/
SELECT *
FROM FFmpeg
WHERE 1 = 1
	AND [Type] = 'enhancement'
	AND [Status] = 'closed' --Have different resolution values
	AND [Resolution] = 'fixed' --More reliable field than Status=closed
	AND [Hash_ID] IS NOT NULL
	AND Component <> 'documentation' --Just documentation, not code
	--AND [Description] IS NOT NULL
	--AND [Description] NOT LIKE '%{{{%}}}%'
	--AND [Description] NOT LIKE '%http%'
	--AND LEN([Description]) >= 6 --Description has at least 6 characters or above
	--AND id = '11001'
ORDER BY id ASC;


select count(ID) from FFmpeg
where 1=1
and [Status]='closed' --Have different resolution values
and [Resolution] ='fixed' --More reliable field than Status=closed
and [Hash_ID] is not null;

select count(distinct ticket_id)
from FFmpeg_Commit_Diff;


select top 10 * from FFmpeg_Commit_Diff
where ticket_id=9502
order by inserted_on desc;

/*
 * TODO: This query get all the relevant id and hash_id exists in 'FFmpeg', but not in 'FFmpeg_Commit_Diff'.
 * Therefore, we need to go through each of these records and understand why the commit doesn't have any file names.
 * Could be: Merge conflict or values are not has id.
*/
SELECT ID, FFmpeg.Hash_ID
FROM FFmpeg
WHERE [Status] = 'closed'
AND [Resolution] = 'fixed'
AND [Hash_ID] IS NOT NULL
AND ID NOT IN (
    SELECT DISTINCT ticket_id
    FROM FFmpeg_Commit_Diff
);

/*
Get distinct FFmpeg_Commit_Diff record's indices if their indices do not exists in FFmpeg_Functions table.
This query shows which commit files have not been processed to extract function names.
*/
SELECT distinct c.*
FROM FFmpeg_Commit_Diff AS c
LEFT JOIN FFmpeg_Functions AS f
    ON c.File_Prev_Index = f.File_Prev_Index
    AND c.File_Index = f.File_Index
WHERE f.File_Prev_Index IS NULL
    AND f.File_Index IS NULL
    AND RIGHT(c.File_Name, 2) = '.c'
	--AND c.File_Prev_Index = 'f3183b2698'
	--AND c.File_Index= '0000000000'
ORDER By c.File_Prev_Index ASC;

/*
Query show all function names and statuses
*/
SELECT cd.Ticket_Id
	,cd.File_Name
	,ff.Function_Name
	,ff.File_Change_Status
	,cd.*
FROM FFmpeg_Commit_Diff cd
INNER JOIN FFmpeg_Functions ff ON ff.File_Prev_Index = cd.File_Prev_Index
	AND ff.File_Index = cd.File_Index
WHERE 1 = 1
	and cd.File_Name='libavfilter/vsrc_testsrc.c' and Ticket_Id='10989'
ORDER BY cd.ticket_id DESC
	,cd.File_Name ASC
	,ff.File_Change_Status ASC;

/*
update FFmpeg_Commit_Diff
set Function_Name='test_fill_picture'
where File_Name='libavfilter/vsrc_testsrc.c' and Ticket_Id='10989' and Function_Name='e'
*/

/**/

select ff.*
FROM FFmpeg_Commit_Diff cd
INNER JOIN FFmpeg_Functions ff ON ff.File_Prev_Index = cd.File_Prev_Index
	AND ff.File_Index = cd.File_Index
WHERE 1 = 1
	and cd.File_Name='libavfilter/vsrc_testsrc.c' and Ticket_Id='10989' and Function_Name='zoneplate_fill_picture'


/*
Ultimate query: This query output associate Defect tickets to each enhancement ticket based on file name and function name.
*/
WITH EnhancementTicketQuery AS (
    SELECT 
        FFmpeg.ID as Ticket_ID,
        FFmpeg.Type as Ticket_Type,
        FFmpeg.Ticket_Created_On,
        FFmpeg_Commit_Diff.File_Name,
        FFmpeg_functions.Function_Name,
        FFmpeg_functions.File_Change_Status,
        FFmpeg_Commit_Diff.Date AS Date
    FROM 
        FFmpeg
    INNER JOIN 
        FFmpeg_Commit_Diff ON FFmpeg_Commit_Diff.Ticket_ID = FFmpeg.ID
    INNER JOIN 
        FFmpeg_functions ON FFmpeg_functions.File_Index = FFmpeg_Commit_Diff.File_Index 
                         AND FFmpeg_functions.File_Prev_Index = FFmpeg_Commit_Diff.File_Prev_Index 
    WHERE 
        FFmpeg.Type = 'enhancement'
        AND FFmpeg.Status = 'closed'
        AND FFmpeg.Resolution = 'fixed'
        AND FFmpeg.Hash_ID IS NOT NULL
        AND FFmpeg.Component <> 'documentation'
		--AND FFmpeg.ID = '896'
        AND (FFmpeg_functions.File_Change_Status = 'modified' 
             OR FFmpeg_functions.File_Change_Status = 'added')
),

DefectTicketQuery AS (
    SELECT 
        FFmpeg.ID as Ticket_ID,
        FFmpeg.Type as Ticket_Type,
        FFmpeg.Ticket_Created_On,
        FFmpeg_Commit_Diff.File_Name,
        FFmpeg_functions.Function_Name,
        FFmpeg_functions.File_Change_Status,
        FFmpeg_Commit_Diff.Date AS Date
    FROM 
        FFmpeg
    INNER JOIN 
        FFmpeg_Commit_Diff ON FFmpeg_Commit_Diff.Ticket_ID = FFmpeg.ID
    INNER JOIN 
        FFmpeg_functions ON FFmpeg_functions.File_Index = FFmpeg_Commit_Diff.File_Index 
                         AND FFmpeg_functions.File_Prev_Index = FFmpeg_Commit_Diff.File_Prev_Index 
    WHERE 
        FFmpeg.Type = 'defect'
        AND FFmpeg.Status = 'closed'
        AND FFmpeg.Resolution = 'fixed'
        AND FFmpeg.Hash_ID IS NOT NULL
        AND FFmpeg.Component <> 'documentation'
        AND (FFmpeg_functions.File_Change_Status = 'modified' 
             OR FFmpeg_functions.File_Change_Status = 'deleted')
),

JoinedQuery AS (
    SELECT 
        e.Ticket_ID AS Enhancement_Ticket_ID,
        e.Ticket_Type AS Enhancement_Type,
        e.Ticket_Created_On AS Enhancement_Ticket_Created_On,
        e.File_Name AS Enhancement_File_Name,
        e.Function_Name AS Enhancement_Function_Name,
        e.File_Change_Status AS Enhancement_File_Change_Status,
        e.Date AS Enhancement_Commit_Date,
		d.File_Name AS Defect_File_Name,
		d.Function_Name AS Defect_Function_Name,
        d.Ticket_ID AS Defect_Ticket_ID,
        d.Ticket_Type AS Defect_Type,
        d.Ticket_Created_On AS Defect_Ticket_Created_On,
        d.File_Change_Status AS Defect_File_Change_Status,
        d.Date AS Defect_Commit_Date
    FROM 
        EnhancementTicketQuery e
    INNER JOIN 
        DefectTicketQuery d ON e.File_Name = d.File_Name 
                           AND e.Function_Name = d.Function_Name
						   AND CONVERT(datetime2, SUBSTRING(e.Date, 6, 20)) < CONVERT(datetime2, SUBSTRING(d.Date, 6, 20))


/* Query to output all the functions associated between enhance and defect tickets. Each row represents each function. Again, do not includes enhancement ticket with zero bug counts.
)
SELECT
    Enhancement_Ticket_ID
    --,Enhancement_Type
    --,Enhancement_Ticket_Created_On
    ,Enhancement_File_Name AS File_Name
    ,Enhancement_Function_Name AS Function_Name
    --,Enhancement_File_Change_Status
    ,Enhancement_Commit_Date
	--,Defect_File_Name
	--,Defect_Function_Name
    ,Defect_Ticket_ID
    --,Defect_Type
    --,Defect_Ticket_Created_On
    --,Defect_File_Change_Status
	,Defect_Commit_Date
FROM JoinedQuery
order by Enhancement_Ticket_ID desc;
--*/

------------------------------------------------------------------------------------------------------------

--/* This is the correct parts to get Enhancement ticket with number of bug count.
),
DistinctQuery AS (
	SELECT DISTINCT Enhancement_Ticket_ID, Defect_Ticket_ID
	FROM JoinedQuery
)
Select DISTINCT Enhancement_Ticket_ID,
COUNT(Defect_Ticket_ID) OVER (PARTITION BY Enhancement_Ticket_ID) AS Bug_Count
from DistinctQuery
order by Enhancement_Ticket_ID desc;
--*/
