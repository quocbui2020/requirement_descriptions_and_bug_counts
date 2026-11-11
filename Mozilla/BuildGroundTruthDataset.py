# BuildGroundTruthDataset.py
# ---------------------------------------------------------------------------
# Purpose:
#   Randomly select N (default 1000) DISTINCT bug IDs to form a ground truth
#   dataset, while:
#     (1) preserving (approximately) the file-type ratio produced by the
#         reference query below (C / C++ / Java / JavaScript / Python), and
#     (2) making sure the selected bugs are SPREAD OUT over the whole ID range
#         instead of being clustered in one region of the pool.
#
# Reference query this program is built on:
#
#   ;with cte1 as (
#       select distinct ID
#       from Bugs_bugbug
#       where [status] in('RESOLVED', 'VERIFIED')
#       and [Resolution] = 'FIXED'
#   )
#   select mf.File_Type, count(*)
#   from cte1
#   inner join [Bugs] b on b.ID = cte1.ID
#       and b.[status] in('RESOLVED', 'VERIFIED')
#       and b.[Resolution] = 'FIXED'
#   inner join GitCommit_Properties gitpro on gitpro.[Value] = b.ID
#       and gitpro.[Name] = 'Bug ID Mentioned'
#   inner join Modified_Files mf on mf.Git_commit_ID = gitpro.Git_Commit_ID
#       and mf.File_Type in('C++', 'JavaScript', 'C', 'Python', 'Java')
#   group by mf.File_Type
#
#   The observed population distribution (file rows per type) is NOT hardcoded:
#   it is queried from the database at runtime and printed before sampling.
#
# Sampling strategy (two steps):
#   STEP A - Quota allocation:
#       Each bug is assigned a "primary file type" = the file type it touches
#       the most (ties are broken in favour of the globally rarer type so that
#       small populations such as Java are not swallowed by C++/JavaScript).
#       The number of bugs taken from each primary-type pool is proportional to
#       that type's share of file rows in the population (largest-remainder
#       rounding, with redistribution when a pool is too small).
#
#   STEP B - Systematic / stratified sampling (anti-clustering):
#       Inside each primary-type pool the bug IDs are sorted ascending and cut
#       into `quota` contiguous, near-equal strata. Exactly ONE bug is drawn at
#       random from each stratum. This guarantees the picks are spread over the
#       whole ID range (e.g. picking 4 bugs out of IDs 1..20 yields one from
#       1-5, one from 6-10, one from 11-15 and one from 16-20) while still
#       being random inside each block.
#
# Usage examples:
#   python BuildGroundTruthDataset.py
#   python BuildGroundTruthDataset.py --database MozillaDataSet2026 --sample-size 1000 \
#       --seed 42 --output ground_truth_1000.csv
# ---------------------------------------------------------------------------

import argparse
import csv
import random
from time import strftime, localtime

import pyodbc

# Connection string (same pattern as bug_description_processor.py)
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=localhost\\SQLEXPRESS;' \
           'DATABASE=MozillaDataSet2026;' \
           'Connection Timeout=300;' \
           'Login Timeout=300;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

# File types considered by the reference query.
FILE_TYPES = ['C', 'C++', 'Java', 'JavaScript', 'Python']


def log(message, end="\n"):
    """Timestamped console logging."""
    print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] {message}", end=end, flush=True)


class GroundTruthDatasetBuilder:
    def __init__(self, conn_str):
        self.conn_str = conn_str

    # -------------------------------------------------------------------
    # DATA ACCESS
    # -------------------------------------------------------------------
    def fetch_bug_file_type_counts(self, database_name):
        """
        Runs the reference query but grouped by (Bug_ID, File_Type) so we know,
        for every candidate bug, how many modified files of each type it has.

        :return: list of dicts {"Bug_ID": int, "File_Type": str, "File_Count": int}
        """
        query = f"""
        WITH cte1 AS (
            SELECT DISTINCT [ID]
            FROM [{database_name}].[dbo].[Bugs_bugbug]
            WHERE [Status] IN ('RESOLVED', 'VERIFIED')
              AND [Resolution] = 'FIXED'
        )
        SELECT
             b.[ID]            AS [Bug_ID]
            ,mf.[File_Type]    AS [File_Type]
            ,COUNT(*)          AS [File_Count]
        FROM cte1
        INNER JOIN [{database_name}].[dbo].[Bugs] b
            ON b.[ID] = cte1.[ID]
            AND b.[Status] IN ('RESOLVED', 'VERIFIED')
            AND b.[Resolution] = 'FIXED'
        INNER JOIN [{database_name}].[dbo].[GitCommit_Properties] gitpro
            ON gitpro.[Value] = b.[ID]
            AND gitpro.[Name] = 'Bug ID Mentioned'
        INNER JOIN [{database_name}].[dbo].[Modified_Files] mf
            ON mf.[Git_Commit_ID] = gitpro.[Git_Commit_ID]
            AND mf.[File_Type] IN ('C++', 'JavaScript', 'C', 'Python', 'Java')
        GROUP BY b.[ID], mf.[File_Type]
        ORDER BY b.[ID];
        """
        try:
            with pyodbc.connect(self.conn_str) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    return [
                        {
                            "Bug_ID": int(row.Bug_ID),
                            "File_Type": row.File_Type,
                            "File_Count": int(row.File_Count),
                        }
                        for row in rows
                    ]
        except Exception as e:
            print(f"An error occurred while fetching bug/file-type counts: {e}")
            return []

    # -------------------------------------------------------------------
    # STEP A - build pools + quotas
    # -------------------------------------------------------------------
    @staticmethod
    def build_bug_profiles(rows):
        """
        Pivots the flat (Bug_ID, File_Type, File_Count) rows into one record per
        bug: {Bug_ID: {File_Type: File_Count, ...}}.
        """
        profiles = {}
        for row in rows:
            profiles.setdefault(row["Bug_ID"], {})[row["File_Type"]] = row["File_Count"]
        return profiles

    @staticmethod
    def population_file_type_totals(rows):
        """Total number of modified-file rows per file type in the whole pool."""
        totals = {file_type: 0 for file_type in FILE_TYPES}
        for row in rows:
            if row["File_Type"] in totals:
                totals[row["File_Type"]] += row["File_Count"]
        return totals

    @staticmethod
    def primary_file_type_of(counts, population_totals):
        """
        Dominant file type of a single bug. Ties are broken in favour of the
        globally RARER file type, otherwise rare languages (Java, C) would
        almost never win a tie against C++/JavaScript.
        """
        return sorted(
            counts.items(),
            key=lambda item: (-item[1], population_totals.get(item[0], 0))
        )[0][0]

    @classmethod
    def assign_primary_file_type(cls, profiles, population_totals):
        """
        Puts every bug into exactly one pool, keyed by its dominant file type.

        :return: {File_Type: [bug_id, ...]} with bug ids sorted ascending
        """
        pools = {file_type: [] for file_type in FILE_TYPES}
        for bug_id, counts in profiles.items():
            pools[cls.primary_file_type_of(counts, population_totals)].append(bug_id)

        for file_type in pools:
            pools[file_type].sort()
        return pools

    @staticmethod
    def allocate_quotas(population_totals, pools, sample_size):
        """
        Splits `sample_size` across file types proportionally to the population
        file-row ratio, using the largest-remainder method. If a pool does not
        contain enough bugs to satisfy its quota, the leftover is redistributed
        to the other pools that still have spare bugs.

        :return: {File_Type: quota}
        """
        grand_total = sum(population_totals.values())
        if grand_total == 0:
            return {file_type: 0 for file_type in FILE_TYPES}

        # Ideal (fractional) number of bugs per file type.
        ideal = {ft: sample_size * population_totals[ft] / grand_total for ft in FILE_TYPES}

        # Largest-remainder rounding so the quotas add up exactly to sample_size.
        quotas = {ft: int(ideal[ft]) for ft in FILE_TYPES}
        remainder_order = sorted(FILE_TYPES, key=lambda ft: ideal[ft] - int(ideal[ft]), reverse=True)
        leftover = sample_size - sum(quotas.values())
        for i in range(leftover):
            quotas[remainder_order[i % len(remainder_order)]] += 1

        # Cap each quota by how many bugs the pool actually contains.
        deficit = 0
        for ft in FILE_TYPES:
            available = len(pools.get(ft, []))
            if quotas[ft] > available:
                deficit += quotas[ft] - available
                quotas[ft] = available

        # Redistribute the deficit to the pools that still have spare capacity,
        # biggest population first (they are the least likely to run out).
        for ft in sorted(FILE_TYPES, key=lambda t: population_totals[t], reverse=True):
            if deficit <= 0:
                break
            spare = len(pools.get(ft, [])) - quotas[ft]
            take = min(spare, deficit)
            quotas[ft] += take
            deficit -= take

        return quotas

    # -------------------------------------------------------------------
    # STEP B - anti-clustering sampling
    # -------------------------------------------------------------------
    @staticmethod
    def stratified_spread_sample(sorted_ids, quota, rng):
        """
        Systematic stratified sampling: cut `sorted_ids` into `quota` contiguous,
        near-equal strata and draw exactly one random ID from each stratum.
        This keeps the picks randomized but evenly spread over the whole range.

        Example: ids = 1..20, quota = 4 -> strata [1-5], [6-10], [11-15], [16-20]
                 and one random pick from each block.
        """
        total = len(sorted_ids)
        if quota <= 0 or total == 0:
            return []
        if quota >= total:
            return list(sorted_ids)

        picks = []
        for stratum_index in range(quota):
            # Boundaries computed from ratios so strata stay near-equal even
            # when `total` is not divisible by `quota`.
            start = (stratum_index * total) // quota
            end = ((stratum_index + 1) * total) // quota  # exclusive
            if end <= start:
                end = start + 1
            picks.append(sorted_ids[rng.randrange(start, end)])
        return picks

    # -------------------------------------------------------------------
    # REPORTING
    # -------------------------------------------------------------------
    @staticmethod
    def summarize(selected_ids, profiles, population_totals):
        """
        Compares the file-type ratio of the sampled bugs against the population
        ratio so we can verify the ground truth dataset is representative.
        """
        sample_totals = {ft: 0 for ft in FILE_TYPES}
        for bug_id in selected_ids:
            for file_type, count in profiles[bug_id].items():
                if file_type in sample_totals:
                    sample_totals[file_type] += count

        population_grand = sum(population_totals.values()) or 1
        sample_grand = sum(sample_totals.values()) or 1

        print("")
        print(f"{'File_Type':<12}{'Pop. files':>12}{'Pop. %':>10}{'Sample files':>14}{'Sample %':>10}")
        print("-" * 58)
        for ft in FILE_TYPES:
            print(f"{ft:<12}{population_totals[ft]:>12,}{population_totals[ft] / population_grand * 100:>9.2f}%"
                  f"{sample_totals[ft]:>14,}{sample_totals[ft] / sample_grand * 100:>9.2f}%")
        print("-" * 58)
        print(f"{'TOTAL':<12}{population_grand:>12,}{100.0:>9.2f}%{sample_grand:>14,}{100.0:>9.2f}%")
        print("")
        return sample_totals


#################################################
# Main
#################################################
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build a ground truth dataset of distinct bug IDs that preserves the "
                    "population file-type ratio and spreads the picks across the ID range.")
    parser.add_argument('--database', type=str, default='MozillaDataSet2026', help='Target database name.')
    parser.add_argument('--sample-size', type=int, default=1000, help='Number of distinct bug IDs to select.')
    parser.add_argument('--seed', type=int, default=None, help='Random seed for reproducible sampling.')
    parser.add_argument('--output', type=str, default='ground_truth_dataset.csv', help='CSV output file path.')
    args = parser.parse_args()

    rng = random.Random(args.seed)
    builder = GroundTruthDatasetBuilder(conn_str)

    log(f"Fetching candidate bugs from [{args.database}] ...")
    rows = builder.fetch_bug_file_type_counts(args.database)
    if not rows:
        log("No rows returned. Nothing to sample. EXIT!")
        raise SystemExit(1)

    profiles = builder.build_bug_profiles(rows)
    population_totals = builder.population_file_type_totals(rows)
    log(f"Candidate bugs: {len(profiles):,} | candidate file rows: {sum(population_totals.values()):,}")

    # Observed population distribution, straight from the database.
    population_grand = sum(population_totals.values())
    for ft in FILE_TYPES:
        share = population_totals[ft] / population_grand * 100 if population_grand else 0.0
        log(f"  population[{ft}] = {population_totals[ft]:,} files ({share:.2f}%)")

    # STEP A: pools + quotas.
    pools = builder.assign_primary_file_type(profiles, population_totals)
    quotas = builder.allocate_quotas(population_totals, pools, args.sample_size)
    for ft in FILE_TYPES:
        log(f"  pool[{ft}] = {len(pools[ft]):,} bugs -> quota {quotas[ft]}")

    # STEP B: spread-out sampling inside every pool.
    selected_ids = []
    for ft in FILE_TYPES:
        selected_ids.extend(builder.stratified_spread_sample(pools[ft], quotas[ft], rng))
    selected_ids = sorted(set(selected_ids))
    log(f"Selected {len(selected_ids):,} distinct bug IDs.")

    # Verify the sample keeps the population ratio.
    builder.summarize(selected_ids, profiles, population_totals)

    # Persist the result: one row per selected bug with its file-type breakdown.
    with open(args.output, 'w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(['Bug_ID', 'Primary_File_Type'] + FILE_TYPES + ['Total_Files'])
        for bug_id in selected_ids:
            counts = profiles[bug_id]
            primary_type = builder.primary_file_type_of(counts, population_totals)
            writer.writerow(
                [bug_id, primary_type] + [counts.get(ft, 0) for ft in FILE_TYPES] + [sum(counts.values())])
    log(f"Wrote ground truth dataset to: {args.output}")

    log("PROGRAM FINISHED. EXIT!")