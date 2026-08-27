# Terminal Text Editor

A lightweight, fast, and feature‑rich terminal‑based text editor written in Python.  
It provides modern editing capabilities such as undo/redo, clipboard integration, bracketed paste handling, and full Unicode width support (including double‑width CJK characters).

![Demo Screenshot](https://raw.githubusercontent.com/yourusername/terminal-editor/main/screenshot.png)

## ✨ Features

- **Unicode‑aware rendering** – correct column width for full‑width characters.
- **Bracketed paste mode** – paste large blocks of text without breaking the editor state.
- **System clipboard support** – copy/cut/paste via `xclip` (fallback to internal buffer).
- **Undo stack** – up to 100 history steps.
- **Multiple selection** – shift + arrows to select text.
- **Line numbers & gutter** – always visible.
- **Configurable keymap** – easy to extend or rebind.
- **File operations** – open, save, and prompt for unsaved changes.
- **Page navigation** – page up/down, home/end.
- **Cross‑platform** – runs on any terminal with Python 3.8+ and `curses`.

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/terminal-editor.git
cd terminal-editor

# (Optional) Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies (only xclip is required on Linux)
# On macOS you can replace xclip with pbcopy/pbpaste in the source.
sudo apt-get install xclip   # Debian/Ubuntu
# brew install xclip         # macOS via Homebrew
```

The editor has **no external Python dependencies** besides the standard library.

## 🚀 Usage

```bash
python3 editor.py [optional_file.txt]
```

- If a filename is supplied, the editor will attempt to load it.
- Without a filename, a new untitled buffer is opened.

## ⌨️ Default Key Bindings

| Key Combination | Action |
|-----------------|--------|
| **Ctrl+S** | Save |
| **Ctrl+O** | Open |
| **Ctrl+Q** | Quit (prompts if unsaved changes) |
| **Ctrl+Z** | Undo |
| **Ctrl+A** | Select all |
| **Ctrl+E** | Delete current line |
| **Ctrl+C** | Copy selection to system clipboard |
| **Ctrl+X** | Cut selection to system clipboard |
| **Ctrl+V** | Paste from system clipboard |
| **Shift+←/→/↑/↓** | Extend selection |
| **← / → / ↑ / ↓** | Move cursor |
| **Home / End** | Jump to line start / end |
| **Page Up / Page Down** | Scroll a page |
| **Enter** | Insert newline |
| **Backspace** | Delete character / merge lines |
| **Bracketed Paste** (automatically detected) | Paste large blocks safely |

All key bindings are defined in `editor.py` under `DEFAULT_KEYMAP`. Feel free to modify or extend them.

## 🛠️ Extending the Editor

The code is split into two clear modules:

- `editor.py` – core editor logic, UI rendering, and key parsing.
- `actions.py` – individual action handlers (save, open, copy, etc.).

## ⌨️ micro-Compatible Key Bindings

Hotkeys are aligned with micro's **Linux defaults**
(`internal/action/defaults_other.go`). Bindings present in both editors behave
identically (save/open/quit/undo/redo/copy/cut/paste, movement, selection,
page nav). The following micro Linux-default hotkeys were ported into py-editor:

| Key | Action |
|-----|--------|
| **Ctrl+F** | Find |
| **Ctrl+N / F3** | Find next match |
| **F4** | Find previous match |
| **Ctrl+G** | Jump to line |
| **Ctrl+Y** | Redo |
| **Ctrl+/** | Toggle comment (per extension) |
| **Tab / Shift+Tab** | Indent / Outdent selection or line |
| **Delete** | Forward-delete character |
| **Home** | Smart start-of-text (toggle) |
| **End** | End of line |
| **Shift+Home / Shift+End** | Select to line start / end |
| **Ctrl+L / Ctrl+J** | Select right / left (fork default) |
| **Ctrl+C / Ctrl+X** | Copy / cut whole line when no selection |
| **Esc** | Clear selection & status |

> 註：`Ctrl+E`(刪行), `Ctrl+G`(跳行), `Ctrl+N`(下一個), `Ctrl+L/J`(選取),
> `Ctrl+B`(分頁) 是此 repo 在 `defaults_other.go` 中的客製化綁定，非原廠　micro
> 預設；其中分頁相關（`Ctrl+E` 以外的 `Ctrl+B`、`Ctrl+T`、`Alt+,`/`Alt+.`、
> `Ctrl+PageUp/PageDown`）因 py-editor 無分頁架構而未移植。
>
> 未移植（需 micro 較大架構）：多分頁、分割窗格、指令列、語法高亮、外掛、
> 巨集、多重游標、自動補全、ShellPane。完整對照見 `GAP_ANALYSIS.md`。

## 🛠️ Extending the Editor

To add a new command:

1. Implement a function in `actions.py` (or as a method on `Editor`).
2. Add the function name to `DEFAULT_KEYMAP` with the desired key combo.
3. Optionally, expose a command‑line flag to toggle the new feature.

## 📜 License

This project is released under the MIT License. See `LICENSE` for details.

