from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QMessageBox, QCheckBox, QGraphicsDropShadowEffect,
    QStackedLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QFont, QPainter, QColor, QLinearGradient, QPixmap, QIcon
from database.db_manager import authenticate_user, create_user
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
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 50))
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
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(24, 24, 24, 24)

        card = QFrame()
        card.setObjectName("LoginCard")
        card.setFixedWidth(440)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 6)
        card.setGraphicsEffect(shadow)

        theme = get_theme("Dark")
        card.setStyleSheet(f"""
            QLabel#CreateTitle {{
                color: white;
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

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(20)
        card_layout.setContentsMargins(34, 42, 34, 34)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(16)
        header_layout.setContentsMargins(0, 24, 0, 16)

        title = QLabel("Create your account")
        title.setObjectName("CreateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont(FONT_FAMILY, 30, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setWordWrap(True)
        header_layout.addWidget(title)

        subtitle = QLabel("Just three steps to a beautiful ProdSmart account: username, password and confirmation.")
        subtitle.setObjectName("LoginSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle_font = QFont(FONT_FAMILY, 11)
        subtitle.setFont(subtitle_font)
        header_layout.addWidget(subtitle)

        card_layout.addLayout(header_layout)

        def field_block(label_text, placeholder=""):
            block = QVBoxLayout()
            block.setSpacing(8)
            block.setContentsMargins(0, 0, 0, 18)

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
            field.setMinimumHeight(44)
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

    def handle_create_account(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm = self.confirm_input.text()

        if not username or not password or not confirm:
            QMessageBox.warning(self, "Registration Error", "Please complete all fields before continuing.")
            return

        if password != confirm:
            QMessageBox.warning(self, "Registration Error", "Passwords do not match.")
            return

        if len(password) < 6:
            QMessageBox.warning(self, "Registration Error", "Password must be at least 6 characters long.")
            return

        if create_user(username, password, None, None):
            self.account_created.emit()
        else:
            QMessageBox.warning(self, "Registration Error", "Username already exists. Please choose a different username.")

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
        main_layout.setSpacing(30)
        main_layout.setContentsMargins(50, 50, 50, 50)

        # Welcome section with icon
        welcome_layout = QVBoxLayout()
        welcome_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.setSpacing(15)

        # App icon/logo placeholder (you can add an actual icon later)
        icon_label = QLabel("🚀")
        icon_label.setObjectName("AppIcon")
        icon_font = QFont(FONT_FAMILY, 48)
        icon_label.setFont(icon_font)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(icon_label)

        # Title with gradient text effect
        title = QLabel("Welcome to ProdSmart")
        title.setObjectName("LoginTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont(FONT_FAMILY, 28, QFont.Weight.Bold)
        title.setFont(title_font)
        welcome_layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Your productivity companion")
        subtitle.setObjectName("LoginSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_font = QFont(FONT_FAMILY, 14)
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
        form_card.setFixedWidth(400)
        
        # Add shadow effect to the card
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 4)
        form_card.setGraphicsEffect(shadow)
        
        form_layout = QVBoxLayout(form_card)
        form_layout.setSpacing(20)
        form_layout.setContentsMargins(40, 40, 40, 40)

        # Username field with icon
        username_layout = QVBoxLayout()
        username_layout.setSpacing(8)
        
        username_label = QLabel("Username")
        username_label.setObjectName("FieldLabel")
        username_label_font = QFont(FONT_FAMILY, 12, QFont.Weight.Bold)
        username_label.setFont(username_label_font)
        username_layout.addWidget(username_label)
        
        username_input_layout = QHBoxLayout()
        username_input_layout.setContentsMargins(0, 0, 0, 0)
        
        # Username icon
        user_icon = QLabel("👤")
        user_icon.setObjectName("FieldIcon")
        user_icon.setFixedSize(20, 20)
        username_input_layout.addWidget(user_icon)
        
        self.username_input = QLineEdit()
        self.username_input.setObjectName("LoginInput")
        self.username_input.setPlaceholderText("Enter your username")
        username_input_layout.addWidget(self.username_input)
        
        username_layout.addLayout(username_input_layout)
        form_layout.addLayout(username_layout)

        # Password field with icon
        password_layout = QVBoxLayout()
        password_layout.setSpacing(8)
        
        password_label = QLabel("Password")
        password_label.setObjectName("FieldLabel")
        password_label.setFont(username_label_font)
        password_layout.addWidget(password_label)
        
        password_input_layout = QHBoxLayout()
        password_input_layout.setContentsMargins(0, 0, 0, 0)
        
        # Password icon
        pass_icon = QLabel("🔒")
        pass_icon.setObjectName("FieldIcon")
        pass_icon.setFixedSize(20, 20)
        password_input_layout.addWidget(pass_icon)
        
        self.password_input = QLineEdit()
        self.password_input.setObjectName("LoginInput")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Enter your password")
        password_input_layout.addWidget(self.password_input)
        
        password_layout.addLayout(password_input_layout)
        form_layout.addLayout(password_layout)

        # Remember me checkbox with better styling
        self.remember_checkbox = QCheckBox("Remember me")
        self.remember_checkbox.setObjectName("LoginCheckbox")
        form_layout.addWidget(self.remember_checkbox)

        # Buttons layout with modern buttons
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(12)

        self.login_button = AnimatedButton("Login", primary=True)
        self.login_button.clicked.connect(self.handle_login)
        buttons_layout.addWidget(self.login_button)

        self.register_button = AnimatedButton("Create Account", primary=False)
        self.register_button.clicked.connect(self.handle_register)
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

    def update_theme(self, theme_name):
        """Update the theme of the login page"""
        self.current_theme = theme_name
        self.update()  # Trigger repaint for gradient background

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

        if not username or not password:
            QMessageBox.warning(self, "Login Error", "Please enter both username and password.")
            return

        user_id = authenticate_user(username, password)
        if user_id:
            self.user_id = user_id
            self.login_successful.emit(user_id)
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password.")

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