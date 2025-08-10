#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Weapon Rig Tool for STALKER 2 Toolkit
Compatible with Maya 2022+ (Python 3, PySide6) and Maya 2022- (Python 2, PySide2)

This script creates control curves for rigged weapons by analyzing joint-mesh constraints
and generating intuitive control rigs for animation.
"""

import os
import sys
import json
import math

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
                                   QFileDialog, QMessageBox, QSplitter, QWidget, QScrollArea, QFrame, QCheckBox,
                                   QSpinBox, QDoubleSpinBox, QGroupBox, QRadioButton, QButtonGroup, QTabWidget)
    from PySide6.QtCore import Qt, QSize
    from PySide6.QtGui import QPixmap, QFont
    from shiboken6 import wrapInstance
    pyside_version = 6
except ImportError:
    try:
        # Maya 2022 and earlier (PySide2)
        from PySide2.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QLabel, QPushButton, 
                                       QLineEdit, QComboBox, QListWidget, QListWidgetItem, QTextEdit, 
                                       QFileDialog, QMessageBox, QSplitter, QWidget, QScrollArea, QFrame, QCheckBox,
                                       QSpinBox, QDoubleSpinBox, QGroupBox, QRadioButton, QButtonGroup, QTabWidget)
        from PySide2.QtCore import Qt, QSize
        from PySide2.QtGui import QPixmap, QFont
        from shiboken2 import wrapInstance
        pyside_version = 2
    except ImportError:
        print("Error: Could not import PySide. Please ensure Maya is running.")
        pyside_version = None

if pyside_version:
    import maya.OpenMayaUI as omui


class JointControlAssociation:
    """Class to store information about a joint-control association"""
    def __init__(self, joint_name, mesh_objects, control_name=None):
        self.joint_name = joint_name
        self.mesh_objects = mesh_objects if isinstance(mesh_objects, list) else [mesh_objects]
        self.control_name = control_name
        self.has_control = control_name is not None
        self.bounding_box = None
        self.suggested_shape = "sphere"
        self.control_shape = "Custom"  # Per-joint control shape: Custom, box, cylinder, sphere
        self.control_scale = 1.0  # Per-joint scale multiplier
        self.control_color = "red"  # Per-joint control color
        self.is_excluded = False  # Whether this joint is excluded from rigging
        
        # Per-joint curve offset settings
        self.curve_offset_x = 0.0
        self.curve_offset_y = 0.0
        self.curve_offset_z = 0.0
        self.curve_rotation_x = 0.0
        self.curve_rotation_y = 0.0
        self.curve_rotation_z = 0.0
        
    def calculate_bounding_box(self):
        """Calculate combined bounding box of all mesh objects"""
        if not self.mesh_objects:
            return None
            
        all_bbox_points = []
        
        for mesh_obj in self.mesh_objects:
            if cmds.objExists(mesh_obj):
                try:
                    bbox = cmds.exactWorldBoundingBox(mesh_obj)
                    if bbox and len(bbox) >= 6:
                        # Add all 8 corners of the bounding box
                        all_bbox_points.extend([
                            [bbox[0], bbox[1], bbox[2]],  # min corner
                            [bbox[3], bbox[4], bbox[5]],  # max corner
                            [bbox[0], bbox[1], bbox[5]],
                            [bbox[0], bbox[4], bbox[2]],
                            [bbox[0], bbox[4], bbox[5]],
                            [bbox[3], bbox[1], bbox[2]],
                            [bbox[3], bbox[1], bbox[5]],
                            [bbox[3], bbox[4], bbox[2]]
                        ])
                except:
                    print("Warning: Could not get bounding box for {0}".format(mesh_obj))
        
        if not all_bbox_points:
            return None
            
        # Calculate overall bounding box
        min_x = min(p[0] for p in all_bbox_points)
        max_x = max(p[0] for p in all_bbox_points)
        min_y = min(p[1] for p in all_bbox_points)
        max_y = max(p[1] for p in all_bbox_points)
        min_z = min(p[2] for p in all_bbox_points)
        max_z = max(p[2] for p in all_bbox_points)
        
        self.bounding_box = [min_x, min_y, min_z, max_x, max_y, max_z]
        
        # Calculate control scale based on bounding box size
        width = max_x - min_x
        height = max_y - min_y
        depth = max_z - min_z
        
        # Use the largest dimension for scale, with minimum and maximum limits
        max_dimension = max(width, height, depth)
        self.control_scale = max(0.5, min(5.0, max_dimension * 1.2))
        
        # Suggest control shape based on mesh dimensions
        if height > width * 1.5 and height > depth * 1.5:
            self.suggested_shape = "cylinder"  # Tall objects
        elif width > height * 2 or depth > height * 2:
            self.suggested_shape = "cube"      # Wide/long objects
        else:
            self.suggested_shape = "sphere"    # General purpose
            
        return self.bounding_box


class WeaponRigToolDialog(QDialog):
    def __init__(self, parent=None):
        super(WeaponRigToolDialog, self).__init__(parent)
        self.setWindowTitle("Weapon Rig Tool - STALKER 2 Toolkit")
        self.setMinimumSize(900, 700)
        self.resize(1200, 800)
        
        # Data
        self.joint_associations = []  # List of JointControlAssociation objects
        self.rig_group = None
        self.excluded_joints = set()  # Set of joint names to exclude from rigging
        
        # Weapon detection and caching
        self.current_weapon_id = None
        self.current_weapon_path = None
        self.curve_settings_cache = {}
        
        # Attachment detection
        self.attachments_by_joint = {}  # {joint_name: [attachment_objects]}
        self.attachment_names_by_joint = {}  # {joint_name: [attachment_names]}
        self.attachment_categories_by_joint = {}  # {joint_name: [attachment_categories]}
        
        # Load master path from weapon importer settings
        self.master_path = ""
        self.load_weapon_importer_settings()
        
        self.setup_ui()
        self.setup_dark_style()
        self.analyze_scene()
    
    def load_weapon_importer_settings(self):
        """Load master path from weapon importer settings"""
        try:
            settings_file = os.path.join(cmds.internalVar(userAppDir=True), "STALKER2_weapon_importer_settings.json")
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    self.master_path = settings.get('master_path', '')
                    if self.master_path:
                        print("Loaded master path from weapon importer: {0}".format(self.master_path))
                    else:
                        print("No master path found in weapon importer settings")
            else:
                print("No weapon importer settings found")
                self.master_path = ""
        except Exception as e:
            print("Warning: Could not load weapon importer settings: {0}".format(str(e)))
            self.master_path = ""
    
    def refresh_all(self):
        """Refresh master path settings and re-analyze scene"""
        print("Refreshing weapon rig tool data...")
        self.load_weapon_importer_settings()
        self.analyze_scene()
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("STALKER 2 Weapon Rig Tool")
        title_label.setProperty("class", "title-label")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Create tab widget for different modes
        self.tab_widget = QTabWidget()
        
        # Analysis Tab
        analysis_tab = QWidget()
        self.setup_analysis_tab(analysis_tab)
        self.tab_widget.addTab(analysis_tab, "Scene Analysis")
        
        # Control Creation Tab
        control_tab = QWidget()
        self.setup_control_tab(control_tab)
        self.tab_widget.addTab(control_tab, "Control Creation")
        
        # Rig Management Tab
        rig_tab = QWidget()
        self.setup_rig_tab(rig_tab)
        self.tab_widget.addTab(rig_tab, "Rig Management")
        
        main_layout.addWidget(self.tab_widget)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh Analysis")
        refresh_btn.setProperty("class", "secondary-button")
        refresh_btn.clicked.connect(self.refresh_all)
        button_layout.addWidget(refresh_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setProperty("class", "secondary-button")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        main_layout.addLayout(button_layout)
    
    def setup_analysis_tab(self, tab_widget):
        """Setup the scene analysis tab"""
        layout = QVBoxLayout(tab_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Scene info section
        info_frame = QFrame()
        info_frame.setProperty("class", "section-frame")
        info_layout = QVBoxLayout(info_frame)
        
        info_header = QLabel("Scene Analysis")
        info_header.setProperty("class", "section-header")
        info_layout.addWidget(info_header)
        
        self.scene_info_label = QLabel("Click 'Refresh Analysis' to analyze the current scene")
        self.scene_info_label.setProperty("class", "info-label")
        self.scene_info_label.setWordWrap(True)
        info_layout.addWidget(self.scene_info_label)
        
        layout.addWidget(info_frame)
        
        # Joint-mesh associations section
        assoc_frame = QFrame()
        assoc_frame.setProperty("class", "section-frame")
        assoc_layout = QVBoxLayout(assoc_frame)
        
        assoc_header = QLabel("Joint-Mesh Associations")
        assoc_header.setProperty("class", "section-header")
        assoc_layout.addWidget(assoc_header)
        
        # Scroll area for associations
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(300)
        
        self.associations_widget = QWidget()
        self.associations_layout = QVBoxLayout(self.associations_widget)
        self.associations_layout.setSpacing(5)
        self.associations_layout.setContentsMargins(5, 5, 5, 5)
        
        scroll_area.setWidget(self.associations_widget)
        assoc_layout.addWidget(scroll_area)
        
        layout.addWidget(assoc_frame)
        
        # Joint exclusion section
        exclusion_frame = QFrame()
        exclusion_frame.setProperty("class", "section-frame")
        exclusion_layout = QVBoxLayout(exclusion_frame)
        
        exclusion_header = QLabel("Joint Exclusion Controls")
        exclusion_header.setProperty("class", "section-header")
        exclusion_layout.addWidget(exclusion_header)
        
        # Exclusion buttons
        exclusion_button_layout = QHBoxLayout()
        
        self.exclude_selected_btn = QPushButton("Exclude Selected Joints")
        self.exclude_selected_btn.setProperty("class", "secondary-button")
        self.exclude_selected_btn.clicked.connect(self.exclude_selected_joints)
        self.exclude_selected_btn.setToolTip("Exclude the currently selected joints from rig creation")
        exclusion_button_layout.addWidget(self.exclude_selected_btn)
        
        self.include_selected_btn = QPushButton("Include Selected Joints")
        self.include_selected_btn.setProperty("class", "secondary-button")
        self.include_selected_btn.clicked.connect(self.include_selected_joints)
        self.include_selected_btn.setToolTip("Include the currently selected joints back into rig creation")
        exclusion_button_layout.addWidget(self.include_selected_btn)
        
        self.clear_exclusions_btn = QPushButton("Clear All Exclusions")
        self.clear_exclusions_btn.setProperty("class", "secondary-button")
        self.clear_exclusions_btn.clicked.connect(self.clear_all_exclusions)
        self.clear_exclusions_btn.setToolTip("Include all joints back into rig creation")
        exclusion_button_layout.addWidget(self.clear_exclusions_btn)
        
        exclusion_layout.addLayout(exclusion_button_layout)
        
        # Exclusion status label
        self.exclusion_status_label = QLabel("No joints excluded")
        self.exclusion_status_label.setProperty("class", "info-label")
        self.exclusion_status_label.setWordWrap(True)
        exclusion_layout.addWidget(self.exclusion_status_label)
        
        layout.addWidget(exclusion_frame)
    
    def setup_control_tab(self, tab_widget):
        """Setup the control creation tab"""
        layout = QVBoxLayout(tab_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Control options section
        options_frame = QFrame()
        options_frame.setProperty("class", "section-frame")
        options_layout = QVBoxLayout(options_frame)
        
        options_header = QLabel("Control Creation Options")
        options_header.setProperty("class", "section-header")
        options_layout.addWidget(options_header)
        
        # Note: Control shape and scale are now set per-joint in the per-joint controls section
        
        # Smoothness options
        smoothness_layout = QHBoxLayout()
        smoothness_layout.addWidget(QLabel("Curve Smoothness:"))
        
        self.smoothness_spin = QSpinBox()
        self.smoothness_spin.setRange(8, 40)
        self.smoothness_spin.setValue(20)
        self.smoothness_spin.setSingleStep(2)
        self.smoothness_spin.setToolTip("Number of control points for smooth curves (more = smoother but heavier)\nAffects both preview curves and final control curves")
        self.smoothness_spin.valueChanged.connect(self.on_smoothness_changed)
        smoothness_layout.addWidget(self.smoothness_spin)
        
        smoothness_layout.addStretch()
        options_layout.addLayout(smoothness_layout)
        
        # Naming options
        naming_layout = QHBoxLayout()
        naming_layout.addWidget(QLabel("Control Suffix:"))
        
        self.suffix_edit = QLineEdit("_ctrl")
        self.suffix_edit.setToolTip("Suffix to add to control names (e.g., 'jnt_trigger' becomes 'jnt_trigger_ctrl')")
        naming_layout.addWidget(self.suffix_edit)
        
        naming_layout.addStretch()
        options_layout.addLayout(naming_layout)
        
        # Curve positioning options
        positioning_group = QGroupBox("Curve Positioning")
        positioning_layout = QVBoxLayout(positioning_group)
        
        # Info about automatic alignment
        info_layout = QHBoxLayout()
        info_label = QLabel("✓ Automatic smart alignment based on mesh geometry")
        info_label.setProperty("class", "info-text")
        info_label.setToolTip("Curves automatically align to mesh orientation using intelligent geometry analysis")
        info_layout.addWidget(info_label)
        info_layout.addStretch()
        positioning_layout.addLayout(info_layout)
        
        # Global curve offset (applies to all joints)
        global_offset_layout = QHBoxLayout()
        global_offset_layout.addWidget(QLabel("Global Curve Offset:"))
        
        self.offset_x_spin = QDoubleSpinBox()
        self.offset_x_spin.setRange(-10.0, 10.0)
        self.offset_x_spin.setValue(0.0)
        self.offset_x_spin.setSingleStep(0.1)
        self.offset_x_spin.setDecimals(2)
        self.offset_x_spin.setToolTip("Global offset for all curve points in X direction")
        global_offset_layout.addWidget(QLabel("X:"))
        global_offset_layout.addWidget(self.offset_x_spin)
        
        self.offset_y_spin = QDoubleSpinBox()
        self.offset_y_spin.setRange(-10.0, 10.0)
        self.offset_y_spin.setValue(0.0)
        self.offset_y_spin.setSingleStep(0.1)
        self.offset_y_spin.setDecimals(2)
        self.offset_y_spin.setToolTip("Global offset for all curve points in Y direction")
        global_offset_layout.addWidget(QLabel("Y:"))
        global_offset_layout.addWidget(self.offset_y_spin)
        
        self.offset_z_spin = QDoubleSpinBox()
        self.offset_z_spin.setRange(-10.0, 10.0)
        self.offset_z_spin.setValue(0.0)
        self.offset_z_spin.setSingleStep(0.1)
        self.offset_z_spin.setDecimals(2)
        self.offset_z_spin.setToolTip("Global offset for all curve points in Z direction")
        global_offset_layout.addWidget(QLabel("Z:"))
        global_offset_layout.addWidget(self.offset_z_spin)
        
        global_offset_layout.addStretch()
        positioning_layout.addLayout(global_offset_layout)
        
        # Per-joint curve adjustment note
        per_joint_info = QLabel("Note: Per-joint position and rotation offsets can be set in the Scene Analysis tab")
        per_joint_info.setProperty("class", "info-text")
        per_joint_info.setWordWrap(True)
        positioning_layout.addWidget(per_joint_info)
        
        options_layout.addWidget(positioning_group)
        
        layout.addWidget(options_frame)
        
        # Cache management section
        cache_frame = QFrame()
        cache_frame.setProperty("class", "section-frame")
        cache_layout = QVBoxLayout(cache_frame)
        
        cache_header = QLabel("Curve Settings Cache")
        cache_header.setProperty("class", "section-header")
        cache_layout.addWidget(cache_header)
        
        cache_info_layout = QHBoxLayout()
        self.cache_status_label = QLabel("Auto-save enabled")
        self.cache_status_label.setProperty("class", "info-label")
        cache_info_layout.addWidget(self.cache_status_label)
        
        save_settings_btn = QPushButton("Save Settings Now")
        save_settings_btn.setProperty("class", "secondary-button")
        save_settings_btn.clicked.connect(self.save_weapon_curve_settings)
        save_settings_btn.setToolTip("Manually save current curve settings for this weapon")
        cache_info_layout.addWidget(save_settings_btn)
        
        cleanup_previews_btn = QPushButton("Clean Up Previews")
        cleanup_previews_btn.setProperty("class", "secondary-button")
        cleanup_previews_btn.clicked.connect(self.cleanup_all_preview_curves)
        cleanup_previews_btn.setToolTip("Delete all preview curves from the scene")
        cache_info_layout.addWidget(cleanup_previews_btn)
        
        update_previews_btn = QPushButton("Update Previews")
        update_previews_btn.setProperty("class", "secondary-button")
        update_previews_btn.clicked.connect(self.update_existing_preview_curves)
        update_previews_btn.setToolTip("Regenerate existing preview curves with current smoothness settings")
        cache_info_layout.addWidget(update_previews_btn)
        
        cache_info_layout.addStretch()
        cache_layout.addLayout(cache_info_layout)
        
        layout.addWidget(cache_frame)
        
        # Action buttons
        action_frame = QFrame()
        action_frame.setProperty("class", "section-frame")
        action_layout = QVBoxLayout(action_frame)
        
        action_header = QLabel("Control Creation Actions")
        action_header.setProperty("class", "section-header")
        action_layout.addWidget(action_header)
        
        button_layout = QVBoxLayout()
        
        # Single control creation
        single_layout = QHBoxLayout()
        
        self.create_selected_btn = QPushButton("Create Controls for Selected Joints")
        self.create_selected_btn.setProperty("class", "primary-button")
        self.create_selected_btn.clicked.connect(self.create_controls_for_selected)
        self.create_selected_btn.setEnabled(False)
        single_layout.addWidget(self.create_selected_btn)
        
        self.create_all_btn = QPushButton("Create All Controls")
        self.create_all_btn.setProperty("class", "create-all-button")
        self.create_all_btn.clicked.connect(self.create_all_controls)
        self.create_all_btn.setEnabled(False)
        single_layout.addWidget(self.create_all_btn)
        
        button_layout.addLayout(single_layout)
        
        # Complete rig creation
        complete_layout = QHBoxLayout()
        
        self.create_complete_rig_btn = QPushButton("Create Complete Weapon Rig")
        self.create_complete_rig_btn.setProperty("class", "complete-rig-button")
        self.create_complete_rig_btn.clicked.connect(self.create_complete_rig)
        self.create_complete_rig_btn.setEnabled(False)
        complete_layout.addWidget(self.create_complete_rig_btn)
        
        button_layout.addLayout(complete_layout)
        
        action_layout.addLayout(button_layout)
        layout.addWidget(action_frame)
        
        # Progress info
        self.progress_label = QLabel("Analyze scene to see available options")
        self.progress_label.setProperty("class", "info-label")
        self.progress_label.setWordWrap(True)
        layout.addWidget(self.progress_label)
    
    def setup_rig_tab(self, tab_widget):
        """Setup the rig management tab"""
        layout = QVBoxLayout(tab_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Existing rigs section
        existing_frame = QFrame()
        existing_frame.setProperty("class", "section-frame")
        existing_layout = QVBoxLayout(existing_frame)
        
        existing_header = QLabel("Existing Weapon Rigs")
        existing_header.setProperty("class", "section-header")
        existing_layout.addWidget(existing_header)
        
        self.existing_rigs_list = QListWidget()
        self.existing_rigs_list.setMinimumHeight(200)
        existing_layout.addWidget(self.existing_rigs_list)
        
        # Rig management buttons
        rig_button_layout = QHBoxLayout()
        
        self.select_rig_btn = QPushButton("Select Rig")
        self.select_rig_btn.setProperty("class", "secondary-button")
        self.select_rig_btn.clicked.connect(self.select_rig)
        self.select_rig_btn.setEnabled(False)
        rig_button_layout.addWidget(self.select_rig_btn)
        
        self.delete_rig_btn = QPushButton("Delete Rig")
        self.delete_rig_btn.setProperty("class", "warning-button")
        self.delete_rig_btn.clicked.connect(self.delete_rig)
        self.delete_rig_btn.setEnabled(False)
        rig_button_layout.addWidget(self.delete_rig_btn)
        
        rig_button_layout.addStretch()
        existing_layout.addLayout(rig_button_layout)
        
        layout.addWidget(existing_frame)
        
        # Connect list selection
        self.existing_rigs_list.itemSelectionChanged.connect(self.on_rig_selection_changed)
        
        # Rig info section
        info_frame = QFrame()
        info_frame.setProperty("class", "section-frame")
        info_layout = QVBoxLayout(info_frame)
        
        info_header = QLabel("Rig Information")
        info_header.setProperty("class", "section-header")
        info_layout.addWidget(info_header)
        
        self.rig_info_label = QLabel("Select a rig to see information")
        self.rig_info_label.setProperty("class", "info-label")
        self.rig_info_label.setWordWrap(True)
        info_layout.addWidget(self.rig_info_label)
        
        layout.addWidget(info_frame)
        
        layout.addStretch()
    
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
        QPushButton:disabled {
            background-color: #2a2a2a;
            color: #666666;
            border: 1px solid #333333;
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
        .create-all-button {
            background-color: #228B22;
            color: #ffffff;
            border: 1px solid #32CD32;
            padding: 10px 20px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }
        .create-all-button:hover {
            background-color: #32CD32;
        }
        .create-all-button:pressed {
            background-color: #006400;
        }
        .complete-rig-button {
            background-color: #8A2BE2;
            color: #ffffff;
            border: 1px solid #9370DB;
            padding: 12px 24px;
            border-radius: 4px;
            font-size: 13px;
            font-weight: bold;
        }
        .complete-rig-button:hover {
            background-color: #9370DB;
        }
        .complete-rig-button:pressed {
            background-color: #6A0DAD;
        }
        .warning-button {
            background-color: #dc3545;
            color: #ffffff;
            border: 1px solid #c82333;
            padding: 8px 16px;
            border-radius: 4px;
        }
        .warning-button:hover {
            background-color: #c82333;
        }
        .warning-button:pressed {
            background-color: #a71e2a;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox {
            background-color: #404040;
            color: #ffffff;
            border: 1px solid #555555;
            padding: 6px;
            border-radius: 3px;
            font-size: 11px;
        }
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border: 1px solid #0078d4;
        }
        QTabWidget::pane {
            border: 1px solid #444444;
            background-color: #222222;
        }
        QTabWidget::tab-bar {
            alignment: left;
        }
        QTabBar::tab {
            background-color: #333333;
            color: #cccccc;
            border: 1px solid #555555;
            padding: 8px 16px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background-color: #0078d4;
            color: #ffffff;
        }
        QTabBar::tab:hover {
            background-color: #555555;
        }
        QListWidget {
            background-color: #404040;
            border: 1px solid #555555;
            selection-background-color: #0078d4;
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
        QGroupBox {
            color: #ffffff;
            border: 1px solid #555555;
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px 0 4px;
            color: #cccccc;
            font-weight: bold;
        }
        QRadioButton {
            color: #ffffff;
            font-size: 11px;
            padding: 4px;
        }
        QRadioButton::indicator {
            width: 16px;
            height: 16px;
            border: 2px solid #555555;
            border-radius: 9px;
            background-color: #404040;
        }
        QRadioButton::indicator:checked {
            background-color: #0078d4;
            border: 2px solid #106ebe;
        }
        QRadioButton::indicator:hover {
            border: 2px solid #777777;
        }
        .joint-association {
            background-color: #333333;
            border: 1px solid #444444;
            border-radius: 3px;
            padding: 8px;
            margin: 2px 0px;
        }
        .joint-name {
            color: #ffffff;
            font-size: 12px;
            font-weight: bold;
        }
        .mesh-info {
            color: #cccccc;
            font-size: 10px;
            margin-left: 10px;
            margin-top: 2px;
        }
        .control-info {
            color: #90EE90;
            font-size: 10px;
            margin-left: 10px;
            margin-top: 2px;
        }
        .no-control {
            color: #888888;
            font-size: 10px;
            font-style: italic;
            margin-left: 10px;
            margin-top: 2px;
        }
        .excluded-joint {
            color: #ff6b6b;
            font-size: 10px;
            font-weight: bold;
            margin-left: 10px;
            margin-top: 2px;
        }
        .info-text {
            color: #66ff66;
            font-size: 11px;
            font-style: italic;
            padding: 2px 4px;
        }
        .curve-adjustment-frame {
            background-color: #2a2a2a;
            border: 1px solid #555555;
            border-radius: 3px;
            margin: 3px 0px;
        }
        .toggle-button {
            background-color: #404040;
            color: #cccccc;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 4px 8px;
            font-size: 10px;
            text-align: left;
        }
        .toggle-button:hover {
            background-color: #505050;
        }
        .toggle-button:checked {
            background-color: #0078d4;
            color: #ffffff;
        }
        .reset-button {
            background-color: #666666;
            color: #ffffff;
            border: 1px solid #777777;
            border-radius: 3px;
            padding: 3px 6px;
            font-size: 9px;
        }
        .reset-button:hover {
            background-color: #777777;
        }
        .preview-button {
            background-color: #228B22;
            color: #ffffff;
            border: 1px solid #32CD32;
            border-radius: 3px;
            padding: 3px 6px;
            font-size: 9px;
        }
        .preview-button:hover {
            background-color: #32CD32;
        }
        """
        self.setStyleSheet(dark_style)
    
    def analyze_scene(self):
        """Analyze the current scene for joint-mesh associations"""
        print("\n=== ANALYZING SCENE FOR WEAPON RIG ===")
        
        self.joint_associations = []
        
        # Detect current weapon and load cached settings
        self.detect_current_weapon()
        self.load_weapon_curve_settings()
        
        # Find all joints with constraints
        all_joints = cmds.ls(type='joint')
        joints_with_meshes = {}
        
        print("Found {0} joints in scene".format(len(all_joints)))
        
        # Look for parent and scale constraints
        all_constraints = cmds.ls(type=['parentConstraint', 'scaleConstraint'])
        
        for constraint in all_constraints:
            try:
                constraint_type = cmds.objectType(constraint)
                
                # Get constraint information using proper Maya constraint queries
                if constraint_type == 'parentConstraint':
                    # Get the drivers (source objects) and constrained object
                    target_list = cmds.parentConstraint(constraint, query=True, targetList=True) or []
                    weight_alias_list = cmds.parentConstraint(constraint, query=True, weightAliasList=True) or []
                    
                elif constraint_type == 'scaleConstraint':
                    # Get the drivers (source objects) and constrained object  
                    target_list = cmds.scaleConstraint(constraint, query=True, targetList=True) or []
                    weight_alias_list = cmds.scaleConstraint(constraint, query=True, weightAliasList=True) or []
                else:
                    continue
                
                # Get the constrained object by finding what the constraint is connected to
                constrained_object = None
                
                # Check constraint connections to find the driven object
                all_connections = cmds.listConnections(constraint, source=False, destination=True) or []
                for conn in all_connections:
                    if cmds.objectType(conn) == 'transform' and conn not in target_list:
                        constrained_object = conn
                        break
                
                if not constrained_object:
                    # Alternative approach: check constraint node name for clues
                    constraint_parts = constraint.split('_')
                    if len(constraint_parts) > 1:
                        potential_name = '_'.join(constraint_parts[:-1])  # Remove constraint suffix
                        if cmds.objExists(potential_name):
                            constrained_object = potential_name
                
                if not constrained_object or not target_list:
                    continue
                
                # Find joints in the target (driver) objects
                joints_in_constraint = [obj for obj in target_list if cmds.objectType(obj) == 'joint']
                
                if joints_in_constraint:
                    print("Found constraint: {0} -> {1} driven by joints: {2}".format(
                        constraint, constrained_object, ', '.join(joints_in_constraint)))
                    
                    # Associate joints with the constrained mesh
                    for joint in joints_in_constraint:
                        if joint not in joints_with_meshes:
                            joints_with_meshes[joint] = []
                        if constrained_object not in joints_with_meshes[joint]:
                            joints_with_meshes[joint].append(constrained_object)
                        
            except Exception as e:
                print("Warning: Error analyzing constraint {0}: {1}".format(constraint, str(e)))
        
        # Create associations
        for joint_name, mesh_objects in joints_with_meshes.items():
            if mesh_objects:  # Only include joints that have associated meshes
                # Remove duplicates
                unique_meshes = list(set(mesh_objects))
                
                # Check if control already exists
                control_name = self.find_existing_control(joint_name)
                
                association = JointControlAssociation(joint_name, unique_meshes, control_name)
                association.calculate_bounding_box()
                
                # Apply cached curve settings if available
                self.apply_cached_curve_settings(association)
                
                self.joint_associations.append(association)
                
                print("Joint '{0}' associated with meshes: {1}".format(
                    joint_name, ', '.join(unique_meshes)))
                if control_name:
                    print("  -> Existing control found: {0}".format(control_name))
        
        # Update exclusion status for existing associations
        self.update_association_exclusions()
        
        # Detect attachments
        self.detect_attachments()
        
        # Update UI
        self.update_scene_info()
        self.update_associations_display()
        self.update_button_states()
        self.update_existing_rigs_list()
        self.update_exclusion_status()
        self.update_cache_status()
        
        print("Analysis complete: found {0} joint-mesh associations".format(len(self.joint_associations)))
    
    def detect_attachments(self):
        """Detect attachments in the S2_Attachments group"""
        print("\n=== DETECTING ATTACHMENTS ===")
        
        self.attachments_by_joint.clear()
        self.attachment_names_by_joint.clear()
        self.attachment_categories_by_joint.clear()
        
        # Look for S2_Attachments group
        attachments_group = None
        s2_groups = cmds.ls("S2_Attachments", type='transform')
        
        if s2_groups:
            attachments_group = s2_groups[0]
            print("Found S2_Attachments group: {0}".format(attachments_group))
        else:
            print("No S2_Attachments group found in scene")
            return
        
        # Get all transforms under the attachments group
        attachment_transforms = cmds.listRelatives(attachments_group, children=True, type='transform') or []
        
        if not attachment_transforms:
            print("No attachment objects found in S2_Attachments group")
            return
        
        print("Found {0} attachment objects".format(len(attachment_transforms)))
        
        # For each attachment, find which joint it's constrained to
        for attachment_obj in attachment_transforms:
            try:
                # Find constraints on this attachment object
                parent_constraints = cmds.listConnections(attachment_obj, type='parentConstraint') or []
                scale_constraints = cmds.listConnections(attachment_obj, type='scaleConstraint') or []
                constraints = parent_constraints + scale_constraints
                
                joint_name = None
                for constraint in constraints:
                    try:
                        constraint_type = cmds.objectType(constraint)
                        
                        # Get constraint drivers
                        if constraint_type == 'parentConstraint':
                            target_list = cmds.parentConstraint(constraint, query=True, targetList=True) or []
                        elif constraint_type == 'scaleConstraint':
                            target_list = cmds.scaleConstraint(constraint, query=True, targetList=True) or []
                        else:
                            continue
                        
                        # Find joint in target list
                        for target in target_list:
                            if cmds.objectType(target) == 'joint' and target.startswith('jnt_'):
                                joint_name = target
                                break
                        
                        if joint_name:
                            break
                    except:
                        continue
                
                if joint_name:
                    # Get the category and display name from the custom attributes
                    category = "Uncategorized"  # Default category
                    display_name = attachment_obj  # Default to object name
                    
                    try:
                        if cmds.attributeQuery('S2_AttachmentCategory', node=attachment_obj, exists=True):
                            category = cmds.getAttr(attachment_obj + '.S2_AttachmentCategory') or "Uncategorized"
                    except:
                        pass  # Use default if attribute can't be read
                    
                    try:
                        if cmds.attributeQuery('S2_AttachmentName', node=attachment_obj, exists=True):
                            display_name = cmds.getAttr(attachment_obj + '.S2_AttachmentName') or attachment_obj
                    except:
                        pass  # Use default if attribute can't be read
                    
                    # Add attachment to the joint's lists
                    if joint_name not in self.attachments_by_joint:
                        self.attachments_by_joint[joint_name] = []
                        self.attachment_names_by_joint[joint_name] = []
                        self.attachment_categories_by_joint[joint_name] = []
                    
                    self.attachments_by_joint[joint_name].append(attachment_obj)
                    self.attachment_names_by_joint[joint_name].append(display_name)
                    self.attachment_categories_by_joint[joint_name].append(category)
                    
                    print("  Attachment '{0}' -> Category: '{1}', Name: '{2}' -> Joint '{3}'".format(
                        attachment_obj, category, display_name, joint_name))
                else:
                    print("  Warning: Could not find constraining joint for attachment '{0}'".format(attachment_obj))
                    
            except Exception as e:
                print("  Error analyzing attachment '{0}': {1}".format(attachment_obj, str(e)))
        
        # Summary
        total_attachments = sum(len(attachments) for attachments in self.attachments_by_joint.values())
        print("Attachment detection complete: found {0} attachments across {1} joints".format(
            total_attachments, len(self.attachments_by_joint)))
        
        for joint_name, attachments in self.attachments_by_joint.items():
            print("  Joint '{0}': {1} attachment(s)".format(joint_name, len(attachments)))
    
    def detect_current_weapon(self):
        """Detect the current weapon based on imported skeleton and metadata"""
        try:
            # Look for weapon identifier node (created by weapon importer)
            weapon_nodes = cmds.ls("S2_WeaponInfo_*", type='locator') or []
            
            if weapon_nodes:
                # Get the first weapon info node
                weapon_info_node = weapon_nodes[0]
                weapon_id = weapon_info_node.replace("S2_WeaponInfo_", "")
                
                # Get weapon path from custom attributes if available
                weapon_path = None
                if cmds.attributeQuery('weaponPath', node=weapon_info_node, exists=True):
                    weapon_path = cmds.getAttr(weapon_info_node + '.weaponPath')
                
                self.current_weapon_id = weapon_id
                self.current_weapon_path = weapon_path
                
                print("Detected weapon: {0}".format(weapon_id))
                if weapon_path:
                    print("Weapon path: {0}".format(weapon_path))
                
                return True
            
            # Fallback: try to detect from skeleton naming and mesh naming
            all_joints = cmds.ls(type='joint')
            all_meshes = cmds.ls(type='mesh')
            
            # Look for weapon identifier in joint names
            if all_joints:
                for joint in all_joints:
                    # Check for weapon skeleton prefixes (e.g., AK74_, M16_, etc.)
                    joint_parts = joint.split('_')
                    if len(joint_parts) > 1:
                        potential_weapon_id = joint_parts[0]
                        
                        # Validate if this looks like a weapon name
                        if len(potential_weapon_id) > 2 and potential_weapon_id.upper() == potential_weapon_id:
                            # This might be a weapon identifier
                            self.current_weapon_id = potential_weapon_id
                            print("Detected weapon from skeleton naming: {0}".format(potential_weapon_id))
                            
                            # Try to guess weapon path based on project structure
                            self.guess_weapon_path_from_id(potential_weapon_id)
                            return True
            
            # Look for weapon identifier in mesh names (e.g., SM_wpn_ak74_*, SM_ak_*)
            if all_meshes:
                for mesh in all_meshes:
                    mesh_transform = cmds.listRelatives(mesh, parent=True, type='transform')
                    if mesh_transform:
                        mesh_name = mesh_transform[0]
                        
                        # Check for patterns like SM_wpn_ak74_*, SM_ak_*, etc.
                        if 'ak74' in mesh_name.lower():
                            self.current_weapon_id = 'AK74'
                            print("Detected weapon from mesh naming: AK74 (found: {0})".format(mesh_name))
                            self.guess_weapon_path_from_id('AK74')
                            return True
                        elif 'ak_' in mesh_name.lower():
                            self.current_weapon_id = 'AK74'
                            print("Detected weapon from mesh naming: AK74 (found: {0})".format(mesh_name))
                            self.guess_weapon_path_from_id('AK74')
                            return True
                        
                        # Add more weapon patterns as needed
                        weapon_patterns = {
                            'm16': 'M16',
                            'm4': 'M4',
                            'glock': 'GLOCK',
                            'ar15': 'AR15'
                        }
                        
                        for pattern, weapon_id in weapon_patterns.items():
                            if pattern in mesh_name.lower():
                                self.current_weapon_id = weapon_id
                                print("Detected weapon from mesh naming: {0} (found: {1})".format(weapon_id, mesh_name))
                                self.guess_weapon_path_from_id(weapon_id)
                                return True
            
            # No weapon detected
            self.current_weapon_id = None
            self.current_weapon_path = None
            print("No weapon detected in scene")
            return False
            
        except Exception as e:
            print("Error detecting weapon: {0}".format(str(e)))
            return False
    
    def guess_weapon_path_from_id(self, weapon_id):
        """Try to guess weapon path based on weapon ID using the same mappings as weapon importer"""
        try:
            # Use master path from weapon importer settings
            if not self.master_path:
                print("No master path available - please configure master path in Weapon Importer first")
                return
            
            # Use the exact same weapon database as the weapon importer
            weapon_categories = {
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
            
            # Category to folder mapping (same as weapon importer)
            category_folders = {
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
            
            # Find which category this weapon belongs to
            found_category = None
            found_weapon_id = None
            
            weapon_id_lower = weapon_id.lower()
            
            for category_name, weapons in weapon_categories.items():
                for weapon_name, weapon_folder_id in weapons:
                    # Check both exact match and case-insensitive match
                    if (weapon_folder_id.lower() == weapon_id_lower or 
                        weapon_folder_id == weapon_id or
                        weapon_name.lower().replace(' ', '').replace('-', '') == weapon_id_lower):
                        found_category = category_name
                        found_weapon_id = weapon_folder_id
                        break
                if found_category:
                    break
            
            if found_category and found_category in category_folders:
                category_folder = category_folders[found_category]
                weapon_path = os.path.join(self.master_path, "Source", "Weapons", category_folder, found_weapon_id)
                
                print("Found weapon '{0}' in category '{1}' (folder: {2})".format(
                    weapon_id, found_category, category_folder))
                print("Checking weapon path: {0}".format(weapon_path))
                
                if os.path.exists(weapon_path):
                    self.current_weapon_path = weapon_path
                    print("Confirmed weapon path exists: {0}".format(weapon_path))
                    return
                else:
                    # Path doesn't exist, but we know where it should be
                    self.current_weapon_path = weapon_path
                    print("Weapon path determined (but doesn't exist): {0}".format(weapon_path))
                    print("You may need to import the weapon first using the Weapon Importer")
                    return
            else:
                print("Could not determine weapon path for: {0}".format(weapon_id))
                print("Available weapon IDs: {0}".format([wid for cat_weapons in weapon_categories.values() for name, wid in cat_weapons]))
            
        except Exception as e:
            print("Error guessing weapon path: {0}".format(str(e)))
    
    def load_weapon_curve_settings(self):
        """Load cached curve settings for the current weapon"""
        if not self.current_weapon_id:
            print("No weapon detected, skipping curve settings load")
            return
        
        try:
            # Determine settings file path
            settings_file = None
            
            if self.current_weapon_path and os.path.exists(self.current_weapon_path):
                # Use weapon-specific folder
                settings_file = os.path.join(self.current_weapon_path, "curve_settings.json")
            elif self.master_path:
                # Use master path cache directory if available
                cache_dir = os.path.join(self.master_path, "Scripts", "weapon_cache")
                if not os.path.exists(cache_dir):
                    try:
                        os.makedirs(cache_dir)
                    except:
                        pass
                settings_file = os.path.join(cache_dir, "{0}_curve_settings.json".format(self.current_weapon_id))
            else:
                # Fallback to script directory
                script_dir = os.path.dirname(__file__)
                cache_dir = os.path.join(script_dir, "weapon_cache")
                if not os.path.exists(cache_dir):
                    os.makedirs(cache_dir)
                settings_file = os.path.join(cache_dir, "{0}_curve_settings.json".format(self.current_weapon_id))
            
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    self.curve_settings_cache = json.load(f)
                print("Loaded curve settings for weapon: {0}".format(self.current_weapon_id))
                print("Settings file: {0}".format(settings_file))
            else:
                print("No cached curve settings found for weapon: {0}".format(self.current_weapon_id))
                self.curve_settings_cache = {}
                
        except Exception as e:
            print("Error loading weapon curve settings: {0}".format(str(e)))
            self.curve_settings_cache = {}
    
    def save_weapon_curve_settings(self):
        """Save current curve settings for the current weapon"""
        if not self.current_weapon_id:
            print("No weapon detected, skipping curve settings save")
            return
        
        try:
            # Collect current settings from all associations
            settings = {}
            for association in self.joint_associations:
                joint_name = association.joint_name
                settings[joint_name] = {
                    'curve_offset_x': association.curve_offset_x,
                    'curve_offset_y': association.curve_offset_y,
                    'curve_offset_z': association.curve_offset_z,
                    'curve_rotation_x': association.curve_rotation_x,
                    'curve_rotation_y': association.curve_rotation_y,
                    'curve_rotation_z': association.curve_rotation_z,
                    'control_shape': getattr(association, 'control_shape', 'Custom'),
                    'control_scale': getattr(association, 'control_scale', 1.0),
                    'control_color': getattr(association, 'control_color', 'red')
                }
            
            # Determine settings file path
            settings_file = None
            
            if self.current_weapon_path and os.path.exists(self.current_weapon_path):
                # Use weapon-specific folder
                settings_file = os.path.join(self.current_weapon_path, "curve_settings.json")
            elif self.master_path:
                # Use master path cache directory if available
                cache_dir = os.path.join(self.master_path, "Scripts", "weapon_cache")
                if not os.path.exists(cache_dir):
                    try:
                        os.makedirs(cache_dir)
                    except:
                        pass
                settings_file = os.path.join(cache_dir, "{0}_curve_settings.json".format(self.current_weapon_id))
            else:
                # Fallback to script directory
                script_dir = os.path.dirname(__file__)
                cache_dir = os.path.join(script_dir, "weapon_cache")
                if not os.path.exists(cache_dir):
                    os.makedirs(cache_dir)
                settings_file = os.path.join(cache_dir, "{0}_curve_settings.json".format(self.current_weapon_id))
            
            # Save settings
            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
            
            print("Saved curve settings for weapon: {0}".format(self.current_weapon_id))
            print("Settings file: {0}".format(settings_file))
            
        except Exception as e:
            print("Error saving weapon curve settings: {0}".format(str(e)))
    
    def apply_cached_curve_settings(self, association):
        """Apply cached curve settings to an association if available"""
        if not self.curve_settings_cache:
            return
        
        joint_name = association.joint_name
        if joint_name in self.curve_settings_cache:
            cached_settings = self.curve_settings_cache[joint_name]
            
            association.curve_offset_x = cached_settings.get('curve_offset_x', 0.0)
            association.curve_offset_y = cached_settings.get('curve_offset_y', 0.0)
            association.curve_offset_z = cached_settings.get('curve_offset_z', 0.0)
            association.curve_rotation_x = cached_settings.get('curve_rotation_x', 0.0)
            association.curve_rotation_y = cached_settings.get('curve_rotation_y', 0.0)
            association.curve_rotation_z = cached_settings.get('curve_rotation_z', 0.0)
            association.control_shape = cached_settings.get('control_shape', 'Custom')
            association.control_scale = cached_settings.get('control_scale', 1.0)
            association.control_color = cached_settings.get('control_color', 'red')
            
            print("Applied cached settings for joint: {0}".format(joint_name))
    
    def exclude_selected_joints(self):
        """Exclude the currently selected joints from rig creation"""
        selected_objects = cmds.ls(selection=True, type='joint') or []
        
        if not selected_objects:
            QMessageBox.information(self, "No Joints Selected", 
                "Please select one or more joints to exclude from rig creation.")
            return
        
        excluded_count = 0
        for joint in selected_objects:
            if joint not in self.excluded_joints:
                self.excluded_joints.add(joint)
                excluded_count += 1
                print("Excluded joint: {0}".format(joint))
        
        if excluded_count > 0:
            # Update association exclusion status
            self.update_association_exclusions()
            self.update_associations_display()
            self.update_button_states()
            self.update_exclusion_status()
            
            QMessageBox.information(self, "Joints Excluded", 
                "Excluded {0} joint(s) from rig creation.".format(excluded_count))
        else:
            QMessageBox.information(self, "Already Excluded", 
                "All selected joints were already excluded.")
    
    def include_selected_joints(self):
        """Include the currently selected joints back into rig creation"""
        selected_objects = cmds.ls(selection=True, type='joint') or []
        
        if not selected_objects:
            QMessageBox.information(self, "No Joints Selected", 
                "Please select one or more joints to include back into rig creation.")
            return
        
        included_count = 0
        for joint in selected_objects:
            if joint in self.excluded_joints:
                self.excluded_joints.remove(joint)
                included_count += 1
                print("Included joint: {0}".format(joint))
        
        if included_count > 0:
            # Update association exclusion status
            self.update_association_exclusions()
            self.update_associations_display()
            self.update_button_states()
            self.update_exclusion_status()
            
            QMessageBox.information(self, "Joints Included", 
                "Included {0} joint(s) back into rig creation.".format(included_count))
        else:
            QMessageBox.information(self, "Not Excluded", 
                "None of the selected joints were excluded.")
    
    def clear_all_exclusions(self):
        """Clear all joint exclusions"""
        if not self.excluded_joints:
            QMessageBox.information(self, "No Exclusions", "No joints are currently excluded.")
            return
        
        reply = QMessageBox.question(self, "Clear All Exclusions", 
            "Are you sure you want to include all excluded joints back into rig creation?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        
        if reply == QMessageBox.Yes:
            excluded_count = len(self.excluded_joints)
            self.excluded_joints.clear()
            
            # Update association exclusion status
            self.update_association_exclusions()
            self.update_associations_display()
            self.update_button_states()
            self.update_exclusion_status()
            
            QMessageBox.information(self, "Exclusions Cleared", 
                "Included {0} joint(s) back into rig creation.".format(excluded_count))
    
    def update_association_exclusions(self):
        """Update the exclusion status of all associations"""
        for association in self.joint_associations:
            association.is_excluded = association.joint_name in self.excluded_joints
    
    def update_exclusion_status(self):
        """Update the exclusion status label"""
        if not self.excluded_joints:
            self.exclusion_status_label.setText("No joints excluded")
        else:
            excluded_list = sorted(list(self.excluded_joints))
            if len(excluded_list) <= 5:
                status_text = "Excluded joints: {0}".format(", ".join(excluded_list))
            else:
                status_text = "Excluded joints: {0} ... and {1} more".format(
                    ", ".join(excluded_list[:5]), len(excluded_list) - 5)
            
            self.exclusion_status_label.setText(status_text)
    
    def update_cache_status(self):
        """Update the cache status label"""
        if not hasattr(self, 'cache_status_label'):
            return
        
        if self.current_weapon_id:
            if self.curve_settings_cache:
                cached_count = len(self.curve_settings_cache)
                status_text = "Auto-save enabled • {0} cached joint(s) for {1}".format(cached_count, self.current_weapon_id)
            else:
                status_text = "Auto-save enabled • No cached settings for {0}".format(self.current_weapon_id)
        else:
            status_text = "No weapon detected • Cache disabled"
        
        self.cache_status_label.setText(status_text)
    
    def find_existing_control(self, joint_name):
        """Check if a control already exists for this joint"""
        # Common control naming patterns
        possible_names = [
            joint_name + "_ctrl",
            joint_name + "_control",
            joint_name + "Ctrl",
            joint_name + "Control",
            "ctrl_" + joint_name,
            "control_" + joint_name
        ]
        
        for name in possible_names:
            if cmds.objExists(name):
                return name
        
        return None
    
    def update_scene_info(self):
        """Update the scene information display"""
        total_joints = len(cmds.ls(type='joint'))
        constrained_joints = len(self.joint_associations)
        existing_controls = len([assoc for assoc in self.joint_associations if assoc.has_control])
        excluded_joints = len([assoc for assoc in self.joint_associations if assoc.is_excluded])
        available_joints = constrained_joints - excluded_joints
        joints_needing_controls = len([assoc for assoc in self.joint_associations 
                                     if not assoc.has_control and not assoc.is_excluded])
        
        info_text = "Scene Analysis Results:\n\n"
        
        # Master path info
        if self.master_path:
            info_text += "Master Path: {0}\n".format(self.master_path)
        else:
            info_text += "Master Path: Not configured (use Weapon Importer to set)\n"
        info_text += "\n"
        
        # Weapon detection info
        if self.current_weapon_id:
            info_text += "Detected Weapon: {0}\n".format(self.current_weapon_id)
            if self.current_weapon_path:
                info_text += "Weapon Path: {0}\n".format(self.current_weapon_path)
            
            # Cache status
            if self.curve_settings_cache:
                cached_joints = len(self.curve_settings_cache)
                info_text += "Cached Settings: {0} joint(s)\n".format(cached_joints)
            else:
                info_text += "Cached Settings: None\n"
            info_text += "\n"
        else:
            info_text += "Weapon Detection: None detected\n\n"
        
        info_text += "Total joints in scene: {0}\n".format(total_joints)
        info_text += "Joints with constrained meshes: {0}\n".format(constrained_joints)
        info_text += "Joints with existing controls: {0}\n".format(existing_controls)
        info_text += "Excluded joints: {0}\n".format(excluded_joints)
        info_text += "Available joints: {0}\n".format(available_joints)
        info_text += "Joints needing controls: {0}".format(joints_needing_controls)
        
        if constrained_joints == 0:
            info_text += "\n\nNo joint-mesh constraints found in the scene."
            info_text += "\nMake sure you have imported a weapon using the Weapon Importer first."
        elif excluded_joints == constrained_joints:
            info_text += "\n\nAll joints are excluded from rig creation."
            info_text += "\nUse the Joint Exclusion Controls to include joints."
        
        self.scene_info_label.setText(info_text)
    
    def update_associations_display(self):
        """Update the associations display"""
        # Clear existing widgets
        while self.associations_layout.count():
            child = self.associations_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not self.joint_associations:
            no_assoc_label = QLabel("No joint-mesh associations found.\n\nImport a weapon using the Weapon Importer to see associations here.")
            no_assoc_label.setProperty("class", "info-label")
            no_assoc_label.setAlignment(Qt.AlignCenter)
            self.associations_layout.addWidget(no_assoc_label)
            return
        
        # Create widgets for each association
        for association in self.joint_associations:
            assoc_widget = QFrame()
            assoc_widget.setProperty("class", "joint-association")
            assoc_layout = QVBoxLayout(assoc_widget)
            assoc_layout.setContentsMargins(8, 8, 8, 8)
            assoc_layout.setSpacing(4)
            
            # Joint name
            joint_label = QLabel(association.joint_name)
            joint_label.setProperty("class", "joint-name")
            assoc_layout.addWidget(joint_label)
            
            # Mesh objects
            mesh_text = "Meshes: {0}".format(", ".join(association.mesh_objects))
            mesh_label = QLabel(mesh_text)
            mesh_label.setProperty("class", "mesh-info")
            mesh_label.setWordWrap(True)
            assoc_layout.addWidget(mesh_label)
            
            # Shape suggestion
            if association.bounding_box:
                shape_text = "Suggested shape: {0} (scale: {1:.1f})".format(
                    association.suggested_shape, association.control_scale)
                shape_label = QLabel(shape_text)
                shape_label.setProperty("class", "mesh-info")
                assoc_layout.addWidget(shape_label)
            
            # Control status
            if association.is_excluded:
                control_text = "✖ EXCLUDED - will not create control"
                control_label = QLabel(control_text)
                control_label.setProperty("class", "excluded-joint")
            elif association.has_control:
                control_text = "✓ Control exists: {0}".format(association.control_name)
                control_label = QLabel(control_text)
                control_label.setProperty("class", "control-info")
            else:
                control_text = "○ No control - ready to create"
                control_label = QLabel(control_text)
                control_label.setProperty("class", "no-control")
            
            assoc_layout.addWidget(control_label)
            
            # Add per-joint curve offset controls (only if not excluded)
            if not association.is_excluded:
                self.add_per_joint_offset_controls(assoc_layout, association)
            
            self.associations_layout.addWidget(assoc_widget)
        
        # Add stretch at the end
        self.associations_layout.addStretch()
    
    def add_per_joint_offset_controls(self, layout, association):
        """Add per-joint curve offset and rotation controls"""
        try:
            # Create collapsible section for curve adjustments
            adjustment_frame = QFrame()
            adjustment_frame.setProperty("class", "curve-adjustment-frame")
            adjustment_layout = QVBoxLayout(adjustment_frame)
            adjustment_layout.setContentsMargins(10, 5, 10, 5)
            adjustment_layout.setSpacing(3)
            
            # Toggle button for showing/hiding controls
            toggle_btn = QPushButton("v Curve Adjustments")
            toggle_btn.setProperty("class", "toggle-button")
            toggle_btn.setCheckable(True)
            toggle_btn.setChecked(False)
            
            # Controls container (initially hidden)
            controls_container = QWidget()
            controls_layout = QVBoxLayout(controls_container)
            controls_layout.setContentsMargins(0, 5, 0, 0)
            controls_layout.setSpacing(5)
            
            # Position offset controls
            pos_layout = QHBoxLayout()
            pos_layout.addWidget(QLabel("Position:"))
            
            # X offset
            pos_x_spin = QDoubleSpinBox()
            pos_x_spin.setRange(-999.0, 999.0)
            pos_x_spin.setValue(association.curve_offset_x)
            pos_x_spin.setSingleStep(0.1)
            pos_x_spin.setDecimals(2)
            pos_x_spin.setFixedWidth(60)
            pos_x_spin.setToolTip("X position offset for this joint's curve points")
            pos_layout.addWidget(QLabel("X:"))
            pos_layout.addWidget(pos_x_spin)
            
            # Y offset
            pos_y_spin = QDoubleSpinBox()
            pos_y_spin.setRange(-999.0, 999.0)
            pos_y_spin.setValue(association.curve_offset_y)
            pos_y_spin.setSingleStep(0.1)
            pos_y_spin.setDecimals(2)
            pos_y_spin.setFixedWidth(60)
            pos_y_spin.setToolTip("Y position offset for this joint's curve points")
            pos_layout.addWidget(QLabel("Y:"))
            pos_layout.addWidget(pos_y_spin)
            
            # Z offset
            pos_z_spin = QDoubleSpinBox()
            pos_z_spin.setRange(-999.0, 999.0)
            pos_z_spin.setValue(association.curve_offset_z)
            pos_z_spin.setSingleStep(0.1)
            pos_z_spin.setDecimals(2)
            pos_z_spin.setFixedWidth(60)
            pos_z_spin.setToolTip("Z position offset for this joint's curve points")
            pos_layout.addWidget(QLabel("Z:"))
            pos_layout.addWidget(pos_z_spin)
            
            pos_layout.addStretch()
            controls_layout.addLayout(pos_layout)
            
            # Rotation controls
            rot_layout = QHBoxLayout()
            rot_layout.addWidget(QLabel("Rotation:"))
            
            # X rotation
            rot_x_spin = QDoubleSpinBox()
            rot_x_spin.setRange(-180.0, 180.0)
            rot_x_spin.setValue(association.curve_rotation_x)
            rot_x_spin.setSingleStep(5.0)
            rot_x_spin.setDecimals(1)
            rot_x_spin.setFixedWidth(60)
            rot_x_spin.setToolTip("X rotation for this joint's curve points (degrees)")
            rot_layout.addWidget(QLabel("X:"))
            rot_layout.addWidget(rot_x_spin)
            
            # Y rotation
            rot_y_spin = QDoubleSpinBox()
            rot_y_spin.setRange(-180.0, 180.0)
            rot_y_spin.setValue(association.curve_rotation_y)
            rot_y_spin.setSingleStep(5.0)
            rot_y_spin.setDecimals(1)
            rot_y_spin.setFixedWidth(60)
            rot_y_spin.setToolTip("Y rotation for this joint's curve points (degrees)")
            rot_layout.addWidget(QLabel("Y:"))
            rot_layout.addWidget(rot_y_spin)
            
            # Z rotation
            rot_z_spin = QDoubleSpinBox()
            rot_z_spin.setRange(-180.0, 180.0)
            rot_z_spin.setValue(association.curve_rotation_z)
            rot_z_spin.setSingleStep(5.0)
            rot_z_spin.setDecimals(1)
            rot_z_spin.setFixedWidth(60)
            rot_z_spin.setToolTip("Z rotation for this joint's curve points (degrees)")
            rot_layout.addWidget(QLabel("Z:"))
            rot_layout.addWidget(rot_z_spin)
            
            rot_layout.addStretch()
            controls_layout.addLayout(rot_layout)
            
            # Control shape selection
            shape_layout = QHBoxLayout()
            shape_layout.addWidget(QLabel("Shape:"))
            
            shape_combo = QComboBox()
            shape_combo.addItems(["Custom", "box", "cylinder", "sphere"])
            shape_combo.setCurrentText(association.control_shape)
            shape_combo.setFixedWidth(80)
            shape_combo.setToolTip("Control shape type for this joint\nCustom = auto-generated from mesh geometry")
            shape_layout.addWidget(shape_combo)
            
            shape_layout.addStretch()
            controls_layout.addLayout(shape_layout)
            
            # Scale multiplier
            scale_layout = QHBoxLayout()
            scale_layout.addWidget(QLabel("Scale:"))
            
            scale_spin = QDoubleSpinBox()
            scale_spin.setRange(0.1, 10.0)
            scale_spin.setValue(association.control_scale)
            scale_spin.setSingleStep(0.1)
            scale_spin.setDecimals(1)
            scale_spin.setFixedWidth(60)
            scale_spin.setToolTip("Scale multiplier for this joint's control")
            scale_layout.addWidget(scale_spin)
            
            scale_layout.addStretch()
            controls_layout.addLayout(scale_layout)
            
            # Control color selection
            color_layout = QHBoxLayout()
            color_layout.addWidget(QLabel("Color:"))
            
            color_combo = QComboBox()
            color_combo.addItems(["red", "yellow", "blue", "green", "purple", "light blue", "orange", "pink", "light green", "white"])
            color_combo.setCurrentText(association.control_color)
            color_combo.setFixedWidth(90)
            color_combo.setToolTip("Control color for this joint")
            color_layout.addWidget(color_combo)
            
            color_layout.addStretch()
            controls_layout.addLayout(color_layout)
            
            # Action buttons
            action_layout = QHBoxLayout()
            
            preview_btn = QPushButton("Preview")
            preview_btn.setProperty("class", "preview-button")
            preview_btn.setFixedWidth(60)
            preview_btn.setToolTip("Create a preview of the curve with current settings")
            action_layout.addWidget(preview_btn)
            
            reset_btn = QPushButton("Reset")
            reset_btn.setProperty("class", "reset-button")
            reset_btn.setFixedWidth(60)
            reset_btn.setToolTip("Reset all curve adjustments for this joint")
            action_layout.addWidget(reset_btn)
            
            action_layout.addStretch()
            controls_layout.addLayout(action_layout)
            
            # Initially hide controls
            controls_container.setVisible(False)
            
            # Connect toggle button
            def toggle_controls():
                visible = not controls_container.isVisible()
                controls_container.setVisible(visible)
                toggle_btn.setText("^ Curve Adjustments" if visible else "v Curve Adjustments")
            
            toggle_btn.clicked.connect(toggle_controls)
            
            # Connect value change signals to update association and auto-save
            def update_pos_x(value):
                association.curve_offset_x = value
                self.save_weapon_curve_settings()
                self.update_preview_for_joint(association)
            def update_pos_y(value):
                association.curve_offset_y = value
                self.save_weapon_curve_settings()
                self.update_preview_for_joint(association)
            def update_pos_z(value):
                association.curve_offset_z = value
                self.save_weapon_curve_settings()
                self.update_preview_for_joint(association)
            def update_rot_x(value):
                association.curve_rotation_x = value
                self.save_weapon_curve_settings()
                self.update_preview_for_joint(association)
            def update_rot_y(value):
                association.curve_rotation_y = value
                self.save_weapon_curve_settings()
                self.update_preview_for_joint(association)
            def update_rot_z(value):
                association.curve_rotation_z = value
                self.save_weapon_curve_settings()
                self.update_preview_for_joint(association)
            def update_shape(text):
                association.control_shape = text
                self.save_weapon_curve_settings()
                self.update_preview_for_joint(association)
            def update_scale(value):
                association.control_scale = value
                self.save_weapon_curve_settings()
                self.update_preview_for_joint(association)
            def update_color(text):
                association.control_color = text
                self.save_weapon_curve_settings()
                self.update_preview_for_joint(association)
            def reset_values():
                association.curve_offset_x = 0.0
                association.curve_offset_y = 0.0
                association.curve_offset_z = 0.0
                association.curve_rotation_x = 0.0
                association.curve_rotation_y = 0.0
                association.curve_rotation_z = 0.0
                association.control_shape = "Custom"
                association.control_scale = 1.0
                association.control_color = "red"
                pos_x_spin.setValue(0.0)
                pos_y_spin.setValue(0.0)
                pos_z_spin.setValue(0.0)
                rot_x_spin.setValue(0.0)
                rot_y_spin.setValue(0.0)
                rot_z_spin.setValue(0.0)
                shape_combo.setCurrentText("Custom")
                scale_spin.setValue(1.0)
                color_combo.setCurrentText("red")
                self.save_weapon_curve_settings()
                self.update_preview_for_joint(association)
            
            def preview_curve():
                self.create_preview_curve_for_joint(association)
            
            pos_x_spin.valueChanged.connect(update_pos_x)
            pos_y_spin.valueChanged.connect(update_pos_y)
            pos_z_spin.valueChanged.connect(update_pos_z)
            rot_x_spin.valueChanged.connect(update_rot_x)
            rot_y_spin.valueChanged.connect(update_rot_y)
            rot_z_spin.valueChanged.connect(update_rot_z)
            shape_combo.currentTextChanged.connect(update_shape)
            scale_spin.valueChanged.connect(update_scale)
            color_combo.currentTextChanged.connect(update_color)
            reset_btn.clicked.connect(reset_values)
            preview_btn.clicked.connect(preview_curve)
            
            # Add to layout
            adjustment_layout.addWidget(toggle_btn)
            adjustment_layout.addWidget(controls_container)
            layout.addWidget(adjustment_frame)
            
        except Exception as e:
            print("Error adding per-joint offset controls: {0}".format(str(e)))
    
    def create_preview_curve_for_joint(self, association):
        """Create a preview curve for a specific joint with current settings"""
        try:
            # Clean up any existing preview curves for this joint
            self.cleanup_preview_curves(association.joint_name)
            
            # Create preview curve name
            preview_name = "PREVIEW_{0}_curve".format(association.joint_name)
            
            print("Creating preview curve for joint: {0}".format(association.joint_name))
            
            # Check control shape to determine creation method
            shape_type = getattr(association, 'control_shape', 'Custom')
            scale = getattr(association, 'control_scale', 1.0)
            
            if shape_type == "Custom":
                # Get current smoothness setting for feedback
                current_smoothness = self.smoothness_spin.value() if hasattr(self, 'smoothness_spin') else 20
                print("Using smoothness setting: {0} points".format(current_smoothness))
                
                # Use the mesh-fitting method for custom shapes
                preview_curve = self.create_unified_curve(preview_name, association, is_preview=True)
            else:
                # Create basic geometric shape (mesh-aware sizing)
                print("Creating mesh-fitted {0} preview shape".format(shape_type))
                preview_curve = self.create_basic_control_shape(preview_name, shape_type, scale, association)
                
                # Position the preview at the mesh center (like custom shapes)
                if preview_curve and cmds.objExists(preview_curve):
                    # Calculate mesh center for basic shapes to match custom shape behavior
                    mesh_center = self.calculate_mesh_center_for_association(association)
                    cmds.xform(preview_curve, worldSpace=True, translation=mesh_center)
                    
                    # Set pivot and orientation to match joint for proper constraint behavior (same as final controls)
                    if cmds.objExists(association.joint_name):
                        joint_pos = cmds.xform(association.joint_name, query=True, worldSpace=True, translation=True)
                        joint_rot = cmds.xform(association.joint_name, query=True, worldSpace=True, rotation=True)
                        
                        # First set the preview's orientation to match the joint
                        cmds.xform(preview_curve, worldSpace=True, rotation=joint_rot)
                        
                        # Then set the pivot to the joint position
                        cmds.xform(preview_curve, worldSpace=True, rotatePivot=joint_pos)
                        cmds.xform(preview_curve, worldSpace=True, scalePivot=joint_pos)
                    
                    # Apply per-joint transforms if any
                    if (association.curve_offset_x != 0 or association.curve_offset_y != 0 or association.curve_offset_z != 0 or
                        association.curve_rotation_x != 0 or association.curve_rotation_y != 0 or association.curve_rotation_z != 0):
                        self.apply_per_joint_transforms_to_curve(preview_curve, association)
                    
                    # Apply preview styling (per-joint color and preview attribute)
                    color_index = self.get_maya_color_index(getattr(association, 'control_color', 'red'))
                    shapes = cmds.listRelatives(preview_curve, shapes=True) or []
                    for shape in shapes:
                        cmds.setAttr(shape + '.overrideEnabled', True)
                        cmds.setAttr(shape + '.overrideColor', color_index)  # Use per-joint color
                        try:
                            cmds.setAttr(shape + '.lineWidth', 3)  # Make it thick
                        except:
                            pass
                    
                    # Add preview attribute
                    if not cmds.attributeQuery('isPreview', node=preview_curve, exists=True):
                        cmds.addAttr(preview_curve, longName='isPreview', attributeType='bool', defaultValue=True)
                        cmds.setAttr(preview_curve + '.isPreview', True)
            
            if preview_curve and cmds.objExists(preview_curve):
                # Select the preview curve for easy visibility
                cmds.select(preview_curve, replace=True)
                
                print("Preview curve created: {0}".format(preview_curve))
                
            else:
                print("Failed to create preview curve for joint: {0}".format(association.joint_name))
                QMessageBox.warning(self, "Preview Failed", 
                    "Could not create preview curve for joint '{0}'.\n"
                    "Make sure the joint has associated mesh objects.".format(association.joint_name))
                
        except Exception as e:
            print("Error creating preview curve: {0}".format(str(e)))
            QMessageBox.critical(self, "Preview Error", 
                "Error creating preview curve: {0}".format(str(e)))
    
    def get_maya_color_index(self, color_name):
        """Convert color name to Maya color index"""
        color_map = {
            "yellow": 17,
            "red": 13,
            "blue": 6,
            "green": 14,
            "purple": 9,
            "light blue": 18,
            "orange": 12,
            "pink": 20,
            "light green": 19,
            "white": 16
        }
        return color_map.get(color_name, 13)  # Default to red
    
    def calculate_mesh_center_for_association(self, association):
        """Calculate the center point of all mesh objects for an association"""
        try:
            all_vertices = []
            
            # Get vertices from all mesh objects
            for mesh_obj in association.mesh_objects:
                if cmds.objExists(mesh_obj):
                    vertices = self.get_mesh_vertices_world_space(mesh_obj)
                    if vertices:
                        all_vertices.extend(vertices)
            
            if all_vertices:
                # Calculate center point
                center = self.calculate_mesh_center(all_vertices)
                return center
            else:
                # Fallback to joint position if no mesh data
                if cmds.objExists(association.joint_name):
                    return cmds.xform(association.joint_name, query=True, worldSpace=True, translation=True)
                else:
                    return [0, 0, 0]  # Origin as last fallback
                    
        except Exception as e:
            print("Error calculating mesh center: {0}".format(str(e)))
            # Fallback to joint position
            if cmds.objExists(association.joint_name):
                return cmds.xform(association.joint_name, query=True, worldSpace=True, translation=True)
            else:
                return [0, 0, 0]
    
    def cleanup_preview_curves(self, joint_name=None):
        """Clean up existing preview curves, optionally for a specific joint"""
        try:
            if joint_name:
                # Clean up preview for specific joint
                preview_name = "PREVIEW_{0}_curve*".format(joint_name)
                existing_previews = cmds.ls(preview_name, type='transform') or []
            else:
                # Clean up all preview curves
                existing_previews = cmds.ls("PREVIEW_*_curve*", type='transform') or []
            
            for preview in existing_previews:
                if cmds.objExists(preview):
                    cmds.delete(preview)
                    print("Cleaned up preview curve: {0}".format(preview))
                    
        except Exception as e:
            print("Error cleaning up preview curves: {0}".format(str(e)))
    

    
    def on_smoothness_changed(self, value):
        """Handle smoothness control value changes"""
        print("Smoothness changed to: {0} points".format(value))
        print("Note: New smoothness will be applied to the next preview curve you create.")
        print("To update existing previews, use the 'Update Previews' button or recreate them manually.")
    
    def cleanup_all_preview_curves(self):
        """Clean up all preview curves in the scene"""
        try:
            # Find all preview curves
            existing_previews = cmds.ls("PREVIEW_*_curve*", type='transform') or []
            
            if not existing_previews:
                QMessageBox.information(self, "No Previews", "No preview curves found in the scene.")
                return
            
            # Ask for confirmation
            reply = QMessageBox.question(self, "Clean Up Previews", 
                "Found {0} preview curve(s) in the scene.\n\n"
                "Are you sure you want to delete all preview curves?".format(len(existing_previews)),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            
            if reply == QMessageBox.Yes:
                deleted_count = 0
                for preview in existing_previews:
                    if cmds.objExists(preview):
                        cmds.delete(preview)
                        deleted_count += 1
                        print("Deleted preview curve: {0}".format(preview))
                
                QMessageBox.information(self, "Cleanup Complete", 
                    "Deleted {0} preview curve(s) from the scene.".format(deleted_count))
                
        except Exception as e:
            print("Error cleaning up all preview curves: {0}".format(str(e)))
            QMessageBox.critical(self, "Cleanup Error", 
                "Error cleaning up preview curves: {0}".format(str(e)))
    
    def update_existing_preview_curves(self):
        """Safely regenerate existing preview curves with current smoothness settings"""
        try:
            # Find all preview curves
            existing_previews = cmds.ls("PREVIEW_*_curve*", type='transform') or []
            
            if not existing_previews:
                QMessageBox.information(self, "No Previews", "No preview curves found in the scene.")
                return
            
            # Get current smoothness setting
            current_smoothness = self.smoothness_spin.value() if hasattr(self, 'smoothness_spin') else 20
            
            # Ask for confirmation
            reply = QMessageBox.question(self, "Update Previews", 
                "Found {0} preview curve(s) in the scene.\n\n"
                "Regenerate all preview curves with current smoothness setting ({1} points)?".format(
                    len(existing_previews), current_smoothness),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            
            if reply != QMessageBox.Yes:
                return
            
            # Find which joints have preview curves and regenerate them safely
            regenerated_count = 0
            failed_count = 0
            
            for preview_curve in existing_previews:
                try:
                    # Extract joint name from preview curve name
                    if preview_curve.startswith("PREVIEW_") and "_curve" in preview_curve:
                        joint_name = preview_curve.replace("PREVIEW_", "").split("_curve")[0]
                        
                        # Find the association for this joint
                        association_found = False
                        for association in self.joint_associations:
                            if association.joint_name == joint_name:
                                # Safely regenerate the preview curve
                                self.create_preview_curve_for_joint(association)
                                regenerated_count += 1
                                association_found = True
                                break
                        
                        if not association_found:
                            print("Warning: Could not find joint association for preview curve: {0}".format(preview_curve))
                            failed_count += 1
                            
                except Exception as e:
                    print("Error regenerating preview for {0}: {1}".format(preview_curve, str(e)))
                    failed_count += 1
            
            # Show results
            if regenerated_count > 0:
                message = "Successfully regenerated {0} preview curve(s) with smoothness = {1}".format(
                    regenerated_count, current_smoothness)
                if failed_count > 0:
                    message += "\n\n{0} curve(s) could not be regenerated.".format(failed_count)
                QMessageBox.information(self, "Update Complete", message)
                print("Updated {0} preview curves with smoothness = {1}".format(regenerated_count, current_smoothness))
            else:
                QMessageBox.warning(self, "Update Failed", 
                    "Could not regenerate any preview curves.\n"
                    "Make sure the weapon is still analyzed and joints are available.")
                    
        except Exception as e:
            print("Error updating existing preview curves: {0}".format(str(e)))
            QMessageBox.critical(self, "Update Error", 
                "Error updating preview curves: {0}".format(str(e)))
    
    def update_preview_for_joint(self, association):
        """Update the preview curve for a specific joint if it exists"""
        try:
            # Check if a preview curve exists for this joint
            preview_name = "PREVIEW_{0}_curve".format(association.joint_name)
            if cmds.objExists(preview_name):
                # Preview exists, regenerate it with current settings
                self.create_preview_curve_for_joint(association)
                print("Auto-updated preview curve for joint: {0}".format(association.joint_name))
        except Exception as e:
            # Silently fail to avoid disrupting the user's workflow
            print("Warning: Could not auto-update preview for joint {0}: {1}".format(
                association.joint_name, str(e)))
    
    def update_button_states(self):
        """Update button enabled states based on current analysis"""
        has_associations = len(self.joint_associations) > 0
        # Only count non-excluded joints for button enabling
        has_unconstrained = len([a for a in self.joint_associations if not a.has_control and not a.is_excluded]) > 0
        has_available = len([a for a in self.joint_associations if not a.is_excluded]) > 0
        
        self.create_all_btn.setEnabled(has_associations and has_unconstrained)
        self.create_complete_rig_btn.setEnabled(has_associations and has_available)
        
        # Update progress label
        if not has_associations:
            self.progress_label.setText("No joint-mesh associations found. Import a weapon first.")
        elif not has_available:
            self.progress_label.setText("All joints are excluded. Use Joint Exclusion Controls to include joints.")
        elif not has_unconstrained:
            self.progress_label.setText("All available joints already have controls. Use Rig Management to work with existing rigs.")
        else:
            unconstrained_count = len([a for a in self.joint_associations if not a.has_control and not a.is_excluded])
            excluded_count = len([a for a in self.joint_associations if a.is_excluded])
            if excluded_count > 0:
                self.progress_label.setText("Ready to create controls for {0} joint(s). ({1} excluded)".format(
                    unconstrained_count, excluded_count))
            else:
                self.progress_label.setText("Ready to create controls for {0} joint(s).".format(unconstrained_count))
    
    def update_existing_rigs_list(self):
        """Update the list of existing weapon rigs"""
        self.existing_rigs_list.clear()
        
        # Look for weapon rig groups in the scene
        all_groups = cmds.ls(type='transform')
        rig_groups = []
        
        for group in all_groups:
            # Look for groups that contain weapon rig elements
            if ('weapon' in group.lower() and 'rig' in group.lower()) or group.startswith('S2_WeaponRig'):
                children = cmds.listRelatives(group, children=True) or []
                # Check if it looks like a weapon rig (has controls and joints)
                has_controls = any('ctrl' in child.lower() or 'control' in child.lower() for child in children)
                if has_controls:
                    rig_groups.append(group)
        
        # Add to list
        for rig_group in rig_groups:
            self.existing_rigs_list.addItem(rig_group)
        
        if not rig_groups:
            item = QListWidgetItem("No weapon rigs found in scene")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.existing_rigs_list.addItem(item)
    
    def on_rig_selection_changed(self):
        """Handle rig selection change"""
        current_item = self.existing_rigs_list.currentItem()
        if current_item and current_item.flags() & Qt.ItemIsSelectable:
            rig_name = current_item.text()
            self.select_rig_btn.setEnabled(True)
            self.delete_rig_btn.setEnabled(True)
            
            # Show rig info
            if cmds.objExists(rig_name):
                children = cmds.listRelatives(rig_name, children=True) or []
                controls = [child for child in children if 'ctrl' in child.lower() or 'control' in child.lower()]
                
                info_text = "Rig: {0}\n\n".format(rig_name)
                info_text += "Controls: {0}\n\n".format(len(controls))
                
                if controls:
                    info_text += "Control list:\n"
                    for control in controls[:10]:  # Show first 10
                        info_text += "- {0}\n".format(control)
                    if len(controls) > 10:
                        info_text += "... and {0} more".format(len(controls) - 10)
                
                self.rig_info_label.setText(info_text)
            else:
                self.rig_info_label.setText("Rig group no longer exists in scene")
        else:
            self.select_rig_btn.setEnabled(False)
            self.delete_rig_btn.setEnabled(False)
            self.rig_info_label.setText("Select a rig to see information")
    
    def get_control_shape(self, association=None):
        """Get the control shape for a specific joint association"""
        if association and hasattr(association, 'control_shape'):
            return association.control_shape
        return "Custom"  # Default fallback
    
    def create_controls_for_selected(self):
        """Create controls for selected joints only"""
        # This would be implemented to work with selected joints
        # For now, redirect to create all
        self.create_all_controls()
    
    def create_all_controls(self):
        """Create controls for all joints that don't have them"""
        if not self.joint_associations:
            QMessageBox.warning(self, "No Associations", "No joint-mesh associations found. Analyze the scene first.")
            return
        
        unconstrained = [assoc for assoc in self.joint_associations if not assoc.has_control and not assoc.is_excluded]
        if not unconstrained:
            QMessageBox.information(self, "All Controls Exist", "All available joints already have controls or are excluded.")
            return
        
        try:
            created_controls = []
            failed_controls = []
            
            for association in unconstrained:
                control_name = self.create_control_for_joint(association)
                if control_name:
                    created_controls.append(control_name)
                    association.control_name = control_name
                    association.has_control = True
                else:
                    failed_controls.append(association.joint_name)
            
            # Freeze transforms on created controls
            if created_controls:
                self.freeze_all_control_transforms()
            
            # Show results
            message = "Control creation completed!\n\n"
            message += "Created: {0} controls\n".format(len(created_controls))
            message += "Failed: {0} controls\n\n".format(len(failed_controls))
            
            if created_controls:
                message += "Successfully created controls:\n"
                for control in created_controls[:10]:  # Show first 10
                    message += "- {0}\n".format(control)
                if len(created_controls) > 10:
                    message += "... and {0} more\n".format(len(created_controls) - 10)
            
            if failed_controls:
                message += "\nFailed to create controls for:\n"
                for joint in failed_controls:
                    message += "- {0}\n".format(joint)
            
            if failed_controls:
                QMessageBox.warning(self, "Creation Complete (with errors)", message)
            else:
                QMessageBox.information(self, "Creation Complete", message)
            
            # Refresh display
            self.analyze_scene()
            
        except Exception as e:
            QMessageBox.critical(self, "Creation Error", "Error creating controls: {0}".format(str(e)))
    
    def create_complete_rig(self):
        """Create a complete weapon rig with controls, constraints, and organization"""
        if not self.joint_associations:
            QMessageBox.warning(self, "No Associations", "No joint-mesh associations found. Analyze the scene first.")
            return
        
        try:
            # Clean up any existing preview curves before creating the final rig
            existing_previews = cmds.ls("PREVIEW_*_curve*", type='transform') or []
            if existing_previews:
                for preview in existing_previews:
                    if cmds.objExists(preview):
                        cmds.delete(preview)
                print("Cleaned up {0} preview curves before creating rig".format(len(existing_previews)))
            # Create all missing controls first (excluding excluded joints)
            unconstrained = [assoc for assoc in self.joint_associations if not assoc.has_control and not assoc.is_excluded]
            if unconstrained:
                for association in unconstrained:
                    control_name = self.create_control_for_joint(association)
                    if control_name:
                        association.control_name = control_name
                        association.has_control = True
            
            # Create rig hierarchy
            rig_group = self.create_rig_hierarchy()
            
            # IMPORTANT: Freeze all control transforms before creating constraints
            self.freeze_all_control_transforms()
            
            # Set up constraints from joints to controls
            self.setup_rig_constraints()
            
            # Set up attachment switching attributes
            self.setup_attachment_attributes(rig_group)
            
            # Show completion message
            controls_count = len([assoc for assoc in self.joint_associations if assoc.has_control])
            
            # Count attachment categories and display names
            attachment_categories = []
            total_display_names = 0
            if self.attachments_by_joint:
                # Group by category to count category attributes
                categories = set()
                for joint_name in self.attachments_by_joint:
                    attachment_categories_list = self.attachment_categories_by_joint.get(joint_name, [])
                    categories.update(attachment_categories_list)
                    attachment_names = self.attachment_names_by_joint.get(joint_name, [])
                    total_display_names += len(attachment_names)
                attachment_categories = list(categories)
            
            message = "Complete weapon rig created successfully!\n\n"
            message += "Rig group: {0}\n".format(rig_group)
            message += "Controls created: {0}\n".format(controls_count)
            message += "Constraint setup: Complete\n"
            
            if attachment_categories:
                message += "Attachment categories: {0}\n".format(len(attachment_categories))
                message += "  Categories: {0}\n".format(", ".join(attachment_categories))
                message += "  Total attachments: {0}\n".format(total_display_names)
            else:
                message += "Attachment categories: None\n"
            
            message += "\nThe weapon rig is now ready for animation.\n"
            message += "Animate the control curves to pose the weapon parts."
            
            if attachment_categories:
                message += "\n\nAttachment switching (Two-Tier System):"
                for category in attachment_categories:
                    attr_name = self.make_safe_attribute_name(category)
                    message += "\n• '{0}' category - select display names within category".format(attr_name)
            
            QMessageBox.information(self, "Rig Creation Complete", message)
            
            # Refresh display
            self.analyze_scene()
            
        except Exception as e:
            QMessageBox.critical(self, "Rig Creation Error", "Error creating complete rig: {0}".format(str(e)))
    
    def create_control_for_joint(self, association):
        """Create a control curve for a specific joint association"""
        joint_name = association.joint_name
        
        # Generate control name
        suffix = self.suffix_edit.text() or "_ctrl"
        control_name = joint_name + suffix
        
        # Make name unique if it already exists
        if cmds.objExists(control_name):
            counter = 1
            while cmds.objExists("{0}_{1:02d}".format(control_name, counter)):
                counter += 1
            control_name = "{0}_{1:02d}".format(control_name, counter)
        
        try:
            # Use the per-joint control shape
            shape_type = association.control_shape if hasattr(association, 'control_shape') else "Custom"
            
            # Create control curve with per-joint transformations
            control = self.create_control_curve(control_name, shape_type, association.control_scale, association)
            
            if control and cmds.objExists(control):
                # Control is already positioned and rotated by create_unified_curve
                print("Created control '{0}' for joint '{1}'".format(control, joint_name))
                return control
            else:
                print("Error: Failed to create control curve")
                return None
                
        except Exception as e:
            print("Error creating control for joint '{0}': {1}".format(joint_name, str(e)))
            return None
    
    def create_control_curve(self, name, shape_type, scale, association):
        """Create a control curve using unified method or basic shapes"""
        if shape_type == "Custom":
            # Use the unified mesh-fitting method for custom shapes
            control = self.create_unified_curve(name, association, is_preview=False)
            
            if control and cmds.objExists(control):
                print("Created custom mesh-fitted control for {0}".format(name))
                return control
            else:
                print("Custom shape failed, falling back to sphere for {0}".format(name))
                shape_type = "sphere"  # Fallback to sphere if custom fails
        
        # Create basic geometric shapes (mesh-fitted)
        if shape_type in ["box", "cylinder", "sphere"]:
            print("Creating mesh-fitted {0} control shape for {1}".format(shape_type, name))
            control = self.create_basic_control_shape(name, shape_type, scale, association)
            
            # Set color and positioning FIRST
            if control and cmds.objExists(control):
                # Position the control at the mesh center (like custom shapes)
                mesh_center = self.calculate_mesh_center_for_association(association)
                cmds.xform(control, worldSpace=True, translation=mesh_center)
                
                # Set pivot and orientation to match joint for proper constraint behavior
                if cmds.objExists(association.joint_name):
                    joint_pos = cmds.xform(association.joint_name, query=True, worldSpace=True, translation=True)
                    joint_rot = cmds.xform(association.joint_name, query=True, worldSpace=True, rotation=True)
                    
                    # First set the control's orientation to match the joint
                    cmds.xform(control, worldSpace=True, rotation=joint_rot)
                    
                    # Then set the pivot to the joint position
                    cmds.xform(control, worldSpace=True, rotatePivot=joint_pos)
                    cmds.xform(control, worldSpace=True, scalePivot=joint_pos)
                    
                    print("Set control orientation and pivot to match joint: pos={0}, rot={1}".format(joint_pos, joint_rot))
                
                # THEN apply per-joint transformations to basic shapes (after positioning)
                if association:
                    self.apply_per_joint_transforms_to_curve(control, association)
                
                # Set color using per-joint color setting
                color_index = self.get_maya_color_index(getattr(association, 'control_color', 'red'))
                shapes = cmds.listRelatives(control, shapes=True) or []
                for shape in shapes:
                    cmds.setAttr(shape + '.overrideEnabled', True)
                    cmds.setAttr(shape + '.overrideColor', color_index)
                

            
            return control
        
        return None
    
    def create_unified_curve(self, name, association, is_preview=False):
        """Unified curve creation method used by both preview and control creation"""
        try:
            # Get the joint position for reference
            joint_pos = [0, 0, 0]  # Default to origin
            if cmds.objExists(association.joint_name):
                joint_pos = cmds.xform(association.joint_name, query=True, worldSpace=True, translation=True)
            else:
                print("Warning: Joint '{0}' not found, creating curve at origin".format(association.joint_name))
            
            # Use the per-joint scale multiplier for both preview and controls
            scale_multiplier = association.control_scale if hasattr(association, 'control_scale') else 1.0
            
            # Create curve using vertex clustering
            curve = self.create_curve_from_vertex_clustering(
                association.mesh_objects, 
                name, 
                joint_pos, 
                scale_multiplier, 
                association
            )
            
            if curve and cmds.objExists(curve):
                # Position the curve at the joint
                cmds.xform(curve, worldSpace=True, translation=joint_pos)
                
                # Set pivot to joint position and orientation for proper constraint behavior
                joint_rot = cmds.xform(association.joint_name, query=True, worldSpace=True, rotation=True)
                cmds.xform(curve, worldSpace=True, rotatePivot=joint_pos)
                cmds.xform(curve, worldSpace=True, scalePivot=joint_pos)
                
                # Apply joint rotation to match joint orientation
                cmds.xform(curve, worldSpace=True, rotation=joint_rot)
                
                # Apply global offset if any
                if hasattr(self, 'offset_x_spin'):
                    global_offset_x = self.offset_x_spin.value()
                    global_offset_y = self.offset_y_spin.value()
                    global_offset_z = self.offset_z_spin.value()
                    
                    if global_offset_x != 0 or global_offset_y != 0 or global_offset_z != 0:
                        self.apply_curve_offset(curve, global_offset_x, global_offset_y, global_offset_z)
                
                # Apply styling based on whether this is a preview or control
                shapes = cmds.listRelatives(curve, shapes=True) or []
                for shape in shapes:
                    cmds.setAttr(shape + '.overrideEnabled', True)
                    
                    # Make BOTH preview and control curves thick for visibility
                    try:
                        cmds.setAttr(shape + '.lineWidth', 3)
                    except:
                        pass  # lineWidth may not be available on all curve types
                    
                    if is_preview:
                        # Use per-joint color for preview curves
                        color_index = self.get_maya_color_index(getattr(association, 'control_color', 'red'))
                        cmds.setAttr(shape + '.overrideColor', color_index)
                        # Add preview attribute
                        if not cmds.attributeQuery('isPreview', node=curve, exists=True):
                            cmds.addAttr(curve, longName='isPreview', attributeType='bool', defaultValue=True)
                            cmds.setAttr(curve + '.isPreview', True)
                    else:
                        # Use per-joint color for final controls
                        color_index = self.get_maya_color_index(getattr(association, 'control_color', 'red'))
                        cmds.setAttr(shape + '.overrideColor', color_index)
                

                
                print("Created {0} curve: {1}".format("preview" if is_preview else "control", name))
                return curve
            else:
                print("Failed to create curve using vertex clustering")
                return None
                
        except Exception as e:
            print("Error in unified curve creation: {0}".format(str(e)))
            return None
    

    
    def calculate_mesh_center(self, vertices):
        """Calculate the center point of a set of vertices"""
        if not vertices:
            return [0, 0, 0]
        
        avg_x = sum(v[0] for v in vertices) / len(vertices)
        avg_y = sum(v[1] for v in vertices) / len(vertices) 
        avg_z = sum(v[2] for v in vertices) / len(vertices)
        
        return [avg_x, avg_y, avg_z]
    
    def create_curve_from_mesh_direct(self, mesh_objects, name, joint_pos, scale_multiplier):
        """Create a curve directly from mesh geometry using Maya's curve-on-mesh features"""
        try:
            for mesh_obj in mesh_objects:
                if not cmds.objExists(mesh_obj):
                    continue
                
                print("Attempting direct curve creation from mesh: {0}".format(mesh_obj))
                
                # Method 1: Try to extract boundary edges and convert to curve
                boundary_curve = self.extract_mesh_boundary_as_curve(mesh_obj, name, joint_pos, scale_multiplier)
                if boundary_curve:
                    return boundary_curve
                
                # Method 2: Try to project a curve onto the mesh surface
                surface_curve = self.project_curve_on_mesh_surface(mesh_obj, name, joint_pos, scale_multiplier)
                if surface_curve:
                    return surface_curve
                    
            return None
            
        except Exception as e:
            print("Error in direct mesh curve creation: {0}".format(str(e)))
            return None
    
    def extract_mesh_boundary_as_curve(self, mesh_obj, name, joint_pos, scale_multiplier):
        """Extract the mesh boundary edges and convert them to a curve"""
        try:
            # Get mesh bounding box to determine best slicing plane
            bbox = cmds.exactWorldBoundingBox(mesh_obj)
            min_x, min_y, min_z, max_x, max_y, max_z = bbox
            
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2  
            center_z = (min_z + max_z) / 2
            
            width = max_x - min_x
            height = max_y - min_y
            depth = max_z - min_z
            
            print("Mesh bbox: W={0:.3f}, H={1:.3f}, D={2:.3f}".format(width, height, depth))
            
            # Create a cutting plane based on the smallest dimension
            if width <= height and width <= depth:
                # Cut along YZ plane at center X
                plane_normal = [1, 0, 0]
                plane_point = [center_x, center_y, center_z]
                print("Using YZ cutting plane (X={0:.3f})".format(center_x))
            elif height <= width and height <= depth:
                # Cut along XZ plane at center Y
                plane_normal = [0, 1, 0]
                plane_point = [center_x, center_y, center_z]
                print("Using XZ cutting plane (Y={0:.3f})".format(center_y))
            else:
                # Cut along XY plane at center Z
                plane_normal = [0, 0, 1]
                plane_point = [center_x, center_y, center_z]
                print("Using XY cutting plane (Z={0:.3f})".format(center_z))
            
            # Try to use Maya's polyToCurve or similar commands
            curve = self.slice_mesh_with_plane(mesh_obj, plane_point, plane_normal, name, joint_pos, scale_multiplier)
            
            return curve
            
        except Exception as e:
            print("Error extracting mesh boundary: {0}".format(str(e)))
            return None
    
    def slice_mesh_with_plane(self, mesh_obj, plane_point, plane_normal, name, joint_pos, scale_multiplier):
        """Slice the mesh with a plane and extract the intersection as a curve"""
        try:
            # Create a temporary cutting plane
            plane_size = 10.0  # Large enough to intersect the mesh
            
            # Create a plane primitive
            plane = cmds.polyPlane(width=plane_size, height=plane_size, subdivisionsX=1, subdivisionsY=1, name="temp_cutting_plane")[0]
            
            # Position and orient the plane
            cmds.xform(plane, worldSpace=True, translation=plane_point)
            
            # Orient the plane based on normal
            if plane_normal == [1, 0, 0]:  # YZ plane
                cmds.xform(plane, worldSpace=True, rotation=[0, 0, 90])
            elif plane_normal == [0, 1, 0]:  # XZ plane  
                cmds.xform(plane, worldSpace=True, rotation=[90, 0, 0])
            # XY plane needs no rotation (default)
            
            # Try to intersect the mesh with the plane
            intersection_curve = self.intersect_mesh_with_plane(mesh_obj, plane, name, joint_pos, scale_multiplier)
            
            # Clean up the temporary plane
            cmds.delete(plane)
            
            return intersection_curve
            
        except Exception as e:
            print("Error slicing mesh with plane: {0}".format(str(e)))
            return None
    
    def intersect_mesh_with_plane(self, mesh_obj, plane_obj, name, joint_pos, scale_multiplier):
        """Find intersection between mesh and plane, convert to curve"""
        try:
            # Duplicate the mesh to work with
            temp_mesh = cmds.duplicate(mesh_obj, name="temp_mesh_for_intersection")[0]
            
            # Try different approaches to get the intersection
            
            # Method 1: Use polyBoolean to get intersection curves
            try:
                # This might create intersection curves
                result = cmds.polyBoolOp(temp_mesh, plane_obj, operation=3, constructionHistory=False)  # Intersection
                
                if result and cmds.objExists(result[0]):
                    # Try to convert result to curves
                    curves = self.convert_mesh_edges_to_curves(result[0], name, joint_pos, scale_multiplier)
                    cmds.delete(result)
                    cmds.delete(temp_mesh)
                    return curves
                    
            except:
                pass
            
            # Method 2: Extract edges at the intersection level
            intersection_points = self.find_mesh_plane_intersection_points(temp_mesh, plane_obj)
            
            cmds.delete(temp_mesh)
            
            if intersection_points and len(intersection_points) > 2:
                # Create curve from intersection points
                curve_points = self.convert_to_relative_points(intersection_points, joint_pos)
                
                # Apply scale multiplier
                if scale_multiplier != 1.0:
                    center = self.calculate_mesh_center(curve_points)
                    curve_points = self.scale_points_around_center(curve_points, center, scale_multiplier)
                
                # Create the curve
                if len(curve_points) >= 3:
                    curve = cmds.curve(name=name, degree=1, point=curve_points)
                    # Close the curve
                    self.close_curve_if_needed(curve)
                    return curve
            
            return None
            
        except Exception as e:
            print("Error intersecting mesh with plane: {0}".format(str(e)))
            return None
    
    def create_curve_from_mesh_edges(self, mesh_objects, name, joint_pos, scale_multiplier):
        """Create curve by extracting and following mesh edges"""
        try:
            for mesh_obj in mesh_objects:
                if not cmds.objExists(mesh_obj):
                    continue
                
                print("Extracting boundary edges from: {0}".format(mesh_obj))
                
                # Get all boundary edges (edges with only one face)
                boundary_edges = self.get_boundary_edges(mesh_obj)
                
                if boundary_edges:
                    # Convert boundary edges to a continuous curve
                    curve = self.boundary_edges_to_curve(boundary_edges, mesh_obj, name, joint_pos, scale_multiplier)
                    if curve:
                        return curve
                
                # If no boundary edges, try to extract prominent edge loops
                edge_loops = self.get_prominent_edge_loops(mesh_obj)
                
                if edge_loops:
                    # Convert best edge loop to curve
                    curve = self.edge_loop_to_curve(edge_loops[0], mesh_obj, name, joint_pos, scale_multiplier)
                    if curve:
                        return curve
            
            return None
            
        except Exception as e:
            print("Error creating curve from mesh edges: {0}".format(str(e)))
            return None
    
    def get_boundary_edges(self, mesh_obj):
        """Get edges that are on the boundary of the mesh"""
        try:
            # Select the mesh
            cmds.select(mesh_obj)
            
            # Convert to edge selection mode
            cmds.selectMode(component=True)
            cmds.selectType(edge=True)
            
            # Get all edges
            all_edges = cmds.polyListComponentConversion(toEdge=True)
            cmds.select(all_edges)
            
            # Find boundary edges (edges connected to only one face)
            boundary_edges = []
            
            if all_edges:
                cmds.select(all_edges[0])
                
                # Use Maya's polySelectBorderShell to find boundary edges
                try:
                    cmds.polySelectBorderShell(1)  # Select border edges
                    selected = cmds.ls(selection=True, flatten=True)
                    if selected:
                        boundary_edges = selected
                except:
                    pass
            
            cmds.select(clear=True)
            print("Found {0} boundary edges".format(len(boundary_edges)))
            return boundary_edges
            
        except Exception as e:
            print("Error getting boundary edges: {0}".format(str(e)))
            return []
    
    def boundary_edges_to_curve(self, boundary_edges, mesh_obj, name, joint_pos, scale_multiplier):
        """Convert boundary edges to a curve"""
        try:
            if not boundary_edges:
                return None
            
            # Get the positions of all edge vertices
            edge_points = []
            for edge in boundary_edges:
                # Get edge vertices
                vertices = cmds.polyListComponentConversion(edge, toVertex=True)
                vertices = cmds.ls(vertices, flatten=True)
                
                for vertex in vertices:
                    if vertex not in [item[1] for item in edge_points]:  # Avoid duplicates
                        pos = cmds.pointPosition(vertex, world=True)
                        edge_points.append((vertex, pos))
            
            if len(edge_points) < 3:
                return None
            
            # Sort points to create a continuous path
            sorted_points = self.sort_points_for_continuous_curve([pt[1] for pt in edge_points])
            
            if not sorted_points:
                return None
            
            # Convert to relative points
            curve_points = self.convert_to_relative_points(sorted_points, joint_pos)
            
            # Apply scale multiplier
            if scale_multiplier != 1.0:
                center = self.calculate_mesh_center(curve_points)
                curve_points = self.scale_points_around_center(curve_points, center, scale_multiplier)
            
            # Create the curve
            if len(curve_points) >= 3:
                curve = cmds.curve(name=name, degree=1, point=curve_points)
                self.close_curve_if_needed(curve)
                return curve
            
            return None
            
        except Exception as e:
            print("Error converting boundary edges to curve: {0}".format(str(e)))
            return None
    
    def create_curve_from_mesh_contour(self, mesh_objects, name, joint_pos, scale_multiplier):
        """Create curve by sampling mesh contour at optimal slice level"""
        try:
            for mesh_obj in mesh_objects:
                if not cmds.objExists(mesh_obj):
                    continue
                
                print("Creating contour curve from: {0}".format(mesh_obj))
                
                # Sample the mesh at multiple levels to find the best contour
                contour_curve = self.sample_mesh_contour_levels(mesh_obj, name, joint_pos, scale_multiplier)
                
                if contour_curve:
                    return contour_curve
            
            return None
            
        except Exception as e:
            print("Error creating curve from mesh contour: {0}".format(str(e)))
            return None
    
    def sample_mesh_contour_levels(self, mesh_obj, name, joint_pos, scale_multiplier):
        """Sample mesh at different levels to find the best contour"""
        try:
            # Get mesh bounding box
            bbox = cmds.exactWorldBoundingBox(mesh_obj)
            min_x, min_y, min_z, max_x, max_y, max_z = bbox
            
            # Determine which axis to sample along (smallest dimension)
            dimensions = {
                'x': (max_x - min_x, min_x, max_x),
                'y': (max_y - min_y, min_y, max_y), 
                'z': (max_z - min_z, min_z, max_z)
            }
            
            # Sort by size and sample along the smallest dimension
            sorted_dims = sorted(dimensions.items(), key=lambda x: x[1][0])
            sample_axis = sorted_dims[0][0]
            axis_min = sorted_dims[0][1][1]
            axis_max = sorted_dims[0][1][2]
            
            print("Sampling along {0} axis from {1:.3f} to {2:.3f}".format(sample_axis, axis_min, axis_max))
            
            # Sample at multiple levels
            best_contour = None
            best_point_count = 0
            
            sample_levels = 5
            for i in range(sample_levels):
                level = axis_min + (axis_max - axis_min) * (i + 1) / (sample_levels + 1)
                
                contour_points = self.extract_contour_at_level(mesh_obj, sample_axis, level)
                
                if contour_points and len(contour_points) > best_point_count:
                    best_contour = contour_points
                    best_point_count = len(contour_points)
            
            if best_contour and len(best_contour) >= 3:
                # Convert to relative points
                curve_points = self.convert_to_relative_points(best_contour, joint_pos)
                
                # Apply scale multiplier
                if scale_multiplier != 1.0:
                    center = self.calculate_mesh_center(curve_points)
                    curve_points = self.scale_points_around_center(curve_points, center, scale_multiplier)
                
                # Create the curve
                curve = cmds.curve(name=name, degree=1, point=curve_points)
                self.close_curve_if_needed(curve)
                return curve
            
            return None
            
        except Exception as e:
            print("Error sampling mesh contour levels: {0}".format(str(e)))
            return None
    
    def extract_contour_at_level(self, mesh_obj, axis, level):
        """Extract contour points by intersecting mesh with a plane at given level"""
        try:
            # This is a simplified version - in practice we'd need more sophisticated mesh intersection
            # For now, get vertices close to the level and project them
            
            vertices = self.get_mesh_vertices_world_space(mesh_obj)
            if not vertices:
                return []
            
            axis_index = {'x': 0, 'y': 1, 'z': 2}[axis]
            tolerance = 0.1  # Distance tolerance for "at level"
            
            # Find vertices close to the level
            near_level_vertices = []
            for vertex in vertices:
                if abs(vertex[axis_index] - level) < tolerance:
                    near_level_vertices.append(vertex)
            
            if len(near_level_vertices) < 3:
                return []
            
            # Project vertices to the plane and find convex hull
            if axis == 'x':
                projected = [(v[1], v[2]) for v in near_level_vertices]
            elif axis == 'y':
                projected = [(v[0], v[2]) for v in near_level_vertices]
            else:  # z
                projected = [(v[0], v[1]) for v in near_level_vertices]
            
            hull_2d = self.convex_hull_2d(projected)
            
            # Convert back to 3D
            contour_3d = []
            for point_2d in hull_2d:
                if axis == 'x':
                    point_3d = [level, point_2d[0], point_2d[1]]
                elif axis == 'y':
                    point_3d = [point_2d[0], level, point_2d[1]]
                else:  # z
                    point_3d = [point_2d[0], point_2d[1], level]
                contour_3d.append(point_3d)
            
            return contour_3d
            
        except Exception as e:
            print("Error extracting contour at level: {0}".format(str(e)))
            return []
    
    # Helper methods for the new curve creation system
    
    def convert_to_relative_points(self, world_points, joint_pos):
        """Convert world space points to joint-relative points"""
        relative_points = []
        for point in world_points:
            relative_point = [
                point[0] - joint_pos[0],
                point[1] - joint_pos[1],
                point[2] - joint_pos[2]
            ]
            relative_points.append(relative_point)
        return relative_points
    
    def scale_points_around_center(self, points, center, scale_factor):
        """Scale points around a center point"""
        scaled_points = []
        for point in points:
            scaled_point = [
                center[0] + (point[0] - center[0]) * scale_factor,
                center[1] + (point[1] - center[1]) * scale_factor,
                center[2] + (point[2] - center[2]) * scale_factor
            ]
            scaled_points.append(scaled_point)
        return scaled_points
    
    def close_curve_if_needed(self, curve):
        """Close a curve if it's not already closed"""
        try:
            # Check if curve is closed by comparing first and last CVs
            spans = cmds.getAttr(curve + ".spans")
            degree = cmds.getAttr(curve + ".degree")
            
            first_cv = cmds.pointPosition(curve + ".cv[0]", world=True)
            last_cv = cmds.pointPosition(curve + ".cv[{0}]".format(spans), world=True)
            
            distance = sum([(first_cv[i] - last_cv[i])**2 for i in range(3)])**0.5
            
            if distance > 0.001:  # If not closed
                # Get current degree to maintain it
                current_degree = cmds.getAttr(curve + ".degree")
                
                # Rebuild as closed curve maintaining the degree
                cmds.rebuildCurve(curve, constructionHistory=False, replaceOriginal=True, 
                                rebuildType=0, endKnots=1, keepRange=0, keepControlPoints=True,
                                keepEndPoints=True, keepTangents=True, spans=0, degree=current_degree)
                # Make it periodic (closed)
                cmds.closeCurve(curve, constructionHistory=False, replaceOriginal=True)
                
        except Exception as e:
            print("Warning: Could not close curve: {0}".format(str(e)))
    
    def sort_points_for_continuous_curve(self, points):
        """Sort points to create a continuous curve path"""
        if len(points) < 3:
            return points
        
        try:
            # Simple nearest-neighbor sorting for continuous path
            sorted_points = [points[0]]
            remaining_points = points[1:]
            
            while remaining_points:
                current_point = sorted_points[-1]
                
                # Find nearest remaining point
                min_distance = float('inf')
                nearest_point = None
                nearest_index = -1
                
                for i, point in enumerate(remaining_points):
                    distance = sum([(current_point[j] - point[j])**2 for j in range(3)])**0.5
                    if distance < min_distance:
                        min_distance = distance
                        nearest_point = point
                        nearest_index = i
                
                if nearest_point:
                    sorted_points.append(nearest_point)
                    remaining_points.pop(nearest_index)
                else:
                    break
            
            return sorted_points
            
        except Exception as e:
            print("Error sorting points: {0}".format(str(e)))
            return points
    
    def apply_curve_offset(self, curve, offset_x, offset_y, offset_z):
        """Apply offset to curve control vertices"""
        try:
            if not curve or not cmds.objExists(curve):
                return
            
            # Get number of CVs
            spans = cmds.getAttr(curve + ".spans")
            degree = cmds.getAttr(curve + ".degree")
            num_cvs = spans + degree
            
            # Move each CV by the offset
            for i in range(num_cvs):
                cv_name = "{0}.cv[{1}]".format(curve, i)
                current_pos = cmds.pointPosition(cv_name, world=False)  # Local space
                new_pos = [
                    current_pos[0] + offset_x,
                    current_pos[1] + offset_y,
                    current_pos[2] + offset_z
                ]
                cmds.move(new_pos[0], new_pos[1], new_pos[2], cv_name, absolute=True, objectSpace=True)
                
        except Exception as e:
                         print("Error applying curve offset: {0}".format(str(e)))
    
    # Vertex clustering mesh curve creation method
    
    def create_curve_from_vertex_clustering(self, mesh_objects, name, joint_pos, scale_multiplier, association=None):
        """Create curve using vertex clustering approach - works with any triangulated mesh"""
        try:
            for mesh_obj in mesh_objects:
                if not cmds.objExists(mesh_obj):
                    continue
                
                print("Using vertex clustering for: {0}".format(mesh_obj))
                
                # Step 1: Get all vertices in mesh local space
                vertices = self.get_mesh_vertices_world_space(mesh_obj)
                if not vertices or len(vertices) < 3:
                    continue
                
                # Step 2: Cluster vertices to remove interior points
                clustered_vertices = self.cluster_mesh_vertices(vertices)
                
                if not clustered_vertices or len(clustered_vertices) < 3:
                    continue
                
                # Step 3: Find convex hull of clustered vertices
                hull_points = self.get_3d_convex_hull_approximation(clustered_vertices)
                
                if not hull_points or len(hull_points) < 3:
                    continue
                
                # Step 4: Convert to curve with per-joint transformations
                curve = self.create_curve_from_hull_points_with_transforms(hull_points, name, joint_pos, scale_multiplier, association)
                
                if curve:
                    print("Created curve using vertex clustering with {0} points".format(len(hull_points)))
                    return curve
            
            return None
            
        except Exception as e:
            print("Error in vertex clustering: {0}".format(str(e)))
            return None
    
    def cluster_mesh_vertices(self, vertices):
        """Cluster vertices to remove interior points and keep boundary representatives"""
        try:
            if len(vertices) <= 20:
                return vertices  # If few vertices, use them all
            
            # Step 1: Find mesh center
            center = self.calculate_mesh_center(vertices)
            
            # Step 2: Calculate distances from center
            vertex_distances = []
            for i, vertex in enumerate(vertices):
                distance = sum((vertex[j] - center[j])**2 for j in range(3))**0.5
                vertex_distances.append((distance, i, vertex))
            
            # Step 3: Sort by distance (furthest first - these are likely boundary points)
            vertex_distances.sort(reverse=True)
            
            # Step 4: Cluster by spatial proximity
            clustered = []
            cluster_radius = self.calculate_cluster_radius(vertices)
            
            for distance, index, vertex in vertex_distances:
                # Check if this vertex is far enough from existing clustered vertices
                is_new_cluster = True
                for existing_vertex in clustered:
                    existing_distance = sum((vertex[j] - existing_vertex[j])**2 for j in range(3))**0.5
                    if existing_distance < cluster_radius:
                        is_new_cluster = False
                        break
                
                if is_new_cluster:
                    clustered.append(vertex)
                    
                    # Stop when we have enough representative points
                    if len(clustered) >= 20:
                        break
            
            # Step 5: Ensure we have at least a minimum number of points
            if len(clustered) < 8:
                # Take the N furthest points
                clustered = [item[2] for item in vertex_distances[:max(8, len(vertex_distances)//4)]]
            
            print("Clustered {0} vertices down to {1} representative points".format(len(vertices), len(clustered)))
            return clustered
            
        except Exception as e:
            print("Error clustering vertices: {0}".format(str(e)))
            return vertices[:20]  # Fallback to first 20 vertices
    
    def calculate_cluster_radius(self, vertices):
        """Calculate appropriate clustering radius based on mesh size"""
        try:
            # Find bounding box
            min_coords = [min(v[i] for v in vertices) for i in range(3)]
            max_coords = [max(v[i] for v in vertices) for i in range(3)]
            
            # Calculate mesh dimensions
            dimensions = [max_coords[i] - min_coords[i] for i in range(3)]
            avg_dimension = sum(dimensions) / 3.0
            
            # Cluster radius should be about 10-20% of average dimension
            cluster_radius = avg_dimension * 0.15
            
            # Clamp to reasonable values
            cluster_radius = max(0.01, min(5.0, cluster_radius))
            
            return cluster_radius
            
        except:
            return 0.5  # Default fallback
    
    def get_3d_convex_hull_approximation(self, vertices):
        """Get 3D convex hull approximation using projection method"""
        try:
            if len(vertices) <= 8:
                return vertices
            
            # Find the best projection plane
            bbox_dims = self.get_bbox_dimensions(vertices)
            
            # Project to the plane with largest area
            if bbox_dims['xy_area'] >= bbox_dims['xz_area'] and bbox_dims['xy_area'] >= bbox_dims['yz_area']:
                # Project to XY plane
                projected = [(v[0], v[1]) for v in vertices]
                constant_axis = 2  # Z
                constant_value = sum(v[2] for v in vertices) / len(vertices)
            elif bbox_dims['xz_area'] >= bbox_dims['yz_area']:
                # Project to XZ plane
                projected = [(v[0], v[2]) for v in vertices]
                constant_axis = 1  # Y
                constant_value = sum(v[1] for v in vertices) / len(vertices)
            else:
                # Project to YZ plane
                projected = [(v[1], v[2]) for v in vertices]
                constant_axis = 0  # X
                constant_value = sum(v[0] for v in vertices) / len(vertices)
            
            # Get 2D convex hull
            hull_2d = self.convex_hull_2d(projected)
            
            # Convert back to 3D
            hull_3d = []
            for point_2d in hull_2d:
                if constant_axis == 0:  # X was constant
                    point_3d = [constant_value, point_2d[0], point_2d[1]]
                elif constant_axis == 1:  # Y was constant
                    point_3d = [point_2d[0], constant_value, point_2d[1]]
                else:  # Z was constant
                    point_3d = [point_2d[0], point_2d[1], constant_value]
                
                hull_3d.append(point_3d)
            
            return hull_3d
            
        except Exception as e:
            print("Error getting 3D convex hull: {0}".format(str(e)))
            return vertices[:8]  # Fallback
    
    def get_bbox_dimensions(self, vertices):
        """Get bounding box dimensions and areas"""
        min_x = min(v[0] for v in vertices)
        max_x = max(v[0] for v in vertices)
        min_y = min(v[1] for v in vertices)
        max_y = max(v[1] for v in vertices)
        min_z = min(v[2] for v in vertices)
        max_z = max(v[2] for v in vertices)
        
        width = max_x - min_x
        height = max_y - min_y
        depth = max_z - min_z
        
        return {
            'width': width,
            'height': height,
            'depth': depth,
            'xy_area': width * height,
            'xz_area': width * depth,
            'yz_area': height * depth
        }
    
    def create_curve_from_hull_points_with_transforms(self, hull_points, name, joint_pos, scale_multiplier, association):
        """Create curve from convex hull points with per-joint transformations"""
        try:
            # Convert to joint-relative coordinates
            curve_points_relative = self.convert_to_relative_points(hull_points, joint_pos)
            
            # Apply scale multiplier
            if scale_multiplier != 1.0:
                center = self.calculate_mesh_center(curve_points_relative)
                curve_points_relative = self.scale_points_around_center(curve_points_relative, center, scale_multiplier)
            
            # Apply per-joint transformations if association is provided
            if association:
                curve_points_relative = self.apply_per_joint_transforms(curve_points_relative, association)
            
            # Enhance curve points for smoother result
            curve_points_relative = self.enhance_curve_points_for_smoothness(curve_points_relative)
            
            # Create a smooth curve with higher degree
            curve = cmds.curve(name=name, degree=3, point=curve_points_relative)
            
            # Close the curve
            self.close_curve_if_needed(curve)
            
            return curve
            
        except Exception as e:
            print("Error creating curve from hull points: {0}".format(str(e)))
            return None
    
    def create_curve_from_hull_points(self, hull_points, name, joint_pos, scale_multiplier):
        """Create curve from convex hull points (legacy method without transforms)"""
        return self.create_curve_from_hull_points_with_transforms(hull_points, name, joint_pos, scale_multiplier, None)
    
    def enhance_curve_points_for_smoothness(self, points):
        """Enhance curve points for smoother curves with more detail"""
        try:
            if len(points) < 3:
                return points
            
            # Use smoothness setting from UI
            target_points = self.smoothness_spin.value() if hasattr(self, 'smoothness_spin') else 20
            min_points = max(8, target_points // 3)  # Minimum is 1/3 of target
            
            print("Enhancing curve points with target: {0}, min: {1}".format(target_points, min_points))
            
            if len(points) < min_points:
                # Interpolate additional points if we have too few
                enhanced_points = self.interpolate_curve_points(points, min_points)
            elif len(points) > target_points * 2:
                # If we have way too many points, intelligently reduce while preserving shape
                enhanced_points = self.smart_simplify_points(points, target_points)
            else:
                # Good number of points, just use as-is
                enhanced_points = points
            
            # Add intermediate points for extra smoothness
            smooth_points = self.add_intermediate_points(enhanced_points)
            
            print("Enhanced curve points: {0} -> {1} points for smoother curve".format(len(points), len(smooth_points)))
            return smooth_points
            
        except Exception as e:
            print("Error enhancing curve points: {0}".format(str(e)))
            return points
    
    def interpolate_curve_points(self, points, target_count):
        """Interpolate additional points between existing points"""
        if len(points) >= target_count:
            return points
        
        interpolated = [points[0]]  # Start with first point
        
        for i in range(len(points) - 1):
            current = points[i]
            next_point = points[i + 1]
            
            # Add the current point
            if i > 0:  # Skip first point as it's already added
                interpolated.append(current)
            
            # Calculate how many intermediate points to add
            remaining_segments = len(points) - 1 - i
            remaining_target = target_count - len(interpolated)
            
            if remaining_segments > 0 and remaining_target > 1:
                intermediate_count = min(2, remaining_target // remaining_segments)
                
                # Add intermediate points
                for j in range(1, intermediate_count + 1):
                    t = float(j) / (intermediate_count + 1)
                    intermediate = [
                        current[0] + t * (next_point[0] - current[0]),
                        current[1] + t * (next_point[1] - current[1]),
                        current[2] + t * (next_point[2] - current[2])
                    ]
                    interpolated.append(intermediate)
        
        # Add the last point
        interpolated.append(points[-1])
        
        return interpolated
    
    def smart_simplify_points(self, points, target_count):
        """Intelligently simplify points while preserving curve shape"""
        if len(points) <= target_count:
            return points
        
        # Use Douglas-Peucker algorithm for shape-preserving simplification
        tolerance = 0.05  # Start with small tolerance
        simplified = self.douglas_peucker_3d(points, tolerance)
        
        # If still too many points, increase tolerance
        while len(simplified) > target_count * 1.5 and tolerance < 1.0:
            tolerance *= 1.5
            simplified = self.douglas_peucker_3d(points, tolerance)
        
        # If still too many, fall back to even sampling
        if len(simplified) > target_count * 1.5:
            step = len(simplified) // target_count
            simplified = [simplified[i] for i in range(0, len(simplified), step)]
        
        return simplified
    
    def add_intermediate_points(self, points):
        """Add intermediate points between each pair for extra smoothness"""
        if len(points) < 3:
            return points
        
        smooth_points = []
        
        for i in range(len(points)):
            # Add the current point
            smooth_points.append(points[i])
            
            # Add intermediate point to next (except for last point)
            if i < len(points) - 1:
                current = points[i]
                next_point = points[i + 1]
                
                # Create intermediate point
                intermediate = [
                    (current[0] + next_point[0]) / 2.0,
                    (current[1] + next_point[1]) / 2.0,
                    (current[2] + next_point[2]) / 2.0
                ]
                smooth_points.append(intermediate)
        
        return smooth_points
    
    def simplify_curve_points(self, points, min_points, max_points):
        """Simplify curve points using even sampling (legacy method)"""
        try:
            if len(points) <= max_points:
                return points
            
            # Use even sampling to reduce points
            step = len(points) // max_points
            simplified = [points[i] for i in range(0, len(points), step)]
            
            # Ensure we don't go below minimum
            if len(simplified) < min_points and len(points) >= min_points:
                step = len(points) // min_points
                simplified = [points[i] for i in range(0, len(points), step)]
            
            # Ensure we have exactly the target number or close to it
            if len(simplified) > max_points:
                simplified = simplified[:max_points]
            
            return simplified
            
        except:
            return points[:max_points]
    
    def apply_per_joint_transforms(self, curve_points, association):
        """Apply per-joint position offset and rotation to curve points"""
        try:
            # Get transformation values
            offset_x = association.curve_offset_x
            offset_y = association.curve_offset_y
            offset_z = association.curve_offset_z
            rot_x = association.curve_rotation_x
            rot_y = association.curve_rotation_y
            rot_z = association.curve_rotation_z
            
            # If no transformations, return original points
            if (offset_x == 0 and offset_y == 0 and offset_z == 0 and 
                rot_x == 0 and rot_y == 0 and rot_z == 0):
                return curve_points
            
            transformed_points = []
            
            # Find curve center for rotation
            curve_center = self.calculate_mesh_center(curve_points)
            
            print("Applying per-joint transforms: offset=({0:.2f}, {1:.2f}, {2:.2f}), rotation=({3:.1f}, {4:.1f}, {5:.1f})".format(
                offset_x, offset_y, offset_z, rot_x, rot_y, rot_z))
            
            for point in curve_points:
                # Start with original point
                new_point = list(point)
                
                # Apply rotation around curve center if any rotation is specified
                if rot_x != 0 or rot_y != 0 or rot_z != 0:
                    # Translate to origin (relative to curve center)
                    relative_point = [
                        point[0] - curve_center[0],
                        point[1] - curve_center[1],
                        point[2] - curve_center[2]
                    ]
                    
                    # Apply rotations (in degrees, convert to radians)
                    import math
                    
                    # Apply X rotation
                    if rot_x != 0:
                        angle_rad = math.radians(rot_x)
                        cos_a = math.cos(angle_rad)
                        sin_a = math.sin(angle_rad)
                        y = relative_point[1] * cos_a - relative_point[2] * sin_a
                        z = relative_point[1] * sin_a + relative_point[2] * cos_a
                        relative_point[1] = y
                        relative_point[2] = z
                    
                    # Apply Y rotation
                    if rot_y != 0:
                        angle_rad = math.radians(rot_y)
                        cos_a = math.cos(angle_rad)
                        sin_a = math.sin(angle_rad)
                        x = relative_point[0] * cos_a + relative_point[2] * sin_a
                        z = -relative_point[0] * sin_a + relative_point[2] * cos_a
                        relative_point[0] = x
                        relative_point[2] = z
                    
                    # Apply Z rotation
                    if rot_z != 0:
                        angle_rad = math.radians(rot_z)
                        cos_a = math.cos(angle_rad)
                        sin_a = math.sin(angle_rad)
                        x = relative_point[0] * cos_a - relative_point[1] * sin_a
                        y = relative_point[0] * sin_a + relative_point[1] * cos_a
                        relative_point[0] = x
                        relative_point[1] = y
                    
                    # Translate back from curve center
                    new_point = [
                        relative_point[0] + curve_center[0],
                        relative_point[1] + curve_center[1],
                        relative_point[2] + curve_center[2]
                    ]
                
                # Apply position offset
                new_point[0] += offset_x
                new_point[1] += offset_y
                new_point[2] += offset_z
                
                transformed_points.append(new_point)
            
            return transformed_points
            
        except Exception as e:
            print("Error applying per-joint transforms: {0}".format(str(e)))
            return curve_points
    
    def apply_per_joint_transforms_to_curve(self, curve, association):
        """Apply per-joint transformations to an existing curve object using Maya transforms"""
        try:
            # Get transformation values
            offset_x = association.curve_offset_x
            offset_y = association.curve_offset_y
            offset_z = association.curve_offset_z
            rot_x = association.curve_rotation_x
            rot_y = association.curve_rotation_y
            rot_z = association.curve_rotation_z
            
            # If no transformations, return
            if (offset_x == 0 and offset_y == 0 and offset_z == 0 and 
                rot_x == 0 and rot_y == 0 and rot_z == 0):
                return
            
            if not cmds.objExists(curve):
                return
            
            print("Applying per-joint transforms to curve: {0}".format(curve))
            print("Transforms: offset=({0:.2f}, {1:.2f}, {2:.2f}), rotation=({3:.1f}, {4:.1f}, {5:.1f})".format(
                offset_x, offset_y, offset_z, rot_x, rot_y, rot_z))
            
            # Apply rotations first (around current position)
            if rot_x != 0 or rot_y != 0 or rot_z != 0:
                # Get current position for rotation center
                current_pos = cmds.xform(curve, query=True, worldSpace=True, translation=True)
                
                # Apply rotations around the control's current center
                if rot_x != 0:
                    cmds.rotate(rot_x, 0, 0, curve, relative=True, pivot=current_pos)
                if rot_y != 0:
                    cmds.rotate(0, rot_y, 0, curve, relative=True, pivot=current_pos)
                if rot_z != 0:
                    cmds.rotate(0, 0, rot_z, curve, relative=True, pivot=current_pos)
            
            # Apply position offset (after rotation)
            if offset_x != 0 or offset_y != 0 or offset_z != 0:
                cmds.move(offset_x, offset_y, offset_z, curve, relative=True, worldSpace=True)
                
        except Exception as e:
            print("Error applying per-joint transforms to curve: {0}".format(str(e)))
    
    def sample_mesh_boundary_smart(self, vertices):
        """Smart mesh boundary sampling using geometry analysis and surface normals simulation"""
        if len(vertices) < 4:
            return None
        
        try:
            # Step 1: Analyze mesh geometry to determine primary orientation
            mesh_analysis = self.analyze_mesh_geometry(vertices)
            if not mesh_analysis:
                return None
            
            # Step 2: Sample boundary points using the mesh's natural orientation
            boundary_points = self.extract_boundary_points(vertices, mesh_analysis)
            
            if not boundary_points or len(boundary_points) < 3:
                return None
            
            print("Smart sampling generated {0} boundary points".format(len(boundary_points)))
            return boundary_points
            
        except Exception as e:
            print("Error in smart mesh sampling: {0}".format(str(e)))
            return None
    
    def analyze_mesh_geometry(self, vertices):
        """Analyze mesh geometry to determine orientation and shape characteristics"""
        try:
            # Calculate mesh center and bounds
            center = self.calculate_mesh_center(vertices)
            
            min_x = min(v[0] for v in vertices)
            max_x = max(v[0] for v in vertices)
            min_y = min(v[1] for v in vertices)
            max_y = max(v[1] for v in vertices)
            min_z = min(v[2] for v in vertices)
            max_z = max(v[2] for v in vertices)
            
            dimensions = {
                'x': max_x - min_x,
                'y': max_y - min_y,
                'z': max_z - min_z
            }
            
            # Find the dominant (longest) and secondary axes
            sorted_dims = sorted(dimensions.items(), key=lambda x: x[1], reverse=True)
            primary_axis = sorted_dims[0][0]
            secondary_axis = sorted_dims[1][0]
            tertiary_axis = sorted_dims[2][0]
            
            # Calculate how elongated the mesh is
            elongation_ratio = sorted_dims[0][1] / max(sorted_dims[1][1], 0.001)
            
            print("Mesh analysis - Primary: {0}, Secondary: {1}, Elongation: {2:.2f}".format(
                primary_axis, secondary_axis, elongation_ratio))
            
            # Determine the best viewing plane based on mesh shape
            if elongation_ratio > 2.0:
                # Highly elongated mesh (like magazine, trigger, etc.)
                viewing_plane = self.get_elongated_mesh_plane(primary_axis, secondary_axis)
            else:
                # More cubic mesh - use the plane that shows most detail
                viewing_plane = self.get_cubic_mesh_plane(dimensions)
            
            return {
                'center': center,
                'dimensions': dimensions,
                'primary_axis': primary_axis,
                'secondary_axis': secondary_axis,
                'tertiary_axis': tertiary_axis,
                'viewing_plane': viewing_plane,
                'elongation_ratio': elongation_ratio,
                'bounds': {
                    'min_x': min_x, 'max_x': max_x,
                    'min_y': min_y, 'max_y': max_y,
                    'min_z': min_z, 'max_z': max_z
                }
            }
            
        except Exception as e:
            print("Error analyzing mesh geometry: {0}".format(str(e)))
            return None
    
    def get_elongated_mesh_plane(self, primary_axis, secondary_axis):
        """Determine the best viewing plane for elongated meshes"""
        # For elongated meshes, we want to view from the side that shows the length
        if primary_axis == 'x':
            if secondary_axis == 'y':
                return 'xy'  # View from Z (shows X-Y length/height)
            else:
                return 'xz'  # View from Y (shows X-Z length/depth)
        elif primary_axis == 'y':
            if secondary_axis == 'x':
                return 'xy'  # View from Z (shows X-Y width/height)
            else:
                return 'yz'  # View from X (shows Y-Z height/depth)
        else:  # primary_axis == 'z'
            if secondary_axis == 'x':
                return 'xz'  # View from Y (shows X-Z width/depth)
            else:
                return 'yz'  # View from X (shows Y-Z height/depth)
    
    def get_cubic_mesh_plane(self, dimensions):
        """Determine the best viewing plane for more cubic meshes"""
        # For cubic meshes, choose the plane that shows the most area
        xy_area = dimensions['x'] * dimensions['y']
        xz_area = dimensions['x'] * dimensions['z']
        yz_area = dimensions['y'] * dimensions['z']
        
        if xy_area >= xz_area and xy_area >= yz_area:
            return 'xy'
        elif xz_area >= xy_area and xz_area >= yz_area:
            return 'xz'
        else:
            return 'yz'
    
    def extract_boundary_points(self, vertices, mesh_analysis):
        """Extract boundary points using the determined viewing plane and mesh characteristics"""
        try:
            viewing_plane = mesh_analysis['viewing_plane']
            center = mesh_analysis['center']
            
            print("Using viewing plane: {0}".format(viewing_plane))
            
            # Project vertices to the determined plane
            if viewing_plane == 'xy':
                projected_points = [(v[0], v[1]) for v in vertices]
                constant_coord = center[2]
                coord_indices = (0, 1, 2)  # x, y, constant_z
            elif viewing_plane == 'xz':
                projected_points = [(v[0], v[2]) for v in vertices]
                constant_coord = center[1]
                coord_indices = (0, 2, 1)  # x, z, constant_y
            else:  # 'yz'
                projected_points = [(v[1], v[2]) for v in vertices]
                constant_coord = center[0]
                coord_indices = (1, 2, 0)  # y, z, constant_x
            
            # Find the convex hull in 2D
            hull_points_2d = self.convex_hull_2d(projected_points)
            
            if len(hull_points_2d) < 3:
                return None
            
            # Convert back to 3D coordinates
            boundary_3d = []
            for point_2d in hull_points_2d:
                if viewing_plane == 'xy':
                    point_3d = [point_2d[0], point_2d[1], constant_coord]
                elif viewing_plane == 'xz':
                    point_3d = [point_2d[0], constant_coord, point_2d[1]]
                else:  # 'yz'
                    point_3d = [constant_coord, point_2d[0], point_2d[1]]
                
                boundary_3d.append(point_3d)
            
            # Enhance boundary with mesh-specific adjustments
            enhanced_boundary = self.enhance_boundary_for_mesh_type(boundary_3d, mesh_analysis)
            
            return enhanced_boundary
            
        except Exception as e:
            print("Error extracting boundary points: {0}".format(str(e)))
            return None
    
    def enhance_boundary_for_mesh_type(self, boundary_points, mesh_analysis):
        """Enhance boundary points based on mesh characteristics"""
        try:
            elongation_ratio = mesh_analysis['elongation_ratio']
            primary_axis = mesh_analysis['primary_axis']
            
            if elongation_ratio > 3.0:
                # Very elongated mesh - likely a magazine, trigger, barrel, etc.
                return self.enhance_elongated_boundary(boundary_points, mesh_analysis)
            elif elongation_ratio > 1.5:
                # Moderately elongated - might be a receiver, stock, etc.
                return self.enhance_moderate_boundary(boundary_points, mesh_analysis)
            else:
                # More cubic - bullet, bolt, small parts
                return self.enhance_cubic_boundary(boundary_points, mesh_analysis)
                
        except Exception as e:
            print("Error enhancing boundary: {0}".format(str(e)))
            return boundary_points
    
    def enhance_elongated_boundary(self, boundary_points, mesh_analysis):
        """Enhance boundary for elongated meshes (magazines, triggers, barrels)"""
        # For elongated meshes, we want to emphasize the length
        center = mesh_analysis['center']
        primary_axis = mesh_analysis['primary_axis']
        
        # Extend the boundary slightly along the primary axis to better represent the mesh
        enhanced_points = []
        for point in boundary_points:
            enhanced_point = point[:]
            
            # Slightly exaggerate the primary dimension
            axis_index = {'x': 0, 'y': 1, 'z': 2}[primary_axis]
            direction = 1 if point[axis_index] > center[axis_index] else -1
            enhanced_point[axis_index] += direction * 0.1  # Small extension
            
            enhanced_points.append(enhanced_point)
        
        return enhanced_points
    
    def enhance_moderate_boundary(self, boundary_points, mesh_analysis):
        """Enhance boundary for moderately elongated meshes"""
        # For moderate meshes, just ensure good representation
        return boundary_points
    
    def enhance_cubic_boundary(self, boundary_points, mesh_analysis):
        """Enhance boundary for cubic meshes (bullets, small parts)"""
        # For cubic meshes, we might want to make the curve slightly more circular
        center = mesh_analysis['center']
        
        # Calculate average distance from center
        distances = []
        for point in boundary_points:
            dist = sum((point[i] - center[i])**2 for i in range(3))**0.5
            distances.append(dist)
        
        avg_distance = sum(distances) / len(distances)
        
        # Normalize distances to make shape more regular
        enhanced_points = []
        for i, point in enumerate(boundary_points):
            direction = [point[j] - center[j] for j in range(3)]
            length = sum(d**2 for d in direction)**0.5
            
            if length > 0:
                # Normalize direction and apply average distance
                factor = avg_distance * 0.9 / length  # Slightly smaller for better fit
                enhanced_point = [
                    center[j] + direction[j] * factor
                    for j in range(3)
                ]
                enhanced_points.append(enhanced_point)
            else:
                enhanced_points.append(point)
        
        return enhanced_points
    
    def generate_outline_by_projection_fallback(self, vertices, scale_multiplier):
        """Fallback method using the original projection approach"""
        try:
            # Find the bounding box center
            min_x = min(v[0] for v in vertices)
            max_x = max(v[0] for v in vertices)
            min_y = min(v[1] for v in vertices)
            max_y = max(v[1] for v in vertices)
            min_z = min(v[2] for v in vertices)
            max_z = max(v[2] for v in vertices)
            
            center = [(min_x + max_x) / 2, (min_y + max_y) / 2, (min_z + max_z) / 2]
            
            # Determine the primary orientation plane
            width = max_x - min_x
            height = max_y - min_y
            depth = max_z - min_z
            
            # Create outline points based on the largest dimensions
            if width >= height and width >= depth:
                # X-Z plane (looking down Y axis)
                outline_points = self.create_outline_points_xz(vertices, center, scale_multiplier)
            elif height >= width and height >= depth:
                # X-Y plane (looking down Z axis) 
                outline_points = self.create_outline_points_xy(vertices, center, scale_multiplier)
            else:
                # Y-Z plane (looking down X axis)
                outline_points = self.create_outline_points_yz(vertices, center, scale_multiplier)
            
            return outline_points
            
        except Exception as e:
            print("Error in fallback projection: {0}".format(str(e)))
            return None
    
    def align_curve_to_mesh_orientation(self, curve_points, mesh_vertices, joint_pos):
        """Align curve points to match mesh orientation using PCA"""
        if len(mesh_vertices) < 3 or len(curve_points) < 3:
            return curve_points
        
        try:
            # Calculate mesh orientation using Principal Component Analysis (PCA)
            mesh_orientation = self.calculate_mesh_orientation(mesh_vertices)
            
            if mesh_orientation is None:
                return curve_points
            
            # Apply rotation to curve points
            rotated_points = []
            for point in curve_points:
                rotated_point = self.rotate_point_by_matrix(point, mesh_orientation)
                rotated_points.append(rotated_point)
            
            return rotated_points
            
        except Exception as e:
            print("Warning: Could not align curve orientation: {0}".format(str(e)))
            return curve_points
    
    def calculate_mesh_orientation(self, vertices):
        """Calculate mesh orientation using simplified PCA"""
        if len(vertices) < 3:
            return None
        
        try:
            # Calculate centroid
            centroid = self.calculate_mesh_center(vertices)
            
            # Center the vertices
            centered_vertices = []
            for v in vertices:
                centered_vertices.append([
                    v[0] - centroid[0],
                    v[1] - centroid[1],
                    v[2] - centroid[2]
                ])
            
            # Calculate covariance matrix (simplified)
            cov_xx = sum(v[0] * v[0] for v in centered_vertices) / len(centered_vertices)
            cov_yy = sum(v[1] * v[1] for v in centered_vertices) / len(centered_vertices)
            cov_zz = sum(v[2] * v[2] for v in centered_vertices) / len(centered_vertices)
            cov_xy = sum(v[0] * v[1] for v in centered_vertices) / len(centered_vertices)
            cov_xz = sum(v[0] * v[2] for v in centered_vertices) / len(centered_vertices)
            cov_yz = sum(v[1] * v[2] for v in centered_vertices) / len(centered_vertices)
            
            # Find dominant axes by comparing variances
            variances = [cov_xx, cov_yy, cov_zz]
            max_var_idx = variances.index(max(variances))
            
            # Create a simple rotation matrix based on dominant axis
            if max_var_idx == 0:  # X dominant
                # Check if mesh is more aligned with Y-Z plane
                if abs(cov_xy) > abs(cov_xz):
                    # Rotate around Z to align with X-Y
                    angle = self.calculate_rotation_angle(cov_xy, cov_xx - cov_yy)
                    return self.create_rotation_matrix_z(angle)
                else:
                    # Rotate around Y to align with X-Z  
                    angle = self.calculate_rotation_angle(cov_xz, cov_xx - cov_zz)
                    return self.create_rotation_matrix_y(angle)
            elif max_var_idx == 1:  # Y dominant
                # Rotate around Z to align with X-Y
                angle = self.calculate_rotation_angle(cov_xy, cov_yy - cov_xx)
                return self.create_rotation_matrix_z(-angle)
            else:  # Z dominant
                # Rotate around Y to align with X-Z
                angle = self.calculate_rotation_angle(cov_xz, cov_zz - cov_xx)
                return self.create_rotation_matrix_y(-angle)
                
        except Exception as e:
            print("Error calculating mesh orientation: {0}".format(str(e)))
            return None
    
    def calculate_rotation_angle(self, cov_ab, cov_diff):
        """Calculate rotation angle from covariance values"""
        import math
        if abs(cov_diff) < 0.0001:
            return 0.0
        return 0.5 * math.atan2(2.0 * cov_ab, cov_diff)
    
    def create_rotation_matrix_y(self, angle):
        """Create rotation matrix around Y axis"""
        import math
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        return [
            [cos_a, 0, sin_a],
            [0, 1, 0],
            [-sin_a, 0, cos_a]
        ]
    
    def create_rotation_matrix_z(self, angle):
        """Create rotation matrix around Z axis"""
        import math
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        return [
            [cos_a, -sin_a, 0],
            [sin_a, cos_a, 0],
            [0, 0, 1]
        ]
    
    def rotate_point_by_matrix(self, point, rotation_matrix):
        """Rotate a 3D point using a rotation matrix"""
        if not rotation_matrix or len(rotation_matrix) != 3:
            return point
            
        try:
            x = (rotation_matrix[0][0] * point[0] + 
                 rotation_matrix[0][1] * point[1] + 
                 rotation_matrix[0][2] * point[2])
            y = (rotation_matrix[1][0] * point[0] + 
                 rotation_matrix[1][1] * point[1] + 
                 rotation_matrix[1][2] * point[2])
            z = (rotation_matrix[2][0] * point[0] + 
                 rotation_matrix[2][1] * point[1] + 
                 rotation_matrix[2][2] * point[2])
            
            return [x, y, z]
        except:
            return point
    
    def get_mesh_vertices_world_space(self, mesh_obj):
        """Get all vertices of a mesh in world space"""
        try:
            # Get all vertices
            vertex_count = cmds.polyEvaluate(mesh_obj, vertex=True)
            if not vertex_count:
                return []
            
            vertices = []
            for i in range(vertex_count):
                vertex_name = "{0}.vtx[{1}]".format(mesh_obj, i)
                world_pos = cmds.xform(vertex_name, query=True, worldSpace=True, translation=True)
                vertices.append(world_pos)
            
            return vertices
            
        except Exception as e:
            print("Error getting vertices for {0}: {1}".format(mesh_obj, str(e)))
            return []
    
    def generate_control_points_from_vertices(self, vertices, scale_multiplier):
        """Generate control curve points by sampling mesh geometry and analyzing surface normals"""
        if len(vertices) < 3:
            return None
        
        try:
            # Use the new mesh-aware sampling approach
            outline_points = self.sample_mesh_boundary_smart(vertices)
            
            if not outline_points:
                print("Smart sampling failed, falling back to projection method")
                # Fallback to original projection method
                outline_points = self.generate_outline_by_projection_fallback(vertices, scale_multiplier)
            
            if not outline_points:
                print("No outline points generated")
                return None
            
            # Apply scale multiplier to final points
            if scale_multiplier != 1.0:
                center = self.calculate_mesh_center(outline_points)
                scaled_points = []
                for point in outline_points:
                    scaled_point = [
                        center[0] + (point[0] - center[0]) * scale_multiplier,
                        center[1] + (point[1] - center[1]) * scale_multiplier,
                        center[2] + (point[2] - center[2]) * scale_multiplier
                    ]
                    scaled_points.append(scaled_point)
                outline_points = scaled_points
            
            # Simplify the outline to reduce control points
            simplified_points = self.simplify_outline_points(outline_points, 8, 16)  # 8-16 points max
            
            print("Generated {0} outline points using smart mesh sampling".format(len(simplified_points) if simplified_points else 0))
            return simplified_points
            
        except Exception as e:
            print("Error generating control points: {0}".format(str(e)))
            return None
    
    def create_outline_points_xz(self, vertices, center, scale_multiplier):
        """Create outline points in X-Z plane"""
        # Project vertices to X-Z plane and find outline
        projected = [(v[0], v[2]) for v in vertices]
        
        # Use convex hull to find outline
        hull_points = self.convex_hull_2d(projected)
        
        # Convert back to 3D with center Y
        outline_3d = [(p[0], center[1], p[1]) for p in hull_points]
        
        # Scale around center
        scaled_outline = []
        for point in outline_3d:
            scaled_point = [
                center[0] + (point[0] - center[0]) * scale_multiplier,
                point[1],  # Keep Y at center
                center[2] + (point[2] - center[2]) * scale_multiplier
            ]
            scaled_outline.append(scaled_point)
        
        return scaled_outline
    
    def create_outline_points_xy(self, vertices, center, scale_multiplier):
        """Create outline points in X-Y plane"""
        # Project vertices to X-Y plane and find outline
        projected = [(v[0], v[1]) for v in vertices]
        
        # Use convex hull to find outline
        hull_points = self.convex_hull_2d(projected)
        
        # Convert back to 3D with center Z
        outline_3d = [(p[0], p[1], center[2]) for p in hull_points]
        
        # Scale around center
        scaled_outline = []
        for point in outline_3d:
            scaled_point = [
                center[0] + (point[0] - center[0]) * scale_multiplier,
                center[1] + (point[1] - center[1]) * scale_multiplier,
                point[2]  # Keep Z at center
            ]
            scaled_outline.append(scaled_point)
        
        return scaled_outline
    
    def create_outline_points_yz(self, vertices, center, scale_multiplier):
        """Create outline points in Y-Z plane"""
        # Project vertices to Y-Z plane and find outline
        projected = [(v[1], v[2]) for v in vertices]
        
        # Use convex hull to find outline
        hull_points = self.convex_hull_2d(projected)
        
        # Convert back to 3D with center X
        outline_3d = [(center[0], p[0], p[1]) for p in hull_points]
        
        # Scale around center
        scaled_outline = []
        for point in outline_3d:
            scaled_point = [
                point[0],  # Keep X at center
                center[1] + (point[1] - center[1]) * scale_multiplier,
                center[2] + (point[2] - center[2]) * scale_multiplier
            ]
            scaled_outline.append(scaled_point)
        
        return scaled_outline
    
    def convex_hull_2d(self, points):
        """Calculate 2D convex hull using Graham scan algorithm"""
        if len(points) < 3:
            return points
        
        # Remove duplicates
        unique_points = list(set(points))
        if len(unique_points) < 3:
            return unique_points
        
        # Find the bottom-most point (and leftmost in case of tie)
        start = min(unique_points, key=lambda p: (p[1], p[0]))
        
        # Sort points by polar angle with respect to start point
        def polar_angle(p):
            import math
            dx = p[0] - start[0]
            dy = p[1] - start[1]
            return math.atan2(dy, dx)
        
        sorted_points = sorted([p for p in unique_points if p != start], key=polar_angle)
        
        # Graham scan
        hull = [start]
        
        for point in sorted_points:
            # Remove points that would create a right turn
            while len(hull) >= 2 and self.cross_product_2d(hull[-2], hull[-1], point) <= 0:
                hull.pop()
            hull.append(point)
        
        return hull
    
    def cross_product_2d(self, o, a, b):
        """Calculate cross product for 2D points"""
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    
    def simplify_outline_points(self, points, min_points, max_points):
        """Simplify outline points to reduce control point count"""
        if not points or len(points) <= min_points:
            return points
        
        if len(points) <= max_points:
            return points
        
        # Use Douglas-Peucker algorithm to simplify
        simplified = self.douglas_peucker_3d(points, tolerance=0.1)
        
        # If still too many points, sample evenly
        if len(simplified) > max_points:
            step = len(simplified) // max_points
            simplified = [simplified[i] for i in range(0, len(simplified), step)]
            if len(simplified) > max_points:
                simplified = simplified[:max_points]
        
        # Ensure minimum points
        if len(simplified) < min_points:
            # Sample evenly to get minimum points
            if len(points) >= min_points:
                step = len(points) // min_points
                simplified = [points[i] for i in range(0, len(points), step)][:min_points]
            else:
                simplified = points
        
        return simplified
    
    def douglas_peucker_3d(self, points, tolerance):
        """Douglas-Peucker line simplification algorithm for 3D points"""
        if len(points) <= 2:
            return points
        
        # Find the point with maximum distance from line between first and last
        max_distance = 0
        max_index = 0
        
        for i in range(1, len(points) - 1):
            distance = self.point_to_line_distance_3d(points[i], points[0], points[-1])
            if distance > max_distance:
                max_distance = distance
                max_index = i
        
        # If maximum distance is greater than tolerance, recursively simplify
        if max_distance > tolerance:
            # Recursive call on both parts
            left_part = self.douglas_peucker_3d(points[:max_index + 1], tolerance)
            right_part = self.douglas_peucker_3d(points[max_index:], tolerance)
            
            # Combine results (remove duplicate point at junction)
            return left_part[:-1] + right_part
        else:
            # All points are close to the line, return endpoints
            return [points[0], points[-1]]
    
    def point_to_line_distance_3d(self, point, line_start, line_end):
        """Calculate distance from a 3D point to a 3D line"""
        import math
        
        # Vector from line_start to line_end
        line_vec = [line_end[i] - line_start[i] for i in range(3)]
        
        # Vector from line_start to point
        point_vec = [point[i] - line_start[i] for i in range(3)]
        
        # Calculate line length
        line_length = math.sqrt(sum(v*v for v in line_vec))
        
        if line_length == 0:
            # Line is a point, return distance to that point
            return math.sqrt(sum((point[i] - line_start[i])**2 for i in range(3)))
        
        # Normalize line vector
        line_unit = [v / line_length for v in line_vec]
        
        # Project point vector onto line
        projection_length = sum(point_vec[i] * line_unit[i] for i in range(3))
        
        # Find closest point on line
        if projection_length <= 0:
            closest = line_start
        elif projection_length >= line_length:
            closest = line_end
        else:
            closest = [line_start[i] + projection_length * line_unit[i] for i in range(3)]
        
        # Calculate distance from point to closest point on line
        return math.sqrt(sum((point[i] - closest[i])**2 for i in range(3)))
    
    def create_basic_control_shape(self, name, shape_type, final_scale, association=None):
        """Create a basic control shape with mesh-aware sizing"""
        if shape_type == "box":
            # Calculate rectangular prism dimensions to contain the mesh
            if association and association.mesh_objects:
                # Get all vertices from associated meshes
                all_vertices = []
                for mesh_obj in association.mesh_objects:
                    if cmds.objExists(mesh_obj):
                        vertices = self.get_mesh_vertices_world_space(mesh_obj)
                        if vertices:
                            all_vertices.extend(vertices)
                
                if all_vertices:
                    # Calculate bounding box dimensions
                    min_x = min(v[0] for v in all_vertices)
                    max_x = max(v[0] for v in all_vertices)
                    min_y = min(v[1] for v in all_vertices)
                    max_y = max(v[1] for v in all_vertices)
                    min_z = min(v[2] for v in all_vertices)
                    max_z = max(v[2] for v in all_vertices)
                    
                    # Calculate individual dimensions for rectangular prism
                    box_width = (max_x - min_x) * 0.6 * final_scale   # X dimension
                    box_height = (max_y - min_y) * 0.6 * final_scale  # Y dimension  
                    box_depth = (max_z - min_z) * 0.6 * final_scale   # Z dimension
                    
                    # Apply minimum sizes to ensure visibility
                    box_width = max(box_width, final_scale * 0.3)
                    box_height = max(box_height, final_scale * 0.3)
                    box_depth = max(box_depth, final_scale * 0.3)
                    
                    print("Rectangular prism dimensions calculated: {0:.2f} x {1:.2f} x {2:.2f} (from mesh: {3:.2f} x {4:.2f} x {5:.2f})".format(
                        box_width, box_height, box_depth, max_x - min_x, max_y - min_y, max_z - min_z))
                else:
                    # Fallback to uniform dimensions
                    box_width = box_height = box_depth = final_scale
            else:
                # Fallback to uniform dimensions
                box_width = box_height = box_depth = final_scale
            
            # Create rectangular prism control with calculated dimensions
            points = [
                [-box_width, -box_height, -box_depth], [box_width, -box_height, -box_depth],
                [box_width, box_height, -box_depth], [-box_width, box_height, -box_depth],
                [-box_width, -box_height, -box_depth], [-box_width, -box_height, box_depth],
                [box_width, -box_height, box_depth], [box_width, box_height, box_depth],
                [-box_width, box_height, box_depth], [-box_width, -box_height, box_depth],
                [box_width, -box_height, box_depth], [box_width, -box_height, -box_depth],
                [box_width, box_height, -box_depth], [box_width, box_height, box_depth],
                [-box_width, box_height, box_depth], [-box_width, box_height, -box_depth]
            ]
            # Create rectangular prism as degree 1 (linear) since it should have sharp corners
            control = cmds.curve(name=name, degree=1, point=points)
            
        elif shape_type == "cylinder":
            # Calculate cylinder radius to contain the mesh  
            if association and association.mesh_objects:
                # Get all vertices from associated meshes
                all_vertices = []
                for mesh_obj in association.mesh_objects:
                    if cmds.objExists(mesh_obj):
                        vertices = self.get_mesh_vertices_world_space(mesh_obj)
                        if vertices:
                            all_vertices.extend(vertices)
                
                if all_vertices:
                    # Calculate mesh center and maximum distance
                    center = self.calculate_mesh_center(all_vertices)
                    max_distance = 0
                    for vertex in all_vertices:
                        # Calculate XZ distance from center (ignore Y for cylinder)
                        distance = ((vertex[0] - center[0])**2 + (vertex[2] - center[2])**2)**0.5
                        max_distance = max(max_distance, distance)
                    
                    cylinder_radius = max_distance * 0.7 * final_scale  # 70% of max distance
                    cylinder_radius = max(cylinder_radius, final_scale * 0.3)  # At least 30% of scale
                    
                    print("Cylinder radius calculated: {0} (from max distance: {1:.2f})".format(
                        cylinder_radius, max_distance))
                else:
                    cylinder_radius = final_scale
            else:
                cylinder_radius = final_scale
            
            # Create circle control (represents cylinder cross-section)
            control = cmds.circle(name=name, constructionHistory=False, normal=[0, 1, 0], radius=cylinder_radius)[0]
            
        elif shape_type == "sphere":
            # Calculate sphere radius to contain the mesh
            if association and association.mesh_objects:
                # Get all vertices from associated meshes
                all_vertices = []
                for mesh_obj in association.mesh_objects:
                    if cmds.objExists(mesh_obj):
                        vertices = self.get_mesh_vertices_world_space(mesh_obj)
                        if vertices:
                            all_vertices.extend(vertices)
                
                if all_vertices:
                    # Calculate mesh center and maximum distance
                    center = self.calculate_mesh_center(all_vertices)
                    max_distance = 0
                    for vertex in all_vertices:
                        # Calculate 3D distance from center
                        distance = ((vertex[0] - center[0])**2 + (vertex[1] - center[1])**2 + (vertex[2] - center[2])**2)**0.5
                        max_distance = max(max_distance, distance)
                    
                    sphere_radius = max_distance * 0.8 * final_scale  # 80% of max distance  
                    sphere_radius = max(sphere_radius, final_scale * 0.3)  # At least 30% of scale
                    
                    print("Sphere radius calculated: {0} (from max distance: {1:.2f})".format(
                        sphere_radius, max_distance))
                else:
                    sphere_radius = final_scale
            else:
                sphere_radius = final_scale
            
            # Create sphere control (3 intersecting circles)
            # Create main circle
            control = cmds.circle(name=name, constructionHistory=False, normal=[0, 1, 0], radius=sphere_radius)[0]
            
            # Create two additional circles for sphere representation
            circle2 = cmds.circle(constructionHistory=False, normal=[1, 0, 0], radius=sphere_radius)[0]
            circle3 = cmds.circle(constructionHistory=False, normal=[0, 0, 1], radius=sphere_radius)[0]
            
            # Combine the shapes
            shapes2 = cmds.listRelatives(circle2, shapes=True)
            shapes3 = cmds.listRelatives(circle3, shapes=True)
            
            if shapes2:
                cmds.parent(shapes2, control, relative=True, shape=True)
            if shapes3:
                cmds.parent(shapes3, control, relative=True, shape=True)
            
            # Delete the temporary transforms
            cmds.delete(circle2, circle3)
            
        else:
            # Default: simple circle (uses final_scale as-is)
            control = cmds.circle(name=name, constructionHistory=False, radius=final_scale)[0]
        
        return control
    
    def create_rig_hierarchy(self):
        """Create organized hierarchy for the weapon rig"""
        # Create main rig group
        rig_group_name = "S2_WeaponRig"
        counter = 1
        
        while cmds.objExists(rig_group_name):
            rig_group_name = "S2_WeaponRig_{0:02d}".format(counter)
            counter += 1
        
        rig_group = cmds.group(empty=True, name=rig_group_name)
        
        # Create controls subgroup only
        controls_group = cmds.group(empty=True, name="S2_Controls", parent=rig_group)
        
        # Move controls to controls group (excluding excluded joints)
        all_controls = []
        for association in self.joint_associations:
            if association.has_control and not association.is_excluded and cmds.objExists(association.control_name):
                all_controls.append(association.control_name)
        
        if all_controls:
            try:
                for control in all_controls:
                    # Check if control doesn't already have a parent
                    parent = cmds.listRelatives(control, parent=True)
                    if not parent:
                        cmds.parent(control, controls_group)
            except Exception as e:
                print("Warning: Error organizing controls: {0}".format(str(e)))
        
        # Note: Joints are left in their original hierarchy as requested
        
        self.rig_group = rig_group
        print("Created rig hierarchy: {0}".format(rig_group))
        return rig_group
    
    def freeze_all_control_transforms(self):
        """Freeze transforms on all control curves before constraining"""
        print("\n=== FREEZING CONTROL TRANSFORMS ===")
        
        frozen_count = 0
        failed_count = 0
        
        for association in self.joint_associations:
            if (association.has_control and not association.is_excluded and 
                cmds.objExists(association.control_name)):
                try:
                    # Store the current pivot position
                    pivot_pos = cmds.xform(association.control_name, query=True, worldSpace=True, rotatePivot=True)
                    
                    # Freeze transforms while preserving the pivot
                    cmds.makeIdentity(association.control_name, apply=True, translate=True, rotate=True, scale=True, normal=False, preserveNormals=True)
                    
                    # Restore the original pivot position
                    cmds.xform(association.control_name, worldSpace=True, rotatePivot=pivot_pos)
                    cmds.xform(association.control_name, worldSpace=True, scalePivot=pivot_pos)
                    
                    frozen_count += 1
                    print("Froze transforms for control: {0} (pivot preserved)".format(association.control_name))
                    
                except Exception as e:
                    print("Warning: Could not freeze transforms for {0}: {1}".format(association.control_name, str(e)))
                    failed_count += 1
        
        print("Froze transforms on {0} controls ({1} failed)".format(frozen_count, failed_count))
        return frozen_count

    def setup_rig_constraints(self):
        """Set up constraints from joints to controls"""
        print("\n=== SETTING UP RIG CONSTRAINTS ===")
        
        constraint_count = 0
        
        for association in self.joint_associations:
            if (association.has_control and not association.is_excluded and 
                cmds.objExists(association.control_name) and cmds.objExists(association.joint_name)):
                try:
                    # Using parent constraint (handles both position and rotation) and scale constraint
                    # instead of separate point and orient constraints
                    parent_constraint = cmds.parentConstraint(association.control_name, association.joint_name, maintainOffset=True)[0]
                    scale_constraint = cmds.scaleConstraint(association.control_name, association.joint_name, maintainOffset=True)[0]
                    
                    constraint_count += 2
                    print("Constrained joint '{0}' to control '{1}' using parent and scale constraints".format(
                        association.joint_name, association.control_name))
                    
                except Exception as e:
                    print("Warning: Could not constrain joint '{0}' to control '{1}': {2}".format(
                        association.joint_name, association.control_name, str(e)))
        
        print("Created {0} constraints for rig".format(constraint_count))
        return constraint_count
    
    def setup_attachment_attributes(self, rig_group):
        """Set up two-tier attachment switching attributes: Category -> Display Name"""
        print("\n=== SETTING UP ATTACHMENT ATTRIBUTES (Two-Tier System) ===")
        
        if not self.attachments_by_joint:
            print("No attachments found, skipping attribute setup")
            return
        
        # Find joints that have both default meshes and attachments
        joints_with_attachments = {}
        
        for joint_name, attachments in self.attachments_by_joint.items():
            # Check if this joint also has default mesh associations
            has_default_mesh = any(assoc.joint_name == joint_name for assoc in self.joint_associations)
            
            if has_default_mesh and attachments:
                joints_with_attachments[joint_name] = attachments
                print("Joint '{0}' has {1} attachment(s) available for switching".format(
                    joint_name, len(attachments)))
        
        if not joints_with_attachments:
            print("No joints found with both default meshes and attachments")
            return
        
        # Group attachments by category first, then by display name within category
        attachments_by_category = {}  # {category: {display_name: [(joint_name, attachment_obj), ...]}}
        
        for joint_name, attachments in joints_with_attachments.items():
            attachment_names = self.attachment_names_by_joint.get(joint_name, [])
            attachment_categories = self.attachment_categories_by_joint.get(joint_name, [])
            
            for i, attachment_obj in enumerate(attachments):
                # Get category and display name
                category = attachment_categories[i] if i < len(attachment_categories) else "Uncategorized"
                display_name = attachment_names[i] if i < len(attachment_names) else attachment_obj.split('|')[-1].split(':')[-1]
                
                # Initialize category if needed
                if category not in attachments_by_category:
                    attachments_by_category[category] = {}
                
                # Initialize display name within category if needed
                if display_name not in attachments_by_category[category]:
                    attachments_by_category[category][display_name] = []
                
                attachments_by_category[category][display_name].append((joint_name, attachment_obj))
        
        print("\n--- Grouped Attachments by Category -> Display Name ---")
        for category, display_names in attachments_by_category.items():
            print("Category '{0}':".format(category))
            for display_name, attachment_list in display_names.items():
                joint_names = [joint_name for joint_name, _ in attachment_list]
                print("  Display name '{0}': {1} attachment(s) across joints {2}".format(
                    display_name, len(attachment_list), joint_names))
        
        # Create enum attributes for each category
        for category, display_names in attachments_by_category.items():
            try:
                # Create attribute name from category
                attr_name = self.make_safe_attribute_name(category)
                attr_name = self.make_valid_attribute_name(attr_name, rig_group)
                
                # Create enum values: "Default" + all display names in this category
                unique_display_names = list(display_names.keys())
                enum_values = ["Default"] + unique_display_names
                enum_string = ":".join(enum_values)
                
                # Add the attribute
                cmds.addAttr(rig_group, longName=attr_name, attributeType='enum', enumName=enum_string)
                cmds.setAttr("{0}.{1}".format(rig_group, attr_name), edit=True, keyable=True)
                
                print("Created category attribute '{0}' with options: {1}".format(attr_name, enum_values))
                print("  Category controls {0} unique display name(s)".format(len(unique_display_names)))
                
                # Set up the switching logic for this category
                self.setup_category_attachment_switching(rig_group, attr_name, category, display_names)
                
            except Exception as e:
                print("Error creating category attribute for '{0}': {1}".format(category, str(e)))
        
        print("Two-tier attachment attribute setup complete")
    
    def make_safe_attribute_name(self, display_name):
        """Convert display name to a safe attribute name"""
        # Replace spaces and special characters with underscores
        safe_name = display_name.lower()
        safe_name = ''.join(c if c.isalnum() else '_' for c in safe_name)
        
        # Remove multiple consecutive underscores
        while '__' in safe_name:
            safe_name = safe_name.replace('__', '_')
        
        # Remove leading/trailing underscores
        safe_name = safe_name.strip('_')
        
        # Ensure it doesn't start with a number
        if safe_name and safe_name[0].isdigit():
            safe_name = "attachment_" + safe_name
        
        # Ensure it's not empty
        if not safe_name:
            safe_name = "attachment"
        
        return safe_name
    
    def make_valid_attribute_name(self, desired_name, node):
        """Ensure attribute name is valid and unique"""
        # Replace invalid characters
        valid_name = desired_name.replace('-', '_').replace(' ', '_')
        valid_name = ''.join(c for c in valid_name if c.isalnum() or c == '_')
        
        # Ensure it doesn't start with a number
        if valid_name and valid_name[0].isdigit():
            valid_name = "attr_" + valid_name
        
        # Make unique if it already exists
        original_name = valid_name
        counter = 1
        while cmds.attributeQuery(valid_name, node=node, exists=True):
            valid_name = "{0}_{1}".format(original_name, counter)
            counter += 1
        
        return valid_name
    
    def setup_category_attachment_switching(self, rig_group, attr_name, category, display_names_dict):
        """Set up switching logic for a category with multiple display names"""
        print("  Setting up category switching for '{0}'".format(category))
        
        try:
            attr_full_name = "{0}.{1}".format(rig_group, attr_name)
            
            # Collect all attachments and their default meshes for this category
            all_attachment_data = {}  # {display_name: {'attachments': [(joint, obj)], 'default_meshes': {joint: [meshes]}}}
            affected_joints = set()
            
            for display_name, attachment_list in display_names_dict.items():
                # Group attachments by joint for this display name
                attachments_by_joint = {}
                for joint_name, attachment_obj in attachment_list:
                    if joint_name not in attachments_by_joint:
                        attachments_by_joint[joint_name] = []
                    attachments_by_joint[joint_name].append(attachment_obj)
                    affected_joints.add(joint_name)
                
                # Find default meshes for each joint
                default_meshes_by_joint = {}
                for joint_name in attachments_by_joint.keys():
                    default_meshes = self.find_default_meshes_for_joint(joint_name)
                    if default_meshes:
                        default_meshes_by_joint[joint_name] = default_meshes
                
                all_attachment_data[display_name] = {
                    'attachments_by_joint': attachments_by_joint,
                    'default_meshes_by_joint': default_meshes_by_joint
                }
            
            # Build expression for the entire category
            expression_lines = []
            
            # Get enum index mapping
            display_name_list = list(display_names_dict.keys())
            
            for joint_name in affected_joints:
                # Default case (when attribute = 0): show defaults, hide all attachments
                default_meshes = []
                for display_name, data in all_attachment_data.items():
                    if joint_name in data['default_meshes_by_joint']:
                        default_meshes.extend(data['default_meshes_by_joint'][joint_name])
                
                # Remove duplicates while preserving order
                seen = set()
                unique_default_meshes = []
                for mesh in default_meshes:
                    if mesh not in seen:
                        unique_default_meshes.append(mesh)
                        seen.add(mesh)
                
                for mesh in unique_default_meshes:
                    expression_lines.append("if ({0} == 0) {1}.visibility = 1;".format(attr_full_name, mesh))
                    expression_lines.append("else {0}.visibility = 0;".format(mesh))
                
                # Hide all attachments when default is selected
                for display_name, data in all_attachment_data.items():
                    if joint_name in data['attachments_by_joint']:
                        for attachment in data['attachments_by_joint'][joint_name]:
                            expression_lines.append("if ({0} == 0) {1}.visibility = 0;".format(attr_full_name, attachment))
                
                # Attachment cases (when attribute > 0): hide defaults, show specific attachment set
                for i, display_name in enumerate(display_name_list):
                    attr_value = i + 1  # +1 because 0 is "Default"
                    data = all_attachment_data[display_name]
                    
                    # Hide defaults for this display name
                    for mesh in unique_default_meshes:
                        expression_lines.append("if ({0} == {1}) {2}.visibility = 0;".format(attr_full_name, attr_value, mesh))
                    
                    # Show attachments for this display name, hide others
                    for j, other_display_name in enumerate(display_name_list):
                        other_data = all_attachment_data[other_display_name]
                        if joint_name in other_data['attachments_by_joint']:
                            for attachment in other_data['attachments_by_joint'][joint_name]:
                                if j == i:  # This is the selected display name
                                    expression_lines.append("if ({0} == {1}) {2}.visibility = 1;".format(attr_full_name, attr_value, attachment))
                                else:  # Hide other display names
                                    expression_lines.append("if ({0} == {1}) {2}.visibility = 0;".format(attr_full_name, attr_value, attachment))
            
            if expression_lines:
                # Combine all lines into one expression
                full_expression = " ".join(expression_lines)
                
                # Create the expression with a unique name
                expression_name = "categoryAttachmentSwitch_{0}".format(self.make_safe_attribute_name(category))
                
                # Make sure expression name is unique
                counter = 1
                base_name = expression_name
                while cmds.objExists(expression_name):
                    expression_name = "{0}_{1}".format(base_name, counter)
                    counter += 1
                
                cmds.expression(name=expression_name, string=full_expression)
                
                print("    Created category switching expression '{0}' for {1} joint(s): {2}".format(
                    expression_name, len(affected_joints), list(affected_joints)))
                print("    Controls {0} display name(s): {1}".format(len(display_name_list), display_name_list))
            else:
                print("    Warning: No valid expression lines generated for category '{0}'".format(category))
                
        except Exception as e:
            print("    Error setting up category attachment switching for '{0}': {1}".format(category, str(e)))
    
    def setup_shared_attachment_switching(self, rig_group, attr_name, display_name, attachment_list):
        """Set up switching logic for attachments sharing the same display name"""
        print("  Setting up shared switching for '{0}'".format(display_name))
        
        try:
            attr_full_name = "{0}.{1}".format(rig_group, attr_name)
            
            # Group attachments by joint for easier processing
            attachments_by_joint = {}
            for joint_name, attachment_obj in attachment_list:
                if joint_name not in attachments_by_joint:
                    attachments_by_joint[joint_name] = []
                attachments_by_joint[joint_name].append(attachment_obj)
            
            # Build expression for each joint affected by this display name
            expression_lines = []
            affected_joints = []
            
            for joint_name, joint_attachments in attachments_by_joint.items():
                # Find default meshes for this joint
                default_meshes = self.find_default_meshes_for_joint(joint_name)
                
                if not default_meshes:
                    print("    Warning: No default meshes found for joint '{0}'".format(joint_name))
                    continue
                
                affected_joints.append(joint_name)
                
                # Default case (when attribute = 0): show defaults, hide attachments
                for mesh in default_meshes:
                    expression_lines.append("if ({0} == 0) {1}.visibility = 1;".format(attr_full_name, mesh))
                    expression_lines.append("else {0}.visibility = 0;".format(mesh))
                
                # Attachment case (when attribute = 1): hide defaults, show attachments
                for attachment in joint_attachments:
                    expression_lines.append("if ({0} == 1) {1}.visibility = 1;".format(attr_full_name, attachment))
                    expression_lines.append("else {0}.visibility = 0;".format(attachment))
            
            if expression_lines:
                # Combine all lines into one expression
                full_expression = " ".join(expression_lines)
                
                # Create the expression with a unique name
                expression_name = "sharedAttachmentSwitch_{0}".format(self.make_safe_attribute_name(display_name))
                
                # Make sure expression name is unique
                counter = 1
                base_name = expression_name
                while cmds.objExists(expression_name):
                    expression_name = "{0}_{1}".format(base_name, counter)
                    counter += 1
                
                cmds.expression(name=expression_name, string=full_expression)
                
                print("    Created shared switching expression '{0}' for {1} joint(s): {2}".format(
                    expression_name, len(affected_joints), affected_joints))
            else:
                print("    Warning: No valid expression lines generated for '{0}'".format(display_name))
                
        except Exception as e:
            print("    Error setting up shared attachment switching for '{0}': {1}".format(display_name, str(e)))
    
    def find_default_meshes_for_joint(self, joint_name):
        """Find default mesh objects constrained to a specific joint"""
        default_meshes = []
        
        for association in self.joint_associations:
            if association.joint_name == joint_name:
                for mesh_obj in association.mesh_objects:
                    # Find actual mesh objects constrained to this joint
                    all_transforms = cmds.ls(type='transform')
                    for transform in all_transforms:
                        if mesh_obj.lower() in transform.lower():
                            # Check if it's constrained to the joint
                            parent_constraints = cmds.listConnections(transform, type='parentConstraint') or []
                            scale_constraints = cmds.listConnections(transform, type='scaleConstraint') or []
                            constraints = parent_constraints + scale_constraints
                            
                            for constraint in constraints:
                                try:
                                    constraint_type = cmds.objectType(constraint)
                                    if constraint_type == 'parentConstraint':
                                        targets = cmds.parentConstraint(constraint, query=True, targetList=True) or []
                                    elif constraint_type == 'scaleConstraint':
                                        targets = cmds.scaleConstraint(constraint, query=True, targetList=True) or []
                                    else:
                                        continue
                                    
                                    if joint_name in targets:
                                        default_meshes.append(transform)
                                        break
                                except:
                                    continue
        
        return default_meshes
    
    def setup_attachment_switching(self, rig_group, attr_name, joint_name, attachments):
        """Set up the switching logic for attachments"""
        try:
            # Find default meshes for this joint
            default_meshes = []
            for association in self.joint_associations:
                if association.joint_name == joint_name:
                    for mesh_obj in association.mesh_objects:
                        # Find actual mesh objects constrained to this joint
                        all_transforms = cmds.ls(type='transform')
                        for transform in all_transforms:
                            if mesh_obj.lower() in transform.lower():
                                # Check if it's constrained to the joint
                                parent_constraints = cmds.listConnections(transform, type='parentConstraint') or []
                                scale_constraints = cmds.listConnections(transform, type='scaleConstraint') or []
                                constraints = parent_constraints + scale_constraints
                                for constraint in constraints:
                                    try:
                                        constraint_type = cmds.objectType(constraint)
                                        if constraint_type == 'parentConstraint':
                                            targets = cmds.parentConstraint(constraint, query=True, targetList=True) or []
                                        elif constraint_type == 'scaleConstraint':
                                            targets = cmds.scaleConstraint(constraint, query=True, targetList=True) or []
                                        else:
                                            continue
                                        
                                        if joint_name in targets:
                                            default_meshes.append(transform)
                                            break
                                    except:
                                        continue
            
            if not default_meshes:
                print("Warning: No default meshes found for joint '{0}'".format(joint_name))
                return
            
            # Create the switching expression
            attr_full_name = "{0}.{1}".format(rig_group, attr_name)
            
            # Build expression string
            expression_lines = []
            
            # Default case (when attribute = 0)
            for i, mesh in enumerate(default_meshes):
                expression_lines.append("if ({0} == 0) {1}.visibility = 1;".format(attr_full_name, mesh))
                expression_lines.append("else {0}.visibility = 0;".format(mesh))
            
            # Attachment cases (when attribute > 0)
            for i, attachment in enumerate(attachments):
                attr_value = i + 1  # +1 because 0 is "Default"
                expression_lines.append("if ({0} == {1}) {2}.visibility = 1;".format(
                    attr_full_name, attr_value, attachment))
                expression_lines.append("else {0}.visibility = 0;".format(attachment))
            
            # Combine all lines
            full_expression = " ".join(expression_lines)
            
            # Create the expression
            expression_name = "attachmentSwitch_{0}".format(joint_name.replace('jnt_', ''))
            cmds.expression(name=expression_name, string=full_expression)
            
            print("Created switching expression for joint '{0}' with {1} default meshes and {2} attachments".format(
                joint_name, len(default_meshes), len(attachments)))
            
        except Exception as e:
            print("Error setting up attachment switching for joint '{0}': {1}".format(joint_name, str(e)))
    
    def select_rig(self):
        """Select the chosen rig in the viewport"""
        current_item = self.existing_rigs_list.currentItem()
        if current_item and current_item.flags() & Qt.ItemIsSelectable:
            rig_name = current_item.text()
            if cmds.objExists(rig_name):
                cmds.select(rig_name, replace=True)
                print("Selected rig: {0}".format(rig_name))
            else:
                QMessageBox.warning(self, "Rig Not Found", "The selected rig no longer exists in the scene.")
                self.update_existing_rigs_list()
    
    def delete_rig(self):
        """Delete the selected weapon rig"""
        current_item = self.existing_rigs_list.currentItem()
        if current_item and current_item.flags() & Qt.ItemIsSelectable:
            rig_name = current_item.text()
            
            reply = QMessageBox.question(
                self,
                "Delete Weapon Rig",
                "Are you sure you want to delete the weapon rig '{0}'?\n\n"
                "This will remove all controls and constraints associated with this rig.\n"
                "This action cannot be undone.".format(rig_name),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                try:
                    if cmds.objExists(rig_name):
                        cmds.delete(rig_name)
                        print("Deleted weapon rig: {0}".format(rig_name))
                        
                        QMessageBox.information(self, "Rig Deleted", 
                            "Weapon rig '{0}' has been deleted successfully.".format(rig_name))
                        
                        # Refresh displays
                        self.analyze_scene()
                    else:
                        QMessageBox.warning(self, "Rig Not Found", 
                            "The selected rig no longer exists in the scene.")
                        self.update_existing_rigs_list()
                        
                except Exception as e:
                    QMessageBox.critical(self, "Deletion Error", 
                        "Error deleting rig: {0}".format(str(e)))


def get_maya_main_window():
    """Get Maya main window as parent for dialog"""
    if pyside_version:
        main_window_ptr = omui.MQtUtil.mainWindow()
        return wrapInstance(int(main_window_ptr), QDialog)
    return None


def show_weapon_rig_tool():
    """Show the Weapon Rig Tool dialog"""
    if not pyside_version:
        cmds.error("PySide is not available. Please ensure Maya is running properly.")
        return
    
    parent = get_maya_main_window()
    dialog = WeaponRigToolDialog(parent)
    dialog.show()


# For Maya drag-and-drop functionality
def onMayaDroppedPythonFile(*args, **kwargs):
    """Maya drag-and-drop entry point"""
    show_weapon_rig_tool()


# Main execution
if __name__ == "__main__":
    show_weapon_rig_tool() 