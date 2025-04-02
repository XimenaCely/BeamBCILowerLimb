import globals
from pathlib import Path

import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog


# function to display a UI window which allows to select a file for analysis
def select_file_dialog(show_newest_n_files=5):

    # scan the data directory recursively for XDF files
    xdf_files_in_data = list(globals.DATA_PATH.rglob("*.[xX][dD][fF]"))
    # determine all the XDF files' modification time
    modification_times = [file.stat().st_mtime for file in xdf_files_in_data]
    # zip file paths and corresponding modifications times
    zipped_files_and_times = list(zip(xdf_files_in_data, modification_times))
    # sort them by modification time
    zipped_sorted = sorted(zipped_files_and_times, key = lambda x: x[1], reverse=True)
    # select only the newest to be shown for selection
    newest_files = zipped_sorted[:show_newest_n_files]


    app = QApplication(sys.argv)

    w = QWidget()
    w.setMinimumWidth(720)
    w.move(app.desktop().screen().rect().center() - w.rect().center());
    w.setWindowTitle('Select file for analysis')

    vlayout1 = QVBoxLayout()
    w.setLayout(vlayout1)

    label_instruction = QLabel("Select a recorded xdf-file for analysis:")
    vlayout1.addWidget(label_instruction)

    hlayout1 = QHBoxLayout()

    input_file_path = QLineEdit()
    hlayout1.addWidget(input_file_path)

    def browse_file():
        path, _ = QFileDialog.getOpenFileName(w, "Choose XDF file ...",
                                              str(globals.DATA_PATH),
                                              filter="XDF file (*.xdf)")
        return path

    button_browse = QPushButton("Browse...")
    button_browse.clicked.connect(lambda: input_file_path.setText(browse_file()))
    hlayout1.addWidget(button_browse)

    vlayout1.addLayout(hlayout1)

    vlayout1.addWidget(QLabel("or select one of the most recent recorded files:"))

    for i, f in enumerate(newest_files):

        fname = str(f[0].relative_to(globals.DATA_PATH))
        fpath = str(f[0].resolve())

        b = QPushButton(fname)
        b.clicked.connect(lambda *x, text=fpath: input_file_path.setText(text))

        vlayout1.addWidget(b)

    vlayout1.addSpacing(20)

    label_error = QLabel("")
    label_error.setStyleSheet("QLabel{ color: #ff0000; font-weight: bold;}")
    vlayout1.addWidget(label_error)

    selected_filepath = [None]

    def check_selected_file():
        selfilepath = input_file_path.text()
        selfilepath = selfilepath.strip()

        if len(selfilepath) < 5:
            label_error.setText("Error: No file was selected.")
            return

        if not Path(selfilepath).exists():
            label_error.setText("Error: File does not exist.")
            return

        if Path(selfilepath).is_dir() or Path(selfilepath).suffix.lower() != '.xdf':
            label_error.setText("Error: Wrong type of file. Required type: XDF.")
            return

        selected_filepath.append(selfilepath)
        app.exit(0)

    hlayout2 = QHBoxLayout()
    button_cancel = QPushButton("cancel")
    button_cancel.clicked.connect(lambda: (selected_filepath.append(None), app.exit(0)))
    button_start = QPushButton("run analysis")
    button_start.clicked.connect(lambda: check_selected_file())
    hlayout2.addStretch(1)
    hlayout2.addWidget(button_cancel)
    hlayout2.addWidget(button_start)
    vlayout1.addLayout(hlayout2)

    vlayout1.addStretch(1)

    w.show()
    w.activateWindow()
    app.exec_()

    return selected_filepath[-1]