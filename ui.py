import keyboard

class SelectionWindow(QWidget):
    """Draggable and resizable overlay window for screen selection"""
    
    def __init__(self, color, position, size):
        super().__init__()
        self.color = color
        self.interactive = True
        self.dragging = False
        self.resizing = False
        self.drag_start = QPoint()
        self.resize_start = QPoint()
        self.resize_rect = QRect()
        self.resize_margin = 10
        
        self.setup_window(position, size)
    
    def setup_window(self, position, size):
        """Initialize window properties"""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(position[0], position[1], size[0], size[1])
        self.setMouseTracking(True)
        self.show()
    
    def paintEvent(self, event):
        """Draw the overlay rectangle"""
        painter = QPainter(self)
        painter.setBrush(QColor(*self.color, 50))
        painter.setPen(QColor(*self.color, 200))
        painter.drawRect(self.rect())
    
    def mousePressEvent(self, event):
        """Handle mouse press for dragging and resizing"""
        if not self.interactive or event.button() != Qt.LeftButton:
            return
            
        if self.is_on_edge(event.pos()):
            self.resizing = True
            self.resize_start = event.globalPos()
            self.resize_rect = self.geometry()
        else:
            self.dragging = True
            self.drag_start = event.globalPos() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, event):
        """Handle mouse movement for dragging and resizing"""
        if not self.interactive:
            return
            
        if self.resizing:
            diff = event.globalPos() - self.resize_start
            new_rect = QRect(self.resize_rect)
            new_rect.setBottomRight(new_rect.bottomRight() + diff)
            self.setGeometry(new_rect)
        elif self.dragging:
            self.move(event.globalPos() - self.drag_start)
        else:
            cursor = Qt.SizeFDiagCursor if self.is_on_edge(event.pos()) else Qt.ArrowCursor
            self.setCursor(cursor)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if not self.interactive:
            return
        self.dragging = False
        self.resizing = False
    
    def is_on_edge(self, pos):
        """Check if position is on the resize edge"""
        rect = self.rect()
        return (abs(pos.x() - rect.right()) < self.resize_margin and 
                abs(pos.y() - rect.bottom()) < self.resize_margin)
    
    def get_rect(self):
        """Get current rectangle coordinates"""
        geo = self.geometry()
        return (geo.left(), geo.top(), geo.width(), geo.height())
    
    def toggle_interactive(self):
        """Toggle between interactive and click-through modes"""
        self.interactive = not self.interactive
        if self.interactive:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        else:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput)
        self.show()

def toggle_window(window, name):
    """Toggle window interactive mode"""
    window.toggle_interactive()
    mode = "interactive" if window.interactive else "click-through"
    print(f"🔄 {name} rectangle: {mode} mode")

def setup_ui():
    app = QApplication(sys.argv)

    question_window = SelectionWindow((255, 0, 0), (100, 100), (500, 100))
    options_window = SelectionWindow((0, 0, 255), (100, 250), (500, 200))

    return app, question_window, options_window


def setup_hotkeys(question_window, options_window, process_callback):
    keyboard.add_hotkey('F6', lambda: toggle_window(question_window, "Red"))
    keyboard.add_hotkey('F7', lambda: toggle_window(options_window, "Blue"))
    keyboard.add_hotkey('F8', process_callback)
