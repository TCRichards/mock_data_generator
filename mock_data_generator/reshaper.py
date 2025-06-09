"""A script to convert a CSV from wide to long format in order to match the format of summary reports."""

import os
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd

from mock_data_generator.util import ask_user, get_response


def reshape_to_long(
    df_wide: Optional[pd.DataFrame] = None,
    time_col: Optional[str] = None,
    num_sets: Optional[int] = None,
    grouping_col: Optional[str] = None,
    save_path: Union[str, Path, None] = None,
    constants: dict[str, Any] = {},
):
    """Reshape a wide DataFrame to long format.

    The "wide" dataframe is expected to have one column per time series.
    The "long" result groups columns that correspond to the same metric
    but different sources (e.g. different sensors) into a single column,
    with another column specified for.

    If any args are not provided, the user will be prompted to enter them through the command line.

    Args:
        df_wide: The wide DataFrame to reshape.
        time_col: The name of the column that contains the time data.
        num_sets: The number of sets of measurements to unpivot.
        grouping_col: The name of the column that will be created to group like measurements.
        save_path: The path to save the reshaped data to.
        constants: A dictionary mapping {column_name: value} with constants to add to the DataFrame.
    """
    df_wide, time_col, num_sets, grouping_col = get_args(df_wide, time_col, num_sets, grouping_col)
    df_long = reshape(df_wide, time_col, num_sets, grouping_col, constants)
    prompt_save_data(df_long, save_path)
    return df_long


def get_args(
    df: Optional[pd.DataFrame],
    time_col: Optional[str] = None,
    num_sets: Optional[int] = None,
    grouping_col: Optional[str] = None,
) -> tuple[pd.DataFrame, str, int, str]:
    """Prompt the user for any missing arguments."""
    if df is None:
        csv_path = get_response(
            "Enter the path to the CSV file (absolute or relative to this file): ", allow_empty=False
        )
        if not Path(csv_path).exists():
            csv_path = Path(__file__).parent / csv_path
            if not csv_path.exists():
                raise FileNotFoundError(f"File not found: {csv_path}")
        df = pd.read_csv(csv_path)
    if num_sets is None:
        num_sets = int(get_response("Enter the number of sets of measurements: ", allow_empty=False))
    if grouping_col is None:
        grouping_col = get_response(
            "Enter the name for the grouping column (e.g. sensor_index): ", allow_empty=False
        )
    if time_col is None:
        time_col = df.columns[0]
    return df, time_col, num_sets, grouping_col


def reshape(
    df: pd.DataFrame,
    time_col: str,
    num_sets: int,
    grouping_col: str,
    constants: dict[str, Any] = {},
):
    """Run the reshape algorithm to convert from wide to long format."""
    # The list to hold each melted dataframe
    melted_dfs = []

    for i in range(num_sets):
        num = ordinal(i + 1)

        # Which measurement to unpivot
        value_column_name = get_response(
            f"Enter the destination name for the {num} first measurement column (e.g. avg_voltage): ",
            allow_empty=False,
        )

        def response_is_column(response: str) -> bool:
            """Returns whether a comma-separated string contains only column in the DataFrame."""
            cols = response.replace(" ", "").split(",")
            missing_cols = [col for col in cols if col not in df.columns]
            if missing_cols:
                print(f"Columns not found: {missing_cols}")
            return not missing_cols

        # Which column names correspond to the current measurement
        unpivot_columns_str = get_response(
            "Enter the comma-separated names of the columns that correspond to "
            f"{value_column_name} (e.g. v1, v2): ",
            allow_empty=False,
            condition=response_is_column,
        )
        unpivot_columns = unpivot_columns_str.replace(" ", "").split(",")

        # How column names correspond to the identifier
        identifier_mapping = {}
        for unpivot_column in unpivot_columns:
            mapped_identifier = get_response(
                f"What {grouping_col} does {unpivot_column} correspond to: ",
                allow_empty=False,
            )
            identifier_mapping[unpivot_column] = mapped_identifier

        # Perform the melt operation for each set of columns
        melted_set = pd.melt(
            df,
            id_vars=[time_col],
            value_vars=unpivot_columns,
            var_name=grouping_col,
            value_name=value_column_name,
        )

        # Replace the identifier values with the mapped values
        melted_set[grouping_col] = melted_set[grouping_col].replace(to_replace=identifier_mapping)

        # Append the result to the list
        melted_dfs.append(melted_set)

    # Merge all the melted dataframes on the identifier column and time
    final_melted_df = melted_dfs[0]
    if len(melted_dfs) > 1:
        for merge_df in melted_dfs[1:]:
            final_melted_df = final_melted_df.merge(merge_df, on=[time_col, grouping_col], how="outer")

    # Sort the DataFrame by the time column
    final_melted_df = final_melted_df.sort_values(by=time_col)

    # Add constants to the DataFrame
    for constant_col, value in constants.items():
        final_melted_df[constant_col] = value

    return final_melted_df


def prompt_save_data(df: pd.DataFrame, save_path: Union[str, Path, None] = None):
    """Prompt the user to save the reshaped data to a file."""
    if save_path is None:
        if not ask_user("Do you want to save the reshaped data to a file? [y/n]: "):
            return False
        save_path = Path(
            get_response(
                "Enter the path to save the reshaped data (absolute or in output dir): ",
                allow_empty=False,
            )
        )

    output_dir = Path(__file__).parent.parent / "output"
    save_path = Path(save_path)
    save_path = save_path if save_path.is_absolute() else output_dir / save_path
    os.makedirs(save_path.parent, exist_ok=True)

    df.to_csv(save_path, index=False)
    print(f"Data saved to {save_path}")


def ordinal(n: Union[int, str]) -> str:
    """Return the ordinal representation of a number (e.g. convert 1 to "1st")."""
    n = int(n)
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return str(n) + suffix


if __name__ == "__main__":
    reshape_to_long()
