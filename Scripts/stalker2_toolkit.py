#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
S.T.A.L.K.E.R. 2 Toolkit - Main UI
Compatible with Maya 2022+ (Python 3, PySide6) and Maya 2022- (Python 2, PySide2)

A comprehensive toolkit for S.T.A.L.K.E.R. 2 modding workflows in Maya.
"""

import os
import sys

# Maya imports
import maya.cmds as cmds

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
    from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, 
                                   QLabel, QPushButton, QMessageBox, QFrame, QScrollArea, QWidget, QSizePolicy)
    from PySide6.QtCore import Qt, QSize
    from PySide6.QtGui import QFont, QIcon
    from shiboken6 import wrapInstance
    pyside_version = 6
except ImportError:
    try:
        # Maya 2022 and earlier (PySide2)
        from PySide2.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, 
                                       QLabel, QPushButton, QMessageBox, QFrame, QScrollArea, QWidget, QSizePolicy)
        from PySide2.QtCore import Qt, QSize
        from PySide2.QtGui import QFont, QIcon
        from shiboken2 import wrapInstance
        pyside_version = 2
    except ImportError:
        print("Error: Could not import PySide. Please ensure Maya is running.")
        pyside_version = None

if pyside_version:
    import maya.OpenMayaUI as omui


class STALKER2ToolkitDialog(QDialog):
    def __init__(self, parent=None):
        super(STALKER2ToolkitDialog, self).__init__(parent)
        self.setWindowTitle("S.T.A.L.K.E.R. 2 Toolkit")
        # 40% bigger than original (400x500 -> 560x700)
        self.setMinimumSize(560, 700)
        self.resize(560, 700)  # Set default size
        # No maximum size restriction - user can resize as much as they want
        self.setup_ui()
        self.setup_dark_style()
    
    def setup_dark_style(self):
        """Apply dark theme styling consistent with S.T.A.L.K.E.R. 2 aesthetic"""
        dark_style = """
        QDialog {
            background-color: #1a1a1a;
            color: #e0e0e0;
            border: 2px solid #333333;
        }
        QLabel {
            color: #e0e0e0;
            font-size: 12px;
        }
        .title-label {
            color: #ffffff;
            font-size: 18px;
            font-weight: bold;
            padding: 10px;
            background-color: #2a2a2a;
            border: 1px solid #444444;
            border-radius: 6px;
        }
        .section-label {
            color: #cccccc;
            font-size: 14px;
            font-weight: bold;
            padding: 8px 4px;
            background-color: #252525;
            border-left: 3px solid #0078d4;
        }
        QPushButton {
            background-color: #2d2d2d;
            color: #ffffff;
            border: 1px solid #555555;
            padding: 12px 16px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: bold;
            text-align: left;
        }
        QPushButton:hover {
            background-color: #3a3a3a;
            border: 1px solid #0078d4;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #1a1a1a;
            border: 1px solid #0078d4;
        }
        .tool-button {
            background-color: #2d2d2d;
            color: #ffffff;
            border: 1px solid #555555;
            padding: 12px 15px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: bold;
            min-height: 60px;
            text-align: left;
            white-space: pre-line;
        }
        .tool-button:hover {
            background-color: #0078d4;
            border: 1px solid #106ebe;
        }
        .tool-button:pressed {
            background-color: #005a9e;
        }
        .about-button {
            background-color: #404040;
            color: #cccccc;
            border: 1px solid #555555;
            padding: 8px 16px;
            border-radius: 4px;
            font-size: 11px;
        }
        .about-button:hover {
            background-color: #505050;
            color: #ffffff;
        }
        QFrame {
            background-color: #222222;
            border: 1px solid #333333;
            border-radius: 4px;
        }
        QScrollArea {
            background-color: #1a1a1a;
            border: none;
        }
        QScrollArea QWidget {
            background-color: #1a1a1a;
        }
        """
        self.setStyleSheet(dark_style)
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title section
        title_label = QLabel("S.T.A.L.K.E.R. 2 Toolkit")
        title_label.setProperty("class", "title-label")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Version info
        version_label = QLabel("Version 1.0 - Maya Modding Tools")
        version_label.setStyleSheet("color: #888888; font-size: 10px; margin-bottom: 10px;")
        version_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(version_label)
        
        # Create scroll area for tools
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        # PySide version compatibility for scroll bar policies
        if pyside_version == 6:
            # PySide6 uses Qt.ScrollBarPolicy enum
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        else:
            # PySide2 uses direct Qt attributes
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(10)
        
        # Material Tools Section
        material_section = self.create_section("Material Tools", [
            ("Material-Texture Matcher", "Automatically assign textures to materials\nwith game-ready settings and advanced options", self.launch_material_texture_matcher),
        ])
        scroll_layout.addWidget(material_section)
        
        # Weapon Tools Section
        weapon_section = self.create_section("Weapon Tools", [
            ("Weapon Importer", "Import weapon skeletons and constrain\nunskinned meshes to joints automatically", self.launch_weapon_importer),
            ("Weapon Rig Tool", "Create control curves for rigged weapons\nwith automatic joint-mesh analysis", self.launch_weapon_rig_tool),
        ])
        scroll_layout.addWidget(weapon_section)
        
        # Placeholder for future tools
        future_section = self.create_section("Coming Soon", [
            ("UV Tools", "UV mapping and optimization utilities\n(Coming in next update)", None),
            ("Mesh Utilities", "Mesh processing and validation tools\n(Coming in next update)", None),
            ("Animation Tools", "Animation import/export helpers\n(Coming in next update)", None),
        ])
        scroll_layout.addWidget(future_section)
        
        # Add stretch to push everything up
        scroll_layout.addStretch()
        
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)
        
        # Bottom buttons
        bottom_layout = QHBoxLayout()
        
        # About button
        about_btn = QPushButton("About")
        about_btn.setProperty("class", "about-button")
        about_btn.clicked.connect(self.show_about)
        bottom_layout.addWidget(about_btn)
        
        # Uninstall button
        uninstall_btn = QPushButton("Uninstall")
        uninstall_btn.setProperty("class", "about-button")
        uninstall_btn.clicked.connect(self.uninstall_toolkit)
        uninstall_btn.setStyleSheet("""
            QPushButton {
                background-color: #8B4513;
                color: #ffffff;
                border: 1px solid #A0522D;
            }
            QPushButton:hover {
                background-color: #A0522D;
                color: #ffffff;
            }
        """)
        bottom_layout.addWidget(uninstall_btn)
        
        bottom_layout.addStretch()
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.setProperty("class", "about-button")
        close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(close_btn)
        
        main_layout.addLayout(bottom_layout)
    
    def create_section(self, title, tools):
        """Create a section with tools"""
        section_frame = QFrame()
        section_layout = QVBoxLayout(section_frame)
        section_layout.setContentsMargins(15, 15, 15, 15)
        section_layout.setSpacing(10)
        
        # Section title
        section_label = QLabel(title)
        section_label.setProperty("class", "section-label")
        section_layout.addWidget(section_label)
        
        # Tool buttons
        for tool_name, description, callback in tools:
            tool_btn = QPushButton()
            tool_btn.setText(tool_name + "\n" + description)
            tool_btn.setProperty("class", "tool-button")
            
            # Set size policy with PySide version compatibility
            if pyside_version == 6:
                # PySide6 uses Policy enum
                tool_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            else:
                # PySide2 uses direct attributes
                tool_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            
            if callback:
                tool_btn.clicked.connect(callback)
            else:
                tool_btn.setEnabled(False)
                tool_btn.setStyleSheet("""
                    QPushButton:disabled {
                        background-color: #1a1a1a;
                        color: #666666;
                        border: 1px solid #333333;
                    }
                """)
            
            section_layout.addWidget(tool_btn)
        
        return section_frame
    
    def launch_material_texture_matcher(self):
        """Launch the Material-Texture Matcher tool"""
        try:
            # Import and run the material texture matcher
            script_dir = os.path.dirname(os.path.abspath(__file__))
            matcher_script = os.path.join(script_dir, "material_texture_matcher.py")
            
            if os.path.exists(matcher_script):
                # Execute the script in the current namespace
                with open(matcher_script, 'r') as f:
                    script_content = f.read()
                
                # Create a clean namespace for execution
                namespace = {
                    '__name__': 'material_texture_matcher',
                    '__file__': matcher_script,
                    'cmds': cmds,  # Add cmds to namespace
                    'sys': sys,    # Add sys to namespace
                    'os': os       # Add os to namespace
                }
                
                # Execute the script
                exec(compile(script_content, matcher_script, 'exec'), namespace)
                
                # Call the main function
                if 'show_material_texture_matcher' in namespace:
                    namespace['show_material_texture_matcher']()
                    # Close the main toolkit UI after launching the tool
                    self.close()
                else:
                    QMessageBox.warning(self, "Error", "Could not find the main function in the Material-Texture Matcher script.")
            else:
                QMessageBox.warning(self, "Error", "Material-Texture Matcher script not found.\nExpected location: " + matcher_script)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", "Failed to launch Material-Texture Matcher:\n" + str(e))
    
    def launch_weapon_importer(self):
        """Launch the Weapon Importer tool"""
        try:
            # Import and run the weapon importer
            script_dir = os.path.dirname(os.path.abspath(__file__))
            importer_script = os.path.join(script_dir, "weapon_importer.py")
            
            if os.path.exists(importer_script):
                # Execute the script in the current namespace
                with open(importer_script, 'r') as f:
                    script_content = f.read()
                
                # Create a clean namespace for execution
                namespace = {
                    '__name__': 'weapon_importer',
                    '__file__': importer_script,
                    'cmds': cmds,  # Add cmds to namespace
                    'sys': sys,    # Add sys to namespace
                    'os': os       # Add os to namespace
                }
                
                # Execute the script
                exec(compile(script_content, importer_script, 'exec'), namespace)
                
                # Call the main function
                if 'show_weapon_importer' in namespace:
                    namespace['show_weapon_importer']()
                    # Close the main toolkit UI after launching the tool
                    self.close()
                else:
                    QMessageBox.warning(self, "Error", "Could not find the main function in the Weapon Importer script.")
            else:
                QMessageBox.warning(self, "Error", "Weapon Importer script not found.\nExpected location: " + importer_script)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", "Failed to launch Weapon Importer:\n" + str(e))
    
    def launch_weapon_rig_tool(self):
        """Launch the Weapon Rig Tool"""
        try:
            # Import and run the weapon rig tool
            script_dir = os.path.dirname(os.path.abspath(__file__))
            rig_tool_script = os.path.join(script_dir, "weapon_rig_tool.py")
            
            if os.path.exists(rig_tool_script):
                # Execute the script in the current namespace
                with open(rig_tool_script, 'r') as f:
                    script_content = f.read()
                
                # Create a clean namespace for execution
                namespace = {
                    '__name__': 'weapon_rig_tool',
                    '__file__': rig_tool_script,
                    'cmds': cmds,  # Add cmds to namespace
                    'sys': sys,    # Add sys to namespace
                    'os': os       # Add os to namespace
                }
                
                # Execute the script
                exec(compile(script_content, rig_tool_script, 'exec'), namespace)
                
                # Call the main function
                if 'show_weapon_rig_tool' in namespace:
                    namespace['show_weapon_rig_tool']()
                    # Close the main toolkit UI after launching the tool
                    self.close()
                else:
                    QMessageBox.warning(self, "Error", "Could not find the main function in the Weapon Rig Tool script.")
            else:
                QMessageBox.warning(self, "Error", "Weapon Rig Tool script not found.\nExpected location: " + rig_tool_script)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", "Failed to launch Weapon Rig Tool:\n" + str(e))
    
    def uninstall_toolkit(self):
        """Uninstall the S.T.A.L.K.E.R. 2 Toolkit"""
        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            "Uninstall S.T.A.L.K.E.R. 2 Toolkit",
            "Are you sure you want to uninstall S.T.A.L.K.E.R. 2 Toolkit?\n\n"
            "This will remove:\n"
            "- All toolkit files from Maya's scripts directory\n"
            "- The STALKER2 shelf button\n"
            "- Custom S.T.A.L.K.E.R. 2 icon from Maya's icons directory\n"
            "- Python path entries\n\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                import shutil
                import sys
                import maya.mel as mel
                
                # Get installation directory
                maya_app_dir = cmds.internalVar(userAppDir=True)
                install_dir = os.path.join(maya_app_dir, "scripts", "STALKER2_Toolkit")
                
                # Get Maya version for icon path
                maya_version = cmds.about(version=True)
                version_parts = maya_version.split(' ')
                major_version = version_parts[0]
                icons_dir = os.path.join(maya_app_dir, major_version, "prefs", "icons")
                custom_icon_path = os.path.join(icons_dir, "STALKER2_Icon.png")
                
                success_messages = []
                error_messages = []
                
                # Remove installation directory
                if os.path.exists(install_dir):
                    try:
                        shutil.rmtree(install_dir)
                        success_messages.append("Removed toolkit files")
                    except Exception as e:
                        error_messages.append("Failed to remove files: " + str(e))
                else:
                    success_messages.append("No installation files found (already removed)")
                
                # Remove custom icon
                if os.path.exists(custom_icon_path):
                    try:
                        os.remove(custom_icon_path)
                        success_messages.append("Removed custom S.T.A.L.K.E.R. 2 icon")
                    except Exception as e:
                        error_messages.append("Failed to remove custom icon: " + str(e))
                else:
                    success_messages.append("No custom icon found (already removed)")
                
                # Remove shelf button using comprehensive detection
                try:
                    current_shelf = cmds.tabLayout(mel.eval('$gShelfTopLevel=$gShelfTopLevel'), query=True, selectTab=True)
                    shelf_buttons = cmds.shelfLayout(current_shelf, query=True, childArray=True) or []
                    
                    removed_buttons = []
                    for button in shelf_buttons:
                        try:
                            # Get button label and annotation to identify STALKER2 buttons
                            label = cmds.shelfButton(button, query=True, label=True) or ""
                            annotation = cmds.shelfButton(button, query=True, annotation=True) or ""
                            
                            # Check if this is a STALKER2 button using multiple criteria
                            if (('STALKER2' in label) or 
                                ('STALKER' in annotation) or 
                                ('S.T.A.L.K.E.R. 2 Toolkit' in annotation) or
                                button.startswith('STALKER2')):
                                cmds.deleteUI(button)
                                removed_buttons.append(button)
                                
                        except:
                            # Button might not be a shelf button or might have issues, skip
                            continue
                    
                    if removed_buttons:
                        success_messages.append("Removed shelf button(s): " + ", ".join(removed_buttons))
                    else:
                        success_messages.append("No shelf buttons found (already removed)")
                        
                except Exception as e:
                    error_messages.append("Failed to remove shelf button: " + str(e))
                
                # Remove from Python path and clean modules
                try:
                    paths_removed = []
                    if install_dir in sys.path:
                        sys.path.remove(install_dir)
                        paths_removed.append(install_dir)
                    
                    scripts_dir = os.path.join(maya_app_dir, "scripts")
                    if scripts_dir in sys.path:
                        # Don't remove this as it's Maya's standard scripts directory
                        pass
                    
                    # Remove loaded modules to ensure clean reinstall
                    modules_to_remove = ['stalker2_toolkit', 'material_texture_matcher', 'weapon_importer', 'weapon_rig_tool']
                    removed_modules = []
                    for module_name in modules_to_remove:
                        if module_name in sys.modules:
                            del sys.modules[module_name]
                            removed_modules.append(module_name)
                    
                    if paths_removed or removed_modules:
                        msg_parts = []
                        if paths_removed:
                            msg_parts.append("Removed from Python path")
                        if removed_modules:
                            msg_parts.append("Cleared loaded modules: " + ", ".join(removed_modules))
                        success_messages.append("; ".join(msg_parts))
                    else:
                        success_messages.append("Python path and modules already clean")
                        
                except Exception as e:
                    error_messages.append("Failed to clean Python path/modules: " + str(e))
                
                # Show results
                if error_messages:
                    result_msg = "Uninstallation completed with some errors:\n\n"
                    result_msg += "SUCCESSFUL:\n- " + "\n- ".join(success_messages) + "\n\n"
                    result_msg += "ERRORS:\n- " + "\n- ".join(error_messages)
                    QMessageBox.warning(self, "Uninstall Complete (with errors)", result_msg)
                else:
                    result_msg = "S.T.A.L.K.E.R. 2 Toolkit successfully uninstalled!\n\n"
                    result_msg += "REMOVED:\n- " + "\n- ".join(success_messages) + "\n\n"
                    result_msg += "You can reinstall anytime by dragging the installer into Maya."
                    QMessageBox.information(self, "Uninstall Complete", result_msg)
                
                # Close the toolkit UI
                self.close()
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Uninstall Error",
                    "Failed to uninstall S.T.A.L.K.E.R. 2 Toolkit:\n\n" + str(e)
                )

    def show_about(self):
        """Show the About dialog"""
        about_text = """
<h2>S.T.A.L.K.E.R. 2 Toolkit</h2>
<p><b>Version:</b> 1.0</p>
<p><b>Compatible with:</b> Maya 2022+ and earlier versions</p>

<h3>Description:</h3>
<p>A comprehensive toolkit designed specifically for S.T.A.L.K.E.R. 2 modding workflows in Autodesk Maya. 
This toolkit provides automated tools to streamline the process of working with S.T.A.L.K.E.R. 2 game assets.</p>

        <h3>Current Tools:</h3>
        <ul>
        <li><b>Material-Texture Matcher:</b> Automatically assigns diffuse (_D) and normal (_N) textures 
        to materials based on strict naming conventions. Uses MI_ prefix for materials and T_ prefix for textures.</li>
        <li><b>Weapon Importer:</b> Imports weapon skeletons (SK_ prefix) and automatically constrains 
        associated unskinned meshes to their respective joints based on naming conventions.</li>
        <li><b>Weapon Rig Tool:</b> Creates control curves for rigged weapons with automatic shape detection 
        and intelligent joint-mesh analysis for easy animation workflows.</li>
        </ul>

<h3>Features:</h3>
<ul>
<li>Cross-Maya version compatibility (2022+ and earlier)</li>
<li>Dark mode UI consistent with modern workflows</li>
<li>Strict name matching to prevent incorrect assignments</li>
<li>Detailed logging and error reporting</li>
<li>Modular design for easy expansion</li>
</ul>

<h3>Upcoming Tools:</h3>
<ul>
<li>UV mapping utilities</li>
<li>Mesh processing tools</li>
<li>Animation import/export helpers</li>
<li>Asset validation tools</li>
</ul>

<p><i>Developed for the S.T.A.L.K.E.R. 2 modding community</i></p>
        """
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("About S.T.A.L.K.E.R. 2 Toolkit")
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setText(about_text)
        msg_box.setStandardButtons(QMessageBox.Ok)
        
        # Style the message box
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: 2px solid #333333;
            }
            QMessageBox QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: 1px solid #106ebe;
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 12px;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #106ebe;
            }
            QMessageBox QLabel {
                color: #e0e0e0;
            }
        """)
        
        msg_box.exec_()


def get_maya_main_window():
    """Get Maya main window as parent for dialog"""
    if pyside_version:
        main_window_ptr = omui.MQtUtil.mainWindow()
        return wrapInstance(int(main_window_ptr), QDialog)
    return None


def show_stalker2_toolkit():
    """Show the main S.T.A.L.K.E.R. 2 Toolkit dialog"""
    if not pyside_version:
        cmds.error("PySide is not available. Please ensure Maya is running properly.")
        return
    
    # Always reload the toolkit modules for fresh execution
    try:
        import sys
        modules_to_reload = ['material_texture_matcher', 'weapon_importer', 'weapon_rig_tool']
        for module_name in modules_to_reload:
            if module_name in sys.modules:
                if sys.version_info[0] >= 3:
                    import importlib
                    importlib.reload(sys.modules[module_name])
                else:
                    reload(sys.modules[module_name])
    except Exception as e:
        print("Note: Could not reload toolkit modules: " + str(e))
    
    parent = get_maya_main_window()
    dialog = STALKER2ToolkitDialog(parent)
    dialog.show()


def safe_launch_stalker2_toolkit():
    """Safe launcher that handles all common issues"""
    try:
        import sys
        import os
        import maya.cmds as cmds
        
        # Add toolkit directory to path if not already there
        maya_app_dir = cmds.internalVar(userAppDir=True)
        toolkit_dir = os.path.join(maya_app_dir, "scripts", "STALKER2_Toolkit")
        if toolkit_dir not in sys.path:
            sys.path.insert(0, toolkit_dir)
        
        # Reload modules for fresh execution
        modules_to_reload = ['stalker2_toolkit', 'material_texture_matcher', 'weapon_importer', 'weapon_rig_tool']
        for module_name in modules_to_reload:
            if module_name in sys.modules:
                if sys.version_info[0] >= 3:
                    import importlib
                    importlib.reload(sys.modules[module_name])
                else:
                    reload(sys.modules[module_name])
        
        # Import and show
        import stalker2_toolkit
        stalker2_toolkit.show_stalker2_toolkit()
        
        return True
        
    except Exception as e:
        error_msg = "Failed to launch S.T.A.L.K.E.R. 2 Toolkit: " + str(e)
        print(error_msg)
        try:
            cmds.error(error_msg)
        except:
            print("Could not display error in Maya")
        return False


# Main execution
if __name__ == "__main__":
    show_stalker2_toolkit() 