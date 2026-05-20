import logging
from typing import List, Optional

from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QGridLayout,
    QScrollArea,
    QLabel,
    QSlider,
    QApplication,
)
from PyQt6.QtCore import pyqtSignal

from amplify.audio.player import AudioPlayer
from amplify.audio.router import AudioRouter
from amplify.sounds.soundlist import SoundList

logger = logging.getLogger(__name__)

GRID_COLUMNS = 4
BUTTON_WIDTH = 100
BUTTON_HEIGHT = 100
FLAT_DARK_STYLESHEET = """
    QMainWindow {
        background-color: #1e1e1e;
        color: #e0e0e0;
    }
    QWidget {
        background-color: #1e1e1e;
        color: #e0e0e0;
    }
    QPushButton {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #444444;
        border-radius: 0px;
        padding: 8px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #3d3d3d;
    }
    QPushButton:pressed {
        background-color: #1d1d1d;
    }
    QPushButton:focus {
        outline: none;
        border: 2px solid #0078d4;
    }
    QLineEdit {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #444444;
        padding: 5px;
        border-radius: 0px;
    }
    QLineEdit:focus {
        border: 2px solid #0078d4;
    }
    QSlider::groove:horizontal {
        background-color: #2d2d2d;
        height: 6px;
        margin: 2px 0px;
        border-radius: 0px;
    }
    QSlider::handle:horizontal {
        background-color: #0078d4;
        width: 18px;
        margin: -6px 0px;
        border-radius: 0px;
    }
    QScrollArea {
        background-color: #1e1e1e;
        border: none;
    }
    QScrollBar:vertical {
        background-color: #1e1e1e;
        width: 12px;
        border: none;
    }
    QScrollBar::handle:vertical {
        background-color: #444444;
        border-radius: 0px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #555555;
    }
"""


class SoundButton(QPushButton):
    clicked_with_sound = pyqtSignal(str)

    def __init__(self, sound_name: str):
        super().__init__(sound_name)
        self.sound_name = sound_name
        self.setFixedSize(QSize(BUTTON_WIDTH, BUTTON_HEIGHT))
        self.setWordWrap(True)
        self.clicked.connect(self.on_clicked)

    def on_clicked(self):
        self.clicked_with_sound.emit(self.sound_name)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AMPLIFY")
        self.setGeometry(100, 100, 1000, 700)
        self.setStyleSheet(FLAT_DARK_STYLESHEET)

        self.player = AudioPlayer()
        self.router = AudioRouter()
        self.sound_list = SoundList()

        self.current_mode = "speaker"
        self.current_volume = 1.0
        self.sound_buttons: dict[str, SoundButton] = {}
        self.displayed_sounds: List[str] = []

        self._create_ui()
        QTimer.singleShot(500, self._load_sounds)

    def _create_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        top_layout = QHBoxLayout()

        self.btn_speaker = QPushButton("SPEAKER")
        self.btn_speaker.setMaximumWidth(100)
        self.btn_speaker.setCheckable(True)
        self.btn_speaker.setChecked(True)
        self.btn_speaker.clicked.connect(lambda: self._set_mode("speaker"))

        self.btn_microphone = QPushButton("MICROPHONE")
        self.btn_microphone.setMaximumWidth(100)
        self.btn_microphone.setCheckable(True)
        self.btn_microphone.clicked.connect(lambda: self._set_mode("microphone"))

        self.btn_both = QPushButton("BOTH")
        self.btn_both.setMaximumWidth(100)
        self.btn_both.setCheckable(True)
        self.btn_both.clicked.connect(lambda: self._set_mode("both"))

        top_layout.addWidget(self.btn_speaker)
        top_layout.addWidget(self.btn_microphone)
        top_layout.addWidget(self.btn_both)

        top_layout.addStretch()
        vol_label = QLabel("Vol:")
        top_layout.addWidget(vol_label)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(100)
        self.volume_slider.setMaximumWidth(150)
        self.volume_slider.sliderMoved.connect(self._on_volume_changed)
        top_layout.addWidget(self.volume_slider)

        main_layout.addLayout(top_layout)

        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to filter sounds...")
        self.search_input.textChanged.connect(self._on_search)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        main_layout.addLayout(search_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: 1px solid #444444; }")

        grid_widget = QWidget()
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setSpacing(8)

        scroll_area.setWidget(grid_widget)
        main_layout.addWidget(scroll_area)

        bottom_layout = QHBoxLayout()

        self.btn_stop_all = QPushButton("STOP ALL")
        self.btn_stop_all.setMaximumWidth(100)
        self.btn_stop_all.clicked.connect(self.player.stop)

        self.status_label = QLabel("Status: Ready")

        bottom_layout.addWidget(self.btn_stop_all)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.status_label)

        main_layout.addLayout(bottom_layout)

    def _load_sounds(self):
        try:
            self.status_label.setText("Status: Loading...")
            QApplication.processEvents()

            if self.sound_list.fetch():
                self.displayed_sounds = self.sound_list.get_sounds()
                self._refresh_grid()
                self.status_label.setText(
                    f"Status: Ready ({len(self.displayed_sounds)} sounds)"
                )
            else:
                self.status_label.setText(
                    f"Status: Error - {self.sound_list.last_error}"
                )
        except Exception as e:
            logger.error(f"Failed to load sounds: {e}")
            self.status_label.setText(f"Status: Error - {str(e)}")

    def _on_search(self, text: str):
        if not text.strip():
            self.displayed_sounds = self.sound_list.get_sounds()
        else:
            self.displayed_sounds = self.sound_list.search(text)

        self._refresh_grid()

    def _refresh_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.sound_buttons.clear()

        for idx, sound_name in enumerate(self.displayed_sounds):
            row = idx // GRID_COLUMNS
            col = idx % GRID_COLUMNS

            btn = SoundButton(sound_name)
            btn.clicked_with_sound.connect(self._on_sound_clicked)
            self.grid_layout.addWidget(btn, row, col)
            self.sound_buttons[sound_name] = btn

        self.grid_layout.addItem(
            self.grid_layout.itemAt(self.grid_layout.count() - 1)
            if self.grid_layout.count() > 0
            else None
        )

    def _on_sound_clicked(self, sound_name: str):
        try:
            url = self.sound_list.get_sound_url(sound_name)
            device_id = self._get_output_device()

            self.status_label.setText(f"Status: Playing {sound_name}...")
            QApplication.processEvents()

            self.player.play_url(url, device_id=device_id, volume=self.current_volume)

            self.status_label.setText(f"Status: Playing {sound_name}")
        except Exception as e:
            logger.error(f"Playback error: {e}")
            self.status_label.setText(f"Status: Error - {str(e)}")

    def _get_output_device(self) -> Optional[int]:
        if self.current_mode == "speaker":
            return self.player.get_default_output_device()
        elif self.current_mode == "microphone":
            return self.router.get_null_sink_id()
        elif self.current_mode == "both":
            return self.player.get_default_output_device()
        return None

    def _set_mode(self, mode: str):
        try:
            self.current_mode = mode

            self.btn_speaker.setChecked(mode == "speaker")
            self.btn_microphone.setChecked(mode == "microphone")
            self.btn_both.setChecked(mode == "both")

            if mode in ("microphone", "both"):
                if not self.router.null_sink_name:
                    if self.router.create_null_sink():
                        self.status_label.setText("Status: Virtual mic ready")
                    else:
                        self.status_label.setText(
                            "Status: Failed to create virtual mic"
                        )
            else:
                if self.router.null_sink_name:
                    self.router.destroy_null_sink()
                    self.status_label.setText("Status: Ready")

        except Exception as e:
            logger.error(f"Mode change error: {e}")
            self.status_label.setText(f"Status: Error - {str(e)}")

    def _on_volume_changed(self, value: int):
        self.current_volume = value / 100.0

    def closeEvent(self, event):
        try:
            self.player.stop()
            self.router.destroy_null_sink()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        event.accept()
