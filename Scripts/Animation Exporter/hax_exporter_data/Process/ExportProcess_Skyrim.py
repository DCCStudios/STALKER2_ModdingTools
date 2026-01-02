"""
Export Process: Skyrim - HKX Animation Conversion
Compatible with Maya 2025 (Python 3, PySide6) and Maya 2022- (Python 2, PySide2)

This module provides post-export FBX to HKX conversion for Skyrim animations.
It registers itself with the HaxExporterSettings system.

Features:
- FBX to HKX conversion via blender-hkx
- Timeline bookmark/annotation integration for Skyrim animations
- Automatic annotation embedding via hkanno64
"""

from __future__ import print_function
import sys
import os
import json
import subprocess
import math
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom

# Maya imports
import maya.cmds as cmds

# PySide compatibility for Maya versions
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    PYSIDE_VERSION = 6
except ImportError:
    try:
        from PySide2 import QtCore, QtGui, QtWidgets
        PYSIDE_VERSION = 2
    except ImportError:
        PYSIDE_VERSION = None

# Import the settings system
try:
    import HaxExporterSettings
except ImportError:
    try:
        from . import HaxExporterSettings
    except ImportError:
        HaxExporterSettings = None
        print("[ExportProcess_Skyrim] Warning: Could not import HaxExporterSettings")

# Import annotation creator module
try:
    from . import SkyrimAnnotationCreator
except ImportError:
    try:
        import SkyrimAnnotationCreator
    except ImportError:
        SkyrimAnnotationCreator = None
        print("[ExportProcess_Skyrim] Warning: Could not import SkyrimAnnotationCreator")

# Process ID and display name
PROCESS_ID = "skyrim"
PROCESS_NAME = "Skyrim (FBX → HKX)"

# Settings storage
SETTINGS_ATTR = "skyrimProcessSettings"

# Available skeleton files - (Display Name, Filename)
SKELETON_OPTIONS = [
    ("Male (Default)", "Skeleton.hkx"),
    ("1st Person", "1skeleton.hkx"),
    ("Female", "femskeleton.hkx"),
    ("XP32", "xpskeleton.hkx"),
    ("XPMS", "skeleton242.hkx"),
    ("Giant", "GiantSkeleton.hkx"),
    ("Draugr", "Draugrskeleton.hkx"),
    ("Falmer", "Falmerskeleton.hkx"),
]

# Target game formats
TARGET_OPTIONS = [
    ("Skyrim SE / AE (64-bit)", "AMD64"),
    ("Skyrim LE (32-bit)", "WIN32")
]

DEFAULT_SETTINGS = {
    "hkxToolPath": "",
    "skeleton": "Skeleton.hkx",
    "targetGame": "AMD64",
    "keepXml": False,
    "hkannoPath": "",
    "embedAnnotations": True,
}


def log_message(message):
    """Log a message"""
    print("[Skyrim Export] " + str(message))


def log_verbose(message):
    """Log a verbose message (only if verbose logging is enabled)"""
    try:
        if HaxExporterSettings and HaxExporterSettings.get_verbose_logging():
            print("[Skyrim Export] [VERBOSE] " + str(message))
    except:
        pass


def is_verbose():
    """Check if verbose logging is enabled"""
    try:
        return HaxExporterSettings and HaxExporterSettings.get_verbose_logging()
    except:
        return False


def load_settings():
    """Load Skyrim-specific settings from scene"""
    try:
        node = HaxExporterSettings.get_settings_node()
        if cmds.attributeQuery(SETTINGS_ATTR, node=node, exists=True):
            settings_json = cmds.getAttr(node + "." + SETTINGS_ATTR)
            if settings_json:
                settings = json.loads(settings_json)
                merged = DEFAULT_SETTINGS.copy()
                merged.update(settings)
                return merged
    except Exception as e:
        log_message("Error loading settings: %s" % str(e))
    return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    """Save Skyrim-specific settings to scene"""
    try:
        node = HaxExporterSettings.get_settings_node()
        if not cmds.attributeQuery(SETTINGS_ATTR, node=node, exists=True):
            cmds.addAttr(node, longName=SETTINGS_ATTR, dataType="string")
        cmds.setAttr(node + "." + SETTINGS_ATTR, json.dumps(settings), type="string")
    except Exception as e:
        log_message("Error saving settings: %s" % str(e))


def validate_tool_path(path):
    """Validate the HKX Conversion Tool path"""
    if not path or not os.path.isdir(path):
        return False, "Path does not exist"
    
    blender_hkx = os.path.join(path, "blender-hkx.exe")
    if not os.path.exists(blender_hkx):
        return False, "blender-hkx.exe not found"
    
    return True, "Valid"


# ============================================================================
# SETTINGS WIDGET
# ============================================================================

class SkyrimSettingsWidget(QtWidgets.QWidget):
    """Widget containing Skyrim-specific settings"""
    
    def __init__(self, parent=None):
        super(SkyrimSettingsWidget, self).__init__(parent)
        self.settings = load_settings()
        self.create_ui()
        self.load_current_settings()
    
    def create_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(8)
        
        # Path section
        path_label = QtWidgets.QLabel("HKX Conversion Tool Path:")
        layout.addWidget(path_label)
        
        path_row = QtWidgets.QHBoxLayout()
        self.path_field = QtWidgets.QLineEdit()
        self.path_field.setPlaceholderText("Path to folder containing blender-hkx.exe...")
        self.path_field.textChanged.connect(self.on_path_changed)
        path_row.addWidget(self.path_field)
        
        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.setMaximumWidth(80)
        browse_btn.clicked.connect(self.browse_path)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)
        
        self.status_label = QtWidgets.QLabel("")
        layout.addWidget(self.status_label)
        
        # HKAnno64 path (optional)
        hkanno_label = QtWidgets.QLabel("HKAnno64 Path (for annotations):")
        layout.addWidget(hkanno_label)
        
        hkanno_row = QtWidgets.QHBoxLayout()
        self.hkanno_field = QtWidgets.QLineEdit()
        self.hkanno_field.setPlaceholderText("Path to folder containing hkanno64.exe (optional)...")
        self.hkanno_field.textChanged.connect(self.on_hkanno_changed)
        hkanno_row.addWidget(self.hkanno_field)
        
        hkanno_browse_btn = QtWidgets.QPushButton("Browse...")
        hkanno_browse_btn.setMaximumWidth(80)
        hkanno_browse_btn.clicked.connect(self.browse_hkanno_path)
        hkanno_row.addWidget(hkanno_browse_btn)
        layout.addLayout(hkanno_row)
        
        self.hkanno_status_label = QtWidgets.QLabel("")
        layout.addWidget(self.hkanno_status_label)
        
        # Options row - Skeleton and Target
        options_layout = QtWidgets.QHBoxLayout()
        
        options_layout.addWidget(QtWidgets.QLabel("Skeleton:"))
        self.skeleton_combo = QtWidgets.QComboBox()
        for display_name, filename in SKELETON_OPTIONS:
            self.skeleton_combo.addItem(display_name, filename)
        options_layout.addWidget(self.skeleton_combo)
        
        options_layout.addSpacing(20)
        
        options_layout.addWidget(QtWidgets.QLabel("Target:"))
        self.target_combo = QtWidgets.QComboBox()
        for display, value in TARGET_OPTIONS:
            self.target_combo.addItem(display, value)
        options_layout.addWidget(self.target_combo)
        
        options_layout.addStretch()
        layout.addLayout(options_layout)
        
        # Checkboxes
        checkbox_layout = QtWidgets.QHBoxLayout()
        
        self.keep_xml_checkbox = QtWidgets.QCheckBox("Keep XML")
        self.keep_xml_checkbox.setToolTip("Keep the intermediate XML file for debugging")
        checkbox_layout.addWidget(self.keep_xml_checkbox)
        
        self.embed_annotations_checkbox = QtWidgets.QCheckBox("Embed Timeline Annotations")
        self.embed_annotations_checkbox.setToolTip(
            "Automatically embed Maya timeline bookmarks as HKX annotations on export.\n"
            "Requires hkanno64.exe path to be set."
        )
        checkbox_layout.addWidget(self.embed_annotations_checkbox)
        
        checkbox_layout.addStretch()
        layout.addLayout(checkbox_layout)
        
        # Separator
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(sep)
        
        # Annotation Creator button
        anno_btn = QtWidgets.QPushButton("🎵 Open Annotation Creator...")
        anno_btn.setToolTip("Open the Skyrim Animation Annotation Creator to add timeline bookmarks")
        anno_btn.clicked.connect(self.open_annotation_creator)
        anno_btn.setStyleSheet("font-weight: bold; padding: 8px;")
        
        # Disable button if annotation module not available
        if SkyrimAnnotationCreator is None:
            anno_btn.setEnabled(False)
            anno_btn.setToolTip("Annotation Creator not available - module failed to load")
        
        layout.addWidget(anno_btn)
        
        # Info text
        info_label = QtWidgets.QLabel(
            "<b>Note:</b> FBX files must be exported as ASCII format. "
            "Use the Annotation Creator to add footstep sounds and other events."
        )
        info_label.setStyleSheet("color: #888; font-size: 9pt;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
    
    def load_current_settings(self):
        self.settings = load_settings()
        self.path_field.setText(self.settings.get("hkxToolPath", ""))
        self.hkanno_field.setText(self.settings.get("hkannoPath", ""))
        
        skel = self.settings.get("skeleton", "Skeleton.hkx")
        for i in range(self.skeleton_combo.count()):
            if self.skeleton_combo.itemData(i) == skel:
                self.skeleton_combo.setCurrentIndex(i)
                break
        
        target = self.settings.get("targetGame", "AMD64")
        for i in range(self.target_combo.count()):
            if self.target_combo.itemData(i) == target:
                self.target_combo.setCurrentIndex(i)
                break
        
        self.keep_xml_checkbox.setChecked(self.settings.get("keepXml", False))
        self.embed_annotations_checkbox.setChecked(self.settings.get("embedAnnotations", True))
        
        self.validate_path()
        self.validate_hkanno_path()
    
    def browse_path(self):
        current = self.path_field.text()
        if not current or not os.path.isdir(current):
            current = ""
        
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select HKX Conversion Tool Folder", current,
            QtWidgets.QFileDialog.ShowDirsOnly
        )
        if path:
            self.path_field.setText(path)
    
    def browse_hkanno_path(self):
        current = self.hkanno_field.text()
        if not current or not os.path.isdir(current):
            current = ""
        
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select HKAnno64 Folder", current,
            QtWidgets.QFileDialog.ShowDirsOnly
        )
        if path:
            self.hkanno_field.setText(path)
    
    def on_path_changed(self):
        self.validate_path()
    
    def on_hkanno_changed(self):
        self.validate_hkanno_path()
    
    def validate_path(self):
        path = self.path_field.text()
        if not path:
            self.status_label.setText("")
            self.status_label.setStyleSheet("")
            return False
        
        valid, msg = validate_tool_path(path)
        if valid:
            self.status_label.setText("✓ " + msg)
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.status_label.setText("✗ " + msg)
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
        return valid
    
    def validate_hkanno_path(self):
        path = self.hkanno_field.text()
        if not path:
            self.hkanno_status_label.setText("(Optional - needed for annotation embedding)")
            self.hkanno_status_label.setStyleSheet("color: #888;")
            return False
        
        if not os.path.isdir(path):
            self.hkanno_status_label.setText("✗ Path does not exist")
            self.hkanno_status_label.setStyleSheet("color: #f44336; font-weight: bold;")
            return False
        
        hkanno_exe = os.path.join(path, "hkanno64.exe")
        if not os.path.exists(hkanno_exe):
            self.hkanno_status_label.setText("✗ hkanno64.exe not found")
            self.hkanno_status_label.setStyleSheet("color: #f44336; font-weight: bold;")
            return False
        
        self.hkanno_status_label.setText("✓ hkanno64.exe found")
        self.hkanno_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        return True
    
    def validate(self):
        """Validate settings before saving. Returns True if valid."""
        if not self.validate_path():
            QtWidgets.QMessageBox.warning(
                self, "Invalid Path",
                "Please provide a valid HKX Conversion Tool path."
            )
            return False
        return True
    
    def open_annotation_creator(self):
        """Open the annotation creator dialog"""
        if SkyrimAnnotationCreator is None:
            QtWidgets.QMessageBox.warning(
                self, "Not Available",
                "Annotation Creator module could not be loaded."
            )
            return
        
        try:
            parent = HaxExporterSettings.maya_main_window() if HaxExporterSettings else None
        except:
            parent = None
        
        SkyrimAnnotationCreator.show_annotation_creator(parent)
    
    def save_settings(self):
        """Save current settings"""
        self.settings["hkxToolPath"] = self.path_field.text()
        self.settings["hkannoPath"] = self.hkanno_field.text()
        self.settings["skeleton"] = self.skeleton_combo.currentData()
        self.settings["targetGame"] = self.target_combo.currentData()
        self.settings["keepXml"] = self.keep_xml_checkbox.isChecked()
        self.settings["embedAnnotations"] = self.embed_annotations_checkbox.isChecked()
        save_settings(self.settings)


# ============================================================================
# FBX PARSER AND HKX XML GENERATOR
# ============================================================================

def decode_bone_name(encoded_name):
    """Decode Maya-encoded bone names back to Skyrim format."""
    decoded = encoded_name
    decoded = decoded.replace('_s_', ' ')
    decoded = decoded.replace('_ob_', '[')
    decoded = decoded.replace('_cb_', ']')
    return decoded


def euler_to_quaternion(rx, ry, rz):
    """Convert Euler angles (degrees) to quaternion (w, x, y, z)."""
    rx = math.radians(rx)
    ry = math.radians(ry)
    rz = math.radians(rz)
    
    cx = math.cos(rx / 2)
    sx = math.sin(rx / 2)
    cy = math.cos(ry / 2)
    sy = math.sin(ry / 2)
    cz = math.cos(rz / 2)
    sz = math.sin(rz / 2)
    
    w = cx * cy * cz + sx * sy * sz
    x = sx * cy * cz - cx * sy * sz
    y = cx * sy * cz + sx * cy * sz
    z = cx * cy * sz - sx * sy * cz
    
    return (w, x, y, z)


def multiply_quaternions(q1, q2):
    """Multiply two quaternions (w, x, y, z)."""
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    
    w = w1*w2 - x1*x2 - y1*y2 - z1*z2
    x = w1*x2 + x1*w2 + y1*z2 - z1*y2
    y = w1*y2 - x1*z2 + y1*w2 + z1*x2
    z = w1*z2 + x1*y2 - y1*x2 + z1*w2
    
    return (w, x, y, z)


def rotate_vector_by_quat(v, q):
    """Rotate a vector by a quaternion."""
    w, x, y, z = q
    vx, vy, vz = v
    
    t = [
        2 * (y * vz - z * vy),
        2 * (z * vx - x * vz),
        2 * (x * vy - y * vx)
    ]
    
    return [
        vx + w * t[0] + y * t[2] - z * t[1],
        vy + w * t[1] + z * t[0] - x * t[2],
        vz + w * t[2] + x * t[1] - y * t[0]
    ]


class FBXParser:
    """Parser for FBX ASCII files."""
    
    FBX_TIME_UNIT = 46186158000
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.models = {}
        self.connections = []
        self.model_names = {}
        self.anim_curves = {}
        self.curve_to_node = {}
        self.node_to_model = {}
        self.frame_count = 2
        self.fps = 30
        self.frame_offset = 0
        self.original_start_frame = 0
    
    def parse(self):
        log_message("  Parsing FBX file...")
        
        with open(self.filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        log_message("    File size: %d bytes" % len(content))
        
        self._parse_models(content)
        log_message("    Found %d models (bones)" % len(self.models))
        
        self._parse_connections(content)
        log_message("    Found %d connections" % len(self.connections))
        
        self._parse_animation_curves(content)
        log_message("    Found %d animation curves" % len(self.anim_curves))
        
        self._parse_animation_connections(content)
        log_message("    Found %d curve-to-node mappings" % len(self.curve_to_node))
        
        if self.frame_offset > 0:
            log_message("    Original frame range: %d-%d (offset by %d to start at 0)" % 
                       (self.original_start_frame, self.original_start_frame + self.frame_count - 1, self.frame_offset))
        log_message("    Animation: %d frames at %d fps" % (self.frame_count, self.fps))
        
        return True
    
    def _parse_models(self, content):
        model_pattern = r'Model:\s*(\d+),\s*"Model::([^"]+)",\s*"LimbNode"\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        
        for match in re.finditer(model_pattern, content, re.MULTILINE | re.DOTALL):
            model_id = match.group(1)
            raw_name = match.group(2)
            properties_block = match.group(3)
            
            model_name = decode_bone_name(raw_name)
            self.model_names[model_id] = model_name
            
            model_data = {
                'name': model_name,
                'translation': [0.0, 0.0, 0.0],
                'rotation': [0.0, 0.0, 0.0],
                'scale': [1.0, 1.0, 1.0],
                'pre_rotation': [0.0, 0.0, 0.0]
            }
            
            trans_match = re.search(r'P:\s*"Lcl Translation"[^,]*,[^,]*,[^,]*,[^,]*,([^,]+),([^,]+),([^\n]+)', properties_block)
            if trans_match:
                try:
                    model_data['translation'] = [
                        float(trans_match.group(1)),
                        float(trans_match.group(2)),
                        float(trans_match.group(3).strip())
                    ]
                except ValueError:
                    pass
            
            rot_match = re.search(r'P:\s*"Lcl Rotation"[^,]*,[^,]*,[^,]*,[^,]*,([^,]+),([^,]+),([^\n]+)', properties_block)
            if rot_match:
                try:
                    model_data['rotation'] = [
                        float(rot_match.group(1)),
                        float(rot_match.group(2)),
                        float(rot_match.group(3).strip())
                    ]
                except ValueError:
                    pass
            
            self.models[model_id] = model_data
    
    def _parse_connections(self, content):
        conn_match = re.search(r'Connections:\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}', content, re.DOTALL)
        if not conn_match:
            return
        
        conn_block = conn_match.group(1)
        conn_pattern = r';Model::([^,]+),\s*Model::([^\n]+)\s*\n\s*C:\s*"OO",(\d+),(\d+)'
        
        for match in re.finditer(conn_pattern, conn_block):
            child_name = match.group(1).strip()
            parent_name = match.group(2).strip()
            child_id = match.group(3)
            parent_id = match.group(4)
            self.connections.append((child_id, parent_id, child_name, parent_name))
    
    def _parse_animation_curves(self, content):
        curve_header_pattern = r'AnimationCurve:\s*(\d+),\s*"[^"]*",\s*""'
        
        raw_curves = {}
        all_frames = []
        
        for header_match in re.finditer(curve_header_pattern, content):
            curve_id = header_match.group(1)
            start_pos = header_match.end()
            search_region = content[start_pos:start_pos + 5000]
            
            time_match = re.search(r'KeyTime:\s*\*\d+\s*\{\s*a:\s*([^\}]+)\}', search_region)
            value_match = re.search(r'KeyValueFloat:\s*\*\d+\s*\{\s*a:\s*([^\}]+)\}', search_region)
            
            if time_match and value_match:
                times_str = time_match.group(1).strip()
                values_str = value_match.group(1).strip()
                
                try:
                    times = [int(t.strip()) for t in times_str.split(',') if t.strip()]
                    values = [float(v.strip()) for v in values_str.split(',') if v.strip()]
                    
                    keys = []
                    for t, v in zip(times, values):
                        frame = int(round((t / self.FBX_TIME_UNIT) * self.fps))
                        keys.append((frame, v))
                        all_frames.append(frame)
                    
                    raw_curves[curve_id] = {'keys': keys}
                except (ValueError, IndexError):
                    pass
        
        if all_frames:
            min_frame = min(all_frames)
            max_frame = max(all_frames)
            self.original_start_frame = min_frame
            self.frame_offset = min_frame
            
            for curve_id, curve_data in raw_curves.items():
                normalized_keys = []
                for frame, value in curve_data['keys']:
                    normalized_frame = frame - min_frame
                    normalized_keys.append((normalized_frame, value))
                self.anim_curves[curve_id] = {'keys': normalized_keys}
            
            self.frame_count = max(2, max_frame - min_frame + 1)
        else:
            self.anim_curves = raw_curves
    
    def _parse_animation_connections(self, content):
        conn_match = re.search(r'Connections:\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}', content, re.DOTALL)
        if not conn_match:
            return
        
        conn_block = conn_match.group(1)
        
        node_to_model_pattern = r';AnimCurveNode::([TRS]),\s*Model::([^\n]+)\s*\n\s*C:\s*"OP",(\d+),(\d+),\s*"Lcl\s*(Translation|Rotation|Scaling)"'
        
        for match in re.finditer(node_to_model_pattern, conn_block):
            node_type = match.group(1)
            raw_bone_name = match.group(2).strip()
            node_id = match.group(3)
            
            bone_name = decode_bone_name(raw_bone_name)
            
            self.node_to_model[node_id] = {
                'bone_name': bone_name,
                'type': node_type,
            }
        
        curve_to_node_pattern = r'C:\s*"OP",(\d+),(\d+),\s*"d\|([XYZ])"'
        
        for match in re.finditer(curve_to_node_pattern, conn_block):
            curve_id = match.group(1)
            node_id = match.group(2)
            axis = match.group(3)
            
            self.curve_to_node[curve_id] = {
                'node_id': node_id,
                'axis': axis
            }
    
    def get_bone_animation(self, bone_name, frame):
        result = {
            'translation': [0.0, 0.0, 0.0],
            'rotation': [0.0, 0.0, 0.0],
            'scale': [1.0, 1.0, 1.0],
            'is_animated': False
        }
        
        for curve_id, curve_data in self.anim_curves.items():
            if curve_id not in self.curve_to_node:
                continue
            
            curve_conn = self.curve_to_node[curve_id]
            node_id = curve_conn['node_id']
            axis = curve_conn['axis']
            
            if node_id not in self.node_to_model:
                continue
            
            node_data = self.node_to_model[node_id]
            if node_data['bone_name'] != bone_name:
                continue
            
            keys = curve_data['keys']
            if keys:
                first_val = keys[0][1]
                is_varying = any(abs(k[1] - first_val) > 0.001 for k in keys)
                if is_varying:
                    result['is_animated'] = True
            
            value = self._sample_curve(keys, frame)
            
            axis_idx = {'X': 0, 'Y': 1, 'Z': 2}[axis]
            if node_data['type'] == 'T':
                result['translation'][axis_idx] = value
            elif node_data['type'] == 'R':
                result['rotation'][axis_idx] = value
            elif node_data['type'] == 'S':
                result['scale'][axis_idx] = value
        
        return result
    
    def _sample_curve(self, keys, frame):
        if not keys:
            return 0.0
        
        prev_key = keys[0]
        next_key = keys[-1]
        
        for f, v in keys:
            if f == frame:
                return v
            if f < frame:
                prev_key = (f, v)
            if f > frame:
                next_key = (f, v)
                break
        
        if frame <= prev_key[0]:
            return prev_key[1]
        if frame >= next_key[0]:
            return next_key[1]
        
        t = (frame - prev_key[0]) / (next_key[0] - prev_key[0])
        return prev_key[1] + t * (next_key[1] - prev_key[1])
    
    def has_animation(self):
        return len(self.anim_curves) > 0 and self.frame_count > 2
    
    def build_hierarchy(self):
        children_of = {}
        parent_of = {}
        
        for child_id, parent_id, child_name, parent_name in self.connections:
            if child_id in self.models:
                if parent_id not in children_of:
                    children_of[parent_id] = []
                children_of[parent_id].append(child_id)
                parent_of[child_id] = parent_id
        
        root_ids = []
        for model_id in self.models:
            parent_id = parent_of.get(model_id)
            if parent_id is None or parent_id not in self.models:
                root_ids.append(model_id)
        
        def build_tree(model_id):
            model = self.models[model_id]
            children = children_of.get(model_id, [])
            return {
                'id': model_id,
                'name': model['name'],
                'translation': model['translation'],
                'rotation': model['rotation'],
                'scale': model['scale'],
                'pre_rotation': model['pre_rotation'],
                'children': [build_tree(cid) for cid in children if cid in self.models]
            }
        
        return [build_tree(rid) for rid in root_ids]


def compute_world_transforms_for_frame(hierarchy, frame, parser, bind_transforms):
    frame_transforms = {}
    
    def compute_bone(bone_data, parent_world_trans, parent_world_rot):
        bone_name = bone_data['name']
        local_trans = bone_data['translation']
        
        anim_data = parser.get_bone_animation(bone_name, frame)
        
        if anim_data['is_animated']:
            local_quat = euler_to_quaternion(
                anim_data['rotation'][0],
                anim_data['rotation'][1],
                anim_data['rotation'][2]
            )
        else:
            bind_rot = bone_data['rotation']
            local_quat = euler_to_quaternion(bind_rot[0], bind_rot[1], bind_rot[2])
        
        if parent_world_trans is not None:
            rotated_trans = rotate_vector_by_quat(local_trans, parent_world_rot)
            world_trans = [
                parent_world_trans[0] + rotated_trans[0],
                parent_world_trans[1] + rotated_trans[1],
                parent_world_trans[2] + rotated_trans[2]
            ]
            world_quat = multiply_quaternions(parent_world_rot, local_quat)
        else:
            world_trans = [0.0, 0.0, 0.0]
            world_quat = (1.0, 0.0, 0.0, 0.0)
        
        frame_transforms[bone_name] = (world_trans, world_quat)
        
        for child in bone_data.get('children', []):
            compute_bone(child, world_trans, world_quat)
    
    for bone in hierarchy:
        compute_bone(bone, None, None)
    
    return frame_transforms


def generate_hkx_xml(hierarchy, parser):
    has_anim = parser.has_animation()
    num_frames = parser.frame_count if has_anim else 2
    fps = parser.fps
    
    log_message("  Generating XML with %d frames at %d fps" % (num_frames, fps))
    
    root = ET.Element('blender-hkx', version='1')
    
    ET.SubElement(root, 'int', name='frames').text = str(num_frames)
    ET.SubElement(root, 'int', name='frameRate').text = str(fps)
    ET.SubElement(root, 'bool', name='additive').text = 'false'
    
    skeleton_elem = ET.SubElement(root, 'skeleton', name='0')
    ET.SubElement(skeleton_elem, 'string', name='referenceFrame').text = 'OBJECT'
    
    all_bones = []
    bone_transforms = {}
    
    def add_bone(parent_elem, bone_data, parent_world_trans=None, parent_world_rot=None, is_root=False):
        bone_elem = ET.SubElement(parent_elem, 'bone', name=bone_data['name'])
        
        local_trans = bone_data['translation']
        rot = bone_data['rotation']
        
        if is_root:
            world_trans = [0.0, 0.0, 0.0]
            world_quat = (1.0, 0.0, 0.0, 0.0)
        else:
            local_quat = euler_to_quaternion(rot[0], rot[1], rot[2])
            
            if parent_world_trans is not None and parent_world_rot is not None:
                rotated_trans = rotate_vector_by_quat(local_trans, parent_world_rot)
                world_trans = [
                    parent_world_trans[0] + rotated_trans[0],
                    parent_world_trans[1] + rotated_trans[1],
                    parent_world_trans[2] + rotated_trans[2]
                ]
                world_quat = multiply_quaternions(parent_world_rot, local_quat)
            else:
                world_trans = local_trans
                world_quat = local_quat
        
        transform_text = "%s %s %s %s %s %s %s 1 1 1" % (
            world_trans[0], world_trans[1], world_trans[2],
            world_quat[0], world_quat[1], world_quat[2], world_quat[3]
        )
        
        ET.SubElement(bone_elem, 'transform', name='ref').text = transform_text
        all_bones.append(bone_data['name'])
        bone_transforms[bone_data['name']] = (world_trans, world_quat)
        
        for child in bone_data.get('children', []):
            add_bone(bone_elem, child, world_trans, world_quat, is_root=False)
    
    for bone in hierarchy:
        add_bone(skeleton_elem, bone, None, None, is_root=True)
    
    log_message("    Added %d bones to skeleton" % len(all_bones))
    
    anim_elem = ET.SubElement(root, 'animation', name='0')
    
    anim_skeleton_root = 'NPC Root [Root]'
    if hierarchy:
        for child in hierarchy[0].get('children', []):
            if 'Root' in child['name']:
                anim_skeleton_root = child['name']
                break
    
    ET.SubElement(anim_elem, 'string', name='skeleton').text = anim_skeleton_root
    ET.SubElement(anim_elem, 'string', name='referenceFrame').text = 'BONE'
    
    excluded_bones = {'NPC', 'CharacterBumper'}
    
    bind_transforms_dict = {}
    for bone_name in all_bones:
        bind_pos, bind_quat = bone_transforms.get(bone_name, ([0,0,0], (1,0,0,0)))
        bind_transforms_dict[bone_name] = (bind_pos, bind_quat)
    
    frame_world_transforms = {}
    if has_anim:
        log_message("    Computing hierarchical world transforms...")
        for frame in range(num_frames):
            frame_world_transforms[frame] = compute_world_transforms_for_frame(
                hierarchy, frame, parser, bind_transforms_dict
            )
    
    animated_bone_count = 0
    total_keyframes = 0
    
    for bone_name in all_bones:
        if bone_name in excluded_bones:
            continue
        
        track_elem = ET.SubElement(anim_elem, 'track', name=bone_name, type='transform')
        
        bind_transform_str = "%s %s %s %s %s %s %s 1 1 1" % (
            bone_transforms[bone_name][0][0], bone_transforms[bone_name][0][1], bone_transforms[bone_name][0][2],
            bone_transforms[bone_name][1][0], bone_transforms[bone_name][1][1], 
            bone_transforms[bone_name][1][2], bone_transforms[bone_name][1][3]
        )
        
        bone_has_animation = False
        
        for frame in range(num_frames):
            if has_anim and frame in frame_world_transforms:
                if bone_name in frame_world_transforms[frame]:
                    world_pos, world_quat = frame_world_transforms[frame][bone_name]
                    transform_text = "%s %s %s %s %s %s %s 1 1 1" % (
                        world_pos[0], world_pos[1], world_pos[2],
                        world_quat[0], world_quat[1], world_quat[2], world_quat[3]
                    )
                    
                    anim_data = parser.get_bone_animation(bone_name, frame)
                    if anim_data['is_animated']:
                        bone_has_animation = True
                else:
                    transform_text = bind_transform_str
            else:
                transform_text = bind_transform_str
            
            ET.SubElement(track_elem, 'transform', name=str(frame)).text = transform_text
            total_keyframes += 1
        
        if bone_has_animation:
            animated_bone_count += 1
    
    log_message("    Animation tracks: %d bones with animation" % animated_bone_count)
    
    rough_string = ET.tostring(root, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    xml_content = reparsed.toprettyxml(indent="\t")
    
    return xml_content


def check_fbx_format(fbx_path):
    try:
        with open(fbx_path, 'rb') as f:
            header = f.read(20)
        if header.startswith(b'Kaydara FBX Binary'):
            return "BINARY"
        elif header.startswith(b'; FBX') or b'FBX' in header:
            return "ASCII"
        else:
            return "UNKNOWN"
    except Exception as e:
        return "ERROR: %s" % str(e)


def process_exported_files(fbx_paths):
    """Process exported FBX files - convert to HKX."""
    log_message("")
    log_message("=" * 70)
    log_message("SKYRIM HKX CONVERSION - STARTING")
    log_message("=" * 70)
    
    if not fbx_paths:
        log_message("No FBX files to convert")
        return True
    
    log_message("Files to convert: %d" % len(fbx_paths))
    
    settings = load_settings()
    tool_path = settings.get("hkxToolPath", "")
    skeleton = settings.get("skeleton", "Skeleton.hkx")
    target = settings.get("targetGame", "AMD64")
    keep_xml = settings.get("keepXml", False)
    embed_annotations = settings.get("embedAnnotations", True)
    hkanno_path = settings.get("hkannoPath", "")
    
    log_message("  Tool Path: %s" % (tool_path if tool_path else "<NOT SET>"))
    log_message("  Skeleton: %s" % skeleton)
    log_message("  Target: %s" % target)
    log_message("  Embed Annotations: %s" % embed_annotations)
    
    if not tool_path:
        log_message("ERROR: HKX Tool Path is not set!")
        cmds.warning("Skyrim HKX conversion skipped: Tool path not set")
        return False
    
    blender_hkx = os.path.join(tool_path, "blender-hkx.exe")
    skeleton_path = os.path.join(tool_path, skeleton)
    
    missing = []
    if not os.path.exists(blender_hkx):
        missing.append("blender-hkx.exe")
    if not os.path.exists(skeleton_path):
        missing.append(skeleton)
    
    if missing:
        log_message("ERROR: Missing files: %s" % ", ".join(missing))
        cmds.warning("Skyrim HKX conversion failed: Missing files")
        return False
    
    successful = []
    failed = []
    
    for idx, fbx_path in enumerate(fbx_paths):
        log_message("")
        log_message("-" * 50)
        log_message("FILE %d/%d: %s" % (idx+1, len(fbx_paths), os.path.basename(fbx_path)))
        log_message("-" * 50)
        
        try:
            if not os.path.exists(fbx_path):
                log_message("  ERROR: File not found!")
                failed.append(os.path.basename(fbx_path))
                continue
            
            fbx_format = check_fbx_format(fbx_path)
            if fbx_format == "BINARY":
                log_message("  ERROR: FBX is BINARY format - must be ASCII!")
                failed.append(os.path.basename(fbx_path))
                continue
            
            base_name = os.path.splitext(fbx_path)[0]
            hkx_path = base_name + ".hkx"
            xml_path = base_name + "_temp.xml"
            
            # Parse FBX
            log_message("  [STEP 1] Parsing FBX...")
            parser = FBXParser(fbx_path)
            parser.parse()
            
            hierarchy = parser.build_hierarchy()
            if not hierarchy:
                log_message("  ERROR: No bones found!")
                failed.append(os.path.basename(fbx_path))
                continue
            
            # Generate XML
            log_message("  [STEP 2] Generating XML...")
            xml_content = generate_hkx_xml(hierarchy, parser)
            
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            # Pack to HKX
            log_message("  [STEP 3] Packing to HKX...")
            cmd = [blender_hkx, 'pack', target, xml_path, hkx_path, skeleton_path]
            
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=tool_path,
                startupinfo=startupinfo,
                timeout=60
            )
            
            # Clean up XML
            if keep_xml:
                final_xml = base_name + ".xml"
                try:
                    if os.path.exists(final_xml):
                        os.remove(final_xml)
                    os.rename(xml_path, final_xml)
                except:
                    pass
            else:
                try:
                    os.remove(xml_path)
                except:
                    pass
            
            if result.returncode == 0 and os.path.exists(hkx_path):
                output_size = os.path.getsize(hkx_path)
                log_message("  ✓ Created HKX: %.1f KB" % (output_size/1024))
                
                # Embed annotations if enabled and module available
                if embed_annotations and SkyrimAnnotationCreator:
                    log_message("  [STEP 4] Embedding annotations...")
                    SkyrimAnnotationCreator.embed_annotations_in_hkx(hkx_path, parser.fps, hkanno_path)
                
                successful.append(os.path.basename(fbx_path))
            else:
                log_message("  ✗ FAILED: blender-hkx error")
                if result.stderr:
                    log_message("    %s" % result.stderr.strip())
                failed.append(os.path.basename(fbx_path))
                
        except Exception as e:
            log_message("  ✗ FAILED: %s" % str(e))
            failed.append(os.path.basename(fbx_path))
    
    # Summary
    log_message("")
    log_message("=" * 70)
    log_message("CONVERSION COMPLETE: %d successful, %d failed" % (len(successful), len(failed)))
    log_message("=" * 70)
    
    if PYSIDE_VERSION:
        try:
            parent = HaxExporterSettings.maya_main_window() if HaxExporterSettings else None
        except:
            parent = None
        
        msg = "HKX Conversion Complete\n\n"
        msg += "Successful: %d\n" % len(successful)
        msg += "Failed: %d\n" % len(failed)
        
        if failed:
            msg += "\nFailed files:\n• " + "\n• ".join(failed)
        
        QtWidgets.QMessageBox.information(parent, "Skyrim HKX Conversion", msg)
    
    return len(failed) == 0


# Register this export process with the settings system
if PYSIDE_VERSION and HaxExporterSettings:
    HaxExporterSettings.register_export_process(
        PROCESS_ID,
        PROCESS_NAME,
        SkyrimSettingsWidget,
        process_exported_files
    )
    log_message("Registered Skyrim export process")
