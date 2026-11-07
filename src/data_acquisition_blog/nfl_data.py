import numpy as np
import pandas as pd
import nflreadpy as nfl
from pathlib import Path


# Load play-by-play data for completed seasons.
seasons = list(range(2016, 2026))
pbp = nfl.load_pbp(seasons=seasons)

# Keep only columns used in the analysis.
columns_to_keep = [
    "game_id", "season", "week", "game_date",
    "home_team", "away_team", "posteam", "posteam_type", "defteam",
    "play_id", "order_sequence", "play_type", "timeout_team", "desc",
    "kicker_player_id", "kicker_player_name",
    "kick_distance", "field_goal_result",
    "qtr", "game_seconds_remaining", "half_seconds_remaining",
    "game_half", "score_differential",
    "temp", "wind", "roof", "weather",
]
columns_to_keep = [col for col in columns_to_keep if col in pbp.columns]

# Select columns while the data is still in Polars, then convert to pandas.
pbp = pbp.select(columns_to_keep).to_pandas()

# Sort plays in chronological order within each game.
sort_cols = ["game_id", "play_id"]
if "order_sequence" in pbp.columns and pbp["order_sequence"].notna().any():
    sort_cols = ["game_id", "order_sequence", "play_id"]

pbp = pbp.sort_values(sort_cols, kind="stable").copy()

# Add information from the immediately preceding row in each game.
pbp["previous_timeout_team"] = (
    pbp.groupby("game_id")["timeout_team"].shift(1)
)
pbp["previous_play_description"] = (
    pbp.groupby("game_id")["desc"].shift(1)
)

# Keep field goal attempts and create the timeout and outcome variables.
fg = pbp.loc[pbp["play_type"].eq("field_goal")].copy()

fg["defensive_timeout_before_kick"] = (
    fg["previous_timeout_team"].eq(fg["defteam"]).fillna(False)
)
fg["made"] = fg["field_goal_result"].eq("made")

print("First few field goal attempts:")
print(fg.head().to_string(index=False))


# Create the full analysis table with one row per field goal attempt.
fg_dataset = fg.copy()

# Make analysis variables numeric.
for column in [
    "kick_distance",
    "game_seconds_remaining",
    "half_seconds_remaining",
    "score_differential",
    "wind",
]:
    if column in fg_dataset.columns:
        fg_dataset[column] = pd.to_numeric(
            fg_dataset[column], errors="coerce"
        )

# Group kicks by distance.
fg_dataset["distance_band"] = pd.cut(
    fg_dataset["kick_distance"],
    bins=[0, 30, 40, 50, 60, 100],
    labels=["30 yards or less", "31–40", "41–50", "51–60", "Over 60"],
    include_lowest=True,
)

# Group kicks by time remaining in the entire game.
fg_dataset["game_time_group"] = pd.cut(
    fg_dataset["game_seconds_remaining"],
    bins=[-1, 120, 600, 1800, np.inf],
    labels=["Final 2 minutes", "2–10 minutes", "10–30 minutes", "Over 30 minutes"],
)

# Group kicks by time remaining in the current half.
in_regulation_half = fg_dataset["game_half"].isin(["Half1", "Half2"])

fg_dataset["half_end_group"] = np.select(
    [
        in_regulation_half & (fg_dataset["half_seconds_remaining"] <= 120),
        in_regulation_half & (fg_dataset["half_seconds_remaining"] > 120),
        fg_dataset["game_half"].eq("Overtime"),
    ],
    [
        "Final 2 minutes of half",
        "More than 2 minutes from half end",
        "Overtime",
    ],
    default="Unknown",
)

# Describe the score from the kicking team's perspective.
score = fg_dataset["score_differential"]

fg_dataset["score_state"] = np.select(
    [
        score <= -8,
        (score >= -7) & (score < 0),
        score == 0,
        (score > 0) & (score <= 7),
        score > 7,
    ],
    [
        "Behind by 8+",
        "Behind by 1–7",
        "Tied",
        "Ahead by 1–7",
        "Ahead by 8+",
    ],
    default="Unknown",
)

# Group wind speeds for an exploratory comparison.
fg_dataset["wind_group"] = (
    pd.cut(
        fg_dataset["wind"],
        bins=[-np.inf, 9, 14, np.inf],
        labels=["0–9 mph", "10–14 mph", "15+ mph"],
    )
    .astype("object")
    .fillna("Unknown")
)


# Overall comparison of kicks with and without a defensive timeout immediately before.
overall_summary = (
    fg_dataset.groupby("defensive_timeout_before_kick")
    .agg(
        attempts=("made", "size"),
        makes=("made", "sum"),
        make_rate=("made", "mean"),
    )
    .reset_index()
)

overall_summary["make_rate_percent"] = overall_summary["make_rate"] * 100

print("\nOverall make rates:")
print(overall_summary.to_string(index=False))


# Check examples flagged as having a defensive timeout immediately before the kick.
print("\nExamples flagged with a defensive timeout:")
print(
    fg_dataset.loc[
        fg_dataset["defensive_timeout_before_kick"],
        [
            "game_id", "game_date", "posteam", "defteam",
            "kick_distance", "field_goal_result",
            "previous_timeout_team", "previous_play_description",
        ],
    ]
    .head(5)
    .to_string(index=False)
)


# Create summary tables for each comparison feature.
summary_parts = []

for column, label in [
    ("distance_band", "Kick distance"),
    ("posteam_type", "Kicking team location"),
    ("game_time_group", "Time remaining in game"),
    ("game_half", "Half of game"),
    ("half_end_group", "Time until end of half"),
    ("score_state", "Score state"),
    ("wind_group", "Wind"),
    ("roof", "Stadium roof"),
]:
    if column in fg_dataset.columns:
        part = (
            fg_dataset
            .groupby(
                [column, "defensive_timeout_before_kick"],
                dropna=False,
                observed=True,
            )
            .agg(
                attempts=("made", "size"),
                makes=("made", "sum"),
                make_rate=("made", "mean"),
            )
            .reset_index()
            .rename(columns={column: "category"})
        )

        part.insert(0, "feature", label)
        part["make_rate_percent"] = part["make_rate"] * 100
        summary_parts.append(part)

summary_table = pd.concat(summary_parts, ignore_index=True)


# Compare circumstances that match on these features.
match_columns = [
    "kicker_player_id",
    "kick_distance",
    "posteam_type",
    "game_half",
    "game_time_group",
    "half_end_group",
    "score_state",
    "wind_group",
    "roof",
]

# Remove kicks without a kicker ID or distance.
match_data = fg_dataset.dropna(
    subset=["kicker_player_id", "kick_distance"]
).copy()

strata_rates = (
    match_data
    .groupby(
        match_columns + ["defensive_timeout_before_kick"],
        dropna=False,
        observed=True,
    )
    .agg(
        attempts=("made", "size"),
        make_rate=("made", "mean"),
    )
    .reset_index()
)

matched_table = strata_rates.pivot(
    index=match_columns,
    columns="defensive_timeout_before_kick",
    values=["attempts", "make_rate"],
)

# Give the result columns readable names.
matched_table.columns = [
    f"{measure}_{'timeout' if timeout else 'no_timeout'}"
    for measure, timeout in matched_table.columns
]
matched_table = matched_table.reset_index()

# Keep only circumstances that have both timeout and no-timeout kicks.
matched_table = matched_table.dropna(
    subset=["make_rate_timeout", "make_rate_no_timeout"]
).copy()

matched_table["make_rate_difference_percentage_points"] = (
    matched_table["make_rate_timeout"]
    - matched_table["make_rate_no_timeout"]
) * 100

print("\nMatched circumstances:")
print(f"Number of matched circumstances: {len(matched_table)}")


# Count how many matched circumstances have a negative make-rate difference.
differences = matched_table["make_rate_difference_percentage_points"]
total = len(matched_table)

if total > 0:
    below_zero = (differences < 0).sum()
    zero_or_above = (differences >= 0).sum()

    print("\nDirection of make-rate differences across matched circumstances:")
    print(f"Below 0: {below_zero} of {total} ({below_zero / total:.1%})")
    print(
        f"Equal to or above 0: {zero_or_above} of {total} "
        f"({zero_or_above / total:.1%})"
    )
else:
    print("\nNo matched circumstances contained both timeout categories.")


# Print an overall plain-language summary.
by_timeout = overall_summary.set_index("defensive_timeout_before_kick")

if True in by_timeout.index and False in by_timeout.index:
    timeout_row = by_timeout.loc[True]
    no_timeout_row = by_timeout.loc[False]

    total_attempts = timeout_row["attempts"] + no_timeout_row["attempts"]
    timeout_share = timeout_row["attempts"] / total_attempts * 100
    rate_difference = (
        timeout_row["make_rate_percent"]
        - no_timeout_row["make_rate_percent"]
    )

    print(
        f"\nOf {total_attempts:,} field goal attempts, "
        f"{timeout_row['attempts']:,} ({timeout_share:.1f}%) had a defensive "
        f"timeout immediately before the kick. The make rate was "
        f"{timeout_row['make_rate_percent']:.1f}% for those kicks and "
        f"{no_timeout_row['make_rate_percent']:.1f}% for other kicks, "
        f"a difference of {rate_difference:.1f} percentage points."
    )


# Save the full dataset and analysis tables.
output_dir = Path("data")
output_dir.mkdir(exist_ok=True)

fg_dataset.to_csv(output_dir / "field_goal_attempts_full.csv", index=False)
overall_summary.to_csv(output_dir / "overall_summary.csv", index=False)
summary_table.to_csv(output_dir / "summary_by_comparison_group.csv", index=False)
matched_table.to_csv(output_dir / "matched_circumstances.csv", index=False)

print("\nSaved the full dataset and summary tables in the data folder.")