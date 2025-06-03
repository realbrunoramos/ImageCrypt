import sys
import zipfile
from pathlib import Path
from PIL import Image as PILImage
from PySide6.QtWidgets import QGridLayout, QFileDialog, QLineEdit, QStackedWidget, QMessageBox, QSplashScreen, \
    QApplication, QLabel, QPushButton, QVBoxLayout, QWidget, QScrollArea, QSizePolicy, QHBoxLayout
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QBrush, QPainterPath, QMovie
from PySide6.QtCore import Qt, QTimer, Signal, QThread
import sqlite3
from datetime import datetime
import hashlib
import base64
from tkinter import messagebox
import secrets
import string
import os
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from collections import deque
from difflib import SequenceMatcher

def inner_path(relative):
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.abspath("."), relative)

class PathSearcher:
    def __init__(self, img_name):
        self.found_paths = multiprocessing.Manager().list()
        self.img_name = img_name.lower()
        self.max_results = 6
        self.search_image()

    def search_image(self):
        start_dirs = [
            os.path.expanduser("~/Desktop"),
            os.path.expanduser("~/Pictures"),
            os.path.expanduser("~/Documents"),
            os.path.expanduser("~/Photos"),
            os.path.expanduser("~/Downloads")
        ]

        with ProcessPoolExecutor() as executor:
            executor.map(self._search_in_directory, start_dirs)

    def _search_in_directory(self, root_dir):
        queue = deque([root_dir])

        while queue and len(self.found_paths) < self.max_results:  # Interrompe quando 6 resultados são encontrados
            current_dir = queue.popleft()
            try:
                with os.scandir(current_dir) as entries:
                    for entry in entries:
                        if entry.is_file():
                            name, ext = os.path.splitext(entry.name.lower())
                            if ext in {".jpg", ".jpeg", ".png", ".svg", ".bmp"}:
                                similarity = self._calculate_similarity(name)  # Calcula a similaridade
                                if similarity > 0.5:  # Adiciona à lista de resultados se a similaridade for suficientemente alta
                                    self.found_paths.append((similarity, entry.path))  # Guarda também a similaridade
                        elif entry.is_dir():
                            queue.append(entry.path)
            except (PermissionError, FileNotFoundError):
                continue

    def _calculate_similarity(self, file_name):
        return SequenceMatcher(None, file_name, self.img_name).ratio()

    def get_paths(self):
        sorted_paths = sorted(self.found_paths, key=lambda x: x[0], reverse=True)
        return [path for _, path in sorted_paths[:self.max_results]]

program_data_dir = os.path.join(os.environ['PROGRAMDATA'], "ImageCrypt")
os.makedirs(program_data_dir, exist_ok=True)
db_path = os.path.join(program_data_dir, "imagecrypt.db")

screen0 = inner_path("bg.svg")
screen1 = inner_path("bg2.svg")
screen2 = inner_path("bg3.svg")

eye0 = inner_path("eye0.png")
eye1 = inner_path("eye1.png")

ic_splash_img = inner_path("ic_splash.png")
searching_ic = inner_path("Searching IC.gif")

icon_ic = inner_path("iconIC.ico")

def generate_key(tamanho=16):
    caracteres = string.ascii_letters + string.digits
    return ''.join(secrets.choice(caracteres) for _ in range(tamanho))

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    db_conn = sqlite3.connect(db_path)
    cursor = db_conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vault (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vault_name TEXT NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL,
            encryption_key TEXT,
            last_login TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS image (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vault_id INTEGER NOT NULL,
            image_name TEXT NOT NULL,
            image_crypt_key TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_accessed TEXT,
            FOREIGN KEY (vault_id) REFERENCES vault (id)
        )
    """)

    db_conn.commit()
    db_conn.close()

def create_vault(hashed_password, vault_name):
    created_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    cv_db_conn = sqlite3.connect(db_path)
    cursor = cv_db_conn.cursor()
    encryption_key = generate_key()

    cursor.execute("""
        INSERT INTO vault (password, created_at, vault_name, encryption_key) 
        VALUES (?, ?, ?, ?)
    """, (hashed_password, created_at, vault_name, encryption_key))
    cv_db_conn.commit()
    cv_db_conn.close()
    messagebox.showinfo("Sucesso", "Cofre criado com sucesso!")

def login_vault(password):
    hashed_password = hash_password(password)
    lv_db_conn = sqlite3.connect(db_path)
    cursor = lv_db_conn.cursor()

    try:
        cursor.execute("SELECT id, vault_name FROM vault WHERE password = ?", (hashed_password,))
        vault = cursor.fetchone()
        if vault:
            vault_id = vault[0]
            vault_name = vault[1]
            atual_login = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            last_login = get_last_login(vault_id)
            lv_db_conn.commit()
            lv_db_conn.close()
            return vault_id, vault_name, last_login, atual_login
        else:
            messagebox.showerror("Erro", "Senha de acesso incorreta ou cofre inexistente.")
    except Exception as e:
        messagebox.showerror("Erro", f"Erro no login: {str(e)}")
        return None
    finally:
        lv_db_conn.close()

def get_last_login(vault_id):
    ll_db_conn = sqlite3.connect(db_path)
    cursor = ll_db_conn.cursor()
    cursor.execute("SELECT last_login FROM vault WHERE id = ?", (vault_id,))
    last_login_c = cursor.fetchone()
    if last_login_c:
        return last_login_c[0]
    return None

def get_vault_images(vault_id):
    ll_db_conn = sqlite3.connect(db_path)
    cursor = ll_db_conn.cursor()

    cursor.execute("SELECT id, image_name, created_at FROM image WHERE vault_id = ?", (vault_id,))
    result_c = cursor.fetchall()
    ll_db_conn.close()
    if not result_c:
        return None
    return {row[0]: list(row[1:]) for row in result_c}

def update_last_login(vault_id, last_login):
    ll_db_conn = sqlite3.connect(db_path)
    cursor = ll_db_conn.cursor()
    cursor.execute("""
                    UPDATE vault 
                    SET last_login = ?
                    WHERE id = ?
                """, (last_login, vault_id))
    ll_db_conn.commit()
    ll_db_conn.close()
    return True

def verify_if_vault_password_exists(hashed_password):
    vve_db_conn = sqlite3.connect(db_path)
    cursor = vve_db_conn.cursor()
    try:
        cursor.execute("SELECT id FROM vault WHERE password = ?", (hashed_password,))
        vault = cursor.fetchone()
        if vault:
            messagebox.showerror("Crie outra senha", "Já existe cofre com a mesma senha de acesso.")
            return True
        else:
            return False
    except Exception as e:
        messagebox.showerror("Erro", f"Base de dados alterada: {str(e)}")
        return None
    finally:
        vve_db_conn.close()

def encode_image(vault_id, image_path, img_name=None):
    ei_db_conn = None
    pimage_path = Path(image_path).resolve()

    try:
        with open(pimage_path, "rb") as img_file:
            image_base64 = base64.b64encode(img_file.read()).decode('utf-8')

        image_name = img_name if img_name else pimage_path.stem
        created_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        ei_db_conn = sqlite3.connect(db_path)
        cursor = ei_db_conn.cursor()

        cursor.execute("SELECT encryption_key FROM vault WHERE id = ?", (vault_id,))
        encryption_key = cursor.fetchone()

        image_crypt_key = encryption_key[0] + "" + image_base64

        cursor.execute("""
            INSERT INTO image (vault_id, image_name, image_crypt_key, created_at) 
            VALUES (?, ?, ?, ?)
        """, (vault_id, image_name, image_crypt_key, created_at))

        ei_db_conn.commit()
        messagebox.showinfo("Sucesso", "Imagem codificada com sucesso!")
        return True

    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao codificar a imagem: {str(e)}")
        return False

    finally:
        ei_db_conn.close()

def decode_image(img_id, vault_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
                SELECT image_crypt_key FROM image 
                WHERE vault_id = ? AND id = ?
            """, (vault_id, img_id))
        result_image_key = cursor.fetchone()

        if not result_image_key:
            messagebox.showerror("Erro", "Imagem não encontrada")
            conn.close()
            return None

        image_crypt_key = result_image_key[0]

        cursor.execute("""
                SELECT encryption_key FROM vault 
                WHERE id = ? 
            """, (vault_id,))

        result_vault_key = cursor.fetchone()

        if not result_vault_key:
            messagebox.showerror("Erro", "Cofre não encontrado")
            conn.close()
            return None

        encryption_key = result_vault_key[0]

        if encryption_key in image_crypt_key:
            encoded_image = image_crypt_key.replace(encryption_key, "")
            conn.close()
            return base64.b64decode(encoded_image)
        messagebox.showerror("Erro", "A imagem não pertence ao cofre")
        return None
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao descodificar a imagem: {str(e)}")
        return None
    finally:
        conn.close()

def delete_image_from_db(img_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM image WHERE id = ?", (img_id,))
        conn.commit()
        return True
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao eliminar imagem do cofre: {str(e)}")
        return False
    finally:
        conn.close()

class PopupWindow(QWidget):

    image_clicked = Signal(str)

    def __init__(self, image_list):
        super().__init__()

        self.setFixedSize(400, 400)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(54, 54, 54, 54)

        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(10)

        self.image_list = image_list
        self.add_images_to_grid()

        self.close_button = QPushButton("✕", self)
        self.close_button.setFixedSize(24, 24)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: #FF0000;
                color: white;
                border-radius: 12px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #CC0000;
            }
        """)
        self.close_button.clicked.connect(self.close)

        self.close_button.move(self.width() - 40, 10)

        self.layout.addLayout(self.grid_layout)

    def add_images_to_grid(self):
        row, col = 0, 0
        for image_path in self.image_list:
            image_label = QLabel()
            pixmap = QPixmap(image_path)
            image_label.setPixmap(pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            image_label.setAlignment(Qt.AlignCenter)

            name_label = QLabel(os.path.basename(image_path))
            name_label.setAlignment(Qt.AlignCenter)

            image_widget = QWidget()
            image_layout = QVBoxLayout(image_widget)
            image_layout.setContentsMargins(0, 0, 0, 0)
            image_layout.setSpacing(5)
            image_layout.addWidget(image_label)
            image_layout.addWidget(name_label)
            image_widget.setLayout(image_layout)

            self.grid_layout.addWidget(image_widget, row, col)

            image_widget.mousePressEvent = lambda event, path=image_path: self.on_image_clicked(path)

            col += 1
            if col > 2:
                col = 0
                row += 1

    def on_image_clicked(self, image_path):
        self.image_clicked.emit(image_path)
        self.close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(self.rect(), 20, 20)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 120)))
        painter.drawPath(path)


class Worker(QThread):
    finished = Signal(list)

    def __init__(self, search_term):
        super().__init__()
        self.search_term = search_term

    def run(self):
        image_paths = PathSearcher(self.search_term).get_paths()
        self.finished.emit(image_paths)  # Emite o sinal com os resultados

class MainWindow(QWidget):
    init_db()

    def __init__(self):
        super().__init__()
        self.vault_name = None
        self.vault_id = None
        self.last_login = None
        self.atual_login = None

        self.images_list = {}

        self.pages = QStackedWidget(self)

        self.setWindowTitle("ImageCrypt")
        self.setWindowIcon(QIcon(icon_ic))
        self.setFixedSize(800, 600)

        self.pages = QStackedWidget(self)

        self.login_page = self.show_login_page()
        self.novo_cofre_page = self.show_novo_cofre_page()
        self.lock_image_page = self.show_lock_image_page()
        self.unlock_image_page = self.show_unlock_image_page()

        self.pages.addWidget(self.login_page)
        self.pages.addWidget(self.novo_cofre_page)
        self.pages.addWidget(self.lock_image_page)
        self.pages.addWidget(self.unlock_image_page)

        layout = QVBoxLayout(self)
        layout.addWidget(self.pages)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.pages.setCurrentWidget(self.login_page)

    def closeEvent(self, event):
        update_last_login(self.vault_id, self.atual_login)
        super().closeEvent(event)

    def reload_work_pages(self):
        self.pages.removeWidget(self.lock_image_page)
        self.lock_image_page.deleteLater()
        self.lock_image_page = self.show_lock_image_page()
        self.pages.addWidget(self.lock_image_page)

        self.pages.removeWidget(self.unlock_image_page)
        self.unlock_image_page.deleteLater()
        self.unlock_image_page = self.show_unlock_image_page()
        self.pages.addWidget(self.unlock_image_page)

    ############################# SHOW SCREEN METHODS #############################

    def show_login_page(self):
        page = QWidget()
        svg_widget = QSvgWidget(screen0, page)
        svg_widget.setParent(page)

        #region __________Abrir cofre Label___________
        password_label = QLabel("Abrir o cofre", page)
        password_label.setStyleSheet("""
                QLabel {
                    font-size: 20px;
                    color: white;
                    font-weight: bold; 
                }
            """)
        password_label.setFixedSize(200, 40)
        password_label.move(395, 160)
        #endregion

        #region ::::::::::::::::::::Botão "Entrar"::::::::::::::::::::
        def entrar_action():
            result = login_vault(password_input.text())
            if result:
                password_input.clear()
                self.vault_id, self.vault_name, self.last_login, self.atual_login = result
                self.reload_work_pages()
                self.pages.setCurrentWidget(self.lock_image_page)
            else:
                password_input.clear()

        entrar = QPushButton("Entrar", page)
        entrar.setStyleSheet("""
            QPushButton {
                background-color: #6B1A6F;  
                color: white;  
                border-radius: 10px;  
                padding: 15px 22px; 
                font-size: 16px;
                opacity: 1; 
            }
            QPushButton:hover {
                background-color: #5F0F63; 
            }
        """)
        entrar.setFixedSize(90, 50)
        entrar.move(500, 320)
        entrar.clicked.connect(entrar_action)
        #endregion

        #region ::::::::::::::::::::Input de senha::::::::::::::::::::
        password_input = QLineEdit(page)
        password_input.setEchoMode(QLineEdit.Password)
        password_input.setPlaceholderText("Digite a senha de acesso")
        password_input.setFixedSize(300, 40)
        password_input.move(300, 225)
        password_input.returnPressed.connect(entrar_action)
        #endregion

        #region ::::::::::::::::::::Toggle visibilidade senha::::::::::::::::::::
        def toggle_password_visibility():
            if password_input.echoMode() == QLineEdit.Password:
                password_input.setEchoMode(QLineEdit.Normal)  # Mostra a senha
                toggle_button.setIcon(QIcon(eye0))  # olho aberto
            else:
                password_input.setEchoMode(QLineEdit.Password)  # Oculta a senha
                toggle_button.setIcon(QIcon(eye1))  # olho fechado
        toggle_button = QPushButton(page)
        toggle_button.setIcon(QIcon(eye1))
        toggle_button.setFixedSize(40, 40)
        toggle_button.setStyleSheet("border: none;")
        toggle_button.move(560, 225)
        toggle_button.clicked.connect(toggle_password_visibility)
        #endregion

        #region ::::::::::::::::::::Botão "Novo Cofre"::::::::::::::::::::
        novo_cofre = QPushButton("Novo Cofre", page)
        novo_cofre.setStyleSheet("""
            QPushButton {
                background-color: #0F0F0F;  
                color: white;  
                border-radius: 10px;  
                padding: 15px 22px; 
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #f0f0f0; 
                color: black;
            }
        """)
        novo_cofre.setFixedSize(150, 50)
        novo_cofre.move(300, 320)
        novo_cofre.clicked.connect(lambda: self.pages.setCurrentWidget(self.novo_cofre_page))
        #endregion
        return page

    def show_novo_cofre_page(self):
        page = QWidget()
        svg_widget = QSvgWidget(screen0, page)
        svg_widget.setParent(page)

        def criar_cofre_action():
            password = password_input.text()
            hashed_password = ""
            if len(password) < 8:
                self.show_dialog("Senha Curta", "Adicione mais caracteres", "A senha deve conter pelo menos 8 caracteres.", QMessageBox.Warning, 1)
                password_input.clear()
            else:
                hashed_password = hash_password(password)

            vault_name = vault_name_input.text()
            if not vault_name:
                self.show_dialog("Cofre sem nome", "Nomeie o seu cofre", "É necessário dar um nome ao cofre antes de proceder com o seu registo.", QMessageBox.Warning, 1)

            if vault_name and hashed_password:
                answer = self.show_dialog("Criar Cofre", "Confirme", "Deseja criar o cofre?", QMessageBox.Question, 3)
                if answer == QMessageBox.Yes:
                    already_exists = verify_if_vault_password_exists(hashed_password)
                    if already_exists:
                        password_input.clear()
                    else:
                        create_vault(hashed_password, vault_name)
                        self.pages.setCurrentWidget(self.login_page)
                        password_input.clear()
                        vault_name_input.clear()

        #region _________________novo cofre label_________________
        password_label = QLabel("Criar novo cofre", page)
        password_label.setStyleSheet("""
                        QLabel {
                            font-size: 20px;
                            color: white;
                            font-weight: bold; 
                        }
                    """)
        password_label.setFixedSize(200, 40)
        password_label.move(375, 110)
        #endregion

        #region _________________Advice label_________________
        advice_label = QLabel("Após a criação da sua senha de acesso, não será possível recuperá-la\nem caso de esquecimento.\nRecomendamos que guarde a senha de forma segura ou a memorize,\npois esta medida faz parte dos procedimentos de segurança do sistema.", page)
        advice_label.setStyleSheet("""
                        QLabel {
                            font-size: 10px;
                            color: #909090;
                        }
                    """)
        advice_label.setFixedSize(360, 52)
        advice_label.move(300, 275)
        #endregion

        #region ::::::::::::::::::::Input de nome para novo cofre::::::::::::::::::::
        vault_name_input = QLineEdit(page)
        vault_name_input.setEchoMode(QLineEdit.Normal)
        vault_name_input.setPlaceholderText("Nome do cofre")
        vault_name_input.setFixedSize(300, 40)
        vault_name_input.move(300, 165)
        vault_name_input.returnPressed.connect(criar_cofre_action)
        #endregion

        #region ::::::::::::::::::::Input de senha para novo cofre::::::::::::::::::::
        password_input = QLineEdit(page)
        password_input.setEchoMode(QLineEdit.Password)
        password_input.setPlaceholderText("Crie uma senha de acesso")
        password_input.setFixedSize(300, 40)
        password_input.move(300, 225)
        password_input.returnPressed.connect(criar_cofre_action)
        #endregion

        #region ::::::::::::::::::::Toggle visibilidade senha::::::::::::::::::::
        def toggle_password_visibility():
            if password_input.echoMode() == QLineEdit.Password:
                password_input.setEchoMode(QLineEdit.Normal)
                toggle_button.setIcon(QIcon(eye0))
            else:
                password_input.setEchoMode(QLineEdit.Password)
                toggle_button.setIcon(QIcon(eye1))

        toggle_button = QPushButton(page)
        toggle_button.setIcon(QIcon(eye1))
        toggle_button.setFixedSize(40, 40)
        toggle_button.setStyleSheet("border: none;")
        toggle_button.move(560, 225)
        toggle_button.clicked.connect(toggle_password_visibility)
        #endregion

        #region ::::::::::::::::::::Botão "Criar Cofre"::::::::::::::::::::
        criar_cofre = QPushButton("Criar Cofre", page)
        criar_cofre.setStyleSheet("""
            QPushButton {
                background-color: #6B1A6F;  
                color: white;  
                border-radius: 10px;  
                padding: 15px 22px; 
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #5F0F63; 
            }
        """)
        criar_cofre.setFixedSize(120, 50)
        criar_cofre.move(500, 340)
        criar_cofre.clicked.connect(lambda: criar_cofre_action())
        #endregion

        #region ::::::::::::::::::::Botão "Voltar"::::::::::::::::::::
        voltar = QPushButton("Voltar", page)
        voltar.setStyleSheet("""
            QPushButton {
                background-color: #0F0F0F;  
                color: white;  
                border-radius: 10px;  
                padding: 15px 22px; 
                font-size: 16px;
                opacity: 1; 
            }
            QPushButton:hover {
                background-color: #f0f0f0; 
                color: black;
            }
        """)
        voltar.setFixedSize(90, 50)
        voltar.move(300, 340)
        voltar.clicked.connect(lambda: self.pages.setCurrentWidget(self.login_page))
        #endregion
        return page

    def show_lock_image_page(self):
        page = QWidget()
        svg_widget = QSvgWidget(screen1, page)
        svg_widget.setParent(page)
        page.image_path_selected = None

        page.loading_label = QLabel(page)
        page.loading_label.setAlignment(Qt.AlignCenter)

        page.movie = QMovie(searching_ic)
        page.loading_label.setMovie(page.movie)

        page.loading_label.setStyleSheet("""
            QLabel {
                background: transparent;
                border: none;
            }
        """)

        gif_width = 500
        gif_height = 500
        page.loading_label.setFixedSize(gif_width, gif_height)
        page.loading_label.move(
            (self.width() - gif_width) // 2,
            (self.height() - gif_height) // 2
        )

        page.loading_label.hide()

        def on_image_selected(image_path):
            page.image_path_selected = image_path
            img = PILImage.open(image_path)
            size = 338
            img = img.resize((size, size), PILImage.Resampling.LANCZOS)
            pimage_path = Path(image_path)

            if not image_rename.text():
                image_rename.setText(pimage_path.stem)

            img.save("temp_resized_image.png", format="PNG")

            page.imgb.setStyleSheet(f"""
                QPushButton {{
                    background-image: url(temp_resized_image.png);
                    background-repeat: no-repeat;
                    background-position: center;
                    width: {size}px;
                    height: {size}px;
                    border: none;
                    border-radius: 20px;
                    outline: none;
                }}
            """)

            page.imgb.setFixedSize(size, size)
            page.imgb.move(164, 230)

            page.imgb_close.setVisible(True)
            trancar.setStyleSheet("""
                QPushButton {
                    border-radius: 10px;
                    background-color: #6B1A6F; 
                    font-size: 10px;               
                    outline: none;
                    color: white;
                }
            """)
            os.remove("temp_resized_image.png")

        def pesquisa_action():
            search_term = deep_search.text()
            if search_term:
                page.loading_label.show()
                page.movie.start()

                # Crie a thread Worker e conecte o sinal finished à função on_search_finished
                page.worker = Worker(search_term)
                page.worker.finished.connect(on_search_finished)
                page.worker.start()
            else:
                QMessageBox.information(self, "Campo vazio", "Escreva antes o nome da imagem que quer procurar.")

        def on_search_finished(image_paths):
            # Oculta o GIF de loading
            page.movie.stop()
            page.loading_label.hide()

            if image_paths:
                # Exibe o popup com as imagens encontradas
                popup = PopupWindow(image_paths)
                popup.image_clicked.connect(lambda path: on_image_selected(path))
                popup.move(self.geometry().center() - popup.rect().center())
                popup.show()
            else:
                QMessageBox.information(self, "Inexistente", "Nenhuma imagem com nome parecido foi encontrada!")

        # region _____________login details_____________
        vault_name_label = QLabel(f"Cofre: {self.vault_name}", page)
        vault_name_label.setStyleSheet("""
                        QLabel {
                            font-size: 18px;
                            color: #534858;
                        }
                    """)
        vault_name_label.setFixedSize(200, 40)
        vault_name_label.move(150, 5)

        last_login_label = QLabel(f"Último acesso: {self.last_login}", page)
        last_login_label.setStyleSheet("""
                        QLabel {
                            font-size: 10px;
                            color: #534858;
                        }
                    """)
        last_login_label.setFixedSize(200, 40)
        last_login_label.move(150, 25)
        # endregion

        # region :::::::::::Botão "sair":::::::::::
        def sair_action():
            update_last_login(self.vault_id, self.atual_login)
            self.pages.setCurrentWidget(self.login_page)

        sair = QPushButton("", page)
        sair.setStyleSheet("""
            QPushButton {
                border-radius: 7px;  
                border: none;
                outline: none;
            }
        """)
        sair.setFixedSize(50, 50)
        sair.move(39, 44)
        sair.clicked.connect(sair_action)
        # endregion

        # region :::::::::::Display selected image:::::::::::
        page.imgb = QPushButton("", page)
        page.imgb.setStyleSheet("""
                                QPushButton {
                                    background-repeat: no-repeat;
                                    background-position: center;
                                    width: 150px;
                                    height: 150px;
                                    border: none;
                                    outline: none;
                                }
                            """)
        page.imgb.setFixedSize(40, 40)
        page.imgb.move(340, 400)

        page.imgb_close = QPushButton("✕", page)
        page.imgb_close.setStyleSheet("""
            QPushButton {
                background-color: #282734;
                color: white;
                border-radius: 12px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5A5966;
            }
        """)
        page.imgb_close.setFixedSize(24, 24)
        page.imgb_close.move(508, 230)
        page.imgb_close.setVisible(False)

        def remove_imgb_img():
            image_rename.clear()
            trancar.setStyleSheet("""
                QPushButton {
                    border-radius: 10px;
                    background-color: #8D8D8D; 
                    font-size: 10px;      
                    color: black;         
                    outline: none;
                }
            """)
            image_rename.clear()
            page.image_path_selected = None
            page.imgb.setStyleSheet("""
                QPushButton {
                    background: none;
                    border: none;
                    outline: none;
                }
            """)
            page.imgb_close.setVisible(False)

        page.imgb_close.clicked.connect(remove_imgb_img)
        # endregion

        # region :::::::::::Input de pesquisa profunda:::::::::::
        deep_search = QLineEdit(page)
        deep_search.setEchoMode(QLineEdit.Normal)
        deep_search.setPlaceholderText("Escreva o nome da imagem")
        deep_search.setStyleSheet("""
            QLineEdit {
                border: black; 
                outline: none;
                color: black;
                background-color: transparent 
            }
        """)
        deep_search.setFixedSize(230, 32)
        deep_search.move(180, 148)
        deep_search.returnPressed.connect(pesquisa_action)
        # endregion

        # region :::::::::::Input de renomear imagem:::::::::::
        image_rename = QLineEdit(page)
        image_rename.setEchoMode(QLineEdit.Normal)
        image_rename.setPlaceholderText("Renomear a imagem para trancar")
        image_rename.setStyleSheet("""
            QLineEdit {
                border-radius: 16px;
                padding: 5px;
                font-size: 10px;
            }
        """)
        image_rename.setFixedSize(180, 32)
        image_rename.move(570, 325)
        image_rename.returnPressed.connect(pesquisa_action)
        # endregion

        # region :::::::::::Botão "pesquisa":::::::::::
        pesquisa = QPushButton("", page)
        pesquisa.setStyleSheet("""
            QPushButton {
                border-radius: 20px;
                outline: none;
            }
        """)
        pesquisa.setFixedSize(40, 40)
        pesquisa.move(420, 147)
        pesquisa.clicked.connect(pesquisa_action)
        # endregion

        # region :::::::::::Toggle "Apagar na origem":::::::::::
        page.posx_ano = 582
        page.posy_ano = 281
        page.w_ano = 40
        page.h_ano = int(round(page.w_ano / 2))
        page.margin = int(round(page.w_ano * 0.06))
        page.wh_anoc = page.h_ano - page.margin
        page.color_off = "#8D8D8D"
        page.color_on = "#6B1A6F"

        # description toggle
        ano_label = QLabel("Apagar imagem original\ndo computador", page)
        ano_label.setStyleSheet("""
                        QLabel {
                            font-size: 9px;
                            color: white;
                        }
                    """)
        ano_label.setFixedSize(100, 20)
        ano_label.move(page.posx_ano + round(page.w_ano * 3 / 2), page.posy_ano - 4)

        # Toggle principal (fundo)
        ano_bar = QPushButton("", page)
        ano_bar.setFixedSize(page.w_ano, page.h_ano)
        ano_bar.move(page.posx_ano, page.posy_ano)
        ano_bar.setStyleSheet(f"""
                QPushButton {{
                  width: {page.w_ano}px;
                  height: {page.h_ano}px;
                  border-radius: {page.h_ano // 2}px;
                  background-color: {page.color_on};
                }}
            """)

        # Botão pequeno (círculo deslizante)
        ano_circle = QPushButton("", page)
        ano_circle.setFixedSize(page.wh_anoc, page.wh_anoc)
        ano_circle.setStyleSheet(f"""
                QPushButton {{
                  width: {page.wh_anoc}px;
                  height: {page.wh_anoc}px;
                  border-radius: {page.wh_anoc // 2}px;
                  background-color: white;
                }}
            """)
        ano_circle.move(page.posx_ano + page.w_ano - page.wh_anoc, page.posy_ano)
        page.toggle_state = True

        def toggle_button():
            if page.toggle_state:
                ano_circle.move(page.posx_ano, page.posy_ano)
                ano_bar.setStyleSheet(f"""
                        QPushButton {{
                          width: {page.w_ano}px;
                          height: {page.h_ano}px;
                          border-radius: {page.h_ano // 2}px;
                          background-color: {page.color_off};
                        }}
                    """)
            else:
                ano_circle.move(page.posx_ano + page.w_ano - page.wh_anoc, page.posy_ano)
                ano_bar.setStyleSheet(f"""
                        QPushButton {{
                          width: {page.w_ano}px;
                          height: {page.h_ano}px;
                          border-radius: {page.h_ano // 2}px;
                          background-color: {page.color_on};
                        }}
                    """)

            page.toggle_state = not page.toggle_state
            ano_circle.update()
            ano_bar.update()
            QApplication.processEvents()

        ano_bar.clicked.connect(toggle_button)
        ano_circle.clicked.connect(toggle_button)

        def delete_image_from_origin(image_path):
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception as e:
                    print(f"Erro ao apagar a imagem: {e}")
            else:
                print(f"Imagem '{image_path}' não encontrada.")

        # endregion

        # region :::::::::::Botão "trancar":::::::::::
        def trancar_action():
            if page.image_path_selected:
                additional_info = "\n(Após a trancagem, a mesma será removida do dispositivo)" if page.toggle_state else ""
                answer = self.show_dialog("Trancar Imagem", "Confirme", f"Deseja trancar essa imagem?{additional_info}",
                                          QMessageBox.Question, 3)
                if answer == QMessageBox.Yes:
                    successfully_encoded = encode_image(self.vault_id, page.image_path_selected, image_rename.text())
                    if successfully_encoded:
                        if page.toggle_state:
                            delete_image_from_origin(page.image_path_selected)
                        remove_imgb_img()

        trancar = QPushButton("Trancar imagem", page)
        trancar.setStyleSheet("""
            QPushButton {
                border-radius: 10px;
                background-color: #8D8D8D; 
                font-size: 10px;               
                outline: none;
            }
            QPushButton:hover {
                background-color: #5F0F63; 
            }
        """)
        trancar.setFixedSize(90, 32)
        trancar.move(575, 390)
        trancar.clicked.connect(trancar_action)
        # endregion

        # region :::::::::::Botão Página Destrancar Imagem:::::::::::
        def mudar_destrancar_action():
            self.images_list = get_vault_images(self.vault_id) or {}
            self.reload_work_pages()
            self.pages.setCurrentWidget(self.unlock_image_page)

        mudar_destrancar = QPushButton("", page)
        mudar_destrancar.setStyleSheet("""
            QPushButton {
                border: none;
                outline: none;
            }
        """)
        mudar_destrancar.setFixedSize(89, 54)
        mudar_destrancar.move(482, 63)
        mudar_destrancar.clicked.connect(mudar_destrancar_action)


        # endregion

        # region :::::::::::Botão Upload Imagem:::::::::::
        def upload_image():
            file, _ = QFileDialog.getOpenFileName(self, "Selecione uma Imagem", "",
                                                  "Imagens (*.png *.jpg *.bmp *.jpeg);")
            if file:
                page.image_path_selected = file
                on_image_selected(page.image_path_selected)

        page.upload = QPushButton("", page)
        page.upload.setStyleSheet("""
            QPushButton {
                border: none;
                outline: none;
            }
        """)
        page.upload.setFixedSize(69, 60)
        page.upload.move(562, 134)
        page.upload.clicked.connect(upload_image)
        # endregion

        return page

    def show_unlock_image_page(self):
        page = QWidget()
        svg_widget = QSvgWidget(screen2, page)
        svg_widget.setParent(page)

        # region _____________login details_____________
        vault_name_label = QLabel(f"Cofre: {self.vault_name}", page)
        vault_name_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                color: #534858;
            }
        """)
        vault_name_label.setFixedSize(200, 40)
        vault_name_label.move(150, 5)

        last_login_label = QLabel(f"Último acesso: {self.last_login}", page)
        last_login_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #534858;
            }
        """)
        last_login_label.setFixedSize(200, 40)
        last_login_label.move(150, 25)

        # endregion

        # region :::::::::::Botão "sair":::::::::::
        def sair_action():
            update_last_login(self.vault_id, self.atual_login)
            self.pages.setCurrentWidget(self.login_page)

        sair = QPushButton("", page)
        sair.setStyleSheet("""
            QPushButton {
                border-radius: 7px;  
                border: none;
                outline: none;
            }
        """)
        sair.setFixedSize(50, 50)
        sair.move(39, 44)
        sair.clicked.connect(sair_action)
        # endregion

        # region :::::::::::Botão "Página Trancar Imagem":::::::::::
        mudar_destrancar = QPushButton("", page)
        mudar_destrancar.setStyleSheet("""
            QPushButton {
                border: none;
                outline: none;
            }
        """)
        mudar_destrancar.setFixedSize(89, 54)
        mudar_destrancar.move(392, 63)
        mudar_destrancar.clicked.connect(lambda: self.pages.setCurrentWidget(self.lock_image_page))

        # endregion

        # region :::::::::::Botão "apagar"::::::::::::
        def atualizar_lista():
            while content_layout.count():
                item = content_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()

            for imgid, imgdata in self.images_list.items():
                item = create_image_item(imgid, imgdata, selected=False)
                content_layout.addWidget(item)

            scroll_area.setWidget(content_widget)

        def apagar_action():
            ids_images_selected_list = get_selected_image_ids()
            success_count = 0
            answer = self.show_dialog("Apagar",
                                      f"Pretende eliminar permanentemente {len(ids_images_selected_list)} imagem(s)?",
                                      "",
                                      QMessageBox.Question,
                                      3)
            if answer == QMessageBox.Yes:
                for image_id in ids_images_selected_list:
                    result = delete_image_from_db(image_id)
                    if result:
                        success_count += 1
                        del self.images_list[image_id]
                messagebox.showinfo("Sucesso", f"{success_count} foram eliminadas com sucesso")
                atualizar_lista()

        apagar = QPushButton("Apagar", page)
        apagar.setStyleSheet("""
            QPushButton {
                border-radius: 10px;
                background-color: #8D8D8D; 
                font-size: 10px;               
                outline: none;
            }
            QPushButton:hover {
                background-color: #5F0F63; 
            }
        """)
        apagar.setFixedSize(90, 35)
        apagar.move(595, 320)
        apagar.clicked.connect(apagar_action)

        # endregion

        # region :::::::::::Botão "destrancar":::::::::::
        def save_unlocked_images(unlocked_images):
            if len(unlocked_images) == 1:
                file_path, _ = QFileDialog.getSaveFileName(
                    None,
                    "Salvar Imagem",
                    "",
                    "PNG Files (*.png);;All Files (*)"
                )
                if file_path:
                    try:
                        with open(file_path, "wb") as f:
                            f.write(unlocked_images[0])
                            messagebox.showinfo("Sucesso", "Imagem salva com sucesso")
                    except Exception as e:
                        messagebox.showinfo("Erro", f"Erro ao salvar a imagem: {e}")
            elif len(unlocked_images) > 1:
                file_path, _ = QFileDialog.getSaveFileName(
                    None,
                    "Salvar Imagens (ZIP)",
                    "",
                    "ZIP Files (*.zip);;All Files (*)"
                )
                if file_path:
                    try:
                        with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                            for idx, img_data_v in enumerate(unlocked_images, start=1):
                                image_filename = f"{img_data_v[0]}_{idx}.png"
                                zipf.writestr(image_filename, img_data_v)

                            messagebox.showinfo("Sucesso", "Imagens salvas com sucesso")
                    except Exception as e:
                        messagebox.showinfo("Erro", f"Erro ao salvar o arquivo ZIP: {e}")

        def destrancar_action():
            unlocked_images = []
            ids_images_selected_list = get_selected_image_ids()
            answer = self.show_dialog("Destrancar",
                                      f"Pretende destrancar {len(ids_images_selected_list)} imagem(s)?",
                                      "",
                                      QMessageBox.Question,
                                      3)
            if answer == QMessageBox.Yes:
                for image_id in ids_images_selected_list:
                    unlocked_data = decode_image(image_id, self.vault_id)
                    if unlocked_data:
                        unlocked_images.append(unlocked_data)
                if unlocked_images:
                    save_unlocked_images(unlocked_images)

        destrancar = QPushButton("Destrancar", page)
        destrancar.setStyleSheet("""
            QPushButton {
                border-radius: 10px;
                background-color: #8D8D8D; 
                font-size: 10px;               
                outline: none;
            }
            QPushButton:hover {
                background-color: #5F0F63; 
            }
        """)
        destrancar.setFixedSize(90, 35)
        destrancar.move(595, 360)
        destrancar.clicked.connect(destrancar_action)

        # endregion

        # region :::::::::::Scroll Area:::::::::::
        scroll_area = QScrollArea(page)
        scroll_area.setWidgetResizable(True)
        scroll_area.setGeometry(165, 230, 350, 345)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent;}")

        fixed_height = 40

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(5)
        content_widget.setLayout(content_layout)
        content_widget.setStyleSheet("background: transparent; border: none;")
        content_widget.selected_ids = set()

        def get_selected_image_ids():
            return list(content_widget.selected_ids)

        def update_buttons():
            if content_widget.selected_ids:
                destrancar.setStyleSheet("""
                    QPushButton {
                        border-radius: 10px;
                        background-color: #6B1A6F; 
                        font-size: 10px;  
                        color: white;               
                        outline: none;
                    }
                """)
                apagar.setStyleSheet("""
                    QPushButton {
                        border-radius: 10px;
                        background-color: #6B1A6F; 
                        color: white;
                        font-size: 10px;               
                        outline: none;
                    }
                """)
            else:
                destrancar.setStyleSheet("""
                    QPushButton {
                        border-radius: 10px;
                        background-color: #8D8D8D; 
                        font-size: 10px;  
                        color: black;             
                        outline: none;
                    }
                """)
                apagar.setStyleSheet("""
                    QPushButton {
                        border-radius: 10px;
                        background-color: #8D8D8D;   
                        color: black;
                        font-size: 10px;               
                        outline: none;
                    }
                """)

        def create_image_item(img_id_p, img_data_p, selected=False):
            item_widget = QWidget()
            item_widget.setFixedHeight(fixed_height)
            item_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            item_widget.img_id = img_id_p

            layout = QHBoxLayout(item_widget)
            layout.setContentsMargins(5, 5, 5, 5)
            layout.setSpacing(10)

            label_name = QLabel(f"{img_data_p[0]}", item_widget)
            label_name.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            label_name.setStyleSheet("font-size: 12px; color: #000;")

            label_date = QLabel(f"{img_data_p[1]}", item_widget)
            label_date.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            label_date.setStyleSheet("font-size: 10px; color: #555;")

            layout.addWidget(label_name)
            layout.addStretch()
            layout.addWidget(label_date)

            if selected:
                item_widget.setStyleSheet("background-color: #9F81C6; border-radius: 4px;")
            else:
                item_widget.setStyleSheet("background-color: transparent;")

            item_widget.selected = selected

            def toggle_selection(event):
                if item_widget.img_id in content_widget.selected_ids:
                    content_widget.selected_ids.remove(item_widget.img_id)
                    item_widget.setStyleSheet("background-color: transparent;")
                else:
                    content_widget.selected_ids.add(item_widget.img_id)
                    item_widget.setStyleSheet("background-color: #9F81C6; border-radius: 4px;")
                update_buttons()

            item_widget.mousePressEvent = toggle_selection

            return item_widget

        if self.images_list:
            for img_id, img_data in self.images_list.items():
                content_layout.addWidget(create_image_item(img_id, img_data, selected=False))

        scroll_area.setWidget(content_widget)
        # endregion

        return page

    ###################################################################################

    @staticmethod
    def show_dialog(title, subtitle, message, type, buttons):
        msg = QMessageBox()
        msg.setIcon(type)
        msg.setWindowTitle(title)
        msg.setText(subtitle)
        msg.setInformativeText(message)
        if buttons == 1:
            msg.setStandardButtons(QMessageBox.Ok)
        elif buttons == 2:
            msg.setStandardButtons(QMessageBox.Cancel | QMessageBox.Ok )
        elif buttons == 3:
            msg.setStandardButtons(QMessageBox.No | QMessageBox.Yes )
        elif buttons == 4:
            msg.setStandardButtons(QMessageBox.Cancel |  QMessageBox.Save)

        return msg.exec()

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    splash_pixmap = QPixmap(ic_splash_img)
    splash = QSplashScreen(splash_pixmap)
    splash.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
    splash.show()

    def start_main_window():
        main_window = MainWindow()
        main_window.show()

    QTimer.singleShot(1200, splash.close)
    QTimer.singleShot(1200, start_main_window)

    sys.exit(app.exec())