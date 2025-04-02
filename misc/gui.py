from PyQt5.QtWidgets import QLabel, QWidget, QPushButton, QVBoxLayout, QMessageBox
from PyQt5.QtGui import QCursor, QColor
from PyQt5 import QtGui, QtCore
from threading import Thread

# GUI colors
colors = ["#242423", "#333533", "#4b4b4b", "#eb5e28", "#CCCCCC"]
colors = ["#242423", "#333533", "#6b6b6b", "#06bcc1", "#CCCCCC"]
colors = ["#242423", "#333533", "#6b6b6b", "#fe4a49", "#CCCCCC"]  # red
colors = ["#242423", "#333533", "#6b6b6b", "#0496ff", "#CCCCCC"]

# converts an hex rgb color string into integer rgb values
def hex_to_rgb(h: str) -> tuple:
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


qcolors = [QColor(*hex_to_rgb(h)) for h in colors]

# runs the given function in a new Thread
def fireoffFunction(func):
    t = Thread(daemon=True, target=func)
    t.start()


# displays a MessageBox with given text
def alert(text: str):

    msg = QMessageBox()
    msg.setWindowTitle("Message:")
    msg.setText(text)
    msg.setStandardButtons(QMessageBox.Close)
    msg.exec_()


# helper class for QLabel with Bold text
class BoldLabel(QLabel):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet("QLabel{ font-weight: 600; color: white;}")


# helper class for QLabel to be used as headline
class HeadlineLabel(QLabel):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet("QLabel { font-weight: 400; font-size: 16pt; color: white; }")

class Button(QPushButton):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(QCursor(QtCore.Qt.PointingHandCursor))
        self.setStyleSheet("""
            QPushButton{
                color: #ffffff;
                margin: 2px;
            }
        """)


main_stylesheet = '''
                
                QMainWindow{
                    /*background-color: ''' + colors[0] + ''';*/
                    /*color: white;*/
                    /*border-radius: 20px;*/
                    opacity: 0;
                }
                
                QMainWindow > QWidget#MainWidget{
                    background-color: ''' + colors[0] + ''';
                    opacity: 50;
                    /*border-radius: 0px 0px 20px 20px;*/
                    border-bottom-left-radius: 20px;
                    border-bottom-right-radius: 20px;
                }
                
                
                QLabel{
                    color: ''' + colors[-1] + ''';
                    font-weight: 400;
                }
                
                QPushButton, QLabel{
                    font-family: Corbel, sans-serif;
                    font-size: 10pt;
                }
                
                QPushButton, QLineEdit, QCombobox, QLabel{
                    margin-top: 1px;
                    margin-bottom: 1px;
                }
                
                QPushButton{
                    background-color: ''' + colors[-2] + ''';
                    color: white;
                    font-weight: bold;
                    height: 20px;
                    border-radius: 10px;
                }
                
                QPushButton:hover{
                    background-color: rgb(''' + str(qcolors[-2].darker(150).red()) + ''', ''' + str(qcolors[-2].darker(150).green()) + ''', ''' + str(qcolors[-2].darker(150).blue()) + ''');
                }
                
                QPushButton:pressed{
                    background-color: rgb(''' + str(qcolors[-2].darker(200).red()) + ''', ''' + str(qcolors[-2].darker(200).green()) + ''', ''' + str(qcolors[-2].darker(200).blue()) + ''');
                }
                
                QPushButton:disabled{
                    background-color: ''' + colors[2] + ''';
                }
                
                QGroupBox{
                    background-color: ''' + colors[1] + ''';
                    border: none;
                    border-radius: 15px;
                    padding: 10px;
                }
                
                QComboBox{
                    color: ''' + colors[-1] + ''';
                    background-color: ''' + colors[2] + ''';
                    border: 2px solid ''' + colors[2] + ''';
                }
                
                QLineEdit{
                    color: ''' + colors[-1] + ''';
                    background-color: ''' + colors[2] + ''';
                    border: none;
                    border-radius: 3px;
                    padding-left: 2px;
                    padding-right: 2px;
                }
                
                QLineEdit:focus{
                    color: white;
                    background-color: ''' + colors[-2] + ''';
                }
                
                QListWidget{
                    background-color: ''' + colors[2] + ''';
                    font-family: Consolas, Menlo;
                }
                
                QMenuBar{
                    color: white;
                    background-color: ''' + colors[1] + ''';
                }
                
                QMenuBar::item:selected{
                    color: white;
                    background-color: ''' + colors[-2] + ''';
                }
                
                QMenu{
                    color: ''' + colors[-1] + ''';
                    background-color: ''' + colors[1] + ''';
                }
                
                QMenu::item:selected{
                    color: ''' + colors[-1] + ''';
                    background-color: ''' + colors[-2] + ''';
                }
                
                
                
                QScrollArea { background: transparent; }
                QScrollArea > QWidget > QWidget { background: transparent; }
                
                
                
                
            '''
