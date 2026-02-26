SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @i int = 1;
DECLARE @sql nvarchar(max);
DECLARE @auto_fix_incompatible bit = 1; -- 1 = drop/recreate incompatible shard tables if empty

WHILE @i <= 20
BEGIN
    DECLARE @filesTable sysname = N'Modified_Files_' + CAST(@i as nvarchar(10));
    DECLARE @funcsTable sysname = N'Modified_Functions_' + CAST(@i as nvarchar(10));

    DECLARE @pkFilesName sysname = N'PK_Modified_Files_' + CAST(@i as nvarchar(10));
    DECLARE @pkFuncsName sysname = N'PK_Modified_Functions_' + CAST(@i as nvarchar(10));
    DECLARE @fkFuncsToFilesName sysname = N'FK_Modified_Functions_' + CAST(@i as nvarchar(10)) + N'_Modified_Files_' + CAST(@i as nvarchar(10));

    DECLARE @filesObjId int = OBJECT_ID(N'[dbo].[' + @filesTable + N']', N'U');
    DECLARE @funcsObjId int = OBJECT_ID(N'[dbo].[' + @funcsTable + N']', N'U');

    DECLARE @filesHashLen smallint = NULL;
    DECLARE @funcsHashLen smallint = NULL;
    DECLARE @filesHasPkOnUniqueHash bit = 0;
    DECLARE @funcsHasPkOnUniqueHash bit = 0;
    DECLARE @funcsHasFunctionArguments bit = 0;
    DECLARE @filesRows bigint = 0;
    DECLARE @funcRows bigint = 0;
    DECLARE @tablesIncompatible bit = 0;

    /* 0) Detect incompatible existing schema */
    IF @filesObjId IS NOT NULL
    BEGIN
        SELECT @filesHashLen = c.max_length
        FROM sys.columns c
        WHERE c.object_id = @filesObjId
          AND c.name = N'Unique_Hash';

        SELECT @filesHasPkOnUniqueHash =
            CASE WHEN EXISTS (
                SELECT 1
                FROM sys.key_constraints kc
                JOIN sys.index_columns ic
                    ON ic.object_id = kc.parent_object_id
                   AND ic.index_id = kc.unique_index_id
                JOIN sys.columns c
                    ON c.object_id = ic.object_id
                   AND c.column_id = ic.column_id
                WHERE kc.parent_object_id = @filesObjId
                  AND kc.[type] = 'PK'
                GROUP BY kc.parent_object_id
                HAVING COUNT(1) = 1
                   AND SUM(CASE WHEN c.name = N'Unique_Hash' THEN 1 ELSE 0 END) = 1
            ) THEN 1 ELSE 0 END;

        IF @filesHashLen IS NULL OR @filesHashLen <> 50 OR @filesHasPkOnUniqueHash = 0
            SET @tablesIncompatible = 1;
    END

    IF @funcsObjId IS NOT NULL
    BEGIN
        SELECT @funcsHashLen = c.max_length
        FROM sys.columns c
        WHERE c.object_id = @funcsObjId
          AND c.name = N'Unique_Hash';

        SELECT @funcsHasFunctionArguments =
            CASE WHEN EXISTS (
                SELECT 1
                FROM sys.columns c
                WHERE c.object_id = @funcsObjId
                  AND c.name = N'Function_Arguments'
            ) THEN 1 ELSE 0 END;

        SELECT @funcsHasPkOnUniqueHash =
            CASE WHEN EXISTS (
                SELECT 1
                FROM sys.key_constraints kc
                JOIN sys.index_columns ic
                    ON ic.object_id = kc.parent_object_id
                   AND ic.index_id = kc.unique_index_id
                JOIN sys.columns c
                    ON c.object_id = ic.object_id
                   AND c.column_id = ic.column_id
                WHERE kc.parent_object_id = @funcsObjId
                  AND kc.[type] = 'PK'
                GROUP BY kc.parent_object_id
                HAVING COUNT(1) = 1
                   AND SUM(CASE WHEN c.name = N'Unique_Hash' THEN 1 ELSE 0 END) = 1
            ) THEN 1 ELSE 0 END;

        IF @funcsHashLen IS NULL OR @funcsHashLen <> 50 OR @funcsHasPkOnUniqueHash = 0 OR @funcsHasFunctionArguments = 0
            SET @tablesIncompatible = 1;
    END

    /* 0.1) Optional auto-fix for previously created incompatible schema */
    IF @tablesIncompatible = 1 AND (@filesObjId IS NOT NULL OR @funcsObjId IS NOT NULL)
    BEGIN
        IF @auto_fix_incompatible = 1
        BEGIN
            IF @filesObjId IS NOT NULL
            BEGIN
                SET @sql = N'SELECT @cnt = COUNT_BIG(1) FROM [dbo].[' + @filesTable + N'];';
                EXEC sp_executesql @sql, N'@cnt bigint OUTPUT', @cnt = @filesRows OUTPUT;
            END

            IF @funcsObjId IS NOT NULL
            BEGIN
                SET @sql = N'SELECT @cnt = COUNT_BIG(1) FROM [dbo].[' + @funcsTable + N'];';
                EXEC sp_executesql @sql, N'@cnt bigint OUTPUT', @cnt = @funcRows OUTPUT;
            END

            IF @filesRows = 0 AND @funcRows = 0
            BEGIN
                IF @funcsObjId IS NOT NULL
                BEGIN
                    SET @sql = N'DROP TABLE [dbo].[' + @funcsTable + N'];';
                    EXEC sp_executesql @sql;
                    PRINT 'Auto-dropped incompatible empty [dbo].[' + @funcsTable + ']';
                END

                IF @filesObjId IS NOT NULL
                BEGIN
                    SET @sql = N'DROP TABLE [dbo].[' + @filesTable + N'];';
                    EXEC sp_executesql @sql;
                    PRINT 'Auto-dropped incompatible empty [dbo].[' + @filesTable + ']';
                END

                SET @filesObjId = NULL;
                SET @funcsObjId = NULL;
            END
            ELSE
            BEGIN
                PRINT 'WARNING: Incompatible shard tables exist and are not empty. Skipping auto-drop for shard ' + CAST(@i as nvarchar(10));
            END
        END
        ELSE
        BEGIN
            PRINT 'WARNING: Incompatible shard tables detected. Set @auto_fix_incompatible = 1 to auto-fix if empty.';
        END
    END

    /* 1) Create Modified_Files_<n> */
    IF @filesObjId IS NULL
    BEGIN
        SET @sql = N'
        CREATE TABLE [dbo].[' + @filesTable + N'](
            [Git_commit_ID] [varchar](40) NOT NULL,
            [Previous_File_Name] [varchar](1000) NOT NULL,
            [Updated_File_Name] [varchar](1000) NOT NULL,
            [File_Status] [varchar](100) NOT NULL,
            [File_Type] [varchar](20) NOT NULL,
            [Unique_Hash] AS (
                CONVERT([varbinary](50), hashbytes(''SHA2_256'', concat([Git_commit_ID], [Previous_File_Name], [Updated_File_Name], [File_Status], [File_Type])))
            ) PERSISTED,
            CONSTRAINT [' + @pkFilesName + N'] PRIMARY KEY CLUSTERED ([Unique_Hash] ASC)
                WITH (
                    PAD_INDEX = OFF,
                    STATISTICS_NORECOMPUTE = OFF,
                    IGNORE_DUP_KEY = OFF,
                    ALLOW_ROW_LOCKS = ON,
                    ALLOW_PAGE_LOCKS = ON,
                    OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF
                )
        ) ON [PRIMARY];
        ';

        EXEC sp_executesql @sql;
        PRINT 'Created [dbo].[' + @filesTable + ']';
        SET @filesObjId = OBJECT_ID(N'[dbo].[' + @filesTable + N']', N'U');
    END
    ELSE
    BEGIN
        PRINT 'Skipped (already exists) [dbo].[' + @filesTable + ']';
    END

    /* 2) Create Modified_Functions_<n> */
    IF @funcsObjId IS NULL
    BEGIN
        SET @sql = N'
        CREATE TABLE [dbo].[' + @funcsTable + N'](
            [Unique_Hash] AS (
                CONVERT([varbinary](50), hashbytes(''SHA2_256'', concat([Modified_File_Unique_Hash], [Function_Name], [Function_Arguments])))
            ) PERSISTED,
            [Modified_File_Unique_Hash] [varbinary](50) NOT NULL,
            [Function_Name] [varchar](1000) NOT NULL,
            [Function_Arguments] [varchar](5000) NOT NULL,
            CONSTRAINT [' + @pkFuncsName + N'] PRIMARY KEY CLUSTERED ([Unique_Hash] ASC)
                WITH (
                    PAD_INDEX = OFF,
                    STATISTICS_NORECOMPUTE = OFF,
                    IGNORE_DUP_KEY = OFF,
                    ALLOW_ROW_LOCKS = ON,
                    ALLOW_PAGE_LOCKS = ON,
                    OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF
                )
        ) ON [PRIMARY];
        ';

        EXEC sp_executesql @sql;
        PRINT 'Created [dbo].[' + @funcsTable + ']';
        SET @funcsObjId = OBJECT_ID(N'[dbo].[' + @funcsTable + N']', N'U');
    END
    ELSE
    BEGIN
        PRINT 'Skipped (already exists) [dbo].[' + @funcsTable + ']';
    END

    /* 2.1) Ensure PK on Unique_Hash for Modified_Files_<n> */
    IF @filesObjId IS NOT NULL
       AND NOT EXISTS (
            SELECT 1
            FROM sys.key_constraints kc
            JOIN sys.index_columns ic
                ON ic.object_id = kc.parent_object_id
               AND ic.index_id = kc.unique_index_id
            JOIN sys.columns c
                ON c.object_id = ic.object_id
               AND c.column_id = ic.column_id
            WHERE kc.parent_object_id = @filesObjId
              AND kc.[type] = 'PK'
            GROUP BY kc.parent_object_id
            HAVING COUNT(1) = 1
               AND SUM(CASE WHEN c.name = N'Unique_Hash' THEN 1 ELSE 0 END) = 1
       )
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM sys.key_constraints kc
            WHERE kc.parent_object_id = @filesObjId
              AND kc.[type] = 'UQ'
              AND kc.[name] = @pkFilesName
        )
        BEGIN
            SET @sql = N'ALTER TABLE [dbo].[' + @filesTable + N'] DROP CONSTRAINT [' + @pkFilesName + N'];';
            EXEC sp_executesql @sql;
        END

        IF NOT EXISTS (
            SELECT 1 FROM sys.key_constraints
            WHERE parent_object_id = @filesObjId AND [type] = 'PK'
        )
        BEGIN
            SET @sql = N'ALTER TABLE [dbo].[' + @filesTable + N'] ADD CONSTRAINT [' + @pkFilesName + N'] PRIMARY KEY CLUSTERED ([Unique_Hash] ASC);';
            EXEC sp_executesql @sql;
            PRINT 'Added PK on [dbo].[' + @filesTable + '].[Unique_Hash]';
        END
        ELSE
        BEGIN
            PRINT 'WARNING: [dbo].[' + @filesTable + '] already has a PK not on [Unique_Hash]; manual fix needed.';
        END
    END

    /* 2.2) Ensure PK on Unique_Hash for Modified_Functions_<n> */
    IF @funcsObjId IS NOT NULL
       AND NOT EXISTS (
            SELECT 1
            FROM sys.key_constraints kc
            JOIN sys.index_columns ic
                ON ic.object_id = kc.parent_object_id
               AND ic.index_id = kc.unique_index_id
            JOIN sys.columns c
                ON c.object_id = ic.object_id
               AND c.column_id = ic.column_id
            WHERE kc.parent_object_id = @funcsObjId
              AND kc.[type] = 'PK'
            GROUP BY kc.parent_object_id
            HAVING COUNT(1) = 1
               AND SUM(CASE WHEN c.name = N'Unique_Hash' THEN 1 ELSE 0 END) = 1
       )
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM sys.key_constraints kc
            WHERE kc.parent_object_id = @funcsObjId
              AND kc.[type] = 'UQ'
              AND kc.[name] = @pkFuncsName
        )
        BEGIN
            SET @sql = N'ALTER TABLE [dbo].[' + @funcsTable + N'] DROP CONSTRAINT [' + @pkFuncsName + N'];';
            EXEC sp_executesql @sql;
        END

        IF NOT EXISTS (
            SELECT 1 FROM sys.key_constraints
            WHERE parent_object_id = @funcsObjId AND [type] = 'PK'
        )
        BEGIN
            SET @sql = N'ALTER TABLE [dbo].[' + @funcsTable + N'] ADD CONSTRAINT [' + @pkFuncsName + N'] PRIMARY KEY CLUSTERED ([Unique_Hash] ASC);';
            EXEC sp_executesql @sql;
            PRINT 'Added PK on [dbo].[' + @funcsTable + '].[Unique_Hash]';
        END
        ELSE
        BEGIN
            PRINT 'WARNING: [dbo].[' + @funcsTable + '] already has a PK not on [Unique_Hash]; manual fix needed.';
        END
    END

    /* 3) PK-only policy: do NOT keep FK Modified_Functions_<n> -> Modified_Files_<n> */
    IF EXISTS (
        SELECT 1
        FROM sys.foreign_keys
        WHERE [name] = @fkFuncsToFilesName
    )
    BEGIN
        SET @sql = N'ALTER TABLE [dbo].[' + @funcsTable + N'] DROP CONSTRAINT [' + @fkFuncsToFilesName + N'];';
        EXEC sp_executesql @sql;
        PRINT 'Dropped FK [' + @fkFuncsToFilesName + '] (PK-only policy)';
    END
    ELSE
    BEGIN
        PRINT 'No FK to drop [' + @fkFuncsToFilesName + '] (PK-only policy)';
    END

    SET @i += 1;
END

PRINT 'Done creating shard tables for Modified_Files and Modified_Functions.';


/*
-- Delete tables if they exist (use with caution - data will be lost!)
SET NOCOUNT ON;

DECLARE @start_n INT = 1;  -- set first n (inclusive)
DECLARE @end_n   INT = 20;  -- set last n (inclusive)

DECLARE @n INT = @start_n;
DECLARE @dropConstraintsSql NVARCHAR(MAX);
DECLARE @dropSql NVARCHAR(MAX);

WHILE @n <= @end_n
BEGIN
    -- Build and execute ALTER TABLE ... DROP CONSTRAINT statements for any FK that references either target table
    SELECT @dropConstraintsSql = STRING_AGG(
        'ALTER TABLE ' + QUOTENAME(OBJECT_SCHEMA_NAME(fk.parent_object_id)) + '.' + QUOTENAME(OBJECT_NAME(fk.parent_object_id))
        + ' DROP CONSTRAINT ' + QUOTENAME(fk.name),
        ';' + CHAR(13)
    )
    FROM sys.foreign_keys fk
    WHERE fk.referenced_object_id IN (
        OBJECT_ID(N'dbo.Modified_Functions_' + CAST(@n AS NVARCHAR(10))),
        OBJECT_ID(N'dbo.Modified_Files_'    + CAST(@n AS NVARCHAR(10)))
    );

    IF @dropConstraintsSql IS NOT NULL
    BEGIN
        EXEC sp_executesql @dropConstraintsSql;
    END

    -- Drop Modified_Functions_n if it exists
    IF OBJECT_ID(N'dbo.Modified_Functions_' + CAST(@n AS NVARCHAR(10))) IS NOT NULL
    BEGIN
        SET @dropSql = N'DROP TABLE dbo.' + QUOTENAME(N'Modified_Functions_' + CAST(@n AS NVARCHAR(10)));
        EXEC sp_executesql @dropSql;
    END

    -- Drop Modified_Files_n if it exists
    IF OBJECT_ID(N'dbo.Modified_Files_' + CAST(@n AS NVARCHAR(10))) IS NOT NULL
    BEGIN
        SET @dropSql = N'DROP TABLE dbo.' + QUOTENAME(N'Modified_Files_' + CAST(@n AS NVARCHAR(10)));
        EXEC sp_executesql @dropSql;
    END

    SET @n = @n + 1;
END

PRINT 'Completed drop for specified range.';
*/