"""
Hax Game Exporter - Help Dialog with Animated GIF Tooltips
Compatible with Maya 2025 (Python 3, PySide6) and Maya 2022- (Python 2, PySide2)
"""

from __future__ import print_function
import sys
import os

# Maya imports
import maya.cmds as cmds
import maya.OpenMayaUI as omui

# PySide compatibility for Maya versions
try:
    # Maya 2025+ (PySide6)
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance
    pyside_version = 6
except ImportError:
    try:
        # Maya 2022 and earlier (PySide2)
        from PySide2 import QtCore, QtGui, QtWidgets
        from shiboken2 import wrapInstance
        pyside_version = 2
    except ImportError:
        print("Error: Could not import PySide. Please ensure Maya is running.")
        pyside_version = None


def maya_main_window():
    """
    Return the Maya main window widget as a Python object
    """
    main_window_ptr = omui.MQtUtil.mainWindow()
    if sys.version_info.major >= 3:
        return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)
    else:
        return wrapInstance(long(main_window_ptr), QtWidgets.QWidget)


class ToolTipAnimation(QtWidgets.QLabel):
    """
    Custom QLabel that displays an animated GIF as a tooltip.
    Shows on hover and auto-hides on user interaction.
    """
    def __init__(self, file_path, width=None, height=None):
        super(ToolTipAnimation, self).__init__(parent=maya_main_window())
        self.setMouseTracking(True)
        
        # Set window flags to ensure it appears on top
        self.setWindowFlags(
            QtCore.Qt.ToolTip | 
            QtCore.Qt.FramelessWindowHint | 
            QtCore.Qt.WindowStaysOnTopHint
        )
        
        # Make sure it's not opaque
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, False)

        # Store parameters for lazy loading
        self._file = file_path
        self._width = width
        self._height = height
        self._shown = False

        # Timer to prevent immediate hiding on enterEvent
        self.showTimer = QtCore.QTimer(interval=100, singleShot=True)
        self.showTimer.setParent(self)  # Parent timer to ensure cleanup

        # Install event filter to hide on any user interaction
        self._app = QtWidgets.QApplication.instance()
        self._event_filter_installed = False
        if self._app:
            self._app.installEventFilter(self)
            self._event_filter_installed = True
        
        # Track cleanup state to prevent double-cleanup
        self._cleaned_up = False
    
    def cleanup(self):
        """Explicit cleanup method - call before widget deletion"""
        if self._cleaned_up:
            return
        self._cleaned_up = True
        
        try:
            # Remove event filter first
            if self._event_filter_installed and self._app is not None:
                try:
                    self._app.removeEventFilter(self)
                except (RuntimeError, AttributeError):
                    pass  # Object already deleted by Qt
                self._event_filter_installed = False
            
            # Stop and clean up movie
            movie = self.movie()
            if movie is not None:
                try:
                    movie.stop()
                    movie.deleteLater()
                except (RuntimeError, AttributeError):
                    pass  # Object already deleted by Qt
                self.setMovie(None)
        except:
            pass

    def load(self):
        """Load and configure the animated GIF"""
        print("[DEBUG] ToolTipAnimation.load() called for: {}".format(self._file))
        movie = QtGui.QMovie(self._file)
        
        if not movie.isValid():
            print("[DEBUG] ERROR: QMovie is not valid for file: {}".format(self._file))
            return
        
        print("[DEBUG] QMovie is valid, frame count: {}".format(movie.frameCount()))
        
        if self._width and not self._height:
            self._height = self._width
        if self._width and self._height:
            size = QtCore.QSize(self._width, self._height)
            movie.setScaledSize(size)
            print("[DEBUG] Scaled GIF to: {}x{}".format(self._width, self._height))
        else:
            # Calculate size from all frames
            size = QtCore.QSize()
            for f in range(movie.frameCount()):
                movie.jumpToFrame(f)
                size = size.expandedTo(movie.currentImage().size())
            print("[DEBUG] GIF size calculated: {}x{}".format(size.width(), size.height()))
        
        self.setFixedSize(size)
        self.setMovie(movie)
        self._shown = True
        print("[DEBUG] GIF loaded successfully")

    def show(self, pos=None):
        """Show the tooltip at the specified position or cursor position"""
        print("[DEBUG] ToolTipAnimation.show() called")
        
        if not self._shown:
            self.load()
        
        if not self.movie():
            print("[DEBUG] ERROR: No movie to show")
            return
        
        print("[DEBUG] Movie exists, showing tooltip")
            
        if pos is None:
            pos = QtGui.QCursor.pos()
        
        # Ensure tooltip stays within screen bounds
        for screen in QtWidgets.QApplication.screens():
            if screen.availableGeometry().contains(pos):
                screen_rect = screen.availableGeometry()
                # Offset so cursor doesn't hide the tip
                pos += QtCore.QPoint(2, 16)
                
                # Keep within screen bounds
                if pos.x() < screen_rect.x():
                    pos.setX(screen_rect.x())
                elif pos.x() + self.width() > screen_rect.right():
                    pos.setX(screen_rect.right() - self.width())
                if pos.y() < screen_rect.y():
                    pos.setY(screen_rect.y())
                elif pos.y() + self.height() > screen_rect.bottom():
                    pos.setY(screen_rect.bottom() - self.height())
                break

        self.move(pos)
        super(ToolTipAnimation, self).show()
        self.movie().start()
        print("[DEBUG] Tooltip displayed and movie started")

    def maybeHide(self):
        """Hide tooltip unless mouse is still within parent's rectangle"""
        if self.parent() is not None:
            parent_pos = self.parent().mapToGlobal(QtCore.QPoint())
            rect = QtCore.QRect(parent_pos, self.parent().size())
            if rect.contains(QtGui.QCursor.pos()):
                return
        self.hide()

    def eventFilter(self, source, event):
        """Hide tooltip on any user interaction"""
        if event.type() in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease,
                            QtCore.QEvent.WindowActivate, QtCore.QEvent.WindowDeactivate,
                            QtCore.QEvent.FocusIn, QtCore.QEvent.FocusOut,
                            QtCore.QEvent.Leave, QtCore.QEvent.Close,
                            QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease,
                            QtCore.QEvent.MouseButtonDblClick, QtCore.QEvent.Wheel):
            self.hide()
        return False

    def mouseMoveEvent(self, event):
        """Hide tooltip when mouse moves over it"""
        QtCore.QTimer.singleShot(100, self.hide)

    def enterEvent(self, event):
        """Hide tooltip when mouse enters (with delay to prevent flicker)"""
        if not self.showTimer.isActive():
            QtCore.QTimer.singleShot(100, self.hide)

    def showEvent(self, event):
        """Start show timer when tooltip appears"""
        self.showTimer.start()

    def hideEvent(self, event):
        """Stop movie when tooltip hides"""
        if self.movie():
            self.movie().stop()


class ButtonIcon(QtWidgets.QPushButton):
    """
    Custom QPushButton that can display an animated GIF or static image as a tooltip on hover.
    """
    def __init__(self, *args, **kwargs):
        super(ButtonIcon, self).__init__(*args, **kwargs)
        # Instance variable, not class variable
        self.toolTipAnimation = None
        self._cleaned_up = False
    
    def cleanup(self):
        """Explicit cleanup method - call before widget deletion"""
        if self._cleaned_up:
            return
        self._cleaned_up = True
        
        try:
            if self.toolTipAnimation:
                # Clean up the tooltip animation
                try:
                    self.toolTipAnimation.cleanup()
                except:
                    pass
                
                # Hide and schedule for deletion
                try:
                    self.toolTipAnimation.hide()
                    self.toolTipAnimation.deleteLater()
                except (RuntimeError, AttributeError):
                    pass  # Already deleted
                
                self.toolTipAnimation = None
        except:
            pass

    def setToolTipImage(self, image, width=None, height=None):
        """Set an image or GIF to display as tooltip"""
        print("[DEBUG] setToolTipImage called with: {}".format(image))
        
        if self.toolTipAnimation:
            self.toolTipAnimation.hide()
            self.toolTipAnimation.deleteLater()
            self.toolTipAnimation = None
            self.setToolTip('')
            
        if not image:
            print("[DEBUG] No image provided, returning")
            return

        # Check if file exists - if not, just don't show any tooltip
        if not os.path.exists(image):
            print("[DEBUG] File does not exist: {}".format(image))
            return
        
        print("[DEBUG] File exists: {}".format(image))

        # Check if it's a GIF (animated format)
        if image.lower().endswith('.gif'):
            print("[DEBUG] Creating animated tooltip for GIF: {}".format(image))
            self.toolTipAnimation = ToolTipAnimation(image, width, height)
            print("[DEBUG] ToolTipAnimation created successfully")
        else:
            print("[DEBUG] Creating static image tooltip")
            # Static image - use standard HTML tooltip
            if width and not height:
                height = width
            if width and height:
                self.setToolTip(
                    '<img src="{}" width="{}" height="{}">'.format(
                        image, width, height))
            else:
                self.setToolTip('<img src="{}">'.format(image))

    def event(self, event):
        """Handle tooltip events for animated tooltips"""
        try:
            if event.type() == QtCore.QEvent.ToolTip:
                print("[DEBUG] ToolTip event triggered on button")
                if self.toolTipAnimation:
                    print("[DEBUG] Button has toolTipAnimation, visible: {}".format(self.toolTipAnimation.isVisible()))
                    if not self.toolTipAnimation.isVisible():
                        print("[DEBUG] Calling show() on tooltip")
                        self.toolTipAnimation.show(event.globalPos())
                        return True
                else:
                    print("[DEBUG] Button has NO toolTipAnimation")
            elif event.type() == QtCore.QEvent.Leave and self.toolTipAnimation:
                print("[DEBUG] Leave event triggered, hiding tooltip")
                self.toolTipAnimation.maybeHide()
        except Exception as e:
            print("[DEBUG] Exception in event handler: {}".format(str(e)))
            pass
        
        # Call parent class event handler
        try:
            return QtWidgets.QPushButton.event(self, event)
        except Exception:
            return False


class HaxExporterHelpDialog(QtWidgets.QDialog):
    """
    Help dialog for Hax Game Exporter with feature descriptions and example GIF buttons.
    """
    
    def __init__(self, parent=maya_main_window()):
        super(HaxExporterHelpDialog, self).__init__(parent)
        
        self.setWindowTitle("Hax Game Exporter - Help")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        
        # Make window non-modal and remove the ? button
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowCloseButtonHint)
        
        # Get the resources directory path
        self.resources_dir = self.get_resources_path()
        
        # Track all buttons with tooltips for cleanup
        self.tooltip_buttons = []
        
        self.create_widgets()
        self.create_layout()
    
    def closeEvent(self, event):
        """Clean up all resources when dialog closes"""
        # Clean up all tooltip animations to release file locks
        for button in self.tooltip_buttons:
            try:
                if hasattr(button, 'cleanup'):
                    button.cleanup()
            except:
                pass
        
        # Clear the list and remove references
        self.tooltip_buttons = []
        
        # Call parent close event directly (avoid super() issues with exec())
        try:
            QtWidgets.QDialog.closeEvent(self, event)
        except:
            event.accept()
    
    def get_resources_path(self):
        """Get the path to the Resources folder in Maya's scripts directory"""
        maya_script_dir = cmds.internalVar(userScriptDir=True)
        resources_path = os.path.join(maya_script_dir, "hax_exporter_data", "Resources")
        print("[DEBUG] Resources path: {}".format(resources_path))
        print("[DEBUG] Resources path exists: {}".format(os.path.exists(resources_path)))
        if os.path.exists(resources_path):
            files = os.listdir(resources_path)
            print("[DEBUG] Files in Resources: {}".format(files))
        return resources_path
    
    def create_widgets(self):
        """Create all widgets for the help dialog"""
        # Main scroll area
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        # Container widget for scroll area
        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setSpacing(15)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title_label = QtWidgets.QLabel("Hax Game Exporter - Help")
        title_font = QtGui.QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2a7ae2;")
        self.scroll_layout.addWidget(title_label)
        
        # Add separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.scroll_layout.addWidget(separator)
        
        # Add each feature section
        self.add_feature_section(
            "Presets",
            "Save and load sets of export settings, root joints, animation layer states, and rotation offset settings. "
            "Use the dropdown to select, the Save Preset button to save, and Add/Remove Joints to manage root joints for each preset. "
            "When a preset is selected, you can choose to update the current preset or create a new one. When selecting a preset, "
            "if any joints use a valid namespace, you will be prompted to set the Namespace dropdown accordingly. "
            "<b>Presets are stored in the hax_exporter_data folder in your maya scripts directory and can be shared!</b>",
            "presets_example.gif"
        )
        
        self.add_feature_section(
            "Namespace Dropdown",
            "Filter joints by namespace for export. The dropdown only shows namespaces present in both the scene and the reference viewer. "
            "Use the Refresh button to update both the Namespace and Preset dropdowns. If a preset contains joints with a valid namespace, "
            "you will be prompted to set the Namespace dropdown after the UI is drawn.",
            "namespace_example.gif"
        )
        
        self.add_feature_section(
            "Animation Clips",
            "Define multiple animation clips for export. Each clip has a name, start/end frames, FPS, and enable/disable toggle. "
            "Use the checkboxes to select which clips to export. Use the up/down arrows to reorder, and the duplicate/delete buttons to manage clips. "
            "The <b>Frame</b> button applies the clip's frame range to the timeline, while the <b>Set</b> button captures the current timeline range and sets it to the clip.",
            "animation_clips_example.gif"
        )
        
        self.add_feature_section(
            "Animation Layers",
            "Control which animation layers are active during export. Check/uncheck layers to enable or disable them for the export process. "
            "The original layer states are restored after export. <b>Base Animation</b> layers (including those from different namespaces) "
            "are automatically grayed out and cannot be disabled. Layer states are saved with your scene data and included in presets and text exports.",
            "animation_layers_example.gif"
        )
        
        self.add_feature_section(
            "Rotation Offset",
            "Apply a rotation offset to a specific joint or control during export using an additive animation layer. "
            "Enable the checkbox, select a joint/control using the Grab button, and set X/Y/Z rotation values in degrees. "
            "The offset is keyed on the first frame, baked during export, and the animation layer is automatically deleted afterward. "
            "Rotation offset settings are saved with presets and scene data.",
            "rotation_offset_example.gif"
        )
        
        self.add_feature_section(
            "Export Path & Prefix",
            "Set the folder where FBX files will be exported and a filename prefix. The filename preview updates in real time as you edit these fields or the clip name. "
            "<b>The prefix is always respected, even after loading a preset or editing the field right before export.</b>",
            "export_path_example.gif"
        )
        
        self.add_feature_section(
            "Overwrite Dialog",
            "When exporting, if a file already exists, the overwrite confirmation dialog now always shows the full filename (including prefix) for clarity."
        )
        
        self.add_feature_section(
            "Export Mode",
            "Choose between exporting all clips or only the checked (enabled) clips.",
            "export_mode_example.gif"
        )
        
        self.add_feature_section(
            "Settings",
            "Choose FBX file type (Binary/ASCII), FBX version, and options like Embed Media, Bake Animation, and Move To Origin. "
            "<b>Move To Origin</b> now zeroes both translation and rotation of the root joint during export, and restores them after export. "
            "<b>Alt Root Control:</b> Use the Grab button to set the control from your current selection, or clear the field if nothing is selected."
        )
        
        self.add_feature_section(
            "Import/Export Data",
            "Import animation clip data from Maya Game Exporter or a text file, and export your current clip data for backup or sharing.",
            "import_export_example.gif"
        )
        
        self.add_feature_section(
            "Logging",
            "All actions, errors, and warnings are logged to HaxExporterOutputLog.txt in your Maya project directory. "
            "Use the Open Log button to view it. The UI is robust against errors and will log issues instead of showing disruptive dialogs. "
            "<b>Note:</b> UI field values are always up-to-date before export, even if you edit them immediately before exporting."
        )
        
        self.add_feature_section(
            "Export Confirmation",
            "After a successful export, you will see a confirmation popup with a random famous anime quote for a bit of fun and motivation!"
        )
        
        # Tips section
        self.add_tips_section()
        
        # Add stretch at the end
        self.scroll_layout.addStretch()
        
        # Set scroll widget
        self.scroll_area.setWidget(self.scroll_widget)
        
        # Close button
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        self.close_button.setMinimumHeight(30)
    
    def add_feature_section(self, title, description, gif_filename=None):
        """Add a feature section with title, description, and optional Show Example button"""
        # Container frame for the feature
        feature_frame = QtWidgets.QFrame()
        feature_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        feature_frame.setStyleSheet("QFrame { background-color: #2d2d2d; border-radius: 5px; padding: 8px; }")
        
        feature_layout = QtWidgets.QVBoxLayout(feature_frame)
        feature_layout.setSpacing(8)
        
        # Top row: Title and optional Show Example button
        top_layout = QtWidgets.QHBoxLayout()
        
        # Title
        title_label = QtWidgets.QLabel(title)
        title_font = QtGui.QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #e67e22;")
        top_layout.addWidget(title_label)
        
        top_layout.addStretch()
        
        # Show Example button (only if gif_filename is provided)
        if gif_filename:
            print("[DEBUG] Creating Show Example button for: {} with GIF: {}".format(title, gif_filename))
            example_button = ButtonIcon("Show Example")
            example_button.setMaximumWidth(120)
            example_button.setMinimumHeight(24)
            example_button.setStyleSheet("""
                QPushButton {
                    background-color: #3a7ca5;
                    color: white;
                    border-radius: 3px;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #4a8cb5;
                }
            """)
            
            # Set the GIF tooltip
            gif_path = os.path.join(self.resources_dir, gif_filename)
            print("[DEBUG] Full GIF path: {}".format(gif_path))
            example_button.setToolTipImage(gif_path, width=400)
            
            # Track this button for cleanup
            if hasattr(self, 'tooltip_buttons'):
                self.tooltip_buttons.append(example_button)
                print("[DEBUG] Button added to tooltip_buttons list (total: {})".format(len(self.tooltip_buttons)))
            
            top_layout.addWidget(example_button)
        else:
            print("[DEBUG] No GIF filename provided for section: {}".format(title))
        
        feature_layout.addLayout(top_layout)
        
        # Description
        desc_label = QtWidgets.QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #cccccc;")
        desc_label.setTextFormat(QtCore.Qt.RichText)
        feature_layout.addWidget(desc_label)
        
        self.scroll_layout.addWidget(feature_frame)
    
    def add_tips_section(self):
        """Add the tips section"""
        # Container frame for tips
        tips_frame = QtWidgets.QFrame()
        tips_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        tips_frame.setStyleSheet("QFrame { background-color: #2d2d2d; border-radius: 5px; padding: 8px; }")
        
        tips_layout = QtWidgets.QVBoxLayout(tips_frame)
        tips_layout.setSpacing(8)
        
        # Title
        tips_title = QtWidgets.QLabel("Tips")
        title_font = QtGui.QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        tips_title.setFont(title_font)
        tips_title.setStyleSheet("color: #e74c3c;")
        tips_layout.addWidget(tips_title)
        
        # Tips text
        tips_text = """
• Double-check your export path and prefix before exporting.<br>
• Use presets to quickly switch between different export setups.<br>
• Use the Refresh button if you add or remove namespaces or presets.<br>
• If you encounter errors, check the log file for details.<br>
• When prompted about namespaces, it is usually best to confirm so your export matches the intended joint set.<br>
• Use the Set button to quickly capture timeline ranges for clips.<br>
• Animation layer states are preserved and restored after export.<br>
• Rotation offsets use additive animation layers for clean, non-destructive edits.<br>
• The tool is compatible with both Python 2 and 3 in Maya.
        """
        
        tips_label = QtWidgets.QLabel(tips_text.strip())
        tips_label.setWordWrap(True)
        tips_label.setStyleSheet("color: #cccccc;")
        tips_label.setTextFormat(QtCore.Qt.RichText)
        tips_layout.addWidget(tips_label)
        
        self.scroll_layout.addWidget(tips_frame)
    
    def create_layout(self):
        """Create the main layout"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 10)
        main_layout.addWidget(self.scroll_area)
        main_layout.addWidget(self.close_button)


def show_hax_exporter_help():
    """Show the Hax Exporter help dialog (non-modal)"""
    if pyside_version is None:
        cmds.warning("PySide is not available. Cannot show help dialog.")
        return
    
    try:
        # Close ALL existing help dialogs (handles hidden, minimized, orphaned, etc.)
        close_all_help_dialogs()
        
        # Give Qt time to process deletions
        import time
        time.sleep(0.1)
        
        # Create and show new dialog
        dialog = HaxExporterHelpDialog()
        dialog.show()
        
        # Keep a reference to prevent garbage collection (only one instance)
        show_hax_exporter_help.current_dialog = dialog
        
        return dialog
    except Exception as e:
        import traceback
        error_msg = "Error showing help dialog:\n{}".format(traceback.format_exc())
        cmds.warning(error_msg)


def close_all_help_dialogs():
    """Close all open help dialogs and release all resources"""
    # Close the tracked dialog
    if hasattr(show_hax_exporter_help, 'current_dialog'):
        try:
            dialog = show_hax_exporter_help.current_dialog
            if dialog:
                # Use explicit cleanup method
                try:
                    if hasattr(dialog, 'tooltip_buttons'):
                        for button in dialog.tooltip_buttons:
                            try:
                                if hasattr(button, 'cleanup'):
                                    button.cleanup()
                            except:
                                pass
                        dialog.tooltip_buttons = []
                except:
                    pass
                
                # Now close and delete the dialog
                dialog.close()
                dialog.deleteLater()
                show_hax_exporter_help.current_dialog = None
        except:
            pass
    
    # Scan for ANY dialogs with our title or class name
    try:
        app = QtWidgets.QApplication.instance()
        if app:
            dialogs_to_close = []
            
            # Get ALL widgets (not just top-level)
            all_widgets = app.allWidgets()
            for widget in all_widgets:
                try:
                    # Check if it's a dialog with our title or class name
                    if isinstance(widget, QtWidgets.QDialog):
                        title_match = (hasattr(widget, 'windowTitle') and 
                                     widget.windowTitle() == "Hax Game Exporter - Help")
                        class_match = widget.__class__.__name__ == 'HaxExporterHelpDialog'
                        
                        if title_match or class_match:
                            dialogs_to_close.append(widget)
                except:
                    pass
            
            # Close all found dialogs
            for dialog in dialogs_to_close:
                try:
                    # Use explicit cleanup method
                    if hasattr(dialog, 'tooltip_buttons'):
                        for button in dialog.tooltip_buttons:
                            try:
                                if hasattr(button, 'cleanup'):
                                    button.cleanup()
                            except:
                                pass
                    
                    dialog.close()
                    dialog.deleteLater()
                except:
                    pass
            
            # Force processing multiple times to ensure cleanup
            for _ in range(3):
                QtWidgets.QApplication.processEvents()
    except:
        pass


# Entry point - called when script is executed
show_hax_exporter_help() 
