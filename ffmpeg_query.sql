/* Note(s):
- Code messages are embedded in {{{ }}}. Removed the records or just remove the non-english words?
- What about descriptions contains links? Removed records or just remove non-english words?
- Note, at the moment, no commit has .c file with `File_Index`=='0000000000', which means no .c file has been deleted
- Only include on .c files, not yet other files.
- Not include .c file with weird function names.
- We need to consider that the bug fixes datetime must be greater than the 'enhancement' tickets.
*/

select ID, Hash_ID from FFmpeg
where 1=1
and [Status]='closed' --Have different resolution values
and [Resolution] ='fixed' --More reliable field than Status=closed
and [Hash_ID] is not null
--and Component <> 'documentation' --Just documentation, not code
--and [Description] is null
--and [Description] not like '%{{{%}}}%' 
--and [Description] not like '%http%' 
--and LEN([Description]) >= 6 --Description has at least 6 characters or above
--and id='11001'
order by id asc;


select count(ID) from FFmpeg
where 1=1
and [Status]='closed' --Have different resolution values
and [Resolution] ='fixed' --More reliable field than Status=closed
and [Hash_ID] is not null;

select count(distinct ticket_id)
from FFmpreg_Commit_Diff;


select top 10 * from FFmpreg_Commit_Diff
where ticket_id=9502
order by inserted_on desc;

/*
 * TODO: This query get all the relevant id and hash_id exists in 'FFmpeg', but not in 'FFmpreg_Commit_Diff'.
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
    FROM FFmpreg_Commit_Diff
);

-- Get distinct FFmpreg_Commit_Diff record's indices if their indices do not exists in FFmpeg_Functions table:
--SELECT DISTINCT c.[File_Prev_Index], c.[File_Index]
SELECT c.*
FROM FFmpreg_Commit_Diff AS c
LEFT JOIN FFmpeg_Functions AS f
    ON c.File_Prev_Index = f.File_Prev_Index
    AND c.File_Index = f.File_Index
WHERE f.File_Prev_Index IS NULL
    AND f.File_Index IS NULL
    AND RIGHT(c.File_Name, 2) = '.c'
	--AND c.File_Prev_Index = 'f3183b2698'
	--AND c.File_Index= '0000000000'
ORDER By c.File_Prev_Index ASC;


select *
from FFmpreg_Commit_Diff cd
inner join FFmpeg_Functions ff on ff.File_Prev_Index = cd.File_Prev_Index and ff.File_Index = cd.File_Index