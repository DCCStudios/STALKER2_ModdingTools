# HaxGameExporterInstaller.py
# This script installs the Hax Game Exporter to Maya's scripts folder and creates a shelf button
# Compatible with Maya 2019 and Python 2.7/3.x

from __future__ import print_function
import maya.cmds as cmds
import maya.mel as mel
import os
import shutil
import traceback
import inspect
import sys

# Python 2/3 compatibility helpers
def is_py2():
    return sys.version_info[0] == 2

def execfile_compat(filename, globals_=None, locals_=None):
    if is_py2():
        execfile(filename, globals_, locals_)
    else:
        with open(filename, 'r') as f:
            code = f.read()
        exec(compile(code, filename, 'exec'), globals_ if globals_ is not None else globals(), locals_)

def reload_compat(module):
    if is_py2():
        reload(module)
    else:
        import importlib
        importlib.reload(module)

# Button specifications
BUTTON_LABEL = "HaxGameExporter"
BUTTON_TOOLTIP = "A Better Game Exporter"
ICON_FILENAME = "HGE_icon.png"

def onMayaDroppedPythonFile(obj):
    """Required function for Maya drag and drop functionality."""
    try:
        install_hax_game_exporter()
    except Exception as e:
        error_msg = "An unexpected error occurred:\n" + str(e) + "\n\nSee script editor for details."
        show_error_dialog(error_msg)
        print(traceback.format_exc())

def install_hax_game_exporter():
    """Install the Hax Game Exporter script to Maya's scripts folder and create a shelf button."""
    try:
        # Get the source file path using multiple methods to ensure it works in all scenarios
        source_file = None
        installer_dir = None
        
        # Method 1: Try to get from the current file's directory (works in script editor)
        try:
            installer_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
            potential_source = os.path.join(installer_dir, "HaxGameExporter.py")
            if os.path.exists(potential_source):
                source_file = potential_source
        except Exception:
            pass
            
        # Method 2: Try to get from __file__ (sometimes works when dragged and dropped)
        if not source_file:
            try:
                installer_dir = os.path.dirname(os.path.abspath(__file__))
                potential_source = os.path.join(installer_dir, "HaxGameExporter.py")
                if os.path.exists(potential_source):
                    source_file = potential_source
            except Exception:
                pass
                
        # Method 3: Try to find the script in Maya's recent script paths
        if not source_file:
            try:
                # Get the directory of the most recently executed script
                latest_command = mel.eval("$temp = $gCommandLine")
                if latest_command and os.path.isfile(latest_command):
                    installer_dir = os.path.dirname(latest_command)
                    potential_source = os.path.join(installer_dir, "HaxGameExporter.py")
                    if os.path.exists(potential_source):
                        source_file = potential_source
            except Exception:
                pass
        
        # If still can't find the source, prompt user to locate it
        if not source_file:
            result = cmds.confirmDialog(
                title='Source File Not Found',
                message='Could not automatically locate HaxGameExporter.py.\nIt should be in the same folder as this installer.\n\nDo you want to manually select the file?',
                button=['Yes', 'No'],
                defaultButton='Yes',
                cancelButton='No',
                dismissString='No'
            )
            
            if result == 'Yes':
                file_paths = cmds.fileDialog2(fileFilter="Python Files (*.py);;All Files (*.*)", dialogStyle=2, fileMode=1)
                if file_paths and len(file_paths) > 0:
                    source_file = file_paths[0]
                    installer_dir = os.path.dirname(source_file)
                else:
                    show_error_dialog("Installation aborted: No file selected.")
                    return False
            else:
                show_error_dialog("Installation aborted: Source file not found.")
                return False
        
        # Get Maya's user script directory
        maya_script_dir = cmds.internalVar(userScriptDir=True)
        destination_file = os.path.join(maya_script_dir, "HaxGameExporter.py")
        
        # Display what we're about to do
        cmds.inViewMessage(amg="Installing HaxGameExporter.py...", pos='topCenter', fade=True)
        print("Source file:", source_file)
        print("Destination:", destination_file)
        
        # Check if the destination file exists
        if os.path.exists(destination_file):
            result = cmds.confirmDialog(
                title='Overwrite Existing File?',
                message='HaxGameExporter.py already exists in the scripts directory. Overwrite?',
                button=['Yes', 'No'],
                defaultButton='Yes',
                cancelButton='No',
                dismissString='No'
            )
            if result != 'Yes':
                show_error_dialog("Installation aborted: User chose not to overwrite existing file.")
                return False
        
        # Copy the file without modifying it
        try:
            shutil.copy2(source_file, destination_file)
            if not os.path.exists(destination_file):
                raise Exception("File copy operation did not create the destination file")
        except Exception as e:
            error_msg = "Failed to copy file: " + str(e)
            show_error_dialog(error_msg)
            return False
        
        # Copy the icon file if it exists
        icon_path = None
        if installer_dir:
            source_icon = os.path.join(installer_dir, ICON_FILENAME)
            if os.path.exists(source_icon):
                try:
                    # Get Maya's prefs/icons directory
                    maya_icon_dir = os.path.join(os.path.dirname(cmds.internalVar(userPrefDir=True)), "prefs", "icons")
                    
                    # Create icons directory if it doesn't exist
                    if not os.path.exists(maya_icon_dir):
                        os.makedirs(maya_icon_dir)
                    
                    destination_icon = os.path.join(maya_icon_dir, ICON_FILENAME)
                    shutil.copy2(source_icon, destination_icon)
                    icon_path = destination_icon
                    print("Copied icon file to:", destination_icon)
                except Exception as e:
                    print("Warning: Could not copy icon file:", str(e))
        
        # Remove existing button with the same label/tooltip if it exists
        remove_existing_button()
        
        # Create the shelf button on the current shelf
        button_created = create_shelf_button(icon_path)
        
        # Create presets folder if it doesn't exist
        presets_dir = os.path.join(maya_script_dir, "custom_game_exporter_presets")
        if not os.path.exists(presets_dir):
            try:
                os.makedirs(presets_dir)
                print("Created presets directory:", presets_dir)
            except Exception as e:
                print("Note: Could not create presets directory:", str(e))
        
        # Installation complete message
        if button_created:
            show_success_dialog("Hax Game Exporter successfully installed!", 
                               "Script location: {}\n\nShelf button created on current shelf.".format(destination_file))
        else:
            show_partial_success_dialog("Script installed but shelf button creation failed.", 
                                      "You can run the exporter with this Python command:\nimport HaxGameExporter; HaxGameExporter.initialize_exporter()")
        
        return True
    except Exception:
        error_msg = "Error installing HaxGameExporter:\n" + traceback.format_exc()
        show_error_dialog(error_msg)
        return False

def remove_existing_button():
    """Remove any existing shelf button with the same label/tooltip."""
    try:
        # Get the current shelf
        gShelfTopLevel = mel.eval('$temp=$gShelfTopLevel')
        if not cmds.tabLayout(gShelfTopLevel, exists=True):
            return False
            
        current_shelf = cmds.tabLayout(gShelfTopLevel, query=True, selectTab=True)
        if not cmds.shelfLayout(current_shelf, exists=True):
            return False
        
        # Get all shelf buttons
        shelf_buttons = cmds.shelfLayout(current_shelf, query=True, childArray=True) or []
        
        for btn in shelf_buttons:
            try:
                # Check if this is our button based on label and annotation
                if cmds.shelfButton(btn, exists=True):
                    label = cmds.shelfButton(btn, query=True, label=True)
                    annotation = cmds.shelfButton(btn, query=True, annotation=True)
                    
                    if label == BUTTON_LABEL and annotation == BUTTON_TOOLTIP:
                        cmds.deleteUI(btn)
                        print("Removed existing HaxGameExporter button")
                        return True
            except Exception:
                pass
        
        return False
    except Exception:
        error_msg = "Error removing existing button:\n" + traceback.format_exc()
        print(error_msg)
        return False

def create_shelf_button(custom_icon_path=None):
    """Create a shelf button for the Hax Game Exporter on the current shelf."""
    try:
        # Get the current shelf
        gShelfTopLevel = mel.eval('$temp=$gShelfTopLevel')
        if not cmds.tabLayout(gShelfTopLevel, exists=True):
            cmds.warning("Could not find the shelf tab layout.")
            return False
            
        current_shelf = cmds.tabLayout(gShelfTopLevel, query=True, selectTab=True)
        if not cmds.shelfLayout(current_shelf, exists=True):
            cmds.warning("Could not find the current shelf: " + str(current_shelf))
            return False
        
        # Create the command to run the exporter - with special handling to ensure it loads correctly
        command = '''
import maya.cmds as cmds
import traceback
import sys
import os

def is_py2():
    return sys.version_info[0] == 2

def execfile_compat(filename, globals_=None, locals_=None):
    if is_py2():
        execfile(filename, globals_, locals_)
    else:
        with open(filename, 'r') as f:
            code = f.read()
        exec(compile(code, filename, 'exec'), globals_ if globals_ is not None else globals(), locals_)

def reload_compat(module):
    if is_py2():
        reload(module)
    else:
        import importlib
        importlib.reload(module)

try:
    # Get Maya script path
    script_path = cmds.internalVar(userScriptDir=True)
    script_file = os.path.join(script_path, "HaxGameExporter.py")
    
    # Check if the file exists
    if not os.path.exists(script_file):
        cmds.warning("HaxGameExporter.py not found at: " + script_file)
        raise ImportError("HaxGameExporter module not found")
        
    # Try to import normally first
    try:
        import HaxGameExporter
        reload_compat(HaxGameExporter)  # Reload to get any changes
    except (ImportError, SyntaxError) as e:
        cmds.warning("Standard import failed: " + str(e) + ". Trying alternative method...")
        
        # If we get here, there was an issue importing the module normally
        # Try to execfile() the Python file directly which can sometimes work around certain import issues
        execfile_compat(script_file)
        
        # The execfile should have defined initialize_exporter() function in the global namespace
        if 'initialize_exporter' in globals():
            initialize_exporter()
        else:
            cmds.warning("Could not find initialize_exporter function after loading script")
            raise Exception("initialize_exporter function not found")
    else:
        # If import succeeded, run normally
        HaxGameExporter.initialize_exporter()
        
except ImportError:
    cmds.warning("HaxGameExporter module not found. Please ensure it's installed in Maya's scripts directory.")
except Exception:
    error_msg = "Error launching HaxGameExporter:\\n" + traceback.format_exc()
    cmds.warning(error_msg)
    print(error_msg)
'''
        
        # Determine which icon to use
        icon = "commandButton.png"  # Default fallback
        
        # First try our custom icon
        if custom_icon_path and os.path.exists(custom_icon_path):
            icon = custom_icon_path
            print("Using custom icon:", icon)
        else:
            # Otherwise, try to find a suitable built-in icon
            icons_to_try = ["game.png", "animationEditor.png", "goToBindPose.png", "export.png", "playblast.png"]
            for test_icon in icons_to_try:
                try:
                    # Try to get Maya's icon path
                    icon_paths = mel.eval('getenv XBMLANGPATH')
                    if icon_paths:
                        for path in icon_paths.split(';'):
                            icon_path = os.path.join(path, test_icon)
                            if os.path.exists(icon_path):
                                icon = test_icon
                                break
                        if icon != "commandButton.png":
                            break
                except Exception:
                    pass
        
        # Create the shelf button with our specified label and tooltip
        button = cmds.shelfButton(
            parent=current_shelf,
            label=BUTTON_LABEL,
            annotation=BUTTON_TOOLTIP,
            image=icon,
            command=command,
            sourceType="python"
        )
        
        if button:
            print("Created shelf button successfully!")
            return True
        else:
            cmds.warning("Failed to create shelf button.")
            return False
    except Exception:
        error_msg = "Error creating shelf button:\n" + traceback.format_exc()
        cmds.warning(error_msg)
        print(error_msg)
        return False

def show_success_dialog(title_message, detail_message=""):
    """Show a success dialog with the specified message."""
    result = cmds.confirmDialog(
        title='Installation Successful',
        message=title_message + "\n\n" + detail_message,
        button=['OK'],
        defaultButton='OK'
    )
    cmds.inViewMessage(amg=title_message, pos='topCenter', fade=True)
    print(title_message)
    if detail_message:
        print(detail_message)

def show_partial_success_dialog(title_message, detail_message=""):
    """Show a partial success dialog with the specified message."""
    result = cmds.confirmDialog(
        title='Partial Installation Success',
        message=title_message + "\n\n" + detail_message,
        button=['OK'],
        defaultButton='OK'
    )
    cmds.inViewMessage(amg=title_message, pos='topCenter', fade=True)
    print(title_message)
    if detail_message:
        print(detail_message)

def show_error_dialog(error_message):
    """Show an error dialog with the specified message."""
    result = cmds.confirmDialog(
        title='Installation Failed',
        message=error_message,
        button=['OK'],
        defaultButton='OK'
    )
    cmds.warning(error_message)
    print(error_message)

# This allows the script to be executed when run from the script editor
if __name__ == "__main__":
    # Wrap in a try-except to ensure errors are visible
    try:
        success = install_hax_game_exporter()
        if not success:
            # In case the function returns False without raising an exception
            show_error_dialog("Installation failed to complete successfully.")
    except Exception as e:
        error_msg = "An unexpected error occurred:\n" + str(e) + "\n\nSee script editor for details."
        show_error_dialog(error_msg)
        print(traceback.format_exc()) 