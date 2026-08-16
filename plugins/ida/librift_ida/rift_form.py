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
        """Initialize form state and widget references."""
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
        self.btn_add_dep = None
        self.btn_remove_dep = None
        self.parent = None
        
        # Arch changed
        self._arch_changed = False
        # Target triple changed
        self._target_triple_changed = False
        # use custom set values
        self._use_custom_set_values = False
        # track which custom fields the user has manually edited
        self._commithash_edited = False
        self._rustver_edited = False

        # RiftController, to kick off multithreading work
        self.rift_controller = RiftController(rift_core=self.core, logger=self.logger)

    def OnCreate(self, form):
        self.parent = self.FormToPyQtWidget(form)
        self.PopulateForm()
        self.logger.info("Populating form done!")

    def formToDefault(self):
        """Updates the current form to default"""
        self.commithash_edit.setText(self.rustmeta.commithash or "")

        rust_version = self.rustmeta.get_channel()
        self.rustver_edit.setText(rust_version if rust_version is not None else "NOT_IDENTIFIED")

        self.arch_edit.setCurrentText(self.rustmeta.arch)

        self.triple_suffix_combo.clear()
        self.triple_suffix_combo.addItems(TARGET_MAP[self.rustmeta.arch])
        triple_suffix = self.rustmeta.get_triple_suffix()
        self.triple_suffix_combo.setCurrentText(triple_suffix if triple_suffix is not None else "NOT_IDENTIFIED")

        self.rust_compiler_field.setText(self.rustmeta.get_target_compiler())
        self._commithash_edited = False
        self._rustver_edited = False


    def PopulateForm(self):
        """Build and arrange all widgets in the form layout."""

        # Initialize VBox
        layout = QtWidgets.QFormLayout()
        layout.setContentsMargins(3,3,3,3)
        layout.setSpacing(10)

        # Rust Git Commithash
        self.commithash_edit = QtWidgets.QLineEdit(self.rustmeta.commithash)
        self.commithash_edit.setMaxLength(0x28)
        self.commithash_edit.setReadOnly(True)
        self.commithash_edit.textEdited.connect(lambda _: setattr(self, '_commithash_edited', True))
        rust_version = self.rustmeta.get_channel()
        if rust_version is None:
            rust_version = "NOT_IDENTIFIED"
        self.rustver_edit = QtWidgets.QLineEdit(rust_version)
        self.rustver_edit.setReadOnly(True)
        self.rustver_edit.textEdited.connect(lambda _: setattr(self, '_rustver_edited', True))
        self.rustver_edit.textChanged.connect(lambda _: self._update_compiler_field())

        # Rust Target triple
        self.triple_suffix_combo = QtWidgets.QComboBox()
        self.triple_suffix_combo.addItems(TARGET_MAP[self.rustmeta.arch])
        triple_suffix = self.rustmeta.get_triple_suffix()
        if triple_suffix is None:
            triple_suffix = "NOT_IDENTIFIED"
        self.triple_suffix_combo.setCurrentText(triple_suffix)
        self.triple_suffix_combo.currentTextChanged.connect(self.onTargetTripleSuffixChanged)
        self.triple_suffix_combo.currentTextChanged.connect(lambda _: self._update_compiler_field())
        self.triple_suffix_combo.setEnabled(False)

        # Architecture
        self.arch_edit = QtWidgets.QComboBox()
        self.arch_edit.addItems(list(TARGET_MAP.keys()))
        self.arch_edit.setCurrentText(self.rustmeta.arch)
        self.arch_edit.currentTextChanged.connect(self.onArchSelectionChanged)
        self.arch_edit.currentTextChanged.connect(lambda _: self._update_compiler_field())
        self.arch_edit.setEnabled(False)

        # Dependencies
        # --- Dependencies as a table instead of QTextEdit ---
        self.crates_table = QtWidgets.QTableWidget()
        self.crates_table.setColumnCount(3)
        self.crates_table.setHorizontalHeaderLabels(["Name", "Version", "Apply FLIRT"])
        self.crates_table.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked)
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
        self.enable_cb.stateChanged.connect(self.onEnableServerChanged)
        self.silent_cb = QtWidgets.QCheckBox("Apply FLIRT silently")
        self.silent_cb.setChecked(True)
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
        self.use_custom_fields.stateChanged.connect(self.onUseCustomFieldsChanged)
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

            ver_item = QtWidgets.QTableWidgetItem(crate.version)
            ver_item.setFlags(ver_item.flags() | QtCore.Qt.ItemIsEditable)
            self.crates_table.setItem(row, 1, ver_item)

            flirt_item = QtWidgets.QTableWidgetItem()
            flirt_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsSelectable)
            flirt_item.setCheckState(QtCore.Qt.Checked)  # default to checked
            flirt_item.setText("")  # keep cell clean; checkbox only
            self.crates_table.setItem(row, 2, flirt_item)           

        # Add / Remove dependency buttons (active only in custom-values mode)
        self.btn_add_dep = QtWidgets.QPushButton("Add Dependency")
        self.btn_add_dep.clicked.connect(self.onAddDependency)
        self.btn_add_dep.setEnabled(False)
        self.btn_remove_dep = QtWidgets.QPushButton("Remove Selected")
        self.btn_remove_dep.clicked.connect(self.onRemoveDependency)
        self.btn_remove_dep.setEnabled(False)
        dep_btn_layout = QtWidgets.QHBoxLayout()
        dep_btn_layout.addStretch()
        dep_btn_layout.addWidget(self.btn_add_dep)
        dep_btn_layout.addWidget(self.btn_remove_dep)

        # Buttons
        btn_apply = QtWidgets.QPushButton("Apply FLIRT")
        btn_apply.clicked.connect(self.onApply)
        btn_export = QtWidgets.QPushButton("Export Metadata")
        btn_export.clicked.connect(self.onExport)
        btn_configure = QtWidgets.QPushButton("Reset")
        btn_configure.clicked.connect(self.onReset)
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
        layout.addRow("Configured Rust Compiler: ", self.rust_compiler_field)
        layout.addRow("Dependencies", self.crates_table)
        layout.addRow(dep_btn_layout)

        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addRow(separator)

        layout.addRow(button_layout)

        # make our created layout the dialogs layout
        self.parent.setLayout(layout)

    def onEnableServerChanged(self, state):
        """Verify server availability when Enable Server is checked; uncheck and log if unavailable."""
        if not state:
            return
        if self.core.rift_server_available():
            self.logger.info("RIFT Server is available — server mode enabled")
            self.set_server_status_available()
        else:
            self.logger.error("RIFT Server is not available — server mode has been disabled")
            self.enable_cb.blockSignals(True)
            self.enable_cb.setChecked(False)
            self.enable_cb.blockSignals(False)
            self.set_server_status_unavailable()

    def set_server_status_unavailable(self):
        """Set the server status label to unavailable (red)."""
        self.status_server.setText("Rift Server: Not available")
        self.status_server.setStyleSheet("color: red; font-weight: 600;")

    def set_server_status_available(self):
        """Set the server status label to available (green)."""
        self.status_server.setText("Rift Server: Available")
        self.status_server.setStyleSheet("color: green; font-weight: 600;")

    def onApply(self):
        """Request FLIRT signature generation from the server for the selected output folder."""

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
            self.rift_controller.start_apply(folder, self.__get_rustmeta(), parent_widget=None, apply_silent=self.silent_cb.isChecked(), debug_build=debug_build)
        
        return 1
      
    def onCancel(self):
        """Close the form without applying any changes."""
        self.logger.info("Cancel clicked, closing form")
        self.Close(0)
        return 1

    def onReset(self):
        """Uncheck custom values and restore all fields to the originally extracted metadata."""
        if self.core.rift_server_available():
            self.set_server_status_available()
        else:
            self.set_server_status_unavailable()
        # Uncheck custom values and restore all fields to their original extracted values
        self.use_custom_fields.setChecked(False)
        self.formToDefault()
        return 1
    
    
    def onUseCustomFieldsChanged(self, _state):
        """Enable or disable editable metadata fields based on the custom values checkbox."""
        enabled = self.use_custom_fields.isChecked()
        self._use_custom_set_values = enabled
        self.commithash_edit.setReadOnly(not enabled)
        self.rustver_edit.setReadOnly(not enabled)
        self.arch_edit.setEnabled(enabled)
        self.triple_suffix_combo.setEnabled(enabled)
        self.btn_add_dep.setEnabled(enabled)
        self.btn_remove_dep.setEnabled(enabled)
        if not enabled:
            self._commithash_edited = False
            self._rustver_edited = False

    def _update_compiler_field(self):
        """Recompute and display the configured Rust compiler string from current form values."""
        arch = self.arch_edit.currentText()
        triple_suffix = self.triple_suffix_combo.currentText()
        rust_ver = self.rustver_edit.text().strip()
        self.rust_compiler_field.setText(f"{rust_ver}-{arch}-{triple_suffix}")

    def onAddDependency(self):
        """Append a blank editable dependency row to the crates table."""
        row = self.crates_table.rowCount()
        self.crates_table.insertRow(row)

        name_item = QtWidgets.QTableWidgetItem("")
        name_item.setFlags(name_item.flags() | QtCore.Qt.ItemIsEditable)
        self.crates_table.setItem(row, 0, name_item)

        ver_item = QtWidgets.QTableWidgetItem("")
        ver_item.setFlags(ver_item.flags() | QtCore.Qt.ItemIsEditable)
        self.crates_table.setItem(row, 1, ver_item)

        flirt_item = QtWidgets.QTableWidgetItem()
        flirt_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsSelectable)
        flirt_item.setCheckState(QtCore.Qt.Checked)
        flirt_item.setText("")
        self.crates_table.setItem(row, 2, flirt_item)

        self.crates_table.setCurrentCell(row, 0)
        self.crates_table.editItem(name_item)

    def onRemoveDependency(self):
        """Remove the currently selected row from the crates table."""
        row = self.crates_table.currentRow()
        if row >= 0:
            self.crates_table.removeRow(row)

    def onArchSelectionChanged(self, text):
        """Changes the triple_suffix depending on the selected architecture."""
        self.triple_suffix_combo.clear()
        self.triple_suffix_combo.addItems(TARGET_MAP[text])
        self._arch_changed = True

    def onTargetTripleSuffixChanged(self, _text):
        """Changes the selected target triple"""
        self._target_triple_changed = True

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
        """Return the active RustMetadata, building it from custom form values if custom mode is on."""
        # Collect only rows whose "Apply FLIRT" checkbox is checked. This must apply
        # regardless of custom-values mode, since the checkboxes are editable either way.
        crates = []
        for row in range(self.crates_table.rowCount()):
            flirt_item = self.crates_table.item(row, 2)
            if flirt_item and flirt_item.checkState() == QtCore.Qt.Checked:
                name = self.crates_table.item(row, 0).text()
                version = self.crates_table.item(row, 1).text()
                crates.append(f"{name}-{version}")

        if not self.use_custom_fields.isChecked():
            self.rustmeta.crates = set(crates)
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
