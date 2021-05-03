#!/usr/local/bin/python3.9

import datetime
import re
import os
from jinja2 import Template, Environment, FileSystemLoader
import glob
from typing import List
from enum import Enum

HOME_DIR="/Users/sahuja4/Dropbox (Facebook)/Second Brain/"
DN_FOLDER="Dailies"
SCRIPTS_FOLDER="Scripts"
TEMPLATES_FOLDER="Templates"

SCRIPT_DIR=f"{HOME_DIR}/{SCRIPTS_FOLDER}"
DN_DIR=f"{HOME_DIR}/{DN_FOLDER}/"
TEMPLATE_DIR=f"{HOME_DIR}/{TEMPLATES_FOLDER}/"
ARCHIVE_NOTE_NAME="Archive"
ARCHIVE_NOTE_DIR=f"{DN_DIR}"
SHAME_CHAR = "!"
JINJA_TEMPLATE="DN.j2"
ARCHIVE_TEMPLATE="archive.j2"
NOTE_FORMAT="D%Y%m%d"
DATE_FORMAT="%Y%m%d"
DATE_PATTERNS = {
    "YYYY-MM-DD": "\d{4}-\d{2}-\d{2}",
    "D%Y%m%d": "\d+",
    "DD-MM-YY": "\d{2}-\d{2}-\d{4}",
    "MM-DD-YYYY": "\d{2}-\d{2}-\d{4}",
}
OPEN_TASK_PATTERN=r"(\s*)-\s+\[(\s|\>)\]\s*(!*)\s*(.*)"
CLOSED_TASK_PATTERN=r"\[x\](.*)"
SHOULD_ARCHIVE=True
SHAME_THRESHOLD=5

class DateNotSupported(Exception):
    pass

class DayNotSupported(Exception):
    pass

class DateTextNotFound(Exception):
    pass

class Action(Enum):
    SHAME = 1
    ARCHIVE = 2

class State(Enum):
    OPEN = 1
    CLOSED = 2
    MOVED = 3

todo_state_map = {
    "[x]" : State.CLOSED,
    "[ ]" : State.OPEN,
    "[>]" :  State.MOVED,
}

"""Thoughts
filname should be notename.md
notename should be the title of the note
"""

class Todo:
    def __init__(self, raw_text, front_spaces="", todo_marker="x", todo_shame="", todo_text=""):
        self.raw_text = raw_text
        self.front_spaces = front_spaces
        self.marker = f"[{todo_marker}]"
        self.shame = todo_shame
        self.text = todo_text
        # Any unknown state will be open state
        self.state = todo_state_map.get(self.marker, State.OPEN)
        self.upcoming_shame=""
        self.action=None
        self.plan_next_action()

    def plan_next_action(self):
        # if there is no shame, init to 0 len
        if not self.shame:
            shame_meter = ""
        shame_meter = len(self.shame) + 1
        if shame_meter > SHAME_THRESHOLD:
            self.action = Action.ARCHIVE
        else:
            self.action = Action.SHAME
            self.upcoming_shame = SHAME_CHAR * shame_meter

    def __repr__(self):
        return f"{__class__.__name__}({self.front_spaces} [{self.marker}] {self.text})"

    def __str__(self):
        return f"{self.front_spaces} [{self.marker}] {self.text})"

def get_date_from_note_name(note_name):
    """Return day date from note_name
    """
    pattern = DATE_PATTERNS.get(NOTE_FORMAT, None)
    if not pattern:
        raise DateNotSupported(f"{NOTE_FORMAT} is not supported")

    t = re.search(pattern, note_name)
    if t and t.group(0):
        date_text = t.group(0)
    else:
        raise DateTextNotFound(f"Nothing found inside {note_name} that looks like a  date")
    note_date = datetime.datetime.strptime(date_text, DATE_FORMAT)
    return note_date

def add_day_delta(note_date, timedelta):
    """Add timedelta to note_date"""
    return note_date + datetime.timedelta(timedelta)

def get_note_name_from_date(note_date):
    """Get note_name from note_date"""
    return note_date.strftime(NOTE_FORMAT)

def get_note_name_for(target) -> str:
    """Get filenames for today, tomorrow, and yesterday notes
    """
    today = datetime.date.today()
    if target == "today":
        return get_note_name_from_date(today)
    elif target == "tomorrow":
        tomorrow = add_day_delta(today, 1)
        return tomorrow.strftime(NOTE_FORMAT)
    elif target == "yesterday":
        yesterday = add_day_delta(today, -1)
        return yesterday.strftime(NOTE_FORMAT)

    raise DayNotSupported(f"Within this function, only today, tomorrow, and yesterday functions are supported")

def get_file_content(filename:str, directory=DN_DIR):
    """get file content from filename, from directory
    """
    filename = f"{directory}/{filename}"
    return open(filename, "r+").read().rstrip()

def find_pattern_in_file(filename, pattern):
    matching_lines = []
    note_text = get_file_content(filename)
    for line in note_text.split("\n"):
        m = re.search(pattern, line)
        if m and m.group(0):
            matching_lines.append(
                Todo(raw_text=m.group(0),
                front_spaces=m.group(1),
                todo_marker=m.group(2),
                todo_shame=m.group(3),
                todo_text=m.group(4))
            )
    return matching_lines

def find_pattern_in_files(FILE_DIR, pattern):
    """find pattern in all files (not subdirectories) in FILE_DIR"""
    matched_patterns = []
    for f in glob.glob(f"{FILE_DIR}*.md", recursive=True):
        filename = f.split("/")[-1]
        matches = find_pattern_in_file(filename, pattern)
        if matches:
            matched_patterns.extend(matches)
    return matched_patterns

def add_shame_or_archive(todos: List[str], original_note_name=None):
    """Format todos for the new note"""
    formatted_todos= []
    to_be_archived = []
    for todo in todos:
        new_todo = f"{todo.front_spaces} - [ ] {todo.upcoming_shame} {todo.text}"
        if todo.action == Action.SHAME:
            formatted_todos.append(new_todo)
        elif todo.action == Action.ARCHIVE:
            # add a backlink to original note
            new_todo += f" [[{original_note_name}]]"
            to_be_archived.append(new_todo)
    return formatted_todos, to_be_archived

def write_file(notename, content, directory=DN_DIR):
    """Write out file in daily note directory
    """
    filename = f"{directory}/{notename}.md"
    with open(filename, "w+") as f:
        f.write(content)
    print(f"Successfully wrote {len(content)} lines to {filename}")

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
    rendered_note = template.render(
        tasks=todos,
        DN_DIR=DN_FOLDER,
        yesterday_note_name=yester_note_name,
        tomorrow_note_name=tmrw_note_name)
    return rendered_note

def replace_open_with_moved_todos(filename):
    """Replace open [ ] with moved todo symbol [>]
    to differentiate between open and close todos
    """
    note = get_file_content(f"{filename}.md")
    modified_content = re.sub(r"\[\s\]", r"[>]", note)
    return modified_content

def get_open_todos(notename):
    """Get todos with the pattern [ ]
    """
    filename = f"{notename}.md"
    open_todos = find_pattern_in_file(filename, OPEN_TASK_PATTERN)
    # check if there are any backlinked todos:
    backlinked_todos = get_backlink_todos(filename)
    open_todos.extend(backlinked_todos)
    print(f"{len(open_todos)} open todos found in {filename}")
    return open_todos

def get_backlink_todos(notename):
    pattern = OPEN_TASK_PATTERN + f"\[\[({notename})\]\]"
    backlink_todos = find_pattern_in_files(DN_DIR, pattern)
    print(f"{len(backlink_todos)} backlinked todo(s) found for note {notename}")
    return backlink_todos

def write_to_archive_template(todos, notename=ARCHIVE_NOTE_NAME, template=ARCHIVE_TEMPLATE):
    filename = f"{ARCHIVE_NOTE_DIR}/{notename}.md"
    file_loader = FileSystemLoader(SCRIPT_DIR)
    env = Environment(loader=file_loader)
    template = env.get_template(template)
    rendered_note = template.render(
        tasks=todos)
    return rendered_note

def get_all_archived_todos(to_be_archived_todos, notename=ARCHIVE_NOTE_NAME):
    filename = f"{ARCHIVE_NOTE_DIR}/{notename}.md"
    # format these existing_todos:
    formatted_todos = [todo.raw_text for todo in get_open_todos(notename)]
    print(f"Found {len(formatted_todos)} todos in current archive..")
    print(f"Adding {len(to_be_archived_todos)} todos to archive..")
    return formatted_todos + to_be_archived_todos

def main():
    """Tommorrow note will not have the archived todos
    """
    today_note_name = get_note_name_for("today")
    today_todos = get_open_todos(today_note_name)
    shamed_todos, to_be_archived_todos = add_shame_or_archive(today_todos, today_note_name)
    # Add todos to tomorrow's note and write it out to a file
    # tmrw_note_name = get_note_name_for("tomorrow")
    # templatified_note = add_content_to_note_template(tmrw_note_name, shamed_todos)
    # write_file(tmrw_note_name, templatified_note)
    # # Make sure that we close out on pending tasks
    # modified_today_note = replace_open_with_moved_todos(today_note_name)
    # write_file(today_note_name, modified_today_note)

    # Now add stuff to archive
    all_archived_todos = get_all_archived_todos(to_be_archived_todos)
    archive_content = write_to_archive_template(all_archived_todos)
    write_file(ARCHIVE_NOTE_NAME, archive_content)
if __name__ == "__main__":
    main()
