"""
Tela do Plenário — Layout Lateral (Monitor 2)
Réplica fiel do SVG "Cópia de TELA DE TEMPO.svg"

FONTES: calculadas a partir da largura disponível da coluna direita,
com teto em % da altura da tela. Isso garante que nada ultrapasse os
limites visíveis em QUALQUER resolução.

Layout:
  ┌──────────┬──────────────────────────────────────────────────┐
  │          │  1ª SESSÃO ORDINÁRIA                             │ ← f_session
  │  FOTO    │                                            2026  │ ← f_year
  │  (col.   │  ░ stripe do PNG ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
  │  esq.)   │  MOISES DO JARDIM | PL                           │ ← f_name
  │          │  DO OURO (word wrap)                             │
  │          │                                                  │
  │          │  10:00                                           │ ← f_timer
  │          │  ─── barra dourada ────────────────────          │
  └──────────┴──────────────────────────────────────────────────┘
"""

import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, Slot, QDate
from PySide6.QtGui import QPixmap, QScreen

PHOTO_COL_RATIO = 0.37   # 37 % da largura total para a foto
COL_PADDING     = 60     # padding horizontal total (30px cada lado) na coluna direita

# Factor de largura média por caractere em Arial Black (empírico)
CHAR_W_FACTOR   = 0.60


class TelaPlenarioLateral(QMainWindow):
    """
    Tela fullscreen com fontes garantidas dentro dos limites da tela.
    """

    # ──────────────────────────────────────────────────────
    #  Inicialização
    # ──────────────────────────────────────────────────────
    def __init__(self):
        super().__init__()

        self.current_vereador = None
        self.remaining_seconds = 0
        self.is_running        = False
        self.timer_started     = False

        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self.blink_update)
        self.blink_state     = True
        self.style_blink_on  = ""
        self.style_blink_off = ""

        from session_config import SessionConfig
        self.session_config = SessionConfig()

        self.init_ui()
        self.move_to_second_monitor()
        self.show_session_info()

    # ──────────────────────────────────────────────────────
    #  Construção da interface
    # ──────────────────────────────────────────────────────
    def init_ui(self):
        self.setWindowTitle("Tela do Plenário — Layout Lateral")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        # ── Fundo PNG ─────────────────────────────────────
        bg_path = os.path.join(
            os.path.dirname(__file__), "fotos", "Cópia de TELA DE TEMPO.png"
        ).replace("\\", "/")
        self.setStyleSheet(f"""
            QMainWindow {{
                border-image: url("{bg_path}") 0 0 0 0 stretch stretch;
            }}
        """)

        # ── Dimensões da tela ──────────────────────────────
        geo        = self.screen().geometry()
        SW, SH     = geo.width(), geo.height()
        photo_w    = int(SW * PHOTO_COL_RATIO)
        right_w    = SW - photo_w
        label_w    = right_w - COL_PADDING      # largura útil (descontando padding)

        # ── Fontes calculadas a partir da LARGURA disponível ──
        #   Cada fonte = min(derivada da largura, teto em % de SH)
        #   Isso garante que o texto NUNCA extrapole horizontalmente.

        # Título da sessão: "1ª SESSÃO ORDINÁRIA" ≈ 20 chars em Arial Black
        f_session = int(label_w / (20 * CHAR_W_FACTOR))          # cabe em 1 linha
        f_session = min(f_session, int(SH * 0.09))               # teto: 9% SH

        # Ano: "2026" — 4 chars, sempre cabe; usar mesmo peso visual do título
        f_year    = int(f_session * 0.82)

        # Nome | Partido: word-wrap ativo; fonte ≤ sesão
        f_name    = int(label_w / (18 * CHAR_W_FACTOR))
        f_name    = min(f_name, int(f_session * 0.92), int(SH * 0.085))

        # Cronômetro: "00:00" ≈ 5 chars + espaçamento — é o elemento DOMINANTE
        f_timer   = int(label_w / (5 * CHAR_W_FACTOR))
        f_timer   = min(f_timer, int(SH * 0.25))                 # teto: 25% SH

        self._f_timer = f_timer   # guardado para estilos dinâmicos

        # ── Alturas das zonas ──────────────────────────────
        h_header   = int(SH * 0.26)   # título + ano + espaço para stripe do PNG
        h_namezone = int(SH * 0.22)   # nome | partido (2 linhas possíveis)

        # ── Raiz ──────────────────────────────────────────
        root = QWidget()
        root.setStyleSheet("background: transparent;")
        self.setCentralWidget(root)

        main_h = QHBoxLayout(root)
        main_h.setContentsMargins(0, 0, 0, 0)
        main_h.setSpacing(0)

        # ══════════════════════════════════════════════════
        #  COLUNA ESQUERDA — FOTO
        # ══════════════════════════════════════════════════
        self.foto_label = QLabel()
        self.foto_label.setFixedWidth(photo_w)
        self.foto_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.foto_label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )
        self.foto_label.setStyleSheet("background: transparent; border: none;")
        self.set_placeholder_photo()
        main_h.addWidget(self.foto_label)

        # ══════════════════════════════════════════════════
        #  COLUNA DIREITA  (largura máxima = right_w)
        # ══════════════════════════════════════════════════
        right_col = QWidget()
        right_col.setMaximumWidth(right_w)   # ← barreira dura contra overflow
        right_col.setStyleSheet("background: transparent;")
        right_v = QVBoxLayout(right_col)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(0)

        # ── CABEÇALHO ─────────────────────────────────────
        #    session_name (topo, word wrap) + year (direita, abaixo)
        header_widget = QWidget()
        header_widget.setFixedHeight(h_header)
        header_widget.setMaximumWidth(right_w)
        header_widget.setStyleSheet("background: transparent;")
        hdr_v = QVBoxLayout(header_widget)
        hdr_v.setContentsMargins(30, 8, 30, 0)
        hdr_v.setSpacing(0)

        # Linha do título da sessão
        self.header_session_label = QLabel()
        self.header_session_label.setWordWrap(True)
        self.header_session_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.header_session_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.header_session_label.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: #ffffff;
                font-size: {f_session}px;
                font-weight: 900;
                font-family: 'Arial Black', 'Segoe UI Black', sans-serif;
            }}
        """)
        hdr_v.addWidget(self.header_session_label)

        # Linha do ANO — direita, logo abaixo do título
        year_row = QHBoxLayout()
        year_row.setContentsMargins(0, 0, 0, 0)
        year_row.addStretch(1)
        self.header_year_label = QLabel()
        self.header_year_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.header_year_label.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: #ffffff;
                font-size: {f_year}px;
                font-weight: 900;
                font-family: 'Arial Black', 'Segoe UI Black', sans-serif;
            }}
        """)
        year_row.addWidget(self.header_year_label)
        hdr_v.addLayout(year_row)

        hdr_v.addStretch(1)   # empurra texto para cima, stripe do PNG aparece abaixo
        right_v.addWidget(header_widget)

        # ── Stretch 1 (pequeno) ───────────────────────────
        right_v.addStretch(1)

        # ── NOME  |  PARTIDO (mesma linha, mesma fonte) ───
        self.nome_partido_label = QLabel("")
        self.nome_partido_label.setFixedHeight(h_namezone)
        self.nome_partido_label.setMaximumWidth(right_w - COL_PADDING)
        self.nome_partido_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.nome_partido_label.setWordWrap(True)
        self.nome_partido_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.nome_partido_label.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: #ffffff;
                font-size: {f_name}px;
                font-weight: 900;
                font-family: 'Arial Black', 'Segoe UI Black', sans-serif;
                padding: 0 30px;
            }}
        """)
        right_v.addWidget(self.nome_partido_label)

        # ── Stretch 2 (médio) ─────────────────────────────
        right_v.addStretch(2)

        # ── CRONÔMETRO ────────────────────────────────────
        self.timer_container = QWidget()
        self.timer_container.setMaximumWidth(right_w)
        self.timer_container.setStyleSheet("background: transparent; border: none;")
        timer_v = QVBoxLayout(self.timer_container)
        timer_v.setContentsMargins(30, 0, 30, 4)
        timer_v.setSpacing(4)

        self.timer_label = QLabel("00:00")
        self.timer_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.timer_label.setMaximumWidth(int(label_w * 1.05))
        self.timer_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._apply_timer_style_normal()
        timer_v.addWidget(self.timer_label)

        # Barra dourada fina
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: rgba(255, 255, 255, 0.08);
            }
            QProgressBar::chunk {
                background-color: #f4a100;
                border-radius: 4px;
            }
        """)
        timer_v.addWidget(self.progress_bar)

        right_v.addWidget(self.timer_container)

        # ── Stretch 3 (rodapé) ────────────────────────────
        right_v.addStretch(3)

        main_h.addWidget(right_col, 1)

        self.showFullScreen()
        self.update_header()

    # ──────────────────────────────────────────────────────
    #  Estilos do timer
    # ──────────────────────────────────────────────────────
    def _timer_css(self, color: str = "#ffffff") -> str:
        return (
            f"background: transparent; border: none; "
            f"font-size: {self._f_timer}px; font-weight: 900; "
            f"font-family: 'Arial Black', 'Segoe UI Black', sans-serif; "
            f"color: {color};"
        )

    def _apply_timer_style_normal(self):
        self.timer_label.setStyleSheet(self._timer_css("#ffffff"))

    def _apply_timer_style_aparte(self):
        self.timer_label.setStyleSheet(self._timer_css("#fce38a"))

    # ──────────────────────────────────────────────────────
    #  Utilitários
    # ──────────────────────────────────────────────────────
    def update_header(self):
        """
        Header: nome da sessão em maiúsculas + apenas o ANO (sem data completa, sem emoji).
        """
        session_name = ""
        if hasattr(self, "session_config"):
            session_name = (self.session_config.get_session_name() or "SESSÃO").upper()
        year = str(QDate.currentDate().year())

        self.header_session_label.setText(session_name)
        self.header_year_label.setText(year)

    def move_to_second_monitor(self):
        screens = QScreen.virtualSiblings(self.screen())
        if len(screens) > 1:
            self.setGeometry(screens[1].geometry())
            print(f"✅ Tela Lateral → Monitor 2: {screens[1].name()}")
        else:
            print("⚠️  Apenas um monitor. Tela Lateral no monitor principal.")

    def set_placeholder_photo(self):
        self.foto_label.clear()
        self.foto_label.setStyleSheet("background: transparent; border: none;")

    def _load_photo(self, foto_path: str):
        """Carrega e recorta a foto para preencher a coluna esquerda (sem bordas)."""
        pixmap = QPixmap(foto_path)
        w = self.foto_label.width()  or 400
        h = self.foto_label.height() or 800
        scaled = pixmap.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (scaled.width()  - w) // 2
        y = (scaled.height() - h) // 2
        self.foto_label.setPixmap(scaled.copy(x, y, w, h))
        self.foto_label.setStyleSheet("background: transparent; border: none;")

    # ──────────────────────────────────────────────────────
    #  Estados: Sessão × Orador
    # ──────────────────────────────────────────────────────
    def show_session_info(self):
        """Tela de espera — exibe logo e dados da câmara."""
        self.timer_container.setVisible(False)

        logo_path = self.session_config.get_logo()
        if logo_path:
            if not os.path.isabs(logo_path):
                abs_logo = self.session_config.get_data_path(logo_path)
                if not os.path.exists(abs_logo):
                    abs_logo = self.session_config.get_bundle_path(logo_path)
                logo_path = abs_logo
            if os.path.exists(logo_path):
                w = self.foto_label.width()  or 400
                h = self.foto_label.height() or 800
                self.foto_label.setPixmap(
                    QPixmap(logo_path).scaled(
                        w, h,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self.foto_label.setStyleSheet("background: transparent; border: none;")
            else:
                self.set_placeholder_photo()
        else:
            self.set_placeholder_photo()

        session_number = self.session_config.get_session_number()
        city = (self.session_config.get_city_name() or "").upper()
        if session_number:
            self.nome_partido_label.setText(session_number)
        else:
            self.nome_partido_label.setText(
                f"CÂMARA MUNICIPAL DE {city}" if city else "CÂMARA MUNICIPAL"
            )

    def show_vereador_info(self):
        """Restaurar layout de orador."""
        self.timer_started = True
        self.timer_container.setVisible(True)
        if self.current_vereador:
            self.update_vereador(self.current_vereador)
        else:
            self.nome_partido_label.setText("")
            self.set_placeholder_photo()

    def reset_timer_state(self):
        """Voltar para tela de espera."""
        self.timer_started = False
        self.show_session_info()

    # ──────────────────────────────────────────────────────
    #  Slots de sincronização com PainelPresidente
    # ──────────────────────────────────────────────────────
    @Slot(dict)
    def update_vereador(self, vereador):
        self.current_vereador = vereador

        if vereador:
            nome    = (vereador.get("nome")    or "").upper()
            partido = (vereador.get("partido") or "").upper()

            # Mesma linha, mesma fonte, com word wrap automático
            if partido:
                self.nome_partido_label.setText(f"{nome}  |  {partido}")
            else:
                self.nome_partido_label.setText(nome)
            self.nome_partido_label.repaint()

            foto_rel = vereador.get("foto")
            if foto_rel:
                foto_path = self.session_config.get_data_path(foto_rel)
                if not os.path.exists(foto_path):
                    foto_path = self.session_config.get_bundle_path(foto_rel)
                if os.path.exists(foto_path):
                    self._load_photo(foto_path)
                else:
                    self.set_placeholder_photo()
            else:
                self.set_placeholder_photo()
        else:
            self.nome_partido_label.setText("")
            self.set_placeholder_photo()
        
        self.update()

    @Slot(int, int, bool)
    def update_timer(self, seconds, total_seconds=0, is_aparte=False):
        try:
            if isinstance(total_seconds, bool):
                is_aparte     = total_seconds
                total_seconds = 0
        except Exception:
            pass

        self.remaining_seconds = seconds
        m, s = divmod(seconds, 60)
        self.timer_label.setText(f"{m:02d}:{s:02d}")

        # Barra de progresso
        if total_seconds > 0:
            self.progress_bar.setValue(int(seconds / total_seconds * 100))
        else:
            self.progress_bar.setValue(0)

        # Aparte → âmbar
        if is_aparte:
            self.blink_timer.stop()
            self.timer_label.setVisible(True)
            self._apply_timer_style_aparte()
            return

        # Perto do zero → piscar vermelho
        if 0 < seconds <= 60:
            interval = 200 if seconds <= 10 else (500 if seconds <= 30 else 1000)
            if not self.blink_timer.isActive() or self.blink_timer.interval() != interval:
                self.blink_timer.start(interval)
            self.style_blink_on  = self._timer_css("#ff2222")
            self.style_blink_off = self._timer_css("rgba(255, 34, 34, 0.10)")
            if self.blink_state:
                self.timer_label.setStyleSheet(self.style_blink_on)
        else:
            self.blink_timer.stop()
            self.timer_label.setVisible(True)
            self.blink_state = True
            self._apply_timer_style_normal()

    def blink_update(self):
        self.blink_state = not self.blink_state
        self.timer_label.setStyleSheet(
            self.style_blink_on if self.blink_state else self.style_blink_off
        )

    @Slot(bool)
    def update_status(self, is_running):
        self.is_running = is_running
        if is_running:
            if not self.timer_container.isVisible():
                self.timer_container.setVisible(True)
            if not self.timer_started:
                self.timer_started = True
                self.show_vereador_info()
        else:
            if not self.timer_started:
                self.show_session_info()

    # ──────────────────────────────────────────────────────
    #  Teclado
    # ──────────────────────────────────────────────────────
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
