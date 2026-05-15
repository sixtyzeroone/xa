import math
import time
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGraphicsScene, QGraphicsView, QGraphicsRectItem, QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsTextItem
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QRectF, QPointF, pyqtProperty
from PyQt6.QtGui import QBrush, QColor, QPen, QFont, QPainter, QPainterPath

class BlinkingArrowItem(QGraphicsLineItem):
    """Animated blinking arrow head untuk beacon connection"""
    
    def __init__(self, x1, y1, x2, y2, color="#00ff00", parent_widget=None, parent=None):
        super().__init__(x1, y1, x2, y2, parent)
        self.base_color = QColor(color)
        self.current_opacity = 1.0
        self.animation_direction = -1  # -1 = fading out, 1 = fading in
        self.blink_speed = 0.05  # Kecepatan blink (semakin kecil semakin cepat)
        self.parent_widget = parent_widget  # NetworkMapWidget sebagai parent timer
        
        # Set pen awal
        pen = QPen(self.base_color, 2)
        pen.setStyle(Qt.PenStyle.SolidLine)
        self.setPen(pen)
        
        # Timer untuk animasi blink - GUNAKAN parent_widget BUKAN self
        if self.parent_widget:
            self.blink_timer = QTimer(self.parent_widget)
            self.blink_timer.timeout.connect(self._blink_step)
            self.blink_timer.start(50)
        else:
            self.blink_timer = None
        
        # Hitung arrow head
        self._update_arrow_head()
        
    def _update_arrow_head(self):
        """Update arrow head position berdasarkan line endpoint"""
        line = self.line()
        x1, y1 = line.x1(), line.y1()
        x2, y2 = line.x2(), line.y2()
        
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx*dx + dy*dy)
        
        if length > 0:
            # Normalized direction
            ux = dx / length
            uy = dy / length
            
            # Perpendicular vector untuk arrow wings
            px = -uy
            py = ux
            
            # Arrow size (proporsional dengan panjang line)
            arrow_size = min(12, length / 3)
            
            # Arrow points
            tip = QPointF(x2, y2)
            left = QPointF(
                x2 - arrow_size * ux + arrow_size * 0.5 * px,
                y2 - arrow_size * uy + arrow_size * 0.5 * py
            )
            right = QPointF(
                x2 - arrow_size * ux - arrow_size * 0.5 * px,
                y2 - arrow_size * uy - arrow_size * 0.5 * py
            )
            
            # Simpan arrow points untuk drawing
            self.arrow_tip = tip
            self.arrow_left = left
            self.arrow_right = right
            
    def _blink_step(self):
        """Step animasi blink - opacity berubah secara sinusoidal"""
        # Update opacity (floating point)
        self.current_opacity += self.animation_direction * self.blink_speed
        
        if self.current_opacity <= 0.2:
            self.current_opacity = 0.2
            self.animation_direction = 1  # Fade in
        elif self.current_opacity >= 1.0:
            self.current_opacity = 1.0
            self.animation_direction = -1  # Fade out
            
        # Update pen dengan opacity baru
        color = QColor(self.base_color)
        color.setAlphaF(self.current_opacity)
        pen = QPen(color, 2)
        pen.setStyle(Qt.PenStyle.SolidLine)
        self.setPen(pen)
        
        # Trigger repaint untuk arrow head
        self.update()
        
    def paint(self, painter, option, widget=None):
        """Override paint untuk menggambar arrow head dengan animasi"""
        super().paint(painter, option, widget)
        
        # Gambar arrow head dengan opacity yang sama
        if hasattr(self, 'arrow_tip'):
            # Arrow head color with opacity
            color = QColor(self.base_color)
            color.setAlphaF(self.current_opacity)
            
            # Arrow path
            path = QPainterPath()
            path.moveTo(self.arrow_tip)
            path.lineTo(self.arrow_left)
            path.lineTo(self.arrow_right)
            path.lineTo(self.arrow_tip)
            
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color, 1))
            painter.drawPath(path)
            
    def stop_animation(self):
        """Stop animasi (panggil saat connection mati)"""
        if self.blink_timer and self.blink_timer.isActive():
            self.blink_timer.stop()


class AnimatedBeamItem(QGraphicsLineItem):
    """Animated scanning beam effect untuk beacon connection (efek seperti radar)"""
    
    def __init__(self, x1, y1, x2, y2, color="#00ff00", parent_widget=None, parent=None):
        super().__init__(x1, y1, x2, y2, parent)
        self.base_color = QColor(color)
        self.beam_position = 0.0  # 0 to 1 (position along the line)
        self.beam_direction = 1   # 1 = forward, -1 = backward
        self.beam_speed = 0.02
        self.parent_widget = parent_widget
        
        # Set pen awal (dashed line untuk base connection)
        pen = QPen(self.base_color, 1.5)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setDashPattern([6, 4])
        self.setPen(pen)
        
        # Timer untuk animasi beam - GUNAKAN parent_widget BUKAN self
        if self.parent_widget:
            self.beam_timer = QTimer(self.parent_widget)
            self.beam_timer.timeout.connect(self._beam_step)
            self.beam_timer.start(30)
        else:
            self.beam_timer = None
        
    def _beam_step(self):
        """Step animasi beam"""
        self.beam_position += self.beam_direction * self.beam_speed
        
        if self.beam_position >= 0.95:
            self.beam_position = 0.95
            self.beam_direction = -1
        elif self.beam_position <= 0.05:
            self.beam_position = 0.05
            self.beam_direction = 1
            
        self.update()
        
    def paint(self, painter, option, widget=None):
        """Override paint untuk menggambar beam effect"""
        super().paint(painter, option, widget)
        
        line = self.line()
        x1, y1 = line.x1(), line.y1()
        x2, y2 = line.x2(), line.y2()
        
        # Hitung posisi beam
        dx = x2 - x1
        dy = y2 - y1
        
        beam_x = x1 + dx * self.beam_position
        beam_y = y1 + dy * self.beam_position
        
        # Gambar beam sebagai lingkaran glow
        glow_color = QColor(self.base_color)
        glow_color.setAlphaF(0.8)
        
        painter.setBrush(QBrush(glow_color))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        
        # Glow effect (lingkaran dengan ukuran bervariasi)
        glow_size = 6 + (abs(self.beam_position - 0.5) * 4)
        painter.drawEllipse(QPointF(beam_x, beam_y), glow_size, glow_size)
        
        # Inner core (lebih terang)
        core_color = QColor(self.base_color)
        core_color.setAlphaF(1.0)
        painter.setBrush(QBrush(core_color))
        painter.drawEllipse(QPointF(beam_x, beam_y), 3, 3)
    
    def stop_animation(self):
        """Stop animasi beam"""
        if self.beam_timer and self.beam_timer.isActive():
            self.beam_timer.stop()


class NetworkMapWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        
        # Cobalt Strike style: Dark theme dengan highlight hijau
        self.view.setBackgroundBrush(QBrush(QColor("#0c0c0c")))
        self.scene.setBackgroundBrush(QBrush(QColor("#0c0c0c")))
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setInteractive(True)
        
        self.view.setStyleSheet("""
            QGraphicsView {
                border: 1px solid #1e1e1e;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.setLayout(layout)

        # Auto refresh setiap 3 detik
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_map)
        self.timer.start(3000)
        self.is_running = True

        self.nodes = {}
        self.edges = []
        self.animated_items = []  # Track animated items untuk cleanup
        self.timers = []  # Track timers untuk cleanup
        
        # Colors palette Cobalt Strike
        self.cs_colors = {
            "primary": "#00ff00",
            "secondary": "#00cc00",
            "accent": "#ff6b00",
            "text": "#cccccc",
            "dark_bg": "#0c0c0c",
            "panel_bg": "#1a1a1a",
            "border": "#333333",
            "listener": "#ff4444",
            "windows": "#4a90e2",
            "linux": "#34c759",
            "macos": "#ff9500",
            "unknown": "#8e8e93",
            "beacon_active": "#00ff00",
            "beacon_inactive": "#666666",
        }

    def stop_refresh(self):
        """Stop auto-refresh (panggil saat module running)"""
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()
            self.is_running = False
    
    def start_refresh(self):
        """Start auto-refresh kembali"""
        if not self.is_running and hasattr(self, 'timer'):
            self.timer.start(3000)
            self.is_running = True
    
    def cleanup(self):
        """Cleanup all timers and animated items"""
        # Stop all timers
        for timer in self.timers:
            try:
                if timer and timer.isActive():
                    timer.stop()
            except:
                pass
        self.timers.clear()
        
        # Stop animated items
        for item in self.animated_items:
            try:
                if hasattr(item, 'stop_animation'):
                    item.stop_animation()
            except:
                pass
        self.animated_items.clear()

    def draw_cobalt_strike_background(self):
        """Background dengan grid subtle seperti CS"""
        grid_pen = QPen(QColor("#1a1a1a"), 1)
        
        # Horizontal grid
        for y in range(-500, 501, 50):
            line = QGraphicsLineItem(-700, y, 700, y)
            line.setPen(grid_pen)
            self.scene.addItem(line)
        
        # Vertical grid
        for x in range(-700, 701, 50):
            line = QGraphicsLineItem(x, -500, x, 500)
            line.setPen(grid_pen)
            self.scene.addItem(line)

    def create_computer_icon(self, x, y, os_type="unknown", is_server=False, 
                           monitor_width=100, monitor_height=70):
        """Create computer icon seperti Cobalt Strike"""
        color_map = {
            "windows": self.cs_colors["windows"],
            "linux": self.cs_colors["linux"],
            "darwin": self.cs_colors["macos"],
            "unknown": self.cs_colors["unknown"]
        }
        color = color_map.get(os_type, self.cs_colors["unknown"])
        
        if is_server:
            # Server rack style
            rack = QGraphicsRectItem(x - 60, y - 40, 120, 80)
            rack.setBrush(QBrush(QColor("#1a1a1a")))
            rack.setPen(QPen(QColor(self.cs_colors["listener"]), 2))
            
            for i in range(3):
                unit = QGraphicsRectItem(x - 50, y - 30 + i*20, 100, 15)
                unit.setBrush(QBrush(QColor("#2a2a2a")))
                unit.setPen(QPen(QColor("#444444"), 1))
                self.scene.addItem(unit)
            
            # Blinking LED untuk server aktif
            led = QGraphicsEllipseItem(x + 35, y - 35, 8, 8)
            led.setBrush(QBrush(QColor("#00ff00")))
            led.setPen(QPen(Qt.GlobalColor.black))
            
            # Animasi LED blink - parent = self (NetworkMapWidget)
            led_blink = QTimer(self)
            led_blink.timeout.connect(lambda: self._blink_led(led))
            led_blink.start(800)
            self.timers.append(led_blink)
            led.setProperty("blink_timer", led_blink)
            
            self.scene.addItem(led)
            self.scene.addItem(rack)
            return rack
        else:
            # Desktop computer icon
            monitor = QGraphicsRectItem(
                x - monitor_width//2, 
                y - monitor_height//2, 
                monitor_width, 
                monitor_height
            )
            monitor.setBrush(QBrush(QColor("#1a1a1a")))
            monitor.setPen(QPen(QColor(color), 2))
            
            screen_margin = 5
            screen = QGraphicsRectItem(
                x - monitor_width//2 + screen_margin,
                y - monitor_height//2 + screen_margin,
                monitor_width - screen_margin*2,
                monitor_height - screen_margin*2 - 10
            )
            screen.setBrush(QBrush(QColor("#2a2a2a")))
            screen.setPen(QPen(QColor("#444444"), 1))
            
            # OS logo
            logos = {"windows": "🪟", "linux": "🐧", "darwin": "🍎", "unknown": "💻"}
            logo = QGraphicsTextItem(logos.get(os_type, "💻"))
            logo.setDefaultTextColor(QColor(color))
            logo.setFont(QFont("Segoe UI Emoji", 16))
            logo.setPos(x - logo.boundingRect().width()/2, y - 15)
            
            # Stand
            stand_width = 20
            stand_height = 10
            stand = QGraphicsRectItem(
                x - stand_width//2,
                y + monitor_height//2 - stand_height//2,
                stand_width,
                stand_height
            )
            stand.setBrush(QBrush(QColor("#333333")))
            stand.setPen(QPen(QColor(color), 1))
            
            self.scene.addItem(monitor)
            self.scene.addItem(screen)
            self.scene.addItem(logo)
            self.scene.addItem(stand)
            
            return monitor

    def _blink_led(self, led):
        """Blink LED effect untuk server/listener aktif"""
        try:
            if led is None or led.scene() is None:
                return
            current_brush = led.brush()
            if current_brush.color() == QColor("#00ff00"):
                led.setBrush(QBrush(QColor("#005500")))
            else:
                led.setBrush(QBrush(QColor("#00ff00")))
        except RuntimeError:
            pass

    def create_beacon_item(self, x, y, text, color="#00ff00", is_beacon=True):
        """Create beacon/agent item"""
        # Outer circle (glow)
        if is_beacon:
            outer = QGraphicsEllipseItem(x - 25, y - 25, 50, 50)
            outer.setBrush(QBrush(QColor(color + "20")))
            outer.setPen(QPen(Qt.PenStyle.NoPen))
            self.scene.addItem(outer)
        
        # Main circle
        circle = QGraphicsEllipseItem(x - 20, y - 20, 40, 40)
        circle.setBrush(QBrush(QColor("#1a1a1a")))
        circle.setPen(QPen(QColor(color), 2))
        self.scene.addItem(circle)
        
        # Icon
        icon = QGraphicsTextItem("🔗" if is_beacon else "⚡")
        icon.setDefaultTextColor(QColor(color))
        icon.setFont(QFont("Segoe UI Emoji", 14))
        icon.setPos(x - icon.boundingRect().width()/2, y - icon.boundingRect().height()/2)
        self.scene.addItem(icon)
        
        # Text
        text_item = QGraphicsTextItem(text)
        text_item.setDefaultTextColor(QColor(self.cs_colors["text"]))
        text_item.setFont(QFont("Consolas", 9))
        text_item.setPos(x - text_item.boundingRect().width()/2, y + 25)
        self.scene.addItem(text_item)
        
        return circle

    def add_animated_connection(self, from_key, to_key, label="", is_active=True):
        """Add connection dengan animasi beacon (blinking arrow + beam effect)"""
        if from_key not in self.nodes or to_key not in self.nodes:
            return
            
        x1, y1 = self.nodes[from_key][2], self.nodes[from_key][3]
        x2, y2 = self.nodes[to_key][2], self.nodes[to_key][3]
        
        # Warna berdasarkan status aktif
        if is_active:
            line_color = self.cs_colors["beacon_active"]
            # Gunakan animated beam untuk koneksi aktif - PASS self sebagai parent_widget
            beam = AnimatedBeamItem(x1, y1, x2, y2, line_color, parent_widget=self)
            self.scene.addItem(beam)
            self.animated_items.append(beam)
            
            # Tambahkan blinking arrow head - PASS self sebagai parent_widget
            arrow = BlinkingArrowItem(x1, y1, x2, y2, line_color, parent_widget=self)
            self.scene.addItem(arrow)
            self.animated_items.append(arrow)
        else:
            # Koneksi mati - solid gray line, no animation
            line_color = self.cs_colors["beacon_inactive"]
            line = QGraphicsLineItem(x1, y1, x2, y2)
            pen = QPen(QColor(line_color), 1.5)
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setDashPattern([6, 6])
            line.setPen(pen)
            self.scene.addItem(line)
        
        # Label untuk connection (opsional)
        if label and is_active:
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2 - 15
            
            # Label background
            label_bg = QGraphicsRectItem(mid_x - 35, mid_y - 10, 70, 20)
            label_bg.setBrush(QBrush(QColor("#1a1a1a")))
            label_bg.setPen(QPen(QColor(line_color), 1))
            self.scene.addItem(label_bg)
            
            # Label text
            txt = QGraphicsTextItem(label.upper())
            txt.setDefaultTextColor(QColor(line_color))
            txt.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            txt.setPos(mid_x - txt.boundingRect().width()/2, mid_y - txt.boundingRect().height()/2)
            self.scene.addItem(txt)

    def refresh_map(self):
        """Refresh map dengan animasi beacon"""
        # Cleanup sebelum refresh
        self.cleanup()
        
        # Clear scene
        self.scene.clear()
        self.nodes.clear()
        self.edges = []
        self.animated_items = []
        
        # Draw background
        self.draw_cobalt_strike_background()
        
        # === KONFIGURASI ===
        SERVER_BOX_WIDTH = 220
        SERVER_BOX_HEIGHT = 220
        SESSION_MONITOR_WIDTH = 100
        SESSION_MONITOR_HEIGHT = int(SERVER_BOX_HEIGHT * 0.6)
        SESSION_INFO_HEIGHT = 60
        SESSION_TOTAL_HEIGHT = SESSION_MONITOR_HEIGHT + SESSION_INFO_HEIGHT + 10
        LISTENER_OFFSET_Y = 50
        
        # === HEADER ===
        header = QGraphicsTextItem("LAZY FRAMEWORK - TEAM SERVER")
        header.setDefaultTextColor(QColor(self.cs_colors["primary"]))
        header.setFont(QFont("Consolas", 18, QFont.Weight.Bold))
        header.setPos(-header.boundingRect().width()/2, -480)
        self.scene.addItem(header)
        
        subtitle = QGraphicsTextItem("Network Visualization & Session Management")
        subtitle.setDefaultTextColor(QColor(self.cs_colors["text"]))
        subtitle.setFont(QFont("Consolas", 11))
        subtitle.setPos(-subtitle.boundingRect().width()/2, -450)
        self.scene.addItem(subtitle)
        
        separator = QGraphicsLineItem(-600, -430, 600, -430)
        separator.setPen(QPen(QColor(self.cs_colors["border"]), 1))
        self.scene.addItem(separator)

        # === TEAM SERVER ===
        attacker_x = -450
        attacker_y = -300
        
        server_box = QGraphicsRectItem(
            attacker_x - SERVER_BOX_WIDTH//2, 
            attacker_y - SERVER_BOX_HEIGHT//2, 
            SERVER_BOX_WIDTH, 
            SERVER_BOX_HEIGHT
        )
        server_box.setBrush(QBrush(QColor("#1a1a1a")))
        server_box.setPen(QPen(QColor(self.cs_colors["primary"]), 3))
        self.scene.addItem(server_box)
        
        server_icon = QGraphicsTextItem("🖥️")
        server_icon.setDefaultTextColor(QColor(self.cs_colors["primary"]))
        server_icon.setFont(QFont("Segoe UI Emoji", 35))
        server_icon.setPos(
            attacker_x - server_icon.boundingRect().width()/2, 
            attacker_y - SERVER_BOX_HEIGHT//2 + 25
        )
        self.scene.addItem(server_icon)
        
        server_info = QGraphicsTextItem(
            f"TEAM SERVER\n"
            f"Operator: {self.parent.framework.session.get('user', 'unknown')}\n"
            f"IP: {self.parent.framework.session.get('LHOST', '0.0.0.0')}\n"
            f"Sessions: {len(self.parent.sessions)}\n"
            f"Status: [ACTIVE]"
        )
        server_info.setDefaultTextColor(QColor(self.cs_colors["text"]))
        server_info.setFont(QFont("Hack", 10))
        server_info.setPos(
            attacker_x - server_info.boundingRect().width()/2, 
            attacker_y - SERVER_BOX_HEIGHT//2 + 100
        )
        self.scene.addItem(server_info)
        
        self.nodes["teamserver"] = (server_box, server_icon, attacker_x, attacker_y)

        # === LISTENERS ===
        listener_x_start = -150
        listener_y = attacker_y + LISTENER_OFFSET_Y
        
        # Cek listener aktif dari GUI
        active_listeners = []
        if hasattr(self.parent, 'active_listeners'):
            with self.parent.listener_lock:
                if isinstance(self.parent.active_listeners, list):
                    active_listeners = list(self.parent.active_listeners)
                elif isinstance(self.parent.active_listeners, dict):
                    active_listeners = list(self.parent.active_listeners.values())
        
        for idx, listener in enumerate(active_listeners):
            if isinstance(listener, dict):
                lhost = listener.get("lhost", "0.0.0.0")
                lport = listener.get("lport", "4444")
            else:
                lhost = "0.0.0.0"
                lport = "4444"
            key = f"listener:{lhost}:{lport}"
            
            listener_x = listener_x_start + idx * 120
            
            beacon = self.create_beacon_item(
                listener_x, listener_y,
                f"LISTENER\n{lport}",
                self.cs_colors["listener"],
                is_beacon=True
            )
            
            details = QGraphicsTextItem(f"{lhost}")
            details.setDefaultTextColor(QColor("#888888"))
            details.setFont(QFont("Consolas", 8))
            details.setPos(
                listener_x - details.boundingRect().width()/2, 
                listener_y + 50
            )
            self.scene.addItem(details)
            
            self.nodes[key] = (beacon, None, listener_x, listener_y)
            
            # Connect team server ke listener (koneksi mati/tidak beranimasi)
            self.add_animated_connection("teamserver", key, f"handler {idx+1}", is_active=False)

        # === SESSIONS ===
        session_x_start = 200
        session_y_start = attacker_y - (SESSION_MONITOR_HEIGHT//2) + LISTENER_OFFSET_Y
        
        for idx, (sid, sess) in enumerate(self.parent.sessions.items()):
            os_type = sess.get("os", "unknown")
            status = sess.get("status", "alive")
            is_active = (status == "alive")
            
            row = idx // 3
            col = idx % 3
            session_x = session_x_start + col * 180
            session_y = session_y_start + row * (SESSION_TOTAL_HEIGHT + 30)
            
            # Computer icon
            computer = self.create_computer_icon(
                session_x, session_y, os_type,
                monitor_width=SESSION_MONITOR_WIDTH,
                monitor_height=SESSION_MONITOR_HEIGHT
            )
            
            # Status glow effect untuk session aktif - TANPA ANIMASI (static)
            if is_active:
                glow = QGraphicsEllipseItem(session_x - 55, session_y - 55, 110, 110)
                glow.setBrush(QBrush(QColor("#00ff0020")))  # Fixed opacity
                glow.setPen(QPen(Qt.PenStyle.NoPen))
                self.scene.addItem(glow)
            
            # Session info box
            info_bg = QGraphicsRectItem(
                session_x - 70, 
                session_y + SESSION_MONITOR_HEIGHT//2 + 10,
                140, 
                SESSION_INFO_HEIGHT
            )
            info_bg.setBrush(QBrush(QColor("#1a1a1a")))
            info_bg.setPen(QPen(QColor(self.cs_colors["border"]), 1))
            self.scene.addItem(info_bg)
            
            # Session ID
            session_id_text = QGraphicsTextItem(f"#{idx+1} {sid[:8]}")
            session_id_text.setDefaultTextColor(QColor(self.cs_colors["primary"]))
            session_id_text.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
            session_id_text.setPos(
                session_x - session_id_text.boundingRect().width()/2, 
                session_y + SESSION_MONITOR_HEIGHT//2 + 15
            )
            self.scene.addItem(session_id_text)
            
            # Session details
            details = QGraphicsTextItem(
                f"{sess.get('ip', '?.?.?.?')}:{sess.get('port', '?')}\n"
                f"{sess.get('type', 'shell')}"
            )
            details.setDefaultTextColor(QColor(self.cs_colors["text"]))
            details.setFont(QFont("Consolas", 8))
            details.setPos(
                session_x - details.boundingRect().width()/2, 
                session_y + SESSION_MONITOR_HEIGHT//2 + 35
            )
            self.scene.addItem(details)
            
            # Status indicator
            status_text = "ALIVE" if is_active else "DEAD"
            status_color = "#00ff00" if is_active else "#ff4444"
            status_item = QGraphicsTextItem(f"● {status_text}")
            status_item.setDefaultTextColor(QColor(status_color))
            status_item.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
            status_item.setPos(
                session_x + 50, 
                session_y - SESSION_MONITOR_HEIGHT//2 + 10
            )
            self.scene.addItem(status_item)
            
            self.nodes[sid] = (computer, session_id_text, session_x, session_y)
            
            # Connect ke listener yang sesuai (dengan animasi jika aktif)
            listener_key = f"listener:{sess.get('lhost', '0.0.0.0')}:{sess.get('lport', '4444')}"
            if listener_key in self.nodes:
                self.add_animated_connection(
                    listener_key, sid, 
                    f"beacon {idx+1}", 
                    is_active=is_active
                )
            
            # Click handler untuk interact dengan session
            computer.mousePressEvent = self._make_click_handler(sid)
            computer.setCursor(Qt.CursorShape.PointingHandCursor)

        # === FOOTER ===
        footer_bg = QGraphicsRectItem(-600, 430, 1200, 60)
        footer_bg.setBrush(QBrush(QColor("#1a1a1a")))
        footer_bg.setPen(QPen(QColor(self.cs_colors["border"]), 1))
        self.scene.addItem(footer_bg)
        
        stats = QGraphicsTextItem(
            f"📊 STATS | Listeners: {len(active_listeners)} • "
            f"Sessions: {len(self.parent.sessions)} • "
            f"Proxy: {'🟢 ON' if self.parent.proxy_enabled else '🔴 OFF'} • "
            f"Updated: {time.strftime('%H:%M:%S')}"
        )
        stats.setDefaultTextColor(QColor(self.cs_colors["text"]))
        stats.setFont(QFont("Consolas", 10))
        stats.setPos(-stats.boundingRect().width()/2, 440)
        self.scene.addItem(stats)
        
        legend = QGraphicsTextItem(
            "🖥️ Team Server • 🔗 Listener • 🪟 Windows • 🐧 Linux • 🍎 macOS • 💻 Unknown • ✨ Blinking = Active"
        )
        legend.setDefaultTextColor(QColor("#666666"))
        legend.setFont(QFont("Consolas", 9))
        legend.setPos(-legend.boundingRect().width()/2, 465)
        self.scene.addItem(legend)
    
    def _make_click_handler(self, session_id):
        """Create click handler untuk session computer icon"""
        def handler(event):
            if hasattr(self.parent, 'interact_with_session'):
                self.parent.interact_with_session(session_id)
        return handler