-- Detach database:
USE master;
EXEC sp_detach_db @dbname = 'ResearchDatasets';

-- Attach database:
USE master;
GO
CREATE DATABASE ResearchDatasets
ON (FILENAME = 'C:\Program Files\Microsoft SQL Server\MSSQL16.MSSQLSERVER01\MSSQL\DATA\ResearchDatasets.mdf'),
   (FILENAME = 'C:\Program Files\Microsoft SQL Server\MSSQL16.MSSQLSERVER01\MSSQL\DATA\ResearchDatasets_log.ldf')
FOR ATTACH;