begin transaction; rollback; commit

/*
transfer data from Parent_Hashes and Child_Hashes columns in the
ResearchDatasets_b.Bugzilla_Mozilla_Changesets table where Task_Group=3 to
the ResearchDatasets.Bugzilla_Mozilla_Changesets table based on the Hash_Id column.
*/
USE ResearchDatasets;
GO
UPDATE dst
SET 
    dst.Parent_Hashes = src.Parent_Hashes,
    dst.Child_Hashes = src.Child_Hashes
FROM ResearchDatasets.dbo.Bugzilla_Mozilla_Changesets dst
INNER JOIN ResearchDatasets_b.dbo.Bugzilla_Mozilla_Changesets src
    ON dst.Hash_Id = src.Hash_Id
WHERE src.Task_Group = 3;
GO

-------------------------------------------------------------------------------
-------------------------------------------------------------------------------
/*
transfer the Backed_Out_By column value from ResearchDatasets_b to ResearchDatasets
based on Hash_Id, and only if the value in ResearchDatasets_b is not null and
the value in ResearchDatasets is null.
*/
USE ResearchDatasets;
GO
UPDATE dst
SET 
    dst.Backed_Out_By = src.Backed_Out_By
FROM ResearchDatasets.dbo.Bugzilla_Mozilla_Changesets dst
INNER JOIN ResearchDatasets_b.dbo.Bugzilla_Mozilla_Changesets src
    ON dst.Hash_Id = src.Hash_Id
WHERE src.Backed_Out_By IS NOT NULL
AND dst.Backed_Out_By IS NULL;
GO

-------------------------------------------------------------------------------
-------------------------------------------------------------------------------
/*
transfer data from the Bugzilla_Mozilla_Changeset_Files table in the ResearchDatasets_b
database to the Bugzilla_Mozilla_Changeset_Files table in the ResearchDatasets database,
using a MERGE operation to prevent identical records.
*/
USE ResearchDatasets;
GO
MERGE INTO ResearchDatasets.dbo.Bugzilla_Mozilla_Changeset_Files AS target
USING (
    SELECT 
        cf.[Changeset_Hash_ID],
        cf.[Previous_File_Name],
        cf.[Updated_File_Name],
        cf.[File_Status],
        cf.[Inserted_On]
    FROM ResearchDatasets_b.dbo.Bugzilla_Mozilla_Changesets c
    INNER JOIN ResearchDatasets_b.dbo.Bugzilla_Mozilla_Changeset_Files cf 
        ON cf.Changeset_Hash_ID = c.Hash_Id
    WHERE c.Task_Group = 3
) AS source
ON target.Changeset_Hash_ID = source.Changeset_Hash_ID
   AND target.Previous_File_Name = source.Previous_File_Name
   AND target.Updated_File_Name = source.Updated_File_Name
   AND target.File_Status = source.File_Status
   AND target.Inserted_On = source.Inserted_On
-- When not matched, insert the new record
WHEN NOT MATCHED BY TARGET THEN
    INSERT (Changeset_Hash_ID, Previous_File_Name, Updated_File_Name, File_Status, Inserted_On)
    VALUES (source.Changeset_Hash_ID, source.Previous_File_Name, source.Updated_File_Name, source.File_Status, source.Inserted_On);
GO