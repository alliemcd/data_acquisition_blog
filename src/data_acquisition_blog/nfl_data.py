import nflreadpy as nfl
import pandas as pd

seasons = list(range(2015,2026))
pbp = nfl.load_pbp(seasons=seasons).to_pandas()

columns_to_keep = [
    "game_id", "season", "week", "game_date",
    "home_team", "away_team", "posteam", "posteam_type", "defteam",
    "play_id", "order_sequence", "play_type", "timeout_team", "desc",
    "kicker_player_id", "kicker_player_name",
    "kick_distance", "field_goal_result",
    "qtr", "game_seconds_remaining", "score_differential",
    "temp", "wind", "roof", "weather",
]
columns_to_keep = [col for col in columns_to_keep if col in pbp.columns]
pbp = pbp.select(columns_to_keep)

sort_cols = ["game_id", "play_id"]
if "order_sequence" in pbp.columns and pbp["order_sequence"].notna().any():
    sort_cols = ["game_id", "order_sequence", "play_id"]
pbp = pbp.sort_values(sort_cols, kind="stable").copy()

pbp["previous_timeout_team"] = (
    pbp.groupby("game_id")["timeout_team"].shift(1)
)

fg = pbp.loc[pbp["play_type"].eq("field_goal")].copy()
fg["defensive_timeout_before_kick"] = (
    fg["previous_timeout_team"].eq(fg["defteam"])
)
fg["made"] = fg["field_goal_result"].eq("made")

print(fg.head())