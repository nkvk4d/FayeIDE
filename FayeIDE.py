import enum
from typing import Callable
from PySide6.QtWidgets import (QApplication, QMainWindow, QPlainTextEdit, QDockWidget,
                                 QMenuBar, QMenu, QFileDialog, QMessageBox, QVBoxLayout,
                                 QWidget, QLabel, QPushButton, QHBoxLayout, QLineEdit,
                                 QDialog, QStatusBar, QTabWidget, QCompleter, QListWidget,
                                 QTreeView, QFileSystemModel, QCheckBox)
from PySide6.QtCore import Qt, QSize, QStringListModel, QProcess, QDir
from PySide6.QtGui import QTextCharFormat, QSyntaxHighlighter, QColor, QFont, QTextCursor, QPainter, QTextDocument
import sys
import subprocess
import re
import os
import logging
from datetime import datetime
import jedi

class LogManager:
    def __init__(self):
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        log_file = f'logs/faye_ide_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
        self.logger = logging.getLogger('FayeIDE')
        self.logger.setLevel(logging.DEBUG)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def log(self, level: str, message: str):
        if level == 'debug':
            self.logger.debug(message)
        elif level == 'info':
            self.logger.info(message)
        elif level == 'warning':
            self.logger.warning(message)
        elif level == 'error':
            self.logger.error(message)
        elif level == 'critical':
            self.logger.critical(message)

log_manager = LogManager()

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        formats = {
            'keyword': self.create_format("#569CD6", bold=True),
            'class': self.create_format("#4EC9B0", bold=True),
            'function': self.create_format("#DCDCAA"),
            'string': self.create_format("#CE9178"),
            'comment': self.create_format("#6A9955", italic=True),
            'numbers': self.create_format("#B5CEA8"),
            'operators': self.create_format("#D4D4D4"),
            'braces': self.create_format("#D4D4D4"),
            'decorators': self.create_format("#569CD6"),
            'constants': self.create_format("#4FC1FF"),
            'builtins': self.create_format("#4EC9B0")
        }

        keywords = [
            'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
            'def', 'del', 'elif', 'else', 'except', 'False', 'finally', 'for',
            'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'None',
            'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'True', 'try',
            'while', 'with', 'yield'
        ]
        self.add_rules(keywords, formats['keyword'])

        builtins = [
            'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes',
            'chr', 'classmethod', 'compile', 'complex', 'delattr', 'dict', 'dir',
            'divmod', 'enumerate', 'eval', 'exec', 'filter', 'float', 'format',
            'frozenset', 'getattr', 'globals', 'hasattr', 'hash', 'help', 'hex',
            'id', 'input', 'int', 'isinstance', 'issubclass', 'iter', 'len',
            'list', 'locals', 'map', 'max', 'memoryview', 'min', 'next', 'object',
            'oct', 'open', 'ord', 'pow', 'print', 'property', 'range', 'repr',
            'reversed', 'round', 'set', 'setattr', 'slice', 'sorted', 'staticmethod',
            'str', 'sum', 'super', 'tuple', 'type', 'vars', 'zip'
        ]
        self.add_rules(builtins, formats['builtins'])

        operators = [
            '=', '==', '!=', '<', '<=', '>', '>=', r'\+', '-', r'\*', '/',
            '//', r'\%', r'\*\*', r'\+=', '-=', r'\*=', '/=', r'\%=', r'\^',
            r'\|', r'\&', r'\~', '>>', '<<'
        ]
        self.add_rules(operators, formats['operators'])

        braces = [r'\{', r'\}', r'\(', r'\)', r'\[', r'\]', ',', ':', ';']
        self.add_rules(braces, formats['braces'])

        self.highlighting_rules.append(
            (re.compile(r'\b[0-9]+\b'), formats['numbers'])
        )

        self.highlighting_rules.append(
            (re.compile(r'@\w+'), formats['decorators'])
        )

        self.highlighting_rules.extend([
            (re.compile(r'""".*?"""', re.DOTALL), formats['string']),
            (re.compile(r"'''.*?'''", re.DOTALL), formats['string']),
            (re.compile(r'"[^"\\]*(\\.[^"\\]*)*"'), formats['string']),
            (re.compile(r"'[^'\\]*(\\.[^'\\]*)*'"), formats['string'])
        ])

        self.highlighting_rules.append(
            (re.compile(r'#.*'), formats['comment'])
        )

        self.comment_start = re.compile(r'"""(?!.*""")')
        self.comment_end = re.compile(r'.*?"""')
        self.comment_format = formats['comment']

    def create_format(self, color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
        text_format = QTextCharFormat()
        text_format.setForeground(QColor(color))
        if bold:
            text_format.setFontWeight(QFont.Weight.Bold)
        if italic:
            text_format.setFontItalic(True)
        return text_format

    def add_rules(self, words: list[str], format):
        for word in words:
            pattern = f"\\b{word}\\b"
            self.highlighting_rules.append((re.compile(pattern), format))

    def highlightBlock(self, text):
        self.setFormat(0, len(text), QTextCharFormat())

        for pattern, format in self.highlighting_rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), format)

        self.setCurrentBlockState(0)
        if self.previousBlockState() == 1:
            end_match = self.comment_end.match(text)
            if end_match:
                comment_length = end_match.end()
                self.setFormat(0, comment_length, self.comment_format)
                self.setCurrentBlockState(0)
            else:
                self.setFormat(0, len(text), self.comment_format)
                self.setCurrentBlockState(1)
        else:
            start_match = self.comment_start.match(text)
            if start_match:
                self.setFormat(start_match.start(), len(text), self.comment_format)
                self.setCurrentBlockState(1)

class FindDialog(QDialog):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Find and replacement")
        self.last_search = ""
        self.case_sensitive = False
        self.whole_words = False
        self.search_backward = False
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        find_layout = QHBoxLayout()
        find_label = QLabel("Find:")
        self.find_input = QLineEdit()
        self.find_input.textChanged.connect(self.find_text_changed)
        find_layout.addWidget(find_label)
        find_layout.addWidget(self.find_input)
        layout.addLayout(find_layout)

        replace_layout = QHBoxLayout()
        replace_label = QLabel("Replace with:")
        self.replace_input = QLineEdit()
        replace_layout.addWidget(replace_label)
        replace_layout.addWidget(self.replace_input)
        layout.addLayout(replace_layout)

        options_layout = QHBoxLayout()
        
        self.case_check = QCheckBox("Match case")
        self.case_check.setChecked(self.case_sensitive)
        self.case_check.stateChanged.connect(self.update_options)
        
        self.whole_check = QCheckBox("Word entirely")
        self.whole_check.setChecked(self.whole_words)
        self.whole_check.stateChanged.connect(self.update_options)
        
        self.backward_check = QCheckBox("Find back")
        self.backward_check.setChecked(self.search_backward)
        self.backward_check.stateChanged.connect(self.update_options)
        
        options_layout.addWidget(self.case_check)
        options_layout.addWidget(self.whole_check)
        options_layout.addWidget(self.backward_check)
        layout.addLayout(options_layout)

        button_layout = QHBoxLayout()
        
        find_next_button = QPushButton("Find further")
        find_prev_button = QPushButton("Find previously")
        replace_button = QPushButton("Replace")
        replace_all_button = QPushButton("Replace all")
        close_button = QPushButton("Close")

        find_next_button.clicked.connect(lambda: self.find_text(forward=True))
        find_prev_button.clicked.connect(lambda: self.find_text(forward=False))
        replace_button.clicked.connect(self.replace_text)
        replace_all_button.clicked.connect(self.replace_all_text)
        close_button.clicked.connect(self.close)

        button_layout.addWidget(find_next_button)
        button_layout.addWidget(find_prev_button)
        button_layout.addWidget(replace_button)
        button_layout.addWidget(replace_all_button)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)
        
    def update_options(self):
        self.case_sensitive = self.case_check.isChecked()
        self.whole_words = self.whole_check.isChecked()
        self.search_backward = self.backward_check.isChecked()
        
    def find_text_changed(self):
        search_text = self.find_input.text()
        if search_text != self.last_search:
            self.last_search = search_text
            self.highlight_matches(search_text)

    def highlight_matches(self, text):
        editor = self.parent.tab_widget.currentWidget()
        if not editor or not text:
            return

        cursor = editor.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(QTextCharFormat())
        cursor.clearSelection()

        if text:
            highlight_format = QTextCharFormat()
            highlight_format.setBackground(QColor("#404040"))
            
            cursor = editor.document().find(text, 0,
                self.get_find_flags())
            
            while not cursor.isNull():
                cursor.mergeCharFormat(highlight_format)
                cursor = editor.document().find(text, cursor,
                    self.get_find_flags())

    def get_find_flags(self):
        flags = QTextDocument.FindFlag(0)
        if self.case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if self.whole_words:
            flags |= QTextDocument.FindFlag.FindWholeWords
        if self.search_backward:
            flags |= QTextDocument.FindFlag.FindBackward
        return flags

    def find_text(self, forward=True):
        text = self.find_input.text()
        editor = self.parent.tab_widget.currentWidget()
        if not editor or not text:
            return

        flags = self.get_find_flags()
        if not forward:
            flags |= QTextDocument.FindFlag.FindBackward

        cursor = editor.textCursor()
        if forward:
            start = cursor.position()
        else:
            start = cursor.anchor()

        new_cursor = editor.document().find(text, start, flags)
        
        if new_cursor.isNull():
            if forward:
                start = 0
            else:
                start = len(editor.toPlainText())
            new_cursor = editor.document().find(text, start, flags)
            
        if not new_cursor.isNull():
            editor.setTextCursor(new_cursor)
        else:
            QMessageBox.information(self, "Search",
                f"Text '{text}' not found.")

    def replace_text(self):
        editor = self.parent.tab_widget.currentWidget()
        if not editor:
            return

        cursor = editor.textCursor()
        if cursor.hasSelection():
            cursor.insertText(self.replace_input.text())
            self.find_text(forward=True)

    def replace_all_text(self):
        editor = self.parent.tab_widget.currentWidget()
        if not editor:
            return

        text = self.find_input.text()
        replace_with = self.replace_input.text()
        
        if not text:
            return

        cursor = editor.textCursor()
        cursor.beginEditBlock()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        editor.setTextCursor(cursor)
        
        count = 0
        while True:
            if not editor.find(text, self.get_find_flags()):
                break
            cursor = editor.textCursor()
            cursor.insertText(replace_with)
            count += 1
            
        cursor.endEditBlock()
        QMessageBox.information(self, "Replacement", f"Replacement {count} coincidences.")

class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Cascadia Code", 12))
        self.file_path = None
        self.highlighter = PythonHighlighter(self.document())
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                border: 1px solid #3E3E3E;
            }
        """)
        self.textChanged.connect(self.on_text_changed)
        
    def on_text_changed(self):
        log_manager.log('debug', f'The text has been changed in the editor. {self.file_path or "New file"}')

class TabWidget(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.tabCloseRequested.connect(self.close_tab)
        self.create_new_tab()
        self.currentChanged.connect(self.on_tab_changed)
        
    def create_new_tab(self, file_path=None):
        editor = CodeEditor(self)
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                editor.setPlainText(content)
                editor.file_path = file_path
                tab_name = os.path.basename(file_path)
            except Exception as e:
                log_manager.log('error', f'Error opening file {file_path}: {str(e)}')
                return None
        else:
            tab_name = "New file"
            
        index = self.addTab(editor, tab_name)
        self.setCurrentIndex(index)
        log_manager.log('info', 'A new tab has been created')
        return editor
        
    def close_tab(self, index):
        widget = self.widget(index)
        if widget.file_path and os.path.exists(widget.file_path):
            log_manager.log('info', f'The tab with the file is closed: {widget.file_path}')
        self.removeTab(index)
        
        if self.count() == 0:
            self.create_new_tab()
            
    def on_tab_changed(self, index):
        if index >= 0:
            editor = self.widget(index)
            if editor.file_path:
                log_manager.log('info', f'Switch to tab: {editor.file_path}')
            else:
                log_manager.log('info', 'Switch to a new tab')

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Faye IDE")
        self.setGeometry(100, 100, 1200, 800)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        main_layout = QVBoxLayout(self.central_widget)
        self.tab_widget = TabWidget(self)
        main_layout.addWidget(self.tab_widget)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        self.create_output_dock()
        
        self.create_menu()
        self.create_toolbar()
        self.set_dark_theme()
        
    def create_output_dock(self):
        self.output_widget = QPlainTextEdit()
        self.output_widget.setReadOnly(True)
        self.output_widget.setFont(QFont("Consolas", 10))
        self.output_widget.setStyleSheet("background-color: #1E1E1E; color: #D4D4D4; border: 1px solid #3E3E3E;")
        self.dock = QDockWidget("Terminal / Output", self)
        self.dock.setWidget(self.output_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock)

    def create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        
        new_action = file_menu.addAction("New")
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.tab_widget.create_new_tab)
        
        open_action = file_menu.addAction("Open")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        
        save_action = file_menu.addAction("Save")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_file)
        
        save_as_action = file_menu.addAction("Save as")
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_file_as)
        
        file_menu.addSeparator()
        
        run_action = file_menu.addAction("Run")
        run_action.setShortcut("F5")
        run_action.triggered.connect(self.run_code)
        
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        
        edit_menu = menubar.addMenu("Edit")
        
        undo_action = edit_menu.addAction("Cancel")
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(lambda: self.get_current_editor().undo())
        
        redo_action = edit_menu.addAction("Repeat")
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(lambda: self.get_current_editor().redo())
        
        edit_menu.addSeparator()
        
        cut_action = edit_menu.addAction("Cut")
        cut_action.setShortcut("Ctrl+X")
        cut_action.triggered.connect(lambda: self.get_current_editor().cut())
        
        copy_action = edit_menu.addAction("Copy")
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(lambda: self.get_current_editor().copy())
        
        paste_action = edit_menu.addAction("Copy")
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(lambda: self.get_current_editor().paste())
        
        edit_menu.addSeparator()
        
        find_action = edit_menu.addAction("Find")
        find_action.setShortcut("Ctrl+F")
        find_action.triggered.connect(self.show_find_dialog)
        
    def create_toolbar(self):
        toolbar = self.addToolBar("Main toolbar")
        toolbar.setMovable(False)
        
        new_action = toolbar.addAction("New")
        new_action.triggered.connect(self.tab_widget.create_new_tab)
        
        open_action = toolbar.addAction("Open")
        open_action.triggered.connect(self.open_file)
        
        save_action = toolbar.addAction("Save")
        save_action.triggered.connect(self.save_file)
        
        toolbar.addSeparator()
        
        run_action = toolbar.addAction("Run")
        run_action.triggered.connect(self.run_code)
        
        toolbar.addSeparator()
        
        cut_action = toolbar.addAction("Cut")
        cut_action.triggered.connect(lambda: self.get_current_editor().cut())
        
        copy_action = toolbar.addAction("Copy")
        copy_action.triggered.connect(lambda: self.get_current_editor().copy())
        
        paste_action = toolbar.addAction("Paste")
        paste_action.triggered.connect(lambda: self.get_current_editor().paste())
        
        toolbar.addSeparator()
        
        find_action = toolbar.addAction("Find")
        find_action.triggered.connect(self.show_find_dialog)
        
    def set_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1E1E1E; color: #D4D4D4; }
            QMenuBar { background-color: #2D2D2D; color: #FFFFFF; }
            QMenuBar::item { color: #FFFFFF; }
            QMenuBar::item:selected { background-color: #3E3E3E; }
            QMenu { background-color: #2D2D2D; color: #FFFFFF; border: 1px solid #3E3E3E; }
            QMenu::item:selected { background-color: #3E3E3E; }
            QToolBar { background-color: #2D2D2D; border: none; color: #FFFFFF; }
            QStatusBar { background-color: #2D2D2D; color: #D4D4D4; }
            QTabWidget::pane { border: 1px solid #3E3E3E; }
            QTabBar::tab { background-color: #2D2D2D; color: #D4D4D4; padding: 5px 10px; border: 1px solid #3E3E3E; }
            QTabBar::tab:selected { background-color: #1E1E1E; }
            QPlainTextEdit { background-color: #1E1E1E; color: #D4D4D4; border: 1px solid #3E3E3E; selection-background-color: #264F78; selection-color: #D4D4D4; }
            QLineEdit { background-color: #1E1E1E; color: #D4D4D4; border: 1px solid #3E3E3E; padding: 2px; }
            QPushButton { background-color: #2D2D2D; color: #D4D4D4; border: 1px solid #3E3E3E; padding: 5px 10px; }
            QPushButton:hover { background-color: #3E3E3E; }
            QPushButton:pressed { background-color: #4E4E4E; }
            QDockWidget { color: #FFFFFF; titlebar-close-icon: none; }
            QDockWidget::title { background-color: #2D2D2D; text-align: center; padding: 5px; }
        """)
        
    def get_current_editor(self):
        return self.tab_widget.currentWidget()
        
    def show_find_dialog(self):
        dialog = FindDialog(self)
        dialog.show()
        
    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open file", "", "Python files (*.py);;Text files (*.txt);;All files (*.*)"
        )
        if file_path:
            try:
                editor = self.tab_widget.create_new_tab(file_path)
                if editor:
                    index = self.tab_widget.currentIndex()
                    self.tab_widget.setTabText(index, os.path.basename(file_path))
                    self.status_bar.showMessage(f"File {file_path} opened")
                    log_manager.log('info', f'Opened file: {file_path}')
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open file: {str(e)}")
                log_manager.log('error', f'Error opening file {file_path}: {str(e)}')
                
    def save_file(self):
        editor = self.get_current_editor()
        if not editor: return False
        if not editor.file_path: return self.save_file_as()
        try:
            with open(editor.file_path, 'w', encoding='utf-8') as file:
                file.write(editor.toPlainText())
            self.status_bar.showMessage(f"File {editor.file_path} saved")
            log_manager.log('info', f'Saved file: {editor.file_path}')
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file: {str(e)}")
            log_manager.log('error', f'Error saving file {editor.file_path}: {str(e)}')
            return False
            
    def save_file_as(self):
        editor = self.get_current_editor()
        if not editor: return False
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save file as", "", "Python files (*.py);;Text files (*.txt);;All files (*.*)"
        )
        if file_path:
            editor.file_path = file_path
            index = self.tab_widget.currentIndex()
            self.tab_widget.setTabText(index, os.path.basename(file_path))
            return self.save_file()
        return False

    def run_code(self):
        editor = self.get_current_editor()
        if not editor: return
        
        if not editor.file_path:
            if not self.save_file_as(): return
        else:
            if not self.save_file(): return
            
        self.output_widget.clear()
        self.output_widget.appendPlainText(f"--- Run {editor.file_path} ---\n")
        
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.handle_output)
        
        log_manager.log('info', f'Run code: {editor.file_path}')
        self.process.start(sys.executable, [editor.file_path])
        
    def handle_output(self):
        data = self.process.readAllStandardOutput()
        text = data.data().decode('utf-8')
        self.output_widget.appendPlainText(text)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
