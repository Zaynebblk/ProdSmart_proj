import os
import json
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, 
    QScrollArea, QLineEdit, QTextEdit, QMessageBox, QFileDialog, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QIcon, QFont, QColor, QPainter, QPainterPath
from resources.theme import get_theme, FONT_FAMILY, rgba


class UserProfilePage(QWidget):
    """User profile page with picture and information display"""
    profile_updated = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setObjectName("UserProfilePage")
        self.username = None
        self.user_id = None
        self.profile_picture_path = None
        self.current_theme = "Dark"
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; } QWidget { background: transparent; }")
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(40, 40, 40, 40)
        content_layout.setSpacing(30)
        
        # ===== HEADER SECTION (Profile Picture + Name) =====
        header_frame = QFrame()
        header_frame.setObjectName("UserProfileHeader")
        header_frame.setMinimumHeight(300)
        header_frame.setMaximumHeight(350)
        header_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(30, 30, 30, 30)
        header_layout.setSpacing(30)
        
        # Profile Picture Section
        pic_container = QFrame()
        pic_container_layout = QVBoxLayout(pic_container)
        pic_container_layout.setContentsMargins(0, 0, 0, 0)
        pic_container_layout.setSpacing(15)
        pic_container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.profile_picture = QLabel()
        self.profile_picture.setFixedSize(200, 200)
        self.profile_picture.setScaledContents(True)
        self.profile_picture.setObjectName("ProfilePicture")
        self.profile_picture.setStyleSheet("""
            QLabel#ProfilePicture {
                border: 3px solid #3078CD;
                border-radius: 100px;
                background-color: #f0f0f0;
            }
        """)
        self._set_default_avatar()
        pic_container_layout.addWidget(self.profile_picture, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Upload Button
        self.btn_upload_picture = QPushButton("📷 Upload Picture")
        self.btn_upload_picture.setFixedHeight(44)
        self.btn_upload_picture.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_upload_picture.setProperty("nav", True)
        self.btn_upload_picture.clicked.connect(self.on_upload_picture)
        pic_container_layout.addWidget(self.btn_upload_picture)
        
        header_layout.addWidget(pic_container)
        
        # User Info Section
        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(15)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        # Title: "My Profile"
        profile_title = QLabel("My Profile")
        profile_title.setObjectName("PageTitle")
        profile_title.setFont(QFont(FONT_FAMILY, 28, QFont.Weight.Bold))
        profile_title.setStyleSheet("color: #3078CD; margin-bottom: 10px;")
        info_layout.addWidget(profile_title)
        
        # Username
        username_label = QLabel("Username")
        username_label.setObjectName("ProfileInfoLabel")
        username_label.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        username_label.setStyleSheet("color: #64748b;")
        info_layout.addWidget(username_label)
        
        self.label_username = QLabel("Not logged in")
        self.label_username.setObjectName("ProfileInfoValue")
        self.label_username.setFont(QFont(FONT_FAMILY, 20, QFont.Weight.Bold))
        self.label_username.setWordWrap(True)
        info_layout.addWidget(self.label_username)
        
        # Join Date
        join_label = QLabel("Member Since")
        join_label.setObjectName("ProfileInfoLabel")
        join_label.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        join_label.setStyleSheet("color: #64748b;")
        info_layout.addWidget(join_label)
        
        self.label_join_date = QLabel(datetime.now().strftime("%B %d, %Y"))
        self.label_join_date.setObjectName("ProfileInfoValue")
        self.label_join_date.setFont(QFont(FONT_FAMILY, 13))
        info_layout.addWidget(self.label_join_date)
        
        # Status
        status_label = QLabel("Status")
        status_label.setObjectName("ProfileInfoLabel")
        status_label.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        status_label.setStyleSheet("color: #64748b;")
        info_layout.addWidget(status_label)
        
        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(8)
        
        self.status_indicator = QLabel("🟢")
        self.status_indicator.setFixedSize(20, 20)
        self.status_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.status_indicator)
        
        self.label_status = QLabel("Active")
        self.label_status.setFont(QFont(FONT_FAMILY, 13))
        status_layout.addWidget(self.label_status)
        status_layout.addStretch()
        
        info_layout.addWidget(status_frame)
        info_layout.addStretch()
        
        header_layout.addWidget(info_container, stretch=1)
        content_layout.addWidget(header_frame)
        
        # ===== DIVIDER =====
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFixedHeight(2)
        divider.setStyleSheet("background-color: #e2e8f0;")
        content_layout.addWidget(divider)
        
        # ===== STATISTICS SECTION =====
        stats_label = QLabel("Statistics")
        stats_label.setFont(QFont(FONT_FAMILY, 16, QFont.Weight.Bold))
        stats_label.setStyleSheet("color: #1e293b; margin-top: 10px;")
        content_layout.addWidget(stats_label)
        
        stats_frame = QFrame()
        stats_frame.setObjectName("StatsFrame")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(20, 20, 20, 20)
        stats_layout.setSpacing(30)
        
        # Stat cards
        self.stat_tasks = self._create_stat_card("Tasks Completed", "0", "#3078CD")
        self.stat_focus = self._create_stat_card("Focus Hours", "0h", "#10b981")
        self.stat_streak = self._create_stat_card("Current Streak", "0 days", "#f59e0b")
        self.stat_teams = self._create_stat_card("Teams Joined", "0", "#8b5cf6")
        
        stats_layout.addWidget(self.stat_tasks)
        stats_layout.addWidget(self.stat_focus)
        stats_layout.addWidget(self.stat_streak)
        stats_layout.addWidget(self.stat_teams)
        
        content_layout.addWidget(stats_frame)
        
        # ===== ABOUT SECTION =====
        about_label = QLabel("About")
        about_label.setFont(QFont(FONT_FAMILY, 16, QFont.Weight.Bold))
        about_label.setStyleSheet("color: #1e293b; margin-top: 10px;")
        content_layout.addWidget(about_label)
        
        about_frame = QFrame()
        about_frame.setObjectName("AboutFrame")
        about_layout = QVBoxLayout(about_frame)
        about_layout.setContentsMargins(20, 20, 20, 20)
        about_layout.setSpacing(15)
        
        about_description = QLabel("Bio")
        about_description.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        about_description.setStyleSheet("color: #64748b;")
        about_layout.addWidget(about_description)
        
        self.text_bio = QTextEdit()
        self.text_bio.setPlaceholderText("Add a bio to tell others about yourself...")
        self.text_bio.setMaximumHeight(100)
        self.text_bio.setStyleSheet("""
            QTextEdit {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 10px;
                background-color: #ffffff;
                color: #333333;
                font-size: 11pt;
            }
        """)
        about_layout.addWidget(self.text_bio)
        
        content_layout.addWidget(about_frame)
        
        # ===== ACTION BUTTONS =====
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        
        self.btn_save = QPushButton("💾 Save Changes")
        self.btn_save.setFixedHeight(44)
        self.btn_save.setMinimumWidth(160)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setProperty("nav", True)
        self.btn_save.clicked.connect(self.on_save_profile)
        buttons_layout.addWidget(self.btn_save)
        
        self.btn_reset = QPushButton("↻ Reset")
        self.btn_reset.setFixedHeight(44)
        self.btn_reset.setMinimumWidth(160)
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.setProperty("nav", True)
        self.btn_reset.clicked.connect(self.load_profile)
        buttons_layout.addWidget(self.btn_reset)
        
        buttons_layout.addStretch()
        content_layout.addLayout(buttons_layout)
        
        content_layout.addStretch()
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
    
    def _create_stat_card(self, title, value, color):
        """Create a statistics card"""
        card = QFrame()
        card.setObjectName("StatCard")
        card.setStyleSheet(f"""
            QFrame#StatCard {{
                background-color: #ffffff;
                border: 2px solid {color}33;
                border-radius: 12px;
                padding: 20px;
            }}
        """)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setMinimumHeight(120)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_label = QLabel(title)
        title_label.setFont(QFont(FONT_FAMILY, 11))
        title_label.setStyleSheet("color: #64748b;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        value_label = QLabel(value)
        value_label.setFont(QFont(FONT_FAMILY, 24, QFont.Weight.Bold))
        value_label.setStyleSheet(f"color: {color};")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)
        
        return card
    
    def _set_default_avatar(self):
        """Set a default avatar with initials"""
        pixmap = QPixmap(200, 200)
        pixmap.fill(QColor("#3078CD"))
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        font = QFont(FONT_FAMILY, 80, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        
        initials = (self.username or "U")[:1].upper()
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, initials)
        painter.end()
        
        self._set_profile_picture_pixmap(pixmap)

    def _create_round_pixmap(self, source_pixmap):
        """Crop a pixmap into a circular avatar."""
        size = self.profile_picture.size()
        scaled = source_pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

        x_offset = max(0, (scaled.width() - size.width()) // 2)
        y_offset = max(0, (scaled.height() - size.height()) // 2)
        square = scaled.copy(x_offset, y_offset, size.width(), size.height())

        rounded = QPixmap(size)
        rounded.fill(Qt.GlobalColor.transparent)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, size.width(), size.height())
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, square)
        painter.end()

        return rounded

    def _set_profile_picture_pixmap(self, pixmap):
        """Display the profile picture as a round avatar."""
        self.profile_picture.setPixmap(self._create_round_pixmap(pixmap))
    
    def set_user_info(self, username, user_id):
        """Set user information"""
        self.username = username
        self.user_id = user_id
        self.label_username.setText(username)
        self._set_default_avatar()
        self.load_profile()
    
    def load_profile(self):
        """Load profile data from settings"""
        try:
            from resources.api_client import load_settings
            settings = load_settings()
            
            # Load bio if exists
            bio = settings.get("user_bio", "")
            self.text_bio.setPlainText(bio)
            
            # Load profile picture if exists
            pic_path = settings.get("user_profile_picture")
            if pic_path and os.path.exists(pic_path):
                pixmap = QPixmap(pic_path)
                if not pixmap.isNull():
                    self._set_profile_picture_pixmap(pixmap)
                    self.profile_picture_path = pic_path
        except Exception as e:
            pass
    
    def on_upload_picture(self):
        """Handle profile picture upload"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Profile Picture",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp);;All Files (*)"
        )
        
        if file_path:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self._set_profile_picture_pixmap(pixmap)
                self.profile_picture_path = file_path
                QMessageBox.information(self, "Success", "Picture updated. Click 'Save Changes' to persist.")
            else:
                QMessageBox.warning(self, "Error", "Failed to load image. Please try another file.")
    
    def on_save_profile(self):
        """Save profile changes"""
        try:
            from resources.api_client import load_settings, save_settings
            import shutil
            
            settings = load_settings()
            
            # Save bio
            settings["user_bio"] = self.text_bio.toPlainText()
            
            # Copy and save profile picture
            if self.profile_picture_path:
                app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                pic_dir = os.path.join(app_dir, "resources", "profiles")
                os.makedirs(pic_dir, exist_ok=True)
                
                pic_filename = f"profile_{self.user_id}.png"
                pic_dest = os.path.join(pic_dir, pic_filename)
                
                shutil.copy2(self.profile_picture_path, pic_dest)
                settings["user_profile_picture"] = pic_dest
            
            save_settings(settings)
            QMessageBox.information(self, "Success", "Profile updated successfully!")
            self.profile_updated.emit()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save profile: {str(e)}")
    
    def update_statistics(self, stats):
        """Update statistics display"""
        try:
            self.stat_tasks.findChild(QLabel).setText(str(stats.get("tasks_completed", 0)))
            # Update other stats as needed
        except Exception:
            pass
    
    def update_theme(self, theme_name):
        """Update theme"""
        self.current_theme = theme_name
        self.update()
