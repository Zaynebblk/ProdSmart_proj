from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout
from PyQt6.QtCore import Qt

class AICard(QFrame):
    def __init__(self, title, desc, icon_color):
        super().__init__()
        self.setStyleSheet(f"background-color: white; border-radius: 12px; border: 1px solid #edf2f7;")
        self.setFixedHeight(100)
        layout = QHBoxLayout(self)
        
        icon_circle = QFrame()
        icon_circle.setFixedSize(45, 45)
        icon_circle.setStyleSheet(f"background-color: {icon_color}; border-radius: 22px; border: none;")
        
        text_layout = QVBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-weight: bold; font-size: 15px; border: none; color: #2d3748;")
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet("color: #718096; border: none; font-size: 13px;")
        
        text_layout.addWidget(title_lbl)
        text_layout.addWidget(desc_lbl)
        
        layout.addWidget(icon_circle)
        layout.addLayout(text_layout)
        layout.addStretch()

class AIAnalysisPage(QWidget): # <--- Vérifie bien ce nom !
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #f7fafc;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        
        header = QLabel("Productivity Dashboard")
        header.setStyleSheet("font-size: 26px; font-weight: bold; color: #1a202c; margin-bottom: 20px;")
        layout.addWidget(header)
        
        # On recrée les cartes de ton image image_1ee606
        layout.addWidget(AICard("Best Productivity Period", "Your peak performance is between 9am - 11am.", "#9b59b6"))
        layout.addWidget(AICard("Task Completion Pattern", "You complete 30% more tasks on weekdays.", "#3498db"))
        layout.addWidget(AICard("Focus Recommendation", "Your average focus session is 22 minutes.", "#f1c40f"))
        
        layout.addStretch()