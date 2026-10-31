import sys
from pathlib import Path

import yaml

from PyQt6.QtCore import Qt, QProcess, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


# ============================================================
# PROJECT PATHS
# ============================================================

from palettle.config import get_default_config_path

CONFIG_PATH = get_default_config_path()


# ============================================================
# PROVIDER -> MODEL LIST
# ============================================================

PROVIDER_MODELS = {
    "ollama": [
        "qwen2:1.5b",
        "llama3.2",
        "llama3.1",
        "mistral",
    ],
    "openai": [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4.1-mini",
    ],
    "anthropic": [
        "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-latest",
    ],
}


# ============================================================
# GRAPH WIDGET
# ============================================================

class GraphWidget(QWidget):
    """
    Professional graph preview for the Palette pipeline.

    The real LangGraph structure is:
        every node in layer N -> every node in layer N+1

    To keep the visualization readable, connections are drawn using
    a shared bus between layers. This prevents the crossed X-shaped
    lines that appear with a naive all-to-all drawing.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.layers = []
        self.setMinimumHeight(460)
        self.setMinimumWidth(520)

    def set_layers(self, layers):
        self.layers = layers or []
        self.update()

    def _node_positions(self):
        """Return [(x, y, w, h), ...] for each layer."""
        width = max(self.width(), 520)
        positions = []

        top = 34
        layer_gap = 128
        box_height = 92

        for layer_index, layer in enumerate(self.layers):
            agents = layer.get("agents", [])

            y = top + layer_index * layer_gap

            box_width = min(width - 36, 760)
            box_x = (width - box_width) // 2

            node_count = max(1, len(agents))
            node_width = 205 if node_count <= 2 else 155
            node_height = 46
            gap = 18

            total_width = (
                node_count * node_width
                + (node_count - 1) * gap
            )

            start_x = box_x + max(
                18,
                (box_width - total_width) // 2
            )

            layer_nodes = []

            for i in range(node_count):
                nx = start_x + i * (node_width + gap)
                ny = y + 35

                layer_nodes.append(
                    (
                        nx,
                        ny,
                        node_width,
                        node_height
                    )
                )

            positions.append(layer_nodes)

        return positions

    @staticmethod
    def _arrow(painter, x1, y1, x2, y2):
        """Draw a clean downward arrow."""
        painter.drawLine(x1, y1, x2, y2)

        size = 6

        painter.drawLine(
            x2,
            y2,
            x2 - size,
            y2 - size
        )

        painter.drawLine(
            x2,
            y2,
            x2 + size,
            y2 - size
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        painter.fillRect(
            self.rect(),
            QColor("#07111f")
        )

        if not self.layers:
            painter.setPen(
                QColor("#8fa3bf")
            )
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Configure layers to see the graph"
            )
            return

        positions = self._node_positions()

        # ----------------------------------------------------
        # LAYER CONTAINERS
        # ----------------------------------------------------

        for layer_index, layer in enumerate(
            self.layers
        ):
            if layer_index >= len(positions):
                continue

            nodes = positions[layer_index]

            if not nodes:
                continue

            first_x = nodes[0][0]
            last_x = nodes[-1][0] + nodes[-1][2]

            box_x = first_x - 22
            box_y = nodes[0][1] - 35
            box_width = last_x - first_x + 44
            box_height = 92

            # Make room around one-node layers.
            if box_width < 440:
                center = (
                    first_x + nodes[0][2] / 2
                )
                box_width = 440
                box_x = int(
                    center - box_width / 2
                )

            painter.setPen(
                QPen(
                    QColor("#30466b"),
                    1
                )
            )

            painter.setBrush(
                QBrush(
                    QColor("#0b1729")
                )
            )

            painter.drawRoundedRect(
                int(box_x),
                int(box_y),
                int(box_width),
                box_height,
                14,
                14
            )

            # Layer title
            painter.setPen(
                QColor("#8daaff")
            )

            painter.setFont(
                QFont(
                    "Segoe UI",
                    9,
                    QFont.Weight.Bold
                )
            )

            painter.drawText(
                int(box_x + 16),
                int(box_y + 21),
                layer.get(
                    "name",
                    f"Layer {layer_index + 1}"
                )
            )

        # ----------------------------------------------------
        # CONNECTIONS
        # ----------------------------------------------------
        #
        # Instead of drawing every edge directly (which creates
        # crossed X lines), create a small routing bus.
        #
        # Example:
        #
        #          A
        #          |
        #      ----+----
        #       |     |
        #       B     C
        #
        # This represents A -> B and A -> C cleanly.
        # ----------------------------------------------------

        connector_color = QColor("#5d82df")

        for layer_index in range(
            len(positions) - 1
        ):
            source_nodes = positions[
                layer_index
            ]

            target_nodes = positions[
                layer_index + 1
            ]

            if not source_nodes or not target_nodes:
                continue

            # Bottom center of each source node
            source_points = [
                (
                    int(x + w / 2),
                    int(y + h)
                )
                for x, y, w, h
                in source_nodes
            ]

            # Top center of each target node
            target_points = [
                (
                    int(x + w / 2),
                    int(y)
                )
                for x, y, w, h
                in target_nodes
            ]

            source_y = max(
                p[1] for p in source_points
            )

            target_y = min(
                p[1] for p in target_points
            )

            # A central routing bus.
            bus_y = int(
                (source_y + target_y) / 2
            )

            painter.setPen(
                QPen(
                    connector_color,
                    2
                )
            )

            # Source -> bus
            for sx, sy in source_points:
                self._arrow(
                    painter,
                    sx,
                    sy,
                    sx,
                    bus_y
                )

            # Bus horizontal range
            all_x = [
                p[0]
                for p in (
                    source_points
                    + target_points
                )
            ]

            left_x = min(all_x)
            right_x = max(all_x)

            if left_x != right_x:
                painter.drawLine(
                    left_x,
                    bus_y,
                    right_x,
                    bus_y
                )

            # Bus -> target
            for tx, ty in target_points:
                self._arrow(
                    painter,
                    tx,
                    bus_y,
                    tx,
                    ty
                )

            # Connection label
            if (
                len(source_points) > 1
                or len(target_points) > 1
            ):
                painter.setPen(
                    QColor("#7188ae")
                )
                painter.setFont(
                    QFont(
                        "Segoe UI",
                        7
                    )
                )

                label = "all-to-all"

                painter.drawText(
                    int(
                        (left_x + right_x) / 2
                        - 27
                    ),
                    bus_y - 7,
                    label
                )

        # ----------------------------------------------------
        # NODE CARDS
        # ----------------------------------------------------

        for layer_index, layer in enumerate(
            self.layers
        ):
            nodes = positions[layer_index]
            agents = layer.get("agents", [])

            for agent_index, agent in enumerate(
                agents
            ):
                if agent_index >= len(nodes):
                    continue

                x, y, w, h = nodes[
                    agent_index
                ]

                # Node
                painter.setPen(
                    QPen(
                        QColor("#2387ee"),
                        1
                    )
                )

                painter.setBrush(
                    QBrush(
                        QColor("#102744")
                    )
                )

                painter.drawRoundedRect(
                    int(x),
                    int(y),
                    int(w),
                    int(h),
                    9,
                    9
                )

                # Node ID
                painter.setPen(
                    QColor("#ffffff")
                )

                painter.setFont(
                    QFont(
                        "Segoe UI",
                        8,
                        QFont.Weight.Bold
                    )
                )

                painter.drawText(
                    int(x + 10),
                    int(y + 18),
                    str(
                        agent.get(
                            "name",
                            "agent"
                        )
                    )[:27]
                )

                # Provider / model
                painter.setPen(
                    QColor("#91a8c7")
                )

                painter.setFont(
                    QFont(
                        "Segoe UI",
                        7
                    )
                )

                provider = agent.get(
                    "provider",
                    ""
                )

                model = agent.get(
                    "model",
                    ""
                )

                provider_model = (
                    f"{provider} • {model}"
                )[:32]

                painter.drawText(
                    int(x + 10),
                    int(y + 35),
                    provider_model
                )


# ============================================================
# AGENT CARD
# ============================================================

class AgentCard(QFrame):

    changed = pyqtSignal()

    def __init__(
        self,
        layer_index,
        agent_index,
        defaults=None,
        parent=None
    ):
        super().__init__(parent)

        defaults = defaults or {}

        self.layer_index = layer_index
        self.agent_index = agent_index

        self.setObjectName("AgentCard")

        layout = QGridLayout(self)

        layout.setContentsMargins(
            12,
            10,
            12,
            10
        )

        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(7)

        # ----------------------------------------------------
        # UNIQUE NODE ID
        # ----------------------------------------------------

        default_node_id = defaults.get(
            "name",
            f"layer_{layer_index + 1}"
            f"_agent_{agent_index + 1}"
        )

        self.node_id = QLineEdit(
            default_node_id
        )

        # Node ID is intentionally read-only.
        # This prevents duplicate LangGraph node IDs.
        self.node_id.setReadOnly(True)

        # ----------------------------------------------------
        # ROLE
        # ----------------------------------------------------

        self.role = QLineEdit(
            defaults.get(
                "role",
                "AI Agent"
            )
        )

        # ----------------------------------------------------
        # PROVIDER
        # ----------------------------------------------------

        self.provider = QComboBox()

        self.provider.addItems(
            [
                "ollama",
                "openai",
                "anthropic"
            ]
        )

        provider = defaults.get(
            "provider",
            "ollama"
        )

        self.provider.setCurrentText(
            provider
        )

        # ----------------------------------------------------
        # MODEL
        # ----------------------------------------------------

        self.model = QComboBox()

        self.update_models()

        default_model = defaults.get(
            "model"
        )

        if default_model:

            index = self.model.findText(
                default_model
            )

            if index >= 0:
                self.model.setCurrentIndex(
                    index
                )

        # ----------------------------------------------------
        # TEMPERATURE
        # ----------------------------------------------------

        self.temperature = QDoubleSpinBox()

        self.temperature.setRange(
            0.0,
            2.0
        )

        self.temperature.setSingleStep(
            0.1
        )

        self.temperature.setDecimals(
            1
        )

        self.temperature.setValue(
            float(
                defaults.get(
                    "temperature",
                    0.7
                )
            )
        )

        # ----------------------------------------------------
        # FINAL
        # ----------------------------------------------------

        self.final = QComboBox()

        self.final.addItems(
            [
                "false",
                "true"
            ]
        )

        self.final.setCurrentText(
            "true"
            if defaults.get(
                "final",
                False
            )
            else "false"
        )

        # ----------------------------------------------------
        # INSTRUCTIONS
        # ----------------------------------------------------

        self.instructions = QTextEdit()

        self.instructions.setFixedHeight(
            60
        )

        self.instructions.setPlainText(
            defaults.get(
                "instructions",
                ""
            )
        )

        # ----------------------------------------------------
        # LABELS
        # ----------------------------------------------------

        layout.addWidget(
            QLabel("Node ID"),
            0,
            0
        )

        layout.addWidget(
            QLabel("Role"),
            0,
            1
        )

        layout.addWidget(
            QLabel("Provider"),
            0,
            2
        )

        layout.addWidget(
            QLabel("Model"),
            0,
            3
        )

        layout.addWidget(
            QLabel("Temp"),
            0,
            4
        )

        # ----------------------------------------------------
        # FIRST ROW
        # ----------------------------------------------------

        layout.addWidget(
            self.node_id,
            1,
            0
        )

        layout.addWidget(
            self.role,
            1,
            1
        )

        layout.addWidget(
            self.provider,
            1,
            2
        )

        layout.addWidget(
            self.model,
            1,
            3
        )

        layout.addWidget(
            self.temperature,
            1,
            4
        )

        # ----------------------------------------------------
        # SECOND ROW
        # ----------------------------------------------------

        layout.addWidget(
            QLabel("Instructions"),
            2,
            0
        )

        layout.addWidget(
            self.instructions,
            2,
            1,
            1,
            3
        )

        layout.addWidget(
            QLabel("Final"),
            2,
            4
        )

        layout.addWidget(
            self.final,
            3,
            4
        )

        # ----------------------------------------------------
        # EVENTS
        # ----------------------------------------------------

        self.provider.currentTextChanged.connect(
            self.provider_changed
        )

        self.role.textChanged.connect(
            self.changed.emit
        )

        self.instructions.textChanged.connect(
            self.changed.emit
        )

        self.temperature.valueChanged.connect(
            self.changed.emit
        )

        self.final.currentTextChanged.connect(
            self.changed.emit
        )

    def provider_changed(self):

        current_model = (
            self.model.currentText()
        )

        self.update_models()

        index = self.model.findText(
            current_model
        )

        if index >= 0:

            self.model.setCurrentIndex(
                index
            )

        self.changed.emit()

    def update_models(self):

        provider = (
            self.provider.currentText()
        )

        self.model.clear()

        self.model.addItems(
            PROVIDER_MODELS.get(
                provider,
                []
            )
        )

    def get_data(self):

        return {
            "name": self.node_id.text().strip(),

            "role": self.role.text().strip(),

            "provider": (
                self.provider.currentText()
            ),

            "model": (
                self.model.currentText()
            ),

            "temperature": (
                self.temperature.value()
            ),

            "instructions": (
                self.instructions
                .toPlainText()
                .strip()
            ),

            "final": (
                self.final.currentText()
                == "true"
            )
        }


# ============================================================
# LAYER CARD
# ============================================================

class LayerCard(QGroupBox):

    changed = pyqtSignal()

    def __init__(
        self,
        layer_index,
        defaults=None,
        parent=None
    ):
        super().__init__(parent)

        self.layer_index = layer_index
        self.defaults = defaults or {}

        max_agents = (
            1
            if layer_index == 0
            else 2
        )

        self.setTitle(
            f"Layer {layer_index + 1} "
            f"(Max {max_agents} Agent"
            f"{'s' if max_agents > 1 else ''})"
        )

        layout = QVBoxLayout(self)

        # ----------------------------------------------------
        # AGENT COUNT
        # ----------------------------------------------------

        top = QHBoxLayout()

        top.addWidget(
            QLabel("Number of Agents:")
        )

        self.agent_count = QComboBox()

        if max_agents == 1:

            self.agent_count.addItem(
                "1"
            )

        else:

            self.agent_count.addItems(
                [
                    "1",
                    "2"
                ]
            )

        existing_agents = (
            self.defaults.get(
                "agents",
                []
            )
        )

        existing_count = len(
            existing_agents
        )

        if existing_count <= 0:
            existing_count = 1

        existing_count = min(
            existing_count,
            max_agents
        )

        self.agent_count.setCurrentText(
            str(existing_count)
        )

        top.addWidget(
            self.agent_count
        )

        top.addStretch()

        layout.addLayout(top)

        # ----------------------------------------------------
        # AGENT AREA
        # ----------------------------------------------------

        self.agents_layout = QVBoxLayout()

        layout.addLayout(
            self.agents_layout
        )

        self.agent_cards = []

        self.rebuild_agents(
            emit_signal=False
        )

        self.agent_count.currentTextChanged.connect(
            lambda _: self.rebuild_agents()
        )

    def rebuild_agents(
        self,
        emit_signal=True
    ):

        # Remove old widgets
        while self.agents_layout.count():

            item = (
                self.agents_layout.takeAt(0)
            )

            widget = item.widget()

            if widget:

                widget.deleteLater()

        self.agent_cards = []

        count = int(
            self.agent_count.currentText()
        )

        defaults = (
            self.defaults.get(
                "agents",
                []
            )
        )

        for i in range(count):

            agent_defaults = (
                defaults[i]
                if i < len(defaults)
                else {}
            )

            # Copy so original YAML data
            # is never modified.
            agent_defaults = dict(
                agent_defaults
            )

            # Always generate a unique node ID
            # for newly created agents.
            if i >= len(defaults):

                agent_defaults["name"] = (
                    f"layer_{self.layer_index + 1}"
                    f"_agent_{i + 1}"
                )

            card = AgentCard(
                self.layer_index,
                i,
                agent_defaults
            )

            card.changed.connect(
                self.changed.emit
            )

            self.agent_cards.append(
                card
            )

            self.agents_layout.addWidget(
                card
            )

        if emit_signal:
            self.changed.emit()

    def get_data(self):

        agents = []

        for card in self.agent_cards:

            data = card.get_data()

            # Node ID is always generated/read-only,
            # but keep this safety check.
            if not data["name"]:

                data["name"] = (
                    f"layer_{self.layer_index + 1}"
                    f"_agent_{len(agents) + 1}"
                )

            agents.append(data)

        return {
            "name": (
                f"layer_{self.layer_index + 1}"
            ),
            "agents": agents
        }


# ============================================================
# MAIN WINDOW
# ============================================================

class PaletteWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            "Palette - Multi-Agent "
            "Orchestration Framework"
        )

        self.resize(
            1500,
            900
        )

        self.process = None

        self.build_ui()

        self.load_existing_config()


    # ========================================================
    # BUILD UI
    # ========================================================

    def build_ui(self):

        central = QWidget()

        self.setCentralWidget(
            central
        )

        root = QVBoxLayout(
            central
        )

        root.setContentsMargins(
            14,
            14,
            14,
            14
        )

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        header = QHBoxLayout()

        title_box = QVBoxLayout()

        title = QLabel(
            "PALETTE"
        )

        title.setObjectName(
            "Title"
        )

        subtitle = QLabel(
            "Multi-Agent Orchestration Framework"
        )

        subtitle.setObjectName(
            "Subtitle"
        )

        title_box.addWidget(
            title
        )

        title_box.addWidget(
            subtitle
        )

        header.addLayout(
            title_box
        )

        header.addStretch()

        self.status_label = QLabel(
            "Ready"
        )

        self.status_label.setObjectName(
            "Status"
        )

        header.addWidget(
            self.status_label
        )

        root.addLayout(
            header
        )

        # ----------------------------------------------------
        # MAIN SPLITTER
        # ----------------------------------------------------

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        # ====================================================
        # LEFT SIDE
        # ====================================================

        left = QWidget()

        left_layout = QVBoxLayout(
            left
        )

        # ----------------------------------------------------
        # GENERAL CONFIG
        # ----------------------------------------------------

        general = QGroupBox(
            "1. General Configuration"
        )

        general_layout = QHBoxLayout(
            general
        )

        general_layout.addWidget(
            QLabel(
                "Number of Layers:"
            )
        )

        self.layer_count = QSpinBox()

        self.layer_count.setRange(
            1,
            10
        )

        self.layer_count.setValue(
            3
        )

        general_layout.addWidget(
            self.layer_count
        )

        general_layout.addStretch()

        left_layout.addWidget(
            general
        )

        # ----------------------------------------------------
        # LAYER CONFIGURATION
        # ----------------------------------------------------

        left_layout.addWidget(
            QLabel(
                "2. Layer Configuration"
            )
        )

        self.layers_scroll = QScrollArea()

        self.layers_scroll.setWidgetResizable(
            True
        )

        self.layers_container = QWidget()

        self.layers_layout = QVBoxLayout(
            self.layers_container
        )

        self.layers_scroll.setWidget(
            self.layers_container
        )

        left_layout.addWidget(
            self.layers_scroll,
            1
        )

        self.layer_count.valueChanged.connect(
            self.rebuild_layers
        )

        # ----------------------------------------------------
        # TASK
        # ----------------------------------------------------

        task_group = QGroupBox(
            "3. Task / Input"
        )

        task_layout = QVBoxLayout(
            task_group
        )

        self.task_edit = QTextEdit()

        self.task_edit.setPlaceholderText(
            "Enter the task/question for Palette..."
        )

        self.task_edit.setFixedHeight(
            100
        )

        self.task_edit.textChanged.connect(
            self.update_preview
        )

        task_layout.addWidget(
            self.task_edit
        )

        left_layout.addWidget(
            task_group
        )

        # ----------------------------------------------------
        # BUTTONS
        # ----------------------------------------------------

        buttons = QHBoxLayout()

        self.run_button = QPushButton(
            "▶  Run Palette"
        )

        self.run_button.setObjectName(
            "RunButton"
        )

        save_button = QPushButton(
            "💾  Save YAML"
        )

        load_button = QPushButton(
            "📂  Load YAML"
        )

        buttons.addWidget(
            self.run_button,
            2
        )

        buttons.addWidget(
            save_button
        )

        buttons.addWidget(
            load_button
        )

        left_layout.addLayout(
            buttons
        )

        # ====================================================
        # RIGHT SIDE
        # ====================================================

        right = QWidget()

        right_layout = QVBoxLayout(
            right
        )

        # ----------------------------------------------------
        # GRAPH
        # ----------------------------------------------------

        graph_group = QGroupBox(
            "Graph Visualization"
        )

        graph_layout = QVBoxLayout(
            graph_group
        )

        self.graph = GraphWidget()

        graph_layout.addWidget(
            self.graph
        )

        right_layout.addWidget(
            graph_group,
            2
        )

        # ----------------------------------------------------
        # OUTPUT TABS
        # ----------------------------------------------------

        self.tabs = QTabWidget()

        self.output = QTextEdit()

        self.output.setReadOnly(
            True
        )

        self.logs = QTextEdit()

        self.logs.setReadOnly(
            True
        )

        self.yaml_preview = QTextEdit()

        self.yaml_preview.setReadOnly(
            True
        )

        self.tabs.addTab(
            self.output,
            "Output"
        )

        self.tabs.addTab(
            self.logs,
            "Logs"
        )

        self.tabs.addTab(
            self.yaml_preview,
            "YAML Preview"
        )

        right_layout.addWidget(
            self.tabs,
            1
        )

        splitter.addWidget(
            left
        )

        splitter.addWidget(
            right
        )

        splitter.setSizes(
            [
                760,
                650
            ]
        )

        root.addWidget(
            splitter
        )

        # ----------------------------------------------------
        # BUTTON EVENTS
        # ----------------------------------------------------

        self.run_button.clicked.connect(
            self.run_palette
        )

        save_button.clicked.connect(
            self.save_yaml
        )

        load_button.clicked.connect(
            self.load_yaml
        )

        # ----------------------------------------------------
        # INITIAL LAYERS
        # ----------------------------------------------------

        self.rebuild_layers(
            3
        )


    # ========================================================
    # REBUILD LAYERS
    # ========================================================

    def rebuild_layers(
        self,
        count=None
    ):

        if count is None:
            count = self.layer_count.value()

        # Remove existing layer widgets
        while self.layers_layout.count():

            item = (
                self.layers_layout.takeAt(0)
            )

            widget = item.widget()

            if widget:
                widget.deleteLater()

        self.layer_cards = []

        for i in range(count):

            card = LayerCard(
                i
            )

            card.changed.connect(
                self.update_preview
            )

            self.layer_cards.append(
                card
            )

            self.layers_layout.addWidget(
                card
            )

        self.layers_layout.addStretch()

        self.update_preview()


    # ========================================================
    # BUILD CONFIG
    # ========================================================

    def get_config(self):

        agents = {}

        layers = []

        used_names = set()

        for layer_card in self.layer_cards:

            layer_data = (
                layer_card.get_data()
            )

            agent_names = []

            for agent in (
                layer_data["agents"]
            ):

                node_id = (
                    agent["name"].strip()
                )

                # Safety check
                if not node_id:

                    raise ValueError(
                        "Agent node ID cannot be empty."
                    )

                # LangGraph requires globally
                # unique node IDs.
                if node_id in used_names:

                    raise ValueError(
                        f"Duplicate node ID: "
                        f"'{node_id}'."
                    )

                used_names.add(
                    node_id
                )

                agent_names.append(
                    node_id
                )

                agent_config = {
                    "provider": (
                        agent["provider"]
                    ),
                    "model": (
                        agent["model"]
                    ),
                    "temperature": (
                        agent["temperature"]
                    ),
                    "role": (
                        agent["role"]
                    ),
                    "instructions": (
                        agent["instructions"]
                    ),
                }

                if agent["final"]:

                    agent_config[
                        "final"
                    ] = True

                agents[
                    node_id
                ] = agent_config

            layers.append(
                {
                    "name": layer_data["name"],
                    "agents": agent_names
                }
            )

        return {
            "task": (
                self.task_edit
                .toPlainText()
                .strip()
            ),
            "agents": agents,
            "layers": layers
        }


    # ========================================================
    # GRAPH DATA
    # ========================================================

    def get_graph_data(self):

        graph_layers = []

        for layer_card in (
            self.layer_cards
        ):

            layer_agents = []

            for card in (
                layer_card.agent_cards
            ):

                data = card.get_data()

                layer_agents.append(
                    {
                        "name": data["name"],
                        "provider": data["provider"],
                        "model": data["model"]
                    }
                )

            graph_layers.append(
                {
                    "name": (
                        f"Layer "
                        f"{layer_card.layer_index + 1}"
                    ),
                    "agents": layer_agents
                }
            )

        return graph_layers


    # ========================================================
    # UPDATE PREVIEW
    # ========================================================

    def update_preview(self):

        try:

            config = self.get_config()

            yaml_text = yaml.safe_dump(
                config,
                sort_keys=False,
                allow_unicode=True
            )

            self.yaml_preview.setPlainText(
                yaml_text
            )

            self.graph.set_layers(
                self.get_graph_data()
            )

        except Exception as e:

            self.yaml_preview.setPlainText(
                f"# Configuration error\n# {e}"
            )


    # ========================================================
    # SAVE YAML
    # ========================================================

    def save_yaml(self):

        try:

            config = self.get_config()

        except Exception as e:

            QMessageBox.warning(
                self,
                "Invalid Configuration",
                str(e)
            )

            return
        CONFIG_PATH.parent.mkdir(
           parents=True,
           exist_ok=True
         )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Palette YAML",
            str(CONFIG_PATH),
            "YAML Files (*.yaml *.yml)"
        )

        if not path:
            return

        try:

            with open(
                path,
                "w",
                encoding="utf-8"
            ) as file:

                yaml.safe_dump(
                    config,
                    file,
                    sort_keys=False,
                    allow_unicode=True
                )

            self.status_label.setText(
                "YAML saved"
            )

            self.logs.append(
                f"Saved YAML: {path}"
            )

        except Exception as e:

            QMessageBox.critical(
                self,
                "Save Error",
                str(e)
            )


    # ========================================================
    # LOAD YAML
    # ========================================================

    def load_yaml(self):
        CONFIG_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Palette YAML",
            str(CONFIG_PATH),
            "YAML Files (*.yaml *.yml)"
        )

        if not path:
            return

        try:

            with open(
                path,
                "r",
                encoding="utf-8"
            ) as file:

                config = yaml.safe_load(
                    file
                )

            if not isinstance(
                config,
                dict
            ):

                raise ValueError(
                    "YAML root must be a mapping."
                )

            self.apply_config(
                config
            )

            self.status_label.setText(
                "YAML loaded"
            )

            self.logs.append(
                f"Loaded YAML: {path}"
            )

        except Exception as e:

            QMessageBox.critical(
                self,
                "Load Error",
                str(e)
            )


    # ========================================================
    # LOAD EXISTING CONFIG
    # ========================================================

    def load_existing_config(self):

        if not CONFIG_PATH.exists():
            return

        try:

            with open(
                CONFIG_PATH,
                "r",
                encoding="utf-8"
            ) as file:

                config = yaml.safe_load(
                    file
                )

            if config:

                self.apply_config(
                    config
                )

        except Exception as e:

            self.logs.append(
                f"Could not load config.yaml: {e}"
            )


    # ========================================================
    # APPLY CONFIG TO GUI
    # ========================================================

    def apply_config(
        self,
        config
    ):

        layers = config.get(
            "layers",
            []
        )

        if not layers:

            layers = [
                {
                    "name": "layer_1",
                    "agents": [
                        "layer_1_agent_1"
                    ]
                }
            ]

        layer_count = min(
            10,
            max(
                1,
                len(layers)
            )
        )

        self.layer_count.blockSignals(
            True
        )

        self.layer_count.setValue(
            layer_count
        )

        self.layer_count.blockSignals(
            False
        )

        self.task_edit.blockSignals(
            True
        )

        self.task_edit.setPlainText(
            config.get(
                "task",
                ""
            )
        )

        self.task_edit.blockSignals(
            False
        )

        # Build layer cards with actual YAML
        # defaults.
        self._rebuild_layers_from_config(
            layers,
            config.get(
                "agents",
                {}
            )
        )

        self.update_preview()


    # ========================================================
    # REBUILD FROM YAML
    # ========================================================

    def _rebuild_layers_from_config(
        self,
        layers,
        agent_configs
    ):
        """
        Rebuild the GUI from YAML.

        LangGraph node IDs must be globally unique. Older YAML files
        may contain generic names such as agent_1 in multiple layers.
        We normalize those IDs here while preserving the agent's role,
        provider, model, instructions, etc.
        """

        while self.layers_layout.count():

            item = self.layers_layout.takeAt(0)

            widget = item.widget()

            if widget:
                widget.deleteLater()

        self.layer_cards = []

        used_ids = set()

        for layer_index, layer_data in enumerate(layers[:10]):

            agent_names = list(
                layer_data.get(
                    "agents",
                    []
                )
            )

            max_agents = (
                1
                if layer_index == 0
                else 2
            )

            agent_names = agent_names[
                :max_agents
            ]

            if not agent_names:
                agent_names = [
                    f"layer_{layer_index + 1}_agent_1"
                ]

            defaults = []

            for agent_index, old_name in enumerate(
                agent_names
            ):

                old_name = str(old_name)

                original = dict(
                    agent_configs.get(
                        old_name,
                        {}
                    )
                )

                # Prefer a clean, layer-scoped ID.
                # This also fixes old files containing
                # agent_1 / agent_2 repeatedly.
                candidate = (
                    f"layer_{layer_index + 1}"
                    f"_agent_{agent_index + 1}"
                )

                # If candidate somehow already exists,
                # keep adding a numeric suffix.
                unique_id = candidate
                suffix = 2

                while unique_id in used_ids:
                    unique_id = (
                        f"{candidate}_{suffix}"
                    )
                    suffix += 1

                used_ids.add(unique_id)

                original["name"] = unique_id

                defaults.append(original)

            layer_defaults = {
                "agents": defaults
            }

            card = LayerCard(
                layer_index,
                layer_defaults
            )

            card.changed.connect(
                self.update_preview
            )

            self.layer_cards.append(card)

            self.layers_layout.addWidget(
                card
            )

        self.layers_layout.addStretch()


    # ========================================================
    # RUN PALETTE
    # ========================================================

    def run_palette(self):

        if (
            self.process
            and self.process.state()
            != QProcess.ProcessState.NotRunning
        ):
            return

        try:
            config = self.get_config()

        except Exception as e:
            QMessageBox.warning(
                self,
                "Invalid Configuration",
                str(e)
            )
            return

        CONFIG_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        try:
            with open(
                CONFIG_PATH,
                "w",
                encoding="utf-8"
            ) as file:
                yaml.safe_dump(
                    config,
                    file,
                    sort_keys=False,
                    allow_unicode=True
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Configuration Error",
                str(e)
            )
            return

        self.output.clear()
        self.logs.clear()
        self.logs.append("Configuration saved.")
        self.logs.append("Starting Palette...")
        self.status_label.setText("Running...")
        self.run_button.setEnabled(False)

        self.process = QProcess(self)
        self.process.setWorkingDirectory(
            str(CONFIG_PATH.parent)
        )
        self.process.readyReadStandardOutput.connect(
            self.read_stdout
        )
        self.process.readyReadStandardError.connect(
            self.read_stderr
        )
        self.process.finished.connect(
            self.process_finished
        )
        self.process.errorOccurred.connect(
            self.process_error
        )
        self.process.start(
            sys.executable,
            [
                "-m",
                "palettle.cli",
                "--config",
                str(CONFIG_PATH)
            ]
        )

    # ========================================================
    # PROCESS OUTPUT
    # ========================================================

    def read_stdout(self):

        if not self.process:
            return

        data = bytes(
            self.process.readAllStandardOutput()
        ).decode(
            "utf-8",
            errors="replace"
        )

        if data.strip():
            self.output.append(data)

    def read_stderr(self):

        if not self.process:
            return

        data = bytes(
            self.process.readAllStandardError()
        ).decode(
            "utf-8",
            errors="replace"
        )

        if data.strip():
            self.output.append(
                f"<span style='color:#ff7b72'>"
                f"{data}"
                f"</span>"
            )

    def process_error(self, error):

        self.logs.append(
            f"Process error: {error}"
        )
        self.run_button.setEnabled(True)
        self.status_label.setText("Error")
        self.process = None

    def process_finished(self, exit_code, exit_status):

        self.run_button.setEnabled(True)

        if exit_code == 0:
            self.status_label.setText("Completed")
            self.logs.append(
                "Palette completed successfully."
            )
        else:
            self.status_label.setText("Error")
            self.logs.append(
                f"Palette exited with code {exit_code}."
            )

        self.process = None


# ============================================================
# APPLICATION STYLE
# ============================================================

def apply_style(app):

    app.setStyleSheet(
        """
        QWidget {
            background-color: #07111f;
            color: #e7eef9;
            font-family: "Segoe UI";
            font-size: 10pt;
        }

        QMainWindow {
            background-color: #07111f;
        }

        QGroupBox {
            border: 1px solid #263b5e;
            border-radius: 12px;
            margin-top: 12px;
            padding: 14px;
            background-color: #0b1728;
            font-weight: bold;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 7px;
            color: #9bb8ff;
        }

        QFrame#AgentCard {
            border: 1px solid #253b5f;
            border-radius: 9px;
            background-color: #0e1c31;
        }

        QLineEdit,
        QTextEdit,
        QComboBox,
        QSpinBox,
        QDoubleSpinBox {
            background-color: #0a1424;
            border: 1px solid #2d4265;
            border-radius: 7px;
            padding: 6px;
            color: #edf4ff;
        }

        QLineEdit:focus,
        QTextEdit:focus,
        QComboBox:focus,
        QSpinBox:focus,
        QDoubleSpinBox:focus {
            border: 1px solid #637cff;
        }

        QLineEdit:read-only {
            background-color: #111d31;
            color: #8fa3bf;
        }

        QComboBox QAbstractItemView {
            background-color: #0c182a;
            color: #edf4ff;
            selection-background-color: #354da8;
        }

        QPushButton {
            background-color: #162844;
            border: 1px solid #35527b;
            border-radius: 8px;
            padding: 9px 15px;
            color: #eef4ff;
            font-weight: 600;
        }

        QPushButton:hover {
            background-color: #21395d;
        }

        QPushButton:disabled {
            color: #65758e;
        }

        QPushButton#RunButton {
            background-color: #5b4de8;
            border: 1px solid #756aff;
            font-size: 11pt;
            padding: 11px;
        }

        QPushButton#RunButton:hover {
            background-color: #6d5cf2;
        }

        QLabel#Title {
            font-size: 25pt;
            font-weight: 800;
            color: #8d7bff;
        }

        QLabel#Subtitle {
            color: #8fa3bf;
            font-size: 10pt;
        }

        QLabel#Status {
            color: #76e4b5;
            font-weight: 600;
        }

        QTabWidget::pane {
            border: 1px solid #263b5e;
            border-radius: 9px;
            background-color: #0b1728;
        }

        QTabBar::tab {
            background-color: #0e1c31;
            color: #91a4bf;
            padding: 9px 18px;
            border: 1px solid #263b5e;
            border-bottom: none;
        }

        QTabBar::tab:selected {
            color: #ffffff;
            background-color: #172846;
        }

        QScrollBar:vertical {
            background: #091423;
            width: 10px;
        }

        QScrollBar::handle:vertical {
            background: #2c4265;
            border-radius: 5px;
        }
        """
    )


# ============================================================
# ENTRY POINT
# ============================================================

def main():

    app = QApplication(
        sys.argv
    )

    apply_style(
        app
    )

    window = PaletteWindow()

    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()
