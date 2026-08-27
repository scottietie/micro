# py-editor ↔ micro 功能差距分析與移植記錄

此文件比較 `py-editor/`（一個純 Python curses 的迷你編輯器）與同目錄下的
**micro**（Go 版完整編輯器）目前的差異，並記錄把 micro 的熱鍵 / 常用功能移植過來的結果。

## 1. 兩者現況

| 面向 | micro (Go) | py-editor (Python) |
|------|-----------|---------------------|
| 語言 / 依賴 | Go + tcell | Python3 + curses（零外部依賴）|
| 多分頁 (tabs) | ✅ AddTab / 上個/下個分頁 | ❌ 僅單一 buffer |
| 分割視窗 (splits) | ✅ 垂直 / 水平 / 切換 | ❌ |
| 指令列 (command bar) | ✅ `>` 輸入 command | ❌ 只有簡易 prompt |
| 搜尋 / 取代 | ✅ 正則、FindNext/Prev、hlsearch | ✅ 搜尋 (Ctrl+F / Ctrl+N / F3/F4)；無正則/取代 |
| 跳行 (jump to line) | ✅ JumpLine | ✅ (Ctrl+G) |
| Undo / Redo | ✅ e redo | ✅ undo / redo (Ctrl+Y) |
| 外掛 (Lua plugins) | ✅ comment/linter/diff… | ❌ |
| 語法高亮 / 配色 | ✅ | ❌ |
| 多重游標 (multi-cursor) | ✅ | ❌ |
| 巨集 (macro) | ✅ | ❌ |
| 自動補全 (autocomplete) | ✅ | ❌ |
| 終端機 pane / ShellMode | ✅ | ❌ |
| 剪貼簿整合 | ✅ | ✅（xclip）|
| 方括號貼上 (bracketed paste) | ✅ | ✅ |
| 全形字元 / CJK 寬度 | ✅ | ✅ |
| 行號 / gutter | ✅ | ✅ |
| 欄選取 (rectangular) | ✅ | ✅ (Alt+Shift+箭頭) |
| 註解切換 | ✅ Ctrl+/ | ✅ (Ctrl+/) |
| 縮排 (indent / outdent) | ✅ Tab / Shift+Tab | ✅ (Tab / Shift+Tab) |
| 單字移動 / 刪除 | ✅ WordLeft/Right… | △ action 存在但未綁預設熱鍵（對齊 micro 後移除） |
| 移動/複製整行 | ✅ | △ 複製/剪下行已綁 (Ctrl+C/X 無選取時)；MoveLinesUp/Down action 存在未綁 |

## 2. micro 有、py-editor 沒有的「可移植」痛點（依優先度）

以下功能不需要完整架構（分頁 / 外掛 / 語法高亮）即可穩固移植。
標記為**歷程記錄**：✅ = 已移植並綁定；⛔ = 移植後因對齊 micro 預設而移除綁定（action 保留在 actions.py）。

1. **Redo（Ctrl+Y）** — ✅ 已實作並綁定。
2. **搜尋（Ctrl+F）** — ✅ 已實作 (Ctrl+F/N、F3/F4)；`Ctrl+P` 非 fork 預設故未綁，僅有 F4 為 FindPrevious。
3. **跳行（Ctrl+G）** — ✅ 已實作並綁定。
4. **Delete 前向刪除** — ✅ 已實作並綁定。
5. **複製/剪下行（無選取時）Ctrl+C / Ctrl+X** — ✅ 已實作。
6. **複製整行 / Duplicate（Ctrl+D）** — ⛔ 非 micro 預設，Ctrl+D 已移除綁定（action 保留）。
7. **註解切換（Ctrl+/）** — ✅ 已實作並綁定。
8. **縮排 / 縮排移除（Tab / Shift+Tab）** — ✅ 已實作並綁定。
9. **單字移動（Ctrl+←/→）與刪除單字（Ctrl+W / Alt+D）** — ⛔ 非 micro 預設，未綁（action 保留）。
10. **整行上/下移（Alt+↑/↓）** — ⛔ 非 micro 預設，未綁（action 保留）。
11. **Home = StartOfTextToggle（智慧行首）** — ✅ 已實作並綁定。
12. **Escape 清除選取 / 狀態列** — ✅ 已實作並綁定。
13. **F 鍵快速鍵** — ✅ F3/F4（FindNext/Previous）；F2/F7 非預設已移除。

## 3. 未移植（需較大架構）與原因

- **分頁 / 分割視窗、多重游標、巨集、自動補全、外掛、語法高亮、ShellPane**：
  這些是 micro 的核心架構（View/Split/Pane、Buffer、Lua VM、tcell），
  移植成本極高且會大幅超出「迷你編輯器」的定位，因此暫時保留為未來工作。

## 4. 移植結果記錄

py-editor 的 `DEFAULT_KEYMAP` 現與 micro 的 **Linux 預設
（`internal/action/defaults_other.go` 的 `bufdefaults`，啟用中的綁定）** 對齊。

### 移植的 micro Linux 預設熱鍵

| 快速鍵 | micro | py-editor（移植後） |
|--------|-------|--------------------|
| Ctrl+F | Find | action_find ✅ |
| Ctrl+N / F3 | FindNext | action_find_next ✅ |
| F4 | FindPrevious | action_find_previous ✅ |
| Ctrl+Y | Redo | action_redo ✅ |
| Ctrl+G | JumpLine | action_jump_line ✅ |
| Ctrl+/ | lua:comment.comment | action_toggle_comment ✅ |
| Tab / Shift+Tab | Indent / Outdent | action_indent / action_outdent ✅ |
| Delete | Delete | action_delete ✅ |
| Home / End | StartOfTextToggle / EndOfLine | action_move_home / end ✅ |
| Shift+Home / Shift+End | SelectToStartOfText / SelectToEndOfLine | ✅ |
| Ctrl+L / Ctrl+J | SelectRight / SelectLeft (fork 客製) | ✅ |
| Ctrl+C / Ctrl+X | Copy\|CopyLine / Cut\|CutLine | ✅ |
| Esc | Deselect / ClearInfo | action_escape ✅ |

> 註：`Ctrl+E`(DeleteLine)、`Ctrl+G`(JumpLine)、`Ctrl+N`(FindNext)、
> `Ctrl+L/J`(Select)、`Ctrl+B`(NextTab) 是**此 repo 在 defaults_other.go 中的
> 客製化綁定**，非原廠 micro 預設（原廠 micro 的 Ctrl+E 是 CommandMode）。

### 誤植後已移除的「非 micro 預設」熱鍵（修正）

以下熱鍵 micro **有**對應 action 但預設**未綁定**（在 defaults_other.go 中註解或
根本沒有），第一版誤當成 micro 預設移植，現已從 `DEFAULT_KEYMAP` 移除：

- Ctrl+D（Duplicate）— 註解
- Ctrl+W（DeleteWordLeft）— 註解
- Ctrl+←/→、Shift+Ctrl+←/→（Word / SelectWord）— 註解
- Alt+B / Alt+F（WordLeft/Right，Emacs 風格）— 註解
- Alt+D（DeleteWordRight）— 無此綁定
- Alt+↑/↓（MoveLinesUp/Down）— 註解
- F2 / F7（Save / Find）— 註解

> 這些 action 仍有對應函式保留在 `actions.py`（是 micro 的合法 action），只是
> 不再綁定預設熱鍵；需要時可在 `DEFAULT_KEYMAP` 自行重綁。

### 因 py-editor 架構未移植（micro 有分頁/窗格，py-editor 無）

Ctrl+T(AddTab)、Ctrl+B(NextTab)、Alt+, / Alt+.(分頁切換)、Ctrl+PageUp/PageDown
(分頁)、Insert(ToggleOverwriteMode)、滑鼠綁定——未移植。

### 未移植（需較大架構）

多分頁、分割窗格、指令列、語法高亮、多重游標、巨集、自動補全、外掛、ShellPane。
