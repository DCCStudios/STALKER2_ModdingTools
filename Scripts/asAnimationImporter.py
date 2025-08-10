#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
============================================================================
Game Animation Reference Pose Importer - Python Version
Compatible with Python 2.7 and Python 3.x
============================================================================

Uses reference pose data to apply transforms to skeleton joints
Author: Generated for STALKER2 Animation Pipeline

USAGE:
1. Paste this script into Maya Script Editor (Python tab)
2. Execute the script
3. UI will open automatically, or run: animation_importer_ui()

============================================================================
"""

# Python 2/3 compatibility imports
from __future__ import print_function, division, absolute_import
try:
    # Python 2
    import Tkinter as tk
    from Tkinter import ttk, messagebox
    import tkFileDialog as filedialog
    basestring
except ImportError:
    # Python 3
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    basestring = str

import maya.cmds as cmds
import json
import os
import sys
import importlib
import time

# For toolkit integration
try:
    from stalker2_toolkit.PrintSkeletonHierarchy import print_hierarchy_with_transforms, save_reference_pose_data, generate_mel_zero_pose_script
    toolkit_integration = True
except ImportError:
    toolkit_integration = False

# Global variables
WINDOW_NAME = "asAnimImporterWindow"
GAMES = {
    "STALKER 2": "stalker2",
    "Fallout New Vegas": "falloutnv", 
    "Skyrim": "skyrimse",
    "Dungeon Crawler": "dc"
}

# Frame range settings file
FRAME_RANGE_FILE = "frame_range_settings.json"

# Dark styling flag for toolkit integration
USE_DARK_STYLE = False

class AnimationImporter(object):
    """Main Animation Importer class"""
    
    def __init__(self, use_dark_style=False):
        self.window = None
        self.game_var = None
        self.status_var = None
        self.start_frame_field = None
        self.end_frame_field = None
        self.saved_start_frame = -1
        self.saved_end_frame = 100  # Default end frame
        global USE_DARK_STYLE
        USE_DARK_STYLE = use_dark_style
        self.load_frame_range_settings()
        self.setup_ui()
    
    def setup_ui(self):
        """Create the main UI window"""
        # Close existing window if it exists
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME)
        
        # Create Maya window
        window_title = "S.T.A.L.K.E.R. 2 Animation Importer" if USE_DARK_STYLE else "Advanced Skeleton 5 - Animation Importer"
        
        self.window = cmds.window(
            WINDOW_NAME,
            title=window_title,
            widthHeight=(450, 450),
            sizeable=True,
            resizeToFitChildren=True
        )
        
        # Main layout
        main_layout = cmds.columnLayout(
            adjustableColumn=True,
            rowSpacing=10,
            columnOffset=('both', 10),
            parent=self.window
        )
        
        # Title
        title_text = "S.T.A.L.K.E.R. 2 Animation Importer" if USE_DARK_STYLE else "Advanced Skeleton 5 - Animation Importer"
        cmds.text(
            label=title_text,
            font="boldLabelFont",
            height=25,
            parent=main_layout
        )
        cmds.separator(height=15, parent=main_layout)
        
        # Animation file selection frame
        anim_frame = cmds.frameLayout(
            label="Animation File",
            collapsable=False,
            labelAlign="center",
            parent=main_layout
        )
        
        anim_column = cmds.columnLayout(
            adjustableColumn=True,
            parent=anim_frame
        )
        
        anim_row = cmds.rowLayout(
            numberOfColumns=3,
            columnWidth3=(80, 250, 80),
            columnAttach3=("left", "both", "right"),
            parent=anim_column
        )
        
        cmds.text(label="File:", parent=anim_row)
        self.anim_file_field = cmds.textField(editable=False, parent=anim_row)
        cmds.button(
            label="Browse...",
            command=lambda x: self.browse_animation_file(),
            parent=anim_row
        )
        
        cmds.setParent(anim_column)
        cmds.separator(height=10, parent=anim_column)
        
        # Game selection frame
        cmds.setParent(main_layout)
        game_frame = cmds.frameLayout(
            label="Game Selection",
            collapsable=False,
            labelAlign="center",
            parent=main_layout
        )
        
        game_column = cmds.columnLayout(
            adjustableColumn=True,
            parent=game_frame
        )
        
        game_row = cmds.rowLayout(
            numberOfColumns=2,
            columnWidth2=(100, 200),
            parent=game_column
        )
        
        cmds.text(label="Game:", parent=game_row)
        self.game_menu = cmds.optionMenu(parent=game_row)
        
        # Populate game menu
        for game_name in GAMES.keys():
            cmds.menuItem(label=game_name, parent=self.game_menu)
        
        cmds.setParent(game_column)
        cmds.text(
            label="Loads reference pose and applies game-specific setup",
            font="smallPlainLabelFont",
            parent=game_column
        )
        cmds.separator(height=10, parent=game_column)
        
        # Instructions frame
        cmds.setParent(main_layout)
        instructions_frame = cmds.frameLayout(
            label="Instructions",
            collapsable=False,
            labelAlign="center",
            parent=main_layout
        )
        
        instructions_column = cmds.columnLayout(
            adjustableColumn=True,
            parent=instructions_frame
        )
        
        cmds.text(
            label="1. Browse and select an animation file to import",
            align="left",
            parent=instructions_column
        )
        cmds.text(
            label="2. Choose the correct game from the dropdown",
            align="left", 
            parent=instructions_column
        )
        cmds.text(
            label="3. Click Import Animation to process the file",
            align="left",
            parent=instructions_column
        )
        cmds.separator(height=5, parent=instructions_column)
        cmds.text(
            label="See README button for detailed workflow instructions",
            align="left",
            font="obliqueLabelFont",
            parent=instructions_column
        )
        cmds.separator(height=10, parent=instructions_column)
        
        # Frame Range Settings
        cmds.setParent(main_layout)
        frame_range_frame = cmds.frameLayout(
            label="Frame Range Settings",
            collapsable=False,
            labelAlign="center",
            parent=main_layout
        )
        
        frame_range_column = cmds.columnLayout(
            adjustableColumn=True,
            parent=frame_range_frame
        )
        
        frame_range_row = cmds.rowLayout(
            numberOfColumns=4,
            columnWidth4=(100, 80, 100, 80),
            columnAttach4=("right", "left", "right", "left"),
            parent=frame_range_column
        )
        
        cmds.text(label="Start Frame:", parent=frame_range_row)
        self.start_frame_field = cmds.intField(
            value=self.saved_start_frame,
            width=75,
            parent=frame_range_row,
            changeCommand=lambda x: self.save_frame_range_settings()
        )
        
        cmds.text(label="End Frame:", parent=frame_range_row)
        self.end_frame_field = cmds.intField(
            value=self.saved_end_frame,
            width=75,
            parent=frame_range_row,
            changeCommand=lambda x: self.save_frame_range_settings()
        )
        
        cmds.setParent(frame_range_column)
        cmds.text(
            label="These frame ranges will be used for both Import and Create Reference operations",
            font="smallPlainLabelFont",
            parent=frame_range_column
        )
        
        # Action buttons
        cmds.setParent(main_layout)
        cmds.separator(height=15, parent=main_layout)
        
        # Create a column layout for centered buttons with padding
        button_column = cmds.columnLayout(
            adjustableColumn=True,
            parent=main_layout
        )
        
        # Use formLayout for centering buttons
        button_form = cmds.formLayout(
            numberOfDivisions=100,
            parent=button_column
        )
        
        # Create buttons with consistent width and add padding between them
        button_width = 110
        button_height = 30
        padding = 10  # Padding between buttons
        
        # README button
        readme_btn = cmds.button(
            label="README",
            width=button_width,
            height=button_height,
            command=lambda x: self.show_readme(),
            backgroundColor=(0.2, 0.2, 0.3) if USE_DARK_STYLE else (0.9, 1.0, 1.0)
        )
        
        # Import Animation button
        import_btn = cmds.button(
            label="Import Animation",
            width=button_width,
            height=button_height,
            command=lambda x: self.import_animation(),
            backgroundColor=(0.2, 0.3, 0.2) if USE_DARK_STYLE else (0.8, 1.0, 0.8)
        )
        
        # Create Reference button (new)
        reference_btn = cmds.button(
            label="Create Reference",
            width=button_width,
            height=button_height,
            command=lambda x: self.create_reference(),
            backgroundColor=(0.3, 0.3, 0.4) if USE_DARK_STYLE else (0.9, 0.9, 1.0)
        )
        
        # MoCap Matcher button
        matcher_btn = cmds.button(
            label="MoCap Matcher",
            width=button_width,
            height=button_height,
            command=lambda x: self.open_mocap_matcher(),
            backgroundColor=(0.2, 0.3, 0.4) if USE_DARK_STYLE else (0.8, 0.9, 1.0)
        )
        
        # Anim Cleanup button
        cleanup_btn = cmds.button(
            label="Anim Cleanup",
            width=button_width,
            height=button_height,
            command=lambda x: self.anim_cleanup(),
            backgroundColor=(0.3, 0.25, 0.15) if USE_DARK_STYLE else (1.0, 0.9, 0.6)
        )
        
        # Cancel button
        cancel_btn = cmds.button(
            label="Cancel",
            width=button_width,
            height=button_height,
            command=lambda x: cmds.deleteUI(self.window),
            backgroundColor=(0.4, 0.2, 0.2) if USE_DARK_STYLE else (1.0, 0.8, 0.8)
        )
        
        # Position buttons horizontally centered with equal spacing
        cmds.formLayout(
            button_form, 
            edit=True,
            attachPosition=[
                (readme_btn, "left", padding, 0),
                (import_btn, "left", padding, 17),
                (reference_btn, "left", padding, 34),
                (matcher_btn, "left", padding, 51),
                (cleanup_btn, "left", padding, 68),
                (cancel_btn, "left", padding, 85),
                
                (readme_btn, "right", padding, 17),
                (import_btn, "right", padding, 34),
                (reference_btn, "right", padding, 51),
                (matcher_btn, "right", padding, 68),
                (cleanup_btn, "right", padding, 85),
                (cancel_btn, "right", padding, 100)
            ]
        )
        
        # Options/Settings Frame
        cmds.setParent(main_layout)
        cmds.separator(height=5, parent=main_layout)
        settings_frame = cmds.frameLayout(
            label="Advanced Options",
            collapsable=True,
            collapse=True,
            labelAlign="center",
            parent=main_layout
        )
        
        settings_column = cmds.columnLayout(
            adjustableColumn=True,
            parent=settings_frame
        )
        
        # Add checkbox for locator-based cleanup
        self.use_locators_cleanup = cmds.checkBox(
            label="Use Locators for Cleanup",
            value=False,
            annotation="Use temporary locators for alignment during cleanup process",
            parent=settings_column
        )
        
        # Status text
        cmds.setParent(main_layout)
        cmds.separator(height=10, parent=main_layout)
        self.status_text = cmds.text(
            label="Browse for animation file, choose game, then click Import...",
            parent=main_layout
        )
        
        # Show window
        cmds.showWindow(self.window)
    
    def browse_animation_file(self):
        """Open file browser to select animation file"""
        file_filter = "Animation Files (*.fbx *.ma *.mb);;FBX Files (*.fbx);;Maya Files (*.ma *.mb);;All Files (*.*)"
        
        result = cmds.fileDialog2(
            fileMode=1,
            caption="Select Animation File",
            fileFilter=file_filter
        )
        
        if result:
            file_path = result[0]
            cmds.textField(self.anim_file_field, edit=True, text=file_path)
            
            # Extract filename for status
            filename = os.path.basename(file_path)
            self.update_status("Animation file selected: {}".format(filename))
    def create_reference(self):
        """Open file browser to select and reference a Maya file"""
        file_filter = "Maya Files (*.ma *.mb);;Maya ASCII (*.ma);;Maya Binary (*.mb);;All Files (*.*)"
        
        self.update_status("Select a Maya file to reference...")
        
        result = cmds.fileDialog2(
            fileMode=1,
            caption="Select Maya File to Reference",
            fileFilter=file_filter
        )
        
        if result:
            ref_file_path = result[0]
            try:
                # Get the filename without path for the namespace
                import os
                file_name = os.path.basename(ref_file_path)
                namespace = os.path.splitext(file_name)[0]
                
                # Reference the file with options
                cmds.file(
                    ref_file_path, 
                    reference=True,      # Create a reference
                    namespace=namespace, # Use filename as namespace
                    options="v=0",       # No prompting about version
                    mergeNamespacesOnClash=False,
                    ignoreVersion=True
                )
                
                # Set timeline using our saved frame range settings
                try:
                    # Get our saved frame range settings
                    min_time = self.saved_start_frame
                    max_time = self.saved_end_frame
                    
                    print(f"// Using stored frame range settings: Start={min_time}, End={max_time}")
                    
                    # Apply the stored frame range
                    cmds.playbackOptions(min=min_time, max=max_time)
                    cmds.playbackOptions(animationStartTime=min_time, animationEndTime=max_time)
                    
                    # Go to start frame
                    cmds.currentTime(min_time)
                    
                    print(f"// Timeline set to stored frame range: {min_time} to {max_time}")
                    self.update_status(f"Applied frame range: {min_time} to {max_time}")
                    
                    # Also store info about the referenced file's timeline for debugging
                    try:
                        ref_nodes = cmds.referenceQuery(namespace + ":", referenceNode=True, topReference=True)
                        if ref_nodes:
                            ref_node = ref_nodes[0]
                            source_start = cmds.getAttr(ref_node + ".sourceStart") if cmds.attributeQuery("sourceStart", node=ref_node, exists=True) else None
                            source_end = cmds.getAttr(ref_node + ".sourceEnd") if cmds.attributeQuery("sourceEnd", node=ref_node, exists=True) else None
                            
                            if source_start is not None and source_end is not None:
                                print(f"// Referenced file's original frame range: {source_start} to {source_end}")
                    except Exception as e:
                        print(f"// Note: Could not query referenced file's source frame range: {str(e)}")
                    
                except Exception as e:
                    print(f"// Warning: Could not set timeline: {str(e)}")
                
                self.update_status(f"Referenced file: {file_name}")
                print(f"// Created reference to {ref_file_path} with namespace '{namespace}'")
                
            except Exception as e:
                self.update_status(f"Error creating reference: {str(e)}")
                print(f"// Error creating reference: {str(e)}")
        else:
            self.update_status("Reference creation cancelled.")
    
    def get_game_codename(self):
        """Get the codename for the selected game"""
        selected_game = cmds.optionMenu(self.game_menu, query=True, value=True)
        return GAMES.get(selected_game, "stalker2")
    
    def find_joint_in_hierarchy(self, joint_name, root_joint):
        """Find a joint or control by name in the hierarchy, handling namespaces"""
        # First try exact match
        if cmds.objExists(joint_name):
            return joint_name
        
        # Get all joints and transforms in the hierarchy (to include control curves)
        try:
            # First get joints
            all_joints = cmds.listRelatives(root_joint, allDescendents=True, type="joint") or []
            all_joints.append(root_joint)  # Include root
            
            # Now get transforms (for control curves)
            all_transforms = cmds.listRelatives(root_joint, allDescendents=True, type="transform") or []
            
            # Combine both lists (remove duplicates)
            all_nodes = list(set(all_joints + all_transforms))
        except:
            return ""
        
        # First check for exact control names (with _ctrl suffix)
        if joint_name.endswith("_ctrl"):
            base_name = joint_name[:-5]  # Remove _ctrl suffix
            for node in all_nodes:
                # Check if node ends with _ctrl
                if node.endswith("_ctrl"):
                    # Get short name without namespace
                    short_name = node.split(":")[-1] if ":" in node else node
                    # Check if it matches our target
                    if short_name == joint_name:
                        return node
                    # Also check without _ctrl suffix
                    short_name_base = short_name[:-5] if short_name.endswith("_ctrl") else short_name
                    if short_name_base == base_name:
                        return node
        
        # Then check for normal joint names
        for node in all_nodes:
            # Get short name without namespace
            short_name = node.split(":")[-1] if ":" in node else node
            
            if short_name == joint_name:
                return node
        
        return ""  # Not found
    
    def update_status(self, message):
        """Update the status text"""
        cmds.text(self.status_text, edit=True, label=message)
        cmds.refresh()
        
    def get_frame_range_settings_path(self):
        """Get the path to the frame range settings file"""
        # First check in Maya's scripts directory
        scripts_dir = cmds.internalVar(userScriptDir=True)
        data_dir = os.path.join(scripts_dir, "animation_importer_data")
        
        # Create the directory if it doesn't exist
        if not os.path.exists(data_dir):
            try:
                os.makedirs(data_dir)
            except Exception as e:
                print(f"// Warning: Could not create directory: {data_dir}. Error: {str(e)}")
                return None
                
        return os.path.join(data_dir, FRAME_RANGE_FILE)
        
    def save_frame_range_settings(self):
        """Save frame range settings to file"""
        # Get values from UI
        if self.start_frame_field and self.end_frame_field:
            self.saved_start_frame = cmds.intField(self.start_frame_field, query=True, value=True)
            self.saved_end_frame = cmds.intField(self.end_frame_field, query=True, value=True)
        
        # Get file path
        settings_path = self.get_frame_range_settings_path()
        if not settings_path:
            print("// Warning: Could not determine settings file path.")
            return
            
        # Create settings data
        settings = {
            "start_frame": self.saved_start_frame,
            "end_frame": self.saved_end_frame,
            "last_updated": time.time()
        }
        
        # Save to file
        try:
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=4)
            print(f"// Frame range settings saved: Start={self.saved_start_frame}, End={self.saved_end_frame}")
        except Exception as e:
            print(f"// Error saving frame range settings: {str(e)}")
    
    def load_frame_range_settings(self):
        """Load frame range settings from file"""
        settings_path = self.get_frame_range_settings_path()
        if not settings_path or not os.path.exists(settings_path):
            # Use defaults if file doesn't exist
            return
            
        try:
            with open(settings_path, 'r') as f:
                settings = json.load(f)
                
            self.saved_start_frame = settings.get("start_frame", -1)
            self.saved_end_frame = settings.get("end_frame", 100)
            print(f"// Loaded frame range settings: Start={self.saved_start_frame}, End={self.saved_end_frame}")
            
            # Update UI if it exists
            if hasattr(self, "start_frame_field") and cmds.intField(self.start_frame_field, exists=True):
                cmds.intField(self.start_frame_field, edit=True, value=self.saved_start_frame)
            
            if hasattr(self, "end_frame_field") and cmds.intField(self.end_frame_field, exists=True):
                cmds.intField(self.end_frame_field, edit=True, value=self.saved_end_frame)
                
        except Exception as e:
            print(f"// Error loading frame range settings: {str(e)}")
    
    def show_readme(self):
        """Show the README popup with game-specific workflow instructions"""
        # Check if window already exists and delete it
        if cmds.window("asAnimImporterReadme", exists=True):
            cmds.deleteUI("asAnimImporterReadme")
            
        # Create a new window
        readme_window = cmds.window(
            "asAnimImporterReadme",
            title="Advanced Skeleton 5 - Animation Workflow Guide",
            widthHeight=(500, 600),
            sizeable=True
        )
        
        # Main layout
        main_layout = cmds.columnLayout(
            adjustableColumn=True,
            rowSpacing=10,
            columnOffset=('both', 10),
            parent=readme_window
        )
        
        # Title
        cmds.text(
            label="Animation Import Workflow Guide",
            font="boldLabelFont",
            height=30,
            parent=main_layout
        )
        cmds.separator(height=10, parent=main_layout)
        
        # Create a tab layout for different games
        tabs = cmds.tabLayout(parent=main_layout)
        
        # STALKER 2 Tab
        stalker_tab = cmds.columnLayout(
            adjustableColumn=True,
            rowSpacing=5,
            columnOffset=('both', 5)
        )
        
        cmds.text(
            label="STALKER 2 Workflow",
            font="boldLabelFont",
            align="left"
        )
        cmds.separator(height=10)
        
        # STALKER 2 steps
        cmds.text(label="1. Save the file as S2_Animation_Import.ma", align="left")
        cmds.text(label="2. Open S2_Rig_Final.ma", align="left")
        cmds.text(label="3. Hit the Create Reference button and select your animation maya file (S2_Animation_Import.ma)", align="left")
        cmds.text(label="4. Open AdvancedSkeleton 5", align="left")
        cmds.text(label="5. Open the MocapMatcher and load the Stalker2 preset", align="left")
        cmds.text(label="6. Detect the namespace for your imported animation", align="left")
        cmds.text(label="7. Set the rig to all FK Controls", align="left")
        cmds.text(label="8. Connect the Mocap Skeleton", align="left")
        cmds.text(label="9. Bake down the Mocap data", align="left")
        cmds.text(label="10. Hit the Cleanup button", align="left")
        
        # Set the parent back to the tab layout
        cmds.setParent('..')
        
        # Fallout New Vegas Tab
        falloutnv_tab = cmds.columnLayout(
            adjustableColumn=True,
            rowSpacing=5,
            columnOffset=('both', 5)
        )
        
        cmds.text(
            label="Fallout New Vegas Workflow",
            font="boldLabelFont",
            align="left"
        )
        cmds.separator(height=10)
        
        # Fallout New Vegas steps
        cmds.text(label="1. Save the imported animation file", align="left")
        cmds.text(label="2. Open your character rig file", align="left")
        cmds.text(label="3. Reference the animation file", align="left")
        cmds.text(label="4. Use the MocapMatcher with the Fallout preset", align="left")
        cmds.text(label="5. Perform any needed cleanup", align="left")
        
        # Set the parent back to the tab layout
        cmds.setParent('..')
        
        # Skyrim Tab
        skyrim_tab = cmds.columnLayout(
            adjustableColumn=True,
            rowSpacing=5,
            columnOffset=('both', 5)
        )
        
        cmds.text(
            label="Skyrim Workflow",
            font="boldLabelFont",
            align="left"
        )
        cmds.separator(height=10)
        
        # Skyrim steps
        cmds.text(label="1. Save the imported animation file", align="left")
        cmds.text(label="2. Open your character rig file", align="left")
        cmds.text(label="3. Reference the animation file", align="left")
        cmds.text(label="4. Use the MocapMatcher with the Skyrim preset", align="left")
        cmds.text(label="5. Perform any needed cleanup", align="left")
        
        # Set the parent back to the tab layout
        cmds.setParent('..')
        
        # Dungeon Crawler Tab
        dc_tab = cmds.columnLayout(
            adjustableColumn=True,
            rowSpacing=5,
            columnOffset=('both', 5)
        )
        
        cmds.text(
            label="Dungeon Crawler Workflow",
            font="boldLabelFont",
            align="left"
        )
        cmds.separator(height=10)
        
        # Dungeon Crawler steps
        cmds.text(label="1. Save the imported animation file", align="left")
        cmds.text(label="2. Open your character rig file", align="left")
        cmds.text(label="3. Reference the animation file", align="left")
        cmds.text(label="4. Use the MocapMatcher with the appropriate preset", align="left")
        cmds.text(label="5. Perform any needed cleanup", align="left")
        
        # Set the parent back to the tab layout
        cmds.setParent('..')
        
        # Add the tabs to the tab layout
        cmds.tabLayout(
            tabs, 
            edit=True,
            tabLabel=(
                (stalker_tab, "STALKER 2"),
                (falloutnv_tab, "Fallout New Vegas"),
                (skyrim_tab, "Skyrim"),
                (dc_tab, "Dungeon Crawler")
            )
        )
        
        # Add a close button at the bottom
        cmds.separator(height=10, parent=main_layout)
        cmds.button(
            label="Close",
            command=lambda x: cmds.deleteUI("asAnimImporterReadme"),
            backgroundColor=(0.4, 0.2, 0.2) if USE_DARK_STYLE else (1.0, 0.8, 0.8),
            parent=main_layout
        )
        
        # Show window
        cmds.showWindow(readme_window)
    
    def open_mocap_matcher(self):
        """Open the Advanced Skeleton MoCap Matcher window"""
        try:
            import maya.mel as mel
            
            # Check if Advanced Skeleton is loaded by testing for a known function
            if not mel.eval('exists("asGetScriptLocation")'):
                # Try to load Advanced Skeleton
                self.update_status("Loading Advanced Skeleton...")
                
                # Try common Advanced Skeleton loading methods
                try:
                    # Method 1: Try to source the main Advanced Skeleton file
                    mel.eval('source "AdvancedSkeleton.mel"')
                except:
                    try:
                        # Method 2: Try alternative loading
                        mel.eval('asMain')
                    except:
                        self.update_status("Error: Advanced Skeleton not found. Please load Advanced Skeleton first.")
                        print("// Advanced Skeleton is not loaded.")
                        print("// Please load Advanced Skeleton manually and try again.")
                        return
            
            # Now try to open the MoCap Matcher
            mel.eval('asMoCapMatcherUI "asPicker"')
            self.update_status("MoCap Matcher window opened.")
            print("// Opened Advanced Skeleton MoCap Matcher")
            
        except Exception as e:
            self.update_status("Error: Could not open MoCap Matcher - {}".format(str(e)))
            print("// Error opening MoCap Matcher: {}".format(str(e)))
            print("// Please ensure Advanced Skeleton is properly loaded:")
            print("//   1. Load Advanced Skeleton plugin/scripts")
            print("//   2. Try manually: asMoCapMatcherUI \"asPicker\"")
    
    def anim_cleanup(self):
        """Perform post-MoCap matching cleanup operations"""
        try:
            # Get the selected game
            game_code = self.get_game_codename()
            
            # Look for game-specific cleanup file
            # First try to find data dir relative to this script's location
            script_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Look directly in Maya's scripts directory
            scripts_dir = cmds.internalVar(userScriptDir=True)
            data_dir = os.path.join(scripts_dir, "animation_importer_data")
            cleanup_file = os.path.join(data_dir, "{}_anim_cleanup.py".format(game_code))
            
            if os.path.exists(cleanup_file):
                self.update_status("Running {} animation cleanup...".format(game_code))
                
                # Get checkbox value for locator-based cleanup
                use_locators = cmds.checkBox(self.use_locators_cleanup, query=True, value=True)
                
                # Create context for cleanup script
                cleanup_globals = {
                    'cmds': cmds,
                    'game_code': game_code,
                    'print': print,
                    'os': os,
                    'self': self,  # Pass self so cleanup script can use helper methods
                    'use_locators_for_cleanup': use_locators  # Pass the checkbox value
                }
                
                # Execute the cleanup file
                with open(cleanup_file, 'r') as f:
                    cleanup_code = f.read()
                
                exec(cleanup_code, cleanup_globals)
                print("// Applied {} animation cleanup from {}".format(game_code, cleanup_file))
                
            else:
                # Fallback to built-in cleanup
                print("// No custom cleanup file found: {}".format(cleanup_file))
                self.apply_builtin_cleanup(game_code)
                
        except Exception as e:
            self.update_status("Error during animation cleanup: {}".format(str(e)))
            print("// Cleanup Error: {}".format(str(e)))
    
    def apply_builtin_cleanup(self, game_code):
        """Apply built-in game-specific cleanup as fallback"""
        if game_code == "stalker2":
            self.stalker2_anim_cleanup()
        elif game_code == "falloutnv":
            print("// Fallout New Vegas cleanup - no specific cleanup defined yet")
        elif game_code == "skyrimse":
            print("// Skyrim SE cleanup - no specific cleanup defined yet")
        elif game_code == "dc":
            print("// Dungeon Crawler cleanup - no specific cleanup defined yet")
        else:
            print("// No specific cleanup available for game: {}".format(game_code))
    
    def stalker2_anim_cleanup(self):
        """Built-in STALKER 2 animation cleanup"""
        print("// STALKER 2 cleanup - no specific cleanup defined yet")
    
    def import_animation(self):
        """Main animation import process"""
        # Get animation file path
        anim_file = cmds.textField(self.anim_file_field, query=True, text=True)
        if not anim_file or anim_file.strip() == "":
            self.update_status("Error: Please select an animation file!")
            return
        
        if not os.path.exists(anim_file):
            self.update_status("Error: Animation file does not exist!")
            return
        
        self.update_status("Importing animation file...")
        
        try:
            # Step 1: Import animation file without namespace
            # Get list of existing objects before import
            existing_objects = set(cmds.ls(assemblies=True))
            
            # Set import options to match the UI settings shown in the screenshot
            cmds.file(
                anim_file, 
                i=True,
                options="v=0",
                loadReferenceDepth="all",
                preserveReferences=True,
                importFrameRate=True,           # Framerate Import: Maintain Original
                importTimeRange="override"      # Animation Range: Override to Match Source
            )
            self.update_status("Animation imported, organizing into group...")
            
            # Step 2: Find newly imported objects
            all_objects = set(cmds.ls(assemblies=True))
            imported_objects = list(all_objects - existing_objects)
            
            if not imported_objects:
                self.update_status("Error: No objects were imported from the animation file!")
                return
            
            # Step 3: Create AnimImport group and parent imported objects
            group_name = "AnimImport"
            if cmds.objExists(group_name):
                cmds.delete(group_name)
            
            anim_import_group = cmds.group(empty=True, name=group_name)
            
            # Parent all imported objects to the group
            for obj in imported_objects:
                try:
                    cmds.parent(obj, anim_import_group)
                except:
                    print("// Warning: Could not parent {} to AnimImport group".format(obj))
                    continue
            
            print("// Created AnimImport group with {} objects".format(len(imported_objects)))
            
            # Step 4: Find the root joint in the imported skeleton
            root_joint = self.find_imported_skeleton_root_in_group(group_name)
            if not root_joint:
                self.update_status("Error: Could not find skeleton root in imported animation!")
                return
            
            print("// Found imported skeleton root: {}".format(root_joint))
            
            # Step 5: Apply reference pose on frame -1
            self.apply_reference_pose_internal(root_joint)
            
            # Set timeline to start at frame -1 after import is complete
            try:
                min_time = -1  # Always start at -1
                
                # Get current timeline settings that were imported from the file
                current_min = cmds.playbackOptions(query=True, min=True)
                current_max = cmds.playbackOptions(query=True, max=True)
                current_anim_start = cmds.playbackOptions(query=True, animationStartTime=True)
                current_anim_end = cmds.playbackOptions(query=True, animationEndTime=True)
                
                # Keep the end frame from the import but set start to -1
                cmds.playbackOptions(min=min_time, max=current_max)
                cmds.playbackOptions(animationStartTime=min_time, animationEndTime=current_anim_end)
                
                # Update our stored frame range settings
                self.saved_start_frame = min_time
                self.saved_end_frame = current_max
                
                # Update UI if it exists
                if hasattr(self, "start_frame_field") and cmds.intField(self.start_frame_field, exists=True):
                    cmds.intField(self.start_frame_field, edit=True, value=min_time)
                
                if hasattr(self, "end_frame_field") and cmds.intField(self.end_frame_field, exists=True):
                    cmds.intField(self.end_frame_field, edit=True, value=current_max)
                
                # Save settings to file
                self.save_frame_range_settings()
                
                # Go to start frame
                cmds.currentTime(min_time)
                print(f"// Timeline adjusted: Start frame set to {min_time}, keeping end frame at {current_max}")
            except Exception as e:
                print(f"// Warning: Could not set timeline start frame: {str(e)}")
            
            # Step 6: Apply game-specific import setup
            game_code = self.get_game_codename()
            self.apply_game_import_setup(game_code, group_name)
            
            self.update_status("Animation import complete! Applied reference pose and game setup.")
            print("// Animation import process completed successfully")
            
        except Exception as e:
            self.update_status("Error during import: {}".format(str(e)))
            print("// Import Error: {}".format(str(e)))
    
    def find_imported_skeleton_root_in_group(self, group_name):
        """Find the root joint of the imported skeleton within the AnimImport group"""
        # Get all joints that are children of the group (at any level)
        joints_in_group = []
        
        # Get all descendants of the group
        descendants = cmds.listRelatives(group_name, allDescendents=True, type="joint")
        if descendants:
            joints_in_group = descendants
        
        if not joints_in_group:
            print("// Warning: No joints found in {} group".format(group_name))
            return None
        
        # Find root joints (joints with no parent joints within the group)
        root_joints = []
        for joint in joints_in_group:
            # Get parent
            parent = cmds.listRelatives(joint, parent=True, type="joint")
            
            # Check if parent is also in our group
            if parent:
                parent_in_group = False
                for p in parent:
                    if p in joints_in_group:
                        parent_in_group = True
                        break
                
                # If parent is not in group, this joint is a root
                if not parent_in_group:
                    root_joints.append(joint)
            else:
                # No parent at all, definitely a root
                root_joints.append(joint)
        
        if not root_joints:
            print("// Warning: No root joints found in {} group".format(group_name))
            return None
        
        if len(root_joints) > 1:
            print("// Warning: Multiple root joints found: {}".format(root_joints))
            print("// Using first root joint: {}".format(root_joints[0]))
        
        return root_joints[0]
    
    def apply_game_import_setup(self, game_code, group_name):
        """Apply game-specific import setup logic"""
        # First try to find data dir relative to this script's location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Check if we're in the subfolder structure
        if os.path.basename(script_dir) == "stalker2_toolkit":
            data_dir = os.path.join(script_dir, "animation_importer_data")
        else:
            # Try adjacent folder
            data_dir = os.path.join(script_dir, "animation_importer_data")
        
        # Fallback to Maya scripts directory
        if not os.path.exists(data_dir):
            scripts_dir = cmds.internalVar(userScriptDir=True)
            data_dir = os.path.join(scripts_dir, "stalker2_toolkit", "animation_importer_data")
            
            # Another fallback for older structure
            if not os.path.exists(data_dir):
                data_dir = os.path.join(scripts_dir, "animation_importer_data")
        setup_file = os.path.join(data_dir, "{}_import_setup.py".format(game_code))
        
        # Check if game-specific setup file exists
        if os.path.exists(setup_file):
            try:
                self.update_status("Applying {}_import_setup...".format(game_code))
                
                # Create a local context for the setup script
                setup_globals = {
                    'cmds': cmds,
                    'group_name': group_name,
                    'game_code': game_code,
                    'print': print,
                    'os': os
                }
                
                # Execute the setup file
                with open(setup_file, 'r') as f:
                    setup_code = f.read()
                
                exec(setup_code, setup_globals)
                print("// Applied {} setup from {}".format(game_code, setup_file))
                
            except Exception as e:
                print("// Warning: Failed to execute {} setup: {}".format(game_code, str(e)))
                # Fallback to built-in setup if file fails
                self.apply_builtin_setup(game_code, group_name)
        else:
            print("// No custom setup file found: {}".format(setup_file))
            print("// Falling back to built-in setup for {}".format(game_code))
            self.apply_builtin_setup(game_code, group_name)
    
    def apply_builtin_setup(self, game_code, group_name):
        """Apply built-in game-specific setup as fallback"""
        if game_code == "stalker2":
            self.apply_stalker2_setup(group_name)
        elif game_code == "falloutnv":
            self.apply_falloutnv_setup(group_name)
        elif game_code == "skyrimse":
            self.apply_skyrimse_setup(group_name)
        elif game_code == "dc":
            self.apply_dc_setup(group_name)
        else:
            print("// No specific setup available for game: {}".format(game_code))
    
    def apply_stalker2_setup(self, group_name):
        """Apply STALKER 2 specific import setup"""
        try:
            self.update_status("Applying STALKER 2 import setup...")
            
            # The AnimImport group already exists and contains the imported skeleton
            # Just rotate the group -90 degrees in Y axis
            if cmds.objExists(group_name):
                cmds.setAttr("{}.rotateY".format(group_name), -90)
                print("// STALKER 2 setup complete: Rotated {} group -90Y".format(group_name))
            else:
                print("// Warning: {} group not found for STALKER 2 setup".format(group_name))
            
        except Exception as e:
            print("// Error in STALKER 2 setup: {}".format(str(e)))
    
    def apply_falloutnv_setup(self, group_name):
        """Apply Fallout New Vegas specific import setup"""
        print("// Fallout New Vegas setup - no specific setup defined yet")
    
    def apply_skyrimse_setup(self, group_name):
        """Apply Skyrim SE specific import setup"""
        print("// Skyrim SE setup - no specific setup defined yet")
    
    def apply_dc_setup(self, group_name):
        """Apply Dungeon Crawler specific import setup"""
        print("// Dungeon Crawler setup - no specific setup defined yet")
    
    def apply_reference_pose(self):
        """Apply reference pose transforms to selected skeleton (UI wrapper)"""
        # Get selected objects
        selection = cmds.ls(selection=True)
        if not selection:
            self.update_status("Error: Please select the root joint of your skeleton!")
            return
        
        root_joint = selection[0]
        
        # Check if it's a joint
        if cmds.objectType(root_joint) != "joint":
            self.update_status("Error: Selected object is not a joint!")
            return
        
        # Call internal method
        self.apply_reference_pose_internal(root_joint)
    
    def apply_reference_pose_internal(self, root_joint):
        """Internal method to apply reference pose transforms"""
        self.update_status("Loading reference pose data...")
        
        # Get game codename and build file path
        game_code = self.get_game_codename()
        
        # First try to find data dir relative to this script's location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Check if we're in the subfolder structure
        if os.path.basename(script_dir) == "stalker2_toolkit":
            data_dir = os.path.join(script_dir, "animation_importer_data")
        else:
            # Try adjacent folder
            data_dir = os.path.join(script_dir, "animation_importer_data")
        
        # Fallback to Maya scripts directory
        if not os.path.exists(data_dir):
            scripts_dir = cmds.internalVar(userScriptDir=True)
            data_dir = os.path.join(scripts_dir, "stalker2_toolkit", "animation_importer_data")
            
            # Another fallback for older structure
            if not os.path.exists(data_dir):
                data_dir = os.path.join(scripts_dir, "animation_importer_data")
        json_file = os.path.join(data_dir, "{}_reference_pose.json".format(game_code))
        
        if not os.path.exists(json_file):
            self.update_status("Error: Reference pose file not found in scripts/animation_importer_data/")
            print("// Expected file: {}".format(json_file))
            return
        
        # Read and parse JSON file
        self.update_status("Applying reference pose transforms...")
        
        try:
            with open(json_file, 'r') as f:
                pose_data = json.load(f)
        except Exception as e:
            self.update_status("Error: Failed to read JSON file!")
            print("// JSON Error: {}".format(str(e)))
            return
        
        # Set timeline to frame -1
        cmds.currentTime(-1)
        print("// Setting reference pose on frame -1")
        
        transforms_applied = 0
        successfully_transformed_joints = []
        
        # Apply transforms to each joint
        for joint_name, transform_data in pose_data.items():
            # Find the joint in hierarchy
            found_joint = self.find_joint_in_hierarchy(joint_name, root_joint)
            
            if found_joint:
                try:
                    # Apply translate
                    if 'translate' in transform_data:
                        t = transform_data['translate']
                        cmds.setAttr("{}.translate".format(found_joint), t[0], t[1], t[2])
                    
                    # Apply rotate
                    if 'rotate' in transform_data:
                        r = transform_data['rotate']
                        cmds.setAttr("{}.rotate".format(found_joint), r[0], r[1], r[2])
                    
                    # Apply joint orient
                    if 'jointOrient' in transform_data:
                        jo = transform_data['jointOrient']
                        cmds.setAttr("{}.jointOrient".format(found_joint), jo[0], jo[1], jo[2])
                    
                    # Apply scale
                    if 'scale' in transform_data:
                        s = transform_data['scale']
                        cmds.setAttr("{}.scale".format(found_joint), s[0], s[1], s[2])
                    
                    # Store successfully transformed joint
                    successfully_transformed_joints.append(found_joint)
                    transforms_applied += 1
                    
                except Exception as e:
                    print("// Warning: Failed to apply transforms to {}: {}".format(found_joint, str(e)))
                    continue
        
        # Set keyframes on frame -1 for all successfully transformed joints
        if successfully_transformed_joints:
            try:
                keyed_joints = []
                for found_joint in successfully_transformed_joints:
                    try:
                        # Key all transform attributes on frame -1
                        cmds.setKeyframe(found_joint, time=-1, attribute='translate')
                        cmds.setKeyframe(found_joint, time=-1, attribute='rotate')
                        cmds.setKeyframe(found_joint, time=-1, attribute='jointOrient')
                        cmds.setKeyframe(found_joint, time=-1, attribute='scale')
                        keyed_joints.append(found_joint)
                        
                    except Exception as e:
                        print("// Warning: Failed to keyframe {}: {}".format(found_joint, str(e)))
                        continue
                
                print("// Keyframed {} joints on frame -1".format(len(keyed_joints)))
                
            except Exception as e:
                print("// Warning: Failed to keyframe joints: {}".format(str(e)))
        
        print("// Reference pose applied: {} joints transformed and keyframed on frame -1".format(transforms_applied))


# Global instance
_importer_instance = None

def reload_animation_importer():
    """Reload the animation importer script"""
    global _importer_instance
    
    # Close existing window if it exists
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)
    
    # Clear the global instance
    _importer_instance = None
    
    # Clear Python module cache if this module exists
    import sys
    module_name = __name__
    if module_name in sys.modules:
        # Force reload by removing from cache
        del sys.modules[module_name]
    
    print("// Animation Importer reloaded and ready")

def animation_importer_ui(use_dark_style=False):
    """Main function to create and show the UI"""
    global _importer_instance
    _importer_instance = AnimationImporter(use_dark_style=use_dark_style)
    return _importer_instance

def get_game_codename():
    """Standalone function to get game codename"""
    if _importer_instance:
        return _importer_instance.get_game_codename()
    return "stalker2"

def apply_reference_pose():
    """Standalone function to apply reference pose"""
    if _importer_instance:
        _importer_instance.apply_reference_pose()

# Convenience functions for MEL compatibility
def asAnimationImporter(use_dark_style=False):
    """MEL-compatible function name"""
    return animation_importer_ui(use_dark_style=use_dark_style)

def asAnimImporterApplyReferencePose():
    """MEL-compatible function name"""
    return apply_reference_pose()

def asAnimImporterGetGameCodename():
    """MEL-compatible function name"""
    return get_game_codename()


# ============================================================================
# SCRIPT INITIALIZATION
# ============================================================================

# Auto-initialize when script is executed
print("// ============================================================================")
print("// Game Animation Reference Pose Importer - Python Version LOADED")
print("// ============================================================================")
print("// READY TO USE:")
print("//   Type: animation_importer_ui()")
print("//   Or MEL compatible: asAnimationImporter()")
print("// ============================================================================")

# Auto-open the UI when script is executed directly
if __name__ == "__main__":
    animation_importer_ui()

# ============================================================================
# GAME SETUP FILES
# ============================================================================

"""
GAME SETUP FILES:
The importer looks for game-specific setup files in:
~/maya/scripts/animation_importer_data/

Required files:
- stalker2_import_setup.py    (rotates group -90Y)
- falloutnv_import_setup.py   (custom Fallout NV setup)
- skyrimse_import_setup.py    (custom Skyrim SE setup)
- dc_import_setup.py          (custom Dungeon Crawler setup)

Each setup file receives these variables:
- cmds: Maya commands module
- group_name: Name of the AnimImport group ("AnimImport")
- game_code: Selected game code ("stalker2", "falloutnv", etc.)
- print: Python print function
- os: Python os module

Example stalker2_import_setup.py:
-----------------------------------
print("// Executing STALKER 2 import setup...")
if cmds.objExists(group_name):
    cmds.setAttr("{}.rotateY".format(group_name), -90)
    print("// Rotated {} group -90Y".format(group_name))
"""

# ============================================================================
# SHELF BUTTON CODE EXAMPLES
# ============================================================================

"""
SHELF BUTTON CODE (Copy one of these for your shelf button):

Option 1 - If script is in Maya scripts directory:
---------------------------------------------------
import maya.cmds as cmds
import sys
scripts_dir = cmds.internalVar(userScriptDir=True)
script_path = scripts_dir + 'asAnimationImporter.py'
if script_path in [m.__file__ for m in sys.modules.values() if hasattr(m, '__file__')]:
    reload_animation_importer()
exec(open(script_path).read())

Option 2 - If script is in specific location:
--------------------------------------------
import maya.cmds as cmds
import sys
script_path = r'G:\STALKER2_AnimationSource\AdvancedSkeleton Reference\asAnimationImporter.py'
# Force reload by clearing cache
for module_name in list(sys.modules.keys()):
    if 'asAnimationImporter' in module_name:
        del sys.modules[module_name]
exec(open(script_path).read())

Option 3 - Simple reload if already loaded:
------------------------------------------
try:
    reload_animation_importer()
    animation_importer_ui()
except:
    # Fallback to full reload
    exec(open(r'path\to\asAnimationImporter.py').read())

Option 4 - Most Reliable (Recommended):
--------------------------------------
import maya.cmds as cmds
import sys
import os

# Define script path
script_path = r'G:\STALKER2_AnimationSource\AdvancedSkeleton Reference\asAnimationImporter.py'

# Clear any existing modules
for module_name in list(sys.modules.keys()):
    if 'asAnimationImporter' in module_name:
        del sys.modules[module_name]

# Close existing window
if cmds.window('asAnimImporterWindow', exists=True):
    cmds.deleteUI('asAnimImporterWindow')

# Execute script
if os.path.exists(script_path):
    exec(open(script_path).read())
else:
    print("Script file not found: " + script_path)
"""