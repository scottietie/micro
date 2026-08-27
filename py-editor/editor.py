#!/usr/bin/env python3
import curses
import os
import subprocess
import sys
import unicodedata

# 縮短 curses 解析 ESC 按鍵與控制碼的等待時間 (毫秒)
os.environ.setdefault("ESCDELAY", "25")

# Import the action handlers defined in actions.py
import actions

def str_width(s: str) -> int:
    """計算字串在終端機上的實際顯示寬度 (全形算 2，半形算 1)"""
    width = 0
    for ch in s:
        if unicodedata.east_asian_width(ch) in ("F", "W"):
            width += 2
        else:
            width += 1
    return width


def slice_by_width(s: str, max_w: int) -> tuple[str, int]:
    """按顯示寬度裁切字串，避免全形字截半，回傳 (裁切字串, 實際顯示寬度)"""
    curr_w = 0
    res = []
    for ch in s:
        w = str_width(ch)
        if curr_w + w > max_w:
            break
        res.append(ch)
        curr_w += w
    return "".join(res), curr_w


def pad_by_width(s: str, target_w: int) -> str:
    """依據螢幕顯示寬度補齊右側空格，確保總顯示寬度精確等於 target_w"""
    s_cut, curr_w = slice_by_width(s, target_w)
    rem = max(0, target_w - curr_w)
    return s_cut + (" " * rem)


# ==============================================================
# 1. 結構化按鍵映射字典
# ==============================================================

DEFAULT_KEYMAP = {
    # 檔案與系統操作
    "ctrl+s": "action_save",
    "ctrl+o": "action_open",
    "ctrl+q": "action_quit",
    # 編輯與剪貼簿
    "ctrl+a": "action_select_all",
    "ctrl+e": "action_delete_line",
    "ctrl+z": "action_undo",
    "ctrl+c": "action_copy",
    "ctrl+x": "action_cut",
    "ctrl+v": "action_paste",
    "bracketed_paste": "action_bracketed_paste",
    # 游標移動 (方向鍵 & 頁面導航)
    "left": "action_move_left",
    "right": "action_move_right",
    "up": "action_move_up",
    "down": "action_move_down",
    "home": "action_move_home",       # 【新增】跳至行頭
    "end": "action_move_end",         # 【新增】跳至行尾
    "ctrl+home": "action_goto_first_line",
    "ctrl+end": "action_goto_last_line",
    "shift+ctrl+home": "action_select_to_first_line",
    "shift+ctrl+end": "action_select_to_last_line",
    "page_up": "action_page_up",     # 【新增】上翻頁
    "page_down": "action_page_down", # 【新增】下翻頁
    # 文字選取 (Shift + 方向鍵)
    "shift+left": "action_select_left",
    "shift+right": "action_select_right",
    "shift+up": "action_select_up",
    "shift+down": "action_select_down",
    # 欄選取 (Alt + Shift + 方向鍵) — Column / Rectangular selection
    "alt+shift+left": "action_column_select_left",
    "alt+shift+right": "action_column_select_right",
    "alt+shift+up": "action_column_select_up",
    "alt+shift+down": "action_column_select_down",
    # 文字輸入控制
    "enter": "action_newline",
    "backspace": "action_backspace",
}


class Editor:
    GUTTER_WIDTH = 5

    def __init__(self, filename: str | None = None, keymap: dict | None = None):
        self.filename = filename
        self.lines: list[str] = []
        self.saved_lines: list[str] = []
        self.cursor_x = 0
        self.cursor_y = 0
        self.view_offset_y = 0
        self.should_quit = False
        self.selection_start: tuple[int, int] | None = None
        self.selection_end: tuple[int, int] | None = None
        self.clipboard = ""
        self.undo_stack: list[dict] = []
        self.column_selecting = False
        self.column_anchor: tuple[int, int] | None = None

        self.keymap = dict(DEFAULT_KEYMAP)
        if keymap:
            self.keymap.update(keymap)

        self.status_message = (
            " [Ctrl+Q Quit] | [Ctrl+S Save] | [Ctrl+O Open] | [Ctrl+A SelectAll]"
        )
        self._load_file()

    @property
    def is_dirty(self) -> bool:
        """動態比對當前內容與最後一次儲存的內容是否不一致"""
        return self.lines != self.saved_lines

    def _load_file(self) -> None:
        if self.filename and os.path.exists(self.filename):
            with open(self.filename, "r", encoding="utf-8") as f:
                self.lines = [line.rstrip("\n") for line in f.readlines()]
            if not self.lines:
                self.lines = [""]
            self.status_message = f" 已載入檔案: {self.filename}"
        else:
            if self.filename:
                self.status_message = f" 新檔案: {self.filename}"
            self.lines = [""]

        self.saved_lines = list(self.lines)
        self.undo_stack.clear()

    # ---------------- 系統剪貼簿 (xclip) 整合 ----------------

    def _set_system_clipboard(self, text: str) -> None:
        """寫入系統剪貼簿 (使用 xclip)，同時更新內部記憶體副本"""
        self.clipboard = text
        try:
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text.encode("utf-8"),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1.0,
            )
        except Exception:
            pass

    def _get_system_clipboard(self) -> str:
        """讀取系統剪貼簿 (使用 xclip)，若失敗則讀取內部副本"""
        try:
            out = subprocess.check_output(
                ["xclip", "-selection", "clipboard", "-o"],
                stderr=subprocess.DEVNULL,
                timeout=1.0,
            )
            return out.decode("utf-8")
        except Exception:
            return self.clipboard

    # ---------------- Undo 復原邏輯 ----------------

    def _save_snapshot(self) -> None:
        state = {
            "lines": list(self.lines),
            "cursor_x": self.cursor_x,
            "cursor_y": self.cursor_y,
        }
        self.undo_stack.append(state)
        if len(self.undo_stack) > 100:
            self.undo_stack.pop(0)

    def undo(self) -> None:
        if not self.undo_stack:
            self.status_message = " 已達最早狀態，無法復原！"
            return
        state = self.undo_stack.pop()
        self.lines = state["lines"]
        self.cursor_x = state["cursor_x"]
        self.cursor_y = state["cursor_y"]
        self._clear_selection()
        self.status_message = " 已復原動作 (Undo)"

    # ---------------- 選取與剪貼簿邏輯 ----------------

    def _clear_selection(self) -> None:
        self.selection_start = None
        self.selection_end = None
        self.column_selecting = False
        self.column_anchor = None

    def _get_selection_range(self) -> tuple[tuple[int, int], tuple[int, int]] | None:
        if self.selection_start is None:
            return None
        start = self.selection_start
        end = (
            self.selection_end
            if self.selection_end is not None
            else (self.cursor_y, self.cursor_x)
        )
        if start == end:
            return None
        return (start, end) if start < end else (end, start)

    def _get_selected_text(self) -> str:
        if self.column_selecting:
            return self._get_column_selected_text()
        sel = self._get_selection_range()
        if not sel:
            return ""
        (y1, x1), (y2, x2) = sel
        if y1 == y2:
            return self.lines[y1][x1:x2]

        result = [self.lines[y1][x1:]]
        for y in range(y1 + 1, y2):
            result.append(self.lines[y])
        result.append(self.lines[y2][:x2])
        return "\n".join(result)

    def _delete_selection(self) -> bool:
        if self.column_selecting:
            return self._delete_column_selection()
        sel = self._get_selection_range()
        if not sel:
            return False
        (y1, x1), (y2, x2) = sel
        if y1 == y2:
            line = self.lines[y1]
            self.lines[y1] = line[:x1] + line[x2:]
        else:
            first_part = self.lines[y1][:x1]
            last_part = self.lines[y2][x2:]
            self.lines[y1] = first_part + last_part
            del self.lines[y1 + 1 : y2 + 1]

        self.cursor_y = y1
        self.cursor_x = x1
        self._clear_selection()
        return True

    # ---------------- Column (Rectangular) Selection ----------------

    def _get_column_selection_rect(self):
        if not self.column_selecting or self.column_anchor is None:
            return None
        ay, ax = self.column_anchor
        cy, cx = self.cursor_y, self.cursor_x
        top = min(ay, cy)
        bottom = max(ay, cy)
        left = min(ax, cx)
        right = max(ax, cx)
        return (top, bottom, left, right)

    def _get_column_selected_text(self) -> str:
        rect = self._get_column_selection_rect()
        if rect is None:
            return ""
        top, bottom, left, right = rect
        lines = []
        for y in range(top, bottom + 1):
            if y < len(self.lines):
                line = self.lines[y]
                if left < len(line):
                    lines.append(line[left:right])
                else:
                    lines.append("")
            else:
                lines.append("")
        return "\n".join(lines)

    def _delete_column_selection(self) -> bool:
        rect = self._get_column_selection_rect()
        if rect is None:
            return False
        top, bottom, left, right = rect
        for y in range(top, bottom + 1):
            if y < len(self.lines):
                line = self.lines[y]
                if left < len(line):
                    self.lines[y] = line[:left] + line[right:]
        self.cursor_y = top
        self.cursor_x = left
        self._clear_selection()
        return True

    def _paste_text(self, text: str) -> None:
        """核心貼上邏輯：將完整字串批次寫入"""
        if not text:
            return
        self._save_snapshot()
        self._delete_selection()
        clip_lines = text.split("\n")
        curr_line = self.lines[self.cursor_y]
        left = curr_line[: self.cursor_x]
        right = curr_line[self.cursor_x :]

        if len(clip_lines) == 1:
            self.lines[self.cursor_y] = left + clip_lines[0] + right
            self.cursor_x += len(clip_lines[0])
        else:
            self.lines[self.cursor_y] = left + clip_lines[0]
            for i in range(1, len(clip_lines) - 1):
                self.lines.insert(self.cursor_y + i, clip_lines[i])
            self.lines.insert(
                self.cursor_y + len(clip_lines) - 1, clip_lines[-1] + right
            )
            self.cursor_y += len(clip_lines) - 1
            self.cursor_x = len(clip_lines[-1])

    # ---------------- 檔案操作邏輯 ----------------

    def open_file(self, stdscr) -> bool:
        if self.is_dirty:
            choice = self._prompt_choice(
                stdscr, " 有未儲存的變更！是否先儲存？ (y:儲存/n:放棄/c:取消): "
            )
            if choice == "y":
                if not self.save(stdscr):
                    return False
            elif choice == "c":
                self.status_message = " 取消開啟檔案！"
                return False

        target_file = self._prompt_input(stdscr, " 請輸入要開啟的檔案路徑: ")
        if not target_file:
            self.status_message = " 取消開啟檔案！"
            return False

        if os.path.exists(target_file):
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    self.lines = [line.rstrip("\n") for line in f.readlines()]
                if not self.lines:
                    self.lines = [""]

                self.filename = target_file
                self.cursor_x = 0
                self.cursor_y = 0
                self.view_offset_y = 0
                self._clear_selection()
                self.saved_lines = list(self.lines)
                self.undo_stack.clear()
                self.status_message = f" 已成功開啟檔案: {target_file}"
                return True
            except Exception as e:
                self.status_message = f" 開啟檔案失敗: {e}"
                return False
        else:
            self.status_message = f" 檔案不存在: {target_file}"
            return False

    def save(self, stdscr=None) -> bool:
        if not self.filename:
            if stdscr is None:
                self.filename = "untitled.txt"
            else:
                new_filename = self._prompt_input(stdscr, " 請輸入儲存檔名: ")
                if not new_filename:
                    self.status_message = " 取消儲存！"
                    return False
                self.filename = new_filename

        try:
            with open(self.filename, "w", encoding="utf-8") as f:
                f.write("\n".join(self.lines))
            self.saved_lines = list(self.lines)
            self.status_message = f" 已成功儲存至: {self.filename}"
            return True
        except Exception as e:
            self.status_message = f" 儲存失敗: {e}"
            return False

    # ---------------- 提示對話框邏輯 ----------------

    def _prompt_input(self, stdscr, prompt: str) -> str:
        input_buf = ""
        curses.curs_set(1)

        while True:
            max_y, max_x = stdscr.getmaxyx()
            target_width = max(0, max_x - 1)
            status = f"{prompt}{input_buf}"

            stdscr.attron(curses.color_pair(3))
            try:
                padded_status = pad_by_width(status, target_width)
                stdscr.addstr(max_y - 1, 0, padded_status)
            except curses.error:
                pass
            stdscr.attroff(curses.color_pair(3))

            cx = str_width(prompt) + str_width(input_buf)
            cx = min(cx, target_width - 1)

            stdscr.move(max_y - 1, max(0, cx))
            stdscr.refresh()

            key = stdscr.getch()
            if key in (10, 13, curses.KEY_ENTER):
                break
            elif key == 27:
                return ""
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                if input_buf:
                    input_buf = input_buf[:-1]
            elif 32 <= key <= 126 or key > 127:
                input_buf += chr(key)

        return input_buf.strip()

    def _prompt_choice(self, stdscr, prompt: str) -> str:
        max_y, max_x = stdscr.getmaxyx()
        target_width = max(0, max_x - 1)

        stdscr.attron(curses.color_pair(3))
        try:
            padded_prompt = pad_by_width(prompt, target_width)
            stdscr.addstr(max_y - 1, 0, padded_prompt)
        except curses.error:
            pass
        stdscr.attroff(curses.color_pair(3))
        stdscr.refresh()

        while True:
            key = stdscr.getch()
            if key in (ord("y"), ord("Y")):
                return "y"
            elif key in (ord("n"), ord("N")):
                return "n"
            elif key in (27, ord("c"), ord("C")):
                return "c"

    def run(self, stdscr) -> None:
        curses.curs_set(1)
        stdscr.keypad(True)
        while not self.should_quit:
            self._draw(stdscr)
            self._handle_event(stdscr)

    # ---------------- 繪製邏輯 ----------------

    def _draw(self, stdscr) -> None:
        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()
        screen_height = max_y - 1
        text_width = max(0, max_x - self.GUTTER_WIDTH)
        sel_range = self._get_selection_range()

        for i in range(screen_height):
            line_index = i + self.view_offset_y
            if line_index < len(self.lines):
                line = self.lines[line_index]
                gutter = f"{line_index + 1:>3} |"
                is_current_line = line_index == self.cursor_y

                # 1. 繪製行號
                if is_current_line:
                    stdscr.attron(curses.color_pair(1))
                else:
                    stdscr.attron(curses.color_pair(2))

                try:
                    stdscr.addstr(i, 0, gutter)
                except curses.error:
                    pass
                stdscr.attroff(curses.color_pair(1))
                stdscr.attroff(curses.color_pair(2))

                # 2. 繪製內文
                curr_col = 0
                for c, ch in enumerate(line):
                    ch_w = str_width(ch)
                    if curr_col + ch_w > text_width:
                        break

                    is_selected = False
                    if sel_range:
                        (y1, x1), (y2, x2) = sel_range
                        pos = (line_index, c)
                        if (y1, x1) <= pos < (y2, x2):
                            is_selected = True
                    elif self.column_selecting and self.column_anchor is not None:
                        ay, ax = self.column_anchor
                        cy, cx = self.cursor_y, self.cursor_x
                        top = min(ay, cy)
                        bottom = max(ay, cy)
                        left = min(ax, cx)
                        right = max(ax, cx)
                        if top <= line_index <= bottom and left <= c < right:
                            is_selected = True

                    if is_selected:
                        attr = curses.A_REVERSE
                    elif is_current_line:
                        attr = curses.color_pair(4)
                    else:
                        attr = curses.A_NORMAL

                    try:
                        stdscr.addstr(i, self.GUTTER_WIDTH + curr_col, ch, attr)
                    except curses.error:
                        pass

                    curr_col += ch_w

                # 3. 當前行右側填滿背景色
                if is_current_line:
                    rem_width = text_width - curr_col
                    if rem_width > 0:
                        try:
                            stdscr.addstr(
                                i,
                                self.GUTTER_WIDTH + curr_col,
                                " " * rem_width,
                                curses.color_pair(4),
                            )
                        except curses.error:
                            pass

        # 4. 繪製底部狀態欄
        file_info = self.filename if self.filename else "未命名"
        dirty_flag = " [*]" if self.is_dirty else ""
        status = (
            f" {self.status_message} | [{file_info}{dirty_flag}] "
            f"Line: {self.cursor_y + 1}/{len(self.lines)} | Col: {self.cursor_x + 1}"
        )
        target_width = max(0, max_x - 1)

        stdscr.attron(curses.color_pair(3))
        try:
            padded_status = pad_by_width(status, target_width)
            stdscr.addstr(max_y - 1, 0, padded_status)
        except curses.error:
            pass
        stdscr.attroff(curses.color_pair(3))

        # 5. 精確計算游標 X 座標
        curr_line = self.lines[self.cursor_y] if self.cursor_y < len(self.lines) else ""
        cursor_col = str_width(curr_line[: self.cursor_x])
        screen_y = self.cursor_y - self.view_offset_y
        screen_x = self.GUTTER_WIDTH + cursor_col
        stdscr.move(screen_y, min(screen_x, max_x - 1))
        stdscr.refresh()

    # ==============================================================================
    # 2. 游標與選取輔助動作
    # ============================================================================

    def _move_left(self):
        if self.cursor_x > 0:
            self.cursor_x -= 1
        elif self.cursor_y > 0:
            self.cursor_y -= 1
            self.cursor_x = len(self.lines[self.cursor_y])

    def _move_right(self):
        line_len = len(self.lines[self.cursor_y])
        if self.cursor_x < line_len:
            self.cursor_x += 1
        elif self.cursor_y + 1 < len(self.lines):
            self.cursor_y += 1
            self.cursor_x = 0

    def _move_up(self):
        if self.cursor_y > 0:
            self.cursor_y -= 1
            self._clamp_cursor_x()

    def _move_down(self):
        if self.cursor_y + 1 < len(self.lines):
            self.cursor_y += 1
            self._clamp_cursor_x()

    def _start_selection_if_needed(self):
        if self.column_selecting:
            self._clear_selection()
        if self.selection_start is None:
            self.selection_start = (self.cursor_y, self.cursor_x)
        self.selection_end = None

    # ==============================================================================
    # 4. 按鍵解析器與事件分發器
    # ============================================================================

    def _parse_key_event(self, stdscr, key: int) -> str | None:
        if key == 27:
            stdscr.nodelay(True)
            seq = []
            while True:
                ch = stdscr.getch()
                if ch == -1:
                    break
                seq.append(ch)
            stdscr.nodelay(False)

            seq_str = "".join(chr(c) for c in seq if 0 <= c <= 255)
            ansi_map = {
                # Shift + Arrow
                "[1;2A": "shift+up",    "[2A": "shift+up",
                "[1;2B": "shift+down",  "[2B": "shift+down",
                "[1;2C": "shift+right", "[2C": "shift+right",
                "[1;2D": "shift+left",  "[2D": "shift+left",
                # Alt + Arrow
                "[1;3A": "alt+up",
                "[1;3B": "alt+down",
                "[1;3C": "alt+right",
                "[1;3D": "alt+left",
                # Alt + Shift + Arrow
                "[1;4A": "alt+shift+up",
                "[1;4B": "alt+shift+down",
                "[1;4C": "alt+shift+right",
                "[1;4D": "alt+shift+left",
                # Page Up / Page Down
                "[5~": "page_up",
                "[6~": "page_down",
                # Home / End
                "[H": "home",  "[1~": "home",  "[7~": "home",  "OH": "home",
                "[F": "end",   "[4~": "end",   "[8~": "end",   "OF": "end",
                # Ctrl+Home / Ctrl+End (common sequences)
                "[1;5H": "ctrl+home",
                "[1;5F": "ctrl+end",
                # Shift+Ctrl+Home / Shift+Ctrl+End
                "[1;6H": "shift+ctrl+home",
                "[1;6F": "shift+ctrl+end",
                # Bracketed Paste Mode
                "[200~": "bracketed_paste",
            }
            return ansi_map.get(seq_str, "esc")

        if key in (10, 13, curses.KEY_ENTER):
            return "enter"
        if key in (curses.KEY_BACKSPACE, 127, 8):
            return "backspace"

        curses_key_map = {
            curses.KEY_LEFT: "left",
            curses.KEY_RIGHT: "right",
            curses.KEY_UP: "up",
            curses.KEY_DOWN: "down",
            curses.KEY_PPAGE: "page_up",
            curses.KEY_NPAGE: "page_down",
            curses.KEY_HOME: "home",
            curses.KEY_END: "end",
            curses.KEY_SLEFT: "shift+left",
            curses.KEY_SRIGHT: "shift+right",
            getattr(curses, "KEY_SUP", -1): "shift+up",
            getattr(curses, "KEY_SR", -1): "shift+up",
            getattr(curses, "KEY_SDOWN", -1): "shift+down",
            getattr(curses, "KEY_SF", -1): "shift+down",
        }
        if key in curses_key_map:
            return curses_key_map[key]

        if 1 <= key <= 26:
            char_name = chr(key + 96)
            return f"ctrl+{char_name}"

        return None

    def _handle_event(self, stdscr) -> None:
        key = stdscr.getch()
        combo_str = self._parse_key_event(stdscr, key)

        if combo_str in self.keymap:
            actions_list = self.keymap[combo_str]
            if isinstance(actions_list, str):
                actions_list = [actions_list]

            for action_name in actions_list:
                # Try to get a method on the editor first, then fall back to actions module
                handler = getattr(self, action_name, None)
                if handler is None:
                    handler = getattr(actions, action_name, None)

                if callable(handler):
                    # action_type_char expects the original key as an extra argument
                    if action_name == "action_type_char":
                        handler(self, stdscr, key)
                    else:
                        handler(self, stdscr)

        elif 32 <= key <= 126 or key > 127:
            # Direct character input (fallback)
            handler = getattr(actions, "action_type_char", None)
            if callable(handler):
                handler(self, stdscr, key)

        max_y, _ = stdscr.getmaxyx()
        screen_height = max_y - 1
        self._scroll(screen_height)

    def _scroll(self, screen_height: int) -> None:
        if self.cursor_y < self.view_offset_y:
            self.view_offset_y = self.cursor_y
        elif self.cursor_y >= self.view_offset_y + screen_height:
            self.view_offset_y = self.cursor_y - screen_height + 1

    def _clamp_cursor_x(self) -> None:
        line_len = len(self.lines[self.cursor_y])
        if self.cursor_x > line_len:
            self.cursor_x = line_len


def _init_curses(stdscr, editor: Editor) -> None:
    curses.raw()
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_YELLOW, -1)
    curses.init_pair(2, curses.COLOR_BLUE, -1)
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLACK)

    if curses.COLORS >= 256:
        curses.init_pair(4, -1, 236)
    else:
        curses.init_pair(4, -1, curses.COLOR_BLACK)

    # 啟用 Terminal Bracketed Paste Mode
    sys.stdout.write("\x1b[?2004h")
    sys.stdout.flush()

    try:
        editor.run(stdscr)
    finally:
        sys.stdout.write("\x1b[?2004l")
        sys.stdout.flush()


def main() -> None:
    filename = sys.argv[1] if len(sys.argv) > 1 else None
    editor = Editor(filename)
    curses.wrapper(lambda stdscr: _init_curses(stdscr, editor))


if __name__ == "__main__":
    main()
