"""Contains the PlotArtist class which can be used to generate mock timeseries data for testing."""

import os
import time
from collections import namedtuple
from pathlib import Path
from typing import Any, Optional

import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd

import mock_data_generator.reshaper as reshaper
from mock_data_generator.util import ask_user, get_response

# A nice way to represent a point with x and y coordinates
Point = namedtuple("Point", ["x", "y"])


class PlotArtist:
    """This class manages an interactive matplotlib canvas where the user can draw mock data.

    The user can draw multiple series, and then save the data to a file in wide or long format.
    """

    def __init__(
        self,
        start: pd.Timestamp,
        end: pd.Timestamp,
        y_min: float,
        y_max: float,
        period: pd.Timedelta,
        time_col: str,
        constants: dict[str, Any] = {},
    ):
        """Initialize the PlotArtist.

        Args:
            start: The start time of the time range
            end: The end time of the time range
            y_min: The minimum y value allowed on the plot
            y_max: The maximum y value allowed on the plot
            period: The period between allowed x coordinates
            time_col: The name of the time column
            constants: A dictionary mapping {column_name: value} with constants to add to the DataFrame.
        """
        # Time range
        self.start = start
        self.end = end
        assert self.start.tzinfo == self.end.tzinfo
        self.tz = self.start.tzinfo
        self.time_col = time_col

        # Allowed x coordinates
        self.period = period
        self.allowed_x = pd.date_range(start, end - pd.Timedelta("1s"), freq=period)

        # How much extra space to add to the left and right of the start and end on the plot
        self.x_buffer = self.period / 3

        # Y range
        self.y_min = y_min
        self.y_max = y_max

        # Columns with constant values
        self.constants = constants

        # DataFrame storing all the points for each series
        index = pd.DatetimeIndex(self.allowed_x, name=self.time_col)
        self.df = pd.DataFrame(index=index)

        # A list of (x, y) points that have been drawn for the current series
        self.points: list[Point] = []

        # The current series's most recent x coordinate (future points must be greater than this)
        self.current_x = None

        # Colors for the series
        self.colors = ["blue", "green", "cyan", "purple", "orange", "brown", "pink", "gray", "olive"]

        # Initialize plot
        self.figure, self.ax = plt.subplots()
        self.initialize_plot()

    def initialize_plot(self):
        """Set the plot limits and labels."""
        self.format_x_axis_times()
        self.ax.set_xlim(self.start - self.x_buffer, self.end + self.x_buffer)  # type: ignore
        self.ax.set_ylim(self.y_min, self.y_max)
        self.ax.set_xlabel(f"{self.time_col} {'(' + str(self.tz) +')' if self.tz else ''}")
        self.ax.set_ylabel("Value")
        self.draw_vertical_lines()

    def format_x_axis_times(self):
        """Handle the date formatting for x axis."""
        month_range = (self.end.year - self.start.year) * 12 + self.end.month - self.start.month
        day_range = (self.end - self.start).days

        # Determine whether to include month or day based on the range of the time period
        if month_range > 1:
            date_component = "%m-%d"
        elif day_range > 1:
            date_component = "-%d"
        else:
            date_component = ""

        # Determine granularity of time component based on period
        time_component = "%H"
        if self.period < pd.Timedelta("1min"):
            time_component += "%M:%S"
        elif self.period < pd.Timedelta("1h"):
            time_component = "%M"

        # Apply the formatting to the x axis
        xfmt = mdates.AutoDateFormatter(date_component + " " + time_component)
        self.ax.xaxis.set_major_formatter(xfmt)
        plt.xticks(rotation=45)

    def start_loop(self):
        """Start an open-ended loop to draw multiple time series."""
        self.draw_series()
        if ask_user("Draw another series? [y/n]: "):
            if ask_user("Change Y range? [y/n]: "):
                self.y_min = float(get_response("Enter new Y min: "))
                self.y_max = float(get_response("Enter new Y max: "))
                self.ax.set_ylim(self.y_min, self.y_max)
                self.figure.canvas.draw()
            return self.start_loop()
        self.prompt_save_data()

    def draw_series(self):
        """Start drawing a single time series until it's complete."""
        name = get_response("Enter Series Name: ", allow_empty=False)
        cur_points = len(self.points)
        self.add_to_legend(name)

        while True:
            continue_loop = self.add_points()
            for p in self.points[cur_points:]:
                x, y = p
                assert isinstance(x, pd.Timestamp) and isinstance(y, float)
            if not continue_loop:
                break
            cur_points = len(self.points)

        # Remove duplicate points and sort by x coordinate
        self.points = sorted(list(set(self.points)), key=lambda point: point.x)
        valid = self.verify_points()
        if not valid:
            print("Received invalid points")
        self.finish_series(name)

    def add_to_legend(self, new_series_name: str):
        """Add an entry for the new series to the legend."""
        existing_cols = list(self.df.columns) if len(self.df.columns) else []
        columns = existing_cols + [new_series_name]
        colors = self.colors[: len(columns)]
        patches = [mpatches.Patch(color=color, label=col) for color, col in zip(colors, columns)]
        self.ax.legend(handles=patches, loc="upper right")

    def finish_series(self, name: str):
        """When all points for a series have been drawn, add it to the DataFrame and reset."""
        self.df[name] = [p.y for p in self.points]
        self.points.clear()
        self.current_x = None

    def prompt_save_data(self):
        """Prompt the user to save the data to a csv file."""
        # Add constant columns to the DataFrame
        for constant_col, value in self.constants.items():
            self.df[constant_col] = value

        if ask_user("Save data in wide format (one column per series)? [y/n]: "):
            save_path = Path(
                get_response("Enter destination file path (absolute or in output dir): ", allow_empty=False)
            )
            output_dir = Path(__file__).parent.parent / "output"
            save_path = save_path if save_path.is_absolute() else output_dir / save_path
            os.makedirs(save_path.parent, exist_ok=True)
            self.df.to_csv(save_path)
            print(f"Data saved to {save_path}")

        if ask_user("Reshape data to long format (group like columns)? [y/n]: "):
            reshaper.reshape_to_long(
                df_wide=self.df.reset_index(), time_col=self.time_col, constants=self.constants
            )

    def draw_vertical_lines(self):
        """Add semi-transparent vertical lines at each period."""
        for x in self.allowed_x:
            self.ax.axvline(x=x, color="red", linewidth=1, alpha=0.6)
        plt.draw()

    def add_points(self) -> bool:
        """Add a point and draw a line connecting to it.

        Returns:
            Whether to keep running the loop.
            i.e. True if there are remaining points, False if all points are drawn
        """
        xys = plt.ginput()
        if len(xys) == 0:
            return False

        x_sel, y = xys[0]
        target_x = self.get_target_x_coord(x_sel)
        if target_x is None:
            return True

        self.plot_selection(target_x, y)
        return self.current_x != self.allowed_x[-1]

    def get_target_x_coord(self, x_sel: float) -> Optional[pd.Timestamp]:
        """In response to a user's click, determine the snapped x coordinate.

        Args:
            x_sel: The x coordinate where the user clicked

        Returns:
            The closest allowed x-coordinate to the user's click
        """
        # Take advantage of the fact that allowed_x is sorted
        if self.current_x is None:
            # For the first point, always start as the first allowed coordinate
            target_x = self.allowed_x[0]
        else:
            # If the x axis is a date, x_sel is in hours since epoch
            x_to_seconds = x_sel * 60 * 60 * 24
            time_struct = time.gmtime(x_to_seconds)
            x_pd = pd.Timestamp(
                year=time_struct.tm_year,
                month=time_struct.tm_mon,
                day=time_struct.tm_mday,
                hour=time_struct.tm_hour,
                minute=time_struct.tm_min,
                second=time_struct.tm_sec,
                tz=self.tz,
            )
            x_ordered = sorted(
                [x for x in self.allowed_x if x > self.current_x],
                key=lambda x: abs(x - x_pd),
            )
            if len(x_ordered) == 0:
                return None
            target_x = x_ordered[0]
        return target_x

    def plot_selection(
        self,
        x_snapped: pd.Timestamp,
        y: float,
    ):
        """Add a line and points to the plot in response to a user's click.

        Args:
            x_snapped: The final x coordinate in the selection
                       (where the user clicked snapped to allowed x coordinates)
            y: The y coordinate where the user clicked
        """
        # Where should the line start from
        prev_x, prev_y = self.points[-1] if len(self.points) else (None, None)

        # If the x coordinate is greater than the current x coordinate, interpolate the points
        if (
            prev_x is not None
            and prev_y is not None
            and self.current_x is not None
            and x_snapped > (self.current_x + self.period)
        ):
            delta = x_snapped - prev_x
            if isinstance(x_snapped, pd.Timestamp):
                delta = (x_snapped - prev_x).total_seconds() / 60
            slope = (y - prev_y) / delta

            for x_intermediate in pd.date_range(
                self.current_x + self.period, x_snapped, freq=self.period, inclusive="left"
            ):
                delta = prev_x - x_intermediate
                if isinstance(x_snapped, pd.Timestamp):
                    delta = (prev_x - x_intermediate).total_seconds() / 60
                y_intermediate = prev_y - slope * delta
                self.points.append(Point(x_intermediate, y_intermediate))
                self.plot_point(x_intermediate, y_intermediate)

        # Add the final point and line
        self.plot_point(x_snapped, y)
        if prev_x is not None and prev_y is not None:
            self.ax.plot([prev_x, x_snapped], [prev_y, y], color=self.color, linewidth=2)
        self.points.append(Point(x_snapped, y))
        self.current_x = x_snapped

        # Update the plot with the new lines
        self.figure.canvas.draw()

    def plot_point(self, x, y):
        """Add a single point to the plot."""
        self.ax.plot(x, y, marker="o", color=self.color, linewidth=5)

    def verify_points(self):
        """Validate that the final list of points are all on valid x coordinates."""
        if len(self.points) != len(self.allowed_x):
            return False
        for p in self.points:
            if p[0] not in self.allowed_x:
                return False
        return True

    @property
    def series_idx(self):
        """The zero-based index of the current series."""
        return len(self.df.columns)

    @property
    def color(self):
        """The color to use for the current series."""
        return self.colors[self.series_idx % len(self.colors)]
