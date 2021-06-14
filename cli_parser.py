import argparse
from daily_notes import set_options_and_generate_notes


def parse():
    parser = argparse.ArgumentParser()

    parser.add_argument("-z",
                        "-debug-mode",
                        action="store_true",
                        help="start debug level logging")
    parser.add_argument(
        '--target',
        dest='day_date',
        default="tomorrow",
        help=("date for which note is to be created in YYYY-MM-DD format "
              "e.g. 2021-04-01 (default is tomorrow)"))
    parser.add_argument(
        "-n",
        "--no-write-out",
        action="store_true",
        help=
        "The script will show all logging output but not write out the files")
    parser.add_argument(
        "-a",
        "--only-write-to-archive",
        action="store_true",
        help=
        "The script will only generate the new archive file, and ignore daily_notes"
    )
    parser.add_argument(
        "-d",
        "--only-write-to-daily-notes",
        action="store_true",
        help=
        "The script will only generate the daily_notes file, and ignore archive"
    )

    args = parser.parse_args()
    set_options_and_generate_notes(args)


if __name__ == "__main__":
    parse()
