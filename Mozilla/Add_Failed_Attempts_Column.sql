-- Add a column to track the number of failed attempts by the model to convert bug descriptions
-- This allows for analysis of problematic records that the model struggles with

ALTER TABLE [dbo].[qwen3_8b_bug_descriptions]
ADD [Failed_Attempts] [int] NULL DEFAULT 0;

-- Optional: Create an index on Failed_Attempts to quickly find problematic records
CREATE INDEX [IX_qwen3_8b_bug_descriptions_Failed_Attempts] 
ON [dbo].[qwen3_8b_bug_descriptions] ([Failed_Attempts]) 
WHERE [Failed_Attempts] > 0;

-- Verify the new column
SELECT TOP 10 
    [Bug_ID],
    [Who_What_Why],
    [Given_When_Then],
    [Failed_Attempts]
FROM [dbo].[qwen3_8b_bug_descriptions]
ORDER BY [Bug_ID] DESC;
