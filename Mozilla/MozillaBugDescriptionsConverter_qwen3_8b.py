import argparse
import json
import time
import traceback
from time import strftime, localtime

import ollama
import pyodbc


# Connection string (same pattern as Bugzilla_mozilla_file_function_scraper.py)
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
		   'SERVER=localhost\\SQLEXPRESS;' \
		   'DATABASE=MozillaDataSet2026;' \
		   'Connection Timeout=300;' \
		   'Login Timeout=300;' \
		   'LongAsMax=yes;' \
		   'TrustServerCertificate=yes;' \
		   'Trusted_Connection=yes;'


class MozillaBugDescriptionsConverterQwen3_8B:
	def __init__(self, model_name="qwen3:8b"):
		self.client = ollama.Client()
		self.model_name = model_name

	def _now(self):
		return strftime('%m/%d/%Y %H:%M:%S', localtime())

	def _log(self, message):
		print(f"[{self._now()}] {message}", flush=True)

	def _connect_with_retry(self, max_connection_attempts=10):
		connection_attempt = 1
		while connection_attempt <= max_connection_attempts:
			try:
				return pyodbc.connect(conn_str)
			except pyodbc.Error as conn_err:
				if conn_err.args and conn_err.args[0] in ['08S01']:
					connection_attempt += 1
					print(
						f"08S01. Connection attempt {connection_attempt}/{max_connection_attempts} failed. Retrying in 5 seconds...",
						end="",
						flush=True,
					)
					time.sleep(5)
				else:
					raise conn_err
		raise Exception("Failed to establish a connection after multiple attempts.")

	def get_unprocessed_bug_records(self, limit=100, min_bug_id=None, max_bug_id=None):
		attempt_number = 1
		max_retries = 3

		while attempt_number <= max_retries:
			conn = None
			cursor = None
			try:
				conn = self._connect_with_retry()
				cursor = conn.cursor()

				query = '''
					SELECT TOP (?)
						b.ID,
						b.Bug_Title,
						b.Bug_Description,
						b.User_Story
					FROM [dbo].[Bugs] b
					LEFT JOIN [dbo].[qwen3_8b_bug_descriptions] q
						ON q.Bug_ID = b.ID
					WHERE q.Bug_ID IS NULL
					  AND (b.Bug_Title IS NOT NULL OR b.Bug_Description IS NOT NULL OR b.User_Story IS NOT NULL)
					  AND (? IS NULL OR b.ID >= ?)
					  AND (? IS NULL OR b.ID <= ?)
					ORDER BY b.ID DESC;
				'''

				cursor.execute(query, (limit, min_bug_id, min_bug_id, max_bug_id, max_bug_id))
				return cursor.fetchall()

			except pyodbc.Error as e:
				attempt_number += 1
				time.sleep(5)
				if attempt_number <= max_retries:
					continue
				print(f"Error - get_unprocessed_bug_records: {e}")
				traceback.print_exc()
				raise
			finally:
				if cursor:
					cursor.close()
				if conn:
					conn.close()

		return []

	def build_prompt(self, bug_title, bug_description, user_story):
		safe_bug_title = bug_title.strip() if bug_title else ""
		safe_bug_description = bug_description.strip() if bug_description else ""
		safe_user_story = user_story.strip() if user_story else ""

		return f'''You are given a single bug record.

Task:
1) Convert the record into a concise user story in Who_What_Why format.
2) Convert the record into test acceptance criteria in Given_When_Then format.

Format definitions:
- Who_What_Why must follow this exact structure in one sentence:
  "As a <who>, I want <what>, so that <why>."
- Given_When_Then must follow this exact structure with three clauses:
  "Given <context>, When <action>, Then <expected outcome>."
- A single user story can have multiple acceptance criteria.
- If there are multiple Given_When_Then criteria, return them as a JSON array of strings.
- Each item in that array must be one complete "Given ..., When ..., Then ..." sentence.

Hard constraints:
- Use ONLY the information explicitly present in the input.
- Do NOT infer, assume, or invent missing details.
- If information is insufficient, say "Not enough information." for the missing part.
- Keep output concise and factual.
- Return valid JSON only (no markdown, no extra text).
- If the record has almost no usable information, set both fields to "Not enough information.".

Required JSON schema:
{{
  "Who_What_Why": "string",
  "Given_When_Then": "string or array of strings"
}}

Input record:
Bug_Title:
"""{safe_bug_title}"""

Bug_Description:
"""{safe_bug_description}"""

User_Story:
"""{safe_user_story}"""
'''

	def _extract_json_object(self, text):
		if not text:
			return None

		try:
			return json.loads(text)
		except json.JSONDecodeError:
			start_index = text.find("{")
			end_index = text.rfind("}")
			if start_index == -1 or end_index == -1 or end_index <= start_index:
				return None
			candidate = text[start_index:end_index + 1]
			try:
				return json.loads(candidate)
			except json.JSONDecodeError:
				return None

	def _normalize_given_when_then(self, given_when_then):
		if given_when_then is None:
			return None

		if isinstance(given_when_then, list):
			items = [str(item).strip() for item in given_when_then if str(item).strip()]
			if not items:
				return "Not enough information."
			return " | ".join(items)

		return str(given_when_then).strip()

	def convert_bug_text(self, bug_title, bug_description, user_story):
		prompt = self.build_prompt(bug_title, bug_description, user_story)

		response = self.client.generate(
			model=self.model_name,
			prompt=prompt,
			options={
				"temperature": 0, # 0 for deterministic output, can increase if you want more creativity but be careful with consistency and JSON validity
				"top_p": 0.1, # 0.1 to focus on most likely tokens, can increase if you want more diversity but be careful with consistency and JSON validity
			},
		)

		raw_output = response.get("response") if isinstance(response, dict) else getattr(response, "response", "")
		parsed = self._extract_json_object(raw_output)

		if not parsed:
			raise ValueError(f"Model output is not valid JSON: {raw_output}")

		who_what_why = parsed.get("Who_What_Why")
		given_when_then = parsed.get("Given_When_Then")

		if who_what_why is not None:
			who_what_why = str(who_what_why).strip()
		given_when_then = self._normalize_given_when_then(given_when_then)

		return who_what_why, given_when_then

	def upsert_conversion_result(self, bug_id, who_what_why, given_when_then):
		attempt_number = 1
		max_retries = 10

		while attempt_number <= max_retries:
			conn = None
			cursor = None
			try:
				conn = self._connect_with_retry()
				cursor = conn.cursor()

				cursor.execute("BEGIN TRANSACTION")

				cursor.execute(
					'''
					MERGE [dbo].[qwen3_8b_bug_descriptions] AS target
					USING (SELECT ? AS [Bug_ID], ? AS [Who_What_Why], ? AS [Given_When_Then], 0 AS [Failed_Attempts]) AS source
					ON target.[Bug_ID] = source.[Bug_ID]
					WHEN MATCHED THEN
						UPDATE SET
							[Who_What_Why] = source.[Who_What_Why],
							[Given_When_Then] = source.[Given_When_Then],
							[Failed_Attempts] = 0
					WHEN NOT MATCHED THEN
						INSERT ([Bug_ID], [Who_What_Why], [Given_When_Then], [Failed_Attempts])
						VALUES (source.[Bug_ID], source.[Who_What_Why], source.[Given_When_Then], 0);
					''',
					(bug_id, who_what_why, given_when_then),
				)

				cursor.execute("COMMIT")
				conn.commit()
				return

			except pyodbc.Error as e:
				try:
					if cursor:
						cursor.execute("ROLLBACK TRANSACTION")
					if conn:
						conn.rollback()
				except Exception:
					pass

				attempt_number += 1
				if attempt_number <= max_retries:
					print(
						f"pyodbc.Error while saving Bug_ID={bug_id}: {e}. Retrying in 10 seconds...",
						end="",
						flush=True,
					)
					time.sleep(10)
					continue

				print(f"Failed to save Bug_ID={bug_id}: {e}")
				traceback.print_exc()
				raise
			finally:
				if cursor:
					cursor.close()
				if conn:
					conn.close()

	def log_failed_conversion_attempt(self, bug_id):
		"""Increment the Failed_Attempts counter for a bug when model conversion fails."""
		attempt_number = 1
		max_retries = 5

		while attempt_number <= max_retries:
			conn = None
			cursor = None
			try:
				conn = self._connect_with_retry()
				cursor = conn.cursor()

				cursor.execute("BEGIN TRANSACTION")

				cursor.execute(
					'''
					MERGE [dbo].[qwen3_8b_bug_descriptions] AS target
					USING (SELECT ? AS [Bug_ID]) AS source
					ON target.[Bug_ID] = source.[Bug_ID]
					WHEN MATCHED THEN
						UPDATE SET
							[Failed_Attempts] = ISNULL([Failed_Attempts], 0) + 1
					WHEN NOT MATCHED THEN
						INSERT ([Bug_ID], [Who_What_Why], [Given_When_Then], [Failed_Attempts])
						VALUES (source.[Bug_ID], NULL, NULL, 1);
					''',
					(bug_id,),
				)

				cursor.execute("COMMIT")
				conn.commit()
				return

			except pyodbc.Error as e:
				try:
					if cursor:
						cursor.execute("ROLLBACK TRANSACTION")
					if conn:
						conn.rollback()
				except Exception:
					pass

				attempt_number += 1
				if attempt_number <= max_retries:
					time.sleep(5)
					continue

				self._log(f"Warning: Failed to log failed attempt for Bug_ID={bug_id}: {e}")
				return
			finally:
				if cursor:
					cursor.close()
				if conn:
					conn.close()

	def run(self, limit=100, min_bug_id=None, max_bug_id=None):
		self._log(
			f"Starting converter | model={self.model_name} | limit={limit} | min_bug_id={min_bug_id} | max_bug_id={max_bug_id}"
		)

		rows = self.get_unprocessed_bug_records(limit=limit, min_bug_id=min_bug_id, max_bug_id=max_bug_id)
		total = len(rows)
		success_count = 0
		failed_count = 0

		if total == 0:
			self._log("No unprocessed bug records found.")
			return

		self._log(f"Fetched {total} unprocessed records.")

		for index, row in enumerate(rows, start=1):
			bug_id, bug_title, bug_description, user_story = row
			remaining_before = total - index + 1
			self._log(
				f"Processing Bug_ID={bug_id} | progress={index}/{total} | remaining_before={remaining_before}"
			)

			try:
				who_what_why, given_when_then = self.convert_bug_text(
					bug_title=bug_title,
					bug_description=bug_description,
					user_story=user_story,
				)

				self.upsert_conversion_result(
					bug_id=bug_id,
					who_what_why=who_what_why,
					given_when_then=given_when_then,
				)

				success_count += 1
				remaining_after = total - index
				self._log(
					f"Saved Bug_ID={bug_id} | success={success_count} | failed={failed_count} | remaining_after={remaining_after}"
				)

			except Exception as e:
				failed_count += 1
				remaining_after = total - index
				self._log(
					f"Failed Bug_ID={bug_id} | error={e} | success={success_count} | failed={failed_count} | remaining_after={remaining_after}"
				)
				# Log the failed attempt to database for tracking and analysis
				self.log_failed_conversion_attempt(bug_id)

		self._log(
			f"Completed run | total={total} | success={success_count} | failed={failed_count}"
		)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description="Convert Mozilla bug text into Who_What_Why and Given_When_Then using qwen3:8b."
	)
	parser.add_argument("--limit", type=int, default=100, help="Max number of unprocessed bug records to process.")
	parser.add_argument("--min-bug-id", type=int, default=None, help="Optional lower bound for Bug_ID.")
	parser.add_argument("--max-bug-id", type=int, default=None, help="Optional upper bound for Bug_ID.")
	parser.add_argument("--model", type=str, default="qwen3:8b", help="Ollama model name.")
	args = parser.parse_args()

	converter = MozillaBugDescriptionsConverterQwen3_8B(model_name=args.model)
	converter.run(limit=args.limit, min_bug_id=args.min_bug_id, max_bug_id=args.max_bug_id)