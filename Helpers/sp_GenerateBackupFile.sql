/*
    Stored Procedure: sp_generateBackupFile

    Description:
    This stored procedure backs up selected tables from an existing SQL Server database
    to a new temporary database, creates a backup file for the new database, and then
    deletes the temporary backup database. It is designed to facilitate targeted backups
    of specific tables within a database.

    Parameters:
    - @OriginalDB NVARCHAR(128): Name of the original database from which tables will be copied.
    - @TableList NVARCHAR(MAX): Comma-separated list of table names to be backed up.
    - @PathBackupFileName  NVARCHAR(255): Full path, including the file name, where the backup file will be saved.
                                 Ensure this path is accessible and SQL Server has write permissions.
    - @BackupDatabaseName NVARCHAR(128): Name of the temporary backup database to be created and deleted
                                         after the backup.

    Safeguard:
    - The procedure includes a safeguard to prevent accidentally setting @OriginalDB and @BackupDatabaseName
      to the same value, which could lead to unintended deletion of the original database.

    Example Usage:
    USE [ResearchDatasets]
    GO

    DECLARE @return_value int

    EXEC @return_value = [dbo].[sp_generateBackupFile]
        @OriginalDB = N'ResearchDatasets',
        @TableList = N'FFmpeg',
        @PathBackupFileName  = N'C:\Backup\BackupDB.bak',
        @BackupDatabaseName = N'BackupDatasets'

    SELECT 'Return Value' = @return_value

    GO

    Reminder:
    - Ensure that @PathBackupFileName  specifies a valid path where SQL Server has permission to write files.
*/

CREATE PROCEDURE sp_GenerateBackupFile
    @OriginalDB NVARCHAR(128),        -- Name of the original database
    @TableList NVARCHAR(MAX),         -- Comma-separated list of table names
    @PathBackupFileName  NVARCHAR(255),        -- Full path including the file name for the backup
    @BackupDatabaseName NVARCHAR(128) -- Name of the backup database
AS
BEGIN
    -- Check if the OriginalDB is the same as BackupDatabaseName
    IF @OriginalDB = @BackupDatabaseName
    BEGIN
        RAISERROR('The original database name and the backup database name cannot be the same.', 16, 1);
        RETURN;
    END

    DECLARE @TableName NVARCHAR(128)
    DECLARE @SQL NVARCHAR(MAX)

    -- Create new database
    SET @SQL = 'IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N''' + @BackupDatabaseName + ''')
                BEGIN
                    CREATE DATABASE ' + @BackupDatabaseName + '
                END'
    EXEC(@SQL)

    -- Iterate through the list of tables
    WHILE LEN(@TableList) > 0
    BEGIN
        SET @TableName = LEFT(@TableList, CHARINDEX(',', @TableList + ',') - 1)
        SET @TableList = STUFF(@TableList, 1, CHARINDEX(',', @TableList + ','), '')

        -- Copy table to BackupDB
        SET @SQL = 'SELECT * INTO ' + @BackupDatabaseName + '.dbo.' + @TableName + ' FROM ' + @OriginalDB + '.dbo.' + @TableName
        EXEC(@SQL)
    END

    -- Backup the new database
    SET @SQL = 'BACKUP DATABASE ' + @BackupDatabaseName + ' TO DISK = ''' + @PathBackupFileName  + ''''
    EXEC(@SQL)

    -- Drop the new database
    SET @SQL = 'DROP DATABASE ' + @BackupDatabaseName
    EXEC(@SQL)
END
GO