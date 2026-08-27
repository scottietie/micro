# actions.py
# Action handler functions moved from editor.py.
# Each function receives the `editor` instance and the curses `stdscr` object.

import curses
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from editor import Editor


def action_save(editor: "Editor", stdscr):
    """Save the current file."""
    editor.save(stdscr)


def action_open(editor: "Editor", stdscr):
    """Open a file, prompting the user."""
    editor.open_file(stdscr)


def action_quit(editor: "Editor", stdscr):
    """Quit the editor, prompting to save if dirty."""
    if editor.is_dirty:
        choice = editor._prompt_choice(
            stdscr, " 有未儲存的變更！是否先儲存？ (y:儲存/n:放棄/c:取消): "
        )
        if choice == "y":
            if editor.save(stdscr):
                editor.should_quit = True
        elif choice == "n":
            editor.should_quit = True
    else:
        editor.should_quit = True


def action_undo(editor: "Editor", stdscr):
    """Undo the last operation."""
    editor.undo()


def action_copy(editor: "Editor", stdscr):
    """Copy selected text to the system clipboard."""
    text = editor._get_selected_text()
    if text:
        editor._set_system_clipboard(text)
        editor.status_message = " 已複製到系統剪貼簿！"


def action_cut(editor: "Editor", stdscr):
    """Cut selected text to the system clipboard."""
    text = editor._get_selected_text()
    if text:
        editor._save_snapshot()
        editor._set_system_clipboard(text)
        editor._delete_selection()
        editor.status_message = " 已剪下到系統剪貼簿！"


def action_paste(editor: "Editor", stdscr):
    """Paste text from the system clipboard."""
    clip_text = editor._get_system_clipboard()
    if clip_text:
        editor._paste_text(clip_text)
        editor.status_message = " 已貼上系統剪貼簿內容！"


def action_bracketed_paste(editor: "Editor", stdscr):
    """Handle bracketed paste mode."""
    stdscr.nodelay(True)
    byte_buf = bytearray()

    while True:
        key = stdscr.getch()
        if key == -1:
            curses.napms(1)
            key = stdscr.getch()
            if key == -1:
                break

        if key == 27:  # ESC
            seq = []
            while True:
                next_ch = stdscr.getch()
                if next_ch == -1:
                    break
                seq.append(next_ch)
            seq_str = "".join(chr(c) for c in seq if 0 <= c <= 255)
            if seq_str == "[201~":
                break
            else:
                byte_buf.append(27)
                byte_buf.extend(seq_str.encode("latin1"))
        elif key in (10, 13):
            byte_buf.extend(b"\n")
        elif 0 <= key <= 255:
            byte_buf.append(key)

    stdscr.nodelay(False)

    pasted_text = byte_buf.decode("utf-8", errors="ignore")
    if pasted_text:
        editor._paste_text(pasted_text)
        editor.status_message = " 已完成貼上！"


def action_select_all(editor: "Editor", stdscr):
    """Select the whole document."""
    editor.selection_start = (0, 0)
    editor.selection_end = (len(editor.lines) - 1, len(editor.lines[-1]))
    editor.status_message = " 已全選！"


def action_delete_line(editor: "Editor", stdscr):
    """Delete the line where the cursor resides."""
    editor._save_snapshot()
    editor._clear_selection()
    if len(editor.lines) > 1:
        editor.lines.pop(editor.cursor_y)
        if editor.cursor_y >= len(editor.lines):
            editor.cursor_y = len(editor.lines) - 1
    else:
        editor.lines[0] = ""
    editor._clamp_cursor_x()
    editor.status_message = " 已刪除當前行！"


def action_move_left(editor: "Editor", stdscr):
    editor._clear_selection()
    editor._move_left()


def action_move_right(editor: "Editor", stdscr):
    editor._clear_selection()
    editor._move_right()


def action_move_up(editor: "Editor", stdscr):
    editor._clear_selection()
    editor._move_up()


def action_move_down(editor: "Editor", stdscr):
    editor._clear_selection()
    editor._move_down()


def action_move_home(editor: "Editor", stdscr):
    """Jump to the beginning of the current line."""
    editor._clear_selection()
    editor.cursor_x = 0


def action_move_end(editor: "Editor", stdscr):
    """Jump to the end of the current line."""
    editor._clear_selection()
    editor.cursor_x = len(editor.lines[editor.cursor_y])

def action_goto_first_line(editor: "Editor", stdscr):
    """Ctrl+Home – Jump to the first line of the document."""
    editor._clear_selection()
    editor.cursor_y = 0
    editor.cursor_x = 0

def action_goto_last_line(editor: "Editor", stdscr):
    """Ctrl+End – Jump to the last line of the document."""
    editor._clear_selection()
    editor.cursor_y = len(editor.lines) - 1
    editor.cursor_x = len(editor.lines[editor.cursor_y])


def action_select_to_first_line(editor: "Editor", stdscr):
    """Shift+Ctrl+Home – Select from the current line up to the first line."""
    # Start a selection if one isn’t already active
    editor._start_selection_if_needed()
    # Move cursor to the very first line, column 0
    editor.cursor_y = 0
    editor.cursor_x = 0
    editor._clamp_cursor_x()


def action_select_to_last_line(editor: "Editor", stdscr):
    """Shift+Ctrl+End – Select from the current line down to the last line."""
    # Start a selection if one isn’t already active
    editor._start_selection_if_needed()
    # Move cursor to the last line, at the end of that line
    editor.cursor_y = len(editor.lines) - 1
    editor.cursor_x = len(editor.lines[editor.cursor_y])
    editor._clamp_cursor_x()


def action_page_up(editor: "Editor", stdscr):
    """Page up – stay in place if not enough lines above."""
    max_y, _ = stdscr.getmaxyx()
    screen_height = max(1, max_y - 1)

    if editor.cursor_y - screen_height < 0:
        editor.status_message = " 上方剩餘行數不足一頁，維持原位！"
        return

    editor._clear_selection()
    relative_y = max(0, min(screen_height - 1, editor.cursor_y - editor.view_offset_y))

    editor.cursor_y -= screen_height
    editor.view_offset_y = max(0, editor.cursor_y - relative_y)
    editor._clamp_cursor_x()


def action_page_down(editor: "Editor", stdscr):
    """Page down – stay in place if not enough lines below."""
    max_y, _ = stdscr.getmaxyx()
    screen_height = max(1, max_y - 1)

    if editor.cursor_y + screen_height >= len(editor.lines):
        editor.status_message = " 下方剩餘行數不足一頁，維持原位！"
        return

    editor._clear_selection()
    relative_y = max(0, min(screen_height - 1, editor.cursor_y - editor.view_offset_y))

    editor.cursor_y += screen_height
    editor.view_offset_y = max(0, editor.cursor_y - relative_y)
    editor._clamp_cursor_x()


def action_select_left(editor: "Editor", stdscr):
    editor._start_selection_if_needed()
    editor._move_left()


def action_select_right(editor: "Editor", stdscr):
    editor._start_selection_if_needed()
    editor._move_right()


def action_select_up(editor: "Editor", stdscr):
    editor._start_selection_if_needed()
    editor._move_up()


def action_select_down(editor: "Editor", stdscr):
    editor._start_selection_if_needed()
    editor._move_down()


def action_newline(editor: "Editor", stdscr):
    """Insert a newline at the cursor position."""
    editor._save_snapshot()
    editor._delete_selection()
    current = editor.lines[editor.cursor_y]
    left = current[: editor.cursor_x]
    right = current[editor.cursor_x :]
    editor.lines[editor.cursor_y] = left
    editor.lines.insert(editor.cursor_y + 1, right)
    editor.cursor_y += 1
    editor.cursor_x = 0


def action_column_select_left(editor: "Editor", stdscr):
    """Extend column (rectangular) selection to the left."""
    if not editor.column_selecting:
        editor._clear_selection()
        editor.column_anchor = (editor.cursor_y, editor.cursor_x)
        editor.column_selecting = True
    editor._move_left()


def action_column_select_right(editor: "Editor", stdscr):
    """Extend column (rectangular) selection to the right."""
    if not editor.column_selecting:
        editor._clear_selection()
        editor.column_anchor = (editor.cursor_y, editor.cursor_x)
        editor.column_selecting = True
    editor._move_right()


def action_column_select_up(editor: "Editor", stdscr):
    """Extend column (rectangular) selection upward."""
    if not editor.column_selecting:
        editor._clear_selection()
        editor.column_anchor = (editor.cursor_y, editor.cursor_x)
        editor.column_selecting = True
    editor._move_up()


def action_column_select_down(editor: "Editor", stdscr):
    """Extend column (rectangular) selection downward."""
    if not editor.column_selecting:
        editor._clear_selection()
        editor.column_anchor = (editor.cursor_y, editor.cursor_x)
        editor.column_selecting = True
    editor._move_down()


def action_backspace(editor: "Editor", stdscr):
    """Handle Backspace – delete selection or character."""
    editor._save_snapshot()
    if not editor._delete_selection():
        if editor.cursor_x > 0:
            line = editor.lines[editor.cursor_y]
            editor.lines[editor.cursor_y] = (
                line[: editor.cursor_x - 1] + line[editor.cursor_x :]
            )
            editor.cursor_x -= 1
        elif editor.cursor_y > 0:
            prev_line = editor.lines[editor.cursor_y - 1]
            cur_line = editor.lines.pop(editor.cursor_y)
            editor.cursor_y -= 1
            editor.cursor_x = len(prev_line)
            editor.lines[editor.cursor_y] = prev_line + cur_line


def action_type_char(editor: "Editor", stdscr, key: int):
    """Insert typed characters (including multi-byte sequences)."""
    editor._save_snapshot()
    editor._delete_selection()

    byte_buf = bytearray()
    if 0 <= key <= 255:
        byte_buf.append(key)

    stdscr.nodelay(True)
    while True:
        next_key = stdscr.getch()
        if next_key == -1:
            break
        if 0 <= next_key <= 255 and next_key not in (10, 13, 27):
            byte_buf.append(next_key)
        else:
            curses.ungetch(next_key)
            break
    stdscr.nodelay(False)

    text = byte_buf.decode("utf-8", errors="ignore")
    if text:
        line = editor.lines[editor.cursor_y]
        editor.lines[editor.cursor_y] = (
            line[: editor.cursor_x] + text + line[editor.cursor_x :]
        )
        editor.cursor_x += len(text)
