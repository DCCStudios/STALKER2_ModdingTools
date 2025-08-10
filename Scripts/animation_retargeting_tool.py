'''
Name: animation_retargeting_tool

Description: Transfer animation data between rigs or transfer raw mocap from a skeleton to a custom rig.
 
Author: Joar Engberg 2021

Installation:
Add animation_retargeting_tool.py to your Maya scripts folder (Username\Documents\maya\scripts).
To start the tool within Maya, run these this lines of code from the Maya script editor or add them to a shelf button:

import animation_retargeting_tool
animation_retargeting_tool.start()
 
'''
from collections import OrderedDict
import os
import sys
import json
import webbrowser
import maya.mel
import maya.cmds as cmds
from functools import partial
import maya.OpenMayaUI as omui

maya_version = int(cmds.about(version=True))

if maya_version < 2025:
    from shiboken2 import wrapInstance
    from PySide2 import QtCore, QtGui, QtWidgets
else:
    from shiboken6 import wrapInstance
    from PySide6 import QtCore, QtGui, QtWidgets


def maya_main_window():
    # Return the Maya main window as QMainWindow
    main_window = omui.MQtUtil.mainWindow()
    if sys.version_info.major >= 3:
        return wrapInstance(int(main_window), QtWidgets.QWidget)
    else:
        return wrapInstance(long(main_window), QtWidgets.QWidget) # type: ignore


class RetargetingTool(QtWidgets.QDialog):
    '''
    Retargeting tool class
    ''' 
    WINDOW_TITLE = "Animation Retargeting Tool"
 
    # Class variable to store the active preset data
    active_preset_data = None
 
    def __init__(self):
        super(RetargetingTool, self).__init__(maya_main_window())
        
        self.script_job_ids = []
        self.connection_ui_widgets = []
        self.color_counter = 0
        self.maya_color_index = OrderedDict([(13, "red"), (18, "cyan"), (14, "lime"), (17, "yellow")])
        self.cached_connect_nodes = []
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.resize(400, 300)
        self.create_ui_widgets()
        self.create_ui_layout()
        self.create_ui_connections()
        self.create_script_jobs()

        if cmds.about(macOS=True):
            self.setWindowFlags(QtCore.Qt.Tool)
 
    def create_ui_widgets(self):
        self.refresh_button = QtWidgets.QPushButton(QtGui.QIcon(":refresh.png"), "")
        self.simple_conn_button = QtWidgets.QPushButton("Create Connection")
        self.ik_conn_button = QtWidgets.QPushButton("Create IK Connection")
        self.bake_button = QtWidgets.QPushButton("Bake Animation")
        self.bake_button.setStyleSheet("background-color: lightgreen; color: black")
        self.batch_bake_button = QtWidgets.QPushButton("Batch Bake And Export ...")
        self.load_preset_button = QtWidgets.QPushButton("Load Preset...")
        self.help_button = QtWidgets.QPushButton("?")
        self.help_button.setFixedWidth(25)
        self.rot_checkbox = QtWidgets.QCheckBox("Rotation")
        self.pos_checkbox = QtWidgets.QCheckBox("Translation")
        self.mo_checkbox = QtWidgets.QCheckBox("Maintain Offset")
        self.snap_checkbox = QtWidgets.QCheckBox("Align To Position")
        
        # Store context for preset handling
        self.current_weapon_id = None
        self.current_master_path = None
        self.current_namespace = None
 
    def create_ui_layout(self):
        horizontal_layout_1 = QtWidgets.QHBoxLayout()
        horizontal_layout_1.addWidget(self.pos_checkbox)
        horizontal_layout_1.addWidget(self.rot_checkbox)
        horizontal_layout_1.addWidget(self.snap_checkbox)
        horizontal_layout_1.addStretch()
        horizontal_layout_1.addWidget(self.help_button)
        
        horizontal_layout_2 = QtWidgets.QHBoxLayout()
        horizontal_layout_2.addWidget(self.simple_conn_button)
        horizontal_layout_2.addWidget(self.ik_conn_button)
        
        # Add preset button in a new row
        horizontal_layout_preset = QtWidgets.QHBoxLayout()
        horizontal_layout_preset.addWidget(self.load_preset_button)
        horizontal_layout_preset.addStretch()
        
        horizontal_layout_3 = QtWidgets.QHBoxLayout()
        horizontal_layout_3.addWidget(self.batch_bake_button)
        horizontal_layout_3.addWidget(self.bake_button)
 
        connection_list_widget = QtWidgets.QWidget()
 
        self.connection_layout = QtWidgets.QVBoxLayout(connection_list_widget)
        self.connection_layout.setContentsMargins(2, 2, 2, 2)
        self.connection_layout.setSpacing(3)
        self.connection_layout.setAlignment(QtCore.Qt.AlignTop)
 
        list_scroll_area = QtWidgets.QScrollArea()
        list_scroll_area.setWidgetResizable(True)
        list_scroll_area.setWidget(connection_list_widget)

        separator_line = QtWidgets.QFrame(parent=None)
        separator_line.setFrameShape(QtWidgets.QFrame.HLine)
        separator_line.setFrameShadow(QtWidgets.QFrame.Sunken)
 
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(list_scroll_area)
        main_layout.addLayout(horizontal_layout_1)
        main_layout.addLayout(horizontal_layout_2)
        main_layout.addLayout(horizontal_layout_preset)
        main_layout.addWidget(separator_line)
        main_layout.addLayout(horizontal_layout_3)
 
    def create_ui_connections(self):
        self.simple_conn_button.clicked.connect(self.create_connection_node)
        self.ik_conn_button.clicked.connect(self.create_ik_connection_node)
        self.refresh_button.clicked.connect(self.refresh_ui_list)
        self.bake_button.clicked.connect(self.bake_animation_confirm)
        self.batch_bake_button.clicked.connect(self.open_batch_window)
        self.help_button.clicked.connect(self.help_dialog)
        self.load_preset_button.clicked.connect(self.show_preset_selector)

        self.rot_checkbox.setChecked(True)
        self.pos_checkbox.setChecked(True)
        self.snap_checkbox.setChecked(True)

    def create_script_jobs(self):
        self.script_job_ids.append(cmds.scriptJob(event=["SelectionChanged", partial(self.refresh_ui_list)]))
        self.script_job_ids.append(cmds.scriptJob(event=["NameChanged", partial(self.refresh_ui_list)]))

    def kill_script_jobs(self):
        for id in self.script_job_ids:
            if cmds.scriptJob(exists=id):
                cmds.scriptJob(kill=id)
            else:
                pass
 
    def refresh_ui_list(self):
        self.clear_list()
 
        connect_nodes_in_scene = RetargetingTool.get_connect_nodes()
        self.cached_connect_nodes = connect_nodes_in_scene
        for node in connect_nodes_in_scene:
            connection_ui_item = ListItemWidget(parent_instance=self, connection_node=node)
            self.connection_layout.addWidget(connection_ui_item)
            self.connection_ui_widgets.append(connection_ui_item)
 
    def clear_list(self):
        self.connection_ui_widgets = []
 
        while self.connection_layout.count() > 0:
            connection_ui_item = self.connection_layout.takeAt(0)
            if connection_ui_item.widget():
                connection_ui_item.widget().deleteLater() 
 
    def showEvent(self, event):
        self.refresh_ui_list()
 
    def closeEvent(self, event):
        self.kill_script_jobs()
        self.clear_list()
        
    def load_and_apply_preset(self, json_path, namespace=None):
        """
        Load a JSON preset file and automatically create connections
        
        Args:
            json_path (str): Path to the JSON preset file
            namespace (str): Namespace prefix for imported joints
            
        The JSON preset can contain the following:
        - Joint settings for each joint
        - post_bake_operations: List of operations to perform after baking
        """
        try:
            print("// Loading retargeting preset...")
            
            # Load the JSON preset
            with open(json_path, 'r') as f:
                preset_data = json.load(f)
                
            if not preset_data:
                print("// Warning: Preset file is empty or invalid")
                return
                
            # Store the preset data in the class for later post-bake operations
            RetargetingTool.active_preset_data = preset_data
            
            # Check for post_bake_operations and log if found
            if 'post_bake_operations' in preset_data:
                operations = preset_data['post_bake_operations']
                print(f"// Found {len(operations)} post-bake operations in preset")
                for i, op in enumerate(operations):
                    print(f"//   {i+1}. {op.get('type', 'unknown')} operation: {op}")
            else:
                print("// No post-bake operations found in preset")
                
            print(f"// Successfully loaded preset with {len(preset_data)} entries")
            
            # Store any additional message log for confirmation dialog
            log_messages = []
            
            # First find all joints in the namespace
            all_joints = []
            if namespace:
                # Standardize namespace format
                if not namespace.endswith(":"):
                    namespace_prefix = namespace + ":"
                else:
                    namespace_prefix = namespace
                    
                # Look for joints with this namespace
                all_joints = cmds.ls(f"{namespace_prefix}*", type="joint")
                print(f"// Found {len(all_joints)} joints in namespace {namespace_prefix}")
                
                # Also try without colon (in case Maya didn't add it correctly)
                if not all_joints:
                    all_joints = [j for j in cmds.ls(type="joint") if j.startswith(namespace)]
                    print(f"// Found {len(all_joints)} joints starting with {namespace} (without colon)")
            else:
                all_joints = cmds.ls(type="joint")
            
            if not all_joints:
                print("// Warning: No joints found to retarget")
                log_messages.append("No joints found to retarget")
                return
            
            # Get all the controls in the scene
            all_transforms = cmds.ls(type="transform")
            all_controls = [t for t in all_transforms if "_ctrl" in t.lower() or "_CTRL" in t]
            
            # Gather all the potential joint-control pairs
            retarget_pairs = []
            
            # Process the joints - either using preset settings if available or default settings
            for joint in all_joints:
                # Extract base joint name (remove namespace)
                if namespace and ":" in joint:
                    base_joint_name = joint.split(":")[-1]
                elif namespace and joint.startswith(namespace):
                    base_joint_name = joint[len(namespace):]
                else:
                    base_joint_name = joint
                    
                # Try different naming patterns for controls
                potential_control_names = []
                
                # Try with both _ctrl and _CTRL suffixes
                for suffix in ["_ctrl", "_CTRL"]:
                    base_control_name = f"{base_joint_name}{suffix}"
                    
                    # Try with and without namespace
                    potential_control_names.append(base_control_name)
                
                # Find matching control
                control_found = False
                control_name = None
                
                # First check if any of the potential names exist directly
                for ctrl_name in potential_control_names:
                    matching_controls = [c for c in all_controls if c.endswith(ctrl_name)]
                    if matching_controls:
                        control_found = True
                        control_name = matching_controls[0]
                        break
                
                # If not found, try a more flexible search
                if not control_found:
                    for ctrl in all_controls:
                        if base_joint_name in ctrl:
                            control_found = True
                            control_name = ctrl
                            break
                
                if not control_found:
                    print(f"// No matching control found for joint: {joint}")
                    continue
                
                # Get settings from preset if available, otherwise use defaults
                settings = {}
                if base_joint_name in preset_data:
                    settings = preset_data[base_joint_name]
                    print(f"// Using preset settings for {base_joint_name}")
                else:
                    settings = {"align_position": True}  # Default settings
                    print(f"// Using default settings for {base_joint_name}")
                
                # Extract settings
                align_position = settings.get("align_position", True)
                post_rotate = settings.get("rotate", None)
                
                # Add to retarget pairs
                retarget_pairs.append((joint, control_name, align_position, post_rotate))
                print(f"// Added pair: {joint} -> {control_name} (Align: {align_position})")
            
            # Sort retarget pairs by hierarchy depth if possible
            try:
                # Try to sort by joint hierarchy depth to process from root to leaves
                sorted_pairs = []
                for joint, control, align, rotate in retarget_pairs:
                    try:
                        # Calculate hierarchy depth (number of parents)
                        hierarchy_path = cmds.listRelatives(joint, fullPath=True, allParents=True) or []
                        depth = len(hierarchy_path)
                        sorted_pairs.append((joint, control, align, rotate, depth))
                    except Exception as e:
                        # If we can't get hierarchy, assume it's at depth 999 (will be processed last)
                        sorted_pairs.append((joint, control, align, rotate, 999))
                
                # Sort by depth (lower depth = higher in hierarchy = processed first)
                sorted_pairs.sort(key=lambda x: x[4])
                
                # Extract sorted pairs without depth
                retarget_pairs = [(j, c, a, r) for j, c, a, r, _ in sorted_pairs]
                print("// Successfully sorted pairs by hierarchy depth")
            except Exception as e:
                print(f"// Warning: Could not sort by hierarchy: {str(e)}")
            
            # Show confirmation dialog with all the pairs
            pairs_info = "\n".join([f"{i+1}. {j} -> {c}" for i, (j, c, a, r) in enumerate(retarget_pairs)])
            
            confirm_message = f"Ready to create {len(retarget_pairs)} connections from preset:\n\n"
            confirm_message += pairs_info
            
            if log_messages:
                confirm_message += "\n\nWarnings:\n" + "\n".join(log_messages)
            
            confirm = cmds.confirmDialog(
                title="Confirm Connections", 
                message=confirm_message,
                button=["Create Connections", "Cancel"],
                defaultButton="Create Connections",
                cancelButton="Cancel",
                dismissString="Cancel"
            )
            
            if confirm != "Create Connections":
                print("// User cancelled automatic connection creation")
                return
            
            # Create connections for confirmed pairs
            for i, (joint, control, align_position, post_rotate) in enumerate(retarget_pairs):
                print(f"// Creating connection {i+1}/{len(retarget_pairs)}: {joint} -> {control}")
                print(f"//   Settings: Align Position: {align_position}, Post Rotate: {post_rotate}")
                
                # Select the joint and control - select via cmds to ensure it works
                try:
                    # Clear current selection
                    cmds.select(clear=True)
                    cmds.refresh()
                    
                    # Select joint first (driver)
                    if not cmds.objExists(joint):
                        print(f"// Error: Joint {joint} no longer exists, skipping")
                        continue
                    cmds.select(joint, replace=True)
                    cmds.refresh()
                    print(f"//   Selected joint: {', '.join(cmds.ls(selection=True))}")
                    
                    # Add control to selection (driven)
                    if not cmds.objExists(control):
                        print(f"// Error: Control {control} no longer exists, skipping")
                        continue
                    cmds.select(control, add=True)
                    cmds.refresh()
                    print(f"//   Selected joint+control: {', '.join(cmds.ls(selection=True))}")
                    
                    # Configure UI settings
                    self.rot_checkbox.setChecked(True)  # Always enable rotation
                    self.pos_checkbox.setChecked(True)  # Always enable position
                    self.snap_checkbox.setChecked(align_position)
                except Exception as e:
                    print(f"//   Error selecting objects: {str(e)}")
                    continue
                
                # Create the connection - using proper UI feedback
                try:
                    # Use the standard method for connection creation
                    self.create_connection_node()
                    print("//   Created connection node")
                    
                    # Refresh the UI list to show the new connection
                    self.refresh_ui_list()
                    
                    # Apply post-rotation if specified
                    if post_rotate:
                        # Wait for connection to be fully created
                        cmds.refresh()
                        cmds.pause(seconds=0.2)
                        
                        # Find the connection node - use the latest nodes from the refresh
                        connection_nodes = RetargetingTool.get_connect_nodes()
                        
                        # Look for connection node with this joint name
                        connection_node = None
                        joint_base_name = joint.split(":")[-1] if ":" in joint else joint
                        
                        for node in connection_nodes:
                            if joint_base_name in node:
                                connection_node = node
                                break
                                
                        if connection_node and cmds.objExists(connection_node):
                            print(f"//   Applying post-rotation {post_rotate} to {connection_node}")
                            rotate_x, rotate_y, rotate_z = post_rotate
                            cmds.select(connection_node, replace=True)
                            cmds.refresh()
                            cmds.rotate(rotate_x, rotate_y, rotate_z, connection_node, relative=True)
                            
                            # Update UI to show rotation
                            cmds.refresh()
                            self.refresh_ui_list()
                        else:
                            print(f"//   Warning: Could not find connection node for {joint_base_name}")
                
                except Exception as e:
                    print(f"//   Error creating connection: {str(e)}")
                
                # Small pause between connections to let UI update
                cmds.refresh()
                cmds.pause(seconds=0.2)
            
            # Refresh the UI to show all connections
            self.refresh_ui_list()
            
            # Success message
            success_message = f"Successfully created {len(retarget_pairs)} connections from preset.\n\n"
            success_message += "Please review the connections and click 'Bake Animation'\n"
            success_message += "when you're ready to bake the animation."
            
            cmds.confirmDialog(
                title="Connections Created", 
                message=success_message,
                button=["OK"],
                defaultButton="OK"
            )
            
            print("// Finished creating connections from preset")
            
        except Exception as e:
            print(f"// Error loading/applying preset: {str(e)}")
            import traceback
            traceback.print_exc()

    def create_connection_node(self):
        try:
            selected_joint = cmds.ls(selection=True)[0]
            selected_ctrl = cmds.ls(selection=True)[1]
        except:
            return cmds.warning("No selections!")

        if self.snap_checkbox.isChecked() == True:
            cmds.matchTransform(selected_ctrl, selected_joint, pos=True)
        else:
            pass
        
        if self.rot_checkbox.isChecked() == True and self.pos_checkbox.isChecked() == False:
            suffix = "_ROT"
    
        elif self.pos_checkbox.isChecked() == True and self.rot_checkbox.isChecked() == False:
            suffix = "_TRAN"
        
        else:
            suffix = "_TRAN_ROT"

        locator = self.create_ctrl_sphere(selected_joint+suffix)
        
        # Add message attr
        cmds.addAttr(locator, longName="ConnectNode", attributeType="message")
        cmds.addAttr(selected_ctrl, longName="ConnectedCtrl", attributeType="message")
        cmds.connectAttr(locator+".ConnectNode",selected_ctrl+".ConnectedCtrl")

        cmds.parent(locator, selected_joint)
        cmds.xform(locator, rotation=(0, 0, 0))
        cmds.xform(locator, translation=(0, 0, 0))
 
        # Select the type of constraint based on the ui checkboxes
        if self.rot_checkbox.isChecked() == True and self.pos_checkbox.isChecked() == True:
            cmds.parentConstraint(locator, selected_ctrl, maintainOffset=True)
    
        elif self.rot_checkbox.isChecked() == True and self.pos_checkbox.isChecked() == False:
            cmds.orientConstraint(locator, selected_ctrl, maintainOffset=True)
    
        elif self.pos_checkbox.isChecked() == True and self.rot_checkbox.isChecked() == False:
            cmds.pointConstraint(locator, selected_ctrl, maintainOffset=True)
        else:
            cmds.warning("Select translation and/or rotation!")
            cmds.delete(locator)
            cmds.deleteAttr(selected_ctrl, at="ConnectedCtrl")

        self.refresh_ui_list()
 
    def create_ik_connection_node(self):
        try:
            selected_joint = cmds.ls(selection=True)[0]
            selected_ctrl = cmds.ls(selection=True)[1]
        except:
            return cmds.warning("No selections!")

        self.rot_checkbox.setChecked(True)
        self.pos_checkbox.setChecked(True)

        if self.snap_checkbox.isChecked() == True:
            cmds.matchTransform(selected_ctrl, selected_joint, pos=True)
        else:
            pass
        
        tran_locator = self.create_ctrl_sphere(selected_joint+"_TRAN")

        cmds.parent(tran_locator, selected_joint)
        cmds.xform(tran_locator, rotation=(0, 0, 0))
        cmds.xform(tran_locator, translation=(0, 0, 0))

        rot_locator = self.create_ctrl_locator(selected_joint+"_ROT")

        # Add message attributes and connect them
        cmds.addAttr(tran_locator, longName="ConnectNode", attributeType="message")
        cmds.addAttr(rot_locator, longName="ConnectNode", attributeType="message")
        cmds.addAttr(selected_ctrl, longName="ConnectedCtrl", attributeType="message")
        cmds.connectAttr(tran_locator+".ConnectNode",selected_ctrl+".ConnectedCtrl")

        cmds.parent(rot_locator, tran_locator)
        cmds.xform(rot_locator, rotation=(0, 0, 0))
        cmds.xform(rot_locator, translation=(0, 0, 0))
    
        joint_parent = cmds.listRelatives(selected_joint, parent=True)[0]
        cmds.parent(tran_locator, joint_parent)
        cmds.makeIdentity(tran_locator, apply=True, translate=True)
    
        cmds.orientConstraint(selected_joint, tran_locator, maintainOffset=False)
        cmds.parentConstraint(rot_locator, selected_ctrl, maintainOffset=True)

        # Lock and hide attributes
        cmds.setAttr(rot_locator+".tx", lock=True, keyable=False)
        cmds.setAttr(rot_locator+".ty", lock=True, keyable=False)
        cmds.setAttr(rot_locator+".tz", lock=True, keyable=False)
        cmds.setAttr(tran_locator+".rx", lock=True, keyable=False)
        cmds.setAttr(tran_locator+".ry", lock=True, keyable=False)
        cmds.setAttr(tran_locator+".rz", lock=True, keyable=False)

        self.refresh_ui_list()

    def scale_ctrl_shape(self, controller, size):
        cmds.select(self.get_cvs(controller), replace=True)
        cmds.scale(size, size, size) 
        cmds.select(clear=True)

    def get_cvs(self, object):
        children = cmds.listRelatives(object, type="shape", children=True)
        ctrl_vertices = []
        for c in children:
            spans = int(cmds.getAttr(c+".spans")) + 1
            vertices = "{shape}.cv[0:{count}]".format(shape=c, count=spans)
            ctrl_vertices.append(vertices)
        return ctrl_vertices

    def create_ctrl_locator(self, ctrl_shape_name):
        curves = []
        curves.append(cmds.curve(degree=1, p=[(0, 0, 1), (0, 0, -1)], k=[0,1]))
        curves.append(cmds.curve(degree=1, p=[(1, 0, 0), (-1, 0, 0)], k=[0,1]))
        curves.append(cmds.curve(degree=1, p=[(0, 1, 0), (0, -1, 0)], k=[0,1]))

        locator = self.combine_shapes(curves, ctrl_shape_name)
        cmds.setAttr(locator+".overrideEnabled", 1)
        cmds.setAttr(locator+".overrideColor", list(self.maya_color_index.keys())[self.color_counter])
        return locator

    def create_ctrl_sphere(self, ctrl_shape_name):
        circles = []
        for n in range(0, 5):
            circles.append(cmds.circle(normal=(0,0,0), center=(0,0,0))[0])

        cmds.rotate(0, 45, 0, circles[0])
        cmds.rotate(0, -45, 0, circles[1])
        cmds.rotate(0, -90, 0, circles[2])
        cmds.rotate(90, 0, 0, circles[3])
        sphere = self.combine_shapes(circles, ctrl_shape_name)
        cmds.setAttr(sphere+".overrideEnabled", 1)
        cmds.setAttr(sphere+".overrideColor", list(self.maya_color_index.keys())[self.color_counter])
        self.scale_ctrl_shape(sphere, 0.5)
        return sphere

    def combine_shapes(self, shapes, ctrl_shape_name):
        shape_nodes = cmds.listRelatives(shapes, shapes=True)
        output_node = cmds.group(empty=True, name=ctrl_shape_name)
        cmds.makeIdentity(shapes, apply=True, translate=True, rotate=True, scale=True)
        cmds.parent(shape_nodes, output_node, shape=True, relative=True)
        cmds.delete(shape_nodes, constructionHistory=True)
        cmds.delete(shapes)
        return output_node

    def bake_animation_confirm(self):
        confirm = cmds.confirmDialog(title="Confirm", message="Baking the animation will delete all the connection nodes. Do you wish to proceed?", button=["Yes","No"], defaultButton="Yes", cancelButton="No")
        if confirm == "Yes":
            progress_dialog = QtWidgets.QProgressDialog("Baking animation", None, 0, -1, self)
            progress_dialog.setWindowFlags(progress_dialog.windowFlags() ^ QtCore.Qt.WindowCloseButtonHint)
            progress_dialog.setWindowFlags(progress_dialog.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
            progress_dialog.setWindowTitle("Progress...")
            progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
            progress_dialog.show()
            QtCore.QCoreApplication.processEvents()
            # Bake animation
            self.bake_animation()
            progress_dialog.close()
        if confirm == "No":
            pass
        self.refresh_ui_list()

    def help_dialog(self):        
        confirm = cmds.confirmDialog(
                        title="How to use",
                        message="To create a connection simply select the driver and then the driven and click 'Create connection'. For IK hands and IK feet controllers you can use 'Create IK Connection' for more complex retargeting. \n \nAs an example: if you want to transfer animation from a skeleton to a rig, first select the animated joint and then select the controller before you create a connection.",
                        button=["How to use the retargeting tool (Youtube)", "How to use the batch exporter (Youtube)", "Cancel"],
                        defaultButton="Cancel",
                        cancelButton="Cancel",
                        dismissString="Cancel")

        if confirm == "How to use the retargeting tool (Youtube)":  
            webbrowser.open_new("https://youtu.be/x2-agPVfinc")
        elif confirm == "How to use the batch exporter (Youtube)":
            webbrowser.open_new("https://youtu.be/KOURUtN36ko")

    def open_batch_window(self):
        try:
            self.settings_window.close()
            self.settings_window.deleteLater()
        except:
            pass
        self.settings_window = BatchExport()
        
    def show_preset_selector(self, weapon_id=None, master_path=None, namespace=None):
        """
        Show a dialog to select a retargeting preset
        
        Args:
            weapon_id (str, optional): Weapon ID to search for presets
            master_path (str, optional): Path to STALKER2_ModdingTools folder
            namespace (str, optional): Namespace prefix for imported joints
        """
        # Store context for future use
        if weapon_id:
            self.current_weapon_id = weapon_id
        if master_path:
            self.current_master_path = master_path
        if namespace:
            self.current_namespace = namespace
        
        # Find available presets
        available_presets, default_preset = find_retarget_presets(
            self.current_weapon_id, 
            self.current_master_path,
            self.current_namespace
        )
        
        if not available_presets:
            cmds.confirmDialog(
                title="No Presets Found",
                message="No retargeting presets were found. Please create one manually.",
                button=["OK"],
                defaultButton="OK"
            )
            return
            
        # Create dialog for preset selection
        preset_dialog = QtWidgets.QDialog(self)
        preset_dialog.setWindowTitle("Select Retargeting Preset")
        preset_dialog.setMinimumWidth(600)
        preset_dialog.setMinimumHeight(400)
        
        # Create layout
        layout = QtWidgets.QVBoxLayout(preset_dialog)
        
        # Add explanation label
        info_label = QtWidgets.QLabel("Select a preset for automatic connection creation:")
        layout.addWidget(info_label)
        
        # Add dropdown
        preset_combo = QtWidgets.QComboBox()
        for name, path in available_presets:
            preset_combo.addItem(name, path)
        
        # Set default selection
        if default_preset:
            for i in range(preset_combo.count()):
                if preset_combo.itemData(i) == default_preset:
                    preset_combo.setCurrentIndex(i)
                    break
        
        layout.addWidget(preset_combo)
        
        # Add info text area
        info_text = QtWidgets.QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMinimumHeight(200)
        layout.addWidget(info_text)
        
        # Function to update info text when selection changes
        def update_preset_info(index):
            selected_path = preset_combo.itemData(index)
            if not selected_path:
                info_text.setText("No preset selected. Manual connection creation required.")
                return
                
            try:
                # Show file path
                info = f"File: {selected_path}\n\n"
                
                # Load and display preset content
                with open(selected_path, 'r') as f:
                    preset_data = json.load(f)
                    
                if preset_data:
                    # Count the number of joint configurations (excluding post_bake_operations)
                    joint_count = sum(1 for key in preset_data if key != "post_bake_operations")
                    info += f"Contains {joint_count} joint configuration(s):\n\n"
                    
                    # Display joint settings
                    for joint_name, settings in preset_data.items():
                        # Skip the post_bake_operations key as it's not a joint
                        if joint_name == "post_bake_operations":
                            continue
                            
                        info += f"* {joint_name}:\n"
                        
                        # Handle both dictionary and non-dictionary settings
                        if isinstance(settings, dict):
                            align_pos = settings.get("align_position", True)
                            info += f"  - Align position: {'Yes' if align_pos else 'No'}\n"
                            
                            if "rotate" in settings:
                                rotation = settings["rotate"]
                                info += f"  - Post rotation: {rotation}\n"
                        else:
                            info += f"  - {settings}\n"
                    
                    # Display post-bake operations if present
                    if "post_bake_operations" in preset_data:
                        ops = preset_data["post_bake_operations"]
                        info += f"\nPost-Bake Operations: {len(ops)}\n"
                        for i, op in enumerate(ops):
                            op_type = op.get("type", "unknown")
                            info += f"* Operation {i+1}: {op_type}\n"
                            
                            if op_type == "rotate":
                                obj = op.get("object", "unknown")
                                vals = op.get("values", [0,0,0])
                                rel = op.get("relative", False)
                                info += f"  - Rotate {obj} by {vals} (relative: {rel})\n"
                            elif op_type == "translate":
                                obj = op.get("object", "unknown")
                                vals = op.get("values", [0,0,0])
                                info += f"  - Translate {obj} to {vals}\n"
                            elif op_type == "custom":
                                cmd = op.get("command", "")
                                info += f"  - Custom command: {cmd[:30]}...\n" if len(cmd) > 30 else f"  - Custom command: {cmd}\n"
                else:
                    info += "Preset is empty."
            except Exception as e:
                info = f"Error loading preset: {str(e)}"
                
            info_text.setText(info)
            
        # Connect dropdown change to update info
        preset_combo.currentIndexChanged.connect(update_preset_info)
        
        # Initialize with current selection
        update_preset_info(preset_combo.currentIndex())
        
        # Add edit button that opens the preset file for editing
        edit_button = QtWidgets.QPushButton("Edit Preset")
        
        def edit_preset():
            selected_path = preset_combo.itemData(preset_combo.currentIndex())
            if selected_path and os.path.exists(selected_path):
                try:
                    # Open the file in a text editor or show it in explorer
                    if os.name == 'nt':  # Windows
                        os.startfile(selected_path)
                    else:
                        import subprocess
                        subprocess.call(['open', selected_path])
                except Exception as e:
                    print(f"// Error opening preset file: {str(e)}")
        
        edit_button.clicked.connect(edit_preset)
        
        # Add create preset button
        create_preset_button = QtWidgets.QPushButton("Create New Preset")
        
        def create_new_preset():
            if not self.current_weapon_id:
                cmds.confirmDialog(
                    title="Missing Weapon ID",
                    message="Please specify a weapon ID to create a preset.",
                    button=["OK"],
                    defaultButton="OK"
                )
                return
                
            # Ask for preset name
            result = cmds.promptDialog(
                title="Create Preset",
                message="Enter preset name:",
                button=["OK", "Cancel"],
                defaultButton="OK",
                cancelButton="Cancel",
                dismissString="Cancel"
            )
            
            if result == "OK":
                preset_name = cmds.promptDialog(query=True, text=True)
                if not preset_name:
                    cmds.confirmDialog(
                        title="Invalid Name",
                        message="Please enter a valid name for the preset.",
                        button=["OK"],
                        defaultButton="OK"
                    )
                    return
                    
                # Determine preset location
                preset_path = None
                
                # If weapon_id is specified, create in weapon directory
                if self.current_weapon_id and self.current_master_path:
                    # Find weapon path
                    weapons_dir = os.path.join(self.current_master_path, "Source", "Weapons")
                    weapon_path = None
                    
                    if os.path.exists(weapons_dir):
                        # Look through all category folders
                        for category in os.listdir(weapons_dir):
                            category_dir = os.path.join(weapons_dir, category)
                            if os.path.isdir(category_dir):
                                # Check if weapon exists in this category
                                potential_weapon_dir = os.path.join(category_dir, self.current_weapon_id)
                                if os.path.isdir(potential_weapon_dir):
                                    weapon_path = potential_weapon_dir
                                    break
                    
                    if weapon_path:
                        preset_path = os.path.join(weapon_path, f"{preset_name}_retarget.json")
                
                # If no weapon path found, save in global presets
                if not preset_path:
                    # Try Maya scripts directory
                    scripts_dir = cmds.internalVar(userScriptDir=True)
                    presets_dir = os.path.join(scripts_dir, "retarget_presets")
                    
                    # Create directory if it doesn't exist
                    if not os.path.exists(presets_dir):
                        try:
                            os.makedirs(presets_dir)
                        except:
                            pass
                    
                    preset_path = os.path.join(presets_dir, f"{preset_name}_retarget.json")
                
                # Create preset with default settings
                try:
                    default_settings = get_default_retarget_settings(self.current_weapon_id)
                    
                    with open(preset_path, 'w') as f:
                        json.dump(default_settings, f, indent=4)
                    
                    # Refresh preset list
                    cmds.confirmDialog(
                        title="Preset Created",
                        message=f"Preset created successfully at:\n{preset_path}\n\nPlease select it from the dropdown.",
                        button=["OK"],
                        defaultButton="OK"
                    )
                    
                    # Refresh the preset list
                    available_presets, _ = find_retarget_presets(
                        self.current_weapon_id, 
                        self.current_master_path,
                        self.current_namespace
                    )
                    
                    preset_combo.clear()
                    for name, path in available_presets:
                        preset_combo.addItem(name, path)
                    
                    # Select the new preset
                    for i in range(preset_combo.count()):
                        if preset_combo.itemData(i) == preset_path:
                            preset_combo.setCurrentIndex(i)
                            break
                    
                except Exception as e:
                    cmds.confirmDialog(
                        title="Error",
                        message=f"Error creating preset: {str(e)}",
                        button=["OK"],
                        defaultButton="OK"
                    )
        
        create_preset_button.clicked.connect(create_new_preset)
        
        # Add buttons
        button_layout = QtWidgets.QHBoxLayout()
        ok_button = QtWidgets.QPushButton("Load Selected")
        cancel_button = QtWidgets.QPushButton("Cancel")
        
        button_layout.addWidget(create_preset_button)
        button_layout.addWidget(edit_button)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        # Connect signals
        ok_button.clicked.connect(preset_dialog.accept)
        cancel_button.clicked.connect(preset_dialog.reject)
        
        # Show dialog
        result = preset_dialog.exec_()
        
        if result == QtWidgets.QDialog.Accepted:
            selected_path = preset_combo.itemData(preset_combo.currentIndex())
            
            if selected_path:
                print(f"// Loading selected preset: {selected_path}")
                self.load_and_apply_preset(selected_path, self.current_namespace)

    @classmethod
    def execute_post_bake_operations(cls, preset_data):
        """
        Execute post-bake operations defined in the preset
        
        Args:
            preset_data (dict): The loaded preset data
        """
        if not preset_data or 'post_bake_operations' not in preset_data:
            return
            
        operations = preset_data.get('post_bake_operations', [])
        if not operations:
            return
            
        print("// Executing post-bake operations:")
        
        for op in operations:
            op_type = op.get('type')
            
            if op_type == 'rotate':
                # Format: {'type': 'rotate', 'object': 'S2_Controls', 'values': [0, -90, 0], 'relative': True}
                obj_name = op.get('object')
                values = op.get('values', [0, 0, 0])
                relative = op.get('relative', False)
                
                # Check if the object exists, considering potential namespace
                target_obj = None
                
                # First try direct existence
                if cmds.objExists(obj_name):
                    target_obj = obj_name
                    print(f"// Found object directly: {target_obj}")
                else:
                    # Try with namespace pattern
                    namespace_pattern = f"*:{obj_name}"
                    potential_targets = cmds.ls(namespace_pattern)
                    if potential_targets:
                        target_obj = potential_targets[0]
                        print(f"// Found object with namespace: {target_obj}")
                    else:
                        # Try more flexible search for nested namespaces or partial name match
                        all_objects = cmds.ls(type="transform")
                        for obj in all_objects:
                            if obj.endswith(f":{obj_name}") or obj.endswith(obj_name):
                                target_obj = obj
                                print(f"// Found object with nested namespace: {target_obj}")
                                break
                
                if target_obj:
                    print(f"// Rotating {target_obj}: {values} (relative: {relative})")
                    cmds.rotate(values[0], values[1], values[2], target_obj, relative=relative)
                    print(f"// Successfully rotated {target_obj}")
                else:
                    print(f"// Warning: Could not find object {obj_name} for rotation operation")
                    
            elif op_type == 'translate':
                # Format: {'type': 'translate', 'object': 'S2_Controls', 'values': [0, 0, 0], 'relative': True}
                obj_name = op.get('object')
                values = op.get('values', [0, 0, 0])
                relative = op.get('relative', False)
                
                # Check if the object exists, considering potential namespace
                target_obj = None
                
                # First try direct existence
                if cmds.objExists(obj_name):
                    target_obj = obj_name
                    print(f"// Found object directly: {target_obj}")
                else:
                    # Try with namespace pattern
                    namespace_pattern = f"*:{obj_name}"
                    potential_targets = cmds.ls(namespace_pattern)
                    if potential_targets:
                        target_obj = potential_targets[0]
                        print(f"// Found object with namespace: {target_obj}")
                    else:
                        # Try more flexible search for nested namespaces or partial name match
                        all_objects = cmds.ls(type="transform")
                        for obj in all_objects:
                            if obj.endswith(f":{obj_name}") or obj.endswith(obj_name):
                                target_obj = obj
                                print(f"// Found object with nested namespace: {target_obj}")
                                break
                
                if target_obj:
                    print(f"// Translating {target_obj}: {values} (relative: {relative})")
                    cmds.move(values[0], values[1], values[2], target_obj, relative=relative)
                    print(f"// Successfully translated {target_obj}")
                else:
                    print(f"// Warning: Could not find object {obj_name} for translation operation")
                    
            elif op_type == 'scale':
                # Format: {'type': 'scale', 'object': 'S2_Controls', 'values': [1, 1, 1], 'relative': False}
                obj_name = op.get('object')
                values = op.get('values', [1, 1, 1])
                relative = op.get('relative', False)
                
                # Check if the object exists, considering potential namespace
                target_obj = None
                
                # First try direct existence
                if cmds.objExists(obj_name):
                    target_obj = obj_name
                    print(f"// Found object directly: {target_obj}")
                else:
                    # Try with namespace pattern
                    namespace_pattern = f"*:{obj_name}"
                    potential_targets = cmds.ls(namespace_pattern)
                    if potential_targets:
                        target_obj = potential_targets[0]
                        print(f"// Found object with namespace: {target_obj}")
                    else:
                        # Try more flexible search for nested namespaces or partial name match
                        all_objects = cmds.ls(type="transform")
                        for obj in all_objects:
                            if obj.endswith(f":{obj_name}") or obj.endswith(obj_name):
                                target_obj = obj
                                print(f"// Found object with nested namespace: {target_obj}")
                                break
                
                if target_obj:
                    print(f"// Scaling {target_obj}: {values} (relative: {relative})")
                    cmds.scale(values[0], values[1], values[2], target_obj, relative=relative)
                    print(f"// Successfully scaled {target_obj}")
                else:
                    print(f"// Warning: Could not find object {obj_name} for scale operation")
                    
            elif op_type == 'custom':
                # Format: {'type': 'custom', 'command': 'cmds.select("S2_Controls")'}
                command = op.get('command', '')
                if command:
                    print(f"// Executing custom command: {command}")
                    try:
                        exec(command)
                        print(f"// Successfully executed custom command")
                    except Exception as e:
                        print(f"// Error executing custom command: {str(e)}")
            
            else:
                print(f"// Warning: Unknown operation type: {op_type}")
                
        print("// Post-bake operations completed")

    @classmethod
    def bake_animation(cls):
        if len(cls.get_connected_ctrls()) == 0:
            cmds.warning("No connections found in scene!")
            return
            
        if len(cls.get_connected_ctrls()) != 0:
            time_min = cmds.playbackOptions(query=True, min=True)
            time_max = cmds.playbackOptions(query=True, max=True)

            # Bake the animation
            cmds.refresh(suspend=True)
            cmds.bakeResults(cls.get_connected_ctrls(), t=(time_min, time_max), sb=1, at=["rx","ry","rz","tx","ty","tz"], hi="none")
            cmds.refresh(suspend=False)

            # Delete the connect nodes
            for node in cls.get_connect_nodes():
                try:
                    cmds.delete(node)
                except:
                    pass
            
            # Remove the message attribute from the controllers
            for ctrl in cls.get_connected_ctrls():
                try:
                    cmds.deleteAttr(ctrl, attribute="ConnectedCtrl")
                except:
                    pass
                    
            # Execute post-bake operations if available
            # Find the active preset data stored in the class
            if hasattr(RetargetingTool, 'active_preset_data') and RetargetingTool.active_preset_data:
                cls.execute_post_bake_operations(RetargetingTool.active_preset_data)

    @classmethod
    def get_connect_nodes(cls):
        connect_nodes_in_scene = []
        for i in cmds.ls():
            if cmds.attributeQuery("ConnectNode", node=i, exists=True) == True:
                connect_nodes_in_scene.append(i)
            else:
                pass
        return connect_nodes_in_scene

    @classmethod
    def get_connected_ctrls(cls):
        connected_ctrls_in_scene = []
        for i in cmds.ls():
            if cmds.attributeQuery("ConnectedCtrl", node=i, exists=True) == True:
                connected_ctrls_in_scene.append(i)
            else:
                pass
        return connected_ctrls_in_scene


class ListItemWidget(QtWidgets.QWidget):
    '''
    UI list item class.
    When a new List Item is created it gets added to the connection_list_widget in the RetargetingTool class.
    '''
    def __init__(self, connection_node, parent_instance):
        super(ListItemWidget, self).__init__()
        self.connection_node = connection_node
        self.main = parent_instance
 
        self.setFixedHeight(26)
        self.create_ui_widgets()
        self.create_ui_layout()
        self.create_ui_connections()

        # If there is already connection nodes in the scene update the color counter
        try:
            current_override = cmds.getAttr(self.connection_node+".overrideColor")
            self.main.color_counter = self.main.maya_color_index.keys().index(current_override)
        except:
            pass
 
    def create_ui_widgets(self):
        self.color_button = QtWidgets.QPushButton()
        self.color_button.setFixedSize(20, 20)
        self.color_button.setStyleSheet("background-color:" + self.get_current_color())
 
        self.sel_button = QtWidgets.QPushButton()
        self.sel_button.setStyleSheet("background-color: #707070")
        self.sel_button.setText("Select")
        self.sel_button.setFixedWidth(80)
 
        self.del_button = QtWidgets.QPushButton()
        self.del_button.setStyleSheet("background-color: #707070")
        self.del_button.setText("Delete")
        self.del_button.setFixedWidth(80)

        self.transform_name_label = QtWidgets.QLabel(self.connection_node)
        self.transform_name_label.setAlignment(QtCore.Qt.AlignCenter)

        self.transform_name_label.setStyleSheet("color: darkgray")
        for selected in cmds.ls(selection=True):
            if selected == self.connection_node:
                self.transform_name_label.setStyleSheet("color: white")
 
    def create_ui_layout(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 20, 0)
        main_layout.addWidget(self.color_button)
        main_layout.addWidget(self.transform_name_label)
        main_layout.addWidget(self.sel_button)
        main_layout.addWidget(self.del_button)
 
    def create_ui_connections(self):
        self.sel_button.clicked.connect(self.select_connection_node)
        self.del_button.clicked.connect(self.delete_connection_node)
        self.color_button.clicked.connect(self.set_color)
 
    def select_connection_node(self):
        cmds.select(self.connection_node) 
        for widget in self.main.connection_ui_widgets:
            widget.transform_name_label.setStyleSheet("color: darkgray")
        self.transform_name_label.setStyleSheet("color: white")

    def delete_connection_node(self):
        try:
            for attr in cmds.listConnections(self.connection_node, destination=True):
                if cmds.attributeQuery("ConnectedCtrl", node=attr, exists=True):
                    cmds.deleteAttr(attr, at="ConnectedCtrl")
        except:
            pass

        cmds.delete(self.connection_node)
        self.main.refresh_ui_list()
 
    def set_color(self):
        # Set the color on the connection node and button
        connection_nodes = self.main.cached_connect_nodes
        color = list(self.main.maya_color_index.keys())

        if self.main.color_counter < 3:
            self.main.color_counter += 1
        else:
            self.main.color_counter = 0

        for node in connection_nodes:
            cmds.setAttr(node+".overrideEnabled", 1)
            cmds.setAttr(node+".overrideColor", color[self.main.color_counter])

        for widget in self.main.connection_ui_widgets:
            widget.color_button.setStyleSheet("background-color:"+self.get_current_color())
 
    def get_current_color(self):
        current_color_index = cmds.getAttr(self.connection_node+".overrideColor")
        color_name = self.main.maya_color_index.get(current_color_index, "grey")
        return color_name

class BatchExport(QtWidgets.QDialog):
    '''
    Batch exporter class
    ''' 
    WINDOW_TITLE = "Batch Exporter"

    def __init__(self):
        super(BatchExport, self).__init__(maya_main_window())
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.resize(400, 250)
        self.animation_clip_paths = []
        self.output_folder = ""
        
        if cmds.about(macOS=True):
            self.setWindowFlags(QtCore.Qt.Tool)

        self.create_ui()
        self.create_connections()

    def create_ui(self):
        self.file_list_widget = QtWidgets.QListWidget()
        self.remove_selected_button = QtWidgets.QPushButton("Remove Selected")
        self.remove_selected_button.setFixedHeight(24)
        self.load_anim_button = QtWidgets.QPushButton("Load Animations")
        self.load_anim_button.setFixedHeight(24)
        self.export_button = QtWidgets.QPushButton("Batch Export Animations")
        self.export_button.setStyleSheet("background-color: lightgreen; color: black")
        self.connection_file_line = QtWidgets.QLineEdit()
        self.connection_file_line.setToolTip("Enter the file path to the connection rig file. A file which contains a rig with connections.")
        self.connection_filepath_button = QtWidgets.QPushButton()
        self.connection_filepath_button.setIcon(QtGui.QIcon(":fileOpen.png"))
        self.connection_filepath_button.setFixedSize(24, 24)

        self.export_selected_label = QtWidgets.QLabel("Export Selected (Optional):")
        self.export_selected_line = QtWidgets.QLineEdit()
        self.export_selected_line.setToolTip("Enter the name(s) of the nodes that should be exported. Leave blank to export all.")
        self.export_selected_button = QtWidgets.QPushButton()
        self.export_selected_button.setIcon(QtGui.QIcon(":addClip.png"))
        self.export_selected_button.setFixedSize(24, 24)

        self.output_filepath_button = QtWidgets.QPushButton()
        self.output_filepath_button.setIcon(QtGui.QIcon(":fileOpen.png"))

        self.file_type_combo = QtWidgets.QComboBox()
        self.file_type_combo.addItems([".fbx", ".ma"])

        horizontal_layout_1 = QtWidgets.QHBoxLayout()
        horizontal_layout_1.addWidget(QtWidgets.QLabel("Connection Rig File:"))
        horizontal_layout_1.addWidget(self.connection_file_line)
        horizontal_layout_1.addWidget(self.connection_filepath_button)

        horizontal_layout_2 = QtWidgets.QHBoxLayout()
        horizontal_layout_2.addWidget(self.load_anim_button)
        horizontal_layout_2.addWidget(self.remove_selected_button)

        horizontal_layout_3 = QtWidgets.QHBoxLayout()
        horizontal_layout_3.addWidget(QtWidgets.QLabel("Output File Type:"))
        horizontal_layout_3.addWidget(self.file_type_combo)
        horizontal_layout_3.addWidget(self.export_button)

        horizontal_layout_4 = QtWidgets.QHBoxLayout()
        horizontal_layout_4.addWidget(self.export_selected_label)
        horizontal_layout_4.addWidget(self.export_selected_line)
        horizontal_layout_4.addWidget(self.export_selected_button)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self.file_list_widget)
        main_layout.addLayout(horizontal_layout_2)
        main_layout.addLayout(horizontal_layout_1)
        main_layout.addLayout(horizontal_layout_4)
        main_layout.addLayout(horizontal_layout_3)

    def create_connections(self):
        self.connection_filepath_button.clicked.connect(self.connection_filepath_dialog)
        self.load_anim_button.clicked.connect(self.animation_filepath_dialog)
        self.export_button.clicked.connect(self.batch_action)
        self.export_selected_button.clicked.connect(self.add_selected_action)
        self.remove_selected_button.clicked.connect(self.remove_selected_item)

    def connection_filepath_dialog(self):
        file_path = QtWidgets.QFileDialog.getOpenFileName(self, "Select Connection Rig File", "", "Maya ACSII (*.ma);;All files (*.*)")
        if file_path[0]:
            self.connection_file_line.setText(file_path[0])

    def output_filepath_dialog(self):
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select export folder path", "")
        if folder_path:
            self.output_folder = folder_path
            return True
        else:
            return False

    def animation_filepath_dialog(self):
        file_paths = QtWidgets.QFileDialog.getOpenFileNames(self, "Select Animation Clips", "", "FBX (*.fbx);;All files (*.*)")
        file_path_list = file_paths[0]

        if file_path_list[0]:
            for i in file_path_list:
                self.file_list_widget.addItem(i)
        
        for i in range(0, self.file_list_widget.count()):
            self.file_list_widget.item(i).setTextColor(QtGui.QColor("white"))

    def add_selected_action(self):
        selection = cmds.ls(selection=True)
        if len(selection) > 1:
            text_string = "["
            for i in selection:
                text_string += '"{}", '.format(i)
            text_string = text_string[:-2]
            text_string += "]"
        elif selection[0]:
            text_string = "{}".format(selection[0])
        else:
            pass

        self.export_selected_line.setText(text_string)

    def remove_selected_item(self):
        try:
            selected_items = self.file_list_widget.selectedItems()
            for item in selected_items:
                self.file_list_widget.takeItem(self.file_list_widget.row(item))
        except:
            pass

    def batch_action(self):
        if self.connection_file_line.text() == "":
            cmds.warning("Connection file textfield is empty. Add a connection rig file to be able to export. This file should contain the rig and connections to a skeleton.")
        elif self.file_list_widget.count() == 0:
            cmds.warning("Animation clip list is empty. Add animation clips to the list to be able to export!")
        else:
            confirm_dialog = self.output_filepath_dialog()
            if confirm_dialog == True:
                self.bake_export()         
            else:
                pass

    def bake_export(self):
        self.animation_clip_paths = []
        for i in range(self.file_list_widget.count()):
            self.animation_clip_paths.append(self.file_list_widget.item(i).text())

        number_of_operations = len(self.animation_clip_paths) * 3
        current_operation = 0
        progress_dialog = QtWidgets.QProgressDialog("Preparing", "Cancel", 0, number_of_operations, self)
        progress_dialog.setWindowFlags(progress_dialog.windowFlags() ^ QtCore.Qt.WindowCloseButtonHint)
        progress_dialog.setWindowFlags(progress_dialog.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        progress_dialog.setValue(0)
        progress_dialog.setWindowTitle("Progress...")
        progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
        progress_dialog.show()
        QtCore.QCoreApplication.processEvents()
        export_result = []

        for i, path in enumerate(self.animation_clip_paths):
            # Import connection file and animation clip
            progress_dialog.setLabelText("Baking and exporting {} of {}".format(i + 1, len(self.animation_clip_paths)))
            self.file_list_widget.item(i).setTextColor(QtGui.QColor("yellow"))
            cmds.file(new=True, force=True)
            cmds.file(self.connection_file_line.text(), open=True)
            maya.mel.eval('FBXImportMode -v "exmerge";')
            maya.mel.eval('FBXImport -file "{}";'.format(path))
            current_operation += 1
            progress_dialog.setValue(current_operation) 

            # Bake animation
            RetargetingTool.bake_animation()
            current_operation += 1
            progress_dialog.setValue(current_operation) 

            # Export animation            
            output_path = self.output_folder + "/" + os.path.splitext(os.path.basename(path))[0]
            if self.file_type_combo.currentText() == ".fbx":
                output_path += ".fbx"
                cmds.file(rename=output_path)
                if self.export_selected_line.text() != "":
                    cmds.select(self.export_selected_line.text(), replace=True)
                    maya.mel.eval('FBXExport -f "{}" -s'.format(output_path))
                else:
                    maya.mel.eval('FBXExport -f "{}"'.format(output_path))
            elif self.file_type_combo.currentText() == ".ma":
                output_path += ".ma"
                cmds.file(rename=output_path)
                if self.export_selected_line.text() != "":
                    cmds.select(self.export_selected_line.text(), replace=True)
                    cmds.file(exportSelected=True, type="mayaAscii")
                else:
                    cmds.file(exportAll=True, type="mayaAscii")
            
            current_operation += 1
            progress_dialog.setValue(current_operation)        

            if os.path.exists(output_path):
                self.file_list_widget.item(i).setTextColor(QtGui.QColor("lime"))
                export_result.append("Sucessfully exported: "+output_path)

            else:
                self.file_list_widget.item(i).setTextColor(QtGui.QColor("red"))
                export_result.append("Failed exporting: "+output_path)
        
        print("------")
        for i in export_result:
            print(i)
        print("------")

        progress_dialog.setValue(number_of_operations)
        progress_dialog.close()


def find_retarget_presets(weapon_id=None, master_path=None, namespace=None):
    """
    Search for available retargeting presets in various locations
    
    Args:
        weapon_id (str): The weapon ID to search for specific presets
        master_path (str): The main project path (STALKER2_ModdingTools)
        namespace (str): Namespace prefix for imported joints
        
    Returns:
        tuple: (available_presets, default_preset)
            available_presets is a list of tuples (display_name, file_path)
            default_preset is the recommended preset path or None
    """
    available_presets = []
    default_preset = None
    searched_paths = []
    
    print("// Searching for retargeting presets...")
    
    try:
        # Get Maya scripts directory
        scripts_dir = cmds.internalVar(userScriptDir=True)
        searched_paths.append(scripts_dir)
        print(f"// Searching in Maya scripts directory: {scripts_dir}")
        
        # 1. Check Maya scripts/retarget_presets directory
        maya_presets_dir = os.path.join(scripts_dir, "retarget_presets")
        searched_paths.append(maya_presets_dir)
        
        if os.path.exists(maya_presets_dir):
            print(f"// Searching in Maya presets directory: {maya_presets_dir}")
            maya_presets = [os.path.join(maya_presets_dir, f) for f in os.listdir(maya_presets_dir) 
                           if f.endswith(".json")]
            for p in maya_presets:
                preset_name = os.path.basename(p).replace(".json", "").replace("_retarget", "")
                available_presets.append((f"Maya Scripts: {preset_name}", p))
                print(f"//   Found Maya preset: {p}")
        
        # 2. If weapon_id is provided, search for weapon-specific preset
        if weapon_id:
            # First find the weapon path
            weapon_path = None
            weapon_category = None
            
            # If master_path is provided, we can find weapon directories
            if master_path and os.path.exists(master_path):
                weapons_dir = os.path.join(master_path, "Source", "Weapons")
                searched_paths.append(weapons_dir)
                print(f"// Searching in weapons directory: {weapons_dir}")
                
                if os.path.exists(weapons_dir):
                    # Look through all category folders
                    for category in os.listdir(weapons_dir):
                        category_dir = os.path.join(weapons_dir, category)
                        if os.path.isdir(category_dir):
                            # Check if weapon exists in this category
                            potential_weapon_dir = os.path.join(category_dir, weapon_id)
                            if os.path.isdir(potential_weapon_dir):
                                weapon_path = potential_weapon_dir
                                weapon_category = category
                                break
            
            # If weapon path found, check for weapon-specific preset
            if weapon_path and os.path.isdir(weapon_path):
                searched_paths.append(weapon_path)
                print(f"// Searching in weapon directory: {weapon_path}")
                
                weapon_preset = os.path.join(weapon_path, f"{weapon_id}_retarget.json")
                if os.path.exists(weapon_preset):
                    available_presets.append((f"Weapon: {weapon_id}", weapon_preset))
                    default_preset = weapon_preset
                    print(f"//   Found weapon-specific preset: {weapon_preset}")
                
                # Also look in the parent directory (weapon category)
                if weapon_category:
                    parent_path = os.path.dirname(weapon_path)
                    if os.path.isdir(parent_path):
                        searched_paths.append(parent_path)
                        print(f"// Searching in category directory: {parent_path}")
                        
                        parent_presets = [os.path.join(parent_path, f) for f in os.listdir(parent_path) 
                                        if f.endswith("_retarget.json") and not f.startswith(weapon_id)]
                        for p in parent_presets:
                            preset_name = os.path.basename(p).replace("_retarget.json", "")
                            available_presets.append((f"Category: {preset_name}", p))
                            print(f"//   Found category preset: {p}")
        
        # 3. If master_path is provided, check global presets directory
        if master_path and os.path.exists(master_path):
            scripts_dir = os.path.join(master_path, "Scripts")
            presets_dir = os.path.join(scripts_dir, "retarget_presets")
            
            # Create presets directory if it doesn't exist
            if not os.path.exists(presets_dir):
                try:
                    os.makedirs(presets_dir)
                    print(f"// Created presets directory: {presets_dir}")
                except:
                    pass
            
            # Look for global presets
            if os.path.exists(presets_dir):
                searched_paths.append(presets_dir)
                print(f"// Searching in global presets directory: {presets_dir}")
                
                global_presets = [os.path.join(presets_dir, f) for f in os.listdir(presets_dir) 
                                if f.endswith(".json")]
                for p in global_presets:
                    preset_name = os.path.basename(p).replace(".json", "").replace("_retarget", "")
                    available_presets.append((f"Global: {preset_name}", p))
                    print(f"//   Found global preset: {p}")
        
        # 4. Check if we need to create a default preset
        if not available_presets and weapon_id and weapon_path and os.path.isdir(weapon_path):
            try:
                default_preset = os.path.join(weapon_path, f"{weapon_id}_retarget.json")
                default_settings = get_default_retarget_settings(weapon_id)
                
                with open(default_preset, 'w') as f:
                    json.dump(default_settings, f, indent=4)
                
                available_presets.insert(0, (f"Default: {weapon_id}", default_preset))
                print(f"// Created default preset: {default_preset}")
            except Exception as e:
                print(f"// Error creating default preset: {str(e)}")
        
        # Summary of search
        print(f"// Searched {len(searched_paths)} paths for presets")
        print(f"// Found {len(available_presets)} presets")
        
        # Always add "No Preset" option
        available_presets.append(("No Preset", None))
        
    except Exception as e:
        print(f"// Error finding presets: {str(e)}")
    
    return available_presets, default_preset

def get_default_retarget_settings(weapon_id):
    """
    Get default retargeting settings for a specific weapon
    
    Args:
        weapon_id (str): The weapon ID
    
    Returns:
        dict: Default retargeting settings
    """
    # Default settings
    default_settings = {
        "jnt_magazine1": {
            "align_position": True,
            "rotate": [0, 0, -90]
        },
        "jnt_shutter": {
            "align_position": False
        }
    }
    
    return default_settings

def start(*args, **kwargs):
    """
    Start the Animation Retargeting Tool, optionally with a JSON preset
    
    Handles both positional and keyword arguments for compatibility:
    
    Positional args (in order):
    - preset_path: Path to a JSON preset file
    - namespace: Namespace prefix for imported joints
    - master_path: Path to the STALKER2_ModdingTools folder
    - weapon_id: The weapon ID
    
    Keyword args:
    - json_preset_path: Path to a JSON preset file
    - preset_path: Alternative name for json_preset_path
    - namespace: Namespace prefix for imported joints
    - master_path: Path to the STALKER2_ModdingTools folder
    - weapon_id: The weapon ID
    """
    # Handle positional args
    preset_path = None
    namespace = None
    master_path = None
    weapon_id = None
    
    # Process positional arguments
    if len(args) > 0:
        preset_path = args[0]
    if len(args) > 1:
        namespace = args[1]
    if len(args) > 2:
        master_path = args[2]
    if len(args) > 3:
        weapon_id = args[3]
    
    # Process keyword arguments (override positional if provided)
    preset_path = kwargs.get('json_preset_path', kwargs.get('preset_path', preset_path))
    namespace = kwargs.get('namespace', namespace)
    master_path = kwargs.get('master_path', master_path)
    weapon_id = kwargs.get('weapon_id', weapon_id)
    
    print(f"// Starting Animation Retargeting Tool with: preset={preset_path}, namespace={namespace}, weapon_id={weapon_id}")
    
    global retarget_tool_ui
    try:
        retarget_tool_ui.close()
        retarget_tool_ui.deleteLater()
    except:
        pass
    
    retarget_tool_ui = RetargetingTool()
    retarget_tool_ui.show()
    
    # If a JSON preset was provided, load it and create connections automatically
    if preset_path and os.path.exists(preset_path):
        print(f"// Loading retargeting preset from: {preset_path}")
        retarget_tool_ui.load_and_apply_preset(preset_path, namespace)
    elif weapon_id:
        # If weapon_id was provided but no preset, show preset selector
        print(f"// Showing preset selector for weapon: {weapon_id}")
        retarget_tool_ui.show_preset_selector(weapon_id, master_path, namespace)

if __name__ == "__main__":
    start()