"""
Hax Exporter Settings - Main Settings Dialog
Compatible with Maya 2025 (Python 3, PySide6) and Maya 2022- (Python 2, PySide2)

This is the main settings dialog that hosts game-specific export process plugins.
Game-specific scripts (ExportProcess_*.py) register themselves with this system.
"""

from __future__ import print_function
import sys
import os
import json
import glob

# Maya imports
import maya.cmds as cmds
import maya.OpenMayaUI as omui

# PySide compatibility for Maya versions
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance
    PYSIDE_VERSION = 6
except ImportError:
    try:
        from PySide2 import QtCore, QtGui, QtWidgets
        from shiboken2 import wrapInstance
        PYSIDE_VERSION = 2
    except ImportError:
        PYSIDE_VERSION = None

# Settings storage
SETTINGS_NODE = "haxExportProcessSettings"

# Registry of available export processes
# Each entry: {"id": str, "name": str, "widget_class": class, "process_func": callable}
_registered_processes = {}


def maya_main_window():
    """Return the Maya main window widget"""
    main_window_ptr = omui.MQtUtil.mainWindow()
    if sys.version_info.major >= 3:
        return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)
    else:
        return wrapInstance(long(main_window_ptr), QtWidgets.QWidget)


def log_message(message):
    """Log a message"""
    print("[ExportProcess] " + str(message))


def get_settings_node():
    """Get or create settings storage node"""
    if not cmds.objExists(SETTINGS_NODE):
        cmds.createNode("script", name=SETTINGS_NODE)
    return SETTINGS_NODE


def get_export_process():
    """Get the current export process setting"""
    try:
        node = get_settings_node()
        if cmds.attributeQuery("exportProcess", node=node, exists=True):
            return cmds.getAttr(node + ".exportProcess") or "default"
    except:
        pass
    return "default"


def set_export_process(process_id):
    """Set the current export process"""
    try:
        node = get_settings_node()
        if not cmds.attributeQuery("exportProcess", node=node, exists=True):
            cmds.addAttr(node, longName="exportProcess", dataType="string")
        cmds.setAttr(node + ".exportProcess", process_id, type="string")
    except Exception as e:
        log_message("Error setting export process: %s" % str(e))


def get_verbose_logging():
    """Get verbose logging setting"""
    try:
        node = get_settings_node()
        if cmds.attributeQuery("verboseLogging", node=node, exists=True):
            return cmds.getAttr(node + ".verboseLogging")
    except:
        pass
    return False


def set_verbose_logging(enabled):
    """Set verbose logging setting"""
    try:
        node = get_settings_node()
        if not cmds.attributeQuery("verboseLogging", node=node, exists=True):
            cmds.addAttr(node, longName="verboseLogging", attributeType="bool")
        cmds.setAttr(node + ".verboseLogging", enabled)
    except Exception as e:
        log_message("Error setting verbose logging: %s" % str(e))


def register_export_process(process_id, display_name, widget_class, process_func):
    """
    Register an export process with the settings system.
    
    Args:
        process_id: Unique identifier (e.g., "skyrim")
        display_name: Display name for dropdown (e.g., "Skyrim (FBX → HKX)")
        widget_class: QWidget subclass for settings UI (or None)
        process_func: Function to call after export (receives list of FBX paths)
    """
    _registered_processes[process_id] = {
        "id": process_id,
        "name": display_name,
        "widget_class": widget_class,
        "process_func": process_func
    }
    log_message("Registered export process: %s" % display_name)


def get_registered_processes():
    """Get all registered export processes"""
    return _registered_processes.copy()


def discover_and_load_processes():
    """
    Discover and load all ExportProcess_*.py scripts in the Process folder.
    Each script should call register_export_process() when loaded.
    """
    import traceback
    
    # Clear existing registrations
    _registered_processes.clear()
    
    # Find the Process folder
    process_folder = os.path.dirname(os.path.abspath(__file__))
    
    # Add the Process folder to sys.path so imports work
    if process_folder not in sys.path:
        sys.path.insert(0, process_folder)
    
    # Make this module available for import by other scripts
    # This allows ExportProcess_*.py to do "import HaxExporterSettings"
    # We need to find the current module in sys.modules (it might be under different names)
    current_module = None
    for mod_name, mod in list(sys.modules.items()):
        if mod is not None and hasattr(mod, '__file__') and mod.__file__:
            try:
                if os.path.normpath(mod.__file__) == os.path.normpath(__file__):
                    current_module = mod
                    break
            except:
                pass
    
    # If we found ourselves, register under the expected name
    if current_module:
        sys.modules['HaxExporterSettings'] = current_module
    else:
        # Create a simple namespace object with what we need
        import types
        fake_module = types.ModuleType('HaxExporterSettings')
        fake_module.register_export_process = register_export_process
        fake_module.get_settings_node = get_settings_node
        fake_module.get_export_process = get_export_process
        fake_module.get_verbose_logging = get_verbose_logging
        fake_module.log_message = log_message
        fake_module.maya_main_window = maya_main_window
        sys.modules['HaxExporterSettings'] = fake_module
    
    # Find all ExportProcess_*.py files (except this one)
    pattern = os.path.join(process_folder, "ExportProcess_*.py")
    exclude_files = ["HaxExporterSettings.py"]
    
    log_message("Searching for export processes in: %s" % process_folder)
    found_files = glob.glob(pattern)
    log_message("Found %d ExportProcess_*.py files" % len(found_files))
    
    for script_path in found_files:
        script_name = os.path.basename(script_path)
        if script_name in exclude_files:
            continue
        
        try:
            log_message("Loading export process: %s" % script_name)
            module_name = script_name[:-3]  # Remove .py
            
            if sys.version_info[0] >= 3:
                import importlib.util
                spec = importlib.util.spec_from_file_location(module_name, script_path)
                module = importlib.util.module_from_spec(spec)
                # Add to sys.modules before exec to allow circular imports
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            else:
                import imp
                module = imp.load_source(module_name, script_path)
            
            log_message("Successfully loaded: %s" % script_name)
            
        except Exception as e:
            log_message("Error loading %s: %s" % (script_name, str(e)))
            log_message(traceback.format_exc())


def process_exported_files(fbx_paths):
    """
    Process exported FBX files using the selected export process.
    Called by the main exporter after export completes.
    
    Returns: True if successful, False if errors occurred
    """
    process_id = get_export_process()
    
    if process_id == "default":
        return True  # Nothing to do
    
    # Make sure processes are loaded
    if not _registered_processes:
        discover_and_load_processes()
    
    if process_id not in _registered_processes:
        log_message("Export process '%s' not found" % process_id)
        return True
    
    process_info = _registered_processes[process_id]
    process_func = process_info.get("process_func")
    
    if process_func:
        try:
            return process_func(fbx_paths)
        except Exception as e:
            log_message("Error in export process: %s" % str(e))
            return False
    
    return True


def is_verbose_logging_enabled():
    """Check if verbose logging is enabled"""
    return get_verbose_logging()


class ExportProcessDialog(QtWidgets.QDialog):
    """Main settings dialog for Export Process selection"""
    
    def __init__(self, parent=maya_main_window()):
        super(ExportProcessDialog, self).__init__(parent)
        
        self.setWindowTitle("Export Process Settings")
        self.setMinimumWidth(520)
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowCloseButtonHint)
        
        # Load available processes
        discover_and_load_processes()
        
        # Store widget instances
        self.process_widgets = {}
        
        self.create_ui()
        self.load_settings()
    
    def create_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # Export Process dropdown
        process_layout = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel("Export Process:")
        label.setStyleSheet("font-size: 11pt; font-weight: bold;")
        process_layout.addWidget(label)
        
        self.process_combo = QtWidgets.QComboBox()
        self.process_combo.addItem("Default", "default")
        
        # Add registered processes
        log_message("Building dropdown - %d registered processes" % len(_registered_processes))
        for proc_id, proc_info in sorted(_registered_processes.items()):
            log_message("  Adding process: %s (%s)" % (proc_id, proc_info["name"]))
            self.process_combo.addItem(proc_info["name"], proc_id)
        
        self.process_combo.setMinimumWidth(250)
        self.process_combo.currentIndexChanged.connect(self.on_process_changed)
        process_layout.addWidget(self.process_combo)
        process_layout.addStretch()
        layout.addLayout(process_layout)
        
        # Separator
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(sep)
        
        # Container for process-specific widgets
        self.widget_container = QtWidgets.QWidget()
        self.widget_layout = QtWidgets.QVBoxLayout(self.widget_container)
        self.widget_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.widget_container)
        
        # Create widgets for each registered process
        for proc_id, proc_info in _registered_processes.items():
            widget_class = proc_info.get("widget_class")
            if widget_class:
                try:
                    widget = widget_class()
                    widget.setVisible(False)
                    self.widget_layout.addWidget(widget)
                    self.process_widgets[proc_id] = widget
                except Exception as e:
                    log_message("Error creating widget for %s: %s" % (proc_id, str(e)))
        
        # Default label (shown when Default is selected)
        self.default_label = QtWidgets.QLabel(
            "Default export process: FBX files are exported normally with no additional processing."
        )
        self.default_label.setStyleSheet("color: #888; font-style: italic;")
        self.default_label.setWordWrap(True)
        self.widget_layout.addWidget(self.default_label)
        
        # Verbose logging checkbox (always visible)
        sep2 = QtWidgets.QFrame()
        sep2.setFrameShape(QtWidgets.QFrame.HLine)
        sep2.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(sep2)
        
        self.verbose_checkbox = QtWidgets.QCheckBox("Verbose Logging (show all joints and animation data)")
        self.verbose_checkbox.setToolTip(
            "When enabled, outputs detailed information about every joint being processed\n"
            "and the associated animation data. Useful for debugging export issues."
        )
        layout.addWidget(self.verbose_checkbox)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QtWidgets.QPushButton("Save")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        save_btn.clicked.connect(self.save_and_close)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        
        self.on_process_changed()
    
    def load_settings(self):
        """Load current settings"""
        process = get_export_process()
        idx = self.process_combo.findData(process)
        if idx >= 0:
            self.process_combo.setCurrentIndex(idx)
        
        self.verbose_checkbox.setChecked(get_verbose_logging())
    
    def on_process_changed(self):
        """Handle process selection change"""
        process = self.process_combo.currentData()
        is_default = (process == "default")
        
        # Show/hide appropriate widgets
        self.default_label.setVisible(is_default)
        
        for proc_id, widget in self.process_widgets.items():
            widget.setVisible(proc_id == process)
        
        self.adjustSize()
    
    def save_and_close(self):
        """Save settings and close"""
        process = self.process_combo.currentData()
        
        # Validate if a process is selected
        if process != "default" and process in self.process_widgets:
            widget = self.process_widgets[process]
            if hasattr(widget, 'validate') and not widget.validate():
                return
        
        # Save settings
        set_export_process(process)
        set_verbose_logging(self.verbose_checkbox.isChecked())
        
        # Let process widgets save their settings
        for proc_id, widget in self.process_widgets.items():
            if hasattr(widget, 'save_settings'):
                widget.save_settings()
        
        log_message("Settings saved: process=%s, verbose=%s" % (process, self.verbose_checkbox.isChecked()))
        
        self.accept()


def show_settings_dialog():
    """Show the export process settings dialog"""
    if PYSIDE_VERSION is None:
        cmds.warning("PySide not available")
        return None
    
    try:
        dialog = ExportProcessDialog()
        dialog.exec_()
        return dialog
    except Exception as e:
        import traceback
        cmds.warning("Error showing settings: %s" % str(e))
        log_message(traceback.format_exc())
        return None


# Entry point for testing
if __name__ == "__main__":
    show_settings_dialog()

