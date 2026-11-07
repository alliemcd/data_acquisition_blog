# Does Icing the Kicker Work?

This project looks at whether a defensive timeout immediately before a field goal is associated with a lower chance of making the kick. I became interested in the question while watching football with my sister and wondering whether “icing the kicker” actually works.

This is a class project using NFL play-by-play data. The results show associations in the data; they do not prove that a timeout caused a kick to be missed.

## Data

I used [`nflreadpy`](https://nflreadpy.nflverse.com/) to download play-by-play data from [nflverse](https://github.com/nflverse) for the 2016–2025 seasons. The source data include information about the game, teams, play, kicker, field goal attempt, and game conditions.

I selected relevant fields, sorted plays within each game, and kept field goal attempts. The resulting dataset has one row per attempt. I defined a defensive timeout before a kick as a timeout recorded on the preceding play where the timeout team matched the field goal attempt’s defensive team. This is a working definition of icing the kicker; the data do not tell us why a timeout was called.

## Analysis

I compared field goal make rates for attempts with and without a defensive timeout immediately before the kick. I also summarized make rates by kick distance and other game conditions.

For a more specific comparison, I grouped kicks with the same:

- Kicker
- Exact kick distance
- Home or away status
- Time until the end of the half
- Score state
- Wind group
- Stadium roof

I kept groups that had both timeout and no-timeout attempts. The difference in each group is the timeout group’s make rate minus the no-timeout group’s make rate. A negative value means the timeout group had a lower make rate in that circumstance.

## Repository contents

- `src/data_acquisition_blog/nfl_data.py` — Python code for downloading, preparing, and analyzing the data.
- `data/field_goal_attempts_full.csv` — Field goal attempts and analysis variables.
- `data/overall_summary.csv` — Overall make rates with and without a preceding defensive timeout.
- `data/summary_by_comparison_group.csv` — Make rates across groups such as distance, game situation, weather, and roof.
- `data/matched_circumstances.csv` — Make rates and differences for circumstances with both timeout and no-timeout attempts.
- `pyproject.toml` and `uv.lock` — Project and package information for `uv`.
- `README.md` — Project overview and instructions.

## Reproducing the analysis

Install the project dependencies with `uv`:

```bash
uv sync
```

Then run the analysis script
```bash
uv run python src/data_acquisition_blog/nfl_data.py
```