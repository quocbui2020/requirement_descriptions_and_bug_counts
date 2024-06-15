USE [ResearchDatasets]
GO

/****** Object:  StoredProcedure [dbo].[sp_GetFFmpegData]    Script Date: 6/14/2024 10:09:26 PM ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

-- =============================================
-- Author:		<Author,,Name>
-- Create date: <Create Date,,>
-- Description:	<Description,,>
-- =============================================
CREATE PROCEDURE [dbo].[sp_GetFFmpegData] 
	-- Add the parameters for the stored procedure here
	@version varchar(100),
	@Characters_Removed_Percentage decimal
AS
BEGIN
	/*
	Ultimate query: This query output associate Defect tickets to each enhancement ticket based on file name and function name.
	*/
	WITH EnhancementTicketQuery AS (
		SELECT 
			FFmpeg.ID as Ticket_ID,
			FFmpeg.Type as Ticket_Type,
			FFmpeg.Summary,
			FFmpeg.Description_Original,
			FFmpeg.Description_Without_SigNonNL,
			FFmpeg.Characters_Removed_Percentage,
			FFmpeg.Is_Contain_SigNonNL,
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
			e.Summary,
			e.Description_Original,
			e.Description_Without_SigNonNL,
			e.Characters_Removed_Percentage,
			e.Is_Contain_SigNonNL,
			d.File_Name AS Defect_File_Name,
			d.Function_Name AS Defect_Function_Name,
			d.Ticket_ID AS Defect_Ticket_ID,
			d.Ticket_Type AS Defect_Type,
			d.Ticket_Created_On AS Defect_Ticket_Created_On,
			d.File_Change_Status AS Defect_File_Change_Status,
			d.Date AS Defect_Commit_Date
		FROM 
			EnhancementTicketQuery e
		LEFT JOIN 
			DefectTicketQuery d ON e.File_Name = d.File_Name 
							   AND e.Function_Name = d.Function_Name
							   AND CONVERT(datetime2, SUBSTRING(e.Date, 6, 20)) < CONVERT(datetime2, SUBSTRING(d.Date, 6, 20)) -- Includes records only if enhancement's commit datetime < defect's commit datetime.

	/* Query to output all the functions associated between enhance and defect tickets. Each row represents each function. Again, do not includes enhancement ticket with zero bug counts.
	)
	SELECT
		Enhancement_Ticket_ID
		--,Enhancement_Type
		--,Enhancement_Ticket_Created_On
		,Enhancement_Commit_Date
		,Enhancement_File_Name AS File_Name
		,Enhancement_Function_Name AS Function_Name
		--,Enhancement_File_Change_Status
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
		SELECT DISTINCT Enhancement_Ticket_ID, Defect_Ticket_ID, Summary, Description_Original, Description_Without_SigNonNL, Characters_Removed_Percentage, Is_Contain_SigNonNL
		FROM JoinedQuery
	)
	SELECT DISTINCT Enhancement_Ticket_ID
		,fsm.version
		,Description_Original
		,Description_Without_SigNonNL
		,Characters_Removed_Percentage
		,COUNT(Defect_Ticket_ID) OVER (PARTITION BY Enhancement_Ticket_ID) AS Bug_Count
		,CASE 
			WHEN COUNT(Defect_Ticket_ID) OVER (PARTITION BY Enhancement_Ticket_ID) > 0 THEN 1  --Threshold: Determine the value of dep. vars.
			ELSE 0
		END AS Does_Contain_Any_Bug
		,CASE 
			WHEN [Characters_Removed_Percentage] > 0 THEN 1
			ELSE 0
		END AS Does_Contain_NonNL
		,fsm.flesch_kincaid_reading_ease
		,fsm.flesch_kincaid_grade_level
		,fsm.gunning_fog_score
		,fsm.smog_index
		,fsm.coleman_liau_index
		,fsm.automated_readability_index
		,fsm.number_of_words
		,fsm.number_of_complex_words
		,fsm.average_grade_level
		,fsm.Number_Of_Predicates
	FROM DistinctQuery
	INNER JOIN FFmpeg_Statistical_Measurements fsm ON fsm.Ticket_ID = DistinctQuery.Enhancement_Ticket_ID
	WHERE [version]= @version
		AND [Characters_Removed_Percentage] <= @Characters_Removed_Percentage
	ORDER BY Enhancement_Ticket_ID ASC;
END
GO


