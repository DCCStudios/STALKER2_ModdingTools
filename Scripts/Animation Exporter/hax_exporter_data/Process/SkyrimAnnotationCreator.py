"""
Skyrim Animation Annotation Creator
Compatible with Maya 2025 (Python 3, PySide6) and Maya 2022- (Python 2, PySide2)

This module provides a tool for creating timeline bookmarks/annotations
for Skyrim HKX animations. Annotations are embedded into HKX files using hkanno64.

Can be used standalone or called from ExportProcess_Skyrim.
"""

from __future__ import print_function
import os
import json
import subprocess
import sys
import traceback

# Maya imports
import maya.cmds as cmds
import maya.mel as mel

# PySide compatibility
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    PYSIDE_VERSION = 6
except ImportError:
    try:
        from PySide2 import QtCore, QtGui, QtWidgets
        PYSIDE_VERSION = 2
    except ImportError:
        PYSIDE_VERSION = None


# ============================================================================
# ANNOTATION PRESETS
# ============================================================================

ANNOTATION_PRESETS = {
    # Locomotion Presets
    "Walk Cycle": {
        "description": "Standard walking animation with footsteps",
        "annotations": [
            {"position": "frameX", "text": "FootLeft"},
            {"position": "frameX2", "text": "FootRight"},
        ]
    },
    "Run Cycle": {
        "description": "Running animation with footsteps",
        "annotations": [
            {"position": "frameX", "text": "FootLeft"},
            {"position": "frameX2", "text": "FootRight"},
        ]
    },
    "Sprint Cycle": {
        "description": "Sprinting animation with footsteps",
        "annotations": [
            {"position": "frameX", "text": "FootLeft"},
            {"position": "frameX2", "text": "FootRight"},
        ]
    },
    "Sneak Walk": {
        "description": "Sneaking walk with scuff sounds",
        "annotations": [
            {"position": "frameX", "text": "FootScuffLeft"},
            {"position": "frameX2", "text": "FootScuffRight"},
        ]
    },
    
    # Combat Presets
    "Weapon Swing": {
        "description": "Melee weapon swing animation",
        "annotations": [
            {"position": "frameX", "text": "weaponSwing"},
            {"position": "frameX2", "text": "SoundPlay.WPNSwingBlade"},
        ]
    },
    "Weapon Draw": {
        "description": "Draw weapon from sheath",
        "annotations": [
            {"position": "frameX", "text": "weaponDraw"},
        ]
    },
    "Weapon Sheathe": {
        "description": "Sheathe weapon",
        "annotations": [
            {"position": "frameX", "text": "weaponSheathe"},
        ]
    },
    "Block Start": {
        "description": "Start blocking with shield/weapon",
        "annotations": [
            {"position": "frameX", "text": "blockStart"},
        ]
    },
    "Block Stop": {
        "description": "Stop blocking",
        "annotations": [
            {"position": "frameX", "text": "blockStop"},
        ]
    },
    "Bow Draw": {
        "description": "Draw bow string",
        "annotations": [
            {"position": "frameX", "text": "bowDraw"},
        ]
    },
    "Bow Release": {
        "description": "Release arrow",
        "annotations": [
            {"position": "frameX", "text": "bowRelease"},
        ]
    },
    
    # MCO/DAR Style
    "MCO Attack": {
        "description": "MCO-style melee attack",
        "annotations": [
            {"position": "frame0", "text": "MCO_WinOpen"},
            {"position": "frameX", "text": "MCO_AttackInitiate"},
            {"position": "frameX2", "text": "MCO_WinClose"},
            {"position": "frameLast", "text": "MCO_Recovery"},
        ]
    },
    "MCO Combo": {
        "description": "MCO combo attack transition",
        "annotations": [
            {"position": "frame0", "text": "MCO_WinOpen"},
            {"position": "frameX", "text": "MCO_AttackInitiate"},
            {"position": "frameX2", "text": "MCO_TransitionOpen"},
            {"position": "frameX3", "text": "MCO_WinClose"},
        ]
    },
    
    # Interaction Presets
    "Pickup Item": {
        "description": "Pick up item from ground",
        "annotations": [
            {"position": "frameX", "text": "Grab"},
        ]
    },
    "Activate": {
        "description": "Activate object (lever, button, etc.)",
        "annotations": [
            {"position": "frameX", "text": "Activate"},
        ]
    },
    
    # Magic Presets
    "Cast Start": {
        "description": "Start casting spell",
        "annotations": [
            {"position": "frameX", "text": "CastStart"},
        ]
    },
    "Cast Release": {
        "description": "Release spell",
        "annotations": [
            {"position": "frameX", "text": "CastRelease"},
        ]
    },
    
    # Custom Sound
    "Custom Sound": {
        "description": "Play a custom sound file",
        "annotations": [
            {"position": "frameX", "text": "SoundPlay.YourSoundHere"},
        ]
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def log_message(message):
    """Log a message - prints to Script Editor"""
    msg = "[Skyrim Annotations] " + str(message)
    print(msg)
    # Force flush to ensure it shows immediately
    sys.stdout.flush()


def get_custom_presets_dir():
    """Get the path to custom annotation presets directory"""
    user_docs = os.path.expanduser("~")
    return os.path.join(user_docs, "Documents", "maya", "scripts", "skyrim_annotation_presets")


def load_custom_presets():
    """Load custom annotation presets from JSON files"""
    custom_presets = {}
    presets_dir = get_custom_presets_dir()
    
    if not os.path.exists(presets_dir):
        try:
            os.makedirs(presets_dir)
        except:
            pass
        return custom_presets
    
    for filename in os.listdir(presets_dir):
        if filename.endswith(".json"):
            try:
                filepath = os.path.join(presets_dir, filename)
                with open(filepath, 'r') as f:
                    preset_data = json.load(f)
                preset_name = os.path.splitext(filename)[0]
                custom_presets[preset_name] = preset_data
            except Exception as e:
                log_message("Error loading preset %s: %s" % (filename, str(e)))
    
    return custom_presets


def save_custom_preset(name, preset_data):
    """Save a custom preset to JSON file"""
    presets_dir = get_custom_presets_dir()
    if not os.path.exists(presets_dir):
        os.makedirs(presets_dir)
    
    filepath = os.path.join(presets_dir, "%s.json" % name)
    with open(filepath, 'w') as f:
        json.dump(preset_data, f, indent=4)
    
    return filepath


def delete_custom_preset(name):
    """Delete a custom preset file"""
    filepath = os.path.join(get_custom_presets_dir(), "%s.json" % name)
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False


def get_maya_bookmarks():
    """
    Get all timeline bookmarks from Maya.
    Returns list of {'frame': float, 'text': str} dictionaries.
    """
    bookmarks = []
    
    # Method 1: Try Maya 2025+ timeSliderBookmark plugin
    try:
        plugin_loaded = False
        try:
            plugin_loaded = cmds.pluginInfo("timeSliderBookmark", query=True, loaded=True)
        except:
            pass
        
        if not plugin_loaded:
            try:
                cmds.loadPlugin("timeSliderBookmark")
                plugin_loaded = True
            except:
                pass
        
        if plugin_loaded:
            try:
                from maya.plugin.timeSliderBookmark import timeSliderBookmark as tsbm
                
                bookmark_names = tsbm.getAllBookmarks()
                
                if bookmark_names:
                    for bm_node in bookmark_names:
                        try:
                            # Get start frame using getBookmarkStartEnd
                            if hasattr(tsbm, 'getBookmarkStartEnd'):
                                start_end = tsbm.getBookmarkStartEnd(bm_node)
                                if start_end and len(start_end) >= 1:
                                    bm_frame = start_end[0]  # Use only start frame
                                    
                                    # Get the bookmark's name attribute
                                    bm_text = bm_node
                                    if cmds.objExists(bm_node):
                                        if cmds.attributeQuery("name", node=bm_node, exists=True):
                                            bm_text = cmds.getAttr(bm_node + ".name") or bm_node
                                    
                                    bookmarks.append({'frame': float(bm_frame), 'text': str(bm_text)})
                                    continue
                            
                            # Fallback: Query node directly
                            if cmds.objExists(bm_node):
                                bm_frame = None
                                bm_text = bm_node
                                
                                for attr in ['timeRangeStart', 'startFrame', 'start']:
                                    if cmds.attributeQuery(attr, node=bm_node, exists=True):
                                        bm_frame = cmds.getAttr(bm_node + "." + attr)
                                        break
                                
                                if cmds.attributeQuery("name", node=bm_node, exists=True):
                                    bm_text = cmds.getAttr(bm_node + ".name") or bm_node
                                
                                if bm_frame is not None:
                                    bookmarks.append({'frame': float(bm_frame), 'text': str(bm_text)})
                                    
                        except Exception as e:
                            log_message("Error reading bookmark %s: %s" % (bm_node, str(e)))
                            continue
                    
                    if bookmarks:
                        log_message("Found %d bookmarks via timeSliderBookmark" % len(bookmarks))
                        return bookmarks
                    
            except ImportError:
                log_message("Could not import timeSliderBookmark API")
            except Exception as e:
                log_message("Error with timeSliderBookmark: %s" % str(e))
                
    except Exception as e:
        log_message("  Error with timeSliderBookmark plugin: %s" % str(e))
    
    # Method 2: Fallback to MEL timeline annotations (older Maya)
    try:
        timeline_control = mel.eval('$temp=$gPlayBackSlider')
        annotations = mel.eval('timeControl -q -ann %s' % timeline_control)
        
        if annotations and len(annotations) > 0:
            for i in range(0, len(annotations), 2):
                if i + 1 < len(annotations):
                    frame = float(annotations[i])
                    text = str(annotations[i + 1])
                    bookmarks.append({'frame': frame, 'text': text})
    except:
        pass
    
    return bookmarks


def create_maya_bookmark(frame, text):
    """Create a bookmark on Maya's timeline"""
    log_message("Creating bookmark: frame=%s, text='%s'" % (frame, text))
    
    try:
        # Try Maya 2025+ timeSliderBookmark plugin
        plugin_loaded = False
        try:
            plugin_loaded = cmds.pluginInfo("timeSliderBookmark", query=True, loaded=True)
        except:
            pass
        
        if not plugin_loaded:
            try:
                cmds.loadPlugin("timeSliderBookmark")
                plugin_loaded = True
                log_message("  Loaded timeSliderBookmark plugin")
            except Exception as e:
                log_message("  Could not load plugin: %s" % str(e))
        
        if plugin_loaded:
            try:
                from maya.plugin.timeSliderBookmark.timeSliderBookmark import createBookmark
                createBookmark(name=text, start=frame, stop=frame, color=(1, 0.8, 0))
                log_message("  Created bookmark via timeSliderBookmark API")
                return True
            except Exception as e:
                log_message("  timeSliderBookmark API error: %s" % str(e))
        
        # Fallback: MEL timeline annotation
        log_message("  Trying MEL fallback...")
        timeline_control = mel.eval('$temp=$gPlayBackSlider')
        mel.eval('timeControl -e -ann "%s" -at %f %s' % (text, frame, timeline_control))
        log_message("  Created annotation via MEL")
        return True
        
    except Exception as e:
        log_message("Error creating bookmark: %s" % str(e))
        return False


def clear_maya_bookmarks():
    """Clear all timeline bookmarks from Maya"""
    try:
        # Try Maya 2025+ timeSliderBookmark plugin
        if cmds.pluginInfo("timeSliderBookmark", query=True, loaded=True):
            try:
                from maya.plugin.timeSliderBookmark.timeSliderBookmark import getAllBookmarks, deleteBookmark
                bookmarks = getAllBookmarks()
                
                for bm in bookmarks:
                    try:
                        if hasattr(bm, 'name'):
                            deleteBookmark(bm.name)
                        elif isinstance(bm, dict) and 'name' in bm:
                            deleteBookmark(bm['name'])
                        elif isinstance(bm, str):
                            deleteBookmark(bm)
                    except:
                        continue
                return True
            except:
                pass
    except:
        pass
    
    return False


def debug_bookmarks():
    """
    Debug function - call this from Maya's Script Editor to test bookmark detection.
    Usage: import SkyrimAnnotationCreator; SkyrimAnnotationCreator.debug_bookmarks()
    """
    log_message("=" * 60)
    log_message("DEBUG: Testing bookmark detection")
    log_message("=" * 60)
    
    bookmarks = get_maya_bookmarks()
    
    log_message("")
    log_message("RESULT: Found %d bookmarks" % len(bookmarks))
    for i, bm in enumerate(bookmarks):
        log_message("  %d. Frame %s: '%s'" % (i+1, bm['frame'], bm['text']))
    
    log_message("=" * 60)
    
    # Also show a Maya warning so it's visible
    if bookmarks:
        cmds.warning("Found %d bookmarks - check Script Editor for details" % len(bookmarks))
    else:
        cmds.warning("No bookmarks found - check Script Editor for debug info")
    
    return bookmarks


def embed_annotations_in_hkx(hkx_path, fps, hkanno_path):
    """
    Embed Maya timeline bookmarks as annotations in the HKX file using hkanno64.
    
    Args:
        hkx_path: Path to the HKX file
        fps: Frames per second of the animation
        hkanno_path: Path to folder containing hkanno64.exe
    
    Returns:
        True if successful, False otherwise
    """
    if not hkanno_path:
        log_message("Skipping annotations: hkanno64 path not set")
        return False
    
    hkanno_exe = os.path.join(hkanno_path, "hkanno64.exe")
    if not os.path.exists(hkanno_exe):
        log_message("Skipping annotations: hkanno64.exe not found")
        return False
    
    # Get timeline bookmarks from Maya
    bookmarks = get_maya_bookmarks()
    
    if not bookmarks:
        log_message("No timeline bookmarks found to embed")
        return False
    
    log_message("Found %d timeline bookmarks to embed" % len(bookmarks))
    
    # Get animation start frame for offset calculation
    start_frame = cmds.playbackOptions(query=True, minTime=True)
    
    # Create anno.txt file
    anno_path = hkx_path.replace(".hkx", "_anno.txt")
    
    try:
        with open(anno_path, 'w') as f:
            f.write("# Maya timeline bookmarks\n")
            f.write("# Embedded by Skyrim HKX Exporter\n")
            
            for bm in sorted(bookmarks, key=lambda x: x['frame']):
                # Convert frame to time in seconds
                # Offset by start frame so annotations align with exported animation
                frame = bm['frame'] - start_frame
                time_seconds = frame / float(fps)
                
                # Ensure non-negative time
                if time_seconds < 0:
                    time_seconds = 0
                
                f.write("%f %s\n" % (time_seconds, bm['text']))
                log_message("  %.3fs: %s" % (time_seconds, bm['text']))
        
        # Run hkanno64 to update the HKX
        log_message("Running hkanno64 to embed annotations...")
        
        cmd = [hkanno_exe, "update", "-i", anno_path, hkx_path]
        
        startupinfo = None
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=hkanno_path,
            startupinfo=startupinfo,
            timeout=30
        )
        
        if result.returncode == 0:
            log_message("✓ Annotations embedded successfully")
            # Clean up anno.txt
            try:
                os.remove(anno_path)
            except:
                pass
            return True
        else:
            log_message("✗ hkanno64 failed: %s" % (result.stderr or result.stdout or "Unknown error"))
            return False
            
    except Exception as e:
        log_message("✗ Error embedding annotations: %s" % str(e))
        return False


# ============================================================================
# ANNOTATION CREATOR DIALOG
# ============================================================================

class SkyrimAnnotationCreator(QtWidgets.QDialog):
    """Dialog for creating Skyrim animation annotations/bookmarks"""
    
    def __init__(self, parent=None):
        super(SkyrimAnnotationCreator, self).__init__(parent)
        self.setWindowTitle("Skyrim Animation Annotation Creator")
        self.setMinimumSize(550, 600)
        self.resize(550, 650)
        
        # Remove help button
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        
        # Load presets
        self.builtin_presets = ANNOTATION_PRESETS.copy()
        self.custom_presets = load_custom_presets()
        self.all_presets = {**self.builtin_presets, **self.custom_presets}
        
        self.create_ui()
        self.update_preset_info()
    
    def create_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Title
        title = QtWidgets.QLabel("<h2 style='color: #FFA500;'>Skyrim Animation Annotations</h2>")
        layout.addWidget(title)
        
        # Custom preset buttons
        preset_btn_layout = QtWidgets.QHBoxLayout()
        self.create_preset_btn = QtWidgets.QPushButton("Create Custom Preset")
        self.create_preset_btn.clicked.connect(self.create_custom_preset)
        self.delete_preset_btn = QtWidgets.QPushButton("Delete Custom Preset")
        self.delete_preset_btn.clicked.connect(self.delete_custom_preset_action)
        self.delete_preset_btn.setEnabled(False)
        preset_btn_layout.addWidget(self.create_preset_btn)
        preset_btn_layout.addWidget(self.delete_preset_btn)
        layout.addLayout(preset_btn_layout)
        
        # Preset selection
        preset_layout = QtWidgets.QHBoxLayout()
        preset_layout.addWidget(QtWidgets.QLabel("Preset:"))
        self.preset_combo = QtWidgets.QComboBox()
        self.update_preset_combo()
        self.preset_combo.currentIndexChanged.connect(self.on_preset_changed)
        preset_layout.addWidget(self.preset_combo, 1)
        layout.addLayout(preset_layout)
        
        # Mode selection
        mode_layout = QtWidgets.QHBoxLayout()
        mode_layout.addWidget(QtWidgets.QLabel("Mode:"))
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("Clear Existing Bookmarks")
        self.mode_combo.addItem("Add to Existing Bookmarks")
        mode_layout.addWidget(self.mode_combo, 1)
        layout.addLayout(mode_layout)
        
        # Frame positions
        frame_group = QtWidgets.QGroupBox("Frame Positions")
        frame_layout = QtWidgets.QGridLayout(frame_group)
        
        frame_layout.addWidget(QtWidgets.QLabel("Frame X:"), 0, 0)
        self.frame_x_spin = QtWidgets.QSpinBox()
        self.frame_x_spin.setRange(0, 9999)
        self.frame_x_spin.setValue(5)
        self.frame_x_spin.setToolTip("Primary annotation frame (e.g., first footstep)")
        frame_layout.addWidget(self.frame_x_spin, 0, 1)
        
        frame_layout.addWidget(QtWidgets.QLabel("Frame X2:"), 0, 2)
        self.frame_x2_spin = QtWidgets.QSpinBox()
        self.frame_x2_spin.setRange(0, 9999)
        self.frame_x2_spin.setValue(15)
        self.frame_x2_spin.setToolTip("Secondary annotation frame (e.g., second footstep)")
        frame_layout.addWidget(self.frame_x2_spin, 0, 3)
        
        frame_layout.addWidget(QtWidgets.QLabel("Frame X3:"), 1, 0)
        self.frame_x3_spin = QtWidgets.QSpinBox()
        self.frame_x3_spin.setRange(0, 9999)
        self.frame_x3_spin.setValue(25)
        self.frame_x3_spin.setToolTip("Tertiary annotation frame (optional)")
        frame_layout.addWidget(self.frame_x3_spin, 1, 1)
        
        layout.addWidget(frame_group)
        
        # Preset info display
        info_group = QtWidgets.QGroupBox("Preset Information")
        info_layout = QtWidgets.QVBoxLayout(info_group)
        self.info_text = QtWidgets.QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(200)
        self.info_text.setStyleSheet("background-color: #2A2A2A; color: #E0E0E0;")
        info_layout.addWidget(self.info_text)
        layout.addWidget(info_group)
        
        # Manual annotation entry
        manual_group = QtWidgets.QGroupBox("Add Manual Annotation")
        manual_layout = QtWidgets.QHBoxLayout(manual_group)
        
        manual_layout.addWidget(QtWidgets.QLabel("Frame:"))
        self.manual_frame_spin = QtWidgets.QSpinBox()
        self.manual_frame_spin.setRange(0, 99999)
        manual_layout.addWidget(self.manual_frame_spin)
        
        manual_layout.addWidget(QtWidgets.QLabel("Text:"))
        self.manual_text_edit = QtWidgets.QLineEdit()
        self.manual_text_edit.setPlaceholderText("e.g., FootLeft, weaponSwing...")
        manual_layout.addWidget(self.manual_text_edit, 1)
        
        add_btn = QtWidgets.QPushButton("Add")
        add_btn.clicked.connect(self.add_manual_annotation)
        manual_layout.addWidget(add_btn)
        
        layout.addWidget(manual_group)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        
        help_btn = QtWidgets.QPushButton("Help")
        help_btn.clicked.connect(self.show_help)
        btn_layout.addWidget(help_btn)
        
        btn_layout.addStretch()
        
        create_btn = QtWidgets.QPushButton("Create Annotations")
        create_btn.setDefault(True)
        create_btn.clicked.connect(self.create_annotations)
        btn_layout.addWidget(create_btn)
        
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def update_preset_combo(self):
        """Update the preset dropdown"""
        self.preset_combo.clear()
        
        # Separate built-in and custom presets
        builtin_names = sorted(self.builtin_presets.keys())
        custom_names = sorted(self.custom_presets.keys())
        
        # Add built-in presets
        for name in builtin_names:
            self.preset_combo.addItem(name, "builtin")
        
        # Add separator and custom presets
        if custom_names:
            self.preset_combo.insertSeparator(self.preset_combo.count())
            for name in custom_names:
                self.preset_combo.addItem(name + " (Custom)", "custom")
    
    def on_preset_changed(self):
        """Handle preset selection change"""
        self.update_preset_info()
        
        # Enable delete button only for custom presets
        preset_type = self.preset_combo.currentData()
        self.delete_preset_btn.setEnabled(preset_type == "custom")
    
    def update_preset_info(self):
        """Update the preset information display"""
        preset_name = self.preset_combo.currentText().replace(" (Custom)", "")
        preset_data = self.all_presets.get(preset_name, {})
        
        html = "<h3 style='color: #FFA500;'>%s</h3>" % preset_name
        
        desc = preset_data.get("description", "")
        if desc:
            html += "<p>%s</p>" % desc
        
        html += "<p><b>Annotations:</b></p><ul>"
        for anno in preset_data.get("annotations", []):
            html += "<li><b>%s:</b> %s</li>" % (anno.get("position", "?"), anno.get("text", ""))
        html += "</ul>"
        
        # Check if it's a custom preset
        if preset_name in self.custom_presets:
            html += "<p style='color: #90EE90;'><i>Custom Preset</i></p>"
        
        self.info_text.setHtml(html)
    
    def calculate_frame(self, position):
        """Calculate actual frame number from position string"""
        start_frame = cmds.playbackOptions(query=True, minTime=True)
        end_frame = cmds.playbackOptions(query=True, maxTime=True)
        
        if position == "frame0":
            return start_frame
        elif position == "frame1":
            return start_frame + 1
        elif position == "frameX":
            return start_frame + self.frame_x_spin.value()
        elif position == "frameX2":
            return start_frame + self.frame_x2_spin.value()
        elif position == "frameX3":
            return start_frame + self.frame_x3_spin.value()
        elif position == "frameLast":
            return end_frame
        elif position == "frameLast-1":
            return end_frame - 1
        elif "frameX+" in position:
            offset = int(position.split("+")[1])
            return start_frame + self.frame_x_spin.value() + offset
        elif "frameLast-" in position:
            offset = int(position.split("-")[1])
            return end_frame - offset
        else:
            return start_frame
    
    def create_annotations(self):
        """Create annotations based on selected preset"""
        preset_name = self.preset_combo.currentText().replace(" (Custom)", "")
        preset_data = self.all_presets.get(preset_name, {})
        
        if not preset_data:
            QtWidgets.QMessageBox.warning(self, "Error", "No preset data found")
            return
        
        # Clear existing if requested
        if self.mode_combo.currentIndex() == 0:
            clear_maya_bookmarks()
        
        # Create annotations
        count = 0
        for anno in preset_data.get("annotations", []):
            frame = self.calculate_frame(anno.get("position", "frame0"))
            text = anno.get("text", "")
            
            if text and create_maya_bookmark(frame, text):
                count += 1
        
        cmds.inViewMessage(
            assistMessage="Created %d annotations from '%s'" % (count, preset_name),
            position='topCenter',
            fade=True,
            fadeOutTime=2000
        )
    
    def add_manual_annotation(self):
        """Add a single manual annotation"""
        frame = self.manual_frame_spin.value()
        text = self.manual_text_edit.text().strip()
        
        if not text:
            QtWidgets.QMessageBox.warning(self, "Error", "Please enter annotation text")
            return
        
        if create_maya_bookmark(frame, text):
            cmds.inViewMessage(
                assistMessage="Added annotation '%s' at frame %d" % (text, frame),
                position='topCenter',
                fade=True,
                fadeOutTime=2000
            )
            self.manual_text_edit.clear()
    
    def create_custom_preset(self):
        """Create a new custom preset"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Create Custom Preset")
        dialog.setMinimumSize(500, 500)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Name
        name_layout = QtWidgets.QHBoxLayout()
        name_layout.addWidget(QtWidgets.QLabel("Preset Name:"))
        name_edit = QtWidgets.QLineEdit()
        name_layout.addWidget(name_edit)
        layout.addLayout(name_layout)
        
        # Description
        desc_layout = QtWidgets.QHBoxLayout()
        desc_layout.addWidget(QtWidgets.QLabel("Description:"))
        desc_edit = QtWidgets.QLineEdit()
        desc_layout.addWidget(desc_edit)
        layout.addLayout(desc_layout)
        
        # Annotations table
        layout.addWidget(QtWidgets.QLabel("Annotations:"))
        table = QtWidgets.QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Position", "Text"])
        table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        table.setRowCount(6)
        layout.addWidget(table)
        
        # Add row button
        add_row_btn = QtWidgets.QPushButton("Add Row")
        add_row_btn.clicked.connect(lambda: table.setRowCount(table.rowCount() + 1))
        layout.addWidget(add_row_btn)
        
        # Help text
        help_text = QtWidgets.QLabel(
            "<small>Position formats: frame0, frame1, frameX, frameX2, frameX3, frameLast, frameLast-1<br>"
            "Common annotations: FootLeft, FootRight, weaponSwing, weaponSheathe, SoundPlay.xxx</small>"
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        save_btn = QtWidgets.QPushButton("Save")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        cancel_btn.clicked.connect(dialog.reject)
        
        def do_save():
            name = name_edit.text().strip()
            if not name:
                QtWidgets.QMessageBox.warning(dialog, "Error", "Please enter a preset name")
                return
            
            if name in self.builtin_presets:
                QtWidgets.QMessageBox.warning(dialog, "Error", "Cannot overwrite built-in preset")
                return
            
            annotations = []
            for row in range(table.rowCount()):
                pos_item = table.item(row, 0)
                text_item = table.item(row, 1)
                if pos_item and text_item and pos_item.text() and text_item.text():
                    annotations.append({
                        "position": pos_item.text(),
                        "text": text_item.text()
                    })
            
            if not annotations:
                QtWidgets.QMessageBox.warning(dialog, "Error", "Please add at least one annotation")
                return
            
            preset_data = {
                "description": desc_edit.text().strip(),
                "annotations": annotations
            }
            
            # Save to file
            save_custom_preset(name, preset_data)
            
            # Update presets
            self.custom_presets[name] = preset_data
            self.all_presets = {**self.builtin_presets, **self.custom_presets}
            self.update_preset_combo()
            
            dialog.accept()
            cmds.inViewMessage(
                assistMessage="Created custom preset: %s" % name,
                position='topCenter',
                fade=True,
                fadeOutTime=2000
            )
        
        save_btn.clicked.connect(do_save)
        dialog.exec_()
    
    def delete_custom_preset_action(self):
        """Delete the selected custom preset"""
        preset_name = self.preset_combo.currentText().replace(" (Custom)", "")
        
        if preset_name not in self.custom_presets:
            return
        
        confirm = QtWidgets.QMessageBox.question(
            self, "Confirm Delete",
            "Delete custom preset '%s'?" % preset_name,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if confirm == QtWidgets.QMessageBox.Yes:
            delete_custom_preset(preset_name)
            del self.custom_presets[preset_name]
            self.all_presets = {**self.builtin_presets, **self.custom_presets}
            self.update_preset_combo()
    
    def show_help(self):
        """Show help dialog"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Skyrim Annotation Help")
        dialog.setMinimumSize(500, 400)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        text = QtWidgets.QTextBrowser()
        text.setOpenExternalLinks(True)
        text.setHtml("""
        <h2 style='color: #FFA500;'>Skyrim Animation Annotations</h2>
        
        <h3>What are Annotations?</h3>
        <p>Annotations are markers embedded in HKX animation files that tell Skyrim's 
        engine when to trigger specific events during animation playback, such as:</p>
        <ul>
            <li>Footstep sounds (FootLeft, FootRight)</li>
            <li>Weapon swoosh sounds (weaponSwing)</li>
            <li>Weapon draw/sheathe events</li>
            <li>Custom sound playback</li>
            <li>MCO/DAR combat events</li>
        </ul>
        
        <h3>How to Use</h3>
        <ol>
            <li>Select a preset that matches your animation type</li>
            <li>Adjust Frame X/X2/X3 positions to match key moments in your animation</li>
            <li>Click "Create Annotations" to add bookmarks to Maya's timeline</li>
            <li>When you export, annotations will be embedded into the HKX file</li>
        </ol>
        
        <h3>Frame Position Reference</h3>
        <ul>
            <li><b>frame0:</b> First frame of animation</li>
            <li><b>frameX:</b> Primary event frame (use for first footstep, swing start, etc.)</li>
            <li><b>frameX2:</b> Secondary event frame (second footstep, hit frame, etc.)</li>
            <li><b>frameX3:</b> Tertiary event frame (recovery, end of combo, etc.)</li>
            <li><b>frameLast:</b> Last frame of animation</li>
        </ul>
        
        <h3>Common Annotation Types</h3>
        <ul>
            <li><b>FootLeft, FootRight:</b> Normal footstep sounds</li>
            <li><b>FootScuffLeft, FootScuffRight:</b> Sneaking footstep sounds</li>
            <li><b>weaponSwing:</b> Melee weapon swing sound</li>
            <li><b>weaponDraw, weaponSheathe:</b> Draw/sheathe events</li>
            <li><b>SoundPlay.xxx:</b> Play custom sound (replace xxx with sound path)</li>
        </ul>
        """)
        layout.addWidget(text)
        
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec_()


def show_annotation_creator(parent=None):
    """Show the annotation creator dialog (standalone entry point)"""
    dialog = SkyrimAnnotationCreator(parent)
    dialog.exec_()
    return dialog


# For standalone testing
if __name__ == "__main__":
    show_annotation_creator()

