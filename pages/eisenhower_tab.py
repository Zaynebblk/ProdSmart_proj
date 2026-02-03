from PyQt6.QtWidgets import (QWidget, QGridLayout, QVBoxLayout, QLabel, 
                             QFrame, QPushButton, QScrollArea)
from PyQt6.QtCore import Qt
import sqlite3

class TaskCard(QFrame):
    """Petite carte blanche pour chaque tâche"""
    def __init__(self, title):
        super().__init__()
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
                padding: 10px;
                margin-bottom: 5px;
            }
        """)
        layout = QVBoxLayout(self)
        label = QLabel(title)
        label.setWordWrap(True) # Important pour les titres longs
        label.setStyleSheet("border: none; color: #333; font-size: 13px;")
        layout.addWidget(label)

class Quadrant(QFrame):
    def __init__(self, title, subtitle, color, border_color):
        super().__init__()
        # Style moderne : fond pastel, bordure fine
        self.setStyleSheet(f"""
            QFrame#QuadrantFrame {{
                background-color: {color};
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
        """)
        self.setObjectName("QuadrantFrame")
        
        layout = QVBoxLayout(self)
        
        # Titre et Sous-titre
        header_layout = QVBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-weight: bold; font-size: 16px; border: none; color: #2c3e50;")
        
        sub_lbl = QLabel(subtitle)
        sub_lbl.setStyleSheet("font-size: 11px; border: none; color: #7f8c8d;")
        
        header_layout.addWidget(title_lbl)
        header_layout.addWidget(sub_lbl)
        layout.addLayout(header_layout)

        # Zone de défilement pour les tâches
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")

        self.tasks_container = QWidget()
        self.tasks_container.setStyleSheet("background: transparent; border: none;")
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.tasks_container)
        layout.addWidget(self.scroll_area)

    def add_task(self, title):
        card = TaskCard(title)
        self.tasks_layout.addWidget(card)

    def clear_tasks(self):
        # On vide la liste pour éviter les doublons lors du rafraîchissement
        while self.tasks_layout.count():
            item = self.tasks_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

class EisenhowerMatrix(QWidget):
    def __init__(self):
        super().__init__()
        layout = QGridLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Création des quadrants
        self.q1 = Quadrant("Urgent & Important", "Do First", "#fff5f5", "#feb2b2")
        self.q2 = Quadrant("Important & Not Urgent", "Schedule", "#f0fff4", "#9ae6b4")
        self.q3 = Quadrant("Urgent & Not Important", "Delegate", "#fffaf0", "#fbd38d")
        self.q4 = Quadrant("Not Urgent & Not Important", "Eliminate", "#f7fafc", "#edf2f7")

        layout.addWidget(self.q1, 0, 0)
        layout.addWidget(self.q2, 0, 1)
        layout.addWidget(self.q3, 1, 0)
        layout.addWidget(self.q4, 1, 1)

        # Premier chargement
        self.refresh_matrix()

    def showEvent(self, event):
        """MAGIE : Cette fonction se lance dès qu'on clique sur l'onglet"""
        self.refresh_matrix()
        super().showEvent(event)

    def refresh_matrix(self):
        """Récupère les données de la base et remplit les cases"""
        # 1. Vider les cases
        self.q1.clear_tasks()
        self.q2.clear_tasks()
        self.q3.clear_tasks()
        self.q4.clear_tasks()

        # 2. Lire la base de données
        conn = sqlite3.connect("prodsmart.db")
        cursor = conn.cursor()
        
        # On vérifie si la table existe (pour éviter une erreur au premier lancement)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
        if not cursor.fetchone():
            conn.close()
            return

        cursor.execute("SELECT title, is_urgent, is_important FROM tasks")
        rows = cursor.fetchall()
        conn.close()

        # 3. Trier dans les cases
        for row in rows:
            title = row[0]
            urgent = row[1]
            important = row[2]

            if urgent and important:
                self.q1.add_task(title)   # Rouge
            elif not urgent and important:
                self.q2.add_task(title)   # Vert
            elif urgent and not important:
                self.q3.add_task(title)   # Jaune
            else:
                self.q4.add_task(title)   # Gris