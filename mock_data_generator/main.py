"""Entry point for the mock data generator CLI application."""

import argparse

import pandas as pd

from mock_data_generator.artist import PlotArtist
from mock_data_generator.util import get_response


def get_args() -> argparse.Namespace:
    """Retrieve command line arguments and prompt the user for any missing arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--start", type=pd.Timestamp, help="Start time")
    parser.add_argument("-e", "--end", type=pd.Timestamp, help="End time")
    parser.add_argument("-tz", "--timezone", type=str, help="Timezone")
    parser.add_argument("-tc", "--time-col", type=str, help="Name of column to use for time index")
    parser.add_argument("-b", "--y-min", type=float, help="Minimum y value")
    parser.add_argument("-t", "--y-max", type=float, help="Maximum y value")
    parser.add_argument("-p", "--period", type=pd.Timedelta, help="Period in minutes")
    parser.add_argument(
        "-c",
        "--constants",
        type=str,
        help="Comma-separated columns with constant values (e.g. block_id=1000, array_index=1)",
    )
    args = parser.parse_args()
    return prompt_user_for_args(args)


def prompt_user_for_args(args) -> argparse.Namespace:
    """Retrieve any missing arguments from the user."""
    if args.start is None:
        args.start = get_response("Enter Start Time (Default 2023-01-01 00:00:00): ", default="2023-01-01")
    if args.end is None:
        args.end = get_response("Enter End Time (Default 2023-01-02 00:00:00): ", default="2023-01-02")
    if args.timezone is None:
        args.timezone = get_response("Enter Timezone (Default UTC): ", default="UTC")
    if args.period is None:
        args.period = get_response(
            "Enter Expression for Period [Must be Convertable to pd.Timedelta] (Default 5min): ",
            default="5min",
        )
    if args.y_min is None:
        args.y_min = get_response("Enter Minimum y Value (Default 0): ", default="0")
    if args.y_max is None:
        args.y_max = get_response("Enter Maximum y Value (Default 100): ", default="100")
    if args.time_col is None:
        args.time_col = get_response(
            "Enter Name of Time Column (Default 'timestamp'): ", default="timestamp"
        )
    if args.constants is None:
        args.constants = get_response(
            "Enter Constant Values [e.g. id=1, version=3] (Default None): ",
        )
    return coerce_arg_types(args)


def coerce_arg_types(args: argparse.Namespace) -> argparse.Namespace:
    """Take a Namespace object with all arguments and coerce them to the right types."""
    try:
        args.start = pd.Timestamp(args.start, tz=args.timezone)
    except ValueError:
        raise ValueError("args.start must be convertable to pd.Timestamp")
    try:
        args.end = pd.Timestamp(args.end, tz=args.timezone)
    except ValueError:
        raise ValueError("args.end must be convertable to pd.Timestamp")
    try:
        args.period = pd.Timedelta(args.period)
    except ValueError:
        raise ValueError("args.period must be convertable to pd.Timedelta")
    try:
        args.y_min = float(args.y_min)
    except ValueError:
        raise ValueError("args.y_min must be convertable to float")
    try:
        args.y_max = float(args.y_max)
    except ValueError:
        raise ValueError("args.y_max must be convertable to float")
    if args.constants:
        args.constants = dict([x.split("=") for x in args.constants.split(",")])
    else:
        args.constants = {}

    assert args.y_min < args.y_max, "y_min must be less than y_max"
    assert args.start < args.end, "Start time must be before the end"
    assert args.period < args.end - args.start, "Period must be less than the time range"
    return args


def create_interactive_session(args: argparse.Namespace):
    """Launch an interactive session of the plot artist.

    This allows the user draw timeseries on an interactive canvas and save the results as a CSV file
    """
    app = PlotArtist(
        start=args.start,
        end=args.end,
        y_min=args.y_min,
        y_max=args.y_max,
        period=args.period,
        time_col=args.time_col,
        constants=args.constants,
    )
    print("-" * 55 + "\nStarting Drawing Session\n" + "-" * 55)
    app.start_loop()


if __name__ == "__main__":
    print("=" * 55)
    print("Welcome to the Mock Data Generator!")
    print("This application allows you to draw a series of points on a plot and save the data to a file.")
    print("=" * 55 + "\n")
    args = get_args()
    create_interactive_session(args)
