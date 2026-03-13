from PySide6 import QtCore, QtWidgets
import idaapi
import json
from librift_ida.rift_controller import RiftController
from librift.rustmeta import RustMetadata

TARGET_MAP = {
  "aarch64": [
    "apple-darwin", "apple-ios", "apple-ios-macabi", "apple-ios-sim",
    "linux-android", "pc-windows-gnullvm", "pc-windows-msvc",
    "unknown-fuchsia", "unknown-linux-gnu", "unknown-linux-musl",
    "unknown-linux-ohos", "unknown-none", "unknown-none-softfloat", "unknown-uefi"
  ],
  "arm": [
    "linux-androideabi", "unknown-linux-gnueabi", "unknown-linux-gnueabihf",
    "unknown-linux-musleabi", "unknown-linux-musleabihf"
  ],
  "arm64ec": ["pc-windows-msvc"],
  "armebv7r": ["none-eabi", "none-eabihf"],
  "armv5te": ["unknown-linux-gnueabi", "unknown-linux-musleabi"],
  "armv7": [
    "linux-androideabi", "unknown-linux-gnueabi", "unknown-linux-gnueabihf",
    "unknown-linux-musleabi", "unknown-linux-musleabihf", "unknown-linux-ohos"
  ],
  "armv7a": ["none-eabi"],
  "armv7r": ["none-eabi", "none-eabihf"],
  "i586": ["unknown-linux-gnu", "unknown-linux-musl"],
  "i686": [
    "linux-android", "pc-windows-gnu", "pc-windows-gnullvm", "pc-windows-msvc",
    "unknown-freebsd", "unknown-linux-gnu", "unknown-linux-musl", "unknown-uefi"
  ],
  "loongarch64": [
    "unknown-linux-gnu", "unknown-linux-musl", "unknown-none", "unknown-none-softfloat"
  ],
  "nvptx64": ["nvidia-cuda"],
  "powerpc": ["unknown-linux-gnu"],
  "powerpc64": ["unknown-linux-gnu"],
  "powerpc64le": ["unknown-linux-gnu", "unknown-linux-musl"],
  "riscv32i": ["unknown-none-elf"],
  "riscv32im": ["unknown-none-elf"],
  "riscv32imac": ["unknown-none-elf"],
  "riscv32imafc": ["unknown-none-elf"],
  "riscv32imc": ["unknown-none-elf"],
  "riscv64gc": ["unknown-linux-gnu", "unknown-linux-musl", "unknown-none-elf"],
  "riscv64imac": ["unknown-none-elf"],
  "s390x": ["unknown-linux-gnu"],
  "sparc64": ["unknown-linux-gnu"],
  "sparcv9": ["sun-solaris"],
  "thumbv6m": ["none-eabi"],
  "thumbv7em": ["none-eabi", "none-eabihf"],
  "thumbv7m": ["none-eabi"],
  "thumbv7neon": ["linux-androideabi", "unknown-linux-gnueabihf"],
  "thumbv8m.base": ["none-eabi"],
  "thumbv8m.main": ["none-eabi", "none-eabihf"],
  "wasm32": ["unknown-emscripten", "unknown-unknown", "wasip1", "wasip1-threads", "wasip2"],
  "wasm32v1": ["none"],
  "x86_64": [
    "apple-darwin", "apple-ios", "apple-ios-macabi", "fortanix-unknown-sgx",
    "linux-android", "pc-solaris", "pc-windows-gnu", "pc-windows-gnullvm",
    "pc-windows-msvc", "unknown-freebsd", "unknown-fuchsia", "unknown-illumos",
    "unknown-linux-gnu", "unknown-linux-gnux32", "unknown-linux-musl",
    "unknown-linux-ohos", "unknown-netbsd", "unknown-none", "unknown-redox", "unknown-uefi"
  ]
}

class RiftIdaForm(idaapi.PluginForm):

    def __init__(self, core, logger, rustmeta):
        super().__init__()
        self.core = core
        self.rustmeta = rustmeta
        self.logger = logger

        self.triple_suffix_combo = None
        self.commithash_edit = None
        self.rustver_edit = None
        self.arch_edit = None
        self.crates_table = None
        self.relmode_box = None
        self.compiler_flirt_box = None
        self.rust_compiler_field = None
        self.use_custom_fields = None
        self.parent = None
        
        # Arch changed
        self._arch_changed = False
        # Target triple changed
        self._target_triple_changed = False
        # use custom set values
        self._use_custom_set_values = False

        # RiftController, to kick off multithreading work
        self.rift_controller = RiftController(rift_core=self.core, logger=self.logger)

    def OnCreate(self, form):
        self.parent = self.FormToPyQtWidget(form)
        self.PopulateForm()
        self.logger.info("Populating form done!")

    def PopulateForm(self):

        # Initialize VBox
        layout = QtWidgets.QFormLayout()
        layout.setContentsMargins(3,3,3,3)
        layout.setSpacing(10)

        # Rust Git Commithash
        self.commithash_edit = QtWidgets.QLineEdit(self.rustmeta.commithash)
        self.commithash_edit.setMaxLength(0x28)
        rust_version = self.rustmeta.get_channel()
        if rust_version is None:
            rust_version = "NOT_IDENTIFIED"
        self.rustver_edit = QtWidgets.QLineEdit(rust_version)

        # Rust Target triple
        self.triple_suffix_combo = QtWidgets.QComboBox()
        self.triple_suffix_combo.addItems(TARGET_MAP[self.rustmeta.arch])
        triple_suffix = self.rustmeta.get_triple_suffix()
        if triple_suffix is None:
            triple_suffix = "NOT_IDENTIFIED"
        self.triple_suffix_combo.setCurrentText(triple_suffix)
        self.triple_suffix_combo.currentTextChanged.connect(self.onTargetTripleSuffixChanged)

        # Architecture
        self.arch_edit = QtWidgets.QComboBox()
        self.arch_edit.addItems(list(TARGET_MAP.keys()))
        self.arch_edit.setCurrentText(self.rustmeta.arch)
        self.arch_edit.currentTextChanged.connect(self.onArchSelectionChanged)

        # Dependencies
        # --- Dependencies as a table instead of QTextEdit ---
        self.crates_table = QtWidgets.QTableWidget()
        self.crates_table.setColumnCount(3)
        self.crates_table.setHorizontalHeaderLabels(["Name", "Version", "Apply FLIRT"])
        self.crates_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)  # prevent inline editing for text cells
        self.crates_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.crates_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.crates_table.verticalHeader().setVisible(False)
        self.crates_table.setAlternatingRowColors(True)

        # Optional: nicer header resize behavior
        header = self.crates_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)   # Name stretches
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # Version fits content
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)  # Checkbox column fits

        # Rust compiler field
        self.rust_compiler_field = QtWidgets.QLineEdit(self.rustmeta.get_target_compiler())
        self.rust_compiler_field.setReadOnly(True)
        self.rust_compiler_field.setFrame(False)
        self.rust_compiler_field.setStyleSheet("background: transparent;")

        # Server option field
        servers_opts_layout = QtWidgets.QHBoxLayout()
        self.status_server = QtWidgets.QLabel()
        if self.core.rift_server_available():
            self.set_server_status_available()
        else:
            self.set_server_status_unavailable()
        self.enable_cb = QtWidgets.QCheckBox("Enable Server") 
        self.enable_cb.setChecked(False) 
        self.silent_cb = QtWidgets.QCheckBox("Apply FLIRT silently (Not supported yet)") 
        self.silent_cb.setChecked(False) 
        servers_opts_layout.addWidget(self.status_server, 1) 
        servers_opts_layout.addWidget(self.enable_cb, 1) 
        servers_opts_layout.addWidget(self.silent_cb, 1)

        # Compiler options
        opts_layout = QtWidgets.QHBoxLayout()
        self.relmode_box = QtWidgets.QCheckBox("Compile Release Mode")
        self.relmode_box.setChecked(True)
        self.compiler_flirt_box = QtWidgets.QCheckBox("Generate compiler FLIRT signatures")
        self.compiler_flirt_box.setChecked(True)
        self.use_custom_fields = QtWidgets.QCheckBox("Use custom set values (Experimental)")
        self.use_custom_fields.setChecked(False)
        opts_layout.addWidget(self.relmode_box)
        opts_layout.addWidget(self.compiler_flirt_box)
        opts_layout.addWidget(self.use_custom_fields)

        # Populate the table from self.rustmeta.crates
        crates = self.rustmeta.get_crates()
        self.crates_table.setRowCount(len(crates))

        for row, crate in enumerate(crates):
            name_item = QtWidgets.QTableWidgetItem(crate.name)
            name_item.setFlags(name_item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.crates_table.setItem(row, 0, name_item)

            # TODO: Version should be editable
            ver_item = QtWidgets.QTableWidgetItem(crate.version)
            ver_item.setFlags(ver_item.flags() | QtCore.Qt.ItemIsEditable)
            self.crates_table.setItem(row, 1, ver_item)

            flirt_item = QtWidgets.QTableWidgetItem()
            flirt_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsSelectable)
            flirt_item.setCheckState(QtCore.Qt.Checked)  # default to checked
            flirt_item.setText("")  # keep cell clean; checkbox only
            self.crates_table.setItem(row, 2, flirt_item)           

        # Buttons
        btn_apply = QtWidgets.QPushButton("Apply FLIRT")
        btn_apply.clicked.connect(self.onApply)
        btn_export = QtWidgets.QPushButton("Export Metadata")
        btn_export.clicked.connect(self.onExport)
        btn_configure = QtWidgets.QPushButton("Configure")
        btn_configure.clicked.connect(self.onConfigure)
        btn_cancel = QtWidgets.QPushButton("Cancel")
        btn_cancel.clicked.connect(self.onCancel)

        # All buttons in horizontal box
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(btn_apply)
        button_layout.addWidget(btn_cancel)
        button_layout.addWidget(btn_configure)
        button_layout.addWidget(btn_export)

        # Build the layout
        layout.addRow("Rust Git Commithash: ", self.commithash_edit)
        layout.addRow("Rust Version: ", self.rustver_edit)
        layout.addRow("Target Triple: ", self.triple_suffix_combo)
        layout.addRow("Architecture: ", self.arch_edit)
        layout.addRow("Compiler Options: ", opts_layout)
        layout.addRow("Server Options: ", servers_opts_layout)
        layout.addRow("Identified Rust Compiler: ", self.rust_compiler_field)
        layout.addRow("Dependencies", self.crates_table)
        layout.addRow(button_layout)

        # make our created layout the dialogs layout
        self.parent.setLayout(layout)

    def set_server_status_unavailable(self):
        self.status_server.setText("Rift Server: Not available")
        self.status_server.setStyleSheet("color: red; font-weight: 600;")

    def set_server_status_available(self):
        self.status_server.setText("Rift Server: Available")
        self.status_server.setStyleSheet("color: green; font-weight: 600;")

    # If apply is clicked, RiftForm reaches out to Rift Server if available and applies the signatures silently or not
    def onApply(self):

        if not self.enable_cb.isChecked():
            self.logger.error("Enable Server is not set. Enable to start generating FLIRT signatures")
            return 0
        if not self.core.rift_server_available():
            self.logger.info(f"RIFT Server not available! Only exporting as JSON supported. Click Export to export as JSON.")
            return 0
        # if self.use_custom_fields.isChecked():
        #     self.logger.info(f"Custom values not supported yet! Use rift_cli until the Ida Plugin supports generating flirt signatures for custom set values")
        #     return 0
    
        self.logger.info(f"Generating FLIRT signatures..")
        folder = QtWidgets.QFileDialog().getExistingDirectory(self.parent,
                                                              "Select Folder",
                                                              "",
                                                              QtWidgets.QFileDialog.ShowDirsOnly)
        if not folder:
            self.logger.warning("No folder selected, aborting")
        else:
            #TODO: Confusing, rather name this compile_release_mode
            debug_build = True
            if not self.relmode_box.isChecked():
                debug_build = False
            # apply silent hardcoded to False for now
            self.rift_controller.start_apply(folder, self.__get_rustmeta(), parent_widget=None, apply_silent=False, debug_build=debug_build)
        
        return 1
      
    def onCancel(self):
        self.logger.info("Cancel clicked, closing form")
        self.Close(0)
        return 1

    # TODO: Needs to update RustMeta by self provided information
    def onConfigure(self):
        if self.core.rift_server_available():
            self.set_server_status_available()
        else:
            self.set_server_status_unavailable()
        return 1
    
    
    def onArchSelectionChanged(self, text):
        """Changes the triple_suffix depending on the selected architecture."""
        self.triple_suffix_combo.clear()
        self.triple_suffix_combo.addItems(TARGET_MAP[text])
        self._arch_changed = True
        self._use_custom_set_values = True
        self.use_custom_fields.setChecked(True)
    
    def onTargetTripleSuffixChanged(self, text):
        """Changes the selected target triple"""
        self._target_triple_changed = True
        self._use_custom_set_values = True
        self.use_custom_fields.setChecked(True)

    def onExport(self):
        """Dump the RustMeta information as a JSON file"""
        file_path, _ = QtWidgets.QFileDialog().getSaveFileName(self.parent, "Save File", "")
        self.logger.info(f"Storing extracted information at {file_path}")
        json_data = self.__get_rustmeta().to_dict()
        if file_path != "":
            with open(file_path, "w+", encoding="utf-8") as f:
                json.dump(json_data, f, ensure_ascii=False, indent=4)
        return 1
    
    def __get_rustmeta(self):
        if not self.use_custom_fields.isChecked():
            return self.rustmeta

        commithash = self.commithash_edit.text().strip()
        arch = self.arch_edit.currentText()
        triple_suffix = self.triple_suffix_combo.currentText()
        target_triple = f"{arch}-{triple_suffix}"

        # Reconstruct version fields from the channel string shown in the GUI
        channel_text = self.rustver_edit.text().strip()
        if channel_text.startswith("nightly-"):
            rust_version = "nightly"
            ts = channel_text[len("nightly-"):]
            version_short = channel_text
        else:
            rust_version = channel_text
            version_short = channel_text
            ts = None

        # Collect only rows whose "Apply FLIRT" checkbox is checked
        crates = []
        for row in range(self.crates_table.rowCount()):
            flirt_item = self.crates_table.item(row, 2)
            if flirt_item and flirt_item.checkState() == QtCore.Qt.Checked:
                name = self.crates_table.item(row, 0).text()
                version = self.crates_table.item(row, 1).text()
                crates.append(f"{name}-{version}")

        meta = RustMetadata(
            commithash=commithash,
            arch=arch,
            target_triple=target_triple,
            rust_version=rust_version,
            version_short=version_short,
            ts=ts,
            filetype=self.rustmeta.filetype,
            crates=crates,
        )
        meta.compiler = meta.get_compiler_from_target_triple(target_triple)

        self.rustmeta = meta
        return self.rustmeta