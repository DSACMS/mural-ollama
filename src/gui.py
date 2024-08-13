from PyQt6.QtWidgets import (QFileDialog, QScrollArea, QLabel, QVBoxLayout, QHBoxLayout, QWidget, 
                             QPushButton, QTextEdit, QLineEdit, QMainWindow, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QSize, QTimer, QThread
from PyQt6.QtGui import QPixmap, QImageReader, QIcon, QPainter
from llm_handler import LLMHandler
from pathlib import Path
import json

current_dir = Path(__file__).parent
config_path = current_dir / 'config.json'
with config_path.open('r') as config_file:
    config = json.load(config_file)

APP_NAME = config['APP_NAME']
WINDOW_WIDTH = config['WINDOW_WIDTH']
WINDOW_HEIGHT = config['WINDOW_HEIGHT']
ASSISTANT_NAME = config['ASSISTANT_NAME']
ASSISTANT_COLOR = config['ASSISTANT_COLOR']

class StreamHandler(QObject):
    new_token = pyqtSignal(str)
    finished = pyqtSignal()

class SpinningWheel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.timer.start(50)
        self.setFixedSize(20, 20)

    def rotate(self):
        self.angle = (self.angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        center = self.rect().center()
        painter.translate(center)
        painter.rotate(self.angle)
        
        for i in range(8):
            painter.rotate(-45)
            painter.drawLine(0, 5, 0, 8)
        
    def start(self):
        self.show()
        self.timer.start()

    def stop(self):
        self.timer.stop()
        self.hide()

class LLMThread(QThread):
    finished = pyqtSignal()

    def __init__(self, llm_handler, method, *args):
        super().__init__()
        self.llm_handler = llm_handler
        self.method = method
        self.args = args

    def run(self):
        method = getattr(self.llm_handler, self.method)
        method(*self.args)
        self.finished.emit()

class MuralAssistantGUI(QMainWindow):
    update_chat_signal = pyqtSignal(str)
    show_loading_signal = pyqtSignal()
    hide_loading_signal = pyqtSignal()
    set_controls_enabled_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.llm_handler = LLMHandler()
        self.current_image_path = None
        self.stream_handler = StreamHandler()
        self.assistant_name = ASSISTANT_NAME
        self.is_assistant_responding = False
        self.llm_thread = None
        self.image_analyzed = False

        self.setWindowTitle(APP_NAME)
        self.setGeometry(100, 100, 1200, 800)
        
        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        main_layout = QHBoxLayout()

        # Left side (image display and buttons)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumSize(600, 400)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_area.setWidget(self.image_label)

        button_layout = QHBoxLayout()
        
        self.upload_button = QPushButton("Upload Mural Screenshot")
        self.upload_button.setFixedHeight(40)

        self.analyze_button = QPushButton("Analyze Mural")
        self.analyze_button.setFixedHeight(40)
        self.analyze_button.setStyleSheet("""
            QPushButton {
                background-color: #b32c4c;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #912740;
            }
        """)
        
        button_layout.addWidget(self.upload_button)
        button_layout.addWidget(self.analyze_button)

        left_layout.addWidget(self.scroll_area)
        left_layout.addLayout(button_layout)

        # Right side (analysis and chat)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        chat_header_layout = QHBoxLayout()
        chat_label = QLabel("Chat:")
        self.spinning_wheel = SpinningWheel()
        self.spinning_wheel.hide()

        chat_header_layout.addWidget(chat_label)
        chat_header_layout.addWidget(self.spinning_wheel)
        chat_header_layout.addStretch()

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)

        input_layout = QHBoxLayout()
        
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Message MurAI")
        self.user_input.setFixedHeight(40)
        
        self.send_button = QPushButton()
        self.send_button.setIcon(QIcon.fromTheme("document-send"))
        self.send_button.setIconSize(QSize(20, 20))
        self.send_button.setFixedSize(40, 40)

        input_layout.addWidget(self.user_input)
        input_layout.addWidget(self.send_button)

        right_layout.addLayout(chat_header_layout)
        right_layout.addWidget(self.chat_display)
        right_layout.addLayout(input_layout)

        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.setup_stylesheet()

    def setup_connections(self):
        self.upload_button.clicked.connect(self.upload_image)
        self.analyze_button.clicked.connect(self.analyze_mural)
        self.send_button.clicked.connect(self.send_message)
        self.user_input.returnPressed.connect(self.send_message)
        
        self.stream_handler.new_token.connect(self.update_chat_display)
        self.stream_handler.finished.connect(self.on_llm_finished)
        self.update_chat_signal.connect(self.update_chat_display)
        self.show_loading_signal.connect(self.show_loading_indicator)
        self.hide_loading_signal.connect(self.hide_loading_indicator)
        self.set_controls_enabled_signal.connect(self.set_controls_enabled)

    def setup_stylesheet(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #1f2124;
                border-radius: 10px;
            }
            QPushButton {
                background-color: rgba(0, 140, 232, 200);
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 5px;
                font-size: 14px;
                height: 40px;
            }
            QPushButton:hover {
                background-color: rgba(0, 120, 212, 180);
            }
            QPushButton#send_button {
                padding: 5px;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QTextEdit, QLineEdit {
                background-color: #25272d;
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 5px;
                padding: 5px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                color: #ffffff;
            }
            QLineEdit {
                height: 40px;
            }
            QLabel {
                font-family: 'Segoe UI', sans-serif;
                font-size: 16px;
                color: #f2f2f2;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(255, 255, 255, 10);
                width: 6px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 80);
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                border: none;
                background: rgba(255, 255, 255, 10);
                height: 6px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(255, 255, 255, 80);
                min-width: 20px;
                border-radius: 3px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

    def set_controls_enabled(self, enabled):
        self.upload_button.setEnabled(enabled)
        self.analyze_button.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.user_input.setEnabled(enabled)

    def send_message(self):
        if not self.is_assistant_responding and self.current_image_path:
            user_message = self.user_input.text()
            if user_message:
                self.update_chat_signal.emit(f"\n<b>You:</b> {user_message}\n")
                self.user_input.clear()
                self.update_chat_signal.emit(f"<b style='color: {ASSISTANT_COLOR};'>{self.assistant_name}:</b> ")
                self.is_assistant_responding = True
                self.show_loading_signal.emit()
                self.set_controls_enabled_signal.emit(False)

                if not self.image_analyzed:
                    # First message after image upload, analyze image and respond to message
                    self.llm_thread = LLMThread(self.llm_handler, 'analyze_and_respond', 
                                                self.current_image_path, user_message, self.stream_handler)
                    self.image_analyzed = True
                else:
                    # Already analyzed image, only respond to message
                    self.llm_thread = LLMThread(self.llm_handler, 'chat', user_message, self.stream_handler)

                self.llm_thread.finished.connect(self.on_llm_finished)
                self.llm_thread.start()
            else:
                self.update_chat_signal.emit("Please enter a message.\n")
        else:
            self.update_chat_signal.emit("Please upload an image first.\n")

    def analyze_mural(self):
        if not self.is_assistant_responding:
            if self.current_image_path:
                self.update_chat_signal.emit("\n<b>You:</b> Analyze this mural\n")
                self.update_chat_signal.emit(f"<b style='color: {ASSISTANT_COLOR};'>{self.assistant_name}:</b> ")
                self.is_assistant_responding = True
                self.show_loading_signal.emit()
                self.set_controls_enabled_signal.emit(False)
                self.llm_thread = LLMThread(self.llm_handler, 'analyze_mural', self.current_image_path, self.stream_handler)
                self.llm_thread.finished.connect(self.on_llm_finished)
                self.llm_thread.start()
                self.image_analyzed = True
            else:
                self.update_chat_signal.emit("Please upload an image first.\n")

    def on_llm_finished(self):
        self.is_assistant_responding = False
        self.hide_loading_signal.emit()
        self.update_chat_signal.emit("\n")
        self.set_controls_enabled_signal.emit(True)
        self.llm_thread = None

    def upload_image(self):
        if not self.is_assistant_responding:
            file_dialog = QFileDialog()
            image_path, _ = file_dialog.getOpenFileName(self, "Open Image", "", "Image Files (*.png *.jpg *.bmp)")
            if image_path:
                self.current_image_path = image_path
                reader = QImageReader(image_path)
                reader.setAutoTransform(True)
                image = reader.read()
                if image.isNull():
                    self.chat_display.append(f"Error loading image: {reader.errorString()}")
                    return

                pixmap = QPixmap.fromImage(image)
                self.display_image(pixmap)
                print("\nImage successfully uploaded\n")
                self.image_analyzed = False  # Reset when a new image is uploaded

    def display_image(self, pixmap):
        scale_factor = self.devicePixelRatio()
        pixmap.setDevicePixelRatio(scale_factor)
        
        max_width, max_height = WINDOW_WIDTH, WINDOW_HEIGHT
        
        if pixmap.width() > max_width or pixmap.height() > max_height:
            pixmap = pixmap.scaled(
                max_width * scale_factor, 
                max_height * scale_factor,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        
        self.image_label.setPixmap(pixmap)
        self.image_label.resize(pixmap.size() / scale_factor)

    def update_chat_display(self, token):
        if self.is_assistant_responding:
            self.chat_display.insertPlainText(token)
        else:
            self.chat_display.append(token)
        self.chat_display.ensureCursorVisible()

    def show_loading_indicator(self):
        self.spinning_wheel.start()

    def hide_loading_indicator(self):
        self.spinning_wheel.stop()
