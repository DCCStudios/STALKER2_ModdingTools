#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Weapon Importer for STALKER 2 Toolkit
Compatible with Maya 2022+ (Python 3, PySide6) and Maya 2022- (Python 2, PySide2)

This script imports weapon skeletons (SK_ prefix) and constrains associated unskinned meshes
to their respective joints based on naming conventions.
"""

import os
import re
import sys
import json

# Maya imports
import maya.cmds as cmds
import maya.mel as mel

# Python 2/3 compatibility
if sys.version_info[0] >= 3:
    string_types = str
    text_type = str
else:
    string_types = basestring
    text_type = unicode

# PySide compatibility for Maya versions
try:
    # Maya 2025+ (PySide6)
    from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QLabel, QPushButton, 
                                   QLineEdit, QComboBox, QListWidget, QListWidgetItem, QTextEdit, 
                                   QFileDialog, QMessageBox, QSplitter, QWidget, QScrollArea, QFrame, QCheckBox)
    from PySide6.QtCore import Qt, QSize
    from PySide6.QtGui import QPixmap, QFont
    from shiboken6 import wrapInstance
    pyside_version = 6
except ImportError:
    try:
        # Maya 2022 and earlier (PySide2)
        from PySide2.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QLabel, QPushButton, 
                                       QLineEdit, QComboBox, QListWidget, QListWidgetItem, QTextEdit, 
                                       QFileDialog, QMessageBox, QSplitter, QWidget, QScrollArea, QFrame, QCheckBox)
        from PySide2.QtCore import Qt, QSize
        from PySide2.QtGui import QPixmap, QFont
        from shiboken2 import wrapInstance
        pyside_version = 2
    except ImportError:
        print("Error: Could not import PySide. Please ensure Maya is running.")
        pyside_version = None

if pyside_version:
    import maya.OpenMayaUI as omui


class CollapsibleSection(QWidget):
    """A collapsible section widget with a toggle header"""
    def __init__(self, title="", parent=None):
        super(CollapsibleSection, self).__init__(parent)
        
        self.base_title = title  # Store the original title
        self.toggle_button = QPushButton()
        self.toggle_button.setProperty("class", "section-toggle")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)  # Expanded by default
        self.toggle_button.clicked.connect(self.toggle_section)
        self.toggle_button.setToolTip("Click to expand/collapse this section")
        
        self.content_widget = QWidget()
        self.content_widget.setProperty("class", "section-content")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(10, 8, 10, 8)
        self.content_layout.setSpacing(5)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.content_widget)
        
        self.update_button_text()
    
    def toggle_section(self):
        """Toggle the visibility of the content"""
        is_expanded = self.toggle_button.isChecked()
        self.content_widget.setVisible(is_expanded)
        self.update_button_text()
    
    def update_button_text(self):
        """Update button text with expand/collapse indicator"""
        if self.toggle_button.isChecked():
            self.toggle_button.setText("[-] " + self.base_title)
        else:
            self.toggle_button.setText("[+] " + self.base_title)
    
    def add_widget(self, widget):
        """Add a widget to the content area"""
        self.content_layout.addWidget(widget)
    
    def add_layout(self, layout):
        """Add a layout to the content area"""
        self.content_layout.addLayout(layout)


class WeaponConfigDialog(QDialog):
    def __init__(self, parent, existing_categories, config_dir):
        super(WeaponConfigDialog, self).__init__(parent)
        self.existing_categories = existing_categories
        self.config_dir = config_dir
        self.weapon_entries = []
        
        self.setWindowTitle("Create Weapon Configuration")
        self.setMinimumSize(605, 600)
        self.setMaximumSize(715, 800)
        self.setup_ui()
        self.setup_style()
        
        # Start with compact size
        self.resize(605, 600)
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header = QLabel("Create New Weapon Configuration")
        header.setProperty("class", "config-dialog-header")
        layout.addWidget(header)
        
        # Category selection section
        category_frame = QFrame()
        category_frame.setProperty("class", "config-section")
        category_layout = QFormLayout(category_frame)
        
        self.category_combo = QComboBox()
        self.category_combo.setToolTip("Select an existing weapon category or choose 'Create New...' to define a custom category")
        filtered_categories = [cat for cat in self.existing_categories if cat != "All Weapons"]
        self.category_combo.addItems(filtered_categories + ["Create New..."])
        self.category_combo.currentTextChanged.connect(self.on_category_selection_changed)
        category_layout.addRow("Category:", self.category_combo)
        
        # New category fields (initially hidden)
        self.new_category_frame = QFrame()
        new_cat_layout = QFormLayout(self.new_category_frame)
        
        self.new_category_name = QLineEdit()
        self.new_category_name.setPlaceholderText("e.g., Energy Weapons")
        self.new_category_name.setToolTip("Display name for the new weapon category (e.g., 'Energy Weapons', 'Experimental Rifles')")
        new_cat_layout.addRow("Category Name:", self.new_category_name)
        
        self.new_category_folder = QLineEdit()
        self.new_category_folder.setPlaceholderText("e.g., energy")
        self.new_category_folder.setToolTip("Folder name in the Weapons directory (lowercase, no spaces - e.g., 'energy', 'experimental_rifles')")
        new_cat_layout.addRow("Folder Name:", self.new_category_folder)
        
        self.new_category_frame.setVisible(False)
        
        layout.addWidget(category_frame)
        layout.addWidget(self.new_category_frame)
        
        # Description field
        desc_frame = QFrame()
        desc_frame.setProperty("class", "config-section")
        desc_layout = QFormLayout(desc_frame)
        
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Optional description for this config")
        self.description_edit.setToolTip("Optional description to document the purpose of this weapon configuration (e.g., 'Prototype weapons from DLC expansion')")
        desc_layout.addRow("Description:", self.description_edit)
        
        layout.addWidget(desc_frame)
        
        # Weapons section
        weapons_widget = QWidget()
        weapons_layout = QVBoxLayout(weapons_widget)
        weapons_layout.setSpacing(8)
        weapons_layout.setContentsMargins(0, 0, 0, 0)
        
        # Weapons scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedHeight(140)
        
        self.weapons_widget = QWidget()
        self.weapons_layout = QVBoxLayout(self.weapons_widget)
        self.weapons_layout.setSpacing(3)
        self.weapons_layout.setContentsMargins(5, 5, 5, 5)
        
        scroll_area.setWidget(self.weapons_widget)
        weapons_layout.addWidget(scroll_area)
        
        # Add weapon button
        add_weapon_btn = QPushButton("Add Weapon")
        add_weapon_btn.setProperty("class", "add-weapon-button")
        add_weapon_btn.setToolTip("Add another weapon entry to this configuration")
        add_weapon_btn.clicked.connect(self.add_weapon_entry)
        weapons_layout.addWidget(add_weapon_btn)
        
        layout.addWidget(weapons_widget)
        
        # Add first weapon entry by default
        self.add_weapon_entry()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondary-button")
        cancel_btn.setToolTip("Cancel config creation and close the dialog")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        button_layout.addStretch()
        
        create_btn = QPushButton("Create Config")
        create_btn.setProperty("class", "primary-button")
        create_btn.setToolTip("Save the weapon configuration as a JSON file")
        create_btn.clicked.connect(self.accept_config)
        button_layout.addWidget(create_btn)
        
        layout.addLayout(button_layout)
        
    def setup_style(self):
        style = """
        .config-dialog-header {
            font-size: 16px;
            font-weight: bold;
            color: #ffffff;
            padding: 10px;
            background-color: #0078d4;
            border-radius: 4px;
            text-align: center;
        }
                 .config-section {
             background-color: #2a2a2a;
             border: 1px solid #444444;
             border-radius: 4px;
             padding: 8px;
         }
        .section-header {
            font-weight: bold;
            color: #ffffff;
            margin-bottom: 5px;
        }
                 .weapon-entry {
             background-color: #333333;
             border: 1px solid #555555;
             border-radius: 4px;
             padding: 4px;
             margin: 1px 0px;
             max-height: 32px;
         }
        .remove-weapon-button {
            background-color: #dc3545;
            color: #ffffff;
            border: 1px solid #c82333;
            border-radius: 3px;
            padding: 2px 8px;
            font-size: 10px;
            max-height: 20px;
        }
        .remove-weapon-button:hover {
            background-color: #c82333;
        }
        .add-weapon-button {
            background-color: #28a745;
            color: #ffffff;
            border: 1px solid #1e7e34;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: bold;
        }
        .add-weapon-button:hover {
            background-color: #218838;
        }
        """
        self.setStyleSheet(style)
        
    def on_category_selection_changed(self, text):
        """Show/hide new category fields based on selection"""
        is_create_new = (text == "Create New...")
        self.new_category_frame.setVisible(is_create_new)
        
        # Resize dialog based on whether new category fields are shown
        if is_create_new:
            self.resize(605, 680)  # Larger size to accommodate extra fields
            self.new_category_name.setFocus()
        else:
            self.resize(605, 600)  # Compact size for existing categories
        
    def add_weapon_entry(self):
        """Add a new weapon entry widget"""
        weapon_frame = QFrame()
        weapon_frame.setProperty("class", "weapon-entry")
        weapon_layout = QHBoxLayout(weapon_frame)
        weapon_layout.setContentsMargins(8, 4, 8, 4)
        weapon_layout.setSpacing(8)
        
        # Weapon name field
        name_label = QLabel("Name:")
        name_label.setFixedWidth(40)
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("Weapon name")
        name_edit.setFixedWidth(180)
        name_edit.setToolTip("Display name for the weapon (e.g., 'Plasma Rifle', 'Modified AK-74')")
        weapon_layout.addWidget(name_label)
        weapon_layout.addWidget(name_edit)
        
        # Weapon ID field
        id_label = QLabel("ID:")
        id_label.setFixedWidth(25)
        id_edit = QLineEdit()
        id_edit.setPlaceholderText("weapon_id")
        id_edit.setFixedWidth(160)
        id_edit.setToolTip("Unique identifier for the weapon folder (lowercase, underscores for spaces - e.g., 'plasma_rifle', 'modified_ak74')")
        weapon_layout.addWidget(id_label)
        weapon_layout.addWidget(id_edit)
        
        # Remove button
        remove_btn = QPushButton("Remove")
        remove_btn.setProperty("class", "remove-weapon-button")
        remove_btn.setFixedWidth(60)
        remove_btn.setToolTip("Remove this weapon entry from the configuration")
        
        def remove_this_entry():
            self.weapon_entries.remove((weapon_frame, name_edit, id_edit))
            self.weapons_layout.removeWidget(weapon_frame)
            weapon_frame.deleteLater()
            
        remove_btn.clicked.connect(remove_this_entry)
        weapon_layout.addWidget(remove_btn)
        
        # Add stretch to keep everything left-aligned
        weapon_layout.addStretch()
        
        # Store reference
        self.weapon_entries.append((weapon_frame, name_edit, id_edit))
        self.weapons_layout.addWidget(weapon_frame)
        
        # Focus on name field for new entries
        name_edit.setFocus()
        
    def accept_config(self):
        """Validate and accept the configuration"""
        # Validate category
        if self.category_combo.currentText() == "Create New...":
            if not self.new_category_name.text().strip():
                QMessageBox.warning(self, "Validation Error", "Please enter a category name.")
                return
            if not self.new_category_folder.text().strip():
                QMessageBox.warning(self, "Validation Error", "Please enter a category folder name.")
                return
        
        # Validate weapons
        valid_weapons = []
        for _, name_edit, id_edit in self.weapon_entries:
            name = name_edit.text().strip()
            weapon_id = id_edit.text().strip()
            
            if name and weapon_id:
                valid_weapons.append((name, weapon_id))
            elif name or weapon_id:  # Only one field filled
                QMessageBox.warning(self, "Validation Error", 
                    "Please fill both name and ID for all weapons, or leave both empty to skip.")
                return
        
        if not valid_weapons:
            QMessageBox.warning(self, "Validation Error", "Please add at least one weapon.")
            return
        
        self.accept()
        
    def get_config_data(self):
        """Generate the config data dictionary"""
        try:
            # Determine category info
            if self.category_combo.currentText() == "Create New...":
                category_name = self.new_category_name.text().strip()
                category_folder = self.new_category_folder.text().strip()
            else:
                category_name = self.category_combo.currentText()
                # Find the folder for existing category
                parent = self.parent()
                category_folder = parent.category_folders.get(category_name, 
                    category_name.lower().replace(' ', '_'))
            
            # Collect weapons
            weapons = []
            for _, name_edit, id_edit in self.weapon_entries:
                name = name_edit.text().strip()
                weapon_id = id_edit.text().strip()
                
                if name and weapon_id:
                    weapons.append({
                        "name": name,
                        "id": weapon_id,
                        "description": ""
                    })
            
            config_data = {
                "category_name": category_name,
                "category_folder": category_folder,
                "description": self.description_edit.text().strip(),
                "weapons": weapons
            }
            
            return config_data
            
        except Exception as e:
            print("Error generating config data: {0}".format(str(e)))
            return None


class WeaponImporterDialog(QDialog):
    def __init__(self, parent=None):
        super(WeaponImporterDialog, self).__init__(parent)
        self.setWindowTitle("Weapon Importer - STALKER 2 Toolkit")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        
        # Weapon database from WeaponList.txt
        self.weapon_categories = {
            "All Weapons": [],
            "Melee": [("Knife", "knife")],
            "Pistols": [
                ("PTM", "pm"), ("UDP Compact", "udp"), ("APSB", "apb"), 
                ("Rhino", "rhino00000"), ("Kora-1911", "kora")
            ],
            "Shotguns": [
                ("Boomstick", "obrez"), ("TOZ-34", "toz34"), ("M680 Cracker", "m86000"),
                ("SPSA-14", "spsa00"), ("Saiga D-12", "d1200"), ("RAM-2", "ram2")
            ],
            "Submachine Guns": [
                ("Viper-5", "vip"), ("AKM-74U", "aku"), ("M10 Gordon", "m1000"),
                ("Buket S-2", "bucket0"), ("ZUBR-19", "zubr0"), ("Integral-A", "integ")
            ],
            "Assault Rifles": [
                ("AK74", "ak74"), ("Fora-221", "fora0"), ("Dnipro", "dnipro"),
                ("GROM S-14", "grim0"), ("AS Lavina", "lav"), ("AR416", "m160"),
                ("GP37", "gp37"), ("Kharod", "kharod000"), ("Sotnyk", "sotnyk")
            ],
            "Sniper Rifles": [
                ("SVU MK S-3", "svu"), ("SVDM-2", "svm"), ("VS Vintar", "vintar"),
                ("M701 Super", "m701"), ("Mark 1 EMR", "mar"), ("Three-Line Rifle", "threeline"),
                ("Gauss Rifle", "gauss")
            ],
            "Machine Guns": [
                ("RPM-74", "pkp00000"), ("PKP", "mgp")
            ],
            "Launchers": [
                ("RPG7U", "rpg7")
            ],
            "Grenades": [
                ("F1 Grenade", "f1"), ("RGD5 Grenade", "rgd5"), ("Smoke Grenade", "smoke")
            ]
        }
        
        # Category to folder mapping
        self.category_folders = {
            "Melee": "knifes",
            "Pistols": "pt",
            "Shotguns": "shg", 
            "Submachine Guns": "smg",
            "Assault Rifles": "ar",
            "Sniper Rifles": "sr",
            "Machine Guns": "mg",
            "Launchers": "gl",
            "Grenades": "grenades"
        }
        
        # Settings
        self.master_path = ""
        self.settings_file = os.path.join(cmds.internalVar(userAppDir=True), "STALKER2_weapon_importer_settings.json")
        self.load_settings()
        
        # Load custom weapon configurations from JSON files
        self.load_custom_weapon_configs()
        
        # Joint-mesh associations
        self.joint_mesh_associations = {}  # {joint_name: [mesh_files]}
        self.joint_selectors = {}  # {joint_name: QComboBox} for user selections
        
        # Attachment data
        self.attachments = []  # List of attachment dictionaries: {fbx_path, joint_name, visible, name}
        self.attachment_widgets = []  # List of attachment UI widgets
        
        self.setup_ui()
        self.setup_dark_style()
        self.populate_all_weapons()
        
        # Connect signals
        self.category_combo.currentTextChanged.connect(self.on_category_changed)
        self.weapon_combo.currentTextChanged.connect(self.on_weapon_changed)
        self.master_path_edit.textChanged.connect(self.on_master_path_edited)
        
        # Initialize the weapon dropdown for the default category
        self.initialize_weapon_selection()
    
    def initialize_weapon_selection(self):
        """Initialize the weapon dropdown with the default category selection"""
        # Get the current category (should be "All Weapons" by default)
        current_category = self.category_combo.currentText()
        
        # Populate the weapon dropdown for this category
        self.on_category_changed(current_category)
        
        # Set a default weapon selection if weapons are available
        if self.weapon_combo.count() > 0:
            self.weapon_combo.setCurrentIndex(0)
            # Trigger the weapon change event for the default selection
            self.on_weapon_changed(self.weapon_combo.currentText())
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Title
        title_label = QLabel("STALKER 2 Weapon Importer")
        title_label.setProperty("class", "title-label")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Master path section - compact
        path_section = CollapsibleSection("Master Path Configuration")
        
        path_input_layout = QHBoxLayout()
        path_input_layout.addWidget(QLabel("Path:"))
        self.master_path_edit = QLineEdit(self.master_path)
        self.master_path_edit.setPlaceholderText("Select STALKER2_ModdingTools folder...")
        path_input_layout.addWidget(self.master_path_edit)
        self.browse_path_btn = QPushButton("Browse")
        self.browse_path_btn.setFixedWidth(60)
        self.browse_path_btn.clicked.connect(self.browse_master_path)
        path_input_layout.addWidget(self.browse_path_btn)
        
        # Current weapon path display - compact
        self.current_path_label = QLabel("Current Path: (select a weapon)")
        self.current_path_label.setProperty("class", "path-label")
        self.current_path_label.setWordWrap(True)
        
        path_section.add_layout(path_input_layout)
        path_section.add_widget(self.current_path_label)
        main_layout.addWidget(path_section)
        
        # Weapon selection section - compact
        weapon_layout = QHBoxLayout()
        weapon_layout.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems(list(self.weapon_categories.keys()))
        weapon_layout.addWidget(self.category_combo)
        
        weapon_layout.addWidget(QLabel("Weapon:"))
        self.weapon_combo = QComboBox()
        weapon_layout.addWidget(self.weapon_combo)
        
        main_layout.addLayout(weapon_layout)
        
        # Main content splitter
        content_splitter = QSplitter()
        if pyside_version == 6:
            content_splitter.setOrientation(Qt.Orientation.Horizontal)
        else:
            content_splitter.setOrientation(Qt.Horizontal)
        
        # Left panel - Joint analysis
        left_panel = QFrame()
        left_panel.setProperty("class", "panel-frame")
        left_layout = QVBoxLayout(left_panel)
        
        joint_header = QLabel("Skeleton Joint Analysis")
        joint_header.setProperty("class", "section-header")
        left_layout.addWidget(joint_header)
        
        # Create scroll area for joint-mesh associations
        joint_scroll = QScrollArea()
        joint_scroll.setWidgetResizable(True)
        joint_scroll.setMaximumHeight(250)
        joint_scroll.setMinimumHeight(150)
        
        # Widget to contain joint-mesh association widgets
        self.joint_container = QWidget()
        self.joint_layout = QVBoxLayout(self.joint_container)
        self.joint_layout.setSpacing(5)
        self.joint_layout.setContentsMargins(5, 5, 5, 5)
        
        joint_scroll.setWidget(self.joint_container)
        left_layout.addWidget(joint_scroll)
        
        # Joint count label
        self.joint_count_label = QLabel("No weapon selected")
        self.joint_count_label.setProperty("class", "info-label")
        left_layout.addWidget(self.joint_count_label)
        
        content_splitter.addWidget(left_panel)
        
        # Right panel - Image preview
        right_panel = QFrame()
        right_panel.setProperty("class", "panel-frame")
        right_layout = QVBoxLayout(right_panel)
        
        preview_header = QLabel("Weapon Preview")
        preview_header.setProperty("class", "section-header")
        right_layout.addWidget(preview_header)
        
        # Image display
        self.image_label = QLabel()
        self.image_label.setProperty("class", "image-preview")
        self.image_label.setMinimumSize(300, 300)
        if pyside_version == 6:
            self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.image_label.setScaledContents(False)
        else:
            self.image_label.setAlignment(Qt.AlignCenter)
            self.image_label.setScaledContents(False)
        self.image_label.setText("Select a weapon to preview")
        self.image_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #555555;
                background-color: #333333;
                color: #888888;
            }
        """)
        right_layout.addWidget(self.image_label)
        
        # Image info
        self.image_info_label = QLabel("No preview available")
        self.image_info_label.setProperty("class", "info-label")
        self.image_info_label.setWordWrap(True)
        right_layout.addWidget(self.image_info_label)
        
        content_splitter.addWidget(right_panel)
        content_splitter.setSizes([400, 500])
        
        main_layout.addWidget(content_splitter)
        
        # Attachments section - collapsible and compact
        attachments_section = CollapsibleSection("Additional Attachments (Optional)")
        attachments_section.toggle_button.setChecked(False)  # Collapsed by default
        attachments_section.toggle_section()  # Apply the collapsed state and update text
        
        # Attachments scroll area
        attachments_scroll = QScrollArea()
        attachments_scroll.setWidgetResizable(True)
        attachments_scroll.setMaximumHeight(150)
        
        self.attachments_container = QWidget()
        self.attachments_layout = QVBoxLayout(self.attachments_container)
        self.attachments_layout.setSpacing(3)
        self.attachments_layout.setContentsMargins(3, 3, 3, 3)
        
        # Add stretch to keep attachments at top
        self.attachments_layout.addStretch()
        
        attachments_scroll.setWidget(self.attachments_container)
        
        # Add attachment button
        add_attachment_btn = QPushButton("Add Attachment")
        add_attachment_btn.setProperty("class", "secondary-button")
        add_attachment_btn.clicked.connect(self.add_attachment_entry)
        add_attachment_btn.setToolTip("Add an additional FBX file to import as an attachment")
        
        attachments_section.add_widget(attachments_scroll)
        attachments_section.add_widget(add_attachment_btn)
        main_layout.addWidget(attachments_section)
        
        # Import options - compact
        options_layout = QVBoxLayout()
        options_layout.setSpacing(5)
        
        # Organization checkbox
        self.organize_checkbox = QCheckBox("Organize into Groups")
        self.organize_checkbox.setChecked(True)
        self.organize_checkbox.setToolTip("Group imported assets: S2_Weapon > S2_Skeleton (joints) + S2_Mesh (mesh parts)")
        options_layout.addWidget(self.organize_checkbox)
        
        # Import buttons layout
        import_buttons_layout = QVBoxLayout()
        
        # Single weapon buttons
        single_weapon_layout = QHBoxLayout()
        
        # Create directory button
        self.create_dir_btn = QPushButton("Create Weapon Directory")
        self.create_dir_btn.setProperty("class", "secondary-button")
        self.create_dir_btn.setEnabled(False)
        self.create_dir_btn.clicked.connect(self.create_weapon_directory)
        single_weapon_layout.addWidget(self.create_dir_btn)
        
        # Import button
        self.import_btn = QPushButton("Import Weapon")
        self.import_btn.setProperty("class", "primary-button")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self.import_weapon)
        single_weapon_layout.addWidget(self.import_btn)
        
        # Load Rig button
        self.load_rig_btn = QPushButton("Load Rig")
        self.load_rig_btn.setProperty("class", "secondary-button")
        self.load_rig_btn.setEnabled(False)
        self.load_rig_btn.clicked.connect(self.load_weapon_rig)
        single_weapon_layout.addWidget(self.load_rig_btn)
        
        # Load Animation button
        self.load_anim_btn = QPushButton("Load Animation")
        self.load_anim_btn.setProperty("class", "secondary-button")
        self.load_anim_btn.clicked.connect(self.load_animation)
        single_weapon_layout.addWidget(self.load_anim_btn)
        
        import_buttons_layout.addLayout(single_weapon_layout)
        
        # Create all directories button
        self.create_all_btn = QPushButton("Create All Weapon Directories")
        self.create_all_btn.setProperty("class", "create-all-button")
        self.create_all_btn.setEnabled(False)
        self.create_all_btn.clicked.connect(self.create_all_weapon_directories)
        import_buttons_layout.addWidget(self.create_all_btn)
        
        options_layout.addLayout(import_buttons_layout)
        
        main_layout.addLayout(options_layout)
        
        # Config management section - collapsible and compact
        config_section = CollapsibleSection("Advanced: Configuration Management")
        config_section.toggle_button.setChecked(False)  # Collapsed by default
        config_section.toggle_section()  # Apply the collapsed state and update text
        
        config_button_layout = QHBoxLayout()
        
        create_config_btn = QPushButton("Create Config")
        create_config_btn.setProperty("class", "config-button")
        create_config_btn.clicked.connect(self.create_new_config)
        config_button_layout.addWidget(create_config_btn)
        
        reload_configs_btn = QPushButton("Reload Configs")
        reload_configs_btn.setProperty("class", "config-button")
        reload_configs_btn.clicked.connect(self.reload_custom_configs)
        config_button_layout.addWidget(reload_configs_btn)
        
        config_button_layout.addStretch()
        
        config_section.add_layout(config_button_layout)
        main_layout.addWidget(config_section)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setProperty("class", "secondary-button")
        refresh_btn.clicked.connect(self.refresh_all_data)
        button_layout.addWidget(refresh_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setProperty("class", "secondary-button")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        main_layout.addLayout(button_layout)
    
    def setup_dark_style(self):
        """Apply dark theme styling consistent with STALKER 2 toolkit"""
        dark_style = """
        QDialog {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QLabel {
            color: #ffffff;
            font-size: 11px;
        }
        .title-label {
            color: #ffffff;
            font-size: 18px;
            font-weight: bold;
            padding: 10px;
            background-color: #1a1a1a;
            border: 2px solid #333333;
            border-radius: 6px;
            margin-bottom: 10px;
        }
        .section-header {
            color: #cccccc;
            font-size: 14px;
            font-weight: bold;
            padding: 8px 4px;
            background-color: #252525;
            border-left: 3px solid #0078d4;
            margin-bottom: 8px;
        }
        .section-frame {
            background-color: #222222;
            border: 1px solid #333333;
            border-radius: 4px;
            padding: 10px;
        }
        .panel-frame {
            background-color: #1f1f1f;
            border: 1px solid #444444;
            border-radius: 4px;
            padding: 10px;
        }
        .path-label {
            color: #cccccc;
            font-size: 10px;
            background-color: #333333;
            padding: 5px;
            border-radius: 3px;
            margin: 5px 0px;
        }
        .info-label {
            color: #cccccc;
            font-size: 10px;
            background-color: #333333;
            padding: 8px;
            border-radius: 3px;
            margin-top: 5px;
        }
        QPushButton {
            background-color: #404040;
            color: #ffffff;
            border: 1px solid #555555;
            padding: 8px 16px;
            border-radius: 4px;
            font-size: 11px;
        }
        QPushButton:hover {
            background-color: #505050;
            border: 1px solid #777777;
        }
        QPushButton:pressed {
            background-color: #353535;
        }
        .primary-button {
            background-color: #0078d4;
            color: #ffffff;
            border: 1px solid #106ebe;
            padding: 12px 20px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }
        .primary-button:hover {
            background-color: #106ebe;
        }
        .primary-button:pressed {
            background-color: #005a9e;
        }
        .primary-button:disabled {
            background-color: #2a2a2a;
            color: #666666;
            border: 1px solid #333333;
        }
        .secondary-button {
            background-color: #404040;
            color: #ffffff;
            border: 1px solid #555555;
            padding: 8px 16px;
            border-radius: 4px;
        }
        .secondary-button:hover {
            background-color: #555555;
        }
        .secondary-button:disabled {
            background-color: #2a2a2a;
            color: #666666;
            border: 1px solid #333333;
        }
        .create-all-button {
            background-color: #228B22;
            color: #ffffff;
            border: 1px solid #32CD32;
            padding: 10px 20px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            margin-top: 8px;
        }
        .create-all-button:hover {
            background-color: #32CD32;
        }
        .create-all-button:pressed {
            background-color: #006400;
        }
        .create-all-button:disabled {
            background-color: #2a2a2a;
            color: #666666;
            border: 1px solid #333333;
        }
        QLineEdit {
            background-color: #404040;
            color: #ffffff;
            border: 1px solid #555555;
            padding: 6px;
            border-radius: 3px;
            font-size: 11px;
        }
        QLineEdit:focus {
            border: 1px solid #0078d4;
        }
        QComboBox {
            background-color: #404040;
            color: #ffffff;
            border: 1px solid #555555;
            padding: 6px;
            border-radius: 3px;
            font-size: 11px;
            min-width: 150px;
        }
        QComboBox:hover {
            border: 1px solid #777777;
        }
        QComboBox:focus {
            border: 1px solid #0078d4;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 15px;
            border-left-width: 1px;
            border-left-color: #555555;
            border-left-style: solid;
            border-top-right-radius: 3px;
            border-bottom-right-radius: 3px;
            background-color: #505050;
        }
        QComboBox::down-arrow {
            width: 8px;
            height: 8px;
            image: none;
            border: 2px solid #cccccc;
            border-top: none;
            border-right: none;
            transform: rotate(45deg);
            margin-right: 3px;
        }
        QComboBox QAbstractItemView {
            background-color: #404040;
            color: #ffffff;
            border: 1px solid #555555;
            selection-background-color: #0078d4;
        }
        QListWidget {
            background-color: #404040;
            border: 1px solid #555555;
            selection-background-color: #0078d4;
            alternate-background-color: #484848;
            color: #ffffff;
        }
        QListWidget::item {
            padding: 4px 8px;
            border-bottom: 1px solid #555555;
        }
        QListWidget::item:selected {
            background-color: #0078d4;
        }
        QListWidget::item:hover {
            background-color: #505050;
        }
        QSplitter::handle {
            background-color: #555555;
            width: 2px;
        }
        QScrollArea {
            background-color: #2b2b2b;
            border: none;
        }
        QScrollArea QWidget {
            background-color: #2b2b2b;
        }
        .joint-item {
            background-color: #333333;
            border: 1px solid #444444;
            border-radius: 3px;
            padding: 5px;
            margin: 2px 0px;
        }
        .joint-name {
            color: #ffffff;
            font-size: 11px;
            font-weight: bold;
        }
        .mesh-file {
            color: #cccccc;
            font-size: 10px;
            margin-left: 10px;
        }
        .no-mesh {
            color: #888888;
            font-size: 10px;
            font-style: italic;
            margin-left: 10px;
        }
        .mesh-selector {
            margin-left: 10px;
            margin-top: 3px;
            min-width: 200px;
            max-width: 300px;
        }
        .config-frame {
            background-color: #1a1a1a;
            border: 1px solid #333333;
            border-radius: 4px;
            margin: 5px 0px;
        }
        .config-header {
            color: #888888;
            font-size: 10px;
            font-weight: bold;
            text-align: center;
            margin: 2px 0px;
        }
        .config-button {
            background-color: #333333;
            color: #cccccc;
            border: 1px solid #444444;
            padding: 4px 8px;
            border-radius: 3px;
            font-size: 10px;
            max-height: 25px;
        }
        .config-button:hover {
            background-color: #444444;
            color: #ffffff;
        }
        .section-toggle {
            background-color: #484848;
            color: #ffffff;
            border: 1px solid #666666;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
            text-align: left;
            font-family: 'Consolas', 'Monaco', monospace;
        }
        .section-toggle:hover {
            background-color: #585858;
            border: 1px solid #888888;
            cursor: pointer;
        }
        .section-toggle:pressed {
            background-color: #383838;
        }
        .section-toggle:checked {
            background-color: #0078d4;
            border: 1px solid #106ebe;
        }
        .section-toggle:checked:hover {
            background-color: #106ebe;
        }
        .section-content {
            background-color: #2a2a2a;
            border: 1px solid #444444;
            border-top: none;
            border-radius: 0px 0px 4px 4px;
            margin: 0px;
        }
        QCheckBox {
            color: #ffffff;
            font-size: 11px;
            padding: 4px;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border: 2px solid #555555;
            border-radius: 3px;
            background-color: #404040;
        }
        QCheckBox::indicator:checked {
            background-color: #0078d4;
            border: 2px solid #106ebe;
            image: none;
        }
        QCheckBox::indicator:hover {
            border: 2px solid #777777;
        }
        QCheckBox::indicator:checked:hover {
            background-color: #106ebe;
            border: 2px solid #0078d4;
        }
        """
        self.setStyleSheet(dark_style)
    
    def load_settings(self):
        """Load persistent settings"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    self.master_path = settings.get('master_path', '')
                    print("Loaded settings: master_path = '{0}'".format(self.master_path))
            else:
                print("No settings file found, using defaults")
        except Exception as e:
            print("Warning: Could not load settings: {0}".format(str(e)))
            self.master_path = ""
    
    def save_settings(self):
        """Save persistent settings"""
        try:
            settings = {
                'master_path': self.master_path
            }
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
            print("Settings saved")
        except Exception as e:
            print("Warning: Could not save settings: {0}".format(str(e)))
    
    def populate_all_weapons(self):
        """Populate the All Weapons category with all weapons from all categories"""
        all_weapons = []
        for category, weapons in self.weapon_categories.items():
            if category != "All Weapons":
                for weapon_name, weapon_id in weapons:
                    all_weapons.append((weapon_name, weapon_id))
        
        # Sort alphabetically by weapon name
        all_weapons.sort(key=lambda x: x[0])
        self.weapon_categories["All Weapons"] = all_weapons
    
    def browse_master_path(self):
        """Browse for master path"""
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Select STALKER2_ModdingTools Master Directory",
            self.master_path if self.master_path else ""
        )
        if directory:
            self.master_path = directory
            self.master_path_edit.setText(directory)
            self.save_settings()
            # Reload custom configs with new master path
            self.load_custom_weapon_configs()
            self.populate_all_weapons()
            self.update_current_weapon_path()
            self.refresh_weapon_data()
            # Update the create all button with new count
            self.update_import_button()
            self.update_load_rig_button()
    
    def on_master_path_edited(self, text):
        """Handle manual edits to master path field"""
        self.master_path = text
        if text:  # Only save if not empty
            self.save_settings()
            # Reload custom configs when master path changes
            self.load_custom_weapon_configs()
            self.populate_all_weapons()
        self.update_current_weapon_path()
        self.update_import_button()
        self.update_load_rig_button()
    
    def on_category_changed(self, category):
        """Handle category selection change"""
        self.weapon_combo.clear()
        
        if category in self.weapon_categories:
            weapons = self.weapon_categories[category]
            for weapon_name, weapon_id in weapons:
                self.weapon_combo.addItem(weapon_name, weapon_id)
        
        # Trigger weapon change to update display
        if self.weapon_combo.count() > 0:
            self.on_weapon_changed(self.weapon_combo.currentText())
    
    def on_weapon_changed(self, weapon_name):
        """Handle weapon selection change"""
        self.update_current_weapon_path()
        self.analyze_weapon_skeleton()
        self.refresh_attachment_joint_combos()  # Update attachment joint options
        self.load_weapon_preview()
        self.update_import_button()
        self.update_load_rig_button()
    
    def update_current_weapon_path(self):
        """Update the current weapon path display"""
        if not self.master_path:
            self.current_path_label.setText("Current Path: (master path not set)")
            return
        
        weapon_id = self.weapon_combo.currentData()
        category = self.category_combo.currentText()
        
        if not weapon_id or category == "All Weapons":
            # For "All Weapons", determine category from weapon_id
            if weapon_id:
                category = self.find_category_for_weapon(weapon_id)
        
        if weapon_id and category and category != "All Weapons":
            category_folder = self.category_folders.get(category, "")
            if category_folder:
                weapon_path = os.path.join(self.master_path, "Source", "Weapons", category_folder, weapon_id)
                if os.path.exists(weapon_path):
                    self.current_path_label.setText("Current Path: {0}".format(weapon_path))
                else:
                    self.current_path_label.setText("Current Path: {0} (directory does not exist - can be created)".format(weapon_path))
            else:
                self.current_path_label.setText("Current Path: (unknown category folder)")
        else:
            self.current_path_label.setText("Current Path: (select a weapon)")
    
    def find_category_for_weapon(self, weapon_id):
        """Find which category a weapon belongs to"""
        for category, weapons in self.weapon_categories.items():
            if category != "All Weapons":
                for weapon_name, w_id in weapons:
                    if w_id == weapon_id:
                        return category
        return None
    
    def get_current_weapon_path(self, create_if_missing=False):
        """Get the current weapon directory path, optionally creating it if missing"""
        if not self.master_path:
            return None
        
        weapon_id = self.weapon_combo.currentData()
        category = self.category_combo.currentText()
        
        if category == "All Weapons":
            category = self.find_category_for_weapon(weapon_id)
        
        if not weapon_id or not category or category == "All Weapons":
            return None
        
        category_folder = self.category_folders.get(category, "")
        if not category_folder:
            return None
        
        weapon_path = os.path.join(self.master_path, "Source", "Weapons", category_folder, weapon_id)
        
        if create_if_missing and not os.path.exists(weapon_path):
            try:
                os.makedirs(weapon_path)
                print("Created weapon directory: {0}".format(weapon_path))
                return weapon_path
            except Exception as e:
                print("Error creating weapon directory {0}: {1}".format(weapon_path, str(e)))
                return None
        
        return weapon_path if os.path.exists(weapon_path) else None
    
    def add_attachment_entry(self):
        """Add a new attachment entry widget"""
        attachment_frame = QFrame()
        attachment_frame.setProperty("class", "joint-item")
        attachment_layout = QVBoxLayout(attachment_frame)
        attachment_layout.setContentsMargins(8, 5, 8, 5)
        attachment_layout.setSpacing(3)
        
        # First row: Category and Name
        first_row = QHBoxLayout()
        
        # Category
        category_label = QLabel("Category:")
        category_label.setFixedWidth(60)
        category_edit = QLineEdit()
        category_edit.setPlaceholderText("e.g., Magazines")
        category_edit.setToolTip("Category for this attachment (e.g., 'Magazines', 'Optics', 'Grips')")
        first_row.addWidget(category_label)
        first_row.addWidget(category_edit, 1)  # Stretch factor 1
        
        # Attachment name
        name_label = QLabel("Name:")
        name_label.setFixedWidth(50)
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("Display name")
        name_edit.setToolTip("Display name for this attachment (e.g., 'Twin Mag', 'Red Dot')")
        first_row.addWidget(name_label)
        first_row.addWidget(name_edit, 1)  # Stretch factor 1
        
        # Duplicate button
        duplicate_btn = QPushButton("[C]")
        duplicate_btn.setProperty("class", "secondary-button")
        duplicate_btn.setFixedWidth(50)
        duplicate_btn.setToolTip("Copy this attachment entry with all current values")
        first_row.addWidget(duplicate_btn)
        
        # Remove button (moved here for better UX)
        remove_btn = QPushButton("X")
        remove_btn.setProperty("class", "remove-weapon-button")
        remove_btn.setFixedWidth(25)
        remove_btn.setToolTip("Remove this attachment entry")
        first_row.addWidget(remove_btn)
        
        attachment_layout.addLayout(first_row)
        
        # Second row: FBX path and browse
        second_row = QHBoxLayout()
        
        # FBX file path
        fbx_label = QLabel("FBX:")
        fbx_label.setFixedWidth(25)
        fbx_edit = QLineEdit()
        fbx_edit.setPlaceholderText("Select FBX file...")
        fbx_edit.setToolTip("Path to the FBX file to import as an attachment")
        second_row.addWidget(fbx_label)
        second_row.addWidget(fbx_edit)
        
        # Browse button
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(30)
        browse_btn.setToolTip("Browse for FBX file")
        browse_btn.clicked.connect(lambda: self.browse_attachment_fbx(fbx_edit))
        second_row.addWidget(browse_btn)
        
        attachment_layout.addLayout(second_row)
        
        # Third row: Joint selection, visibility, and remove button
        third_row = QHBoxLayout()
        
        # Target joint
        joint_label = QLabel("Joint:")
        joint_label.setFixedWidth(35)
        joint_combo = QComboBox()
        joint_combo.setFixedWidth(120)
        joint_combo.setToolTip("Select which joint this attachment should be constrained to")
        third_row.addWidget(joint_label)
        third_row.addWidget(joint_combo)
        
        # Populate joint combo with available joints
        self.populate_attachment_joint_combo(joint_combo)
        
        # Visibility checkbox
        visible_checkbox = QCheckBox("Visible")
        visible_checkbox.setToolTip("Whether this attachment should be visible when imported")
        visible_checkbox.setChecked(False)  # Default to hidden
        third_row.addWidget(visible_checkbox)
        
        # Add stretch to push everything left
        third_row.addStretch()
        
        attachment_layout.addLayout(third_row)
        
        # Store widget references
        attachment_data = {
            'frame': attachment_frame,
            'category_edit': category_edit,
            'name_edit': name_edit,
            'fbx_edit': fbx_edit,
            'joint_combo': joint_combo,
            'visible_checkbox': visible_checkbox,
            'duplicate_btn': duplicate_btn,
            'remove_btn': remove_btn
        }
        
        # Connect duplicate button
        def duplicate_this_attachment():
            self.duplicate_attachment_entry(attachment_data)
        duplicate_btn.clicked.connect(duplicate_this_attachment)
        
        # Connect remove button
        def remove_this_attachment():
            self.remove_attachment_entry(attachment_data)
        remove_btn.clicked.connect(remove_this_attachment)
        
        # Add to attachments list and layout
        self.attachment_widgets.append(attachment_data)
        
        # Insert before the stretch
        stretch_item = self.attachments_layout.takeAt(self.attachments_layout.count() - 1)
        self.attachments_layout.addWidget(attachment_frame)
        self.attachments_layout.addItem(stretch_item)
        
        # Focus on name field
        name_edit.setFocus()
    
    def duplicate_attachment_entry(self, source_attachment_data):
        """Duplicate an attachment entry with all current values"""
        # Get current values from the source attachment
        current_category = source_attachment_data['category_edit'].text()
        current_name = source_attachment_data['name_edit'].text()
        current_fbx = source_attachment_data['fbx_edit'].text()
        current_joint = source_attachment_data['joint_combo'].currentText()
        current_visible = source_attachment_data['visible_checkbox'].isChecked()
        
        # Create a new attachment entry
        self.add_attachment_entry()
        
        # Get the newly created attachment (last one in the list)
        if self.attachment_widgets:
            new_attachment = self.attachment_widgets[-1]
            
            # Populate with copied values
            new_attachment['category_edit'].setText(current_category)
            new_attachment['name_edit'].setText(current_name + " Copy")  # Add "Copy" to distinguish
            new_attachment['fbx_edit'].setText(current_fbx)
            new_attachment['visible_checkbox'].setChecked(current_visible)
            
            # Set joint selection if it exists in the combo
            joint_index = new_attachment['joint_combo'].findText(current_joint)
            if joint_index >= 0:
                new_attachment['joint_combo'].setCurrentIndex(joint_index)
            
            # Focus on the name field of the new entry for easy editing
            new_attachment['name_edit'].setFocus()
            new_attachment['name_edit'].selectAll()
    
    def remove_attachment_entry(self, attachment_data):
        """Remove an attachment entry"""
        if attachment_data in self.attachment_widgets:
            self.attachment_widgets.remove(attachment_data)
            self.attachments_layout.removeWidget(attachment_data['frame'])
            attachment_data['frame'].deleteLater()
    
    def browse_attachment_fbx(self, fbx_edit):
        """Browse for an attachment FBX file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Attachment FBX File",
            "",
            "FBX Files (*.fbx);;All Files (*)"
        )
        if file_path:
            fbx_edit.setText(file_path)
    
    def populate_attachment_joint_combo(self, joint_combo):
        """Populate a joint combo box with available joints"""
        joint_combo.clear()
        
        # Add default option
        joint_combo.addItem("(Select Joint)")
        
        # Add joints from current weapon analysis
        if hasattr(self, 'joint_mesh_associations') and self.joint_mesh_associations:
            sorted_joints = sorted(self.joint_mesh_associations.keys())
            for joint_name in sorted_joints:
                joint_combo.addItem(joint_name)
    
    def refresh_attachment_joint_combos(self):
        """Refresh all attachment joint combo boxes when weapon changes"""
        for attachment_data in self.attachment_widgets:
            current_selection = attachment_data['joint_combo'].currentText()
            self.populate_attachment_joint_combo(attachment_data['joint_combo'])
            
            # Try to restore previous selection
            index = attachment_data['joint_combo'].findText(current_selection)
            if index >= 0:
                attachment_data['joint_combo'].setCurrentIndex(index)
    
    def get_attachment_data(self):
        """Get current attachment data from UI widgets"""
        attachments = []
        for attachment_data in self.attachment_widgets:
            category = attachment_data['category_edit'].text().strip()
            name = attachment_data['name_edit'].text().strip()
            fbx_path = attachment_data['fbx_edit'].text().strip()
            joint_name = attachment_data['joint_combo'].currentText()
            visible = attachment_data['visible_checkbox'].isChecked()
            
            if category and name and fbx_path and joint_name != "(Select Joint)":
                attachments.append({
                    'category': category,
                    'name': name,
                    'fbx_path': fbx_path,
                    'joint_name': joint_name,
                    'visible': visible
                })
        
        return attachments
    
    def analyze_weapon_skeleton(self):
        """Analyze the weapon skeleton and populate joint-mesh associations"""
        # Clear previous data
        self.clear_joint_container()
        self.joint_mesh_associations.clear()
        self.joint_selectors.clear()
        
        weapon_path = self.get_current_weapon_path()
        if not weapon_path:
            weapon_id = self.weapon_combo.currentData()
            if weapon_id and self.master_path:
                self.joint_count_label.setText("Directory not found - use 'Create Weapon Directory' button")
            else:
                self.joint_count_label.setText("Cannot analyze: weapon path not configured")
            return
        
        weapon_id = self.weapon_combo.currentData()
        if not weapon_id:
            self.joint_count_label.setText("No weapon selected")
            return
        
        # Find skeleton file (SK_ prefix)
        skeleton_file = None
        mesh_files = []
        
        try:
            for filename in os.listdir(weapon_path):
                if filename.lower().endswith('.fbx'):
                    if filename.startswith('SK_'):
                        skeleton_file = os.path.join(weapon_path, filename)
                    elif not filename.startswith('SK_'):  # Any non-skeleton FBX
                        mesh_files.append(filename)
        except Exception as e:
            self.joint_count_label.setText("Error reading weapon directory: {0}".format(str(e)))
            return
        
        if not skeleton_file:
            self.joint_count_label.setText("No skeleton file (SK_*.fbx) found in weapon directory")
            return
        
        # Get expected joints for this weapon
        joints = self.get_skeleton_joints_preview(skeleton_file)
        
        if not joints:
            self.joint_count_label.setText("No joints with 'jnt_' prefix found in skeleton file")
            # Create a simple message widget
            message_widget = QFrame()
            message_widget.setProperty("class", "joint-item")
            message_layout = QVBoxLayout(message_widget)
            message_layout.setContentsMargins(5, 5, 5, 5)
            
            message_label = QLabel("No 'jnt_' joints found in skeleton")
            message_label.setProperty("class", "joint-name")
            message_layout.addWidget(message_label)
            
            detail_label = QLabel("-> The skeleton file may not contain joints with the expected 'jnt_' prefix")
            detail_label.setProperty("class", "no-mesh")
            message_layout.addWidget(detail_label)
            
            self.joint_layout.addWidget(message_widget)
            self.joint_layout.addStretch()
            return
        
        # Analyze mesh files and match them to joints
        self.analyze_joint_mesh_associations(joints, mesh_files, weapon_id)
        
        # Create UI widgets for joint associations
        self.create_joint_association_widgets()
        
        # Update count label
        total_joints = len(joints)
        joints_with_meshes = len([j for j in joints if j in self.joint_mesh_associations and self.joint_mesh_associations[j]])
        
        self.joint_count_label.setText("Found {0} joint(s), {1} have associated mesh files".format(
            total_joints, joints_with_meshes))
    
    def clear_joint_container(self):
        """Clear all widgets from the joint container"""
        while self.joint_layout.count():
            child = self.joint_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def analyze_joint_mesh_associations(self, joints, mesh_files, weapon_id):
        """Analyze which mesh files match which joints using best-match algorithm"""
        self.joint_mesh_associations = {}
        
        # Initialize all joints with empty lists
        for joint in joints:
            self.joint_mesh_associations[joint] = []
        
        # For each mesh file, find the best matching joint(s)
        for mesh_file in mesh_files:
            best_match, all_magazine_matches = self.find_best_joint_match_with_magazine_handling(mesh_file, joints)
            
            if best_match:
                if all_magazine_matches:
                    # Special case: this file matched multiple magazine/clip joints
                    # Add it to all matching magazine/clip joints
                    for magazine_joint in all_magazine_matches:
                        self.joint_mesh_associations[magazine_joint].append(mesh_file)
                        print("Assigned mesh '{0}' to magazine/clip joint '{1}' (special case)".format(mesh_file, magazine_joint))
                else:
                    # Normal case: single best match
                    self.joint_mesh_associations[best_match].append(mesh_file)
                    print("Assigned mesh '{0}' to joint '{1}' (best match)".format(mesh_file, best_match))
            else:
                print("No matching joint found for mesh file: {0}".format(mesh_file))
    
    def find_best_joint_match_with_magazine_handling(self, mesh_filename, available_joints):
        """Find the best matching joint, with special handling for magazine/clip joints"""
        mesh_base = os.path.splitext(mesh_filename)[0].lower()
        
        print("Finding best match for mesh file: {0}".format(mesh_filename))
        
        matches = []  # List of (joint_name, identifier, match_quality)
        magazine_special_matches = []  # List of magazine/clip joints that match with special rule
        
        # Check each joint to see if it matches this mesh file
        for joint_name in available_joints:
            if not joint_name.startswith('jnt_'):
                continue  # Skip non-jnt joints
            
            # Extract identifier after "jnt_"
            joint_identifier = joint_name[4:]  # Remove "jnt_" prefix
            
            # Check for magazine/clip special case matches
            is_magazine_special = self.is_magazine_clip_special_match(joint_identifier, mesh_base)
            
            if is_magazine_special:
                magazine_special_matches.append(joint_name)
                matches.append((joint_name, joint_identifier, 500))  # All get same score for special case
                print("  Magazine/clip special match: '{0}' with identifier '{1}' (quality: 500)".format(
                    joint_name, joint_identifier))
            else:
                # Regular matching logic
                match_quality = self.calculate_match_quality(mesh_base, joint_identifier, joint_name)
                
                if match_quality > 0:
                    matches.append((joint_name, joint_identifier, match_quality))
                    print("  Potential match: '{0}' with identifier '{1}' (quality: {2})".format(
                        joint_name, joint_identifier, match_quality))
        
        if not matches:
            print("  -> No matches found")
            return None, []
        
        # Sort by match quality (higher is better)
        matches.sort(key=lambda x: x[2], reverse=True)
        best_joint = matches[0][0]
        best_quality = matches[0][2]
        
        # Check if the best match is a magazine/clip special case
        if best_quality == 500 and magazine_special_matches:
            # This is a magazine/clip special case - return all matching magazine joints
            print("  -> MAGAZINE/CLIP SPECIAL: Assigning to {0} magazine/clip joints: {1}".format(
                len(magazine_special_matches), ', '.join(magazine_special_matches)))
            return best_joint, magazine_special_matches
        else:
            # Normal best match
            print("  -> BEST MATCH: '{0}' with quality {1}".format(best_joint, best_quality))
            return best_joint, []
    
    def is_magazine_clip_special_match(self, joint_identifier, mesh_base):
        """Check if this is a magazine/clip special case match"""
        joint_id_lower = joint_identifier.lower()
        
        # List of identifiers that get the special "mag" matching rule
        magazine_clip_identifiers = ['magazine', 'magazine1', 'clip_base', 'clip_base_full']
        
        return joint_id_lower in magazine_clip_identifiers and 'mag' in mesh_base
    
    def calculate_match_quality(self, mesh_base, joint_identifier, joint_name):
        """Calculate how well a joint identifier matches a mesh filename"""
        joint_id_lower = joint_identifier.lower()
        
        # Split mesh filename and joint identifier into words
        mesh_words = mesh_base.split('_')
        joint_words = joint_id_lower.split('_')
        
        # Look for the joint identifier pattern in the mesh filename
        match_found = False
        exact_sequence_match = False
        match_position = -1  # Position where the match starts in the filename
        
        # Method 1: Check for exact sequence match (consecutive words)
        if len(joint_words) > 1:
            # For compound identifiers like "bullet_shell", look for consecutive word matches
            for i in range(len(mesh_words) - len(joint_words) + 1):
                mesh_sequence = mesh_words[i:i + len(joint_words)]
                if mesh_sequence == joint_words:
                    exact_sequence_match = True
                    match_found = True
                    match_position = i
                    break
        
        # Method 2: Check for single word exact match
        if len(joint_words) == 1:
            try:
                match_position = mesh_words.index(joint_id_lower)
                exact_sequence_match = True
                match_found = True
            except ValueError:
                pass
        
        # Method 3: Check for substring match if no exact sequence found
        if not match_found and joint_id_lower in mesh_base:
            match_found = True
            # For substring matches, estimate position
            match_position = mesh_base.find(joint_id_lower) / len(mesh_base)
        
        if not match_found:
            return 0
        
        # Calculate quality score based on specificity and match type
        base_score = len(joint_id_lower) * 10  # Longer identifiers get higher base scores
        
        if exact_sequence_match:
            # Big bonus for exact word sequence matches
            base_score += 1000
            
            # Extra bonus for longer sequences (more specific)
            if len(joint_words) > 1:
                base_score += len(joint_words) * 100
        else:
            # Lower score for substring matches
            base_score += 100
        
        # Specificity bonus: longer identifiers that match get exponentially higher scores
        specificity_bonus = (len(joint_id_lower) ** 2) * 5
        
        # Position bonus: identifiers that appear later in the filename are more specific
        # This helps prioritize "bullet" over "wpn_ak74" in "SM_wpn_ak74_SM_bullet.FBX"
        if exact_sequence_match and match_position >= 0:
            # Calculate position as percentage through the filename
            position_percentage = float(match_position) / max(1, len(mesh_words) - len(joint_words))
            position_bonus = int(position_percentage * 500)  # Up to 500 point bonus for later positions
            
            # Special handling for weapon base identifiers (like "wpn_ak74")
            # If this looks like a weapon base identifier and there are words after it, deprioritize it
            is_weapon_base = ('wpn_' in joint_id_lower) and (match_position < len(mesh_words) - len(joint_words))
            if is_weapon_base and len(mesh_words) > match_position + len(joint_words):
                # This is likely a base weapon joint with more specific parts after it
                position_bonus -= 1000  # Heavy penalty for being a generic base identifier
                print("      - Detected weapon base identifier, applying penalty")
        else:
            position_bonus = 0
        
        final_score = base_score + specificity_bonus + position_bonus
        
        print("    Match analysis for '{0}':".format(joint_identifier))
        print("      - Exact sequence match: {0}".format(exact_sequence_match))
        print("      - Joint words: {0}".format(joint_words))
        print("      - Mesh words: {0}".format(mesh_words))
        print("      - Match position: {0}".format(match_position))
        print("      - Position bonus: {0}".format(position_bonus))
        print("      - Final score: {0}".format(final_score))
        
        return final_score
    
    def create_joint_association_widgets(self):
        """Create UI widgets showing joint-mesh associations"""
        sorted_joints = sorted(self.joint_mesh_associations.keys())
        
        for joint_name in sorted_joints:
            mesh_files = self.joint_mesh_associations[joint_name]
            
            # Create container for this joint
            joint_widget = QFrame()
            joint_widget.setProperty("class", "joint-item")
            joint_layout = QVBoxLayout(joint_widget)
            joint_layout.setContentsMargins(5, 5, 5, 5)
            joint_layout.setSpacing(3)
            
            # Joint name label
            name_label = QLabel(joint_name)
            name_label.setProperty("class", "joint-name")
            joint_layout.addWidget(name_label)
            
            if mesh_files:
                if len(mesh_files) == 1:
                    # Single mesh file - just show the name
                    mesh_label = QLabel("-> {0}".format(mesh_files[0]))
                    mesh_label.setProperty("class", "mesh-file")
                    joint_layout.addWidget(mesh_label)
                    
                    # Store the selection (no dropdown needed)
                    self.joint_selectors[joint_name] = mesh_files[0]
                    
                else:
                    # Multiple mesh files - create dropdown
                    selector_combo = QComboBox()
                    selector_combo.setProperty("class", "mesh-selector")
                    
                    for mesh_file in mesh_files:
                        selector_combo.addItem(mesh_file)
                    
                    # Add a label before the dropdown
                    multi_label = QLabel("-> Multiple files found:")
                    multi_label.setProperty("class", "mesh-file")
                    joint_layout.addWidget(multi_label)
                    joint_layout.addWidget(selector_combo)
                    
                    # Store the selector widget
                    self.joint_selectors[joint_name] = selector_combo
                    
            else:
                # No mesh files
                no_mesh_label = QLabel("-> No associated mesh file")
                no_mesh_label.setProperty("class", "no-mesh")
                joint_layout.addWidget(no_mesh_label)
                
                # Store that there's no selection
                self.joint_selectors[joint_name] = None
            
            # Add to main layout
            self.joint_layout.addWidget(joint_widget)
        
        # Add stretch at the end
        self.joint_layout.addStretch()
    
    def get_skeleton_joints_preview(self, skeleton_file):
        """Get actual joints from skeleton file, using persistent file-based caching"""
        
        # Create cache file path in the same directory as the skeleton
        skeleton_dir = os.path.dirname(skeleton_file)
        cache_file = os.path.join(skeleton_dir, "_joints_cache.txt")
        
        # Check if cache file exists and is newer than skeleton file
        cache_valid = False
        if os.path.exists(cache_file):
            try:
                cache_time = os.path.getmtime(cache_file)
                skeleton_time = os.path.getmtime(skeleton_file)
                if cache_time >= skeleton_time:
                    cache_valid = True
            except:
                cache_valid = False
        
        # Try to use cached data if valid
        if cache_valid:
            try:
                print("Reading cached joint data from {0}".format(cache_file))
                with open(cache_file, 'r') as f:
                    cached_joints = [line.strip() for line in f.readlines() if line.strip()]
                
                if cached_joints:
                    print("Loaded {0} joints from cache: {1}".format(
                        len(cached_joints), ", ".join(cached_joints)))
                    return cached_joints
                else:
                    print("Cache file was empty, will regenerate")
            except Exception as e:
                print("Failed to read cache file: {0}".format(str(e)))
        
        # Cache invalid or doesn't exist - analyze skeleton file
        joints = []
        
        try:
            print("Analyzing skeleton file to extract joint names...")
            
            # Clear selection and store existing scene state
            cmds.select(clear=True)
            existing_transforms = set(cmds.ls(type='transform', long=True))
            
            # Import skeleton temporarily
            cmds.file(skeleton_file, i=True, type="FBX", ignoreVersion=True, 
                     mergeNamespacesOnClash=False, namespace=":")
            
            # Find newly imported transforms
            new_transforms = set(cmds.ls(type='transform', long=True)) - existing_transforms
            
            # Get all joints from the newly imported objects
            all_new_joints = set()
            for transform in new_transforms:
                # Get joints in this transform hierarchy
                joints_in_transform = cmds.listRelatives(transform, allDescendents=True, type='joint', fullPath=True) or []
                all_new_joints.update(joints_in_transform)
            
            # Filter for joints with "jnt_" prefix and get their short names
            for joint in all_new_joints:
                joint_short_name = joint.split('|')[-1]
                if joint_short_name.startswith('jnt_'):
                    joints.append(joint_short_name)
                    print("Found joint: {0}".format(joint_short_name))
            
            # Clean up - delete the temporarily imported objects
            if new_transforms:
                transforms_to_delete = list(new_transforms)
                for transform in transforms_to_delete:
                    try:
                        if cmds.objExists(transform):
                            cmds.delete(transform)
                    except:
                        pass  # Ignore errors during cleanup
                print("Cleaned up temporary import")
            
            # Save results to cache file
            sorted_joints = sorted(joints) if joints else []
            
            try:
                print("Saving joint data to cache file: {0}".format(cache_file))
                with open(cache_file, 'w') as f:
                    for joint_name in sorted_joints:
                        f.write(joint_name + '\n')
                print("Cached {0} joints for future use".format(len(sorted_joints)))
            except Exception as e:
                print("Warning: Could not save cache file: {0}".format(str(e)))
            
            print("Analysis complete: found {0} joints with 'jnt_' prefix".format(len(sorted_joints)))
            return sorted_joints
            
        except Exception as e:
            print("Error analyzing skeleton joints: {0}".format(str(e)))
            return []
    
    def load_weapon_preview(self):
        """Load weapon preview image"""
        weapon_path = self.get_current_weapon_path()
        if not weapon_path:
            weapon_id = self.weapon_combo.currentData()
            if weapon_id and self.master_path:
                self.image_label.setText("Weapon directory not found\n\nUse 'Create Weapon Directory'\nto set up the folder structure")
                self.image_info_label.setText("Directory needs to be created")
            else:
                self.image_label.setText("Select a weapon to preview")
                self.image_info_label.setText("No preview available")
            return
        
        # Look for the first image file in weapon directory
        image_file = None
        image_extensions = ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.gif', '.webp']
        
        try:
            files = os.listdir(weapon_path)
            # Sort files to ensure consistent ordering
            files.sort()
            
            for filename in files:
                if any(filename.lower().endswith(ext) for ext in image_extensions):
                    image_file = os.path.join(weapon_path, filename)
                    break
        except Exception as e:
            self.image_label.setText("Error reading weapon directory:\n{0}".format(str(e)))
            self.image_info_label.setText("Cannot access weapon directory")
            return
        
        if image_file and os.path.exists(image_file):
            try:
                pixmap = QPixmap(image_file)
                if not pixmap.isNull():
                    # Scale image to fit label while maintaining aspect ratio
                    label_size = self.image_label.size()
                    if pyside_version == 6:
                        scaled_pixmap = pixmap.scaled(
                            label_size,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                    else:
                        scaled_pixmap = pixmap.scaled(
                            label_size,
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation
                        )
                    self.image_label.setPixmap(scaled_pixmap)
                    
                    # Update image info
                    file_size = os.path.getsize(image_file)
                    size_mb = file_size / (1024 * 1024)
                    image_info = "File: {0}\nSize: {1:.1f} MB\nDimensions: {2}x{3}".format(
                        os.path.basename(image_file), size_mb, pixmap.width(), pixmap.height())
                    self.image_info_label.setText(image_info)
                else:
                    self.image_label.setText("Could not load image:\n{0}".format(os.path.basename(image_file)))
                    self.image_info_label.setText("Invalid image file")
            except Exception as e:
                self.image_label.setText("Error loading image:\n{0}".format(str(e)))
                self.image_info_label.setText("Image loading failed")
        else:
            self.image_label.setText("No preview image found\nin weapon directory")
            self.image_info_label.setText("No image files (.png, .jpg, etc.) found")
    
    def update_import_button(self):
        """Update import and create directory button states"""
        weapon_path = self.get_current_weapon_path()
        has_weapon = self.weapon_combo.currentData() is not None
        has_path = weapon_path is not None
        has_master_path = bool(self.master_path)
        
        # Update import button
        self.import_btn.setEnabled(has_weapon and has_path and has_master_path)
        
        if not has_master_path:
            self.import_btn.setText("Import Weapon (Set Master Path First)")
        elif not has_weapon:
            self.import_btn.setText("Import Weapon (Select Weapon)")
        elif not has_path:
            self.import_btn.setText("Import Weapon (Create Directory First)")
        else:
            self.import_btn.setText("Import Weapon")
        
        # Update create directory button
        can_create_dir = has_weapon and has_master_path and not has_path
        self.create_dir_btn.setEnabled(can_create_dir)
        
        if not has_master_path:
            self.create_dir_btn.setText("Create Directory (Set Master Path First)")
        elif not has_weapon:
            self.create_dir_btn.setText("Create Directory (Select Weapon)")
        elif has_path:
            self.create_dir_btn.setText("Directory Exists")
        else:
            self.create_dir_btn.setText("Create Weapon Directory")
        
        # Update create all directories button
        self.create_all_btn.setEnabled(has_master_path)
        
        if not has_master_path:
            self.create_all_btn.setText("Create All Directories (Set Master Path First)")
        else:
            # Check how many directories need to be created
            missing_count = self.count_missing_weapon_directories()
            if missing_count > 0:
                self.create_all_btn.setText("Create All Weapon Directories ({0} missing)".format(missing_count))
            else:
                self.create_all_btn.setText("All Weapon Directories Exist")
                self.create_all_btn.setEnabled(False)
    
    def update_load_rig_button(self):
        """Update Load Rig button state based on Maya rig file existence"""
        weapon_id = self.weapon_combo.currentData()
        weapon_path = self.get_current_weapon_path()
        has_weapon = weapon_id is not None
        has_path = weapon_path is not None
        has_master_path = bool(self.master_path)
        
        # Check if a Maya rig file exists for this weapon
        has_rig_file = False
        if has_weapon and has_path:
            # Look for Maya files with the weapon identifier as the name
            rig_file_path = os.path.join(weapon_path, weapon_id + ".ma")
            rig_file_path_mb = os.path.join(weapon_path, weapon_id + ".mb")
            has_rig_file = os.path.exists(rig_file_path) or os.path.exists(rig_file_path_mb)
        
        # Enable button only if rig file exists
        self.load_rig_btn.setEnabled(has_rig_file and has_weapon and has_path and has_master_path)
        
        # Update button text based on state
        if not has_master_path:
            self.load_rig_btn.setText("Load Rig (Set Master Path First)")
        elif not has_weapon:
            self.load_rig_btn.setText("Load Rig (Select Weapon)")
        elif not has_path:
            self.load_rig_btn.setText("Load Rig (Create Directory First)")
        elif not has_rig_file:
            self.load_rig_btn.setText("Load Rig (No Rig File Found)")
        else:
            self.load_rig_btn.setText("Load Rig")
    
    def count_missing_weapon_directories(self):
        """Count how many weapon directories are missing"""
        if not self.master_path:
            return 0
        
        missing_count = 0
        
        for category, weapons in self.weapon_categories.items():
            if category == "All Weapons":
                continue
            
            category_folder = self.category_folders.get(category, "")
            if not category_folder:
                continue
            
            for weapon_name, weapon_id in weapons:
                weapon_path = os.path.join(self.master_path, "Source", "Weapons", category_folder, weapon_id)
                if not os.path.exists(weapon_path):
                    missing_count += 1
        
        return missing_count
    
    def create_all_weapon_directories(self):
        """Create directories for all weapons that don't exist"""
        if not self.create_all_btn.isEnabled():
            return
        
        if not self.master_path:
            QMessageBox.warning(self, "Error", "Master path is not set.")
            return
        
        # Confirm with user before creating many directories
        missing_count = self.count_missing_weapon_directories()
        if missing_count == 0:
            QMessageBox.information(self, "All Directories Exist", "All weapon directories already exist.")
            return
        
        reply = QMessageBox.question(
            self,
            "Create All Weapon Directories",
            "This will create {0} weapon directories.\n\n"
            "Are you sure you want to create all missing weapon directories?\n\n"
            "This will create the complete folder structure for all weapons "
            "across all categories in your STALKER2_ModdingTools directory.".format(missing_count),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Create all missing directories
        created_count = 0
        failed_count = 0
        created_details = []
        failed_details = []
        
        for category, weapons in self.weapon_categories.items():
            if category == "All Weapons":
                continue
            
            category_folder = self.category_folders.get(category, "")
            if not category_folder:
                continue
            
            for weapon_name, weapon_id in weapons:
                weapon_path = os.path.join(self.master_path, "Source", "Weapons", category_folder, weapon_id)
                
                if not os.path.exists(weapon_path):
                    try:
                        os.makedirs(weapon_path)
                        created_count += 1
                        created_details.append("Created: {0} ({1})".format(weapon_name, weapon_id))
                        print("Created weapon directory: {0}".format(weapon_path))
                    except Exception as e:
                        failed_count += 1
                        failed_details.append("Failed: {0} ({1}) - {2}".format(weapon_name, weapon_id, str(e)))
                        print("Error creating weapon directory {0}: {1}".format(weapon_path, str(e)))
        
        # Show results
        if created_count > 0 or failed_count > 0:
            message = "Weapon directory creation completed!\n\n"
            message += "Created: {0} directories\n".format(created_count)
            message += "Failed: {0} directories\n\n".format(failed_count)
            
            if created_count > 0:
                message += "SUCCESSFULLY CREATED:\n"
                # Show first 10 created, then summarize if more
                show_count = min(10, len(created_details))
                for i in range(show_count):
                    message += "- {0}\n".format(created_details[i])
                if len(created_details) > 10:
                    message += "... and {0} more\n".format(len(created_details) - 10)
                message += "\n"
            
            if failed_count > 0:
                message += "FAILED TO CREATE:\n"
                for detail in failed_details:
                    message += "- {0}\n".format(detail)
                message += "\nCheck the console for detailed error messages.\n"
            
            message += "\nDirectory structure is now ready for weapon assets.\n"
            message += "Add your weapon files to the appropriate directories:\n"
            message += "- SK_[weapon_id].fbx (skeleton files)\n"
            message += "- wpn_*_[weapon_id]_*.fbx (mesh parts)\n"
            message += "- [weapon_id].png/jpg (preview images)"
            
            if failed_count > 0:
                QMessageBox.warning(self, "Creation Complete (with errors)", message)
            else:
                QMessageBox.information(self, "Creation Complete", message)
        
        # Refresh the UI to reflect the new directories
        self.refresh_weapon_data()
    
    def create_weapon_directory(self):
        """Create the weapon directory structure"""
        if not self.create_dir_btn.isEnabled():
            return
        
        weapon_name = self.weapon_combo.currentText()
        weapon_id = self.weapon_combo.currentData()
        
        # Create the directory
        weapon_path = self.get_current_weapon_path(create_if_missing=True)
        
        if weapon_path and os.path.exists(weapon_path):
            message = "Weapon directory created successfully!\n\n"
            message += "Weapon: {0}\n".format(weapon_name)
            message += "Directory: {0}\n\n".format(weapon_path)
            message += "You can now add your weapon files to this directory:\n"
            message += "- SK_{0}.fbx (skeleton file)\n".format(weapon_id)
            message += "- wpn_*_{0}_*.fbx (mesh parts)\n".format(weapon_id)
            message += "- {0}.png/jpg (preview image)\n\n".format(weapon_id)
            message += "The directory structure has been created and is ready for your weapon assets."
            
            QMessageBox.information(self, "Directory Created", message)
            
            # Refresh the UI to reflect the new directory
            self.refresh_weapon_data()
        else:
            QMessageBox.warning(self, "Creation Failed", "Failed to create weapon directory. Check the console for details.")
    
    def refresh_weapon_data(self):
        """Refresh weapon data and analysis"""
        current_weapon = self.weapon_combo.currentText()
        self.on_weapon_changed(current_weapon)
    
    def import_weapon(self):
        """Import the selected weapon with skeleton and constrained meshes"""
        if not self.import_btn.isEnabled():
            return
        
        weapon_name = self.weapon_combo.currentText()
        weapon_id = self.weapon_combo.currentData()
        
        if not weapon_id:
            QMessageBox.warning(self, "Import Error", "Please select a weapon to import.")
            return
        
        # Try to get the weapon path, creating directory if needed
        weapon_path = self.get_current_weapon_path(create_if_missing=True)
        
        if not weapon_path:
            QMessageBox.warning(self, "Import Error", "Cannot access or create weapon directory. Check the console for details.")
            return
        
        try:
            # Import skeleton and meshes
            imported_skeleton, imported_meshes, constraint_count = self.import_weapon_files(weapon_path, weapon_id)
            
            # Show results
            if imported_skeleton:
                message = "Weapon import completed successfully!\n\n"
                message += "Weapon: {0}\n".format(weapon_name)
                message += "Skeleton: {0}\n".format(imported_skeleton)
                message += "Imported meshes: {0}\n".format(len(imported_meshes))
                message += "Constraints created: {0}\n\n".format(constraint_count)
                
                if imported_meshes:
                    message += "Imported mesh files:\n"
                    for mesh_file in imported_meshes:
                        message += "- {0}\n".format(os.path.basename(mesh_file))
                else:
                    message += "No associated mesh files found.\n"
                
                message += "\nThe skeleton and meshes are now ready for use."
                
                QMessageBox.information(self, "Import Successful", message)
            else:
                QMessageBox.warning(self, "Import Error", "Failed to import weapon skeleton.")
                
        except Exception as e:
            error_msg = "Error during weapon import: {0}".format(str(e))
            print("Import error details: {0}".format(error_msg))
            QMessageBox.critical(self, "Import Error", error_msg)
    
    def load_weapon_rig(self):
        """Reference the Maya rig file for the selected weapon"""
        if not self.load_rig_btn.isEnabled():
            return
        
        weapon_name = self.weapon_combo.currentText()
        weapon_id = self.weapon_combo.currentData()
        weapon_path = self.get_current_weapon_path()
        
        if not weapon_id or not weapon_path:
            QMessageBox.warning(self, "Load Error", "Please select a weapon with an existing directory.")
            return
        
        # Look for Maya rig files
        rig_file_ma = os.path.join(weapon_path, weapon_id + ".ma")
        rig_file_mb = os.path.join(weapon_path, weapon_id + ".mb")
        
        rig_file_to_load = None
        if os.path.exists(rig_file_ma):
            rig_file_to_load = rig_file_ma
        elif os.path.exists(rig_file_mb):
            rig_file_to_load = rig_file_mb
        
        if not rig_file_to_load:
            QMessageBox.warning(self, "Load Error", "No Maya rig file found for weapon: {0}".format(weapon_id))
            return
        
        try:
            # Reference the Maya file
            import maya.cmds as cmds
            
            # Create reference namespace based on weapon ID
            namespace = weapon_id + "_rig"
            
            # Reference the file
            cmds.file(rig_file_to_load, reference=True, namespace=namespace)
            
            print("Referenced rig file: {0} with namespace: {1}".format(rig_file_to_load, namespace))
            
            # Show success message and close the tool
            QMessageBox.information(self, "Rig Loaded", 
                "Successfully referenced rig file:\n{0}\n\nNamespace: {1}\n\nThe importer will now close.".format(
                    os.path.basename(rig_file_to_load), namespace))
            
            # Close the tool
            self.accept()
            
        except Exception as e:
            error_msg = "Error loading rig file: {0}".format(str(e))
            print("Rig load error details: {0}".format(error_msg))
            QMessageBox.critical(self, "Load Error", error_msg)
    
    def import_weapon_files(self, weapon_path, weapon_id):
        """Import skeleton and associated mesh files"""
        imported_skeleton = None
        imported_meshes = []
        constraint_count = 0
        
        # Find skeleton file
        skeleton_file = None
        for filename in os.listdir(weapon_path):
            if filename.startswith('SK_') and filename.lower().endswith('.fbx'):
                skeleton_file = os.path.join(weapon_path, filename)
                break
        
        if not skeleton_file:
            raise Exception("No skeleton file (SK_*.fbx) found in weapon directory")
        
        print("Found skeleton file: {0}".format(os.path.basename(skeleton_file)))
        
        # Clear selection before import
        cmds.select(clear=True)
        
        # Step 1: Import skeleton first
        print("\n=== IMPORTING SKELETON ===")
        print("Importing: {0}".format(skeleton_file))
        
        # Store existing transforms to identify new ones
        existing_transforms = set(cmds.ls(type='transform', long=True))
        
        # Import skeleton
        cmds.file(skeleton_file, i=True, type="FBX", ignoreVersion=True, 
                 mergeNamespacesOnClash=False, namespace=":")
        
        # Find newly imported transforms
        new_transforms = set(cmds.ls(type='transform', long=True)) - existing_transforms
        
        # Find the skeleton root - look for the top-level transform among new imports
        skeleton_candidates = []
        for transform in new_transforms:
            # Check if this transform has no parent (top-level) or is a likely skeleton root
            parent = cmds.listRelatives(transform, parent=True, fullPath=True)
            if not parent or not any(p in new_transforms for p in parent):
                skeleton_candidates.append(transform)
        
        if skeleton_candidates:
            # Prefer transforms with 'SK_' or weapon_id in name
            for candidate in skeleton_candidates:
                if 'SK_' in candidate or weapon_id.lower() in candidate.lower():
                    imported_skeleton = candidate
                    break
            if not imported_skeleton:
                imported_skeleton = skeleton_candidates[0]  # Take first candidate
        else:
            # Fallback: try to find any transform with skeleton-like names
            for transform in new_transforms:
                if 'SK_' in transform or weapon_id.lower() in transform.lower():
                    imported_skeleton = transform
                    break
        
        if not imported_skeleton:
            raise Exception("Could not identify imported skeleton root")
        
        print("Identified skeleton root: {0}".format(imported_skeleton))
        
        # Get all joints in the skeleton hierarchy
        all_joints = cmds.listRelatives(imported_skeleton, allDescendents=True, type='joint', fullPath=True) or []
        if not all_joints:
            print("Warning: No joints found in imported skeleton")
            # Try to find joints in any of the imported transforms
            for transform in new_transforms:
                joints_in_transform = cmds.listRelatives(transform, allDescendents=True, type='joint', fullPath=True) or []
                all_joints.extend(joints_in_transform)
        
        print("Found {0} joints in skeleton:".format(len(all_joints)))
        for joint in all_joints:
            print("  - {0}".format(joint.split('|')[-1]))
        
        # Step 2: Import mesh files based on user selections
        print("\n=== IMPORTING AND CONSTRAINING MESHES ===")
        
        # Get mesh files to import from user selections
        mesh_files_to_import = []
        for joint_name, selector in self.joint_selectors.items():
            if selector is not None:
                if isinstance(selector, str):
                    # Single file selection
                    mesh_files_to_import.append((joint_name, selector))
                elif hasattr(selector, 'currentText'):
                    # QComboBox selection
                    selected_file = selector.currentText()
                    if selected_file:
                        mesh_files_to_import.append((joint_name, selected_file))
        
        print("Will import {0} mesh files based on user selections".format(len(mesh_files_to_import)))
        
        for i, (target_joint_name, mesh_filename) in enumerate(mesh_files_to_import):
            try:
                mesh_file_path = os.path.join(weapon_path, mesh_filename)
                print("\nImporting mesh {0}/{1}: {2} for joint {3}".format(
                    i+1, len(mesh_files_to_import), mesh_filename, target_joint_name))
                
                # Clear selection before import
                cmds.select(clear=True)
                
                # Store existing transforms before this mesh import
                existing_before_mesh = set(cmds.ls(type='transform', long=True))
                
                # Import mesh
                cmds.file(mesh_file_path, i=True, type="FBX", ignoreVersion=True, 
                         mergeNamespacesOnClash=False, namespace=":")
                
                # Find newly imported transforms for this mesh
                new_mesh_transforms = set(cmds.ls(type='transform', long=True)) - existing_before_mesh
                
                print("  Found {0} new transforms after import".format(len(new_mesh_transforms)))
                
                # Find the target joint by name
                target_joint = None
                for joint in all_joints:
                    if joint.split('|')[-1] == target_joint_name:
                        target_joint = joint
                        break
                
                if target_joint:
                    print("  Target joint: {0}".format(target_joint.split('|')[-1]))
                    
                    # Create constraints for each new transform
                    constrained_objects = []
                    for mesh_transform in new_mesh_transforms:
                        try:
                            # Create position and rotation constraints
                            pos_constraint = cmds.pointConstraint(target_joint, mesh_transform, 
                                                                maintainOffset=False)[0]
                            rot_constraint = cmds.orientConstraint(target_joint, mesh_transform, 
                                                                 maintainOffset=False)[0]
                            constraint_count += 2
                            constrained_objects.append(mesh_transform.split('|')[-1])
                            print("    Constrained: {0}".format(mesh_transform.split('|')[-1]))
                        except Exception as e:
                            print("    Warning: Could not constrain {0}: {1}".format(
                                mesh_transform.split('|')[-1], str(e)))
                    
                    if constrained_objects:
                        print("  Successfully constrained {0} object(s) to {1}".format(
                            len(constrained_objects), target_joint.split('|')[-1]))
                    else:
                        print("  Warning: No objects were successfully constrained")
                
                else:
                    print("  Warning: Could not find target joint '{0}' in skeleton".format(target_joint_name))
                    print("    Available joints: {0}".format([j.split('|')[-1] for j in all_joints]))
                
                imported_meshes.append(mesh_file_path)
                
            except Exception as e:
                print("Error importing mesh {0}: {1}".format(mesh_filename, str(e)))
        
        # Step 3: Import attachments
        imported_attachments = []
        attachment_data = self.get_attachment_data()
        
        if attachment_data:
            print("\n=== IMPORTING ATTACHMENTS ===")
            print("Will import {0} attachment(s)".format(len(attachment_data)))
            
            for i, attachment in enumerate(attachment_data):
                try:
                    print("\nImporting attachment {0}/{1}: {2}".format(
                        i+1, len(attachment_data), attachment['name']))
                    
                    # Clear selection before import
                    cmds.select(clear=True)
                    
                    # Store existing transforms before this attachment import
                    existing_before_attachment = set(cmds.ls(type='transform', long=True))
                    
                    # Import attachment
                    cmds.file(attachment['fbx_path'], i=True, type="FBX", ignoreVersion=True, 
                             mergeNamespacesOnClash=False, namespace=":")
                    
                    # Find newly imported transforms for this attachment
                    new_attachment_transforms = set(cmds.ls(type='transform', long=True)) - existing_before_attachment
                    
                    print("  Found {0} new transforms after import".format(len(new_attachment_transforms)))
                    
                    # Find the target joint by name
                    target_joint = None
                    for joint in all_joints:
                        if joint.split('|')[-1] == attachment['joint_name']:
                            target_joint = joint
                            break
                    
                    if target_joint:
                        print("  Target joint: {0}".format(target_joint.split('|')[-1]))
                        
                        # Create constraints for each new transform
                        constrained_objects = []
                        for attachment_transform in new_attachment_transforms:
                            try:
                                # Create position and rotation constraints
                                pos_constraint = cmds.pointConstraint(target_joint, attachment_transform, 
                                                                    maintainOffset=False)[0]
                                rot_constraint = cmds.orientConstraint(target_joint, attachment_transform, 
                                                                     maintainOffset=False)[0]
                                constraint_count += 2
                                constrained_objects.append(attachment_transform.split('|')[-1])
                                print("    Constrained: {0}".format(attachment_transform.split('|')[-1]))
                                
                                # Store the category and display name as custom attributes for the weapon rig tool
                                try:
                                    # Store category
                                    if not cmds.attributeQuery('S2_AttachmentCategory', node=attachment_transform, exists=True):
                                        cmds.addAttr(attachment_transform, longName='S2_AttachmentCategory', 
                                                   dataType='string')
                                    cmds.setAttr(attachment_transform + '.S2_AttachmentCategory', 
                                               attachment['category'], type='string')
                                    
                                    # Store display name
                                    if not cmds.attributeQuery('S2_AttachmentName', node=attachment_transform, exists=True):
                                        cmds.addAttr(attachment_transform, longName='S2_AttachmentName', 
                                                   dataType='string')
                                    cmds.setAttr(attachment_transform + '.S2_AttachmentName', 
                                               attachment['name'], type='string')
                                    
                                    print("    Stored category: '{0}', display name: '{1}'".format(
                                        attachment['category'], attachment['name']))
                                except Exception as e:
                                    print("    Warning: Could not store attachment attributes: {0}".format(str(e)))
                                
                                # Set initial visibility
                                cmds.setAttr(attachment_transform + '.visibility', attachment['visible'])
                                if not attachment['visible']:
                                    print("    Set to hidden (as requested)")
                                
                            except Exception as e:
                                print("    Warning: Could not constrain {0}: {1}".format(
                                    attachment_transform.split('|')[-1], str(e)))
                        
                        if constrained_objects:
                            print("  Successfully constrained {0} object(s) to {1}".format(
                                len(constrained_objects), target_joint.split('|')[-1]))
                            
                            imported_attachments.append({
                                'name': attachment['name'],
                                'joint_name': attachment['joint_name'],
                                'transforms': list(new_attachment_transforms),
                                'visible': attachment['visible']
                            })
                        else:
                            print("  Warning: No objects were successfully constrained")
                    
                    else:
                        print("  Warning: Could not find target joint '{0}' in skeleton".format(attachment['joint_name']))
                        print("    Available joints: {0}".format([j.split('|')[-1] for j in all_joints]))
                
                except Exception as e:
                    print("Error importing attachment {0}: {1}".format(attachment['name'], str(e)))
        
        print("\n=== IMPORT SUMMARY ===")
        print("Skeleton: {0}".format(imported_skeleton.split('|')[-1] if imported_skeleton else "Failed"))
        print("Meshes imported: {0}".format(len(imported_meshes)))
        print("Attachments imported: {0}".format(len(imported_attachments)))
        print("Constraints created: {0}".format(constraint_count))
        
        # Organize into groups if checkbox is checked
        if self.organize_checkbox.isChecked():
            self.organize_imported_assets(imported_skeleton, weapon_id, imported_attachments)
        
        return imported_skeleton, imported_meshes, constraint_count
    
    def organize_imported_assets(self, imported_skeleton, weapon_id, imported_attachments=None):
        """Organize imported assets into S2_Weapon > S2_Skeleton + S2_Mesh + S2_Attachments groups"""
        print("\n=== ORGANIZING INTO GROUPS ===")
        
        try:
            # Create main weapon group
            main_group = "S2_Weapon"
            if cmds.objExists(main_group):
                # If it exists, make it unique
                main_group = cmds.group(empty=True, name=main_group)
            else:
                main_group = cmds.group(empty=True, name=main_group)
            
            print("Created main group: {0}".format(main_group))
            
            # Create skeleton group
            skeleton_group = cmds.group(empty=True, name="S2_Skeleton", parent=main_group)
            print("Created skeleton group: {0}".format(skeleton_group))
            
            # Create mesh group  
            mesh_group = cmds.group(empty=True, name="S2_Mesh", parent=main_group)
            print("Created mesh group: {0}".format(mesh_group))
            
            # Create attachments group under mesh group
            attachments_group = cmds.group(empty=True, name="S2_Attachments", parent=mesh_group)
            print("Created attachments group: {0}".format(attachments_group))
            
            # Move skeleton to skeleton group
            if imported_skeleton and cmds.objExists(imported_skeleton):
                skeleton_short_name = imported_skeleton.split('|')[-1]
                try:
                    cmds.parent(imported_skeleton, skeleton_group)
                    print("Moved skeleton '{0}' to skeleton group".format(skeleton_short_name))
                except Exception as e:
                    print("Warning: Could not parent skeleton to group: {0}".format(str(e)))
            
            # Find all mesh objects (non-joint transforms that aren't part of the skeleton hierarchy)
            all_transforms = cmds.ls(type='transform')
            mesh_objects = []
            
            # Get all joints in the skeleton to exclude them
            skeleton_joints = set()
            if imported_skeleton and cmds.objExists(imported_skeleton):
                skeleton_joints_list = cmds.listRelatives(imported_skeleton, allDescendents=True, type='joint', fullPath=True) or []
                skeleton_joints = set(skeleton_joints_list)
            
            # FIRST: Organize attachments into attachments group (do this before regular meshes)
            attachment_transforms = set()
            if imported_attachments:
                attachment_count = 0
                print("\n--- Organizing Attachments First ---")
                for attachment in imported_attachments:
                    attachment_name = attachment.get('name', 'Unknown')
                    for attachment_transform in attachment['transforms']:
                        attachment_transforms.add(attachment_transform)  # Track for exclusion
                        try:
                            # Check if it exists and needs to be moved
                            if cmds.objExists(attachment_transform):
                                current_parent = cmds.listRelatives(attachment_transform, parent=True, fullPath=True)
                                # Move to attachments group if it's top-level or not already in our group structure
                                if not current_parent or not any(attachments_group in str(p) for p in current_parent):
                                    cmds.parent(attachment_transform, attachments_group)
                                    print("Moved attachment '{0}' ({1}) to attachments group".format(
                                        attachment_transform.split('|')[-1], attachment_name))
                                    attachment_count += 1
                                else:
                                    print("Attachment '{0}' already properly organized".format(
                                        attachment_transform.split('|')[-1]))
                        except Exception as e:
                            print("Warning: Could not parent attachment '{0}' to group: {1}".format(
                                attachment_transform.split('|')[-1], str(e)))
                
                print("Organized {0} attachment objects into attachments group".format(attachment_count))
                print("Attachment transforms tracked for exclusion: {0}".format([t.split('|')[-1] for t in attachment_transforms]))
            else:
                print("No attachments found to organize")
            
            # SECOND: Find regular mesh objects (transforms that are not joints, attachments, or already in groups)
            print("\n--- Organizing Regular Meshes ---")
            for transform in all_transforms:
                # Skip if it's a joint
                if cmds.objectType(transform) == 'joint':
                    continue
                    
                # Skip if it's already in skeleton hierarchy
                if transform in skeleton_joints:
                    continue
                    
                # Skip if it's an attachment transform (will be organized separately)
                if transform in attachment_transforms:
                    continue
                    
                # Skip if it's one of our created groups
                if transform in [main_group, skeleton_group, mesh_group, attachments_group]:
                    continue
                    
                # Skip if it already has a parent in our groups (including attachments group)
                parents = cmds.listRelatives(transform, parent=True, fullPath=True) or []
                if any(main_group in parent or skeleton_group in parent or mesh_group in parent or attachments_group in parent for parent in parents):
                    continue
                    
                # Skip if it's the skeleton root
                if transform == imported_skeleton:
                    continue
                    
                # Check if it looks like a weapon mesh (contains weapon_id or common mesh prefixes)
                transform_name = transform.split('|')[-1].lower()
                if (weapon_id.lower() in transform_name or 
                    transform_name.startswith('sm_') or 
                    transform_name.startswith('wpn_') or
                    'bullet' in transform_name or
                    'mag' in transform_name or
                    'trigger' in transform_name or
                    'selector' in transform_name):
                    print("Detected mesh candidate: {0}".format(transform.split('|')[-1]))
                    mesh_objects.append(transform)
            
            # Move mesh objects to mesh group
            if mesh_objects:
                for mesh_obj in mesh_objects:
                    try:
                        # Check if it doesn't already have a parent (top-level objects)
                        current_parent = cmds.listRelatives(mesh_obj, parent=True, fullPath=True)
                        if not current_parent:
                            cmds.parent(mesh_obj, mesh_group)
                            print("Moved mesh '{0}' to mesh group".format(mesh_obj.split('|')[-1]))
                    except Exception as e:
                        print("Warning: Could not parent mesh '{0}' to group: {1}".format(
                            mesh_obj.split('|')[-1], str(e)))
                        
                print("Organized {0} mesh objects into mesh group".format(len(mesh_objects)))
            else:
                print("No mesh objects found to organize")
            
            # Print final hierarchy for verification
            print("\n=== FINAL ORGANIZATION HIERARCHY ===")
            print("S2_Weapon")
            print("  ├── S2_Skeleton")
            print("  └── S2_Mesh")
            print("      └── S2_Attachments")
            
            # Verify the actual hierarchy
            try:
                skeleton_children = cmds.listRelatives(skeleton_group, children=True) or []
                mesh_children = cmds.listRelatives(mesh_group, children=True) or []
                attachment_children = cmds.listRelatives(attachments_group, children=True) or []
                
                print("Skeleton group contains: {0} object(s)".format(len(skeleton_children)))
                print("Mesh group contains: {0} object(s)".format(len(mesh_children) - 1))  # -1 for attachments group
                print("Attachments group contains: {0} object(s)".format(len(attachment_children)))
            except:
                print("Could not verify hierarchy details")
                
            print("Asset organization complete")
            
        except Exception as e:
            print("Error organizing assets: {0}".format(str(e)))
    
    def determine_target_joint(self, mesh_filename, available_joints):
        """Determine which joint a mesh should be constrained to based on filename"""
        # Remove file extension and make lowercase for matching
        base_name = os.path.splitext(mesh_filename)[0].lower()
        
        print("    Analyzing mesh file: {0}".format(mesh_filename))
        
        # Check each joint to see if its identifier matches this mesh file
        for joint in available_joints:
            joint_short_name = joint.split('|')[-1]  # Get short name from full path
            
            if not joint_short_name.startswith('jnt_'):
                continue  # Skip non-jnt joints
            
            # Extract identifier after "jnt_"
            joint_identifier = joint_short_name[4:]  # Remove "jnt_" prefix
            
            print("    Checking joint '{0}' with identifier '{1}'".format(joint_short_name, joint_identifier))
            
            # Special case for magazine - check for "mag" in filename
            if joint_identifier.lower() == 'magazine':
                if 'mag' in base_name:
                    print("    -> MATCH: Magazine joint matches file with 'mag'")
                    return joint
                continue
            
            # Check if the joint identifier appears in the mesh filename
            if joint_identifier.lower() in base_name:
                print("    -> MATCH: Identifier '{0}' found in filename".format(joint_identifier))
                return joint
            
            # Also try with underscores replaced with nothing (in case of naming variations)
            identifier_no_underscores = joint_identifier.replace('_', '').lower()
            mesh_no_underscores = base_name.replace('_', '')
            
            if identifier_no_underscores in mesh_no_underscores:
                print("    -> MATCH: Identifier '{0}' found in filename (no underscores)".format(joint_identifier))
                return joint
        
        print("    -> No matching joint found for filename: {0}".format(mesh_filename))
        return None
    
    def load_custom_weapon_configs(self):
        """Load custom weapon configurations from JSON files in the config folder"""
        if not self.master_path:
            print("No master path set, skipping custom config loading")
            return
        
        config_dir = os.path.join(self.master_path, "Source", "Weapons", "config")
        if not os.path.exists(config_dir):
            print("Config directory does not exist: {0}".format(config_dir))
            return
        
        try:
            loaded_count = 0
            for filename in os.listdir(config_dir):
                if filename.endswith('.json'):
                    config_file = os.path.join(config_dir, filename)
                    try:
                        with open(config_file, 'r') as f:
                            config_data = json.load(f)
                        
                        self.process_config_data(config_data, filename)
                        loaded_count += 1
                        
                    except Exception as e:
                        print("Error loading config {0}: {1}".format(filename, str(e)))
            
            if loaded_count > 0:
                print("Loaded {0} custom weapon config(s)".format(loaded_count))
                
        except Exception as e:
            print("Error reading config directory: {0}".format(str(e)))
    
    def process_config_data(self, config_data, filename):
        """Process a single config file and add weapons to categories"""
        try:
            category_name = config_data.get('category_name', 'Custom')
            category_folder = config_data.get('category_folder', 'custom')
            weapons = config_data.get('weapons', [])
            
            if not weapons:
                print("No weapons found in config: {0}".format(filename))
                return
            
            # Add category if it doesn't exist
            if category_name not in self.weapon_categories:
                self.weapon_categories[category_name] = []
                self.category_folders[category_name] = category_folder
                print("Added new category: {0} (folder: {1})".format(category_name, category_folder))
            
            # Add weapons to category
            for weapon in weapons:
                weapon_name = weapon.get('name', '')
                weapon_id = weapon.get('id', '')
                
                if weapon_name and weapon_id:
                    self.weapon_categories[category_name].append((weapon_name, weapon_id))
                    print("Added weapon: {0} ({1}) to category {2}".format(
                        weapon_name, weapon_id, category_name))
                else:
                    print("Invalid weapon entry in {0}: {1}".format(filename, weapon))
                    
        except Exception as e:
            print("Error processing config data from {0}: {1}".format(filename, str(e)))
    
    def create_new_config(self):
        """Open dialog to create a new weapon config"""
        if not self.master_path:
            QMessageBox.warning(self, "No Master Path", "Please set a master path before creating configs.")
            return
        
        config_dir = os.path.join(self.master_path, "Source", "Weapons", "config")
        
        # Create config directory if it doesn't exist
        try:
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
                print("Created config directory: {0}".format(config_dir))
        except Exception as e:
            QMessageBox.critical(self, "Error", "Could not create config directory: {0}".format(str(e)))
            return
        
        # Open config creation dialog
        existing_categories = list(self.weapon_categories.keys())
        dialog = WeaponConfigDialog(self, existing_categories, config_dir)
        
        if dialog.exec_() == QDialog.Accepted:
            config_data = dialog.get_config_data()
            if config_data:
                try:
                    # Generate filename
                    import time
                    timestamp = int(time.time())
                    config_filename = "{0}_{1}.json".format(
                        config_data['category_folder'], timestamp)
                    config_file = os.path.join(config_dir, config_filename)
                    
                    with open(config_file, 'w') as f:
                        json.dump(config_data, f, indent=2)
                    
                    print("Created config: {0}".format(config_file))
                    
                    # Show detailed confirmation dialog
                    self.show_config_created_confirmation(config_data, config_filename)
                    
                    # Reload configs to show the new one
                    self.reload_custom_configs()
                    
                except Exception as e:
                    QMessageBox.critical(self, "Error", 
                        "Could not create config file: {0}".format(str(e)))
    
    def show_config_created_confirmation(self, config_data, config_filename):
        """Show detailed confirmation with setup instructions after config creation"""
        category_name = config_data.get('category_name', 'Unknown')
        category_folder = config_data.get('category_folder', 'unknown')
        weapons = config_data.get('weapons', [])
        
        # Build message with detailed info
        message = "Successfully created weapon configuration!\n\n"
        message += "CONFIG DETAILS:\n"
        message += "File: {0}\n".format(config_filename)
        message += "Category: {0}\n".format(category_name)
        message += "Folder: {0}\n".format(category_folder)
        message += "Weapons: {0}\n\n".format(len(weapons))
        
        # List weapons
        if weapons:
            message += "WEAPONS ADDED:\n"
            for i, weapon in enumerate(weapons, 1):
                weapon_name = weapon.get('name', 'Unknown')
                weapon_id = weapon.get('id', 'unknown')
                message += "{0}. {1} (ID: {2})\n".format(i, weapon_name, weapon_id)
        
        message += "\nSETUP INSTRUCTIONS:\n"
        message += "To use these weapons in the importer:\n\n"
        
        message += "1. CREATE FOLDERS:\n"
        weapon_path = "Source/Weapons/{0}".format(category_folder)
        message += "   Create these folders in your master path:\n"
        message += "   {0}/\n".format(weapon_path)
        
        if weapons:
            for weapon in weapons:
                weapon_id = weapon.get('id', 'unknown')
                message += "   {0}/{1}/\n".format(weapon_path, weapon_id)
        
        message += "\n2. ADD FILES:\n"
        message += "   For each weapon folder, add:\n"
        message += "   - SK_weaponname.FBX (main skeleton)\n"
        message += "   - Additional mesh FBX files\n"
        message += "   - Texture files (optional preview)\n"
        
        message += "\n3. REFRESH:\n"
        message += "   Click 'Refresh' or 'Reload Configs' in the main tool\n"
        message += "   to see your new category and weapons."
        
        # Create custom message box with more space
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Configuration Created Successfully")
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setText("Weapon configuration created successfully!")
        msg_box.setDetailedText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        
        # Make the dialog larger to show the detailed text by default
        msg_box.setStyleSheet("""
            QMessageBox {
                min-width: 500px;
            }
            QMessageBox QTextEdit {
                min-width: 500px;
                min-height: 300px;
                font-family: Consolas, Monaco, monospace;
                font-size: 10px;
            }
        """)
        
        # Auto-expand the details
        for button in msg_box.buttons():
            if msg_box.buttonRole(button) == QMessageBox.ActionRole:
                button.click()
                break
        
        msg_box.exec_()
    
    def reload_custom_configs(self):
        """Reload all custom weapon configurations"""
        if not self.master_path:
            QMessageBox.warning(self, "No Master Path", "Please set a master path before reloading configs.")
            return
        
        # Store current selections
        current_category = self.category_combo.currentText()
        current_weapon = self.weapon_combo.currentText()
        
        # Remove all custom categories (keep original hardcoded ones)
        self.reset_to_hardcoded_weapons()
        
        # Reload custom configs
        self.load_custom_weapon_configs()
        
        # Repopulate All Weapons category
        self.populate_all_weapons()
        
        # Update UI
        self.category_combo.clear()
        self.category_combo.addItems(list(self.weapon_categories.keys()))
        
        # Try to restore previous selections
        category_index = self.category_combo.findText(current_category)
        if category_index >= 0:
            self.category_combo.setCurrentIndex(category_index)
            # This will trigger weapon dropdown update
            weapon_index = self.weapon_combo.findText(current_weapon)
            if weapon_index >= 0:
                self.weapon_combo.setCurrentIndex(weapon_index)
        
        print("Reloaded custom weapon configurations")
        QMessageBox.information(self, "Configs Reloaded", "Custom weapon configurations have been reloaded.")
    
    def reset_to_hardcoded_weapons(self):
        """Reset weapon categories to original hardcoded values"""
        self.weapon_categories = {
            "All Weapons": [],
            "Melee": [("Knife", "knife")],
            "Pistols": [
                ("PTM", "pm"), ("UDP Compact", "udp"), ("APSB", "apb"), 
                ("Rhino", "rhino00000"), ("Kora-1911", "kora")
            ],
            "Shotguns": [
                ("Boomstick", "obrez"), ("TOZ-34", "toz34"), ("M680 Cracker", "m86000"),
                ("SPSA-14", "spsa00"), ("Saiga D-12", "d1200"), ("RAM-2", "ram2")
            ],
            "Submachine Guns": [
                ("Viper-5", "vip"), ("AKM-74U", "aku"), ("M10 Gordon", "m1000"),
                ("Buket S-2", "bucket0"), ("ZUBR-19", "zubr0"), ("Integral-A", "integ")
            ],
            "Assault Rifles": [
                ("AK74", "ak74"), ("Fora-221", "fora0"), ("Dnipro", "dnipro"),
                ("GROM S-14", "grim0"), ("AS Lavina", "lav"), ("AR416", "m160"),
                ("GP37", "gp37"), ("Kharod", "kharod000"), ("Sotnyk", "sotnyk")
            ],
            "Sniper Rifles": [
                ("SVU MK S-3", "svu"), ("SVDM-2", "svm"), ("VS Vintar", "vintar"),
                ("M701 Super", "m701"), ("Mark 1 EMR", "mar"), ("Three-Line Rifle", "threeline"),
                ("Gauss Rifle", "gauss")
            ],
            "Machine Guns": [
                ("RPM-74", "pkp00000"), ("PKP", "mgp")
            ],
            "Launchers": [
                ("RPG7U", "rpg7")
            ],
            "Grenades": [
                ("F1 Grenade", "f1"), ("RGD5 Grenade", "rgd5"), ("Smoke Grenade", "smoke")
            ]
        }
        
        self.category_folders = {
            "Melee": "knifes",
            "Pistols": "pt",
            "Shotguns": "shg", 
            "Submachine Guns": "smg",
            "Assault Rifles": "ar",
            "Sniper Rifles": "sr",
            "Machine Guns": "mg",
            "Launchers": "gl",
            "Grenades": "grenades"
        }
    
    def load_animation(self):
        """Open popup to choose animation import type and proceed with selected option"""
        # Check if a weapon control curve is selected
        selection = cmds.ls(selection=True)
        if not selection:
            QMessageBox.warning(self, "Selection Required", "Please select a control curve on the weapon rig first.")
            return
        
        # Verify that the selection is part of a weapon rig
        selected_control = selection[0]
        if not selected_control.endswith("_ctrl") and not "_ctrl" in selected_control:
            QMessageBox.warning(self, "Invalid Selection", 
                              "Please select a control curve from the weapon rig (should end with '_ctrl').")
            return
            
        # Get corresponding joint name (remove "_ctrl" suffix)
        if selected_control.endswith("_ctrl"):
            joint_base_name = selected_control[:-5]  # Remove "_ctrl" suffix
        else:
            # Handle case where "_ctrl" might be in the middle of the name
            parts = selected_control.split("_ctrl")
            joint_base_name = parts[0]
        
        # Open file browser to select animation file - filter for FBX files only
        file_filter = "FBX Files (*.fbx)"
        result = QFileDialog.getOpenFileName(self, "Select Animation File", "", file_filter)
        
        if not result[0]:
            return  # User cancelled
            
        anim_file_path = result[0]
        
        # Show popup asking if weapon should be attached to character rig
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Animation Import Options")
        msg_box.setText("How do you want to import this animation?")
        standalone_btn = msg_box.addButton("Standalone Animation", QMessageBox.ActionRole)
        attach_btn = msg_box.addButton("Attach to Character Rig", QMessageBox.ActionRole)
        cancel_btn = msg_box.addButton(QMessageBox.Cancel)
        
        msg_box.exec_()
        
        if msg_box.clickedButton() == cancel_btn:
            return
        elif msg_box.clickedButton() == attach_btn:
            # Placeholder for character rig attachment
            QMessageBox.information(self, "Feature Coming Soon", 
                                 "Attaching to character rig feature will be implemented in a future update.")
            return
        
        # Proceed with standalone animation import
        self.do_import_standalone_animation(anim_file_path, selected_control, joint_base_name)
    
    def import_standalone_animation(self):
        """Legacy method - redirects to load_animation"""
        self.load_animation()
    
    def do_import_standalone_animation(self, anim_file_path, selected_control, joint_base_name):
        """
        Import standalone animation onto weapon control curves using the Animation Retargeting Tool
        
        Process:
        1. Import the animation file into WeaponImport namespace
        2. Open the Animation Retargeting Tool
        3. Create connections based on weapon retarget presets
        4. Bake the animation
        5. Apply weapon-specific adjustments (rotating S2_Controls)
        """
        try:
            # Import the animation file
            print("\n=== IMPORTING WEAPON ANIMATION ===")
            print("Animation file: {}".format(anim_file_path))
            print("Selected control: {}".format(selected_control))
            
            # Use a fixed namespace "WeaponImport" for all animation imports
            namespace = "WeaponImport"
            
            print("// STEP 1: Setting up WeaponImport namespace")
            
            # IMPORTANT: Create/setup the namespace BEFORE import
            try:
                # First check if the namespace exists
                if cmds.namespace(exists=namespace):
                    print(f"// Namespace '{namespace}' already exists")
                    
                    # Try to reset it by removing objects (if possible)
                    try:
                        # List objects in namespace to see what we're dealing with
                        namespace_objects = cmds.ls(f"{namespace}:*")
                        print(f"// Found {len(namespace_objects)} objects in namespace '{namespace}'")
                        
                        # Try to delete objects in the namespace first
                        for obj in namespace_objects:
                            try:
                                if cmds.objExists(obj) and not cmds.lockNode(obj, query=True)[0]:
                                    cmds.delete(obj)
                                    print(f"// Deleted: {obj}")
                            except Exception as e:
                                print(f"// Could not delete {obj}: {str(e)}")
                        
                        # Try to remove the now hopefully empty namespace
                        try:
                            cmds.namespace(removeNamespace=namespace, force=True)
                            print(f"// Successfully removed existing namespace '{namespace}'")
                            # Now recreate it fresh
                            cmds.namespace(add=namespace)
                            print(f"// Created fresh namespace '{namespace}'")
                        except Exception as e:
                            print(f"// Could not remove namespace: {str(e)}")
                            print(f"// Will use existing namespace '{namespace}' as is")
                    except Exception as e:
                        print(f"// Error managing existing namespace: {str(e)}")
                else:
                    # Create the namespace if it doesn't exist
                    print(f"// Creating new namespace '{namespace}'")
                    cmds.namespace(add=namespace)
                    print(f"// Successfully created namespace '{namespace}'")
            except Exception as e:
                print(f"// Error in namespace management: {str(e)}")
                
                # As a fallback, try using MEL commands to ensure namespace exists
                try:
                    print("// Attempting namespace creation via MEL as fallback")
                    mel.eval(f'namespace -exists "{namespace}";')
                    mel.eval(f'if (!`namespace -exists "{namespace}"`) {{ namespace -add "{namespace}"; }}')
                    print(f"// Namespace '{namespace}' ensured via MEL")
                except Exception as mel_error:
                    print(f"// MEL namespace fallback also failed: {str(mel_error)}")
                    # Continue anyway, as Maya will create the namespace during import if needed
            
            # Verify the namespace exists before proceeding
            if cmds.namespace(exists=namespace):
                print(f"// CONFIRMED: Namespace '{namespace}' exists and is ready for import")
            else:
                print(f"// WARNING: Namespace '{namespace}' could not be verified")
            
            # Set the current namespace to WeaponImport to match the screenshot
            # This is critical - ensures the namespace is selected as shown in the screenshot
            cmds.namespace(set=':')  # First go to root
            cmds.namespace(set=namespace)  # Then set to WeaponImport
            print(f"// Current namespace set to '{namespace}'")
            
            # Explicitly force "Use namespaces" option to be checked
            mel.eval('optionVar -iv "useNamespaces" 1;')
            
            print("// STEP 2: Getting pre-import state")
            # Get list of joints before import
            joints_before = set(cmds.ls(type='joint'))
            print(f"// Found {len(joints_before)} joints before import")
            
            print("// STEP 3: Importing file with namespace")
            # Import the file with the namespace - using exact settings from screenshot and animation importer settings
            # Settings: "Use namespaces" checked + "Merge into selected namespace and rename incoming objects that match"
            cmds.file(
                anim_file_path, 
                i=True,
                namespace=namespace,
                options="v=0",
                preserveReferences=True,
                mergeNamespacesOnClash=True,  # This enables "Merge into selected namespace"
                renameAll=True,               # This enables "rename incoming objects that match"
                importFrameRate=True,         # Framerate Import: Maintain Original
                importTimeRange="override"    # Animation Range: Override to Match Source
            )
            print(f"// Import completed with namespace '{namespace}'")
            
            # Set timeline to start at frame -1 after import is complete
            try:
                min_time = -1  # Always start at -1
                
                # Get current timeline settings that were imported from the file
                current_min = cmds.playbackOptions(query=True, min=True)
                current_max = cmds.playbackOptions(query=True, max=True)
                current_anim_start = cmds.playbackOptions(query=True, animationStartTime=True)
                current_anim_end = cmds.playbackOptions(query=True, animationEndTime=True)
                
                print(f"// Current timeline settings: min={current_min}, max={current_max}")
                print(f"// Current animation range: start={current_anim_start}, end={current_anim_end}")
                
                # Keep the end frame from the import but set start to -1
                cmds.playbackOptions(min=min_time, max=current_max)
                cmds.playbackOptions(animationStartTime=min_time, animationEndTime=current_anim_end)
                
                # Go to start frame
                cmds.currentTime(min_time)
                print(f"// Timeline adjusted: Start frame set to {min_time}, keeping end frame at {current_max}")
            except Exception as e:
                print(f"// Warning: Could not set timeline start frame: {str(e)}")
            
            # Get list of joints after import and find the new ones
            joints_after = set(cmds.ls(type='joint'))
            imported_joints = list(joints_after - joints_before)
            
            # Filter for joints in our namespace
            # Filter for joints in our namespace - handle both with and without colon
            imported_joints = [joint for joint in imported_joints if joint.startswith(namespace + ":") or joint.startswith(namespace)]
            
            # Print imported joint names for debugging
            print("// Imported joints:")
            for joint in imported_joints[:10]:  # Limit to first 10 to avoid spam
                print(f"//   - {joint}")
            if len(imported_joints) > 10:
                print(f"//   - ... and {len(imported_joints) - 10} more")
            
            if not imported_joints:
                QMessageBox.warning(self, "Import Failed", "No joints found in the imported animation file.")
                return
                
            print(f"Imported {len(imported_joints)} joints in namespace '{namespace}'")
            print("Imported {} joints".format(len(imported_joints)))
            
            # Switch back to root namespace
            print("// Switching back to root namespace")
            cmds.namespace(set=':')
            print("// Current namespace is now: root")
            
            # =========================================================================
            # STEP 4: Launch Animation Retargeting Tool for manual setup
            # =========================================================================
            print("\n// STEP 4: Launching Animation Retargeting Tool for manual setup")
            
            # Get weapon ID from the selected control to find the retarget preset
            weapon_id = self.get_weapon_id_from_control(selected_control)
            print(f"// Identified weapon: {weapon_id}")
            
            # Load retarget preset if available
            try:
                retarget_settings = self.load_weapon_retarget_preset(weapon_id)
            except Exception as e:
                print(f"// Error loading retargeting preset for {weapon_id}: {str(e)}")
                retarget_settings = self.get_default_retarget_settings(weapon_id)
            
            # Import the animation retargeting tool
            try:
                import importlib
                
                # Try to import animation retargeting tool
                # First find the local copy
                script_dir = os.path.dirname(os.path.abspath(__file__))
                anim_retarget_path = os.path.join(script_dir, "animation_retargeting_tool.py")
                
                if os.path.exists(anim_retarget_path):
                    # Load directly from file to ensure we have the updated version
                    print(f"// Found animation_retargeting_tool at: {anim_retarget_path}")
                    try:
                        # Use a simple module-like object with the necessary functions
                        animation_retargeting_tool = type('SimpleModule', (), {})()
                        
                        # Execute the script in a namespace and grab the functions we need
                        # Include all necessary imports for the script
                        module_namespace = {
                            '__file__': anim_retarget_path,
                            'os': os,
                            'sys': sys, 
                            'cmds': cmds,
                            'json': json
                        }
                        
                        # Add collections.OrderedDict
                        try:
                            from collections import OrderedDict
                            module_namespace['OrderedDict'] = OrderedDict
                        except ImportError:
                            pass
                            
                        # Add maya modules
                        try:
                            import maya.mel
                            module_namespace['maya'] = maya
                        except ImportError:
                            pass
                        
                        # Try to include PySide to avoid import errors
                        try:
                            import PySide2
                            module_namespace['PySide2'] = PySide2
                            from PySide2 import QtCore, QtGui, QtWidgets
                            module_namespace['QtCore'] = QtCore
                            module_namespace['QtGui'] = QtGui
                            module_namespace['QtWidgets'] = QtWidgets
                        except ImportError:
                            try:
                                import PySide6
                                module_namespace['PySide6'] = PySide6
                                from PySide6 import QtCore, QtGui, QtWidgets
                                module_namespace['QtCore'] = QtCore
                                module_namespace['QtGui'] = QtGui
                                module_namespace['QtWidgets'] = QtWidgets
                            except ImportError:
                                pass
                                
                        # Execute the script file
                        with open(anim_retarget_path, 'r') as f:
                            exec(f.read(), module_namespace)
                        
                        # Store the functions we need
                        animation_retargeting_tool.start = module_namespace['start']
                        print("// Successfully loaded start() function")
                    except Exception as e:
                        print(f"// Error loading from file: {str(e)}")
                        # Fall back to regular import
                        try:
                            import animation_retargeting_tool
                            importlib.reload(animation_retargeting_tool)
                        except ImportError:
                            # If not found in main path, try with stalker2_toolkit prefix
                            try:
                                from stalker2_toolkit import animation_retargeting_tool
                                importlib.reload(animation_retargeting_tool)
                            except ImportError:
                                QMessageBox.critical(self, "Error", "Could not import animation_retargeting_tool module.")
                                return
                else:
                    # If local file not found, try regular import
                    try:
                        import animation_retargeting_tool
                        importlib.reload(animation_retargeting_tool)
                    except ImportError:
                        # If not found in main path, try with stalker2_toolkit prefix
                        try:
                            from stalker2_toolkit import animation_retargeting_tool
                            importlib.reload(animation_retargeting_tool)
                        except ImportError:
                            QMessageBox.critical(self, "Error", "Could not import animation_retargeting_tool module.")
                            return
                
                print("// Successfully imported Animation Retargeting Tool")
                
                # Find available presets
                available_presets = []
                default_preset = None
                
                try:
                    # Make sure we have the master path
                    if not hasattr(self, 'master_path') or not self.master_path:
                        print("// Warning: Master path not set, using limited preset search")
                    
                    # 1. First look for weapon-specific preset
                    weapon_path = self.find_weapon_path_by_id(weapon_id)
                    if weapon_path and os.path.isdir(weapon_path):
                        weapon_preset = os.path.join(weapon_path, f"{weapon_id}_retarget.json")
                        if os.path.exists(weapon_preset):
                            available_presets.append((f"Weapon: {weapon_id}", weapon_preset))
                            default_preset = weapon_preset
                            print(f"// Found weapon-specific preset: {weapon_preset}")
                    
                    # 2. Look for weapon type presets in parent directory
                    if weapon_path and os.path.isdir(weapon_path):
                        parent_path = os.path.dirname(weapon_path)
                        if os.path.isdir(parent_path):
                            parent_name = os.path.basename(parent_path)
                            parent_presets = [os.path.join(parent_path, f) for f in os.listdir(parent_path) 
                                            if f.endswith("_retarget.json") and not f.startswith(weapon_id)]
                            for p in parent_presets:
                                preset_name = os.path.basename(p).replace("_retarget.json", "")
                                available_presets.append((f"Category: {preset_name}", p))
                                print(f"// Found category preset: {p}")
                    
                    # 3. Look in master path's Scripts directory for global presets
                    if hasattr(self, 'master_path') and self.master_path:
                        scripts_dir = os.path.join(self.master_path, "Scripts")
                        presets_dir = os.path.join(scripts_dir, "retarget_presets")
                        
                                                # Create presets directory if it doesn't exist
                        if not os.path.exists(presets_dir):
                            try:
                                os.makedirs(presets_dir)
                                print(f"// Created presets directory: {presets_dir}")
                            except Exception as e:
                                print(f"// Warning: Could not create presets directory: {str(e)}")
                                pass
        
                        # Look for global presets
                        if os.path.exists(presets_dir):
                            global_presets = [os.path.join(presets_dir, f) for f in os.listdir(presets_dir) 
                                            if f.endswith(".json")]
                            for p in global_presets:
                                preset_name = os.path.basename(p).replace(".json", "").replace("_retarget", "")
                                available_presets.append((f"Global: {preset_name}", p))
                                print(f"// Found global preset: {p}")
                    
                    # 4. Create default preset if none found
                    if not available_presets and weapon_path and os.path.isdir(weapon_path):
                        default_preset = os.path.join(weapon_path, f"{weapon_id}_retarget.json")
                        default_settings = self.get_default_retarget_settings(weapon_id)
                        with open(default_preset, 'w') as f:
                            json.dump(default_settings, f, indent=4)
                        available_presets.insert(0, (f"Default: {weapon_id}", default_preset))
                        print(f"// Created default preset: {default_preset}")
                    
                    # Always add "No Preset" option
                    available_presets.append(("No Preset", None))
                    
                except Exception as e:
                    print(f"// Error finding/creating presets: {str(e)}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import Animation Retargeting Tool: {str(e)}")
                print(f"// Error importing Animation Retargeting Tool: {str(e)}")
                return
            
            # Create pairs list for retargeting
            retarget_pairs = []
            
            # Find all control curves and matching imported joints
            all_controls = cmds.ls("*_ctrl", "*:*_ctrl")
            control_namespace = ""
            
            # Extract namespace from selected control
            control_parts = selected_control.split(':')
            if len(control_parts) > 1:
                control_namespace = ':'.join(control_parts[:-1]) + ':'
            
            # Find weapon controls with matching namespace
            weapon_controls = [ctrl for ctrl in all_controls if ctrl.startswith(control_namespace)]
            print(f"// Found {len(weapon_controls)} weapon controls with namespace: {control_namespace}")
            
            # Match each control to imported joint
            for control in weapon_controls:
                # Get base name without _ctrl
                if control.endswith("_ctrl"):
                    base_name = control[:-5]
            else:
                    base_name = control.split("_ctrl")[0]
                
                    # Get short name without namespace
                    base_short_name = base_name.split(':')[-1]
                    
                    # Expected joint name in the import namespace
                    expected_joint = f"{namespace}:{base_short_name}"
                    
                    if cmds.objExists(expected_joint):
                        retarget_pairs.append((expected_joint, control, base_short_name))
                        print(f"// Found match: {expected_joint} → {control}")
            
            if not retarget_pairs:
                QMessageBox.warning(self, "No Matches Found", "Could not find matching joints for any weapon controls.")
                return
                
            # Sort pairs based on hierarchy depth (top of hierarchy first)
            print("// Sorting pairs based on hierarchy depth (top to bottom)")
            
            # First get hierarchy information for each joint
            hierarchy_data = []
            for joint, control, joint_name in retarget_pairs:
                try:
                    # Calculate hierarchy depth (number of parents)
                    hierarchy_path = cmds.listRelatives(joint, fullPath=True, allParents=True) or []
                    depth = len(hierarchy_path)
                    
                    # Also get actual path for visualization
                    full_path = cmds.ls(joint, long=True)[0] if cmds.ls(joint, long=True) else joint
                    
                    # Store tuple of (joint, control, joint_name, depth, full_path)
                    hierarchy_data.append((joint, control, joint_name, depth, full_path))
                    
                    print(f"//   {joint} → depth {depth}, path: {full_path}")
                except Exception as e:
                    print(f"// Warning: Could not process hierarchy for {joint}: {str(e)}")
                    # If we can't get hierarchy, assume it's at depth 999 (will be processed last)
                    hierarchy_data.append((joint, control, joint_name, 999, joint))
            
            # Sort by depth (lower depth = higher in hierarchy = processed first)
            hierarchy_data.sort(key=lambda x: x[3])
            
            # Replace retarget_pairs with sorted version
            retarget_pairs = [(j, c, n) for j, c, n, _, _ in hierarchy_data]
            
            print("// Sorted retarget pairs (top to bottom):")
            for i, (joint, control, _) in enumerate(retarget_pairs):
                print(f"//   {i+1}. {joint} → {control}")
            
            # Use the built-in preset selection UI in animation_retargeting_tool
            print("// STEP 4: Launching Animation Retargeting Tool with integrated preset selector")
            print(f"// Identified weapon: {weapon_id}")
            
            # Get the weapon ID from the selected control (if not already known)
            if not weapon_id:
                weapon_id = self.get_weapon_id_from_control(selected_control)
                print(f"// Extracted weapon ID from control: {weapon_id}")
            
            # Launch the animation retargeting tool with our parameters
            # The tool's built-in preset selector will handle the preset selection
            try:
                print(f"// Calling animation_retargeting_tool.start with parameters: preset=None, namespace={namespace}, master_path={self.master_path}, weapon_id={weapon_id}")
                
                # Try direct call with positional arguments
                animation_retargeting_tool.start(None, namespace, self.master_path, weapon_id)
                print("// Successfully launched Animation Retargeting Tool")
            except Exception as e:
                print(f"// Error launching tool with parameters: {str(e)}")
                print("// Falling back to basic start() method")
                
                try:
                    # Most basic call - no parameters
                    animation_retargeting_tool.start()
                    print("// Tool launched without parameters - preset selection may not work")
                except Exception as inner_e:
                    print(f"// Critical error launching tool: {str(inner_e)}")
                    QMessageBox.critical(self, "Error", f"Failed to launch Animation Retargeting Tool: {str(inner_e)}")
            
            print("=== ANIMATION RETARGETING ===")
            print("The tool will:")
            print("1. Automatically create connections for ALL joints based on preset settings")
            print("2. Allow you to review and adjust connections if needed")
            print("3. Bake the animation when you click 'Bake Animation'")
            print("4. Execute post-bake operations defined in the preset (like rotating S2_Controls)")
            
            cmds.refresh()
            
            # Note: We no longer wait for the window - the connections are created automatically
            
            # Note: Post-bake operations like rotating S2_Controls are now handled
            # by the animation_retargeting_tool.py via the preset file
            
            # Success message
            QMessageBox.information(self, "Success", 
                                 "Animation imported successfully. Use the Animation Retargeting Tool to create connections.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error importing animation: {str(e)}")
            print(f"// Error importing animation: {str(e)}")
            import traceback
            traceback.print_exc()
            
    def get_weapon_id_from_control(self, control_name):
        """Extract weapon ID from a control name by analyzing namespace or parent structure"""
        try:
            # Try to get weapon ID from namespace first
            if ':' in control_name:
                namespace = control_name.split(':')[0]
                # Check if namespace matches a weapon ID pattern
                for category in self.weapon_categories:
                    for weapon_id in self.weapons_by_category[category]:
                        if weapon_id.lower() in namespace.lower():
                            return weapon_id
            
            # If that fails, try to find any parent group that has the weapon ID
            root_obj = cmds.listRelatives(control_name, parent=True, path=True)
            while root_obj:
                root_name = root_obj[0]
                # Check if name contains a weapon ID
                for category in self.weapon_categories:
                    for weapon_id in self.weapons_by_category[category]:
                        if weapon_id.lower() in root_name.lower():
                            return weapon_id
                            
                # Go up one level
                root_obj = cmds.listRelatives(root_name, parent=True, path=True)
                
            # If no match found, extract from the most likely weapon controls group
            controls_group = None
            if cmds.objExists("S2_Controls"):
                controls_group = "S2_Controls"
            elif cmds.objExists("*:S2_Controls"):
                controls_group_results = cmds.ls("*:S2_Controls")
                if controls_group_results:
                    controls_group = controls_group_results[0]
                    
            if controls_group:
                # Check if any weapon ID is in the control group's name
                for category in self.weapon_categories:
                    for weapon_id in self.weapons_by_category[category]:
                        if weapon_id.lower() in controls_group.lower():
                            return weapon_id
        except:
            pass
            
        # Default to "ak74" if we can't identify the weapon
        return "ak74"
        
    def load_weapon_retarget_preset(self, weapon_id):
        """
        Load weapon-specific retargeting settings from preset file
        
        The file can be either JSON or simple text format, and should be located in 
        the weapon's directory, named <weapon_id>_retarget.json or .txt
        """
        retarget_settings = {}
        
        try:
            # Find the weapon directory
            weapon_path = None
            
            # Try direct lookup in the category lists if available
            if hasattr(self, 'weapon_categories') and hasattr(self, 'category_folders'):
                for category in self.weapon_categories:
                    if category == "All Weapons" or category not in self.category_folders:
                        continue
                        
                    # Check if weapon is in this category
                    weapon_ids = [w[1] for w in self.weapon_categories[category]]
                    if weapon_id in weapon_ids:
                        category_folder = self.category_folders.get(category, "")
                        if category_folder:
                            weapon_path = os.path.join(self.master_path, "Source", "Weapons", category_folder, weapon_id)
                            break
            
            # If not found through direct lookup, search for it
            if not weapon_path:
                weapon_path = self.find_weapon_path_by_id(weapon_id)
            
            if not weapon_path or not os.path.isdir(weapon_path):
                print(f"// Warning: Could not find directory for weapon {weapon_id}")
                return self.get_default_retarget_settings(weapon_id)
            
            # Look for retarget preset files
            json_preset = os.path.join(weapon_path, f"{weapon_id}_retarget.json")
            txt_preset = os.path.join(weapon_path, f"{weapon_id}_retarget.txt")
            
            if os.path.exists(json_preset):
                # Parse JSON preset
                with open(json_preset, 'r') as f:
                    import json
                    retarget_settings = json.load(f)
                print(f"// Loaded retargeting preset from {json_preset}")
                
            elif os.path.exists(txt_preset):
                # Parse simple text preset
                with open(txt_preset, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):  # Skip empty lines and comments
                            parts = line.split(',')
                            if len(parts) >= 2:
                                joint_name = parts[0].strip()
                                settings = {}
                                
                                # Parse settings
                                for setting in parts[1:]:
                                    setting = setting.strip()
                                    if setting.startswith("align_position="):
                                        value = setting[len("align_position="):].lower()
                                        settings["align_position"] = (value == "true")
                                    elif setting.startswith("rotate="):
                                        rotate_str = setting[len("rotate="):]
                                        rotate_vals = [float(x) for x in rotate_str.strip('()').split()]
                                        if len(rotate_vals) == 3:
                                            settings["rotate"] = rotate_vals
                                
                                retarget_settings[joint_name] = settings
                                print(f"// Loaded retargeting preset from {txt_preset}")
            else:
                print(f"// No retargeting preset found for {weapon_id}, using defaults")
                return self.get_default_retarget_settings(weapon_id)
        except Exception as e:
            print(f"// Error loading retargeting preset for {weapon_id}: {str(e)}")
            return self.get_default_retarget_settings(weapon_id)
            
        return retarget_settings
    
    def get_default_retarget_settings(self, weapon_id):
        """Return default retargeting settings for a given weapon ID"""
        # Default settings with known special cases for specific weapons
        special_settings = {}
        
        # AK-74 specific settings
        if weapon_id == "ak74":
            special_settings = {
                "jnt_magazine1": {"align_position": True, "rotate": [0, 0, -90]},
                "jnt_shutter": {"align_position": False}
            }
        
        # Return the special settings - all other joints will use default values
        # (align_position=True, no rotation) which are applied in animation_retargeting_tool.py
        return special_settings
    
    # attach_to_character_rig functionality is now handled directly in the load_animation method
    
    def find_weapon_path_by_id(self, weapon_id):
        """Find the path to a weapon directory by its ID"""
        # Search all categories
        for category in self.weapon_categories:
            category_dir = os.path.join(self.master_path, category)
            if os.path.isdir(category_dir):
                # Check if weapon directory exists directly
                weapon_dir = os.path.join(category_dir, weapon_id)
                if os.path.isdir(weapon_dir):
                    return weapon_dir
                
                # If not, search subdirectories for a match
                for subdir in os.listdir(category_dir):
                    subdir_path = os.path.join(category_dir, subdir)
                    if os.path.isdir(subdir_path) and weapon_id.lower() in subdir.lower():
                        return subdir_path
        
        return None
    
    def refresh_all_data(self):
        """Refresh weapon data and reload configs"""
        # Reload configs first
        self.reload_custom_configs()
        
        # Then refresh current weapon data
        current_weapon = self.weapon_combo.currentText()
        self.on_weapon_changed(current_weapon)


def get_maya_main_window():
    """Get Maya main window as parent for dialog"""
    if pyside_version:
        main_window_ptr = omui.MQtUtil.mainWindow()
        return wrapInstance(int(main_window_ptr), QDialog)
    return None


def show_weapon_importer():
    """Show the Weapon Importer dialog"""
    if not pyside_version:
        cmds.error("PySide is not available. Please ensure Maya is running properly.")
        return
    
    parent = get_maya_main_window()
    dialog = WeaponImporterDialog(parent)
    dialog.show()


# For Maya drag-and-drop functionality
def onMayaDroppedPythonFile(*args, **kwargs):
    """Maya drag-and-drop entry point"""
    show_weapon_importer()


# Main execution
if __name__ == "__main__":
    show_weapon_importer() 