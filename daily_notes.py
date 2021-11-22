#!/usr/local/bin/python3.9
"""
Philosophy
Keep what should be in focus at the top
If start date is in the future, then don't show it on the current daily note
I will think about it when the time comes
"""

import pathlib
import datetime
import argparse
import re
import os
import sys
import traceback
from jinja2 import Environment, FileSystemLoader
from typing import List, Dict, Union, IO
from enum import Enum
import logging
from quotes import QuotesGetter

HOME_DIR = "/Users/sahuja4/Dropbox (Facebook)/Second Brain"
DN_FOLDER = "Dailies"
SCRIPTS_FOLDER = "Scripts"
TEMPLATES_FOLDER = "Templates"

SCRIPT_DIR = f"{HOME_DIR}/{SCRIPTS_FOLDER}"
DN_DIR = f"{HOME_DIR}/{DN_FOLDER}"
TEMPLATE_DIR = f"{HOME_DIR}/{TEMPLATES_FOLDER}"
ARCHIVE_NOTE_NAME = "Archive"
ARCHIVE_NOTE_DIR = f"{DN_DIR}"
SHAME_CHAR = "!"
JINJA_TEMPLATE = "DN.j2"
ARCHIVE_TEMPLATE = "archive.j2"
NOTE_FORMAT = "D%Y%m%d"
DATE_FORMAT = "%Y%m%d"
DATE_PATTERNS = {
    "YYYY-MM-DD": "\d{4}-\d{2}-\d{2}",
    "D%Y%m%d": "\d+",
    "DD-MM-YY": "\d{2}-\d{2}-\d{4}",
    "MM-DD-YYYY": "\d{2}-\d{2}-\d{4}",
}
OPEN_TASK_PATTERN = r"(\s*)-\s+\[(\s|\>)\]\s*(!*)\s*(.*)"
CLOSED_TASK_PATTERN = r"\[x\](.*)"
SHOULD_ARCHIVE = True
SHAME_THRESHOLD = 5
STICKY_CHAR = "~S~"
HIDE_FUTURE_TODOS_FROM_DAILY_NOTE = True
PRESERVE_ORDER = False
dlogger = logging.getLogger(__name__)


class DateNotSupported(Exception):
    pass


class DayNotSupported(Exception):
    pass


class DateTextNotFound(Exception):
    pass


class Action(Enum):
    SHAME = 1
    # ARCHIVE state is for notes that are either in archive
    # or to be archived
    ARCHIVE = 2
    NOOP = 3
    FUTURE = 4


class State(Enum):
    OPEN = 1
    CLOSED = 2
    MOVED = 3


class Todo:
    def __init__(self,
                 raw_text,
                 notename,
                 front_spaces="",
                 todo_marker="x",
                 todo_shame="",
                 todo_text=""):
        self.raw_text = raw_text
        self.src_note = notename
        self.target_note = None
        self.front_spaces = front_spaces
        self.marker = f"[{todo_marker}]"
        self.shame = todo_shame
        self.text = todo_text.strip()
        self.upcoming_shame = ""
        self.action = Action.NOOP
        self.start_date_note = None
        self.get_target_note_from_todo_text()
        self.plan_next_action()

    def set_action(self, action: Action):
        self.action = action

    def get_target_note_from_todo_text(self):
        """The first [[<daily_note>]] which follows the text will be the start_date note name"""
        start_date_regex = r"\[\[(D\d+)\]\]"
        matches = re.findall(start_date_regex, self.raw_text)
        if matches:
            # the last match will blindly be the start date
            self.start_date_note = matches[-1]
            self.text = self.text.split(
                f"[[{self.start_date_note}]]")[0].strip()

    def is_start_date_in_future(self) -> bool:
        if not self.start_date_note:
            return False
        today = datetime.date.today()
        try:
            start_date = get_date_from_note_name(self.start_date_note)
        except DateNotSupported:
            raise DateNotSupported(
                f"Your start date (specified as [[]] at the end of the todo) is not in note format {NOTE_FORMAT}"
            )
        return today < start_date.date()

    def plan_next_action(self):
        # if the note is stickied, don't add shame
        if STICKY_CHAR in self.text:
            return
        # if the note is coming from archive, then it doesn't need shame
        # or action
        if ARCHIVE_NOTE_NAME in self.src_note:
            self.action = Action.ARCHIVE
            return
        # if start date is set to a future date, the don't add shame
        if self.is_start_date_in_future():
            self.action = Action.FUTURE
            self.upcoming_shame = ""
            return
        # if there is no shame, init to 0 len
        if not self.shame:
            shame_meter = ""

        shame_meter = len(self.shame) + 1
        if shame_meter > SHAME_THRESHOLD:
            # No sense of putting shame on an archived todo
            self.action = Action.ARCHIVE
            self.upcoming_shame = ""
        else:
            self.action = Action.SHAME
            self.upcoming_shame = SHAME_CHAR * shame_meter

    def __repr__(self):
        return f"{__class__.__name__}({self.front_spaces} {self.marker} {self.upcoming_shame} {self.text}) {self.action}"

    def __str__(self):
        return f"{self.front_spaces} {self.marker} {self.text})"


def get_date_from_note_name(note_name: str) -> datetime.datetime:
    """Return day date from note_name
    """
    pattern = DATE_PATTERNS.get(NOTE_FORMAT, None)
    if not pattern:
        raise DateNotSupported(f"{NOTE_FORMAT} is not supported")

    t = re.search(pattern, note_name)
    if t and t.group(0):
        date_text = t.group(0)
    else:
        raise DateTextNotFound(
            f"Nothing found inside {note_name} that looks like a  date")
    try:
        note_date = datetime.datetime.strptime(date_text, DATE_FORMAT)
    except Exception as e:
        print(
            f"Trouble in converting {date_text} to note_name, Full error {e}")
    return note_date


def add_day_delta(note_date: datetime.datetime, timedelta: int):
    """Add timedelta to note_date"""
    return note_date + datetime.timedelta(timedelta)


def get_note_name_from_date(note_date: datetime.datetime) -> str:
    """
    note_date: datetime object
    Get note_name from note_date
    """
    return note_date.strftime(NOTE_FORMAT)


def get_note_name_for(target: str, timedelta: int) -> str:
    """Get filenames for target date
    """

    match = re.search(r"\d{4}-\d{2}-\d{2}", target)
    if match:
        target = match.group(0)
    # Supported only the iso format YYYY-MM-DD
    dateObject = datetime.datetime.fromisoformat(match.group(0))
    targetDateObject = add_day_delta(dateObject, timedelta)
    return get_note_name_from_date(targetDateObject)


def get_file_path_from_vault(notename, directory):
    """Search for a note inside the entire vault
    """
    matches = pathlib.Path(directory).glob(f"**/{notename}.md")
    return list(matches)


def get_file_content(notename: str, directory=DN_DIR) -> IO:
    """get file content from filename, from directory

    """
    try:
        filename = f"{directory}/{notename}.md"
        filePath = pathlib.Path(filename)
        if not filePath.is_file():
            # it's possible the file changes dirs, so search for it
            discovered_file_path = get_file_path_from_vault(notename, HOME_DIR)
            if not discovered_file_path:
                raise FileNotFoundError(
                    f"Unable to locate file {filename} in vault {HOME_DIR}")
            filename = discovered_file_path[0]

        return open(filename, "r+").read().rstrip()
    except Exception as e:
        dlogger.error(f"Unable to get file {filename} content: {e}")
        traceback.print_exc()
        sys.exit(1)


def find_pattern_in_file(notename: str, pattern, dir_path=None) -> List[Todo]:
    """
    Filters the text within the note content to find matching lines against
    something that looks similar to - [ ] <todo text>
    """
    matching_lines = []
    note_text = get_file_content(notename, dir_path)
    for line in note_text.split("\n"):
        m = re.search(pattern, line)
        if m and m.group(0):
            matching_lines.append(
                Todo(raw_text=m.group(0),
                     notename=notename,
                     front_spaces=m.group(1),
                     todo_marker=m.group(2),
                     todo_shame=m.group(3),
                     todo_text=m.group(4)))
    return matching_lines


def find_pattern_in_files(FILE_DIR: str, pattern: str) -> List[Todo]:
    """find pattern in all files (not subdirectories) in FILE_DIR"""
    matched_patterns = []
    for root, d_name, f_names in os.walk(f"{DN_DIR}"):
        for fname in f_names:
            if fname.startswith("."):
                # want to ignore hidden files
                continue
            notename = fname.split(".")[0]
            matches = find_pattern_in_file(notename, pattern, root)
            if matches:
                matched_patterns.extend(matches)
    return matched_patterns


def format_todos_by_action(todos: List[str],
                           original_note_name=None) -> List[str]:
    """Format todos for the new note
    This is needed because of the need to have the best possible
    information infront of me. Tasks that are meant for a future day
    are not presented today. Spaces are respected so sub-lists order can be
    maintained
    """
    formatted_todos = []
    for todo in todos:
        new_todo = f"{todo.front_spaces}- [ ] {todo.upcoming_shame} {todo.text}"
        if todo.action == Action.SHAME:
            formatted_todos.append(new_todo)
        elif todo.action == Action.FUTURE:
            # if the future todos are to be hidden from the DN
            if HIDE_FUTURE_TODOS_FROM_DAILY_NOTE:
                continue
            else:
                formatted_todos.append(new_todo)
        elif todo.action == Action.ARCHIVE:
            # add a backlink to original note
            new_todo = (f"{todo.front_spaces}- [ ] {todo.text}")
            formatted_todos.append(new_todo)
        elif todo.action == Action.NOOP:
            # make sure that the marker for the todo is not moved
            # for backlinked todos, can be solved better by managing
            # state of the todo
            moved_to_open = todo.raw_text.replace("[>]", "[ ]")
            moved_to_open = moved_to_open.split(
                f"[[{todo.start_date_note}]]")[0].rstrip()
            formatted_todos.append(f"{moved_to_open}")

    return formatted_todos


def write_file(notename, content, directory=DN_DIR):
    """Write out file in daily note directory
    """
    filename = f"{directory}/{notename}.md"
    with open(filename, "w+") as f:
        f.write(content)
    dlogger.info(f"Successfully wrote {len(content)} lines to {filename}")


def add_content_to_archive(filename, todos):
    file_loader = FileSystemLoader(SCRIPT_DIR)
    env = Environment(loader=file_loader)
    template = env.get_template(ARCHIVE_TEMPLATE)
    rendered_note = template.render(tasks=todos)
    return rendered_note


def add_content_to_note_template(filename, todos):
    """Publish the filename content to daily note jinja template
    """
    file_loader = FileSystemLoader(SCRIPT_DIR)
    env = Environment(loader=file_loader)
    template = env.get_template(JINJA_TEMPLATE)
    note_date = get_date_from_note_name(filename)
    tmrw_date = add_day_delta(note_date, 1)
    tmrw_note_name = get_note_name_from_date(tmrw_date)
    yester_date = add_day_delta(note_date, -1)
    yester_note_name = get_note_name_from_date(yester_date)
    quote = QuotesGetter().get_a_random_quote()
    rendered_note = template.render(tasks=todos,
                                    DN_DIR=DN_FOLDER,
                                    yesterday_note_name=yester_note_name,
                                    tomorrow_note_name=tmrw_note_name,
                                    quote=quote)
    return rendered_note


def replace_open_with_moved_todos(notename):
    """Replace open [ ] with moved todo symbol [>]
    to differentiate between open and close todos
    """
    note = get_file_content(notename)
    modified_content = re.sub(r"\[\s\]", r"[>]", note)
    return modified_content


def get_open_todos(notename: str):
    """Get todos with the pattern [ ]
    """
    open_todos = find_pattern_in_file(notename, OPEN_TASK_PATTERN, DN_DIR)
    # check if there are any backlinked todos:
    dlogger.info(f"{len(open_todos)} open todos found in {notename}.md")
    return open_todos


def get_backlink_todos(notename: str):
    """backlinked todos will have a date set to future, so if their start date is
    the note for which the todos are being created, then their action should be
    NOOP
    """
    pattern = OPEN_TASK_PATTERN + f"\[\[({notename})\]\]"
    backlink_todos = find_pattern_in_files(DN_DIR, pattern)
    dlogger.info(
        f"{len(backlink_todos)} backlinked todo(s) found for note {notename}")
    for todo in backlink_todos:
        todo.set_action(Action.NOOP)
    return backlink_todos


def render_archive_template(todos, template=ARCHIVE_TEMPLATE):
    file_loader = FileSystemLoader(SCRIPT_DIR)
    env = Environment(loader=file_loader)
    template = env.get_template(template)
    rendered_note = template.render(tasks=todos)
    return rendered_note


def get_current_archived_todos(to_be_archived_todos,
                               notename=ARCHIVE_NOTE_NAME):
    # format these existing_todos by getting the open todos in archive
    todos_in_archive = get_open_todos(notename)
    dlogger.info(f"Found {len(todos_in_archive)} todos in current archive..")
    dlogger.debug(f"Currently Archives todos are {todos_in_archive}")
    return todos_in_archive


def deduplicate_todos(todos: List[Todo]):
    """Remove duplicates
    """
    dedup_todos = []
    seen = set()
    for todo in todos:
        thash = hash(todo.text)
        if thash in seen:
            continue
        else:
            dedup_todos.append(todo)
            seen.add(thash)
    dlogger.debug(f"Post deduplication, todos look like this {dedup_todos}")
    return dedup_todos


def filter_todos_by_action(todos: List[Todo],
                           include_action: Action = None,
                           exclude_action: Action = None):
    if not include_action and not exclude_action:
        return todos
    if include_action:
        return [todo for todo in todos if todo.action == include_action]
    if exclude_action:
        return [todo for todo in todos if todo.action != exclude_action]


def reorder_todos(today_todos: List[Todo]):
    # shame first, next noop, next future, followed by archive
    shamed_todos = filter_todos_by_action(today_todos,
                                          include_action=Action.SHAME)
    # for daily notes, noop would be stickied todos
    noop_todos = filter_todos_by_action(today_todos,
                                        include_action=Action.NOOP)
    archived_todos = filter_todos_by_action(today_todos,
                                            include_action=Action.ARCHIVE)
    future_todos = filter_todos_by_action(today_todos,
                                          include_action=Action.FUTURE)

    return shamed_todos + noop_todos + future_todos + archived_todos


def generate_daily_note(config: Dict[str, Union[str, bool]]):
    """Tommorrow note will not have the archived todos
    Workflow
    Get all open todos from today and extract todos which are shamed
    and to be included in tomorrow's note, as well as archived todos
    get backlinked todos for tomorrow, and ad them to the shamed todos
    write out the DN.j2 template, and finally write out tomorrow's note
    and write archived notes to Archive note
    """

    today_note_name = get_note_name_for(config["day_date"], timedelta=0)
    yesterday_note_name = get_note_name_for(config["day_date"], timedelta=-1)

    yesterday_todos = get_open_todos(yesterday_note_name)
    # reorder by what feels best
    if not PRESERVE_ORDER:
        yesterday_todos = reorder_todos(yesterday_todos)
    backlinked_todos = get_backlink_todos(today_note_name)
    # Add todos to tomorrow's note and write it out to a file
    tmrw_todos_dedup = deduplicate_todos(
        backlinked_todos +
        filter_todos_by_action(yesterday_todos, exclude_action=Action.ARCHIVE))
    formatted_tmrw_todos = format_todos_by_action(tmrw_todos_dedup)
    templatified_note = add_content_to_note_template(today_note_name,
                                                     formatted_tmrw_todos)
    # Make sure that we close out on pending tasks
    modified_today_note = replace_open_with_moved_todos(yesterday_note_name)

    # Now add stuff to archive
    # this involves, getting the current todos->combining them with new
    # archived todos -> removing duplicates -> formatting them -> adding to
    # archive template -> write file
    to_be_archived_todos = filter_todos_by_action(
        yesterday_todos, include_action=Action.ARCHIVE)
    current_archived_todos = get_current_archived_todos(to_be_archived_todos)
    all_archive_todos = current_archived_todos + to_be_archived_todos
    dedup_archived_todos = deduplicate_todos(all_archive_todos)
    dedup_archived_todos_formatted = format_todos_by_action(
        dedup_archived_todos, yesterday_note_name)
    archive_content = render_archive_template(dedup_archived_todos_formatted)

    if config["disable_writes"]:
        dlogger.info(templatified_note)
        return

    if config["only_write_to_archive"]:
        write_file(ARCHIVE_NOTE_NAME, archive_content)

    if config["only_write_to_daily_notes"]:
        write_file(today_note_name, templatified_note)
        write_file(yesterday_note_name, modified_today_note)


def generate_daily_notes(config: Dict[str, Union[str, bool]]):
    """
    The launchctl facility in macOS has a peculiarity where if the
    system doesn't run (not logged in) for some days, then only the latest
    instance of the job is run
    for example, if I logged into the system on 17th March 2021, and then
    logged back on 19th March 2021, launchctl would run the daily notes job for
    19th only, and not for 18th. This becomes a problem because the code would
    use the daily notes for 18th to generate the ones for 19th, and missing
    todos for 18th means no todos for 19th.
    this function will scan the DN dir for the last generate note, and count
    back from current date upto that date to generate notes from last generated
    date to today's date if the --upto cli option is set
    """
    if not config["up_to_today"]:
        generate_daily_note(config)
        return

    notes = [
        f for f in os.listdir(DN_DIR)
        if os.path.isfile(os.path.join(DN_DIR, f))
    ]
    notes.sort()
    last_created_note_name = notes[-1]
    last_note_date = get_date_from_note_name(last_created_note_name)
    config_day_date = datetime.datetime.strptime(config["day_date"],
                                                 "%Y-%m-%d")
    difference = (config_day_date - last_note_date).days
    for i in range(difference, -1, -1):
        config["day_date"] = add_day_delta(config_day_date,
                                           -i).strftime("%Y-%m-%d")
        generate_daily_note(config)


def _configure_logger():
    dlogger.setLevel(level=logging.INFO)
    # log_format = "%(asctime)s:[%(name)s:%(lineno)d] %(levelname)s:%(message)s"
    logging.basicConfig(
        format=
        '%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d:%H:%M:%S')


def set_options_and_generate_notes(args: argparse.Namespace):
    """
    This function acts as an intermediary between cli options,
    and the config fed to generate_daily_notes
    This intermediary method allows me to set logging levels for now
    and is a pretty ugly way to modify the args
    """
    _configure_logger()
    today = datetime.date.today()
    config = {
        "day_date": today.isoformat(),
        "disable_writes": False,
        "only_write_to_archive": True,
        "only_write_to_daily_notes": True,
        "up_to_today": False,
    }

    if args:
        # parse the argparse arguments
        if args and args.z:
            # with debug mode , we disable file writing regardless of
            # other options
            dlogger.setLevel(level=logging.DEBUG)

        config["up_to_today"] = args.up_to_today
        config["day_date"] = args.day_date
        if args and args.no_write_out:
            config["disable_writes"] = True
        elif args and args.only_write_to_archive:
            config["only_write_to_daily_notes"] = False
        elif args and args.only_write_to_daily_notes:
            config["only_write_to_archive"] = False

    generate_daily_notes(config)


if __name__ == "__main__":
    set_options_and_generate_notes()
