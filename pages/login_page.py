import os
import sys
import subprocess
from urllib.parse import urlparse
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QMessageBox, QCheckBox, QGraphicsDropShadowEffect,
    QStackedLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QFont, QPainter, QColor, QLinearGradient, QPixmap, QIcon
from resources.api_client import (
    ApiError,
    api_login,
    api_register,
    api_ping,
    get_base_url,
    set_base_url,
)
from resources.theme import get_theme, FONT_FAMILY, rgba

class AnimatedButton(QPushButton):
    """A custom button with hover animations and modern styling"""
    def __init__(self, text, primary=False):
        super().__init__(text)
        self.primary = primary
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("AnimatedButton")
        self.setProperty("primary", primary)
        
        # Simple hover state
        self.hover_state = False
        
        # Shadow effect
        shadow = QGraphicsDropShadowEffect()
        if self.primary:
            shadow.setBlurRadius(18)
            shadow.setColor(QColor(0, 0, 0, 70))
            shadow.setOffset(0, 4)
        else:
            shadow.setBlurRadius(12)
            shadow.setColor(QColor(0, 0, 0, 40))
            shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

    def enterEvent(self, event):
        self.hover_state = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover_state = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        
        if self.hover_state:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Draw hover overlay
            overlay_color = QColor(255, 255, 255, 30)
            painter.fillRect(self.rect(), overlay_color)
            painter.end()

class CreateAccountPage(QWidget):
    account_created = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.current_theme = "Dark"
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(24, 24, 24, 24)

        card = QFrame()
        card.setObjectName("LoginCard")
        card.setFixedWidth(580)
        card.setMinimumHeight(620)
        card.setMaximumHeight(900)
        self.card = card

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 6)
        card.setGraphicsEffect(shadow)

        self.update_theme(self.current_theme)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        card_layout.setContentsMargins(30, 30, 30, 28)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(10)
        header_layout.setContentsMargins(0, 8, 0, 12)

        title = QLabel("Create your account")
        title.setObjectName("CreateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont(FONT_FAMILY, 26, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setWordWrap(True)
        header_layout.addWidget(title)

        card_layout.addLayout(header_layout)

        def field_block(label_text, placeholder=""):
            block = QVBoxLayout()
            block.setSpacing(8)
            block.setContentsMargins(0, 0, 0, 12)

            separator_layout = QHBoxLayout()
            separator_layout.setContentsMargins(0, 0, 0, 0)
            separator_layout.setSpacing(10)

            left_line = QFrame()
            left_line.setObjectName("SectionLine")
            left_line.setFrameShape(QFrame.Shape.HLine)
            left_line.setFrameShadow(QFrame.Shadow.Plain)
            left_line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            separator_layout.addWidget(left_line)

            section_label = QLabel(label_text)
            section_label.setObjectName("SectionTitle")
            section_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            separator_layout.addWidget(section_label)

            right_line = QFrame()
            right_line.setObjectName("SectionLine")
            right_line.setFrameShape(QFrame.Shape.HLine)
            right_line.setFrameShadow(QFrame.Shadow.Plain)
            right_line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            separator_layout.addWidget(right_line)

            block.addLayout(separator_layout)

            field = QLineEdit()
            field.setObjectName("LoginInput")
            field.setPlaceholderText(placeholder)
            field.setFixedHeight(50)
            block.addWidget(field)
            return block, field

        username_block, self.username_input = field_block("Username", "Choose a username")
        card_layout.addLayout(username_block)

        password_block, self.password_input = field_block("Password", "Create a password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        card_layout.addLayout(password_block)

        confirm_block, self.confirm_input = field_block("Confirm Password", "Repeat your password")
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        card_layout.addLayout(confirm_block)

        server_block, self.server_input = field_block("Server URL", "http://127.0.0.1:8000")
        try:
            self.server_input.setText(get_base_url())
        except Exception:
            pass
        card_layout.addLayout(server_block)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(12)

        self.create_button = AnimatedButton("Create account", primary=True)
        self.create_button.clicked.connect(self.handle_create_account)
        action_layout.addWidget(self.create_button)

        self.back_button = AnimatedButton("Back to login", primary=False)
        self.back_button.clicked.connect(lambda: self.cancel_requested.emit())
        action_layout.addWidget(self.back_button)

        card_layout.addLayout(action_layout)
        main_layout.addWidget(card)
        main_layout.addStretch()

    def update_theme(self, theme_name):
        self.current_theme = theme_name
        theme = get_theme(theme_name)
        self.card.setStyleSheet(f"""
            QLabel#CreateTitle {{
                color: {theme['text']};
                font-size: 32px;
                font-weight: 900;
            }}
            QLabel#SectionTitle {{
                color: {theme['accent']};
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 1px;
                text-transform: uppercase;
                padding: 0 10px;
            }}
            QFrame#SectionLine {{
                background-color: {rgba(theme['border'], 0.5)};
                min-height: 1px;
                max-height: 1px;
            }}
            QLabel#BlockSubtitle {{
                color: {theme['sub']};
                font-size: 11px;
            }}
        """)

    def handle_create_account(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm = self.confirm_input.text()
        server_url = self.server_input.text().strip() or get_base_url()

        if not username or not password or not confirm:
            QMessageBox.warning(self, "Registration Error", "Please complete all fields before continuing.")
            return

        if password != confirm:
            QMessageBox.warning(self, "Registration Error", "Passwords do not match.")
            return

        if len(password) < 6:
            QMessageBox.warning(self, "Registration Error", "Password must be at least 6 characters long.")
            return

        try:
            set_base_url(server_url)
            api_register(username, password)
            self.account_created.emit()
        except ApiError as e:
            QMessageBox.warning(self, "Registration Error", str(e))

class LoginPage(QWidget):
    login_successful = pyqtSignal(int)  # Signal emitted with user_id when login succeeds

    def __init__(self):
        super().__init__()
        self.user_id = None
        self.init_ui()

    def init_ui(self):
        # Main layout with gradient background
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setSpacing(22)
        main_layout.setContentsMargins(40, 36, 40, 36)

        # Welcome section with icon
        welcome_layout = QVBoxLayout()
        welcome_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.setSpacing(10)

        # Title with gradient text effect
        title = QLabel("Welcome to ProdSmart")
        title.setObjectName("LoginTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont(FONT_FAMILY, 22, QFont.Weight.Bold)
        title.setFont(title_font)
        welcome_layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Your productivity companion")
        subtitle.setObjectName("LoginSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_font = QFont(FONT_FAMILY, 11)
        subtitle.setFont(subtitle_font)
        welcome_layout.addWidget(subtitle)

        main_layout.addLayout(welcome_layout)

        self.stack = QStackedLayout()
        self.login_view = QWidget()
        login_wrapper = QVBoxLayout(self.login_view)
        login_wrapper.setContentsMargins(0, 0, 0, 0)
        login_wrapper.setSpacing(0)

        # Login form container with modern card design
        form_card = QFrame()
        form_card.setObjectName("LoginCard")
        form_card.setFixedWidth(580)
        
        # Add shadow effect to the card
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 4)
        form_card.setGraphicsEffect(shadow)
        
        form_layout = QVBoxLayout(form_card)
        form_layout.setSpacing(14)
        form_layout.setContentsMargins(44, 38, 44, 36)

        card_title = QLabel("LOGIN TO YOUR ACCOUNT")
        card_title.setObjectName("LoginCardTitle")
        card_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_title_font = QFont(FONT_FAMILY, 18, QFont.Weight.Bold)
        card_title.setFont(card_title_font)
        form_layout.addWidget(card_title)

        # Username field
        input_height = 54

        def section_header(label_text):
            header = QHBoxLayout()
            header.setContentsMargins(0, 0, 0, 0)
            header.setSpacing(10)

            left_line = QFrame()
            left_line.setObjectName("SectionLine")
            left_line.setFrameShape(QFrame.Shape.HLine)
            left_line.setFrameShadow(QFrame.Shadow.Plain)
            left_line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            header.addWidget(left_line)

            section_label = QLabel(label_text)
            section_label.setObjectName("SectionTitle")
            section_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.addWidget(section_label)

            right_line = QFrame()
            right_line.setObjectName("SectionLine")
            right_line.setFrameShape(QFrame.Shape.HLine)
            right_line.setFrameShadow(QFrame.Shadow.Plain)
            right_line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            header.addWidget(right_line)

            return header

        def field_block(label_text, placeholder, is_password=False):
            block = QVBoxLayout()
            block.setSpacing(8)
            block.addLayout(section_header(label_text))

            field = QLineEdit()
            field.setObjectName("LoginInput")
            field.setPlaceholderText(placeholder)
            field.setFixedHeight(input_height)
            if is_password:
                field.setEchoMode(QLineEdit.EchoMode.Password)
            block.addWidget(field)
            return block, field

        username_block, self.username_input = field_block("Username", "Enter your username")
        form_layout.addLayout(username_block)

        password_block, self.password_input = field_block("Password", "Enter your password", is_password=True)
        form_layout.addLayout(password_block)

        server_block = QVBoxLayout()
        server_block.setSpacing(8)
        server_block.addLayout(section_header("Server URL"))

        server_row = QHBoxLayout()
        server_row.setSpacing(12)

        self.server_input = QLineEdit()
        self.server_input.setObjectName("LoginInput")
        self.server_input.setPlaceholderText("http://127.0.0.1:8000")
        self.server_input.setFixedHeight(input_height)
        try:
            self.server_input.setText(get_base_url())
        except Exception:
            pass
        server_row.addWidget(self.server_input, 1)

        self.start_server_button = AnimatedButton("Start Server", primary=False)
        self.start_server_button.setFixedHeight(input_height)
        self.start_server_button.setMinimumWidth(140)
        self.start_server_button.clicked.connect(self.start_cloud_server)
        self.start_server_button.setGraphicsEffect(None)
        server_row.addWidget(self.start_server_button)

        server_block.addLayout(server_row)
        form_layout.addLayout(server_block)

        self.server_status = QLabel("Server: not running")
        self.server_status.setObjectName("LoginSubtitle")
        self.server_status.setContentsMargins(2, 0, 0, 0)
        form_layout.addWidget(self.server_status)

        # Remember me checkbox with better styling
        self.remember_checkbox = QCheckBox("Remember me")
        self.remember_checkbox.setObjectName("LoginCheckbox")
        form_layout.addWidget(self.remember_checkbox)

        # Buttons layout with modern buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(16)

        self.login_button = AnimatedButton("Login", primary=True)
        self.login_button.clicked.connect(self.handle_login)
        self.login_button.setFixedHeight(44)
        self.login_button.setMinimumWidth(170)
        buttons_layout.addWidget(self.login_button)

        self.register_button = AnimatedButton("Create Account", primary=False)
        self.register_button.clicked.connect(self.handle_register)
        self.register_button.setFixedHeight(44)
        self.register_button.setMinimumWidth(170)
        buttons_layout.addWidget(self.register_button)

        form_layout.addLayout(buttons_layout)

        login_wrapper.addWidget(form_card, alignment=Qt.AlignmentFlag.AlignCenter)
        login_wrapper.addStretch()

        self.register_view = CreateAccountPage()
        self.register_view.account_created.connect(self.on_registration_success)
        self.register_view.cancel_requested.connect(self.show_login_page)

        self.stack.addWidget(self.login_view)
        self.stack.addWidget(self.register_view)
        main_layout.addLayout(self.stack)
        main_layout.addStretch()

        # Connect enter key to login
        self.username_input.returnPressed.connect(self.handle_login)
        self.password_input.returnPressed.connect(self.handle_login)
        self.server_input.returnPressed.connect(self.handle_login)

    def update_theme(self, theme_name):
        """Update the theme of the login page"""
        self.current_theme = theme_name
        if hasattr(self, "register_view"):
            self.register_view.update_theme(theme_name)
        self.update()  # Trigger repaint for gradient background

    def _is_local_url(self, url):
        try:
            parsed = urlparse(url)
            host = parsed.hostname or ""
            return host in ("127.0.0.1", "localhost")
        except Exception:
            return False

    def start_cloud_server(self):
        server_url = self.server_input.text().strip() if hasattr(self, "server_input") else ""
        if not server_url:
            server_url = "http://127.0.0.1:8000"

        if not self._is_local_url(server_url):
            QMessageBox.information(
                self,
                "Server URL",
                "This URL points to another machine. Start the server on that machine, or use 127.0.0.1 here."
            )
            return

        try:
            set_base_url(server_url)
        except Exception:
            pass

        try:
            api_ping()
            if hasattr(self, "server_status"):
                self.server_status.setText("Server: running")
            QMessageBox.information(self, "Server", "Server is already running.")
            return
        except ApiError:
            pass
        except Exception:
            # Timeout or network error: treat as not running and try starting locally.
            if hasattr(self, "server_status"):
                self.server_status.setText("Server: not reachable")

        server_path = os.path.join(os.getcwd(), "server", "main.py")
        if not os.path.exists(server_path):
            QMessageBox.warning(self, "Server", "Server entrypoint not found (server/main.py).")
            return

        creationflags = 0
        if os.name == "nt":
            try:
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            except Exception:
                creationflags = 0

        try:
            subprocess.Popen(
                [sys.executable, server_path],
                cwd=os.getcwd(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            if hasattr(self, "server_status"):
                self.server_status.setText("Server: starting...")
            QMessageBox.information(self, "Server", "Server started. Try login again in a few seconds.")
        except Exception as e:
            QMessageBox.warning(self, "Server", f"Could not start server: {e}")

    def paintEvent(self, event):
        """Custom paint event to draw gradient background"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Create gradient background
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        theme = get_theme(self.current_theme if hasattr(self, 'current_theme') else "Dark")
        
        gradient.setColorAt(0.0, QColor(theme["bg"]))
        gradient.setColorAt(0.5, QColor(theme["card_alt"]))
        gradient.setColorAt(1.0, QColor(theme["deep"]))
        
        painter.fillRect(self.rect(), gradient)
        painter.end()
        
        super().paintEvent(event)

    def handle_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        server_url = self.server_input.text().strip() or get_base_url()

        if not username or not password:
            QMessageBox.warning(self, "Login Error", "Please enter both username and password.")
            return

        try:
            set_base_url(server_url)
            res = api_login(username, password)
            user_id = res.get("user_id") if isinstance(res, dict) else None
            if user_id:
                self.user_id = user_id
                self.login_successful.emit(user_id)
                return
            QMessageBox.warning(self, "Login Failed", "Invalid username or password.")
        except ApiError as e:
            QMessageBox.warning(self, "Login Failed", str(e))

    def handle_register(self):
        self.show_registration_page()

    def show_registration_page(self):
        self.stack.setCurrentWidget(self.register_view)

    def show_login_page(self):
        self.stack.setCurrentWidget(self.login_view)
        self.username_input.clear()
        self.password_input.clear()

    def on_registration_success(self):
        QMessageBox.information(self, "Success", "Account created successfully! You can now log in.")
        self.show_login_page()
