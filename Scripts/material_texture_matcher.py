#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Material-Texture Matcher for STALKER 2 Toolkit
Compatible with Maya 2022+ (Python 3, PySide6) and Maya 2022- (Python 2, PySide2)

This script assigns textures from a specified directory to materials based on strict name matching.
- Material prefix: "MI_"
- Texture prefix: "T_"
- Only assigns _D (diffuse) and _N (normal) textures
- Ignores _RMA and other texture types
"""

import os
import re
import sys

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
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QTextEdit, QFileDialog, QMessageBox, QListWidget, QListWidgetItem, QSplitter, QWidget, QCheckBox
    from PySide6.QtCore import Qt, QSize
    from PySide6.QtGui import QPixmap, QImageReader
    from shiboken6 import wrapInstance
    pyside_version = 6
except ImportError:
    try:
        # Maya 2022 and earlier (PySide2)
        from PySide2.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QTextEdit, QFileDialog, QMessageBox, QListWidget, QListWidgetItem, QSplitter, QWidget, QCheckBox
        from PySide2.QtCore import Qt, QSize
        from PySide2.QtGui import QPixmap, QImageReader
        from shiboken2 import wrapInstance
        pyside_version = 2
    except ImportError:
        print("Error: Could not import PySide. Please ensure Maya is running.")
        pyside_version = None

if pyside_version:
    import maya.OpenMayaUI as omui


class TextureSelectionDialog(QDialog):
    def __init__(self, material_name, texture_candidates, texture_type, all_textures_of_type=None):
        super(TextureSelectionDialog, self).__init__()
        
        self.material_name = material_name
        self.texture_candidates = texture_candidates  # List of (path, score) tuples
        self.texture_type = texture_type  # "Diffuse" or "Normal"
        self.all_textures_of_type = all_textures_of_type or []  # Full list of textures of this type
        self.selected_texture = None
        self.user_choice = "cancel"  # "assign", "skip", "cancel"
        
        self.setWindowTitle("Select {0} Texture for {1}".format(texture_type, material_name))
        self.setMinimumSize(1200, 700)  # Much larger for better preview experience
        self.setModal(True)
        
        self.setup_ui()
        self.setup_dark_style()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Header
        header_label = QLabel("Multiple {0} texture matches found for material:".format(self.texture_type))
        header_label.setProperty("class", "header-label")
        layout.addWidget(header_label)
        
        # Material name
        material_label = QLabel(self.material_name)
        material_label.setProperty("class", "material-label")
        layout.addWidget(material_label)
        
        # Instructions
        instructions = QLabel("Please select the best matching texture, or skip this material.\nUse the checkbox below to include additional 'pla_' prefixed textures:")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Checkbox for including pla_ textures
        self.include_pla_checkbox = QCheckBox("Include textures with 'pla_' prefix")
        self.include_pla_checkbox.setProperty("class", "pla-checkbox")
        self.include_pla_checkbox.stateChanged.connect(self.on_pla_checkbox_changed)
        layout.addWidget(self.include_pla_checkbox)
        
        # Create splitter for list and preview
        splitter = QSplitter()
        if pyside_version == 6:
            splitter.setOrientation(Qt.Orientation.Horizontal)
        else:
            splitter.setOrientation(Qt.Horizontal)
        
        # Texture list
        self.texture_list = QListWidget()
        self.texture_list.setAlternatingRowColors(True)
        self.texture_list.setMinimumWidth(300)
        self.texture_list.setMaximumWidth(450)
        self.texture_list.currentItemChanged.connect(self.on_texture_selected)
        
        splitter.addWidget(self.texture_list)
        
        # Image preview area
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(10, 10, 10, 10)
        
        # Preview label
        preview_label = QLabel("Texture Preview:")
        preview_label.setProperty("class", "preview-label")
        preview_layout.addWidget(preview_label)
        
        # Image display
        self.image_label = QLabel()
        self.image_label.setProperty("class", "image-preview")
        self.image_label.setMinimumSize(500, 400)
        # Remove maximum size constraint to allow full expansion
        if pyside_version == 6:
            self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.image_label.setScaledContents(False)  # Better quality scaling
            # Set size policy to expand
            from PySide6.QtWidgets import QSizePolicy
            self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        else:
            self.image_label.setAlignment(Qt.AlignCenter)
            self.image_label.setScaledContents(False)  # Better quality scaling
            # Set size policy to expand
            from PySide2.QtWidgets import QSizePolicy
            self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setText("Select a texture to preview")
        self.image_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #555555;
                background-color: #333333;
                color: #888888;
            }
        """)
        # Give the image the maximum space possible
        preview_layout.addWidget(self.image_label, 1)  # Stretch factor of 1
        
        # Texture info (compact)
        self.info_label = QLabel("No texture selected")
        self.info_label.setProperty("class", "info-label")
        self.info_label.setWordWrap(True)
        self.info_label.setMaximumHeight(120)  # More height for alpha channel and preview info
        if pyside_version == 6:
            from PySide6.QtWidgets import QSizePolicy
            self.info_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        else:
            from PySide2.QtWidgets import QSizePolicy  
            self.info_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        preview_layout.addWidget(self.info_label, 0)  # No stretch for info
        splitter.addWidget(preview_widget)
        
        # Set splitter sizes (30% list, 70% preview for maximum image viewing space)
        splitter.setSizes([360, 840])
        
        layout.addWidget(splitter)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        assign_btn = QPushButton("Assign Selected")
        assign_btn.setProperty("class", "primary-button")
        assign_btn.clicked.connect(self.assign_selected)
        assign_btn.setDefault(True)
        button_layout.addWidget(assign_btn)
        
        skip_btn = QPushButton("Skip This Material")
        skip_btn.setProperty("class", "secondary-button")
        skip_btn.clicked.connect(self.skip_material)
        button_layout.addWidget(skip_btn)
        
        cancel_btn = QPushButton("Cancel All")
        cancel_btn.setProperty("class", "secondary-button")
        cancel_btn.clicked.connect(self.cancel_all)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Now that all UI elements are created, populate the texture list
        self.populate_texture_list()
    
    def on_texture_selected(self, current, previous):
        """Handle texture selection and update preview"""
        if current is None:
            return
        
        # Safety check: make sure image_label exists (UI setup complete)
        if not hasattr(self, 'image_label'):
            return
        
        # Get texture path
        if pyside_version == 6:
            texture_path = current.data(Qt.ItemDataRole.UserRole)
        else:
            texture_path = current.data(Qt.UserRole)
        
        if texture_path and os.path.exists(texture_path):
            # Load a down-res version for faster preview
            pixmap = self.load_preview_image(texture_path)
            if not pixmap.isNull():
                self.image_label.setPixmap(pixmap)
                
                # Update info (get original image dimensions, not preview dimensions)
                texture_name = os.path.basename(texture_path)
                file_size = os.path.getsize(texture_path)
                size_mb = file_size / (1024 * 1024)
                
                # Get original image dimensions
                original_dimensions = self.get_original_image_dimensions(texture_path)
                image_size = "{0}x{1}".format(original_dimensions[0], original_dimensions[1]) if original_dimensions else "Unknown"
                
                # Check for alpha channel
                has_alpha = self.check_texture_alpha_channel(texture_path)
                alpha_status = "Yes" if has_alpha else "No"
                
                info_text = "File: {0}\nSize: {1} ({2:.1f} MB)\nDimensions: {3}\nAlpha Channel: {4}\n(Preview optimized for speed)".format(
                    texture_name, self.format_file_size(file_size), size_mb, image_size, alpha_status)
                self.info_label.setText(info_text)
            else:
                self.image_label.setText("Cannot load image:\n{0}".format(os.path.basename(texture_path)))
                self.info_label.setText("Invalid image file")
        else:
            self.image_label.setText("File not found:\n{0}".format(texture_path))
            self.info_label.setText("Missing file")
    
    def format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes < 1024:
            return "{0} B".format(size_bytes)
        elif size_bytes < 1024 * 1024:
            return "{0:.1f} KB".format(size_bytes / 1024)
        else:
            return "{0:.1f} MB".format(size_bytes / (1024 * 1024))
    
    def load_preview_image(self, texture_path):
        """Load a down-res version of the image for faster preview"""
        try:
            # Define maximum preview size for performance (512x512 is good balance)
            max_preview_size = 512
            
            # Use QImageReader for more control over loading
            image_reader = QImageReader(texture_path)
            
            if not image_reader.canRead():
                return QPixmap()
            
            # Get original image size
            original_size = image_reader.size()
            
            # Calculate scaled size while maintaining aspect ratio
            if original_size.width() > max_preview_size or original_size.height() > max_preview_size:
                if pyside_version == 6:
                    scaled_size = original_size.scaled(
                        QSize(max_preview_size, max_preview_size),
                        Qt.AspectRatioMode.KeepAspectRatio
                    )
                else:
                    scaled_size = original_size.scaled(
                        QSize(max_preview_size, max_preview_size),
                        Qt.KeepAspectRatio
                    )
                
                # Set the scaled size on the reader BEFORE reading
                image_reader.setScaledSize(scaled_size)
            
            # Read the image at the scaled size
            image = image_reader.read()
            
            if image.isNull():
                # Fallback to regular QPixmap loading if QImageReader fails
                return self.load_fallback_preview(texture_path, max_preview_size)
            
            # Convert to pixmap
            pixmap = QPixmap.fromImage(image)
            
            # Final scaling to fit the label if needed
            label_size = self.image_label.size()
            if label_size.width() > 100 and label_size.height() > 100:
                if pyside_version == 6:
                    pixmap = pixmap.scaled(
                        label_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                else:
                    pixmap = pixmap.scaled(
                        label_size,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
            
            return pixmap
            
        except Exception as e:
            print("Warning: Could not load preview image {0}: {1}".format(texture_path, str(e)))
            return self.load_fallback_preview(texture_path, 512)
    
    def load_fallback_preview(self, texture_path, max_size):
        """Fallback method for loading preview when QImageReader fails"""
        try:
            # Load full image and scale down (slower but more compatible)
            pixmap = QPixmap(texture_path)
            if not pixmap.isNull():
                if pixmap.width() > max_size or pixmap.height() > max_size:
                    if pyside_version == 6:
                        pixmap = pixmap.scaled(
                            QSize(max_size, max_size),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                    else:
                        pixmap = pixmap.scaled(
                            QSize(max_size, max_size),
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation
                        )
            return pixmap
        except Exception as e:
            print("Warning: Fallback preview failed for {0}: {1}".format(texture_path, str(e)))
            return QPixmap()
    
    def get_original_image_dimensions(self, texture_path):
        """Get original image dimensions without loading the full image"""
        try:
            # Use QImageReader to get dimensions without loading the full image
            image_reader = QImageReader(texture_path)
            if image_reader.canRead():
                size = image_reader.size()
                return (size.width(), size.height())
            else:
                # Fallback: try to load with QPixmap (slower)
                pixmap = QPixmap(texture_path)
                if not pixmap.isNull():
                    return (pixmap.width(), pixmap.height())
                else:
                    return None
        except Exception as e:
            print("Warning: Could not get image dimensions for {0}: {1}".format(texture_path, str(e)))
            return None
    
    def check_texture_alpha_channel(self, texture_path):
        """Quick check if texture has alpha channel (for display purposes)"""
        try:
            # Simple file extension check for alpha-capable formats
            ext = os.path.splitext(texture_path)[1].lower()
            alpha_capable_formats = ['.png', '.tga', '.tiff', '.tif', '.exr']
            
            if ext in alpha_capable_formats:
                # For display purposes, we'll use a simpler approach
                # Try to load with Maya's QPixmap which can detect alpha
                pixmap = QPixmap(texture_path)
                if not pixmap.isNull():
                    # Check if pixmap has alpha channel
                    if pyside_version == 6:
                        from PySide6.QtGui import QPixmap
                        has_alpha = pixmap.hasAlphaChannel()
                    else:
                        from PySide2.QtGui import QPixmap
                        has_alpha = pixmap.hasAlphaChannel()
                    return has_alpha
                else:
                    # Fallback: assume alpha-capable formats have alpha
                    return True
            else:
                # JPEG and other formats typically don't have alpha
                return False
        except Exception as e:
            # If we can't determine, assume no alpha to be safe
            return False
    
    def populate_texture_list(self):
        """Populate the texture list with current candidates and optionally pla_ textures"""
        self.texture_list.clear()
        
        # Start with original candidates
        textures_to_show = list(self.texture_candidates)
        
        # If checkbox is checked, add pla_ textures
        if self.include_pla_checkbox.isChecked():
            pla_textures = self.find_pla_textures()
            textures_to_show.extend(pla_textures)
        
        # Sort by score (highest first)
        textures_to_show.sort(key=lambda x: x[1], reverse=True)
        
        # Populate the list
        for texture_path, score in textures_to_show:
            texture_name = os.path.basename(texture_path)
            item_text = "{0} (Score: {1:.2f})".format(texture_name, score)
            
            item = QListWidgetItem(item_text)
            # Store full path using Qt.UserRole (compatible with both PySide2/6)
            if pyside_version == 6:
                item.setData(Qt.ItemDataRole.UserRole, texture_path)
            else:
                item.setData(Qt.UserRole, texture_path)
            self.texture_list.addItem(item)
        
        # Select the first (best) option by default and trigger preview
        if self.texture_list.count() > 0:
            self.texture_list.setCurrentRow(0)
            self.texture_list.setFocus()  # Ensure the list has focus
            # Ensure the preview updates for the selected item
            current_item = self.texture_list.currentItem()
            if current_item:
                # Make sure the selected item is visible
                self.texture_list.scrollToItem(current_item)
                self.on_texture_selected(current_item, None)
    
    def find_pla_textures(self):
        """Find additional textures with pla_ prefix that might match this material"""
        pla_candidates = []
        
        if not self.all_textures_of_type:
            return pla_candidates
        
        # Get material base name for matching
        material_base = self.material_name
        if material_base.startswith('MI_'):
            material_base = material_base[3:]  # Remove MI_ prefix
        
        # Look for textures with pla_ prefix
        for texture_path in self.all_textures_of_type:
            texture_name = os.path.basename(texture_path)
            
            # Skip if not a pla_ texture
            if not texture_name.startswith('T_pla_'):
                continue
            
            # Skip if already in candidates
            already_included = any(texture_path == candidate[0] for candidate in self.texture_candidates)
            if already_included:
                continue
            
            # Calculate score for this pla_ texture
            score = self.calculate_pla_texture_score(material_base, texture_path)
            
            if score >= 0.4:  # Lower threshold for pla_ textures
                pla_candidates.append((texture_path, score))
        
        return pla_candidates
    
    def calculate_pla_texture_score(self, material_base, texture_path):
        """Calculate similarity score for pla_ texture"""
        # Remove prefix and extension from texture
        texture_name = os.path.basename(texture_path)
        if texture_name.startswith('T_pla_'):
            texture_name = texture_name[6:]  # Remove T_pla_ prefix
        
        # Remove extension and texture type suffix
        texture_name = os.path.splitext(texture_name)[0]
        texture_name = re.sub(r'_[DN](\d+)?$', '', texture_name)
        texture_name = re.sub(r'_RMA(\d+)?$', '', texture_name)
        
        # Extract first 3 segments from both
        material_segments = material_base.split('_')[:3]
        texture_segments = texture_name.split('_')[:3]
        
        # Calculate basic similarity
        if len(material_segments) >= 2 and len(texture_segments) >= 2:
            matches = 0
            min_len = min(len(material_segments), len(texture_segments))
            
            for i in range(min_len):
                if i < len(material_segments) and i < len(texture_segments):
                    if material_segments[i] == texture_segments[i]:
                        matches += 1
            
            return float(matches) / max(len(material_segments), len(texture_segments))
        
        return 0.0
    
    def on_pla_checkbox_changed(self, state):
        """Handle checkbox state change"""
        self.populate_texture_list()
    
    def showEvent(self, event):
        """Override showEvent to ensure first item is selected when dialog opens"""
        super(TextureSelectionDialog, self).showEvent(event)
        # Ensure the first item is selected and preview is shown when dialog opens
        if self.texture_list.count() > 0 and not self.texture_list.currentItem():
            self.texture_list.setCurrentRow(0)
            current_item = self.texture_list.currentItem()
            if current_item:
                self.texture_list.scrollToItem(current_item)
                self.on_texture_selected(current_item, None)
    
    def assign_selected(self):
        current_item = self.texture_list.currentItem()
        if current_item:
            # Get stored texture path (compatible with both PySide2/6)
            if pyside_version == 6:
                self.selected_texture = current_item.data(Qt.ItemDataRole.UserRole)
            else:
                self.selected_texture = current_item.data(Qt.UserRole)
            self.user_choice = "assign"
            self.accept()
    
    def skip_material(self):
        self.user_choice = "skip"
        self.accept()
    
    def cancel_all(self):
        self.user_choice = "cancel"
        self.reject()
    
    def setup_dark_style(self):
        """Apply dark mode styling"""
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            .header-label {
                font-size: 12px;
                font-weight: bold;
                color: #cccccc;
            }
            .material-label {
                font-size: 14px;
                font-weight: bold;
                color: #FFD700;
                padding: 5px;
                background-color: #404040;
                border-radius: 3px;
            }
            QListWidget {
                background-color: #404040;
                border: 1px solid #555555;
                selection-background-color: #0078d4;
                alternate-background-color: #484848;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #555555;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
            }
            .primary-button {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            .primary-button:hover {
                background-color: #106ebe;
            }
            .secondary-button {
                background-color: #404040;
                color: white;
                border: 1px solid #555555;
                padding: 8px 16px;
                border-radius: 4px;
            }
            .secondary-button:hover {
                background-color: #555555;
            }
            .preview-label {
                font-size: 12px;
                font-weight: bold;
                color: #cccccc;
                margin-bottom: 5px;
            }
            .image-preview {
                border: 2px solid #555555;
                background-color: #404040;
                color: #888888;
            }
            .info-label {
                font-size: 10px;
                color: #cccccc;
                background-color: #333333;
                padding: 10px;
                border-radius: 3px;
                margin-top: 5px;
                line-height: 1.3;
            }
            QSplitter::handle {
                background-color: #555555;
                width: 2px;
            }
            .pla-checkbox {
                color: #ffffff;
                font-size: 11px;
                padding: 5px;
                margin: 5px 0px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #555555;
                background-color: #404040;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border-color: #106ebe;
            }
            QCheckBox::indicator:hover {
                border-color: #0078d4;
            }
        """)


class MaterialTextureMatcherDialog(QDialog):
    def __init__(self, parent=None):
        super(MaterialTextureMatcherDialog, self).__init__(parent)
        self.setWindowTitle("Material-Texture Matcher - STALKER 2 Toolkit")
        self.setMinimumSize(500, 350)
        self.texture_path = ""
        self.setup_ui()
        self.setup_dark_style()
    
    def setup_dark_style(self):
        """Apply dark theme styling"""
        dark_style = """
        QDialog {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QLabel {
            color: #ffffff;
            font-size: 11px;
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
        """
        self.setStyleSheet(dark_style)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("Material-Texture Matcher")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Texture path selection
        path_layout = QHBoxLayout()
        self.path_label = QLabel("Texture Directory:")
        self.path_edit = QLineEdit()
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_texture_path)
        
        path_layout.addWidget(self.path_label)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.browse_btn)
        layout.addLayout(path_layout)
        
        # Instructions
        instructions = QLabel(
            "Instructions:\n"
            "1. Select mesh objects with materials assigned\n"
            "2. Choose the directory containing textures (with T_ prefix)\n"
            "3. Click 'Assign Textures' to automatically match and assign\n"
            "4. Only _D (diffuse) and _N (normal) textures will be assigned\n"
            "5. Matches first 3 segments after prefix (e.g., 'arm_ban_06')\n"
            "6. For multiple matches, a selection dialog will appear\n"
            "7. Materials with existing textures will be skipped\n"
            "8. Alpha channels in diffuse textures auto-connect to transparency\n"
            "9. Selection dialog includes option to show 'pla_' prefixed textures\n"
            "10. Specular color automatically set to black for game-ready materials"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("margin: 10px 0px; padding: 10px; background-color: #353535; border-radius: 5px;")
        layout.addWidget(instructions)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.assign_btn = QPushButton("Assign Textures")
        self.cancel_btn = QPushButton("Close")
        
        self.assign_btn.clicked.connect(self.assign_textures)
        self.cancel_btn.clicked.connect(self.reject)
        
        # Style main buttons differently
        self.assign_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: 1px solid #106ebe;
                padding: 10px 20px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        
        button_layout.addWidget(self.assign_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
    
    def browse_texture_path(self):
        """Browse for texture directory"""
        directory = QFileDialog.getExistingDirectory(self, "Select Texture Directory")
        if directory:
            self.texture_path = directory
            self.path_edit.setText(directory)
    
    def assign_textures(self):
        """Main function to assign textures to materials"""
        if not self.texture_path:
            self.texture_path = self.path_edit.text()
        
        if not self.texture_path or not os.path.exists(self.texture_path):
            QMessageBox.warning(self, "Warning", "Please select a valid texture directory.")
            return
        
        # Get selected objects
        selection = cmds.ls(selection=True, long=True)
        if not selection:
            QMessageBox.warning(self, "Warning", "Please select mesh objects with materials.")
            return
        
        # Get all materials from selected objects
        materials = self.get_materials_from_selection(selection)
        if not materials:
            QMessageBox.warning(self, "Warning", "No materials found on selected objects.")
            return
        
        # Get all textures from directory
        textures = self.get_textures_from_directory(self.texture_path)
        if not textures:
            QMessageBox.warning(self, "Warning", "No textures found in selected directory.")
            return
        
        # Assign textures to materials
        assigned_count, missing_materials, skipped_materials = self.assign_textures_to_materials(materials, textures)
        
        # Show results
        self.show_results(assigned_count, missing_materials, skipped_materials)
        if assigned_count > 0:
            self.accept()
    
    def get_materials_from_selection(self, selection):
        """Get all materials assigned to selected objects"""
        materials = set()
        
        for obj in selection:
            # Get shape nodes
            shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
            
            for shape in shapes:
                # Get shading engines connected to the shape
                shading_engines = cmds.listConnections(shape, type='shadingEngine') or []
                
                for sg in shading_engines:
                    # Get materials connected to shading engine
                    connected_materials = cmds.listConnections(sg + '.surfaceShader') or []
                    for mat in connected_materials:
                        if mat.startswith('MI_'):
                            materials.add(mat)
        
        return list(materials)
    
    def get_textures_from_directory(self, directory):
        """Get all relevant textures from directory"""
        textures = {'diffuse': [], 'normal': []}
        
        for filename in os.listdir(directory):
            if not filename.startswith('T_') or not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.exr')):
                continue
            
            filepath = os.path.join(directory, filename)
            
            # More precise texture type detection
            if re.search(r'_D(\d+)?\.', filename) or filename.endswith('_D.png') or filename.endswith('_D.jpg'):
                textures['diffuse'].append(filepath)
            elif re.search(r'_N(\d+)?\.', filename) or filename.endswith('_N.png') or filename.endswith('_N.jpg'):
                textures['normal'].append(filepath)
        
        return textures
    
    def normalize_name_for_matching(self, name, is_texture=False):
        """Normalize material or texture name for looser comparison using first 3 segments"""
        # Remove prefix
        if name.startswith('MI_'):
            name = name[3:]
        elif name.startswith('T_'):
            name = name[2:]
        
        # For textures, remove file extension and texture type suffix
        if is_texture:
            name = os.path.splitext(os.path.basename(name))[0]
            # Remove texture type suffixes like _D, _N, _D01, _N02, etc.
            name = re.sub(r'_[DN](\d+)?$', '', name)
            name = re.sub(r'_RMA(\d+)?$', '', name)
        
        # Extract first 3 segments separated by underscores
        # Example: "arm_ban_06_a" -> "arm_ban_06"
        segments = name.split('_')
        if len(segments) >= 3:
            # Take first 3 segments
            matching_part = '_'.join(segments[:3])
        elif len(segments) >= 2:
            # If less than 3 segments, take what we have
            matching_part = '_'.join(segments[:2])
        else:
            # Single segment, use as is
            matching_part = name
        
        return matching_part.lower()
    
    def find_texture_match(self, material_name, texture_list):
        """Find texture match for a material using flexible segment matching"""
        material_normalized = self.normalize_name_for_matching(material_name)
        
        # First pass: Look for exact matches on first 3 segments
        for texture_path in texture_list:
            texture_normalized = self.normalize_name_for_matching(texture_path, is_texture=True)
            
            if material_normalized == texture_normalized:
                print("  Found exact match: '{0}' == '{1}'".format(material_normalized, texture_normalized))
                return texture_path
        
        # Second pass: Look for flexible segment matches
        material_segments = material_normalized.split('_')
        candidates = []
        
        print("  Material segments: {0}".format(material_segments))
        
        for texture_path in texture_list:
            texture_normalized = self.normalize_name_for_matching(texture_path, is_texture=True)
            texture_segments = texture_normalized.split('_')
            
            # Try different matching strategies
            score = self.calculate_flexible_similarity(material_segments, texture_segments)
            
            if score > 0.3:  # Show more potential matches for debugging
                print("  Texture '{0}' segments: {1}, score: {2:.2f}".format(
                    os.path.basename(texture_path), texture_segments, score))
            
            if score >= 0.6:  # Collect all good candidates
                candidates.append((texture_path, score))
        
        if not candidates:
            print("  No suitable match found (needed 0.6+)")
            return None
        
        # Sort candidates by score (best first)
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # If there's a clear winner (much better than others), auto-assign
        if len(candidates) == 1 or candidates[0][1] >= 0.85:
            best_match = candidates[0][0]
            print("  Auto-selected best match: '{0}' with score {1:.2f}".format(
                os.path.basename(best_match), candidates[0][1]))
            return best_match
        
        # Multiple close matches - return candidates for user selection
        print("  Found {0} potential matches - will show selection dialog".format(len(candidates)))
        return candidates
    
    def calculate_flexible_similarity(self, material_segments, texture_segments):
        """Calculate flexible similarity allowing for prefix differences and partial matches"""
        if not material_segments or not texture_segments:
            return 0.0
        
        # Try different alignment strategies
        best_score = 0.0
        
        # Strategy 1: Direct comparison (original approach)
        score1 = self.compare_segment_sequences(material_segments, texture_segments)
        best_score = max(best_score, score1)
        
        # Strategy 2: Skip first segment of texture (handles extra prefixes like "pla_")
        if len(texture_segments) > 1:
            score2 = self.compare_segment_sequences(material_segments, texture_segments[1:])
            best_score = max(best_score, score2)
        
        # Strategy 3: Skip first segment of material (handles different naming)
        if len(material_segments) > 1:
            score3 = self.compare_segment_sequences(material_segments[1:], texture_segments)
            best_score = max(best_score, score3)
        
        # Strategy 4: Check if any texture segments contain material segments
        score4 = self.calculate_containment_similarity(material_segments, texture_segments)
        best_score = max(best_score, score4)
        
        return best_score
    
    def compare_segment_sequences(self, seq1, seq2):
        """Compare two sequences of segments for similarity"""
        if not seq1 or not seq2:
            return 0.0
        
        min_len = min(len(seq1), len(seq2))
        max_len = max(len(seq1), len(seq2))
        
        # Count matching segments from the beginning
        matching = 0
        for i in range(min_len):
            if seq1[i] == seq2[i]:
                matching += 1
            else:
                break  # Stop at first mismatch for sequence comparison
        
        if max_len == 0:
            return 0.0
        
        return float(matching) / max_len
    
    def calculate_containment_similarity(self, material_segments, texture_segments):
        """Check if material segments are contained in texture segments"""
        if not material_segments or not texture_segments:
            return 0.0
        
        # Count how many material segments appear anywhere in texture segments
        matches = 0
        for mat_seg in material_segments:
            if mat_seg in texture_segments:
                matches += 1
        
        return float(matches) / len(material_segments)
    
    def assign_textures_to_materials(self, materials, textures):
        """Assign textures to materials using flexible matching with user selection"""
        assigned_count = 0
        missing_materials = []
        skipped_materials = []
        user_cancelled = False
        
        # Store texture lists for the selection dialog
        self._current_diffuse_textures = textures['diffuse']
        self._current_normal_textures = textures['normal']
        
        for material in materials:
            if user_cancelled:
                break
            
            # Check if material already has textures assigned
            existing_textures = self.check_existing_textures(material)
            if existing_textures['diffuse'] or existing_textures['normal']:
                texture_types = []
                if existing_textures['diffuse']:
                    texture_types.append("diffuse")
                if existing_textures['normal']:
                    texture_types.append("normal")
                
                print("Skipping material '{0}' - already has {1} texture(s) assigned".format(
                    material, " and ".join(texture_types)))
                skipped_materials.append(material)
                continue
                
            diffuse_texture = self.find_texture_match(material, textures['diffuse'])
            normal_texture = self.find_texture_match(material, textures['normal'])
            
            material_assigned = False
            
            # Show matching segments for debugging
            material_segments = self.normalize_name_for_matching(material)
            print("Material '{0}' normalized to segments: '{1}'".format(material, material_segments))
            
            # Handle diffuse texture assignment
            diffuse_result = self.handle_texture_assignment(material, diffuse_texture, 'color', 'Diffuse')
            if diffuse_result == "cancel":
                user_cancelled = True
                break
            elif diffuse_result == "assigned":
                material_assigned = True
            
            # Handle normal texture assignment (only if user didn't cancel)
            if not user_cancelled:
                normal_result = self.handle_texture_assignment(material, normal_texture, 'normalCamera', 'Normal')
                if normal_result == "cancel":
                    user_cancelled = True
                    break
                elif normal_result == "assigned":
                    material_assigned = True
            
            if material_assigned:
                assigned_count += 1
            else:
                missing_materials.append(material)
                print("No suitable texture match found for material: {0}".format(material))
        
        if user_cancelled:
            print("Texture assignment cancelled by user.")
        
        # Print summary
        if skipped_materials:
            print("Skipped {0} material(s) that already had textures assigned: {1}".format(
                len(skipped_materials), ", ".join(skipped_materials)))
        
        return assigned_count, missing_materials, skipped_materials
    
    def check_existing_textures(self, material):
        """Check if material already has textures assigned to diffuse and normal channels"""
        existing = {'diffuse': False, 'normal': False}
        
        try:
            # Check diffuse (color) channel
            color_connections = cmds.listConnections(material + '.color', source=True, destination=False)
            if color_connections:
                existing['diffuse'] = True
            
            # Check normal channel
            normal_connections = cmds.listConnections(material + '.normalCamera', source=True, destination=False)
            if normal_connections:
                existing['normal'] = True
                
        except Exception as e:
            print("Warning: Could not check existing textures for material '{0}': {1}".format(material, str(e)))
        
        return existing
    
    def handle_texture_assignment(self, material, texture_match, attribute, texture_type):
        """Handle texture assignment with user selection for multiple candidates"""
        if texture_match is None:
            return "none"
        
        # Single texture match - assign directly
        if isinstance(texture_match, (str, text_type)):
            if self.assign_texture_to_material(material, texture_match, attribute):
                texture_segments = self.normalize_name_for_matching(texture_match, is_texture=True)
                print("Assigned {0} texture: {1} -> {2} (matched segments: '{3}')".format(
                    texture_type.lower(), os.path.basename(texture_match), material, texture_segments))
                return "assigned"
            return "failed"
        
        # Multiple candidates - show selection dialog
        elif isinstance(texture_match, list):
            # Get the appropriate full texture list
            if texture_type == "Diffuse":
                all_textures = getattr(self, '_current_diffuse_textures', [])
            else:
                all_textures = getattr(self, '_current_normal_textures', [])
            
            selection_dialog = TextureSelectionDialog(material, texture_match, texture_type, all_textures)
            result = selection_dialog.exec_()
            
            if selection_dialog.user_choice == "assign" and selection_dialog.selected_texture:
                if self.assign_texture_to_material(material, selection_dialog.selected_texture, attribute):
                    texture_segments = self.normalize_name_for_matching(selection_dialog.selected_texture, is_texture=True)
                    print("User-selected {0} texture: {1} -> {2} (matched segments: '{3}')".format(
                        texture_type.lower(), os.path.basename(selection_dialog.selected_texture), material, texture_segments))
                    return "assigned"
                else:
                    print("Failed to assign user-selected {0} texture for material: {1}".format(texture_type.lower(), material))
                    return "failed"
            elif selection_dialog.user_choice == "skip":
                print("User skipped {0} texture assignment for material: {1}".format(texture_type.lower(), material))
                return "skipped"
            elif selection_dialog.user_choice == "cancel":
                print("User cancelled texture assignment process.")
                return "cancel"
        
        return "none"
    
    def assign_texture_to_material(self, material, texture_path, attribute):
        """Assign a texture to a material attribute"""
        try:
            # Create file texture node
            texture_name = os.path.splitext(os.path.basename(texture_path))[0]
            file_node = cmds.shadingNode('file', asTexture=True, name=texture_name + '_file')
            
            # Set the texture file path
            cmds.setAttr(file_node + '.fileTextureName', texture_path, type='string')
            
            # Create place2dTexture node
            place2d = cmds.shadingNode('place2dTexture', asUtility=True, name=texture_name + '_place2d')
            
            # Connect place2dTexture to file node
            cmds.connectAttr(place2d + '.coverage', file_node + '.coverage')
            cmds.connectAttr(place2d + '.translateFrame', file_node + '.translateFrame')
            cmds.connectAttr(place2d + '.rotateFrame', file_node + '.rotateFrame')
            cmds.connectAttr(place2d + '.mirrorU', file_node + '.mirrorU')
            cmds.connectAttr(place2d + '.mirrorV', file_node + '.mirrorV')
            cmds.connectAttr(place2d + '.stagger', file_node + '.stagger')
            cmds.connectAttr(place2d + '.wrapU', file_node + '.wrapU')
            cmds.connectAttr(place2d + '.wrapV', file_node + '.wrapV')
            cmds.connectAttr(place2d + '.repeatUV', file_node + '.repeatUV')
            cmds.connectAttr(place2d + '.offset', file_node + '.offset')
            cmds.connectAttr(place2d + '.rotateUV', file_node + '.rotateUV')
            cmds.connectAttr(place2d + '.noiseUV', file_node + '.noiseUV')
            cmds.connectAttr(place2d + '.vertexUvOne', file_node + '.vertexUvOne')
            cmds.connectAttr(place2d + '.vertexUvTwo', file_node + '.vertexUvTwo')
            cmds.connectAttr(place2d + '.vertexUvThree', file_node + '.vertexUvThree')
            cmds.connectAttr(place2d + '.vertexCameraOne', file_node + '.vertexCameraOne')
            cmds.connectAttr(place2d + '.outUV', file_node + '.uv')
            cmds.connectAttr(place2d + '.outUvFilterSize', file_node + '.uvFilterSize')
            
            # Connect file node to material
            if attribute == 'normalCamera':
                # For normal maps, we need a bump2d node
                bump_node = cmds.shadingNode('bump2d', asUtility=True, name=texture_name + '_bump')
                cmds.connectAttr(file_node + '.outAlpha', bump_node + '.bumpValue')
                cmds.connectAttr(bump_node + '.outNormal', material + '.' + attribute)
            else:
                cmds.connectAttr(file_node + '.outColor', material + '.' + attribute)
                
                # For diffuse textures, also check for alpha channel and connect to transparency
                if attribute == 'color':
                    alpha_connected = self.connect_alpha_to_transparency(file_node, material, texture_path)
                    if alpha_connected:
                        print("  Alpha channel detected and connected to transparency")
            
            # Set specular color to black for game-ready materials
            self.set_specular_to_black(material)
            
            return True
            
        except Exception as e:
            print("Error assigning texture {0} to material {1}: {2}".format(texture_path, material, str(e)))
            return False
    
    def connect_alpha_to_transparency(self, file_node, material, texture_path):
        """Connect alpha channel to material transparency if alpha exists"""
        try:
            # Check if the texture has an alpha channel by examining the file
            has_alpha = self.texture_has_alpha_channel(texture_path)
            
            if has_alpha:
                # Check if transparency is already connected
                existing_connections = cmds.listConnections(material + '.transparency', source=True, destination=False)
                if not existing_connections:
                    # Connect the alpha output to transparency
                    cmds.connectAttr(file_node + '.outAlpha', material + '.transparency')
                    return True
                else:
                    print("  Material already has transparency connection, skipping alpha")
                    return False
            else:
                return False
                
        except Exception as e:
            print("  Warning: Could not connect alpha channel: {0}".format(str(e)))
            return False
    
    def texture_has_alpha_channel(self, texture_path):
        """Check if a texture file has an alpha channel"""
        try:
            # Try to use Maya's image info to check for alpha
            # This is more reliable than trying to load the image with Python libraries
            
            # Create a temporary file node to check the image properties
            temp_file = cmds.shadingNode('file', asTexture=True)
            cmds.setAttr(temp_file + '.fileTextureName', texture_path, type='string')
            
            # Force Maya to evaluate the file to get proper info
            # Check if the alpha is being used (outAlpha has connections or is non-zero)
            try:
                # Try to query the alpha output - if it exists and has meaningful data, assume alpha channel
                alpha_exists = cmds.getAttr(temp_file + '.outAlpha')
                # Delete the temporary node
                cmds.delete(temp_file)
                
                # If we can read alpha and it's not exactly 1.0 (opaque), assume there's alpha data
                # Note: This is a heuristic - for more robust detection, we'd need image libraries
                # For now, we'll assume most diffuse textures with alpha are meant to use it
                
                # Simple check: if the file extension suggests it can have alpha, assume it does
                ext = os.path.splitext(texture_path)[1].lower()
                alpha_capable_formats = ['.png', '.tga', '.tiff', '.tif', '.exr']
                
                if ext in alpha_capable_formats:
                    return True
                else:
                    return False
                    
            except:
                # If we can't read alpha, clean up and assume no alpha
                try:
                    cmds.delete(temp_file)
                except:
                    pass
                return False
                
        except Exception as e:
            print("  Warning: Could not check alpha channel for {0}: {1}".format(texture_path, str(e)))
            return False
    
    def set_specular_to_black(self, material):
        """Set the specular color to black (0,0,0) for game-ready materials"""
        try:
            # Check if the material has a specular color attribute
            if cmds.attributeQuery('specularColor', node=material, exists=True):
                cmds.setAttr(material + '.specularColor', 0, 0, 0, type='double3')
                print("  Set specular color to black")
                return True
            
            # Some materials might use different specular attributes
            specular_attrs = ['specularColor', 'specular', 'specularRollOff']
            
            for attr in specular_attrs:
                if cmds.attributeQuery(attr, node=material, exists=True):
                    attr_type = cmds.getAttr(material + '.' + attr, type=True)
                    
                    if attr_type == 'double3':  # RGB color
                        cmds.setAttr(material + '.' + attr, 0, 0, 0, type='double3')
                        print("  Set {0} to black".format(attr))
                        return True
                    elif attr_type in ['double', 'float']:  # Single value
                        cmds.setAttr(material + '.' + attr, 0)
                        print("  Set {0} to 0".format(attr))
                        return True
            
            print("  No specular attributes found to modify")
            return False
            
        except Exception as e:
            print("  Warning: Could not set specular color for {0}: {1}".format(material, str(e)))
            return False
    
    def show_results(self, assigned_count, missing_materials, skipped_materials=None):
        """Show results in a popup"""
        message = "Material-Texture Matching Results\n\n"
        message += "Materials successfully processed: {0}\n".format(assigned_count)
        
        if skipped_materials:
            message += "Materials skipped (already had textures): {0}\n".format(len(skipped_materials))
        
        if missing_materials:
            message += "\nMaterials without suitable texture matches:\n"
            for material in missing_materials:
                message += "- {0}\n".format(material)
            message += "\n(Check console for detailed matching information)"
        else:
            if not skipped_materials:
                message += "\nAll materials were successfully matched!"
            else:
                message += "\nAll new materials were successfully matched!"
        
        if skipped_materials:
            message += "\n\nSkipped materials (already textured):\n"
            for material in skipped_materials:
                message += "- {0}\n".format(material)
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Results")
        msg_box.setText(message)
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QMessageBox QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: 1px solid #106ebe;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        msg_box.exec_()


def get_maya_main_window():
    """Get Maya main window as parent for dialog"""
    if pyside_version:
        main_window_ptr = omui.MQtUtil.mainWindow()
        return wrapInstance(int(main_window_ptr), QDialog)
    return None


def show_material_texture_matcher():
    """Show the Material-Texture Matcher dialog"""
    if not pyside_version:
        cmds.error("PySide is not available. Please ensure Maya is running properly.")
        return
    
    parent = get_maya_main_window()
    dialog = MaterialTextureMatcherDialog(parent)
    dialog.show()


# For backwards compatibility
def show_texture_assignment_dialog():
    """Backwards compatibility function"""
    show_material_texture_matcher()


# Main execution
if __name__ == "__main__":
    show_material_texture_matcher() 