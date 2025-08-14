import sys
import os
import random
import time
import json
import re
from datetime import datetime
import requests
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QProgressBar, QListWidget, QMessageBox, QLineEdit,
    QCheckBox, QFileDialog, QGroupBox, QTabWidget, QScrollArea, QSizePolicy,
    QDialog, QListWidget, QDialogButtonBox
)
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PIL import Image, ImageDraw, ImageFont

API_KEY = "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"
IMAGES_FOLDER = "images"
OUTPUT_FOLDER = "output"
FONTS_FOLDER = "fonts"
CONFIG_FILE = "config.json"
SESSION_FILE = "session.json"
TEXT_FONT_NAME = "PlusJakartaSans-Regular.ttf"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

CATEGORIES = ["Sister", "Love", "Friends", "Mom", "Papa", "Bhai", "Life", "Sad", "Romantic", "Motivational"]
EMOJI_REGEX = re.compile(r'[\U00010000-\U0010ffff]')

try:
    from instagrapi import Client
    INSTAGRAPI_AVAILABLE = True
except ImportError:
    INSTAGRAPI_AVAILABLE = False

class Utilities:
    @staticmethod
    def font_path(filename):
        return os.path.join(os.getcwd(), FONTS_FOLDER, filename)

    @staticmethod
    def ensure_text_font():
        return os.path.isfile(Utilities.font_path(TEXT_FONT_NAME))

    @staticmethod
    def save_config(data):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    @staticmethod
    def load_config():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def remove_emojis(text):
        return EMOJI_REGEX.sub('', text)

class ShayariEngine:
    @staticmethod
    def generate_prompt(category):
        return (
            f"Write a beautiful 2-4 line under in 4 line Hindi shayari in English script about {category} "
            "with no emojis. Make it emotional and poetic. "
            "Return only the shayari lines, no extra text or numbering."
            "Return only shyri do not add any symbole like double quotation marks "
        )

    @staticmethod
    def hashtag_prompt(shayari):
        return (
            f"Generate exactly 5 most relevant Instagram hashtags for:\n{shayari}\n"
            "Return only hashtags separated by spaces, no numbers or extra text."
        )

    @staticmethod
    def call_ai(prompt, max_tokens=220, temperature=0.85):
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://your-site.com",
            "X-Title": "AI Shayri Instabot"
        }
        payload = {
            "model": "deepseek/deepseek-chat-v3-0324:free",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception as e:
            print(f"API Error: {e}")
            return ""

class ImageProcessor:
    @staticmethod
    def create_image(text, image_path, output_folder=OUTPUT_FOLDER):
        try:
            img = Image.open(image_path).convert("RGBA")
            W, H = img.size
            
            txt_layer = Image.new("RGBA", (W, H), (255, 255, 255, 0))
            draw = ImageDraw.Draw(txt_layer)
            
            font_path = Utilities.font_path(TEXT_FONT_NAME)
            try:
                font_size = max(24, int(W * 0.045))
                font = ImageFont.truetype(font_path, font_size)
            except:
                font = ImageFont.load_default()
            
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            line_height = int(font_size * 1.5)
            total_text_height = len(lines) * line_height
            y = (H - total_text_height) // 2
            
            for line in lines:
                text_width = draw.textlength(line, font=font)
                x = (W - text_width) // 2
                
                shadow_color = (0, 0, 0, 150)
                for offset in [(-1,-1), (1,1), (-1,1), (1,-1)]:
                    draw.text((x+offset[0], y+offset[1]), line, font=font, fill=shadow_color)
                
                draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
                y += line_height
            
            result = Image.alpha_composite(img, txt_layer).convert("RGB")
            os.makedirs(output_folder, exist_ok=True)
            output_path = os.path.join(output_folder, f"shayari_{int(time.time())}.jpg")
            result.save(output_path, quality=95)
            return output_path
        except Exception as e:
            print(f"Image processing error: {e}")
            return None

class InstagramManager:
    @staticmethod
    def try_load_session(client, log_callback):
        if not INSTAGRAPI_AVAILABLE:
            log_callback("instagrapi not available")
            return False
        
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r") as f:
                    settings = json.load(f)
                    client.set_settings(settings)
                    client.set_uuids(settings.get("uuids"))
                    client.get_timeline()
                    log_callback("Session loaded successfully")
                    return True
            except Exception as e:
                log_callback(f"Session load failed: {e}")
        return False

    @staticmethod
    def save_session(client, log_callback):
        try:
            settings = client.get_settings()
            with open(SESSION_FILE, "w") as f:
                json.dump(settings, f)
            log_callback("Session saved")
            return True
        except Exception as e:
            log_callback(f"Failed to save session: {e}")
            return False

class ImageSelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Background Image")
        self.setMinimumSize(400, 300)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self.image_list = QListWidget()
        self.load_images()
        layout.addWidget(self.image_list)
        
        self.computer_btn = QPushButton("Select From Computer")
        self.computer_btn.clicked.connect(self.select_from_computer)
        layout.addWidget(self.computer_btn)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.selected_image = None
    
    def load_images(self):
        try:
            images = [
                f for f in os.listdir(IMAGES_FOLDER) 
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            self.image_list.clear()
            self.image_list.addItems(images)
        except Exception as e:
            print(f"Error loading images: {e}")
    
    def select_from_computer(self):
        options = QFileDialog.Options()
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Background Image",
            "",
            "Images (*.png *.jpg *.jpeg)",
            options=options
        )
        
        if files:
            self.selected_image = files[0]
            self.accept()
    
    def accept(self):
        if self.image_list.currentItem() and not self.selected_image:
            self.selected_image = os.path.join(IMAGES_FOLDER, self.image_list.currentItem().text())
        super().accept()

class Worker(QThread):
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    shayari_generated = pyqtSignal(str)
    image_created = pyqtSignal(str)
    hashtags_ready = pyqtSignal(str)
    finished = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)

    def __init__(self, category, username="", password="", post_to_ig=False, custom_image=None, shayari_text=""):
        super().__init__()
        self.category = category
        self.username = username
        self.password = password
        self.post_to_ig = post_to_ig
        self.custom_image = custom_image
        self.shayari_text = shayari_text
        self.generated_shayari = ""
        self.generated_hashtags = ""
        self.image_path = ""

    def run(self):
        try:
            self.progress_updated.emit(10)
            
            if not self.shayari_text:
                self.status_updated.emit("Generating shayari...")
                prompt = ShayariEngine.generate_prompt(self.category)
                self.generated_shayari = ShayariEngine.call_ai(prompt)
                
                if not self.generated_shayari:
                    raise Exception("AI failed to generate shayari")
                
                self.shayari_generated.emit(self.generated_shayari)
                self.progress_updated.emit(30)
                
                self.status_updated.emit("Generating hashtags...")
                prompt = ShayariEngine.hashtag_prompt(self.generated_shayari)
                raw_hashtags = ShayariEngine.call_ai(prompt, max_tokens=60, temperature=0.6)
                self.generated_hashtags = self.clean_hashtags(raw_hashtags)
                self.hashtags_ready.emit(self.generated_hashtags)
            else:
                self.generated_shayari = self.shayari_text
                self.progress_updated.emit(50)
            
            self.status_updated.emit("Creating image...")
            image_file = self.custom_image if self.custom_image else self.select_random_image()
            if not image_file:
                raise Exception("No images found")
                
            self.image_path = ImageProcessor.create_image(
                Utilities.remove_emojis(self.generated_shayari),
                image_file
            )
            
            if not self.image_path:
                raise Exception("Failed to create image")
                
            self.image_created.emit(self.image_path)
            self.progress_updated.emit(80)
            
            if self.post_to_ig and INSTAGRAPI_AVAILABLE:
                self.status_updated.emit("Posting to Instagram...")
                self.post_to_instagram()
            
            self.progress_updated.emit(100)
            self.status_updated.emit("Process completed successfully")
            self.finished.emit(True)
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            self.finished.emit(False)

    def clean_hashtags(self, raw_tags):
        tags = []
        for word in raw_tags.split():
            if word.startswith("#"):
                clean = re.sub(r'[^#A-Za-z0-9_]', '', word)
                if clean and clean not in tags:
                    tags.append(clean)
            elif re.match(r'^[A-Za-z0-9_]+$', word):
                tag = f"#{word}"
                if tag not in tags:
                    tags.append(tag)
            if len(tags) >= 5:
                break
        
        if len(tags) < 5:
            tags.extend(["#shayari", "#hindishayari", "#dilse", "#feelings", "#poetry"][:5-len(tags)])
        return " ".join(tags[:5])

    def select_random_image(self):
        try:
            images = [
                f for f in os.listdir(IMAGES_FOLDER) 
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            if not images:
                return None
            return os.path.join(IMAGES_FOLDER, random.choice(images))
        except Exception:
            return None

    def post_to_instagram(self):
        try:
            cl = Client()
            if not InstagramManager.try_load_session(cl, self.status_updated.emit):
                if not self.username or not self.password:
                    raise Exception("Instagram credentials required")
                cl.login(self.username, self.password)
                InstagramManager.save_session(cl, self.status_updated.emit)
            
            caption = f"{self.generated_shayari}\n\n{self.generated_hashtags}"
            cl.photo_upload(self.image_path, caption)
            self.status_updated.emit("Posted successfully to Instagram")
        except Exception as e:
            raise Exception(f"Instagram post failed: {str(e)}")

class ImagePreviewDialog(QWidget):
    def __init__(self, image_path):
        super().__init__()
        self.setWindowTitle("Image Preview")
        self.setGeometry(100, 100, 800, 600)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.image_label)
        
        self.load_image(image_path)
        
    def load_image(self, image_path):
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.size(), 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)

class ShayariApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Shayri Instabot - by S-Nishad")
        self.setMinimumSize(900, 600)
        self.current_preview = None
        self.worker = None
        self.current_shayari = ""
        self.current_hashtags = ""
        self.custom_image_path = None
        self.setup_ui()
        self.load_config()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        
        left_panel = QVBoxLayout()
        left_panel.setContentsMargins(5, 5, 5, 5)
        
        account_group = QGroupBox("Account Settings")
        account_layout = QVBoxLayout()
        
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.save_creds_cb = QCheckBox("Save Credentials")
        self.save_creds_cb.setChecked(True)
        
        account_layout.addWidget(QLabel("Instagram Username:"))
        account_layout.addWidget(self.username_input)
        account_layout.addWidget(QLabel("Instagram Password:"))
        account_layout.addWidget(self.password_input)
        account_layout.addWidget(self.save_creds_cb)
        account_group.setLayout(account_layout)
        left_panel.addWidget(account_group)
        
        settings_group = QGroupBox("Shayari Settings")
        settings_layout = QVBoxLayout()
        
        self.cat_combo = QComboBox()
        self.cat_combo.addItems(CATEGORIES)
        self.cat_combo.setCurrentIndex(0)
        
        self.select_img_btn = QPushButton("Select Custom Image (Optional)")
        self.select_img_btn.clicked.connect(self.select_custom_image)
        
        settings_layout.addWidget(QLabel("Select Category:"))
        settings_layout.addWidget(self.cat_combo)
        settings_layout.addWidget(self.select_img_btn)
        settings_group.setLayout(settings_layout)
        left_panel.addWidget(settings_group)
        
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout()
        
        self.shayari_display = QTextEdit()
        self.shayari_display.setReadOnly(False)
        self.shayari_display.setFixedHeight(100)
        self.shayari_display.setStyleSheet("font-size: 14px;")
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll_area.setWidget(self.preview_label)
        
        preview_layout.addWidget(QLabel("Generated Shayari:"))
        preview_layout.addWidget(self.shayari_display)
        preview_layout.addWidget(QLabel("Image Preview:"))
        preview_layout.addWidget(self.scroll_area)
        preview_group.setLayout(preview_layout)
        left_panel.addWidget(preview_group)
        
        btn_layout = QHBoxLayout()
        self.generate_btn = QPushButton("Generate Shayari")
        self.generate_btn.setStyleSheet("font-weight: bold;")
        self.generate_btn.clicked.connect(self.generate_shayari_only)
        
        self.create_img_btn = QPushButton("Create Image")
        self.create_img_btn.clicked.connect(self.create_image_only)
        self.create_img_btn.setEnabled(False)
        
        self.post_btn = QPushButton("Post to Instagram")
        self.post_btn.setStyleSheet("background-color: #405DE6; color: white; font-weight: bold;")
        self.post_btn.clicked.connect(self.post_to_instagram)
        self.post_btn.setEnabled(False)
        
        btn_layout.addWidget(self.generate_btn)
        btn_layout.addWidget(self.create_img_btn)
        btn_layout.addWidget(self.post_btn)
        left_panel.addLayout(btn_layout)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #405DE6;
            }
        """)
        left_panel.addWidget(self.progress_bar)
        
        right_panel = QVBoxLayout()
        right_panel.setContentsMargins(5, 5, 5, 5)
        
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout()
        
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("font-family: monospace; font-size: 12px;")
        
        log_layout.addWidget(self.log_box)
        log_group.setLayout(log_layout)
        right_panel.addWidget(log_group)
        
        history_group = QGroupBox("History")
        history_layout = QVBoxLayout()
        
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.show_history_item)
        self.history_list.setStyleSheet("font-size: 12px;")
        
        history_layout.addWidget(self.history_list)
        history_group.setLayout(history_layout)
        right_panel.addWidget(history_group)
        
        main_layout.addLayout(left_panel, 60)
        main_layout.addLayout(right_panel, 40)

    def load_config(self):
        config = Utilities.load_config()
        self.username_input.setText(config.get("username", ""))
        self.password_input.setText(config.get("password", ""))

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.append(f"[{timestamp}] {message}")
        self.log_box.ensureCursorVisible()

    def generate_shayari_only(self):
        if not API_KEY:
            QMessageBox.warning(self, "Error", "API key is required")
            return
        
        self.worker = Worker(
            self.cat_combo.currentText(),
            self.username_input.text(),
            self.password_input.text()
        )
        
        self.worker.progress_updated.connect(self.progress_bar.setValue)
        self.worker.status_updated.connect(self.log)
        self.worker.shayari_generated.connect(self.handle_shayari_generated)
        self.worker.hashtags_ready.connect(self.handle_hashtags_generated)
        self.worker.finished.connect(self.process_finished)
        self.worker.error_occurred.connect(self.show_error)
        
        self.set_ui_enabled(False)
        self.worker.start()

    def handle_shayari_generated(self, shayari):
        self.current_shayari = shayari
        self.shayari_display.setPlainText(shayari)
        self.create_img_btn.setEnabled(True)

    def handle_hashtags_generated(self, hashtags):
        self.current_hashtags = hashtags
        self.log(f"Generated hashtags: {hashtags}")

    def create_image_only(self):
        if not self.current_shayari:
            QMessageBox.warning(self, "Error", "No shayari generated yet")
            return
        
        if self.custom_image_path:
            self.create_image_with_custom_path(self.custom_image_path)
        else:
            dialog = ImageSelectDialog(self)
            if dialog.exec_() == QDialog.Accepted and dialog.selected_image:
                self.create_image_with_custom_path(dialog.selected_image)

    def create_image_with_custom_path(self, image_path):
        self.worker = Worker(
            self.cat_combo.currentText(),
            self.username_input.text(),
            self.password_input.text(),
            custom_image=image_path,
            shayari_text=self.shayari_display.toPlainText()
        )
        
        self.worker.progress_updated.connect(self.progress_bar.setValue)
        self.worker.status_updated.connect(self.log)
        self.worker.image_created.connect(self.show_preview)
        self.worker.finished.connect(self.process_finished)
        self.worker.error_occurred.connect(self.show_error)
        
        self.set_ui_enabled(False)
        self.worker.start()

    def select_custom_image(self):
        dialog = ImageSelectDialog(self)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_image:
            self.custom_image_path = dialog.selected_image
            self.log(f"Selected custom image: {os.path.basename(self.custom_image_path)}")

    def post_to_instagram(self):
        if not hasattr(self, 'current_preview'):
            QMessageBox.warning(self, "Error", "No image created yet")
            return
            
        reply = QMessageBox.question(
            self,
            "Confirm Post",
            "Are you sure you want to post this to Instagram?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.worker = Worker(
                self.cat_combo.currentText(),
                self.username_input.text(),
                self.password_input.text(),
                post_to_ig=True,
                custom_image=self.custom_image_path,
                shayari_text=self.shayari_display.toPlainText()
            )
            
            self.worker.image_path = self.current_preview
            
            self.worker.progress_updated.connect(self.progress_bar.setValue)
            self.worker.status_updated.connect(self.log)
            self.worker.finished.connect(self.process_finished)
            self.worker.error_occurred.connect(self.show_error)
            
            self.set_ui_enabled(False)
            self.worker.start()

    def show_preview(self, path):
        self.current_preview = path
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self.preview_label.setPixmap(pixmap)
            self.preview_label.setMinimumSize(1, 1)
            self.preview_label.adjustSize()
            
            self.history_list.insertItem(0, f"{datetime.now().strftime('%H:%M:%S')} - {os.path.basename(path)}")
            self.post_btn.setEnabled(True)
            
            preview_dialog = ImagePreviewDialog(path)
            preview_dialog.show()

    def show_history_item(self, item):
        path = os.path.join(OUTPUT_FOLDER, item.text().split(" - ")[1])
        if os.path.exists(path):
            self.show_preview(path)

    def process_finished(self, success):
        self.set_ui_enabled(True)
        if success and self.save_creds_cb.isChecked():
            Utilities.save_config({
                "username": self.username_input.text(),
                "password": self.password_input.text()
            })

    def show_error(self, message):
        QMessageBox.critical(self, "Error", message)
        self.log(f"Error: {message}")

    def set_ui_enabled(self, enabled):
        self.generate_btn.setEnabled(enabled)
        self.create_img_btn.setEnabled(enabled and bool(self.shayari_display.toPlainText()))
        self.post_btn.setEnabled(enabled and hasattr(self, 'current_preview'))
        self.select_img_btn.setEnabled(enabled)
        self.cat_combo.setEnabled(enabled)
        self.username_input.setEnabled(enabled)
        self.password_input.setEnabled(enabled)
        self.save_creds_cb.setEnabled(enabled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'current_preview') and self.current_preview:
            self.update_preview_size()
        
    def update_preview_size(self):
        if not self.current_preview:
            return
        
        pixmap = QPixmap(self.current_preview)
        if pixmap.isNull():
            return
        
        available_size = self.scroll_area.viewport().size()
        available_size.setWidth(available_size.width() - 20)
        available_size.setHeight(available_size.height() - 20)
        
        scaled_pixmap = pixmap.scaled(
            available_size, 
            Qt.KeepAspectRatio, 
            Qt.SmoothTransformation
        )
        self.preview_label.setPixmap(scaled_pixmap)

def main():
    if not os.path.exists(IMAGES_FOLDER):
        os.makedirs(IMAGES_FOLDER)
    
    if not os.path.exists(FONTS_FOLDER):
        os.makedirs(FONTS_FOLDER)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = ShayariApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()