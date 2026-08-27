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
    """Copy selected text to the system clipboard. 無選取時複製整行 (CopyLine)。"""
    text = editor._get_selected_text()
    if text:
        editor._set_system_clipboard(text)
        editor.status_message = " 已複製到系統剪貼簿！"
    else:
        # CopyLine fallback (micro 行為)
        editor._set_system_clipboard(editor.lines[editor.cursor_y])
        editor.status_message = " 已複製整行到系統剪貼簿！"


def action_cut(editor: "Editor", stdscr):
    """Cut selected text to the system clipboard. 無選取時剪下整行 (CutLine)。"""
    text = editor._get_selected_text()
    if text:
        editor._save_snapshot()
        editor._set_system_clipboard(text)
        editor._delete_selection()
        editor.status_message = " 已剪下到系統剪貼簿！"
    else:
        # CutLine fallback (micro 行為)
        editor._save_snapshot()
        editor._set_system_clipboard(editor.lines[editor.cursor_y])
        del editor.lines[editor.cursor_y]
        if not editor.lines:
            editor.lines = [""]
        if editor.cursor_y >= len(editor.lines):
            editor.cursor_y = len(editor.lines) - 1
        editor._clamp_cursor_x()
        editor.status_message = " 已剪下整行到系統剪貼簿！"


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
    """StartOfTextToggle – 智慧行首：
    若游標已在非空白首字處，跳到行首；否則跳到第一個非空白字元。"""
    editor._clear_selection()
    line = editor.lines[editor.cursor_y]
    first_nonspace = len(line) - len(line.lstrip())
    if editor.cursor_x == 0 or (editor.cursor_x > first_nonspace and editor.home_state):
        editor.cursor_x = 0
        editor.home_state = 0
    else:
        editor.cursor_x = first_nonspace
        editor.home_state = 1


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


# ==============================================================================
# micro 移植新增動作
# ==============================================================================

def action_redo(editor: "Editor", stdscr):
    """Ctrl+Y – 重做上次回復的動作。"""
    editor.redo()


def action_find(editor: "Editor", stdscr):
    """Ctrl+F – 輸入關鍵字搜尋並跳至第一個符合位置。"""
    editor._clear_selection()
    initial = editor._get_selected_text()
    query = editor._prompt_input(stdscr, f" 搜尋 (目前: {editor.find_query or '無'}): ")
    query = query.strip()
    if not query:
        editor.status_message = " 已取消搜尋！"
        return
    editor.find_query = query
    editor.find_direction = 1
    if editor.search_for(query, 1):
        editor.status_message = f" 找到: {query}"
    else:
        editor.status_message = f" 找不到: {query}"


def action_find_next(editor: "Editor", stdscr):
    """Ctrl+N / F3 – 尋找下一個符合。"""
    editor._clear_selection()
    if not editor.find_query:
        editor.status_message = " 尚未設定搜尋關鍵字，請先按 Ctrl+F！"
        return
    editor.find_direction = 1
    if editor.search_for(editor.find_query, 1):
        editor.status_message = f" 下一個: {editor.find_query}"
    else:
        editor.status_message = f" 找不到下一個: {editor.find_query}"


def action_find_previous(editor: "Editor", stdscr):
    """Ctrl+P / F4 – 尋找上一個符合。"""
    editor._clear_selection()
    if not editor.find_query:
        editor.status_message = " 尚未設定搜尋關鍵字，請先按 Ctrl+F！"
        return
    editor.find_direction = -1
    if editor.search_for(editor.find_query, -1):
        editor.status_message = f" 上一個: {editor.find_query}"
    else:
        editor.status_message = f" 找不到上一個: {editor.find_query}"


def action_jump_line(editor: "Editor", stdscr):
    """Ctrl+G – 跳到指定行號。"""
    editor._clear_selection()
    resp = editor._prompt_input(stdscr, f" 跳到行號 (共 {len(editor.lines)} 行): ")
    try:
        n = int(resp.strip())
    except (ValueError, TypeError):
        editor.status_message = " 輸入無效的行號！"
        return
    if n < 1:
        n = 1
    if n > len(editor.lines):
        n = len(editor.lines)
    editor.cursor_y = n - 1
    editor._clamp_cursor_x()
    editor.status_message = f" 已跳到第 {n} 行"


def action_duplicate(editor: "Editor", stdscr):
    """Ctrl+D – 複製當前行 (DuplicateLine)。"""
    editor._save_snapshot()
    editor._clear_selection()
    editor.lines.insert(editor.cursor_y, editor.lines[editor.cursor_y])
    editor.status_message = " 已複製當前行！"


def action_delete(editor: "Editor", stdscr):
    """Delete – 前向刪除字元。有選取時刪除選取範圍。"""
    editor._save_snapshot()
    if editor._delete_selection():
        editor.status_message = " 已刪除選取內容！"
        return
    line = editor.lines[editor.cursor_y]
    if editor.cursor_x < len(line):
        editor.lines[editor.cursor_y] = line[: editor.cursor_x] + line[editor.cursor_x + 1 :]
    elif editor.cursor_y + 1 < len(editor.lines):
        nxt = editor.lines.pop(editor.cursor_y + 1)
        editor.lines[editor.cursor_y] = line + nxt


def _current_selection_lines(editor: "Editor"):
    """回傳目前選取範圍所涵蓋的所有行索引 (含欄/列選取)。"""
    if editor.column_selecting and editor.column_anchor is not None:
        top, bottom, _, _ = editor._get_column_selection_rect()
        return list(range(top, bottom + 1))
    sel = editor._get_selection_range()
    if not sel:
        return [editor.cursor_y]
    (y1, _), (y2, _) = sel
    return list(range(y1, y2 + 1))


def action_toggle_comment(editor: "Editor", stdscr):
    """Ctrl+/ – 對選取範圍或當前行切換註解 (依副檔名判斷)。"""
    prefix = editor._comment_prefix()
    if prefix is None:
        editor.status_message = " 無法判斷此檔案的註解符號！"
        return
    lines_idx = _current_selection_lines(editor)
    editor._save_snapshot()
    # 檢查是否所有行都已註解
    all_commented = all(editor.lines[i].lstrip().startswith(prefix.strip().split()[0])
                        for i in lines_idx)
    for i in lines_idx:
        line = editor.lines[i]
        if all_commented:
            # 移除最前方註解符號
            stripped = line.lstrip()
            comment = prefix.strip().split()[0]
            if stripped.startswith(comment):
                indent = line[: len(line) - len(stripped)]
                editor.lines[i] = indent + stripped[len(comment):].lstrip()
        else:
            editor.lines[i] = prefix + line
    editor._clamp_cursor_x()
    editor.status_message = " 已註解 / 取消註解！"


def action_indent(editor: "Editor", stdscr):
    """Tab – 對選取範圍或當前行縮排 4 個空格。"""
    lines_idx = _current_selection_lines(editor)
    editor._save_snapshot()
    for i in lines_idx:
        editor.lines[i] = "    " + editor.lines[i]
    if editor.cursor_y in lines_idx:
        editor.cursor_x += 4
    editor.status_message = " 已縮排！"


def action_outdent(editor: "Editor", stdscr):
    """Shift+Tab – 對選取範圍或當前行取消縮排。"""
    lines_idx = _current_selection_lines(editor)
    editor._save_snapshot()
    shifted = 0
    for i in lines_idx:
        before = len(editor.lines[i])
        editor.lines[i] = editor.lines[i][4:] if editor.lines[i].startswith("    ") else editor.lines[i]
        if i == editor.cursor_y:
            shifted = before - len(editor.lines[i])
    editor.cursor_x = max(0, editor.cursor_x - shifted)
    editor.status_message = " 已取消縮排！"


def action_word_left(editor: "Editor", stdscr):
    """Ctrl+← / Alt+B – 向左移動一個單字。"""
    editor._clear_selection()
    line = editor.lines[editor.cursor_y]
    editor.cursor_x = editor._word_left_pos(editor.cursor_x, line)


def action_word_right(editor: "Editor", stdscr):
    """Ctrl+→ / Alt+F – 向右移動一個單字。"""
    editor._clear_selection()
    line = editor.lines[editor.cursor_y]
    editor.cursor_x = editor._word_right_pos(editor.cursor_x, line)


def action_select_word_left(editor: "Editor", stdscr):
    """Shift+Ctrl+← – 向左選取單字。"""
    editor._start_selection_if_needed()
    line = editor.lines[editor.cursor_y]
    editor.cursor_x = editor._word_left_pos(editor.cursor_x, line)


def action_select_word_right(editor: "Editor", stdscr):
    """Shift+Ctrl+→ – 向右選取單字。"""
    editor._start_selection_if_needed()
    line = editor.lines[editor.cursor_y]
    editor.cursor_x = editor._word_right_pos(editor.cursor_x, line)


def action_delete_word_left(editor: "Editor", stdscr):
    """Ctrl+W – 刪除游標左側的單字。"""
    editor._save_snapshot()
    editor._delete_selection()
    line = editor.lines[editor.cursor_y]
    new_x = editor._word_left_pos(editor.cursor_x, line)
    editor.lines[editor.cursor_y] = line[:new_x] + line[editor.cursor_x:]
    editor.cursor_x = new_x


def action_delete_word_right(editor: "Editor", stdscr):
    """Alt+D – 刪除游標右側的單字。"""
    editor._save_snapshot()
    editor._delete_selection()
    line = editor.lines[editor.cursor_y]
    new_x = editor._word_right_pos(editor.cursor_x, line)
    editor.lines[editor.cursor_y] = line[: editor.cursor_x] + line[new_x:]


def action_move_lines_up(editor: "Editor", stdscr):
    """Alt+↑ – 將當前行（或選取行）上移。"""
    lines_idx = _current_selection_lines(editor)
    if not lines_idx or lines_idx[0] == 0:
        editor.status_message = " 已是最上方，無法上移！"
        return
    editor._save_snapshot()
    editor._clear_selection()
    target = lines_idx[0] - 1
    for i in lines_idx:
        editor.lines[target], editor.lines[i] = editor.lines[i], editor.lines[target]
        target += 1
    editor.cursor_y = lines_idx[0] - 1
    editor.status_message = " 已上移一行！"


def action_move_lines_down(editor: "Editor", stdscr):
    """Alt+↓ – 將當前行（或選取行）下移。"""
    lines_idx = _current_selection_lines(editor)
    if not lines_idx or lines_idx[-1] == len(editor.lines) - 1:
        editor.status_message = " 已是最下方，無法下移！"
        return
    editor._save_snapshot()
    editor._clear_selection()
    target = lines_idx[-1] + 1
    for i in reversed(lines_idx):
        editor.lines[target], editor.lines[i] = editor.lines[i], editor.lines[target]
        target -= 1
    editor.cursor_y = lines_idx[-1] + 1
    editor.status_message = " 已下移一行！"


def action_escape(editor: "Editor", stdscr):
    """Esc – 清除選取與狀態訊息。"""
    editor._clear_selection()
    editor.status_message = ""


def action_select_page_up(editor: "Editor", stdscr):
    """Shift+PageUp – 向上選取一頁。"""
    editor._start_selection_if_needed()
    max_y, _ = stdscr.getmaxyx()
    screen_height = max(1, max_y - 1)
    editor.cursor_y = max(0, editor.cursor_y - screen_height)
    editor._clamp_cursor_x()


def action_select_page_down(editor: "Editor", stdscr):
    """Shift+PageDown – 向下選取一頁。"""
    editor._start_selection_if_needed()
    max_y, _ = stdscr.getmaxyx()
    screen_height = max(1, max_y - 1)
    editor.cursor_y = min(len(editor.lines) - 1, editor.cursor_y + screen_height)
    editor._clamp_cursor_x()


def action_select_to_line_start(editor: "Editor", stdscr):
    """Shift+Home (SelectToStartOfTextToggle) – 選取到行首 / 首個非空白字元。"""
    editor._start_selection_if_needed()
    line = editor.lines[editor.cursor_y]
    first_nonspace = len(line) - len(line.lstrip())
    # 游標若已非空白首字則先跳行首；否則跳至第一個非空白字元
    if editor.cursor_x <= first_nonspace:
        editor.cursor_x = 0
    else:
        editor.cursor_x = first_nonspace


def action_select_to_line_end(editor: "Editor", stdscr):
    """Shift+End (SelectToEndOfLine) – 選取到行尾。"""
    editor._start_selection_if_needed()
    editor.cursor_x = len(editor.lines[editor.cursor_y])
