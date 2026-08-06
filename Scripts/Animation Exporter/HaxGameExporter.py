from __future__ import print_function
import maya.cmds as cmds
import maya.mel as mel
import json
import traceback
import sys
import os
import time
import datetime
import re
import random

# Logging setup
log_file = None

def setup_logging():
    """Set up logging to external file in Maya project directory."""
    global log_file
    try:
        project_dir = cmds.workspace(query=True, rootDirectory=True)
        if not project_dir:
            project_dir = cmds.internalVar(userWorkspaceDir=True)
        log_path = os.path.join(project_dir, "HaxExporterOutputLog.txt")
        log_file = open(log_path, 'w')
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write("===== Hax Game Exporter Log =====\n")
        log_file.write("Started: %s\n\n" % timestamp)
        log_file.flush()
        log_message("Logging initialized - Writing to: %s" % log_path)
        return True
    except Exception:
        error_msg = "Failed to set up logging:\n%s" % traceback.format_exc()
        cmds.warning(error_msg)
        print(error_msg)
        return False

def log_message(message):
    """Write a message to both Maya's script editor and the log file."""
    print(message)
    global log_file
    if log_file and not log_file.closed:
        try:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            log_file.write("[%s] %s\n" % (timestamp, message))
            log_file.flush()
        except:
            pass

# Window and node constants
WINDOW_NAME = "HaxGameExporter"
EXPORTER_NODE_TYPE = "gameFbxExporter"
CUSTOM_DATA_NODE = "haxGameExporterData"

# Data storage
global clip_data, file_types, fbx_versions, fps_options, export_settings, overwrite_all, skip_all
clip_data = []
file_types = ["Binary", "ASCII"]
fbx_versions = ["2014", "2015", "2016", "2018", "2020"]
fps_options = [30, 60, 120, 240]
overwrite_all = False
skip_all = False

# Anime quotes for export completion dialog
anime_quotes = [
    "Believe it! - Naruto",
    "I'm gonna be King of the Pirates! - Monkey D. Luffy",
    "Plus Ultra! - All Might",
    "It's over 9000! - Vegeta",
    "I'll take a potato chip... and eat it! - Light Yagami",
    "Who the hell do you think I am?! - Kamina",
    "I am here! - All Might",
    "Kamehameha! - Goku",
    "Tatakae! - Eren Yeager",
    "El Psy Congroo - Okabe Rintarou",
    "Tuturu! - Mayuri Shiina",
    "Yare yare daze - Jotaro Kujo",
    "Omae wa mou shindeiru - Kenshiro",
    "Bankai! - Ichigo Kurosaki",
    "Ora ora ora! - Jotaro Kujo",
    "Muda muda muda! - Dio Brando",
    "If you win, you live. If you lose, you die. If you don't fight, you can't win! - Eren Yeager",
    "A lesson without pain is meaningless - Edward Elric",
    "Believe in the me that believes in you! - Kamina",
    "I am justice! - Light Yagami",
    "Total Concentration! - Tanjiro Kamado",
    "The fake is of far greater value - Kaiki Deishuu",
    "A dropout will beat a genius through hard work - Rock Lee",
    "Fun things are fun! - Yui Hirasawa",
    "I don't know everything, I just know what I know - Tsubasa Hanekawa",
    "Even in the depths of hell, beauty can bloom - Kyojuro Rengoku",
    "The world is cruel, but also very beautiful - Mikasa Ackerman",
    "My drill is the drill that will pierce the heavens! - Simon"
]

# Helper function for UI refresh
def force_ui_refresh():
    """Force a UI refresh with a slight delay to ensure Maya processes updates."""
    try:
        cmds.refresh(force=True)
        time.sleep(0.01)  # Small delay to allow UI processing
        cmds.refresh()
        log_message("Forced UI refresh completed")
    except Exception as e:
        log_message("Error during UI refresh: %s" % str(e))

# Helper function to get joints and locators from selection or list
def get_joints_and_locators(objects=None):
    """
    Get joints and locators from a list of objects or from current selection.
    Locators are identified as transform nodes with locator shape children.
    
    Args:
        objects (list): Optional list of objects to filter. If None, uses current selection.
        
    Returns:
        list: List of joint and locator transform nodes
    """
    if objects is None:
        objects = cmds.ls(selection=True)
    
    result = []
    for obj in objects:
        node_type = cmds.nodeType(obj)
        if node_type == "joint":
            result.append(obj)
        elif node_type == "transform":
            # Check if this transform has a locator shape
            shapes = cmds.listRelatives(obj, shapes=True, type="locator") or []
            if shapes:
                result.append(obj)
    return result

# Deferred execution functions
def _force_refresh_fn():
    log_message("Forcing UI refresh via deferred execution...")
    force_ui_refresh()

def _try_alternative_export_fn():
    log_message("Trying alternative export method...")
    try:
        sel = get_joints_and_locators()
        if not sel:
            log_message("No root joint/locator found for alternative export")
            return
        root = sel[0]
        out_path = cmds.optionVar(q="out_path_temp") if cmds.optionVar(exists="out_path_temp") else ""
        if not out_path:
            log_message("No output path available for alternative export")
            return
        log_message("Alternative export to: %s using root: %s" % (out_path, root))
        try:
            select_export_subset(root)
            mel.eval("FBXResetExport;")
            mel.eval("FBXExportInAscii -v 0;")
            mel.eval("FBXExportSkins -v true;")
            mel.eval("FBXExportShapes -v true;")
            mel.eval("FBXExportUpAxis y;")
            mel.eval("FBXExportFileVersion -v FBX201800;")
            mel.eval('FBXExport -f "%s" -s;' % out_path)
            log_message("Alternative MEL FBXExport was successful")
        except Exception as e:
            log_message("MEL export failed, falling back to cmds.file(): %s" % str(e))
            cmds.file(out_path, force=True, options="v=0", type="FBX export", preserveReferences=False, exportSelected=True)
            log_message("cmds.file() export method completed")
        log_message("Alternative export method completed successfully")
    except Exception as alt_error:
        log_message("Alternative export method failed: %s" % str(alt_error))

# Default export settings
default_export_settings = {
    "fileType": "ASCII",
    "fbxVersion": "2018",
    "embedMedia": True,
    "bakeAnimation": True,
    "moveToOrigin": False,
    "exportPath": "",
    "clipPrefix": "",
    "exportMode": "Export All Clips",
    "currentPreset": "<None>",
    "removeNamespaces": False,
    "bakeFromConstraints": False,
    "includeChildren": True,
    "inputConnections": False,
    "constraints": False,
    "rotationOffset": {
        "enabled": False,
        "joint": "",
        "rotationX": 0.0,
        "rotationY": 0.0,
        "rotationZ": 0.0
    }
}
export_settings = default_export_settings.copy()

global scene_data_loaded
scene_data_loaded = False

def maya_exception_hook(exc_type, exc_value, exc_traceback):
    error_msg = "Maya Game Exporter Error: %s\n%s" % (exc_value, "".join(traceback.format_tb(exc_traceback)))
    cmds.warning(error_msg)
    log_message(error_msg)
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = maya_exception_hook

def open_log_file():
    global log_file
    try:
        project_dir = cmds.workspace(query=True, rootDirectory=True)
        if not project_dir:
            project_dir = cmds.internalVar(userWorkspaceDir=True)
        log_path = os.path.join(project_dir, "HaxExporterOutputLog.txt")
        if log_file and not log_file.closed:
            log_file.flush()
            log_file.close()
        if os.path.exists(log_path):
            log_message("Opening log file: %s" % log_path)
            if os.name == 'nt':
                os.startfile(log_path)
            elif os.name == 'posix':
                os.system('open "%s"' % log_path if sys.platform == 'darwin' else 'xdg-open "%s"' % log_path)
            log_file = open(log_path, 'a')
            return True
        log_message("Log file not found: %s" % log_path)
        return False
    except Exception as e:
        cmds.warning("Failed to open log file: %s" % str(e))
        return False

def get_or_create_data_node():
    """Get or create the custom data node, ensuring all required attributes exist."""
    if cmds.objExists(CUSTOM_DATA_NODE):
        node = CUSTOM_DATA_NODE
        # Verify required attributes exist, add if missing
        if not cmds.attributeQuery("clipData", node=node, exists=True):
            cmds.addAttr(node, longName="clipData", dataType="string")
            log_message("Added missing clipData attribute to node: %s" % node)
        if not cmds.attributeQuery("exportSettings", node=node, exists=True):
            cmds.addAttr(node, longName="exportSettings", dataType="string")
            log_message("Added missing exportSettings attribute to node: %s" % node)
        if not cmds.attributeQuery("dataVersion", node=node, exists=True):
            cmds.addAttr(node, longName="dataVersion", attributeType="short")
            log_message("Added missing dataVersion attribute to node: %s" % node)
        if not cmds.attributeQuery("currentPreset", node=node, exists=True):
            cmds.addAttr(node, longName="currentPreset", dataType="string")
            log_message("Added missing currentPreset attribute to node: %s" % node)
        return node
    try:
        node = cmds.createNode("script", name=CUSTOM_DATA_NODE)
        cmds.addAttr(node, longName="clipData", dataType="string")
        cmds.addAttr(node, longName="exportSettings", dataType="string")
        cmds.addAttr(node, longName="dataVersion", attributeType="short")
        cmds.addAttr(node, longName="currentPreset", dataType="string")
        log_message("Created new data node: %s with all required attributes" % node)
        return node
    except Exception:
        error_msg = "Error creating data node:\n%s" % traceback.format_exc()
        cmds.warning(error_msg)
        log_message(error_msg)
        return None

def save_scene_data():
    """Save clip data, export settings, and current preset to the data node."""
    global clip_data, export_settings
    try:
        node = get_or_create_data_node()
        if not node:
            cmds.warning("Failed to get or create data node.")
            log_message("Failed to get or create data node.")
            return False
        cmds.lockNode(node, lock=False)
        clip_data_json = json.dumps(clip_data)
        settings_json = json.dumps(export_settings)
        current_preset = cmds.optionMenu("presetDropdown", q=True, value=True) if cmds.optionMenu("presetDropdown", exists=True) else "<None>"
        try:
            cmds.setAttr(node + ".clipData", clip_data_json, type="string")
            log_message("Saved clipData to node: %s" % node)
        except Exception as e:
            log_message("Failed to set clipData attribute: %s" % str(e))
        try:
            cmds.setAttr(node + ".exportSettings", settings_json, type="string")
            log_message("Saved exportSettings to node: %s" % node)
        except Exception as e:
            log_message("Failed to set exportSettings attribute: %s" % str(e))
        try:
            cmds.setAttr(node + ".dataVersion", 1)
            log_message("Saved dataVersion to node: %s" % node)
        except Exception as e:
            log_message("Failed to set dataVersion attribute: %s" % str(e))
        try:
            cmds.setAttr(node + ".currentPreset", current_preset, type="string")
            log_message("Saved currentPreset '%s' to node: %s" % (current_preset, node))
        except Exception as e:
            log_message("Failed to set currentPreset attribute: %s" % str(e))
            # Attempt to recreate the attribute
            if not cmds.attributeQuery("currentPreset", node=node, exists=True):
                cmds.addAttr(node, longName="currentPreset", dataType="string")
                log_message("Recreated missing currentPreset attribute on node: %s" % node)
                try:
                    cmds.setAttr(node + ".currentPreset", current_preset, type="string")
                    log_message("Successfully saved currentPreset '%s' after recreating attribute" % current_preset)
                except Exception as e2:
                    log_message("Failed to set currentPreset after recreation: %s" % str(e2))
                    cmds.warning("Failed to save currentPreset attribute.")
                    return False
        # Save selected namespace
        selected_ns = get_selected_namespace()
        if not cmds.attributeQuery("selectedNamespace", node=node, exists=True):
            cmds.addAttr(node, longName="selectedNamespace", dataType="string")
        try:
            cmds.setAttr(node + ".selectedNamespace", selected_ns or "<None>", type="string")
            log_message("Saved selectedNamespace '%s' to node: %s" % (selected_ns, node))
        except Exception as e:
            log_message("Failed to set selectedNamespace attribute: %s" % str(e))
        cmds.lockNode(node, lock=True)
        log_message("Exporter data saved successfully to node: %s" % node)
        # In save_scene_data, after saving other data:
        save_anim_layer_states_to_node()
        return True
    except Exception:
        error_msg = "Error saving scene data to node:\n%s" % traceback.format_exc()
        cmds.warning(error_msg)
        log_message(error_msg)
        return False

def load_scene_data():
    global clip_data, export_settings, scene_data_loaded
    try:
        if not cmds.objExists(CUSTOM_DATA_NODE):
            scene_data_loaded = False
            return False
        node = CUSTOM_DATA_NODE
        if not cmds.attributeQuery("clipData", node=node, exists=True) or \
           not cmds.attributeQuery("exportSettings", node=node, exists=True):
            scene_data_loaded = False
            return False
        clip_data_json = cmds.getAttr(node + ".clipData")
        settings_json = cmds.getAttr(node + ".exportSettings")
        current_preset = cmds.getAttr(node + ".currentPreset") if cmds.attributeQuery("currentPreset", node=node, exists=True) else "<None>"
        if clip_data_json:
            clip_data[:] = json.loads(clip_data_json)
        if settings_json:
            export_settings.update(json.loads(settings_json))
        preset_dir = get_presets_folder()
        preset_path = os.path.join(preset_dir, current_preset + ".json")
        if current_preset != "<None>" and not os.path.exists(preset_path):
            current_preset = "<None>"
            log_message("Preset '%s' no longer exists, reverting to <None>" % current_preset)
        export_settings["currentPreset"] = current_preset
        log_message("Exporter data loaded from node: %s" % node)
        scene_data_loaded = True
        # Load selected namespace from metadata node
        global loaded_selected_ns
        loaded_selected_ns = None
        if cmds.attributeQuery("selectedNamespace", node=node, exists=True):
            loaded_selected_ns = cmds.getAttr(node + ".selectedNamespace")
        # Do not call refresh_namespace_menu here; wait until UI is built
        return True
    except Exception:
        error_msg = "Error loading scene data from node:\n%s" % traceback.format_exc()
        cmds.warning(error_msg)
        log_message(error_msg)
        if not scene_data_loaded:
            scene_data_loaded = False
        return False
    # In load_scene_data, after loading other data:
    global anim_layer_checkboxes
    anim_layer_checkboxes = load_anim_layer_states_from_node()

def get_presets_folder():
    scripts_dir = cmds.internalVar(userScriptDir=True)
    export_dir = os.path.join(scripts_dir, "hax_exporter_data")
    preset_dir = os.path.join(export_dir, "Presets")
    if not os.path.exists(export_dir):
        os.makedirs(export_dir)
    if not os.path.exists(preset_dir):
        os.makedirs(preset_dir)
    return preset_dir

def export_data_command(*args):
    """Export animation clip data to a text file."""
    global clip_data
    try:
        if not clip_data:
            cmds.warning("No clip data to export.")
            log_message("No clip data to export.")
            return
        scripts_dir = cmds.internalVar(userScriptDir=True)
        export_dir = os.path.join(scripts_dir, "hax_exporter_data")
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)
            log_message("Created directory: %s" % export_dir)
        scene_path = cmds.file(q=True, sceneName=True)
        scene_name = os.path.basename(scene_path)
        scene_name = re.sub(r'\.\d+$', '', scene_name)
        scene_name = os.path.splitext(scene_name)[0]
        if not scene_name:
            scene_name = "untitled"
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = "%s_%s.txt" % (timestamp, scene_name)
        file_path = os.path.join(export_dir, file_name)
        with open(file_path, 'w') as f:
            # Write selected namespace at the top
            selected_ns = get_selected_namespace() or "<None>"
            f.write("# Hax Game Exporter Clip Data\n")
            f.write("# Exported: %s\n" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            f.write("# Scene: %s\n" % scene_path)
            f.write("# Selected Namespace: %s\n" % selected_ns)
            # Write Export Path and Prefix
            f.write("# Export Path: %s\n" % export_settings.get("exportPath", ""))
            f.write("# Prefix: %s\n" % export_settings.get("clipPrefix", ""))
            # Write Rotation Offset settings
            rotation_settings = export_settings.get("rotationOffset", {})
            f.write("# Rotation Offset Enabled: %s\n" % rotation_settings.get("enabled", False))
            f.write("# Rotation Offset Joint: %s\n" % rotation_settings.get("joint", ""))
            f.write("# Rotation Offset XYZ: %.2f %.2f %.2f\n" % (
                rotation_settings.get("rotationX", 0.0),
                rotation_settings.get("rotationY", 0.0),
                rotation_settings.get("rotationZ", 0.0)
            ))
            f.write("\n# Animation Layer States (checked = enabled):\n")
            for layer, checked in anim_layer_checkboxes.items():
                f.write("%s: %s\n" % (layer, "[x]" if checked else "[ ]"))
            f.write("\n")
            f.write("# Format: [Enabled] ClipName StartFrame EndFrame FPS\n\n")
            for clip in clip_data:
                enabled_marker = "[x]" if clip.get("enabled", False) else "[ ]"
                clip_name = clip.get("name", "Untitled")
                start_frame = clip.get("start", 1)
                end_frame = clip.get("end", 24)
                fps = clip.get("fps", 30)
                f.write("%s %s %d %d %d\n" % (
                    enabled_marker, 
                    clip_name, 
                    start_frame, 
                    end_frame, 
                    fps
                ))
        log_message("Exported clip data to: %s" % file_path)
        cmds.inViewMessage(amg="Exported clip data to:\n%s" % file_path, pos='topCenter', fade=True)
        # Open containing folder
        if os.name == 'nt':
            os.startfile(export_dir)
        elif os.name == 'posix':
            if sys.platform == 'darwin':
                os.system('open "%s"' % export_dir)
            else:
                os.system('xdg-open "%s"' % export_dir)
        # Show confirmation dialog with file name and path
        cmds.confirmDialog(
            title='Export Successful',
            message='Clip data was exported successfully!\n\nFile:\n%s' % file_path,
            button=['OK'],
            defaultButton='OK',
            cancelButton='OK',
            dismissString='OK'
        )
        return True
    except Exception:
        error_msg = "Error exporting clip data:\n%s" % traceback.format_exc()
        cmds.warning(error_msg)
        log_message(error_msg)
        return False

def import_text_data(file_path):
    """Import animation clip data from a text file."""
    global clip_data
    try:
        if not os.path.exists(file_path):
            cmds.warning("File does not exist: %s" % file_path)
            log_message("File does not exist: %s" % file_path)
            return False
        # Read all lines from the file once
        with open(file_path, 'r') as f:
            lines = f.readlines()
        # First pass: parse Export Path and Prefix, and animation layer states
        anim_layer_section = False
        imported_anim_layer_states = {"Base Animation": True}
        export_path = None
        prefix = None
        rotation_offset_data = {
            "enabled": False,
            "joint": "",
            "rotationX": 0.0,
            "rotationY": 0.0,
            "rotationZ": 0.0
        }
        for line in lines:
            line = line.strip()
            if line.startswith('# Export Path:'):
                export_path = line.split(':', 1)[1].strip()
            elif line.startswith('# Prefix:'):
                prefix = line.split(':', 1)[1].strip()
            elif line.startswith('# Rotation Offset Enabled:'):
                enabled_str = line.split(':', 1)[1].strip()
                rotation_offset_data["enabled"] = enabled_str.lower() in ('true', 'yes', '1')
            elif line.startswith('# Rotation Offset Joint:'):
                rotation_offset_data["joint"] = line.split(':', 1)[1].strip()
            elif line.startswith('# Rotation Offset XYZ:'):
                xyz_str = line.split(':', 1)[1].strip()
                try:
                    values = xyz_str.split()
                    if len(values) >= 3:
                        rotation_offset_data["rotationX"] = float(values[0])
                        rotation_offset_data["rotationY"] = float(values[1])
                        rotation_offset_data["rotationZ"] = float(values[2])
                except (ValueError, IndexError):
                    log_message("Failed to parse rotation offset XYZ values: %s" % xyz_str)
            elif line.startswith('# Animation Layer States'):
                anim_layer_section = True
                continue
            if anim_layer_section:
                if not line or line.startswith('#'):
                    anim_layer_section = False
                    continue
                if ':' in line:
                    parts = line.split(':', 1)
                    layer = parts[0].strip()
                    state = parts[1].strip()
                    checked = '[x]' in state.lower()
                    imported_anim_layer_states[layer] = checked
        # After parsing, merge with current scene layers
        scene_layers = ["Base Animation"] + get_ordered_anim_layers()
        global anim_layer_checkboxes
        anim_layer_checkboxes = {}
        for l in scene_layers:
            if l in imported_anim_layer_states:
                anim_layer_checkboxes[l] = imported_anim_layer_states[l]
            else:
                anim_layer_checkboxes[l] = True  # Default to checked if not in import
        for l in imported_anim_layer_states:
            if l not in scene_layers:
                log_message("Imported anim layer '%s' not found in scene and will be ignored." % l)
        log_message("Applied imported anim layer states: %s" % anim_layer_checkboxes)
        # Set export path and prefix if found
        if export_path is not None:
            export_settings["exportPath"] = export_path
            if cmds.textField("pathField", exists=True):
                cmds.textField("pathField", edit=True, text=export_path)
        if prefix is not None:
            export_settings["clipPrefix"] = prefix
            if cmds.textField("prefixField", exists=True):
                cmds.textField("prefixField", edit=True, text=prefix)
        
        # Apply rotation offset data
        export_settings["rotationOffset"] = rotation_offset_data
        # Update rotation offset UI fields if they exist
        if cmds.checkBox("rotationOffsetEnabled", exists=True):
            cmds.checkBox("rotationOffsetEnabled", edit=True, value=rotation_offset_data["enabled"])
        if cmds.textField("rotationOffsetJoint", exists=True):
            cmds.textField("rotationOffsetJoint", edit=True, text=rotation_offset_data["joint"])
        if cmds.floatField("rotationOffsetX", exists=True):
            cmds.floatField("rotationOffsetX", edit=True, value=rotation_offset_data["rotationX"])
        if cmds.floatField("rotationOffsetY", exists=True):
            cmds.floatField("rotationOffsetY", edit=True, value=rotation_offset_data["rotationY"])
        if cmds.floatField("rotationOffsetZ", exists=True):
            cmds.floatField("rotationOffsetZ", edit=True, value=rotation_offset_data["rotationZ"])
        log_message("Applied imported rotation offset settings: %s" % rotation_offset_data)
        # Second pass: parse clips
        new_clips = []
        for line in lines:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            # Skip animation layer state lines (e.g., LayerName: [x], [ ], [], or with whitespace)
            if re.match(r'^.+: \[\s?.?\s?\]$', line):
                continue
            # Parse the line
            # Format: [Enabled] ClipName StartFrame EndFrame FPS
            try:
                # Check if the line has the expected format
                match = re.match(r'^\[(x| )\] (.*) (\d+) (\d+) (\d+)$', line)
                if match:
                    enabled = match.group(1) == 'x'
                    clip_name = match.group(2)
                    start_frame = int(match.group(3))
                    end_frame = int(match.group(4))
                    fps = int(match.group(5))
                    # Validate FPS value
                    if fps not in fps_options:
                        cmds.warning("Invalid FPS value in import: %s. Allowed: %s. Defaulting to 30." % (fps, fps_options))
                        log_message("Invalid FPS value in import: %s. Defaulting to 30." % fps)
                        fps = 30
                    new_clips.append({
                        "name": clip_name,
                        "start": start_frame,
                        "end": end_frame,
                        "fps": fps,
                        "enabled": enabled,
                        "exportMesh": True  # Default value
                    })
                else:
                    log_message("Warning: Could not parse line: %s" % line)
            except Exception as e:
                log_message("Error parsing line '%s': %s" % (line, str(e)))
        if not new_clips:
            cmds.warning("No valid clip data found in file.")
            log_message("No valid clip data found in file: %s" % file_path)
            return False
        # Replace existing clips with new ones
        clip_data[:] = new_clips
        log_message("Imported %d clips from: %s" % (len(new_clips), file_path))
        for idx, c in enumerate(clip_data):
            log_message("Clip entry imported: index=%d, entry=%s" % (idx, c))
        save_scene_data()
        refresh_ui()
        return True
    except Exception:
        error_msg = "Error importing clip data from file:\n%s" % traceback.format_exc()
        cmds.warning(error_msg)
        log_message(error_msg)
        return False

def save_preset(name):
    """Save a preset, fetch updated preset list, and update dropdown deferredly."""
    if not name:
        log_message("No preset name provided, aborting save.")
        return
    preset_dir = get_presets_folder()
    path = os.path.join(preset_dir, name + ".json")
    try:
        # Capture current UI values into export_settings before saving
        if cmds.textField("pathField", exists=True):
            export_settings["exportPath"] = cmds.textField("pathField", q=True, text=True)
        if cmds.textField("prefixField", exists=True):
            export_settings["clipPrefix"] = cmds.textField("prefixField", q=True, text=True)
        
        # Capture file type and FBX version from UI
        if cmds.optionMenuGrp("fileTypeMenu", exists=True):
            export_settings["fileType"] = cmds.optionMenuGrp("fileTypeMenu", q=True, value=True)
        if cmds.optionMenuGrp("fbxVerMenu", exists=True):
            export_settings["fbxVersion"] = cmds.optionMenuGrp("fbxVerMenu", q=True, value=True)
        
        # Capture checkbox values from UI
        if cmds.checkBox("removeNamespacesCheck", exists=True):
            export_settings["removeNamespaces"] = cmds.checkBox("removeNamespacesCheck", q=True, value=True)
        if cmds.checkBox("bakeFromConstraintsCheck", exists=True):
            export_settings["bakeFromConstraints"] = cmds.checkBox("bakeFromConstraintsCheck", q=True, value=True)
        if cmds.checkBox("includeChildrenCheck", exists=True):
            export_settings["includeChildren"] = cmds.checkBox("includeChildrenCheck", q=True, value=True)
        if cmds.checkBox("inputConnectionsCheck", exists=True):
            export_settings["inputConnections"] = cmds.checkBox("inputConnectionsCheck", q=True, value=True)
        if cmds.checkBox("constraintsCheck", exists=True):
            export_settings["constraints"] = cmds.checkBox("constraintsCheck", q=True, value=True)
        
        # Capture rotation offset UI values
        if cmds.checkBox("rotationOffsetEnabled", exists=True):
            if "rotationOffset" not in export_settings:
                export_settings["rotationOffset"] = {}
            export_settings["rotationOffset"]["enabled"] = cmds.checkBox("rotationOffsetEnabled", q=True, value=True)
        if cmds.textField("rotationOffsetJoint", exists=True):
            if "rotationOffset" not in export_settings:
                export_settings["rotationOffset"] = {}
            export_settings["rotationOffset"]["joint"] = cmds.textField("rotationOffsetJoint", q=True, text=True)
        if cmds.floatField("rotationOffsetX", exists=True):
            if "rotationOffset" not in export_settings:
                export_settings["rotationOffset"] = {}
            export_settings["rotationOffset"]["rotationX"] = cmds.floatField("rotationOffsetX", q=True, value=True)
        if cmds.floatField("rotationOffsetY", exists=True):
            if "rotationOffset" not in export_settings:
                export_settings["rotationOffset"] = {}
            export_settings["rotationOffset"]["rotationY"] = cmds.floatField("rotationOffsetY", q=True, value=True)
        if cmds.floatField("rotationOffsetZ", exists=True):
            if "rotationOffset" not in export_settings:
                export_settings["rotationOffset"] = {}
            export_settings["rotationOffset"]["rotationZ"] = cmds.floatField("rotationOffsetZ", q=True, value=True)
        
        # Capture current animation layer UI states
        global anim_layer_checkboxes
        scene_layers = ["Base Animation"] + get_ordered_anim_layers()
        for layer in scene_layers:
            checkbox_name = "animLayer_" + layer
            if cmds.checkBox(checkbox_name, exists=True):
                # Only capture non-Base Animation layers that are interactive
                if layer != "Base Animation" and cmds.checkBox(checkbox_name, q=True, enable=True):
                    anim_layer_checkboxes[layer] = cmds.checkBox(checkbox_name, q=True, value=True)
        log_message("Captured animation layer states before saving preset: %s" % anim_layer_checkboxes)
        
        joints = get_joints_and_locators()
        
        # If no joints selected, check if we're updating an existing preset
        if not joints:
            if os.path.isfile(path):
                # Preset exists - load existing joint list and update only settings
                log_message("No joints selected, updating settings for existing preset '%s'" % name)
                try:
                    with open(path, "r") as f:
                        existing_data = json.load(f)
                    # Keep existing joints, update only settings and animation layers
                    joints = existing_data.get("root_joints", [])
                    log_message("Preserving %d existing joints from preset" % len(joints))
                except Exception as e:
                    log_message("Error reading existing preset: %s" % str(e))
                    joints = []
                
                # If still no joints (corrupted preset or empty), show error
                if not joints:
                    cmds.warning("Cannot update preset without joints.")
                    cmds.confirmDialog(
                        title="No Joints in Preset",
                        message="This preset has no joints. Please select at least one joint or locator to save.",
                        button=["OK"],
                        defaultButton="OK"
                    )
                    return
            else:
                # New preset - must have joints selected
                cmds.warning("No joints/locators selected for new preset.")
                log_message("No joints/locators selected for new preset '%s'" % name)
                cmds.confirmDialog(
                    title="No Joints/Locators Selected",
                    message="You must select at least one joint or locator to create a new preset.",
                    button=["OK"],
                    defaultButton="OK",
                    cancelButton="OK",
                    dismissString="OK"
                )
                return
        else:
            log_message("Saving preset '%s' with %d selected joints/locators" % (name, len(joints)))
        
        data = {
            "export_settings": export_settings.copy(),
            "root_joints": joints,
            "animation_layer_states": anim_layer_checkboxes.copy()
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        log_message("Saved preset '%s' to %s" % (name, path))
        # Fetch updated preset list immediately after saving
        force_ui_refresh()  # Ensure file system is up-to-date
        presets = cmds.getFileList(folder=preset_dir, filespec="*.json")
        preset_names = [p.replace(".json", "") for p in presets]
        log_message("Fetched %d presets after saving '%s': %s" % (len(preset_names), name, preset_names))
        # Update the preset menu with the new preset list
        def deferred_update():
            try:
                update_preset_menu(presets=presets)  # Pass pre-fetched presets
                if cmds.optionMenu("presetDropdown", exists=True):
                    if name in preset_names:
                        try:
                            cmds.optionMenu("presetDropdown", edit=True, value=name)
                            log_message("Deferred: Set dropdown to preset '%s'" % name)
                            # Don't call on_preset_selected - we're just updating the UI to reflect the current preset
                            export_settings["currentPreset"] = name
                            save_scene_data()
                        except Exception as e:
                            log_message("Deferred: Error setting dropdown to '%s': %s" % (name, str(e)))
                            # Fallback to <None>
                            cmds.optionMenu("presetDropdown", edit=True, value="<None>")
                            log_message("Deferred: Fell back to <None> due to selection error")
                            export_settings["currentPreset"] = "<None>"
                            save_scene_data()
                    else:
                        log_message("Deferred: Preset '%s' not found in menu, setting to <None>" % name)
                        cmds.optionMenu("presetDropdown", edit=True, value="<None>")
                        export_settings["currentPreset"] = "<None>"
                        save_scene_data()
                    force_ui_refresh()  # Ensure UI reflects changes
                    cmds.inViewMessage(amg="Preset '%s' saved." % name, pos='topCenter', fade=True)
            except Exception as e:
                error_msg = "Deferred: Error during preset menu update: %s" % str(e)
                cmds.warning(error_msg)
                log_message(error_msg)
        cmds.evalDeferred(deferred_update, lowestPriority=True)
        log_message("Scheduled deferred preset menu update for '%s'" % name)
    except Exception:
        error_msg = "Error saving preset '%s':\n%s" % (name, traceback.format_exc())
        cmds.warning(error_msg)
        log_message(error_msg)
        print(error_msg)

def load_preset(name, skip_path_update=False):
    preset_dir = get_presets_folder()
    path = os.path.join(preset_dir, name + ".json")
    try:
        if cmds.file(path, query=True, exists=True):
            with open(path, 'r') as f:
                data = json.load(f)
            
            # If we're loading during export, preserve more settings
            if skip_path_update:
                # Save current settings we want to preserve
                current_settings = {
                    "exportPath": export_settings.get("exportPath", ""),
                    "clipPrefix": export_settings.get("clipPrefix", ""),
                    "exportMode": export_settings.get("exportMode", "Export All Clips"),
                    "rotationOffset": export_settings.get("rotationOffset", {}).copy(),
                    "includeChildren": export_settings.get("includeChildren", True),
                    "inputConnections": export_settings.get("inputConnections", False),
                    "constraints": export_settings.get("constraints", False),
                    "removeNamespaces": export_settings.get("removeNamespaces", False),
                    "bakeFromConstraints": export_settings.get("bakeFromConstraints", False),
                    "moveToOrigin": export_settings.get("moveToOrigin", False),
                    "embedMedia": export_settings.get("embedMedia", True),
                    "bakeAnimation": export_settings.get("bakeAnimation", True),
                    "altRootControl": export_settings.get("altRootControl", "")
                }
                
                # Get animation layer states before they're overwritten
                current_anim_layers = anim_layer_checkboxes.copy()
                
                # Update settings from preset (only for joint data)
                preset_settings = data.get("export_settings", {})
                
                # Only update specific settings from the preset, preserve the rest
                for key in preset_settings:
                    if key not in ["exportPath", "clipPrefix", "exportMode", "rotationOffset", 
                                  "includeChildren", "inputConnections", "constraints", "removeNamespaces", "bakeFromConstraints",
                                  "moveToOrigin", "embedMedia", "bakeAnimation", "altRootControl"]:
                        export_settings[key] = preset_settings[key]
                
                # Restore preserved settings
                for key, value in current_settings.items():
                    export_settings[key] = value
                
                log_message("Preserved current settings during preset loading for export")
            else:
                # Normal preset loading - update all settings
                export_settings.update(data.get("export_settings", {}))
                
                # Update UI with new settings
                if cmds.textField("pathField", exists=True):
                    cmds.textField("pathField", edit=True, text=export_settings["exportPath"])
                
                # Only update the prefix field if the preset has a non-empty prefix
                preset_prefix = export_settings.get("clipPrefix", "")
                if cmds.textField("prefixField", exists=True):
                    if preset_prefix:
                        cmds.textField("prefixField", edit=True, text=preset_prefix)
                    else:
                        # If the preset prefix is empty, keep the current UI value and update export_settings
                        export_settings["clipPrefix"] = cmds.textField("prefixField", q=True, text=True)
            if cmds.checkBoxGrp("exportOptionsGrp", exists=True):
                cmds.checkBoxGrp("exportOptionsGrp", e=True, value3=export_settings["moveToOrigin"])
            
            # Only update UI fields if we're not in export mode
            if not skip_path_update:
                # Update rotation offset UI fields if they exist
                rotation_settings = export_settings.get("rotationOffset", {})
                if cmds.checkBox("rotationOffsetEnabled", exists=True):
                    cmds.checkBox("rotationOffsetEnabled", edit=True, value=rotation_settings.get("enabled", False))
                if cmds.textField("rotationOffsetJoint", exists=True):
                    cmds.textField("rotationOffsetJoint", edit=True, text=rotation_settings.get("joint", ""))
                if cmds.floatField("rotationOffsetX", exists=True):
                    cmds.floatField("rotationOffsetX", edit=True, value=rotation_settings.get("rotationX", 0.0))
                if cmds.floatField("rotationOffsetY", exists=True):
                    cmds.floatField("rotationOffsetY", edit=True, value=rotation_settings.get("rotationY", 0.0))
                if cmds.floatField("rotationOffsetZ", exists=True):
                    cmds.floatField("rotationOffsetZ", edit=True, value=rotation_settings.get("rotationZ", 0.0))
                
                # Update remove namespaces checkbox
                if cmds.checkBox("removeNamespacesCheck", exists=True):
                    cmds.checkBox("removeNamespacesCheck", edit=True, value=export_settings.get("removeNamespaces", False))
                
                # Update bake from constraints checkbox
                if cmds.checkBox("bakeFromConstraintsCheck", exists=True):
                    cmds.checkBox("bakeFromConstraintsCheck", edit=True, value=export_settings.get("bakeFromConstraints", False))
                
                # Update include children checkbox
                if cmds.checkBox("includeChildrenCheck", exists=True):
                    cmds.checkBox("includeChildrenCheck", edit=True, value=export_settings.get("includeChildren", True))
                
                # Update input connections checkbox
                if cmds.checkBox("inputConnectionsCheck", exists=True):
                    cmds.checkBox("inputConnectionsCheck", edit=True, value=export_settings.get("inputConnections", False))
                
                # Update constraints checkbox
                if cmds.checkBox("constraintsCheck", exists=True):
                    cmds.checkBox("constraintsCheck", edit=True, value=export_settings.get("constraints", False))
                
                # Update file type dropdown (Binary/ASCII)
                if cmds.optionMenuGrp("fileTypeMenu", exists=True):
                    file_type = export_settings.get("fileType", "ASCII")
                    try:
                        cmds.optionMenuGrp("fileTypeMenu", edit=True, value=file_type)
                    except Exception as e:
                        log_message("Could not set file type to '%s': %s" % (file_type, str(e)))
                
                # Update FBX version dropdown
                if cmds.optionMenuGrp("fbxVerMenu", exists=True):
                    fbx_version = export_settings.get("fbxVersion", "2018")
                    try:
                        cmds.optionMenuGrp("fbxVerMenu", edit=True, value=fbx_version)
                    except Exception as e:
                        log_message("Could not set FBX version to '%s': %s" % (fbx_version, str(e)))
                    
                # Update export mode dropdown if it exists
                if "exportMode" in export_settings and cmds.optionMenu("exportModeMenu", exists=True):
                    if export_settings["exportMode"] == "Export All Clips":
                        cmds.optionMenu("exportModeMenu", edit=True, select=1)
                    else:
                        cmds.optionMenu("exportModeMenu", edit=True, select=2)
            
            # Load and apply animation layer states if they exist in the preset
            preset_anim_layer_states = data.get("animation_layer_states", {})
            
            # Only update animation layers if we're not in export mode (skip_path_update=False)
            if preset_anim_layer_states and not skip_path_update:
                # Get current scene layers
                scene_layers = ["Base Animation"] + get_ordered_anim_layers()
                # Update anim_layer_checkboxes with preset states
                for layer in scene_layers:
                    if layer in preset_anim_layer_states:
                        anim_layer_checkboxes[layer] = preset_anim_layer_states[layer]
                    # If layer is not in preset, keep current state (don't force default)
                
                # Update animation layer UI if it exists
                for layer in scene_layers:
                    checkbox_name = "animLayer_" + layer
                    if cmds.checkBox(checkbox_name, exists=True):
                        cmds.checkBox(checkbox_name, edit=True, value=anim_layer_checkboxes.get(layer, True))
                
                # Save the updated animation layer states
                save_anim_layer_states_to_node()
                log_message("Loaded animation layer states from preset: %s" % preset_anim_layer_states)
            elif skip_path_update:
                # In export mode, preserve current animation layer states
                log_message("Preserved current animation layer states during export")
            
            log_message("Loaded preset '%s' from %s" % (name, path))
            return data.get("root_joints", [])
        log_message("Preset file not found: %s" % path)
        return []
    except Exception:
        error_msg = "Error loading preset '%s':\n%s" % (name, traceback.format_exc())
        cmds.warning(error_msg)
        log_message(error_msg)
        print(error_msg)
        return []

def delete_preset():
    """Delete a preset and update the dropdown menu immediately."""
    name = cmds.optionMenu("presetDropdown", q=True, value=True)
    if name == "<None>":
        cmds.warning("No preset selected.")
        log_message("No preset selected for deletion.")
        return
    confirm = cmds.confirmDialog(
        title="Delete Preset?",
        message="Are you sure you want to delete preset: %s?" % name,
        button=["Yes", "Cancel"],
        defaultButton="Yes",
        cancelButton="Cancel",
        dismissString="Cancel"
    )
    if confirm != "Yes":
        log_message("Preset deletion cancelled for '%s'" % name)
        return
    preset_dir = get_presets_folder()
    path = os.path.join(preset_dir, name + ".json")
    if os.path.exists(path):
        try:
            os.remove(path)
            log_message("Deleted preset '%s' from %s" % (name, path))
            update_preset_menu()
            # Set dropdown to <None> or last saved preset
            if cmds.optionMenu("presetDropdown", exists=True):
                preset_dir = get_presets_folder()
                presets = cmds.getFileList(folder=preset_dir, filespec="*.json")
                new_selection = export_settings.get("currentPreset", "<None>")
                preset_names = [p.replace(".json", "") for p in presets]
                if new_selection != "<None>" and new_selection not in preset_names:
                    new_selection = "<None>"
                    log_message("Deleted preset was last used, falling back to <None>")
                try:
                    cmds.optionMenu("presetDropdown", edit=True, value=new_selection)
                    log_message("Setting dropdown to: %s" % new_selection)
                    on_preset_selected(new_selection)
                except Exception as e:
                    log_message("Error setting dropdown to '%s': %s" % (new_selection, str(e)))
                    # Force recreate the menu if setting fails
                    update_preset_menu()
                    cmds.optionMenu("presetDropdown", edit=True, value="<None>")
                    on_preset_selected("<None>")
            refresh_ui()  # Ensure UI reflects the deletion
            cmds.inViewMessage(amg="Preset '%s' deleted.", pos='topCenter', fade=True)
        except Exception:
            error_msg = "Error deleting preset '%s':\n%s" % (name, traceback.format_exc())
            cmds.warning(error_msg)
            log_message(error_msg)
    else:
        log_message("Preset file not found: %s" % path)
        cmds.warning("Preset file not found.")

def update_preset_menu(presets=None):
    """Update the preset dropdown menu with available presets, using last saved preset."""
    preset_dir = get_presets_folder()
    # Use provided presets if available, otherwise query the directory
    if presets is None:
        presets = cmds.getFileList(folder=preset_dir, filespec="*.json")
    try:
        if cmds.optionMenu("presetDropdown", exists=True):
            # Remove all existing menu items safely
            menu_items = cmds.optionMenu("presetDropdown", q=True, itemListLong=True) or []
            for item in menu_items:
                try:
                    cmds.deleteUI(item)
                except Exception as e:
                    log_message('Failed to delete preset menu item {}: {}'.format(item, str(e)))
            # Add <None> first
            cmds.menuItem(label="<None>", annotation="Clear preset selection", parent="presetDropdown")
            # Add available presets
            preset_names = []
            for preset in presets:
                name = preset.replace(".json", "")
                cmds.menuItem(label=name, annotation="Load preset '%s'" % name, parent="presetDropdown")
                preset_names.append(name)
            log_message("Populated preset dropdown with %d presets: %s" % (len(preset_names), preset_names))
            # Defer setting the selection to the last saved preset
            def deferred_selection():
                try:
                    # Use the last saved preset from export_settings
                    new_selection = export_settings.get("currentPreset", "<None>")
                    if new_selection != "<None>" and new_selection not in preset_names:
                        log_message("Last saved preset '%s' not found, falling back to <None>" % new_selection)
                        new_selection = "<None>"
                    log_message("Attempting to set dropdown to last saved preset: %s" % new_selection)
                    for attempt in range(3):  # Retry up to 3 times
                        try:
                            cmds.optionMenu("presetDropdown", edit=True, value=new_selection)
                            log_message("Deferred: Successfully set dropdown to: %s (attempt %d)" % (new_selection, attempt+1))
                            break
                        except Exception as e:
                            log_message("Deferred: Retry %d failed to set dropdown to '%s': %s" % (attempt+1, new_selection, str(e)))
                            time.sleep(0.05)  # Wait briefly before retrying
                    else:
                        log_message("Deferred: All retries failed, falling back to <None>")
                        cmds.optionMenu("presetDropdown", edit=True, value="<None>")
                        new_selection = "<None>"
                    on_preset_selected(new_selection)
                    force_ui_refresh()
                except Exception as e:
                    error_msg = "Deferred: Error setting dropdown selection: %s" % str(e)
                    cmds.warning(error_msg)
                    log_message(error_msg)
            cmds.evalDeferred(deferred_selection, lowestPriority=True)
            log_message("Scheduled deferred dropdown selection to: %s" % export_settings.get("currentPreset", "<None>"))
        else:
            log_message("Preset dropdown does not exist, skipping update")
    except Exception:
        error_msg = "Error updating preset menu:\n%s" % traceback.format_exc()
        cmds.warning(error_msg)
        log_message(error_msg)

def has_native_exporter_data():
    nodes = cmds.ls(type=EXPORTER_NODE_TYPE)
    if not nodes:
        return False
    log_message("Found Maya Game Exporter nodes: %s" % nodes)
    return len(nodes) > 0

def show_import_dialog():
    result = cmds.confirmDialog(
        title='Import Maya Game Exporter Data',
        message='This scene contains clip data, export path, and prefix from Maya\'s native Game Exporter.\n\nWould you like to import these settings?',
        button=['Import', 'Start Empty'],
        defaultButton='Import',
        cancelButton='Start Empty',
        dismissString='Start Empty'
    )
    return result == 'Import'

# Add a module-level flag to track popup state
_namespace_popup_shown = False

def on_preset_selected(name, from_initialization=False):
    global _namespace_popup_shown
    _namespace_popup_shown = False  # Reset flag on each new preset selection
    if name == "<None>":
        export_settings["currentPreset"] = "<None>"
        save_scene_data()
        log_message("Selected preset: <None>")
        return
    
    # Set the preset as normal
    export_settings["currentPreset"] = name
    
    # Only load preset data if this is from user interaction, not initialization
    if not from_initialization:
        # Normal preset loading - update UI path
        load_preset(name, skip_path_update=False)
        save_scene_data()
        refresh_ui()
    else:
        # During initialization, data is already loaded, just save the current preset
        save_scene_data()
    
    log_message("Selected preset: %s" % name)

    # After UI is drawn, check for namespace match and prompt user to set namespace
    def check_and_prompt_namespace():
        global _namespace_popup_shown
        if _namespace_popup_shown:
            return
        try:
            # Get preset joints from the already loaded preset
            preset_dir = get_presets_folder()
            preset_path = os.path.join(preset_dir, name + ".json")
            preset_joints = []
            if os.path.exists(preset_path):
                try:
                    with open(preset_path, 'r') as f:
                        data = json.load(f)
                        preset_joints = data.get("root_joints", [])
                except:
                    preset_joints = []
            
            valid_namespaces = get_all_namespaces()
            valid_namespaces = [ns for ns in valid_namespaces if ns != '<None>']
            found_ns = None
            for joint in preset_joints:
                for ns in valid_namespaces:
                    if joint.startswith(ns + ":"):
                        found_ns = ns
                        break
                if found_ns:
                    break
            if found_ns:
                _namespace_popup_shown = True
                confirm = cmds.confirmDialog(
                    title="Set Namespace?",
                    message=("Some joints in this preset use the namespace: '%s'.\n\nSet the Namespace dropdown to this value?" % found_ns),
                    button=["Yes", "No"],
                    defaultButton="Yes",
                    cancelButton="No",
                    dismissString="No"
                )
                if confirm == "Yes":
                    if cmds.optionMenu(NAMESPACE_MENU, exists=True):
                        cmds.optionMenu(NAMESPACE_MENU, edit=True, value=found_ns)
                        save_scene_data()
                        log_message("Namespace set to '%s' after preset selection." % found_ns)
        except Exception as e:
            log_message("Error in deferred namespace check: %s" % str(e))
    # Schedule the check after the UI is drawn and stable
    cmds.evalDeferred(check_and_prompt_namespace, lowestPriority=True)

def on_export_mode_selected(mode):
    export_settings["exportMode"] = mode
    save_scene_data()
    if mode == "Export All Clips":
        export_clips()
    else:
        export_selected_clips()

def move_to_origin(root, use_anim_layer=False):
    """Move the root joint to the origin using an additive animation layer.
    
    Args:
        root (str): The root joint or control to move to origin
        use_anim_layer (bool): Whether to use an animation layer (always true now)
    
    Returns:
        tuple: (original position, original rotation, animation layer)
    """
    # Always capture original position and rotation
    pos = cmds.xform(root, q=True, ws=True, t=True)
    rot = cmds.xform(root, q=True, ws=True, ro=True)
    
    # Always use animation layer now for consistency with rotation offset
    anim_layer = None
    layer_name = "HaxMoveToOriginLayer"
    
    # Clean up any existing layer first
    if cmds.objExists(layer_name):
        cmds.delete(layer_name)
        log_message("Deleted existing move to origin layer")
    
    # Create temporary additive animation layer
    try:
        anim_layer = cmds.animLayer(layer_name, override=False)
        log_message("Created temporary additive animation layer for Move to Origin: %s" % anim_layer)
        
        # Add the root/control to the animation layer
        cmds.select(root, replace=True)
        cmds.animLayer(anim_layer, edit=True, addSelectedObjects=True)
        log_message("Added '%s' to move to origin layer" % root)
        
        # Get current frame to key on
        current_frame = cmds.currentTime(q=True)
        
        # Set keyframes with zero values for position and rotation
        for attr, value in [
            ("translateX", 0), ("translateY", 0), ("translateZ", 0),
            ("rotateX", 0), ("rotateY", 0), ("rotateZ", 0)
        ]:
            # Set the keyframe on the animation layer
            cmds.setKeyframe(root, attribute=attr, time=current_frame, value=value, animLayer=anim_layer)
            log_message("Set keyframe: %s.%s = %.2f at frame %d on layer %s" % (root, attr, value, current_frame, anim_layer))
        
        # Force Maya to process the animation layer
        cmds.refresh(force=True)
        # Small delay to ensure Maya fully processes the animation layer
        import time
        time.sleep(0.1)
        # Force evaluation at the keyed frame
        cmds.currentTime(current_frame)
        cmds.refresh(force=True)
        
        log_message("Move to origin applied successfully using additive animation layer")
    except Exception as e:
        log_message("Error applying move to origin: %s" % str(e))
        # Fall back to direct transformation if animation layer fails
        if not anim_layer:
            cmds.xform(root, ws=True, t=[0,0,0])
            cmds.xform(root, ws=True, ro=[0,0,0])
            log_message("Used direct transformation for move to origin (fallback)")
    
    return pos, rot, anim_layer

def restore_position(root, pos_rot_anim):
    """Restore the original position and clean up the animation layer.
    
    Args:
        root (str): The root joint or control to restore
        pos_rot_anim (tuple): (original position, original rotation, animation layer)
    """
    pos, rot, anim_layer = pos_rot_anim if len(pos_rot_anim) == 3 else (pos_rot_anim[0], pos_rot_anim[1], None)
    
    # If we have an animation layer, mute it first before deleting
    if anim_layer and cmds.objExists(anim_layer):
        try:
            # Mute the layer first
            cmds.animLayer(anim_layer, edit=True, mute=True)
            log_message("Muted move to origin layer '%s' before deletion" % anim_layer)
            
            # Force Maya to process the muting
            cmds.refresh(force=True)
            import time
            time.sleep(0.05)
            
            # Delete the layer
            cmds.delete(anim_layer)
            log_message("Deleted move to origin layer '%s' after export" % anim_layer)
        except Exception as e:
            log_message("Failed to delete move to origin layer '%s': %s" % (anim_layer, str(e)))
            # Try alternative deletion method if the first one failed
            try:
                cmds.animLayer(anim_layer, edit=True, lock=False)
                cmds.animLayer(anim_layer, edit=True, selected=True)
                cmds.animLayer(edit=True, removeSelectedAnimLayer=True)
                log_message("Used alternative method to delete move to origin layer")
            except Exception as e2:
                log_message("All attempts to delete move to origin layer failed: %s" % str(e2))
    
    # Restore the original position and rotation as a fallback
    cmds.xform(root, ws=True, t=pos)
    cmds.xform(root, ws=True, ro=rot)
    log_message("Restored original position and rotation for '%s'" % root)

def apply_rotation_offset(start_frame):
    """Apply rotation offset using animation layer if enabled.
    
    Args:
        start_frame (int): The first frame of the export range to key the offset on
    """
    rotation_layer = None
    try:
        rotation_settings = export_settings.get("rotationOffset", {})
        if not rotation_settings.get("enabled", False):
            return None
            
        joint_name = rotation_settings.get("joint", "")
        if not joint_name or not cmds.objExists(joint_name):
            log_message("Rotation offset enabled but no valid joint specified: %s" % joint_name)
            return None
            
        rot_x = rotation_settings.get("rotationX", 0.0)
        rot_y = rotation_settings.get("rotationY", 0.0)
        rot_z = rotation_settings.get("rotationZ", 0.0)
        
        if rot_x == 0.0 and rot_y == 0.0 and rot_z == 0.0:
            log_message("Rotation offset values are all zero, skipping")
            return None
            
        log_message("Applying rotation offset to '%s': X=%.2f, Y=%.2f, Z=%.2f on frame %d" % (joint_name, rot_x, rot_y, rot_z, start_frame))
        
        # Clean up any existing rotation offset layer
        layer_name = "HaxRotationOffsetLayer"
        if cmds.objExists(layer_name):
            cmds.delete(layer_name)
            log_message("Deleted existing rotation offset layer")
            
        # Create temporary additive animation layer
        rotation_layer = cmds.animLayer(layer_name, override=False)
        log_message("Created temporary additive animation layer: %s" % rotation_layer)
        
        # Add the joint/control to the animation layer
        cmds.select(joint_name, replace=True)
        cmds.animLayer(rotation_layer, edit=True, addSelectedObjects=True)
        log_message("Added '%s' to rotation offset layer" % joint_name)
        
        # Set keyframes on the first frame of the export range with the rotation offset values
        for attr, value in [("rotateX", rot_x), ("rotateY", rot_y), ("rotateZ", rot_z)]:
            if value != 0.0:
                # Set the keyframe on the animation layer at the first frame
                cmds.setKeyframe(joint_name, attribute=attr, time=start_frame, value=value, animLayer=rotation_layer)
                log_message("Set keyframe: %s.%s = %.2f at frame %d on layer %s" % (joint_name, attr, value, start_frame, rotation_layer))
        
        # Force Maya to process the animation layer before export
        cmds.refresh(force=True)
        # Small delay to ensure Maya fully processes the animation layer
        import time
        time.sleep(0.1)
        # Force evaluation at the keyed frame to ensure the layer is active
        cmds.currentTime(start_frame)
        cmds.refresh(force=True)
        
        log_message("Rotation offset applied successfully using additive animation layer")
        return rotation_layer
        
    except Exception as e:
        error_msg = "Error applying rotation offset: %s" % str(e)
        log_message(error_msg)
        cmds.warning(error_msg)
        # Clean up if something went wrong
        if rotation_layer and cmds.objExists(rotation_layer):
            try:
                cmds.delete(rotation_layer)
                log_message("Cleaned up rotation layer after error")
            except:
                pass
        return None

def remove_rotation_offset(rotation_layer):
    """Remove the rotation offset animation layer."""
    if not rotation_layer:
        log_message("No rotation layer to remove")
        return
        
    log_message("Attempting to remove rotation offset layer: %s" % rotation_layer)
    
    if cmds.objExists(rotation_layer):
        try:
            # Force Maya to refresh before deletion to ensure layer is not in use
            cmds.refresh(force=True)
            
            # Mute the animation layer before deletion
            try:
                cmds.animLayer(rotation_layer, edit=True, mute=True)
                log_message("Muted rotation offset layer before deletion")
            except Exception as mute_err:
                log_message("Warning: Could not mute layer before deletion: %s" % str(mute_err))
            
            # Delete the animation layer
            cmds.delete(rotation_layer)
            log_message("Successfully removed rotation offset layer: %s" % rotation_layer)
            
            # Verify deletion
            if cmds.objExists(rotation_layer):
                log_message("Warning: Layer still exists after deletion attempt")
                # Try alternative deletion method
                try:
                    cmds.animLayer(rotation_layer, edit=True, delete=True)
                    log_message("Layer removed using alternative method")
                except:
                    log_message("Alternative deletion method also failed")
            else:
                log_message("Confirmed: Layer successfully deleted")
                
        except Exception as e:
            log_message("Failed to remove rotation offset layer '%s': %s" % (rotation_layer, str(e)))
            # Try alternative deletion
            try:
                cmds.animLayer(rotation_layer, edit=True, delete=True)
                log_message("Layer removed using fallback method")
            except Exception as e2:
                log_message("Fallback deletion also failed: %s" % str(e2))
    else:
        log_message("Rotation offset layer '%s' does not exist (already removed)" % rotation_layer)

def has_namespace(joint_name):
    """Check if a joint name has a namespace."""
    return ":" in joint_name

def get_namespace_from_joint(joint_name):
    """Extract namespace from joint name."""
    if ":" in joint_name:
        return joint_name.split(":")[0]
    return ""

def remove_namespace_from_joint(joint_name):
    """Remove namespace from joint name."""
    if ":" in joint_name:
        return joint_name.split(":")[-1]
    return joint_name

def duplicate_skeleton_without_namespaces(root_joint):
    """
    Duplicate the skeleton hierarchy and remove namespaces from all joint names.
    
    Args:
        root_joint (str): The root joint to duplicate
        
    Returns:
        tuple: (duplicate_root, duplicate_joints_list, original_joints_list)
    """
    duplicate_root = None
    duplicate_joints = []
    original_joints = []
    
    try:
        # Check if the root joint has a namespace
        if not has_namespace(root_joint):
            log_message("Root joint '%s' has no namespace, skipping duplication" % root_joint)
            return None, [], []
            
        log_message("Duplicating skeleton hierarchy from root: %s" % root_joint)
        
        # Select the root joint and all its descendants
        cmds.select(root_joint, hierarchy=True)
        original_joints = get_joints_and_locators(cmds.ls(selection=True, long=True))
        
        if not original_joints:
            log_message("No joints/locators found in hierarchy")
            return None, [], []
            
        log_message("Found %d joints in original hierarchy" % len(original_joints))
        
        # Duplicate the entire hierarchy
        duplicated_nodes = cmds.duplicate(root_joint, renameChildren=True)
        duplicate_root = duplicated_nodes[0]
        
        # Get all joints in the duplicated hierarchy
        cmds.select(duplicate_root, hierarchy=True)
        duplicate_joints = get_joints_and_locators(cmds.ls(selection=True, long=True))
        
        log_message("Duplicated %d joints/locators" % len(duplicate_joints))
        
        # Remove namespaces from all duplicated joints
        renamed_joints = []
        for joint in duplicate_joints:
            try:
                clean_name = remove_namespace_from_joint(joint.split("|")[-1])  # Get short name and remove namespace
                if has_namespace(joint.split("|")[-1]):  # Only rename if it has a namespace
                    new_name = cmds.rename(joint, clean_name)
                    renamed_joints.append(new_name)
                    log_message("Renamed duplicate joint: %s -> %s" % (joint, clean_name))
                else:
                    renamed_joints.append(joint)
            except Exception as e:
                log_message("Could not rename duplicate joint %s: %s" % (joint, str(e)))
                renamed_joints.append(joint)
        
        # Update duplicate_root name if it was renamed
        if renamed_joints:
            duplicate_root = renamed_joints[0]
            
        log_message("Successfully duplicated skeleton without namespaces. Root: %s" % duplicate_root)
        return duplicate_root, renamed_joints, original_joints
        
    except Exception as e:
        log_message("Error duplicating skeleton: %s" % str(e))
        # Clean up any partial duplication
        if duplicate_root and cmds.objExists(duplicate_root):
            try:
                cmds.delete(duplicate_root)
                log_message("Cleaned up failed duplication")
            except:
                pass
        return None, [], []

def constrain_and_bake_skeleton(duplicate_joints, original_joints, start_frame, end_frame):
    """
    Constrain duplicate joints to original joints and bake the animation.
    
    Args:
        duplicate_joints (list): List of duplicate joint names
        original_joints (list): List of original joint names
        start_frame (int): Start frame for baking
        end_frame (int): End frame for baking
    """
    constraints = []
    
    try:
        log_message("Constraining %d duplicate joints to originals" % len(duplicate_joints))
        
        # Create constraints between duplicate and original joints
        for i, (dup_joint, orig_joint) in enumerate(zip(duplicate_joints, original_joints)):
            try:
                # Point constraint for translation
                point_constraint = cmds.pointConstraint(orig_joint, dup_joint, maintainOffset=False)[0]
                constraints.append(point_constraint)
                
                # Orient constraint for rotation
                orient_constraint = cmds.orientConstraint(orig_joint, dup_joint, maintainOffset=False)[0]
                constraints.append(orient_constraint)
                
                # Scale constraint for scale
                scale_constraint = cmds.scaleConstraint(orig_joint, dup_joint, maintainOffset=False)[0]
                constraints.append(scale_constraint)
                
                if i % 10 == 0:  # Log progress every 10 joints
                    log_message("Constrained %d/%d joints" % (i + 1, len(duplicate_joints)))
                    
            except Exception as e:
                log_message("Could not constrain joint %s to %s: %s" % (dup_joint, orig_joint, str(e)))
        
        log_message("Created %d constraints, now setting visibility and baking animation from frame %d to %d" % (len(constraints), start_frame, end_frame))
        
        # Ensure all duplicate joints have visibility set to ON and keyed
        for dup_joint in duplicate_joints:
            try:
                # Set visibility to ON
                cmds.setAttr("%s.visibility" % dup_joint, 1)
                # Key the visibility at both start and end frames to ensure it stays on
                cmds.setKeyframe("%s.visibility" % dup_joint, time=start_frame, value=1)
                cmds.setKeyframe("%s.visibility" % dup_joint, time=end_frame, value=1)
            except Exception as e:
                log_message("Could not set visibility for joint %s: %s" % (dup_joint, str(e)))
        
        log_message("Set visibility ON for all duplicate joints")
        
        # Select all duplicate joints for baking
        cmds.select(duplicate_joints, replace=True)
        
        # Bake animation on duplicate joints
        cmds.bakeResults(
            duplicate_joints,
            time=(start_frame, end_frame),
            simulation=True,
            sampleBy=1,
            disableImplicitControl=True,
            preserveOutsideKeys=True,
            sparseAnimCurveBake=False,
            removeBakedAttributeFromLayer=False,
            removeBakedAnimFromLayer=False,
            bakeOnOverrideLayer=False,
            minimizeRotation=True,
            controlPoints=False,
            shape=True
        )
        
        log_message("Successfully baked animation on duplicate skeleton")
        
        # Delete all constraints
        for constraint in constraints:
            try:
                if cmds.objExists(constraint):
                    cmds.delete(constraint)
            except Exception as e:
                log_message("Could not delete constraint %s: %s" % (constraint, str(e)))
        
        log_message("Deleted %d constraints" % len(constraints))
        
    except Exception as e:
        log_message("Error constraining and baking skeleton: %s" % str(e))
        # Clean up constraints if something went wrong
        for constraint in constraints:
            try:
                if cmds.objExists(constraint):
                    cmds.delete(constraint)
            except:
                pass

def cleanup_duplicate_skeleton(duplicate_root):
    """
    Clean up the duplicate skeleton.
    
    Args:
        duplicate_root (str): The root of the duplicate skeleton to delete
    """
    if duplicate_root and cmds.objExists(duplicate_root):
        try:
            cmds.delete(duplicate_root)
            log_message("Cleaned up duplicate skeleton: %s" % duplicate_root)
        except Exception as e:
            log_message("Could not clean up duplicate skeleton %s: %s" % (duplicate_root, str(e)))

def browse_export_path(*args):
    path = cmds.fileDialog2(dialogStyle=2, fileMode=3)
    if path:
        export_settings["exportPath"] = path[0]
        cmds.textField("pathField", edit=True, text=path[0])
        save_scene_data()
        refresh_ui()  # Update filename preview

def update_clip_value(index, key, value):
    global clip_data
    try:
        if key == "fps":
            # Only allow valid FPS values
            if value not in fps_options:
                cmds.warning("Invalid FPS value: %s. Allowed: %s" % (value, fps_options))
                log_message("Invalid FPS value attempted: %s. Allowed: %s" % (value, fps_options))
                return
        if key == "name":
            # Validate again here in case called from other places
            invalid_chars = set(r'<>:"/\\|?*')
            if not value or not str(value).strip():
                error_msg = "Clip name cannot be empty."
                cmds.warning(error_msg)
                log_message(error_msg)
                return
            if any((c in invalid_chars) for c in value):
                error_msg = "Clip name contains invalid characters: < > : \" / \\ | ? *"
                cmds.warning(error_msg)
                log_message(error_msg)
                return
            if len(value) > 128:
                error_msg = "Clip name is too long (max 128 characters)."
                cmds.warning(error_msg)
                log_message(error_msg)
                return
        if 0 <= index < len(clip_data):
            old_value = clip_data[index].get(key, None)
            clip_data[index][key] = value
            log_message("Clip entry updated: index=%d, key='%s', old_value=%s, new_value=%s" % (index, key, old_value, value))
            if key == "fps":
                refresh_fps_ui(index)
            elif key == "name":
                update_filename_preview()  # Only update preview, do NOT refresh the whole UI
            else:
                refresh_ui()  # Only refresh UI for other keys
    except Exception as e:
        error_msg = "Fatal error updating clip entry: index=%s, key=%s, value=%s\n%s" % (str(index), str(key), str(value), traceback.format_exc())
        cmds.warning(error_msg)
        log_message(error_msg)

def refresh_fps_ui(index):
    """Refresh only the FPS field and filename preview for the given clip index."""
    try:
        # Update the FPS optionMenu for this clip
        fps_menu_name = None
        # The FPS optionMenu is created in refresh_ui as an unnamed widget, so we can't directly address it by name.
        # Instead, update the filename preview and rely on the UI to reflect the new value on next full refresh.
        update_filename_preview()
        # Optionally, you could add more granular UI update logic here if you use named widgets for FPS fields.
        log_message("Refreshed FPS UI for clip index: %d" % index)
    except Exception:
        error_msg = "Error refreshing FPS UI for clip index %s\n%s" % (str(index), traceback.format_exc())
        cmds.warning(error_msg)
        log_message(error_msg)

def update_filename_preview():
    """Update the filename preview text based on the first active clip and current prefix."""
    try:
        if not cmds.text("filenamePreviewText", exists=True):
            log_message("Filename preview text does not exist, skipping update")
            return
        first_active_clip = next((clip for clip in clip_data if clip.get("enabled", False)), None)
        if first_active_clip:
            clip_name = first_active_clip.get("name", "Untitled")
            if not clip_name:
                clip_name = "Untitled"
            # Always get export path from UI when available
            prefix = cmds.textField("prefixField", q=True, text=True) if cmds.textField("prefixField", exists=True) else export_settings["clipPrefix"]
            # IMPORTANT: Always get the export path from the UI text field, not from export_settings
            export_path = cmds.textField("pathField", q=True, text=True) if cmds.textField("pathField", exists=True) else export_settings["exportPath"]
            preview_path = os.path.join(export_path,
                                       prefix + clip_name + ".fbx").replace("\\", "/")
            cmds.text("filenamePreviewText", edit=True, label="Filename Preview: " + preview_path)
            log_message("Real-time filename preview updated: %s" % preview_path)
        else:
            cmds.text("filenamePreviewText", edit=True, label="Filename Preview: No active clips to preview")
            log_message("Real-time filename preview: No active clips")
    except Exception:
        error_msg = "Error updating filename preview:\n%s" % traceback.format_exc()
        log_message(error_msg)

def check_callback(val, i):
    # Commit any active text field value before refreshing UI
    try:
        text_field_name = "clipName%d" % i
        if cmds.textField(text_field_name, exists=True):
            # Get the current text value from the UI
            current_text = cmds.textField(text_field_name, q=True, text=True)
            # Update the clip data with the current text value (this won't trigger refresh)
            if 0 <= i < len(clip_data):
                clip_data[i]["name"] = current_text
                save_scene_data()  # Save the committed text value
                log_message("Committed text field value before checkbox update: index=%d, name='%s'" % (i, current_text))
    except Exception as e:
        log_message("Error committing text field value: %s" % str(e))
    
    update_clip_value(i, "enabled", val)
    update_filename_preview()  # Update preview when enabling/disabling clips

def name_callback(val, i):
    try:
        # Validate the new name: disallow empty, whitespace-only, or problematic characters
        invalid_chars = set(r'<>:"/\\|?*')
        if not val or not val.strip():
            error_msg = "Clip name cannot be empty."
            cmds.warning(error_msg)
            log_message(error_msg)
            return
        if any((c in invalid_chars) for c in val):
            error_msg = "Clip name contains invalid characters: < > : \" / \\ | ? *"
            cmds.warning(error_msg)
            log_message(error_msg)
            return
        # Optionally, limit length
        if len(val) > 128:
            error_msg = "Clip name is too long (max 128 characters)."
            cmds.warning(error_msg)
            log_message(error_msg)
            return
        update_clip_value(i, "name", val)
        update_filename_preview()  # Update preview when clip name changes
    except Exception as e:
        error_msg = "Fatal error during renaming animation clip: %s\n%s" % (str(e), traceback.format_exc())
        cmds.warning(error_msg)
        log_message(error_msg)

def _debounced_update(index, key, value):
    """Debounced update for clip data to prevent UI refresh loops."""
    global clip_data
    try:
        if 0 <= index < len(clip_data):
            clip_data[index][key] = value
            save_scene_data()
            # Defer UI refresh to avoid recursive calls
            def deferred_refresh():
                try:
                    refresh_ui()
                except Exception as e:
                    log_message("Deferred UI refresh failed: %s" % str(e))
            cmds.evalDeferred(deferred_refresh, lowestPriority=True)
    except Exception:
        error_msg = "Error in debounced update for clip %d, key %s:\n%s" % (index, key, traceback.format_exc())
        cmds.warning(error_msg)
        log_message(error_msg)

def start_callback(val, i):
    try:
        # Convert value to integer and update using debounced function
        _debounced_update(i, "start", int(val))
    except ValueError:
        cmds.warning("Invalid start frame value: %s" % val)
        log_message("Invalid start frame value: %s" % val)

def end_callback(val, i):
    try:
        # Convert value to integer and update using debounced function
        _debounced_update(i, "end", int(val))
    except ValueError:
        cmds.warning("Invalid end frame value: %s" % val)
        log_message("Invalid end frame value: %s" % val)

def fps_callback(val, i):
    try:
        fps_int = int(val)
        if fps_int not in fps_options:
            cmds.warning("Invalid FPS value: %s. Allowed: %s" % (val, fps_options))
            log_message("Invalid FPS value attempted in UI: %s. Allowed: %s" % (val, fps_options))
            return
        update_clip_value(i, "fps", fps_int)
    except Exception:
        error_msg = "Error in fps_callback: val=%s, index=%s\n%s" % (str(val), str(i), traceback.format_exc())
        cmds.warning(error_msg)
        log_message(error_msg)

def add_clip(*args):
    global clip_data
    try:
        new_clip = {
            "name": "",
            "start": int(cmds.playbackOptions(q=True, min=True)),
            "end": int(cmds.playbackOptions(q=True, max=True)),
            "exportMesh": True,
            "fps": 30,
            "enabled": False
        }
        clip_data.append(new_clip)
        log_message("Clip entry added: %s" % new_clip)
        refresh_ui()
        save_scene_data()
    except Exception:
        error_msg = "Error adding clip entry:\n%s" % traceback.format_exc()
        cmds.warning(error_msg)
        log_message(error_msg)

def move_clip(index, direction):
    global clip_data
    try:
        new_i = index + direction
        if 0 <= new_i < len(clip_data) and 0 <= index < len(clip_data):
            clip_data[index], clip_data[new_i] = clip_data[new_i], clip_data[index]
            log_message("Clip entry moved: from index %d to %d" % (index, new_i))
            refresh_ui()
            save_scene_data()
    except Exception:
        error_msg = "Error moving clip entry: from index %s, direction %s\n%s" % (str(index), str(direction), traceback.format_exc())
        cmds.warning(error_msg)
        log_message(error_msg)

def delete_clip(index):
    global clip_data
    try:
        if 0 <= index < len(clip_data):
            removed_clip = clip_data[index]
            clip_data.pop(index)
            log_message("Clip entry deleted: index=%d, entry=%s" % (index, removed_clip))
            refresh_ui()
            save_scene_data()
    except Exception:
        error_msg = "Error deleting clip entry: index=%s\n%s" % (str(index), traceback.format_exc())
        cmds.warning(error_msg)
        log_message(error_msg)

def get_current_clip_name(index):
    try:
        if 0 <= index < len(clip_data):
            textfield_name = "clipName%d" % index
            if cmds.textField(textfield_name, exists=True):
                return cmds.textField(textfield_name, q=True, text=True)
    except:
        pass
    if 0 <= index < len(clip_data):
        return clip_data[index].get("name", "")
    return ""

def duplicate_clip(index):
    global clip_data
    try:
        if not (0 <= index < len(clip_data)):
            cmds.warning("Invalid clip index: %d" % index)
            return
        source_clip = clip_data[index].copy()
        current_name = get_current_clip_name(index)
        new_clip = {}
        for key, value in source_clip.items():
            if value is not None:
                new_clip[key] = value
        if current_name:
            new_clip["name"] = current_name + "_copy"
        elif source_clip.get("name"):
            new_clip["name"] = source_clip["name"] + "_copy"
        else:
            new_clip["name"] = "Copy"
        if "start" not in new_clip:
            new_clip["start"] = int(cmds.playbackOptions(q=True, min=True))
        if "end" not in new_clip:
            new_clip["end"] = int(cmds.playbackOptions(q=True, max=True))
        if "fps" not in new_clip:
            new_clip["fps"] = 30
        if "enabled" not in new_clip:
            new_clip["enabled"] = False
        if "exportMesh" not in new_clip:
            new_clip["exportMesh"] = True
        clip_data.insert(index+1, new_clip)
        log_message("Clip entry duplicated: from index %d to %d, entry=%s" % (index, index+1, new_clip))
        refresh_ui()
        save_scene_data()
    except Exception:
        error_msg = "Error duplicating clip entry: index=%s\n%s" % (str(index), traceback.format_exc())
        cmds.warning(error_msg)
        log_message(error_msg)

def check_all_clips(*args):
    global clip_data
    try:
        for idx, c in enumerate(clip_data):
            c["enabled"] = True
            log_message("Clip entry enabled: index=%d, entry=%s" % (idx, c))
        refresh_ui()
        save_scene_data()
    except Exception:
        error_msg = "Error enabling all clip entries:\n%s" % traceback.format_exc()
        cmds.warning(error_msg)
        log_message(error_msg)

def uncheck_all_clips(*args):
    global clip_data
    try:
        for idx, c in enumerate(clip_data):
            c["enabled"] = False
            log_message("Clip entry disabled: index=%d, entry=%s" % (idx, c))
        refresh_ui()
        save_scene_data()
    except Exception:
        error_msg = "Error disabling all clip entries:\n%s" % traceback.format_exc()
        cmds.warning(error_msg)
        log_message(error_msg)

def confirm_overwrite(file_path):
    global overwrite_all, skip_all
    if overwrite_all:
        return True
    if skip_all:
        return False
    if os.path.exists(file_path):
        # Show the full file path (with prefix) in the dialog
        result = cmds.confirmDialog(
            title='Confirm Overwrite',
            message='The file already exists:\n\n%s\n\nOverwrite?' % file_path,
            button=['Overwrite', 'Overwrite All', 'Skip', 'Skip All', 'Cancel'],
            defaultButton='Overwrite',
            cancelButton='Cancel',
            dismissString='Cancel'
        )
        if result == 'Overwrite':
            return True
        elif result == 'Overwrite All':
            overwrite_all = True
            return True
        elif result == 'Skip':
            return False
        elif result == 'Skip All':
            skip_all = True
            return False
        else:
            raise Exception("Export cancelled by user.")
    return True

def set_fbx_export_settings(adjusted_start, adjusted_end, fbx_version, is_ascii=False):
    log_message("Setting FBX export options...")
    try:
        mel.eval("FBXResetExport;")
        log_message("Reset FBX export settings")
    except Exception as e:
        log_message("Warning: Failed to reset FBX export settings: %s" % str(e))
    success = True
    try:
        mel.eval("FBXExportBakeComplexAnimation -v true;")
        mel.eval("FBXExportBakeComplexStep -v 1;")
        mel.eval("FBXExportBakeResampleAnimation -v true;")
        mel.eval("FBXExportBakeComplexStart -v %d;" % adjusted_start)
        mel.eval("FBXExportBakeComplexEnd -v %d;" % adjusted_end)
        mel.eval("FBXExportSkins -v true;")
        mel.eval("FBXExportShapes -v true;")
        mel.eval("FBXExportApplyConstantKeyReducer -v false;")
        mel.eval("FBXExportConstraints -v %s;" % ("true" if export_settings.get("constraints", False) else "false"))
        mel.eval("FBXExportSkeletonDefinitions -v true;")
        mel.eval("FBXExportCameras -v true;")
        mel.eval("FBXExportLights -v true;")
        mel.eval("FBXExportEmbeddedTextures -v true;")
        mel.eval("FBXExportIncludeChildren -v %s;" % ("true" if export_settings.get("includeChildren", True) else "false"))
        mel.eval("FBXExportInputConnections -v %s;" % ("true" if export_settings.get("inputConnections", False) else "false"))
        mel.eval("FBXExportInAscii -v %d;" % (1 if is_ascii else 0))
        mel.eval("FBXExportFileVersion -v FBX%s00;" % fbx_version)
        mel.eval("FBXExportScaleFactor 1.0;")
        mel.eval("FBXExportUseSceneName -v false;")
        mel.eval("FBXExportQuaternion -v euler;")
        mel.eval("FBXExportAxisConversionMethod none;")
        mel.eval("FBXExportUpAxis y;")
        log_message("FBX export settings configured successfully")
    except Exception as e:
        log_message("Error setting FBX export options: %s" % str(e))
        success = False
    return success

def select_export_subset(joints_to_export):
    """
    Select the export subset - all specified joints and optionally their hierarchies.
    
    Args:
        joints_to_export: Single joint/locator string OR list of joints/locators to export
    """
    try:
        # Handle both single joint and list of joints
        if isinstance(joints_to_export, str):
            joints_to_export = [joints_to_export]
        
        # Select all specified joints
        all_selected = []
        for joint in joints_to_export:
            if cmds.objExists(joint):
                # Select this joint and its hierarchy
                cmds.select(joint, hierarchy=True, add=True if all_selected else False)
                hierarchy = cmds.ls(selection=True, long=True)
                for item in hierarchy:
                    if item not in all_selected:
                        all_selected.append(item)
        
        # Make sure all joints are selected
        if all_selected:
            cmds.select(all_selected, replace=True)
        
        selected = cmds.ls(selection=True, long=True)
        log_message("Selected export subset: %d root joints, %d total objects" % (len(joints_to_export), len(selected)))
        
        # Check if verbose logging is enabled
        verbose = is_verbose_logging_enabled()
        if verbose:
            log_message("[VERBOSE] ===== JOINT HIERARCHY FOR EXPORT =====")
            joints = cmds.ls(selection=True, type="joint")
            log_message("[VERBOSE] Total joints selected: %d" % len(joints))
            for i, joint in enumerate(joints):
                short_name = joint.split("|")[-1]
                # Get animation data info
                anim_curves = cmds.listConnections(joint, type="animCurve") or []
                # Get transform values
                try:
                    tx, ty, tz = cmds.getAttr(joint + ".translate")[0]
                    rx, ry, rz = cmds.getAttr(joint + ".rotate")[0]
                    log_message("[VERBOSE] %3d. %s" % (i+1, short_name))
                    log_message("[VERBOSE]      Trans: (%.3f, %.3f, %.3f)  Rot: (%.3f, %.3f, %.3f)" % (tx, ty, tz, rx, ry, rz))
                    log_message("[VERBOSE]      Anim curves: %d" % len(anim_curves))
                    if anim_curves:
                        for curve in anim_curves[:5]:  # Show first 5 curves
                            curve_type = cmds.nodeType(curve)
                            key_count = cmds.keyframe(curve, query=True, keyframeCount=True) or 0
                            log_message("[VERBOSE]        - %s (%s, %d keys)" % (curve, curve_type, key_count))
                        if len(anim_curves) > 5:
                            log_message("[VERBOSE]        ... and %d more curves" % (len(anim_curves) - 5))
                except Exception as je:
                    log_message("[VERBOSE] %3d. %s (error reading attrs: %s)" % (i+1, short_name, str(je)))
            log_message("[VERBOSE] =========================================")
    except Exception as e:
        log_message("Error selecting export subset: %s" % str(e))


def is_verbose_logging_enabled():
    """Check if verbose logging is enabled in export process settings."""
    try:
        script_path = find_export_process_script()
        if script_path:
            if sys.version_info[0] >= 3:
                import importlib.util
                spec = importlib.util.spec_from_file_location("HaxExporterSettings", script_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module.is_verbose_logging_enabled()
            else:
                import imp
                module = imp.load_source('HaxExporterSettings', script_path)
                return module.is_verbose_logging_enabled()
    except:
        pass
    return False

def export_selected_clips():
    global clip_data, overwrite_all, skip_all
    # Extra robust: Force text fields to lose focus to ensure values are committed
    try:
        cmds.setFocus("pathField")
        cmds.setFocus("prefixField")
        cmds.setFocus("mainColumn")  # Move focus away
    except Exception:
        pass
    # Get current UI values for export path and prefix
    if cmds.textField("pathField", exists=True):
        export_settings["exportPath"] = cmds.textField("pathField", q=True, text=True)
    if cmds.textField("prefixField", exists=True):
        export_settings["clipPrefix"] = cmds.textField("prefixField", q=True, text=True)
    overwrite_all = False
    skip_all = False
    selected = [c for c in clip_data if c.get("enabled", False)]
    if not selected:
        cmds.warning("No clips selected for export.")
        log_message("No clips selected for export.")
        return
    export_clips(selected)

def anim_layer_states_match():
    for l, checked in anim_layer_checkboxes.items():
        if l == "Base Animation":
            continue
        if cmds.objExists(l):
            try:
                current = not bool(cmds.getAttr(l + ".mute"))
                if current != checked:
                    return False
            except Exception:
                continue
    return True

def bake_joints_animation(root_joint, start_frame, end_frame):
    """
    Bake animation on all joints in the hierarchy by keying them on every frame.
    This is useful for baking constraint-driven animations into keyframes.
    
    Args:
        root_joint (str): The root joint of the hierarchy to bake
        start_frame (int): Start frame for baking
        end_frame (int): End frame for baking
    """
    try:
        log_message("Baking animation for joint hierarchy starting from: %s" % root_joint)
        log_message("Frame range: %d to %d" % (start_frame, end_frame))
        
        # Select the root and all its descendants
        cmds.select(root_joint, hierarchy=True)
        joints_to_bake = get_joints_and_locators(cmds.ls(selection=True, long=True))
        
        if not joints_to_bake:
            log_message("No joints found to bake")
            return
        
        log_message("Found %d joints/locators to bake" % len(joints_to_bake))
        
        # Bake animation on all joints
        cmds.bakeResults(
            joints_to_bake,
            time=(start_frame, end_frame),
            simulation=True,
            sampleBy=1,
            disableImplicitControl=True,
            preserveOutsideKeys=True,
            sparseAnimCurveBake=False,
            removeBakedAttributeFromLayer=False,
            removeBakedAnimFromLayer=False,
            bakeOnOverrideLayer=False,
            minimizeRotation=True,
            controlPoints=False,
            shape=True
        )
        
        log_message("Successfully baked animation on %d joints" % len(joints_to_bake))
        
    except Exception as e:
        error_msg = "Error baking joints animation: %s" % str(e)
        log_message(error_msg)
        cmds.warning(error_msg)

def export_clips(targets=None):
    global clip_data, overwrite_all, skip_all
    # Extra robust: Force text fields to lose focus to ensure values are committed
    try:
        cmds.setFocus("pathField")
        cmds.setFocus("prefixField")
        cmds.setFocus("mainColumn")  # Move focus away
    except Exception:
        pass
    # Get current UI values for export path and prefix
    if cmds.textField("pathField", exists=True):
        export_settings["exportPath"] = cmds.textField("pathField", q=True, text=True)
    if cmds.textField("prefixField", exists=True):
        export_settings["clipPrefix"] = cmds.textField("prefixField", q=True, text=True)
    overwrite_all = False
    skip_all = False
    save_scene_data()
    if targets is None:
        targets = clip_data
    if not targets:
        cmds.warning("No clips to export.")
        log_message("No clips to export.")
        return
    orig_unit = cmds.currentUnit(q=True, time=True)
    orig_min = cmds.playbackOptions(q=True, min=True)
    orig_max = cmds.playbackOptions(q=True, max=True)
    orig_selection = cmds.ls(selection=True)
    log_message("\n==== STARTING EXPORT SESSION ====\n")
    log_message("Original settings - Unit: %s, Range: %d-%d" % (orig_unit, orig_min, orig_max))
    log_message("Clips to process: %d" % len(targets))
    # --- Animation Layer Muting ---
    if anim_layer_states_match():
        orig_anim_layer_states = None  # No need to restore
        log_message("All anim layers already in correct mute/unmute state; skipping muting/unmuting and pause.")
    else:
        orig_anim_layer_states = get_anim_layer_states()
        log_message("Original anim layer mute states: %s" % orig_anim_layer_states)
        set_anim_layer_states(anim_layer_checkboxes)
        log_message("Set anim layer mute states for export: %s" % anim_layer_checkboxes)
        try:
            cmds.refresh(force=True)
            time.sleep(0.05)  # Give Maya time to recalculate
        except Exception:
            pass
    # --- Restore root joint selection logic ---
    sel = get_joints_and_locators()
    root = None
    namespace = None
    try:
        if 'get_selected_namespace' in globals():
            namespace = get_selected_namespace()
    except Exception as e:
        log_message("Error checking selected namespace: %s" % str(e))
    # joints_for_export will hold all joints to be exported
    joints_for_export = []
    
    if sel:
        # If joints/locators are explicitly selected, use them regardless of namespace
        valid_joints = [j for j in sel if cmds.objExists(j)]
        if valid_joints:
            joints_for_export = valid_joints
            root = valid_joints[0]  # Keep root for compatibility
            log_message("Using %d selected joints/locators" % len(joints_for_export))
            log_message("User has joints/locators selected - ignoring namespace filtering and preset joints")
    else:
        current_preset = cmds.optionMenu("presetDropdown", q=True, value=True) if cmds.optionMenu("presetDropdown", exists=True) else "<None>"
        if current_preset != "<None>":
            # Use skip_path_update=True to preserve all current settings during export
            preset_joints = load_preset(current_preset, skip_path_update=True)
            log_message("Loaded preset with %d joints" % len(preset_joints))
            # Filter for existing joints and locators
            existing_joints = [j for j in preset_joints if cmds.objExists(j)]
            valid_joints = get_joints_and_locators(existing_joints)
            if namespace:
                try:
                    if 'filter_joints_by_namespace' in globals():
                        valid_joints = filter_joints_by_namespace(valid_joints, namespace)
                except Exception as e:
                    log_message("Error filtering preset joints by namespace: %s" % str(e))
            if valid_joints:
                joints_for_export = valid_joints  # Use ALL preset joints
                root = valid_joints[0]  # Keep root for compatibility
                log_message("Using %d joints from preset '%s'" % (len(joints_for_export), current_preset))
    
    if not joints_for_export:
        error_message = "Select a root joint or locator before exporting."
        cmds.warning(error_message)
        cmds.confirmDialog(
            title="Export Error",
            message=error_message,
            button=["OK"],
            defaultButton="OK",
            cancelButton="OK",
            dismissString="OK"
        )
        log_message("ERROR: No root joint/locator selected. Select a root joint or locator before exporting.")
        return
    log_message("Using root joint/locator: %s" % root)
    successful_exports = 0
    exported_fbx_paths = []  # Track successfully exported FBX paths for Skyrim conversion
    try:
        clips_to_export = []
        log_message("\n-- Checking export paths for existing files --")
        for clip in targets:
            try:
                clip_name = clip.get("name", "Untitled")
                if not clip_name:
                    clip_name = "Untitled"
                # Always get the current path from UI when available
                current_path = cmds.textField("pathField", q=True, text=True) if cmds.textField("pathField", exists=True) else export_settings["exportPath"]
                # Construct filename with prefix before overwrite check
                out_path = os.path.join(current_path,
                                       export_settings["clipPrefix"] + clip_name + ".fbx").replace("\\", "/")
                log_message("Applied prefix '%s' to filename: %s (before overwrite check)" % (export_settings["clipPrefix"], os.path.basename(out_path)))
                log_message("Checking if file exists: %s" % out_path)
                if os.path.exists(out_path):
                    log_message("  File exists: %s" % out_path)
                if not confirm_overwrite(out_path):
                    log_message("  Skipping export of '%s' as per user request." % clip_name)
                    continue
                export_dir = os.path.dirname(out_path)
                if not os.path.exists(export_dir):
                    os.makedirs(export_dir)
                    log_message("  Created directory: %s" % export_dir)
                clips_to_export.append((clip, out_path))
                log_message("  Will export: %s" % out_path)
            except Exception as e:
                if str(e) == "Export cancelled by user.":
                    log_message("Export process cancelled by user.")
                    return
                else:
                    error_msg = "Error checking file: %s:\n%s" % (clip.get("name", ""), traceback.format_exc())
                    cmds.warning(error_msg)
                    log_message(error_msg)
        if not clips_to_export:
            log_message("No clips to export after overwrite checks.")
            return
        log_message("\n-- Starting export of %d clips --" % len(clips_to_export))
        for i, (clip, out_path) in enumerate(clips_to_export):
            try:
                start_time = time.time()
                clip_name = clip.get("name", "Untitled")
                log_message("\nExporting clip %d/%d: '%s'" % (i+1, len(clips_to_export), clip_name))
                start = clip.get("start", 1)
                end = clip.get("end", 24)
                clip_fps = clip.get("fps", 30)
                fbx_version = export_settings["fbxVersion"]
                is_ascii = export_settings["fileType"] == "ASCII"
                scale_factor = float(clip_fps) / 30
                adjusted_start = int(start * scale_factor)
                adjusted_end = int(end * scale_factor)
                log_message("FPS: %d, FBX version: FBX%s00" % (clip_fps, fbx_version))
                log_message("Original range: %d-%d, Adjusted range: %d-%d (scale: %.2f)" % (
                    start, end, adjusted_start, adjusted_end, scale_factor))
                cmds.currentUnit(time="%dfps" % clip_fps)
                cmds.playbackOptions(min=adjusted_start, max=adjusted_end)
                force_ui_refresh()
                
                # Apply rotation offset if enabled (key on the first frame of export range)
                rotation_layer = apply_rotation_offset(adjusted_start)
                
                # Ensure rotation offset is fully processed before continuing
                if rotation_layer:
                    log_message("Rotation offset layer applied, ensuring Maya processes it before export")
                    cmds.refresh(force=True)
                
                pos_rot_anim = None
                alt_root = export_settings.get("altRootControl", "")
                use_alt_root = alt_root and cmds.objExists(alt_root)
                if export_settings["moveToOrigin"]:
                    root_for_origin = alt_root if use_alt_root else root
                    # Always use animation layer for Move to Origin
                    pos_rot_anim = move_to_origin(root_for_origin, use_anim_layer=True)
                    log_message("Moved %s to origin using additive animation layer" % root_for_origin)
                # Bake from constraints if enabled (before namespace removal)
                if export_settings.get("bakeFromConstraints", False):
                    log_message("Bake from Constraints enabled - baking animation on joints")
                    bake_joints_animation(root, adjusted_start, adjusted_end)
                
                # Handle namespace removal if enabled
                duplicate_root = None
                duplicate_joints = []
                original_joints = []
                original_root = root
                
                # Determine what joints to export
                export_joints = joints_for_export if joints_for_export else [root]
                
                if export_settings.get("removeNamespaces", False) and has_namespace(root):
                    log_message("Remove Namespaces enabled - creating duplicate skeleton")
                    duplicate_root, duplicate_joints, original_joints = duplicate_skeleton_without_namespaces(root)
                    
                    if duplicate_root:
                        # Constrain and bake the duplicate skeleton
                        constrain_and_bake_skeleton(duplicate_joints, original_joints, adjusted_start, adjusted_end)
                        
                        # Use the duplicate skeleton for export
                        export_joints = [duplicate_root]  # Use duplicate root with hierarchy
                        root = duplicate_root
                        log_message("Using duplicate skeleton for export: %s" % root)
                    else:
                        log_message("Failed to create duplicate skeleton, using original")
                
                select_export_subset(export_joints)
                log_message("Selected %d joints for export" % len(cmds.ls(selection=True)))
                set_fbx_export_settings(adjusted_start, adjusted_end, fbx_version, is_ascii)
                export_details = []
                export_details.append("Bake Animation: ON")
                export_details.append("Resample All: ON")
                export_details.append("Bake Range: %d-%d" % (adjusted_start, adjusted_end))
                export_details.append("Skins: ON")
                export_details.append("Blend Shapes: ON")
                export_details.append("Skeleton Definitions: ON")
                export_details.append("Cameras: ON")
                export_details.append("Lights: ON")
                export_details.append("Embed Media: ON")
                export_details.append("Include Children: %s" % ("ON" if export_settings.get("includeChildren", True) else "OFF"))
                export_details.append("Input Connections: %s" % ("ON" if export_settings.get("inputConnections", False) else "OFF"))
                export_details.append("Constraints: %s" % ("ON" if export_settings.get("constraints", False) else "OFF"))
                export_details.append("Bake from Constraints: %s" % ("ON" if export_settings.get("bakeFromConstraints", False) else "OFF"))
                log_message("Export configuration:\n- " + "\n- ".join(export_details))
                log_message("Starting export to: %s" % out_path)
                cmds.optionVar(stringValue=["out_path_temp", out_path])
                force_ui_refresh()
                export_success = False
                try:
                    export_cmd = 'FBXExport -f "%s" -s;' % out_path
                    log_message("Using MEL command: %s" % export_cmd)
                    mel.eval(export_cmd)
                    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                        log_message("FBX file created successfully: %s" % out_path)
                        export_success = True
                    else:
                        log_message("Warning: FBXExport completed but no file was created")
                        raise Exception("File not created by primary export method")
                except Exception as e:
                    log_message("Primary export failed: %s" % str(e))
                    try:
                        log_message("Trying alternative export methods...")
                        select_export_subset(export_joints)
                        cmds.file(
                            out_path,
                            force=True,
                            options="v=0",
                            type="FBX export",
                            preserveReferences=False,
                            exportSelected=True
                        )
                        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                            log_message("FBX file created successfully by cmds.file method")
                            export_success = True
                        else:
                            log_message("Warning: cmds.file export completed but no file was created")
                            raise Exception("File not created by cmds.file method")
                    except Exception as alt_err:
                        log_message("Alternative cmds.file export failed: %s" % str(alt_err))
                        _try_alternative_export_fn()
                        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                            log_message("FBX file created successfully by final backup method")
                            export_success = True
                        else:
                            log_message("All export methods failed to create file")
                            raise Exception("All export methods failed")
                force_ui_refresh()
                if export_success:
                    end_time = time.time()
                    duration = end_time - start_time
                    log_message("Export completed successfully! (%.2f seconds)" % duration)
                    successful_exports += 1
                    exported_fbx_paths.append(out_path)  # Track for Skyrim conversion
                else:
                    log_message("Export failed - file was not created")
                    raise Exception("Export failed - file was not created")
                if export_settings["moveToOrigin"] and pos_rot_anim is not None:
                    root_for_origin = alt_root if use_alt_root else root
                    restore_position(root_for_origin, pos_rot_anim)
                    log_message("Restored %s position" % root_for_origin)
                
                # Remove rotation offset layer
                if rotation_layer:
                    remove_rotation_offset(rotation_layer)
                
                # Clean up duplicate skeleton if it was created
                if duplicate_root:
                    cleanup_duplicate_skeleton(duplicate_root)
                
                log_message("Clip '%s' exported successfully" % clip_name)
            except Exception:
                # Clean up rotation offset layer if it exists
                if 'rotation_layer' in locals() and rotation_layer:
                    remove_rotation_offset(rotation_layer)
                
                # Clean up duplicate skeleton if it was created
                if 'duplicate_root' in locals() and duplicate_root:
                    cleanup_duplicate_skeleton(duplicate_root)
                
                error_msg = "Error exporting clip %s:\n%s" % (clip.get("name", ""), traceback.format_exc())
                cmds.warning(error_msg)
                log_message(error_msg)
    finally:
        if orig_anim_layer_states is not None:
            log_message("Restoring original anim layer mute states: %s" % orig_anim_layer_states)
            set_anim_layer_states(orig_anim_layer_states)
            try:
                cmds.refresh(force=True)
                time.sleep(0.05)
            except Exception:
                pass
        log_message("\n==== Export process complete ====")
        log_message("Restoring original settings - Unit: %s, Range: %d-%d" % (orig_unit, orig_min, orig_max))
        try:
            force_ui_refresh()
            cmds.currentUnit(time=orig_unit)
            cmds.playbackOptions(min=orig_min, max=orig_max)
            force_ui_refresh()
            current_unit = cmds.currentUnit(q=True, time=True)
            current_min = cmds.playbackOptions(q=True, min=True)
            current_max = cmds.playbackOptions(q=True, max=True)
            log_message("Verified restored settings - Unit: %s, Range: %d-%d" % (current_unit, current_min, current_max))
            if cmds.optionVar(exists="out_path_temp"):
                cmds.optionVar(remove="out_path_temp")
            if orig_selection:
                cmds.select(orig_selection)
            else:
                cmds.select(clear=True)
            force_ui_refresh()
            log_message("All settings restored. Export complete.\n")
            # Show confirmation popup with random anime quote if at least one export succeeded
            if successful_exports > 0:
                quote = random.choice(anime_quotes)
                cmds.confirmDialog(
                    title="Export Complete!",
                    message="All exports completed successfully!\n\n" + quote,
                    button=["OK"],
                    defaultButton="OK",
                    cancelButton="OK",
                    dismissString="OK"
                )
                
                # Run Skyrim HKX conversion if enabled
                if exported_fbx_paths:
                    log_message("Checking for Skyrim HKX conversion...")
                    run_skyrim_conversion(exported_fbx_paths)
        except Exception as e:
            log_message("Error during restoration: %s" % str(e))
            log_message("Try refreshing the UI manually if Maya seems unresponsive.")
        # In export_clips, before exporting:
        orig_anim_layer_states = get_anim_layer_states()
        set_anim_layer_states(anim_layer_checkboxes)
        # After export (in finally block), restore original states:
        set_anim_layer_states(orig_anim_layer_states)

def set_clip_timeline(index):
    """Set Maya's timeline to match this clip's frame range."""
    global clip_data
    if 0 <= index < len(clip_data):
        try:
            s = cmds.intField("startField%d" % index, q=True, v=True)
            e = cmds.intField("endField%d" % index, q=True, v=True)
            update_clip_value(index, "start", s)
            update_clip_value(index, "end", e)
            cmds.playbackOptions(min=s, max=e)
            save_scene_data()
        except Exception:
            error_msg = "Could not set timeline for clip %d:\n%s" % (index, traceback.format_exc())
            cmds.warning(error_msg)

def get_clip_timeline(index):
    """Get current timeline frame range and set it as the animation clip's frame range."""
    global clip_data
    if 0 <= index < len(clip_data):
        try:
            current_start = int(cmds.playbackOptions(q=True, min=True))
            current_end = int(cmds.playbackOptions(q=True, max=True))
            
            # Update the UI fields
            cmds.intField("startField%d" % index, edit=True, value=current_start)
            cmds.intField("endField%d" % index, edit=True, value=current_end)
            
            # Update the clip data
            update_clip_value(index, "start", current_start)
            update_clip_value(index, "end", current_end)
            save_scene_data()
            
            log_message("Got timeline range for clip %d: %d-%d" % (index, current_start, current_end))
        except Exception:
            error_msg = "Could not get timeline for clip %d:\n%s" % (index, traceback.format_exc())
            cmds.warning(error_msg)
            log_message(error_msg)

def play_clip(index):
    if 0 <= index < len(clip_data):
        set_clip_timeline(index)
        cmds.play(forward=True)

def move_up(index):
    move_clip(index, -1)

def move_down(index):
    move_clip(index, 1)

def delete_callback(index):
    delete_clip(index)

def import_data_command(*args):
    """Show import options and handle user selection."""
    try:
        # Add tooltips to the confirmDialog by including them in the message
        result = cmds.confirmDialog(
            title='Import Animation Data',
            message='Select import source:\n\nMaya Game Exporter: Import animation clips from Maya\'s built-in Game Exporter.\nText File: Import animation clips from a previously exported text file.',
            button=['Maya Game Exporter', 'Text File', 'Cancel'],
            defaultButton='Maya Game Exporter',
            cancelButton='Cancel',
            dismissString='Cancel'
        )
        if result == 'Maya Game Exporter':
            if not has_native_exporter_data():
                cmds.warning("No Maya Game Exporter data found in the scene.")
                log_message("No Maya Game Exporter data found for import.")
                return
            confirm = cmds.confirmDialog(
                title='Import Maya Game Exporter Data',
                message='Importing will replace all current animation clip entries with data from Maya\'s native Game Exporter.\n\nContinue?\n\nTip: This will overwrite your current clip list with the clips defined in the Maya Game Exporter.',
                button=['Import', 'Cancel'],
                defaultButton='Import',
                cancelButton='Cancel',
                dismissString='Cancel'
            )
            if confirm == 'Import':
                load_game_exporter_metadata()
                refresh_ui()
                log_message("Imported Maya Game Exporter data, replaced existing clip entries.")
                cmds.inViewMessage(amg="Imported Maya Game Exporter data.", pos='topCenter', fade=True)
            else:
                log_message("Import of Maya Game Exporter data cancelled by user.")
        elif result == 'Text File':
            file_path = cmds.fileDialog2(
                dialogStyle=2,
                fileMode=1,
                fileFilter="Text Files (*.txt);;All Files (*.*)",
                caption="Import Animation Clip Data"
            )
            if file_path and len(file_path) > 0:
                confirm = cmds.confirmDialog(
                    title='Import Text Data',
                    message='Importing will replace all current animation clip entries with data from the selected file.\n\nContinue?\n\nTip: The text file should be exported from this tool and follow the expected format.',
                    button=['Import', 'Cancel'],
                    defaultButton='Import',
                    cancelButton='Cancel',
                    dismissString='Cancel'
                )
                if confirm == 'Import':
                    success = import_text_data(file_path[0])
                    if success:
                        cmds.inViewMessage(amg="Imported animation clip data from text file.", pos='topCenter', fade=True)
                else:
                    log_message("Import from text file cancelled by user.")
    except Exception:
        error_msg = "Error in import data command:\n%s" % traceback.format_exc()
        cmds.warning(error_msg)
        log_message(error_msg)

def load_game_exporter_metadata():
    global clip_data, scene_data_loaded, export_settings
    try:
        clip_data[:] = []
        nodes = cmds.ls(type=EXPORTER_NODE_TYPE)
        if not nodes:
            print("No Maya Game Exporter nodes (gameFbxExporter) found.")
            scene_data_loaded = True
            return False
        print("Found %d Maya Game Exporter nodes: %s" % (len(nodes), nodes))
        imported_count = 0
        export_path = None
        export_filename = None
        for node in nodes:
            try:
                attrs = cmds.listAttr(node, userDefined=True)
                if not attrs:
                    attrs = cmds.listAttr(node) or []
                print("Attributes for node %s: %s" % (node, attrs))
                print("String-type attributes for %s:" % node)
                for attr in attrs:
                    if cmds.attributeQuery(attr, node=node, exists=True):
                        try:
                            attr_type = cmds.attributeQuery(attr, node=node, attributeType=True)
                            if attr_type in ["string", "TdataCompound"]:
                                value = cmds.getAttr("%s.%s" % (node, attr))
                                print("  %s: %s (type: %s)" % (attr, value, type(value)))
                        except:
                            pass
                path_candidates = ["exportPath", "filePath", "path", "exportDirectory", "presetName", "selectionSetName"]
                for attr in path_candidates:
                    if cmds.attributeQuery(attr, node=node, exists=True):
                        try:
                            value = cmds.getAttr("%s.%s" % (node, attr))
                            print("Checking path candidate %s: %s (type: %s)" % (attr, value, type(value)))
                            if isinstance(value, str) and value.strip() and "/" in value:
                                export_path = value
                                print("Assigned exportPath from %s: %s" % (attr, export_path))
                                break
                        except Exception as e:
                            print("Error retrieving %s for %s: %s" % (attr, node, str(e)))
                prefix_candidates = ["exportFilename", "filePrefix", "prefix", "filename", "presetName", "selectionSetName"]
                for attr in prefix_candidates:
                    if cmds.attributeQuery(attr, node=node, exists=True):
                        try:
                            value = cmds.getAttr("%s.%s" % (node, attr))
                            print("Checking prefix candidate %s: %s (type: %s)" % (attr, value, type(value)))
                            if isinstance(value, str) and value.strip():
                                export_filename = value
                                print("Assigned exportFilename from %s: %s" % (attr, export_filename))
                                break
                        except Exception as e:
                            print("Error retrieving %s for %s: %s" % (attr, node, str(e)))
                if cmds.attributeQuery("useFilenameAsPrefix", node=node, exists=True):
                    try:
                        value = cmds.getAttr("%s.useFilenameAsPrefix" % node)
                        print("useFilenameAsPrefix: %s (type: %s)" % (value, type(value)))
                    except Exception as e:
                        print("Error retrieving useFilenameAsPrefix for %s: %s" % (node, str(e)))
                if cmds.attributeQuery("animClips", node=node, exists=True):
                    clip_count = cmds.getAttr(node + ".animClips", size=True)
                    print("Node %s has %d clips" % (node, clip_count))
                    for i in range(clip_count):
                        try:
                            clip_name = cmds.getAttr("%s.animClips[%d].animClipName" % (node, i))
                            start_frame = cmds.getAttr("%s.animClips[%d].animClipStart" % (node, i))
                            end_frame = cmds.getAttr("%s.animClips[%d].animClipEnd" % (node, i))
                            fps = 30  # Default FPS
                            # If the node has a per-clip FPS attribute, try to get it and validate
                            try:
                                if cmds.attributeQuery("animClipFps", node=node, exists=True):
                                    fps_val = cmds.getAttr("%s.animClips[%d].animClipFps" % (node, i))
                                    if isinstance(fps_val, int) and fps_val in fps_options:
                                        fps = fps_val
                                    else:
                                        cmds.warning("Invalid FPS value in Maya Game Exporter: %s. Allowed: %s. Defaulting to 30." % (fps_val, fps_options))
                                        log_message("Invalid FPS value in Maya Game Exporter: %s. Defaulting to 30." % fps_val)
                            except:
                                pass
                            clip = {
                                "name": clip_name,
                                "start": int(start_frame),
                                "end": int(end_frame),
                                "exportMesh": True,
                                "fps": fps,
                                "enabled": True
                            }
                            clip_data.append(clip)
                            log_message("Clip entry imported from Maya Game Exporter: index=%d, entry=%s" % (len(clip_data)-1, clip))
                            imported_count += 1
                            print("Imported clip '%s' from node '%s' (Frames %d-%d)" % (
                                clip_name, node, start_frame, end_frame))
                        except Exception:
                            error_msg = "Error importing clip from Maya Game Exporter: node=%s, index=%s\n%s" % (str(node), str(i), traceback.format_exc())
                            cmds.warning(error_msg)
                            log_message(error_msg)
                else:
                    print("Node %s does not have 'animClips' attribute" % node)
                if cmds.attributeQuery("message", node=node, exists=True):
                    connections = cmds.listConnections("%s.message" % node, source=False, destination=True) or []
                    print("Connections from %s.message: %s" % (node, connections))
                    for conn in connections:
                        conn_attrs = cmds.listAttr(conn, string="file*") or []
                        for attr in conn_attrs:
                            try:
                                value = cmds.getAttr("%s.%s" % (conn, attr))
                                print("Connected node %s.%s: %s (type: %s)" % (conn, attr, value, type(value)))
                                if isinstance(value, str) and value.strip() and "/" in value and not export_path:
                                    export_path = value
                                    print("Assigned exportPath from connected %s.%s: %s" % (conn, attr, export_path))
                                elif isinstance(value, str) and value.strip() and not export_filename:
                                    export_filename = value
                                    print("Assigned exportFilename from connected %s.%s: %s" % (conn, attr, export_filename))
                            except Exception:
                                error_msg = "Error processing connected node attribute: conn=%s, attr=%s\n%s" % (str(conn), str(attr), traceback.format_exc())
                                cmds.warning(error_msg)
                                log_message(error_msg)
            except Exception as e:
                print("Error processing node %s: %s" % (node, str(e)))
        export_settings["exportPath"] = export_path if export_path else default_export_settings["exportPath"]
        export_settings["clipPrefix"] = export_filename if export_filename else default_export_settings["clipPrefix"]
        print("Final export_settings: exportPath='%s', clipPrefix='%s'" % (
            export_settings["exportPath"], export_settings["clipPrefix"]))
        if imported_count == 0:
            print("No clips found in gameFbxExporter nodes. Creating default clip from timeline.")
            start_frame = int(cmds.playbackOptions(q=True, min=True))
            end_frame = int(cmds.playbackOptions(q=True, max=True))
            clip = {
                "name": "Default_Clip",
                "start": int(start_frame),
                "end": int(end_frame),
                "exportMesh": True,
                "fps": 30,
                "enabled": True
            }
            clip_data.append(clip)
            log_message("Clip entry imported from Maya Game Exporter: index=%d, entry=%s" % (len(clip_data)-1, clip))
            imported_count = 1
        # Validate all imported FPS values
        for idx, clip in enumerate(clip_data):
            if "fps" not in clip or clip["fps"] not in fps_options:
                cmds.warning("Invalid FPS value in imported Maya Game Exporter data: %s. Allowed: %s. Defaulting to 30." % (clip.get("fps", None), fps_options))
                log_message("Invalid FPS value in imported Maya Game Exporter data: %s. Defaulting to 30." % clip.get("fps", None))
                clip["fps"] = 30
        print("Loaded %d clips from Maya Game Exporter." % imported_count)
        get_or_create_data_node()
        scene_data_loaded = True
        save_scene_data()
        return imported_count > 0
    except Exception:
        error_msg = "Error loading metadata from Maya Game Exporter:\n%s" % traceback.format_exc()
        cmds.warning(error_msg)
        log_message(error_msg)
        print(error_msg)
        scene_data_loaded = True
        return False

def refresh_ui():
    global clip_data
    try:
        if not cmds.window(WINDOW_NAME, exists=True):
            return
        try:
            if cmds.rowLayout("checkAllLayout", exists=True):
                cmds.deleteUI("checkAllLayout")
        except:
            pass
        try:
            if cmds.scrollLayout("clipListScrollLayout", exists=True):
                cmds.deleteUI("clipListScrollLayout")
        except:
            pass
        try:
            cmds.setParent("clipsFrame")
        except:
            print("Could not set parent to clipsFrame")
            return
        cmds.rowLayout("checkAllLayout", numberOfColumns=2,
                       columnAttach=[(1,"left",0),(2,"left",5)])
        cmds.button(label="Check All", width=80, height=20,
                    command=check_all_clips,
                    annotation="Enable all clips")
        cmds.button(label="Uncheck All", width=80, height=20,
                    command=uncheck_all_clips,
                    annotation="Disable all clips")
        cmds.setParent("clipsFrame")
        
        # Create a scrollable area for the clip list only
        cmds.scrollLayout("clipListScrollLayout", childResizable=True, height=300)
        cmds.columnLayout("clipListLayout", adjustableColumn=True, rowSpacing=4)
        
        for i, clip in enumerate(clip_data):
            if clip is None:
                continue
            try:
                row_name = "clipRow%d" % i
                cmds.rowLayout(row_name, numberOfColumns=12, adjustableColumn=2)
                def create_check_command(idx):
                    def cmd(value):
                        check_callback(value, idx)
                        save_scene_data()
                    return cmd
                def create_name_command(idx):
                    def cmd(value):
                        name_callback(value, idx)
                        save_scene_data()
                    return cmd
                def create_start_command(idx):
                    def cmd(value):
                        start_callback(value, idx)
                    return cmd
                def create_end_command(idx):
                    def cmd(value):
                        end_callback(value, idx)
                    return cmd
                def create_fps_command(idx):
                    def cmd(value):
                        fps_callback(value, idx)
                        save_scene_data()
                    return cmd
                def create_set_command(idx):
                    def cmd(*args):
                        set_clip_timeline(idx)
                    return cmd
                def create_get_command(idx):
                    def cmd(*args):
                        get_clip_timeline(idx)
                    return cmd
                def create_play_command(idx):
                    def cmd(*args):
                        play_clip(idx)
                    return cmd
                def create_duplicate_command(idx):
                    def cmd(*args):
                        text_field_name = "clipName%d" % idx
                        if cmds.textField(text_field_name, exists=True):
                            current_name = cmds.textField(text_field_name, q=True, text=True)
                            update_clip_value(idx, "name", current_name)
                        duplicate_clip(idx)
                    return cmd
                def create_up_command(idx):
                    def cmd(*args):
                        move_up(idx)
                    return cmd
                def create_down_command(idx):
                    def cmd(*args):
                        move_down(idx)
                    return cmd
                def create_delete_command(idx):
                    def cmd(*args):
                        delete_callback(idx)
                    return cmd
                cmds.checkBox(label='', value=clip.get("enabled", False),
                              annotation="Enable this clip",
                              changeCommand=create_check_command(i))
                clip_name = ""
                if "name" in clip and clip["name"] is not None:
                    clip_name = clip["name"]
                name_field = cmds.textField("clipName%d" % i, text=clip_name,
                             placeholderText="Clip Name", width=150,
                             annotation="Name of this animation clip",
                             changeCommand=create_name_command(i))
                cmds.intField("startField%d" % i, value=clip.get("start", 1), width=40,
                              annotation="Start Frame",
                              changeCommand=create_start_command(i))
                cmds.intField("endField%d" % i, value=clip.get("end", 24), width=40,
                              annotation="End Frame",
                              changeCommand=create_end_command(i))
                cmds.button(label="Frame", width=40, height=18,
                            annotation="Set Maya's timeline to this clip range",
                            command=create_set_command(i))
                cmds.button(label="Set", width=30, height=18,
                            annotation="Set this clip range to match Maya's current timeline",
                            command=create_get_command(i))
                cmds.button(label="Play", width=40, height=18,
                            annotation="Play this clip",
                            command=create_play_command(i))
                cmds.button(label="Dup", width=30, height=18,
                            annotation="Duplicate this clip",
                            command=create_duplicate_command(i))
                fps_menu = cmds.optionMenu(width=50,
                                           annotation="Frames Per Second",
                                           changeCommand=create_fps_command(i))
                for f in fps_options:
                    cmds.menuItem(label=str(f), parent=fps_menu, annotation="%d FPS" % f)
                if "fps" in clip and clip["fps"] in fps_options:
                    fps_idx = fps_options.index(clip["fps"]) + 1
                    cmds.optionMenu(fps_menu, edit=True, select=fps_idx)
                cmds.button(label=u"\u2191", width=20, height=18,
                            annotation="Move clip up",
                            command=create_up_command(i))
                cmds.button(label=u"\u2193", width=20, height=18,
                            annotation="Move clip down",
                            command=create_down_command(i))
                cmds.button(label="Delete", width=50, height=18,
                            annotation="Delete this clip",
                            command=create_delete_command(i))
                cmds.setParent("clipListLayout")
            except Exception:
                cmds.warning("Error creating UI row %d" % i)
                continue
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1,
                       columnAttach=[(1,"both",0),(2,"right",5)])
        cmds.separator(style="none", width=1)
        cmds.symbolButton(image="addClip.png", height=16, width=16,
                          command=add_clip,
                          annotation="Add a new animation clip")
        
        # Return to main layout
        cmds.setParent("clipsFrame")
        
        print("Updating UI: pathField='%s', prefixField='%s'" % (
            export_settings["exportPath"], export_settings["clipPrefix"]))
        cmds.textField("pathField", edit=True, text=export_settings["exportPath"])
        cmds.textField("prefixField", edit=True, text=export_settings["clipPrefix"])
        if "exportMode" in export_settings and cmds.optionMenu("exportModeMenu", exists=True):
            if export_settings["exportMode"] == "Export All Clips":
                cmds.optionMenu("exportModeMenu", edit=True, select=1)
            else:
                cmds.optionMenu("exportModeMenu", edit=True, select=2)
        # Update filename preview
        update_filename_preview()
    except Exception:
        error_msg = "Error refreshing UI:\n%s" % traceback.format_exc()
        cmds.warning(error_msg)
        print(error_msg)

def update_preset_joints(add=True):
    preset_dir = get_presets_folder()
    name = cmds.optionMenu("presetDropdown", q=True, value=True)
    if name == "<None>":
        cmds.warning("No preset selected.")
        return
    path = os.path.join(preset_dir, name + ".json")
    if not os.path.isfile(path):
        cmds.warning("Preset file not found.")
        return
    try:
        with open(path, "r") as f:
            data = json.load(f)
        root_joints = set(data.get("root_joints", []))
        selected = set(get_joints_and_locators())
        if not selected and add:
            cmds.warning("No joints/locators selected.")
            return
        if add:
            root_joints.update(selected)
        else:
            root_joints.difference_update(selected)
        data["root_joints"] = list(root_joints)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        cmds.inViewMessage(amg="Preset joints updated.", pos='topCenter', fade=True)
    except Exception:
        error_msg = "Error updating preset joints:\n%s" % traceback.format_exc()
        cmds.warning(error_msg)
        log_message(error_msg)

def get_hierarchical_joint_order(joints):
    """
    Sort joints in hierarchical order, showing parent-child relationships.
    Returns a list of tuples: [(joint_name, indent_level, prefix), ...]
    
    Args:
        joints (list): List of joint/locator names
        
    Returns:
        list: List of tuples (joint_name, indent_level, tree_prefix) in hierarchical order
    """
    if not joints:
        return []
    
    # Filter to only existing joints
    existing_joints = [j for j in joints if cmds.objExists(j)]
    if not existing_joints:
        # Return non-existing joints as-is with 0 indent and no prefix
        return [(j, 0, "") for j in joints]
    
    # Find roots: joints whose parent is not in the list or have no parent
    roots = []
    for joint in existing_joints:
        parent = cmds.listRelatives(joint, parent=True)
        if not parent or parent[0] not in existing_joints:
            roots.append(joint)
    
    # Recursively build hierarchy with tree-style prefixes
    result = []
    visited = set()
    
    def add_hierarchy(joint_name, depth=0, is_last_child=True, parent_prefix=""):
        if joint_name in visited:
            return
        visited.add(joint_name)
        
        # Build the tree prefix for this joint - using simple characters and larger spacing
        if depth == 0:
            # Root joint - no prefix
            tree_prefix = ""
        else:
            # Child joint - add tree characters with extra spacing
            if is_last_child:
                tree_prefix = parent_prefix + u"\u2514\u2500\u2500\u2500 "  # └───  (3 dashes + space)
            else:
                tree_prefix = parent_prefix + u"\u251C\u2500\u2500\u2500 "  # ├───  (3 dashes + space)
        
        result.append((joint_name, depth, tree_prefix))
        
        # Get children that are in our joint list
        children = cmds.listRelatives(joint_name, children=True, type="transform") or []
        child_joints = [c for c in children if c in existing_joints and c not in visited]
        
        # Sort children alphabetically for consistency
        child_joints = sorted(child_joints)
        
        # Process children
        for i, child in enumerate(child_joints):
            is_last = (i == len(child_joints) - 1)
            
            # Build prefix for child's children - always use spaces (no vertical continuation)
            child_parent_prefix = parent_prefix + "      "  # 6 spaces for indentation
            
            add_hierarchy(child, depth + 1, is_last, child_parent_prefix)
    
    # Process each root hierarchy
    sorted_roots = sorted(roots)
    for idx, root in enumerate(sorted_roots):
        add_hierarchy(root, 0)
        # Add a blank separator between different root hierarchies (except after last)
        if idx < len(sorted_roots) - 1:
            result.append(("", -1, ""))  # Separator marker
    
    # Add any non-existing joints at the end with 0 indent
    non_existing = [j for j in joints if j not in existing_joints]
    for joint in non_existing:
        result.append((joint, 0, ""))
    
    return result

def show_preset_joints():
    preset_dir = get_presets_folder()
    name = cmds.optionMenu("presetDropdown", q=True, value=True)
    if name == "<None>":
        cmds.warning("No preset selected.")
        return
    path = os.path.join(preset_dir, name + ".json")
    if not os.path.isfile(path):
        cmds.warning("Preset file not found.")
        return
    try:
        with open(path, "r") as f:
            data = json.load(f)
        joints = data.get("root_joints", [])
        
        if cmds.window("presetJointListWin", exists=True):
            cmds.deleteUI("presetJointListWin")
        
        # Get or initialize ordering mode preference
        if not cmds.optionVar(exists="haxExporter_jointOrderMode"):
            cmds.optionVar(stringValue=("haxExporter_jointOrderMode", "added"))
        
        win = cmds.window("presetJointListWin", title="Preset Joints: " + name, 
                         widthHeight=(400, 350))
        main_layout = cmds.columnLayout("presetJointMainLayout", adjustableColumn=True, rowSpacing=5)
        
        # Info section
        cmds.separator(height=5, style="none")
        cmds.text("presetJointTotalText", label="Total Joints in Preset: %d" % len(joints), 
                 align="left", font="boldLabelFont")
        cmds.text("presetJointSelectedText", label="Currently Selected: 0", 
                 align="left", font="boldLabelFont")
        cmds.separator(height=5, style="in")
        
        # Select All button
        def select_all_preset_joints(*args):
            try:
                # Filter joints to only select ones that exist in the scene
                existing_joints = [j for j in joints if cmds.objExists(j)]
                if existing_joints:
                    cmds.select(existing_joints, replace=True)
                    log_message("Selected %d joints from preset '%s'" % (len(existing_joints), name))
                else:
                    cmds.warning("None of the preset joints exist in the current scene.")
                    log_message("No preset joints found in scene for preset '%s'" % name)
            except Exception as e:
                error_msg = "Error selecting preset joints: %s" % str(e)
                cmds.warning(error_msg)
                log_message(error_msg)
        
        cmds.button(label="Select All Joints", height=30, 
                   command=select_all_preset_joints,
                   annotation="Select all joints from this preset that exist in the scene",
                   bgc=(0.65, 0.87, 0.65))
        
        # Function to rebuild joint list with current ordering
        def rebuild_joint_list(*args):
            try:
                # Delete existing joint list layout if it exists
                if cmds.scrollLayout("presetJointScrollLayout", exists=True):
                    cmds.deleteUI("presetJointScrollLayout")
                
                # Set parent back to main layout
                cmds.setParent(main_layout)
                
                # Get current ordering mode
                order_mode = cmds.optionVar(q="haxExporter_jointOrderMode")
                
                # Prepare joint list based on ordering mode
                if order_mode == "hierarchical":
                    joint_list = get_hierarchical_joint_order(joints)
                else:  # "added" order
                    joint_list = [(j, 0, "") for j in joints]
                
                # Create scrollable joint list
                cmds.scrollLayout("presetJointScrollLayout", childResizable=True, height=450, parent=main_layout)
                cmds.columnLayout("presetJointListColumn", adjustableColumn=True)
                
                # Get current selection to highlight selected joints
                current_selection = cmds.ls(selection=True) or []
                
                # Variable to track last clicked joint for Shift+Click range selection
                last_clicked_joint = [None]  # Use list to allow mutation in nested function
                
                # Store flattened joint names for index lookups
                flat_joints = [j[0] for j in joint_list if j[0]]  # Skip empty separators
                
                for idx, joint_data in enumerate(joint_list):
                    # Handle separator entries
                    if len(joint_data) == 3 and joint_data[1] == -1:
                        # This is a separator between root hierarchies
                        cmds.separator(height=3, style="none")
                        continue
                    
                    joint, indent_level, tree_prefix = joint_data
                    # Create clickable button for each joint
                    def make_select_joint_command(joint_name, joint_index):
                        def cmd(*args):
                            try:
                                if cmds.objExists(joint_name):
                                    # Get keyboard modifiers
                                    modifiers = cmds.getModifiers()
                                    shift_held = (modifiers & 1) > 0
                                    ctrl_held = (modifiers & 4) > 0
                                    
                                    if shift_held and last_clicked_joint[0] is not None:
                                        # Shift+Click: Range selection
                                        try:
                                            last_idx = flat_joints.index(last_clicked_joint[0]) if last_clicked_joint[0] in flat_joints else None
                                            current_idx = joint_index
                                            
                                            if last_idx is not None:
                                                start_idx = min(last_idx, current_idx)
                                                end_idx = max(last_idx, current_idx)
                                                range_joints = [flat_joints[i] for i in range(start_idx, end_idx + 1) if cmds.objExists(flat_joints[i])]
                                                
                                                if range_joints:
                                                    if ctrl_held:
                                                        cmds.select(range_joints, add=True)
                                                        log_message("Added range of %d joints to selection" % len(range_joints))
                                                    else:
                                                        cmds.select(range_joints, replace=True)
                                                        log_message("Selected range of %d joints" % len(range_joints))
                                        except Exception as e:
                                            log_message("Error in range selection: %s" % str(e))
                                            cmds.select(joint_name, replace=True)
                                    elif ctrl_held:
                                        # Ctrl+Click: Toggle selection
                                        current_sel = cmds.ls(selection=True) or []
                                        if joint_name in current_sel:
                                            cmds.select(joint_name, deselect=True)
                                            log_message("Deselected joint: %s" % joint_name)
                                        else:
                                            cmds.select(joint_name, add=True)
                                            log_message("Added joint to selection: %s" % joint_name)
                                        last_clicked_joint[0] = joint_name
                                    else:
                                        # Normal click: Replace selection
                                        cmds.select(joint_name, replace=True)
                                        log_message("Selected joint: %s" % joint_name)
                                        last_clicked_joint[0] = joint_name
                                else:
                                    cmds.warning("Joint does not exist in scene: %s" % joint_name)
                            except Exception as e:
                                error_msg = "Error selecting joint %s: %s" % (joint_name, str(e))
                                cmds.warning(error_msg)
                                log_message(error_msg)
                        return cmd
                    
                    # Create unique button name for this joint
                    button_name = "presetJointBtn_%d" % idx
                    
                    # Color code joints based on existence in scene and selection state
                    if cmds.objExists(joint):
                        is_selected = joint in current_selection
                        bg_color = (0.45, 0.45, 0.45) if is_selected else (0.25, 0.25, 0.25)
                        # Add tree prefix and selection marker
                        label = tree_prefix + (u"\u25BA " + joint if is_selected else joint)
                        
                        cmds.button(button_name, label=label, align="left", height=20,
                                   command=make_select_joint_command(joint, idx),
                                   annotation="Click to select | Shift+Click for range | Ctrl+Click to add/remove",
                                   backgroundColor=bg_color)
                    else:
                        cmds.button(button_name, label=tree_prefix + joint + " (not in scene)", align="left", height=20,
                                   enable=False,
                                   annotation="This joint does not exist in the current scene",
                                   backgroundColor=(0.2, 0.2, 0.2))
                
                cmds.setParent("..")
                cmds.setParent("..")
                
                log_message("Rebuilt joint list with '%s' ordering" % order_mode)
            except Exception as e:
                error_msg = "Error rebuilding joint list: %s" % traceback.format_exc()
                cmds.warning(error_msg)
                log_message(error_msg)
        
        # Toggle button for ordering mode
        def toggle_order_mode(*args):
            current_mode = cmds.optionVar(q="haxExporter_jointOrderMode")
            new_mode = "hierarchical" if current_mode == "added" else "added"
            cmds.optionVar(stringValue=("haxExporter_jointOrderMode", new_mode))
            
            # Update button label
            if cmds.button("toggleOrderBtn", exists=True):
                label = "Order: Hierarchical" if new_mode == "hierarchical" else "Order: Added"
                cmds.button("toggleOrderBtn", edit=True, label=label)
            
            # Rebuild the joint list
            rebuild_joint_list()
            
            log_message("Switched joint ordering to: %s" % new_mode)
        
        # Create toggle button
        current_mode = cmds.optionVar(q="haxExporter_jointOrderMode")
        mode_label = "Order: Hierarchical" if current_mode == "hierarchical" else "Order: Added"
        cmds.button("toggleOrderBtn", label=mode_label, height=25,
                   command=toggle_order_mode,
                   annotation="Toggle between added order and hierarchical order",
                   bgc=(0.4, 0.6, 0.8))
        
        cmds.separator(height=5, style="in")
        
        # Build initial joint list
        rebuild_joint_list()
        
        # Function to update selected count and button highlighting
        def update_selected_count(*args):
            try:
                if not cmds.window("presetJointListWin", exists=True):
                    return
                selected = get_joints_and_locators()
                # Count how many selected joints are in the preset
                selected_in_preset = [j for j in selected if j in joints]
                count = len(selected_in_preset)
                if cmds.text("presetJointSelectedText", exists=True):
                    cmds.text("presetJointSelectedText", edit=True, 
                             label="Currently Selected: %d" % count)
                
                # Get current ordering mode and joint list
                order_mode = cmds.optionVar(q="haxExporter_jointOrderMode")
                if order_mode == "hierarchical":
                    joint_list = get_hierarchical_joint_order(joints)
                else:
                    joint_list = [(j, 0, "") for j in joints]
                
                # Update button colors and labels to highlight selected joints
                for idx, joint_data in enumerate(joint_list):
                    # Skip separator entries
                    if len(joint_data) == 3 and joint_data[1] == -1:
                        continue
                    
                    joint, indent_level, tree_prefix = joint_data
                    button_name = "presetJointBtn_%d" % idx
                    if cmds.button(button_name, exists=True):
                        # Only update color for existing joints (not disabled buttons)
                        if cmds.objExists(joint):
                            is_selected = joint in selected
                            # Lighter gray for selected, normal dark gray for unselected
                            bg_color = (0.45, 0.45, 0.45) if is_selected else (0.25, 0.25, 0.25)
                            
                            # Add tree prefix and visual marker
                            label = tree_prefix + (u"\u25BA " + joint if is_selected else joint)
                            
                            cmds.button(button_name, edit=True, backgroundColor=bg_color, label=label)
            except Exception:
                pass
        
        # Create script job to update selection count
        script_job_id = cmds.scriptJob(event=["SelectionChanged", update_selected_count], 
                                      parent="presetJointListWin")
        
        # Initial update
        update_selected_count()
        
        cmds.showWindow(win)
        log_message("Opened preset joints window for '%s' with %d joints" % (name, len(joints)))
    except Exception:
        error_msg = "Error showing preset joints:\n%s" % traceback.format_exc()
        cmds.warning(error_msg)
        log_message(error_msg)

def create_ui():
    if cmds.objExists("FitSkeleton"):
        cmds.confirmDialog(title="Advanced Skeleton",
                           message="Switching to Advanced Skeleton mode",
                           button=["OK"])
    try:
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME)
        cmds.window(WINDOW_NAME, title="Hax Game Exporter",
                    widthHeight=(700,1000), sizeable=True)
        cmds.columnLayout("mainColumn", adjustableColumn=True)

        cmds.separator(height=6, style="none")
        cmds.text(
            label=("IMPORTANT: For STALKER 2, you MUST open MoCap Matcher using "
                   "the Animation Importer's 'MoCap Matcher' button."),
            align="center",
            font="boldLabelFont",
            height=32
        )
        cmds.separator(height=6, style="none")
        
        # Add 5px spacing after Preset line
        cmds.columnLayout(adjustableColumn=True, height=5)
        cmds.setParent("..")
        
        # Preset row (remove Namespace dropdown from here)
        cmds.rowLayout(numberOfColumns=7, adjustableColumn=2)
        cmds.text(label="Preset:", annotation="Select a preset configuration")
        cmds.optionMenu("presetDropdown", changeCommand=on_preset_selected,
                        annotation="Select or load a preset")
        update_preset_menu()
        cmds.button(label="Add Joints", width=90, height=18,
                    command=lambda *_: update_preset_joints(add=True),
                    annotation="Add selected joints to current preset",
                    bgc=(0.65, 0.87, 0.65))  # non-aggressive green
        cmds.button(label="Remove Joints", width=90, height=18,
                    command=lambda *_: update_preset_joints(add=False),
                    annotation="Remove selected joints from current preset",
                    bgc=(0.95, 0.65, 0.65))  # non-aggressive red
        cmds.button(label="Show Joints", width=100, height=18,
                    command=lambda *_: show_preset_joints(),
                    annotation="Show joints stored in current preset",
                    bgc=(0.93, 0.93, 0.93))  # white/grey-ish
        cmds.setParent("..")
        # New row: Namespace dropdown + Delete Preset + Save Preset + Open Log + Import/Export Data
        cmds.rowLayout(numberOfColumns=6, adjustableColumn=2)
        setup_namespace_menu()
        cmds.button(label="Delete Preset", width=100, height=18,
                    command=lambda *_: delete_preset(),
                    annotation="Delete the selected preset permanently")
        def save_preset_command(*args):
            try:
                # Check if there's a current preset selected
                current_preset = cmds.optionMenu("presetDropdown", q=True, value=True) if cmds.optionMenu("presetDropdown", exists=True) else "<None>"
                
                if current_preset != "<None>":
                    # Ask user if they want to update current preset or create new one
                    choice_result = cmds.confirmDialog(
                        title='Save Preset',
                        message='A preset "%s" is currently selected.\n\nWhat would you like to do?' % current_preset,
                        button=['Update Current Preset', 'Create New Preset', 'Cancel'],
                        defaultButton='Update Current Preset',
                        cancelButton='Cancel',
                        dismissString='Cancel'
                    )
                    
                    if choice_result == 'Update Current Preset':
                        # Update the existing preset
                        save_preset(current_preset)
                        return
                    elif choice_result == 'Create New Preset':
                        # Continue to name prompt for new preset
                        pass
                    else:
                        # User cancelled
                        return
                
                # Prompt for new preset name (either no current preset or user chose to create new)
                result = cmds.promptDialog(
                    title='Save New Preset',
                    message='Name:',
                    button=['OK','Cancel'],
                    defaultButton='OK',
                    cancelButton='Cancel',
                    dismissString='Cancel'
                )
                if result == 'OK':
                    name = cmds.promptDialog(q=True, text=True)
                    save_preset(name)
            except Exception:
                error_msg = "Error saving preset:\n%s" % traceback.format_exc()
                cmds.warning(error_msg)
                log_message(error_msg)
        cmds.button(label="Save Preset", width=180, height=18,
                    command=save_preset_command,
                    annotation="Save current settings as preset")
        cmds.button(label="Open Log", width=80, height=18,
                    command=lambda x: open_log_file(),
                    annotation="Open the log file in text editor")
        # Combine Import Data and Export Data on the same row
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1)
        cmds.button(label="Import Data", width=80, height=18,
                    command=import_data_command,
                    annotation="Import animation clip data from Maya Game Exporter or text file")
        cmds.button(label="Export Data", width=80, height=18,
                    command=export_data_command,
                    annotation="Export animation clip data to a text file")
        cmds.setParent("..")
        cmds.setParent("..")
        
        # Add 5px spacing above Export Mode
        cmds.columnLayout(adjustableColumn=True, height=5)
        cmds.setParent("..")
        
        def export_mode_changed(mode):
            export_settings["exportMode"] = mode
            save_scene_data()
            log_message("Export mode changed to: %s" % mode)
        # Add Export Mode dropdown with right-justified SETTINGS and HELP buttons on the same row
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnAlign=[(1, 'left'), (2, 'right'), (3, 'right')], columnAttach=[(1, 'both', 0), (2, 'right', 5), (3, 'right', 0)], width=700)
        cmds.optionMenu("exportModeMenu", label="Export Mode",
                        changeCommand=export_mode_changed,
                        annotation="Choose export all or selected clips")
        cmds.menuItem(label="Export All Clips",
                      annotation="Export every clip")
        cmds.menuItem(label="Export Selected Clips",
                      annotation="Export only checked clips")
        if "exportMode" in export_settings:
            if export_settings["exportMode"] == "Export All Clips":
                cmds.optionMenu("exportModeMenu", edit=True, select=1)
            else:
                cmds.optionMenu("exportModeMenu", edit=True, select=2)
        # Right-justified SETTINGS button - bright orange for visibility
        cmds.button(label="SETTINGS", width=90, height=24, bgc=(1.0, 0.55, 0.0),
                    annotation="Configure Skyrim HKX export and other settings",
                    command=lambda *_: run_skyrim_settings_and_update())
        # Right-justified HELP button, non-aggressive yellow
        cmds.button(label="HELP", width=80, height=24, bgc=(0.98, 0.92, 0.55),
                    annotation="Show detailed help for the Hax Game Exporter",
                    command=lambda *_: run_hax_exporter_helper())
        cmds.setParent("..")
        
        # Export Process indicator row - shows current export process prominently (hidden when Default)
        cmds.rowLayout("exportProcessRow", numberOfColumns=1, adjustableColumn=1, height=22, visible=False)
        cmds.text("exportProcessIndicator", label="", align="center", font="boldLabelFont",
                  annotation="Current export process - click SETTINGS to change")
        cmds.setParent("..")
        update_export_process_indicator()  # Initialize the indicator (will show/hide as needed)
        
        # Animation Clips Frame with non-scrollable buttons and scrollable clips
        cmds.frameLayout("clipsFrame", label="Animation Clips",
                         collapsable=True, collapse=False,
                         marginHeight=5)
        cmds.setParent("..")
        
        # In create_ui, just before settingsFrame:
        build_anim_layers_ui()
        
        # Add rotation offset frame
        build_rotation_offset_ui()
        
        cmds.frameLayout("settingsFrame", label="Settings",
                         collapsable=True, collapse=False,
                         marginHeight=5)
        cmds.columnLayout(adjustableColumn=True)
        cmds.optionMenuGrp("fileTypeMenu", label="File Type",
                           changeCommand=lambda v: [export_settings.update({"fileType":v}), save_scene_data()],
                           annotation="Choose Binary or ASCII FBX")
        for ft in file_types:
            cmds.menuItem(label=ft, annotation=ft)
        # Set initial file type selection from export_settings
        try:
            file_type = export_settings.get("fileType", "ASCII")
            cmds.optionMenuGrp("fileTypeMenu", edit=True, value=file_type)
        except Exception as e:
            log_message("Could not initialize fileTypeMenu: %s" % str(e))
        
        cmds.optionMenuGrp("fbxVerMenu", label="FBX Version",
                           changeCommand=lambda v: [export_settings.update({"fbxVersion":v}), save_scene_data()],
                           annotation="Choose FBX version year")
        for fv in fbx_versions:
            cmds.menuItem(label=fv, annotation=fv)
        # Set initial FBX version selection from export_settings
        try:
            fbx_version = export_settings.get("fbxVersion", "2018")
            cmds.optionMenuGrp("fbxVerMenu", edit=True, value=fbx_version)
        except Exception as e:
            log_message("Could not initialize fbxVerMenu: %s" % str(e))
        
        def update_settings(*args):
            try:
                export_settings.update({
                    "embedMedia": cmds.checkBoxGrp("exportOptionsGrp", q=True, value1=True),
                    "bakeAnimation": cmds.checkBoxGrp("exportOptionsGrp", q=True, value2=True),
                    "moveToOrigin": cmds.checkBoxGrp("exportOptionsGrp", q=True, value3=True),
                    "altRootControl": cmds.textField("altRootControlField", q=True, text=True)
                })
                save_scene_data()
            except Exception:
                error_msg = "Error updating settings:\n%s" % traceback.format_exc()
                cmds.warning(error_msg)
                print(error_msg)
        cmds.rowLayout(numberOfColumns=4, adjustableColumn=1, columnAlign=[(1, 'left'), (2, 'right'), (3, 'right'), (4, 'right')], columnAttach=[(1, 'left', 0), (2, 'both', 2), (3, 'both', 2), (4, 'both', 2)], width=700)
        cmds.checkBoxGrp("exportOptionsGrp", label="Options",
                         numberOfCheckBoxes=3,
                         labelArray3=["Embed Media","Bake Animation","Move To Origin"],
                         valueArray3=[export_settings["embedMedia"],
                                      export_settings["bakeAnimation"],
                                      export_settings["moveToOrigin"]],
                         annotation="FBX export options",
                         changeCommand=update_settings)
        cmds.text(label="Alt Root Control:", align="right", annotation="Optional: Use this object for Move To Origin instead of the root joint.")
        cmds.textField("altRootControlField", text=export_settings.get("altRootControl", ""), width=160,
                      placeholderText="Alt Root Control",
                      annotation="Optional: Use this object for Move To Origin instead of the root joint. Click the button to grab the current selection.",
                      changeCommand=lambda v: [export_settings.update({"altRootControl": v}), save_scene_data()])
        def grab_alt_root_control(*_):
            sel = cmds.ls(selection=True)
            if sel:
                cmds.textField("altRootControlField", edit=True, text=sel[0])
                export_settings["altRootControl"] = sel[0]
                save_scene_data()
            else:
                # Clear the field if nothing is selected
                cmds.textField("altRootControlField", edit=True, text="")
                export_settings["altRootControl"] = ""
                save_scene_data()
        cmds.button(label="Grab", width=50, height=18, command=grab_alt_root_control, annotation="Set Alt Root Control to the currently selected object.")
        cmds.setParent("..")
        
        # Add Remove Namespaces checkbox
        cmds.checkBox("removeNamespacesCheck", label="Remove Namespaces on Export",
                     value=export_settings.get("removeNamespaces", False),
                     annotation="Create a duplicate skeleton without namespaces for export. Only applies if the root joint has a namespace. The duplicate is constrained, baked, exported, then deleted.",
                     changeCommand=lambda v: [export_settings.update({"removeNamespaces": v}), save_scene_data()])
        
        # Add Bake from Constraints checkbox
        cmds.checkBox("bakeFromConstraintsCheck", label="Bake from Constraints",
                     value=export_settings.get("bakeFromConstraints", False),
                     annotation="SAVE BEFORE USING.\n\nKey all joints on every frame of the animation before export.\nUseful for baking constraint animations into keyframes.\n\nThis isn't normally needed, but if joints are being exported\nwithout any animation, this may fix it.\n\nTHIS WILL LIKELY BREAK YOUR RIG. RELOAD YOUR SCENE.",
                     changeCommand=lambda v: [export_settings.update({"bakeFromConstraints": v}), save_scene_data()])
        
        # Add Include Children checkbox
        cmds.checkBox("includeChildrenCheck", label="Include Children",
                     value=export_settings.get("includeChildren", True),
                     annotation="Include child objects in the FBX export. When enabled, all children of selected objects will be exported.",
                     changeCommand=lambda v: [export_settings.update({"includeChildren": v}), save_scene_data()])
        
        # Add Input Connections checkbox
        cmds.checkBox("inputConnectionsCheck", label="Input Connections",
                     value=export_settings.get("inputConnections", False),
                     annotation="Include input connections in the FBX export. When enabled, input connections to exported objects will be preserved.",
                     changeCommand=lambda v: [export_settings.update({"inputConnections": v}), save_scene_data()])
        
        # Add Constraints checkbox
        cmds.checkBox("constraintsCheck", label="Constraints",
                     value=export_settings.get("constraints", False),
                     annotation="When enabled, transforms from constraints will be taken into account and exported.",
                     changeCommand=lambda v: [export_settings.update({"constraints": v}), save_scene_data()])
        
        cmds.setParent("..")
        cmds.frameLayout("pathFrame", label="Path",
                         collapsable=True, collapse=False,
                         marginHeight=5)
        cmds.columnLayout(adjustableColumn=True)
        # Filename preview text
        first_active_clip = next((clip for clip in clip_data if clip.get("enabled", False)), None)
        preview_label = "Filename Preview: No active clips to preview"
        if first_active_clip:
            clip_name = first_active_clip.get("name", "Untitled")
            if not clip_name:
                clip_name = "Untitled"
            preview_path = os.path.join(export_settings["exportPath"],
                                       export_settings["clipPrefix"] + clip_name + ".fbx").replace("\\", "/")
            preview_label = "Filename Preview: " + preview_path
        cmds.text("filenamePreviewText", label=preview_label,
                  annotation="Preview of the first active clip's output filename")
        log_message("Initialized filename preview in Path section: %s" % preview_label)
        # Sample text above path field
        cmds.text(label="e.g., anim_", font="smallObliqueLabelFont",
                  annotation="Example prefix that will be added to all exported filenames")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, 'left', 0), (2, 'left', 2)])
        cmds.textField("pathField", text=export_settings["exportPath"],
                       placeholderText="Export Path",
                       annotation="Directory for FBX exports",
                       changeCommand=lambda v: [export_settings.update({"exportPath": v}), save_scene_data(), refresh_ui()])
        cmds.button(label="Browse", command=browse_export_path,
                    annotation="Select export directory")
        cmds.setParent("..")
        cmds.rowLayout(numberOfColumns=1, adjustableColumn=1, columnAttach=[(1, 'left', 0)])
        cmds.textField("prefixField", text=export_settings["clipPrefix"],
                       placeholderText="Prefix",
                       annotation="Filename prefix",
                       changeCommand=lambda v: [export_settings.update({"clipPrefix": v}), save_scene_data(), update_filename_preview()],
                       width=120)
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.rowLayout(numberOfColumns=1, adjustableColumn=1)
        def export_button_command(*args):
            try:
                export_mode = cmds.optionMenu("exportModeMenu", query=True, value=True)
                print("Export button clicked with mode: %s" % export_mode)
                if export_mode == "Export All Clips":
                    export_clips()
                else:
                    export_selected_clips()
            except Exception:
                error_msg = "Error executing export:\n%s" % traceback.format_exc()
                cmds.warning(error_msg)
                print(error_msg)
        cmds.button(label="Export", width=100, height=30,
                    command=export_button_command,
                    annotation="Export clips based on selected mode and settings")
        cmds.setParent("..")
        refresh_ui()
        # Set dropdown to last saved preset if it exists and is valid
        if "currentPreset" in export_settings and cmds.optionMenu("presetDropdown", exists=True):
            preset_dir = get_presets_folder()
            preset_path = os.path.join(preset_dir, export_settings["currentPreset"] + ".json")
            if export_settings["currentPreset"] != "<None>" and os.path.exists(preset_path):
                try:
                    cmds.optionMenu("presetDropdown", edit=True, value=export_settings["currentPreset"])
                    log_message("Initialized dropdown to last saved preset: %s" % export_settings["currentPreset"])
                    on_preset_selected(export_settings["currentPreset"], from_initialization=True)
                except Exception as e:
                    log_message("Error setting dropdown to last saved preset '%s': %s" % (export_settings["currentPreset"], str(e)))
                    cmds.optionMenu("presetDropdown", edit=True, value="<None>")
                    on_preset_selected("<None>", from_initialization=True)
            else:
                log_message("Last saved preset '%s' not found or invalid, setting to <None>" % export_settings["currentPreset"])
                cmds.optionMenu("presetDropdown", edit=True, value="<None>")
                on_preset_selected("<None>", from_initialization=True)
        
        # Add cleanup script job to close child windows when main window closes
        def cleanup_child_windows():
            """Close Show Joints and Helper windows when main exporter closes"""
            try:
                # Close Show Joints window
                if cmds.window("presetJointListWin", exists=True):
                    cmds.deleteUI("presetJointListWin")
                    log_message("Closed Show Joints window on main window close")
            except Exception as e:
                log_message("Error closing Show Joints window: %s" % str(e))
            
            try:
                # Close Helper dialog (Qt dialog)
                # Try to call the close function if it exists in globals
                if 'close_all_help_dialogs' in globals():
                    close_all_help_dialogs()
                    log_message("Closed Help dialog on main window close")
                else:
                    # Fallback: Try to find and close the dialog using Qt
                    try:
                        # Try importing PySide to close the dialog directly
                        try:
                            from PySide6 import QtWidgets
                        except ImportError:
                            from PySide2 import QtWidgets
                        
                        app = QtWidgets.QApplication.instance()
                        if app:
                            all_widgets = app.allWidgets()
                            for widget in all_widgets:
                                try:
                                    if isinstance(widget, QtWidgets.QDialog):
                                        if hasattr(widget, 'windowTitle') and widget.windowTitle() == "Hax Game Exporter - Help":
                                            widget.close()
                                            widget.deleteLater()
                                            log_message("Closed Help dialog using Qt fallback method")
                                except Exception:
                                    pass
                    except Exception:
                        pass
            except Exception as e:
                log_message("Error closing Help dialog: %s" % str(e))
        
        cmds.scriptJob(uiDeleted=[WINDOW_NAME, cleanup_child_windows], protected=False)
        log_message("Registered cleanup script job for child windows")
        
        cmds.showWindow(WINDOW_NAME)
    except Exception:
        error_msg = "Error creating UI:\n%s" % traceback.format_exc()
        cmds.warning(error_msg)
        print(error_msg)

def initialize_exporter():
    try:
        global scene_data_loaded
        setup_logging()
        log_message("Initializing Hax Game Exporter...")
        data_loaded = load_scene_data()
        maya_data_exists = has_native_exporter_data()
        if data_loaded:
            scene_data_loaded = True
            log_message("Using existing custom game exporter data")
        elif maya_data_exists:
            if show_import_dialog():
                load_game_exporter_metadata()
            else:
                scene_data_loaded = True
                log_message("Starting with empty configuration (Maya exporter data not imported)")
        else:
            scene_data_loaded = True
            log_message("No existing exporter data found")
        create_ui()
        log_message("Hax Game Exporter v1.0 initialized successfully")
        log_message("Clip data and settings are stored in the Maya scene")
    except Exception:
        error_msg = "Error initializing exporter:\n%s" % traceback.format_exc()
        cmds.warning(error_msg)
        log_message(error_msg)

def cleanup_logging():
    global log_file
    if log_file and not log_file.closed:
        try:
            log_file.write("\n===== Hax Game Exporter Session Ended =====\n")
            log_file.close()
        except:
            pass

import atexit
atexit.register(cleanup_logging)

def run_hax_exporter_helper():
    """Run the help dialog using the helper script."""
    # Try to find the helper script in multiple locations
    helper_script = None
    
    # Method 1: Look in the same directory as this file
    try:
        if '__file__' in globals():
            helper_script = os.path.join(os.path.dirname(__file__), 'HaxExporterHelper.py')
            if not os.path.exists(helper_script):
                helper_script = None
    except:
        pass
    
    # Method 2: Look in Maya's scripts directory
    if not helper_script:
        maya_script_dir = cmds.internalVar(userScriptDir=True)
        potential_path = os.path.join(maya_script_dir, 'HaxExporterHelper.py')
        if os.path.exists(potential_path):
            helper_script = potential_path
    
    if not helper_script or not os.path.exists(helper_script):
        error_msg = 'HaxExporterHelper.py not found. Please reinstall the Hax Game Exporter.'
        cmds.warning(error_msg)
        log_message(error_msg)
        return
    
    try:
        if sys.version_info[0] == 2:
            execfile(helper_script, globals())
        else:
            with open(helper_script, 'r') as f:
                code = f.read()
            exec(compile(code, helper_script, 'exec'), globals())
    except Exception as e:
        error_msg = 'Error running HaxExporterHelper.py: %s\n%s' % (str(e), traceback.format_exc())
        cmds.warning(error_msg)
        log_message(error_msg)

def find_export_process_script():
    """Find the HaxExporterSettings.py script in various locations."""
    script_name = 'HaxExporterSettings.py'
    
    paths_to_try = []
    
    # Method 1: Look relative to this file (if __file__ is defined)
    try:
        if '__file__' in dir() or '__file__' in globals():
            base_dir = os.path.dirname(os.path.abspath(__file__))
            paths_to_try.append(os.path.join(base_dir, 'hax_exporter_data', 'Process', script_name))
    except:
        pass
    
    # Method 2: Look in Maya's user scripts directory
    try:
        maya_script_dir = cmds.internalVar(userScriptDir=True)
        if maya_script_dir:
            paths_to_try.append(os.path.join(maya_script_dir, 'hax_exporter_data', 'Process', script_name))
    except:
        pass
    
    # Method 3: Look in Maya's app scripts directory
    try:
        maya_app_dir = cmds.internalVar(userAppDir=True)
        if maya_app_dir:
            paths_to_try.append(os.path.join(maya_app_dir, 'scripts', 'hax_exporter_data', 'Process', script_name))
    except:
        pass
    
    # Method 4: Check MAYA_SCRIPT_PATH environment variable
    try:
        script_paths = os.environ.get('MAYA_SCRIPT_PATH', '').split(os.pathsep)
        for sp in script_paths:
            if sp:
                paths_to_try.append(os.path.join(sp, 'hax_exporter_data', 'Process', script_name))
    except:
        pass
    
    # Try each path
    for path in paths_to_try:
        try:
            normalized_path = os.path.normpath(path)
            if os.path.exists(normalized_path):
                log_message("Found HaxExporterSettings at: %s" % normalized_path)
                return normalized_path
        except:
            pass
    
    # Debug: Log what we tried
    log_message("Could not find %s. Tried paths:" % script_name)
    for path in paths_to_try:
        log_message("  - %s (exists: %s)" % (path, os.path.exists(path) if path else False))
    
    return None

def get_current_export_process():
    """Get the current export process setting from the scene."""
    try:
        script_path = find_export_process_script()
        if script_path:
            if sys.version_info[0] >= 3:
                import importlib.util
                spec = importlib.util.spec_from_file_location("HaxExporterSettings", script_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module.get_export_process()
            else:
                import imp
                module = imp.load_source('HaxExporterSettings', script_path)
                return module.get_export_process()
    except:
        pass
    return "default"

def update_export_process_indicator():
    """Update the export process indicator label on the main UI. Hidden when Default."""
    try:
        if not cmds.rowLayout("exportProcessRow", exists=True):
            return
        if not cmds.text("exportProcessIndicator", exists=True):
            return
        
        process = get_current_export_process()
        
        if process == "default":
            # Default - hide the entire row
            cmds.rowLayout("exportProcessRow", edit=True, visible=False)
        elif process == "skyrim":
            # Skyrim - bright cyan/teal to stand out, centered, bold
            cmds.text("exportProcessIndicator", edit=True,
                     label="⚡ Export Process: SKYRIM (FBX → HKX) ⚡",
                     align="center",
                     font="boldLabelFont",
                     backgroundColor=(0.0, 0.5, 0.5))
            cmds.rowLayout("exportProcessRow", edit=True, visible=True)
        else:
            # Unknown process - show it anyway, centered, bold
            cmds.text("exportProcessIndicator", edit=True,
                     label="Export Process: %s" % process.title(),
                     align="center",
                     font="boldLabelFont",
                     backgroundColor=(0.4, 0.4, 0.2))
            cmds.rowLayout("exportProcessRow", edit=True, visible=True)
        
        log_message("Export process indicator updated: %s" % process)
    except Exception as e:
        log_message("Error updating export process indicator: %s" % str(e))

def run_skyrim_settings():
    """Run the Export Process settings dialog."""
    script_path = find_export_process_script()
    
    if not script_path:
        error_msg = 'HaxExporterSettings.py not found. Please reinstall the Hax Game Exporter.'
        cmds.warning(error_msg)
        log_message(error_msg)
        return
    
    try:
        # Import and run the settings dialog
        if sys.version_info[0] >= 3:
            import importlib.util
            spec = importlib.util.spec_from_file_location("HaxExporterSettings", script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.show_settings_dialog()
        else:
            import imp
            module = imp.load_source('HaxExporterSettings', script_path)
            module.show_settings_dialog()
    except Exception as e:
        error_msg = 'Error opening settings: %s\n%s' % (str(e), traceback.format_exc())
        cmds.warning(error_msg)
        log_message(error_msg)

def run_skyrim_settings_and_update():
    """Run the Export Process settings dialog and update the indicator after."""
    run_skyrim_settings()
    # Update the indicator after the dialog closes
    update_export_process_indicator()

def run_skyrim_conversion(exported_fbx_paths):
    """
    Run post-export processing on exported FBX files.
    Called after export completes.
    
    Args:
        exported_fbx_paths: List of FBX file paths that were exported
    
    Returns:
        bool: True if successful or no processing needed, False if errors occurred
    """
    script_path = find_export_process_script()
    
    if not script_path:
        # Export process script not found - skip silently
        return True
    
    try:
        # Import and run the processing
        if sys.version_info[0] >= 3:
            import importlib.util
            spec = importlib.util.spec_from_file_location("HaxExporterSettings", script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.process_exported_files(exported_fbx_paths)
        else:
            import imp
            module = imp.load_source('HaxExporterSettings', script_path)
            return module.process_exported_files(exported_fbx_paths)
    except Exception as e:
        log_message('Error in export processing: %s\n%s' % (str(e), traceback.format_exc()))
        return False

# Namespace dropdown and filtering logic
NAMESPACE_MENU = "namespaceDropdown"

def get_all_namespaces():
    # Get all namespaces in the scene
    all_ns = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []
    filtered = [ns for ns in all_ns if ns not in (':UI', ':shared', '')]
    # Get namespaces from reference viewer
    ref_files = cmds.file(q=True, r=True) or []
    ref_namespaces = set()
    for ref in ref_files:
        try:
            ns = cmds.referenceQuery(ref, namespace=True)
            if ns:
                ref_namespaces.add(ns.lstrip(':'))
        except Exception:
            pass
    # Only include namespaces present in both scene and reference viewer
    valid_ns = ['<None>'] + sorted([ns.lstrip(':') for ns in filtered if ns.lstrip(':') in ref_namespaces])
    return valid_ns

def setup_namespace_menu(selected_ns=None):
    if cmds.optionMenu(NAMESPACE_MENU, exists=True):
        cmds.deleteUI(NAMESPACE_MENU)
    cmds.optionMenu(NAMESPACE_MENU, label='Namespace', width=220, annotation='Select a namespace to filter joints',
                    changeCommand=on_namespace_changed)
    # Update: Refresh button now refreshes both Namespace and Preset dropdowns
    def refresh_both_menus(*_):
        refresh_namespace_menu()
        update_preset_menu()
    cmds.button(label="Refresh", width=60, height=18, command=refresh_both_menus, annotation="Refresh namespace and preset list")
    refresh_namespace_menu(selected_ns)

def refresh_namespace_menu(selected_ns=None):
    try:
        if cmds.optionMenu(NAMESPACE_MENU, exists=True):
            # Remove all existing menu items safely
            menu_items = cmds.optionMenu(NAMESPACE_MENU, q=True, itemListLong=True) or []
            for item in menu_items:
                try:
                    cmds.deleteUI(item)
                except Exception as e:
                    log_message('Failed to delete menu item {}: {}'.format(item, str(e)))
            # Repopulate the menu
            namespaces = get_all_namespaces()
            # Always ensure <None> is present and unique
            namespaces = ['<None>'] + [ns for ns in namespaces if ns != '<None>']
            for ns in namespaces:
                cmds.menuItem(label=ns, parent=NAMESPACE_MENU)
            # Validate selection
            if selected_ns in namespaces:
                cmds.optionMenu(NAMESPACE_MENU, edit=True, value=selected_ns)
            else:
                cmds.optionMenu(NAMESPACE_MENU, edit=True, value="<None>")
    except Exception as e:
        log_message('Namespace menu refresh error: {}'.format(str(e)))

def on_namespace_changed(ns):
    save_scene_data()

def get_selected_namespace():
    if cmds.optionMenu(NAMESPACE_MENU, exists=True):
        ns = cmds.optionMenu(NAMESPACE_MENU, q=True, value=True)
        if ns == '<None>':
            return None
        return ns
    return None

def filter_joints_by_namespace(joints, namespace):
    if not namespace or namespace == '<None>':
        return joints
    ns_prefix = namespace + ':'
    return [j for j in joints if j.startswith(ns_prefix)]

# --- Animation Layer State Management ---
import json

ANIM_LAYER_STATES_ATTR = "animLayerStates"

# Helper to get all animation layers in order (lowest to highest priority)
def get_ordered_anim_layers():
    layers = cmds.ls(type='animLayer') or []
    root_layers = cmds.animLayer(query=True, root=True) or []
    def traverse(layer, out):
        if not layer or not cmds.objExists(layer):
            return
        out.append(layer)
        try:
            children = cmds.animLayer(layer, query=True, children=True) or []
        except Exception:
            children = []
        for c in children:
            traverse(c, out)
    ordered = []
    for root in root_layers:
        traverse(root, ordered)
    # Remove duplicates, preserve order
    seen = set()
    result = []
    for l in ordered:
        if l not in seen:
            result.append(l)
            seen.add(l)
    for l in layers:
        if l not in seen:
            result.append(l)
    return result

# Helper to get current anim layer enabled states as a dict
def get_anim_layer_states():
    states = {"Base Animation": True}  # Base always enabled
    for l in get_ordered_anim_layers():
        try:
            states[l] = not bool(cmds.getAttr(l + ".mute"))
        except Exception:
            states[l] = True
    return states

# Helper to set anim layer enabled states from a dict
def set_anim_layer_states(states):
    for l, checked in states.items():
        if l == "Base Animation":
            continue
        if cmds.objExists(l):
            try:
                cmds.setAttr(l + ".mute", not bool(checked))
            except Exception:
                pass

# --- Persistence in custom data node ---

def save_anim_layer_states_to_node():
    node = get_or_create_data_node()
    if not node:
        return
    # Unlock node before adding attribute
    try:
        cmds.lockNode(node, lock=False)
    except Exception:
        pass
    if not cmds.attributeQuery(ANIM_LAYER_STATES_ATTR, node=node, exists=True):
        try:
            cmds.addAttr(node, longName=ANIM_LAYER_STATES_ATTR, dataType="string")
        except Exception:
            pass
    try:
        cmds.setAttr(node + "." + ANIM_LAYER_STATES_ATTR, json.dumps(anim_layer_checkboxes), type="string")
    except Exception:
        pass
    try:
        cmds.lockNode(node, lock=True)
    except Exception:
        pass

def load_anim_layer_states_from_node():
    node = get_or_create_data_node()
    if not node:
        return {"Base Animation": True}
    if cmds.attributeQuery(ANIM_LAYER_STATES_ATTR, node=node, exists=True):
        try:
            val = cmds.getAttr(node + "." + ANIM_LAYER_STATES_ATTR)
            if val:
                return json.loads(val)
        except Exception:
            pass
    return {"Base Animation": True}

# --- UI State ---
# Global dict: {layerName: checked}
anim_layer_checkboxes = {"Base Animation": True}

# --- Rotation Offset UI ---
def build_rotation_offset_ui():
    """Build the rotation offset UI frame."""
    # Remove old UI if exists
    if cmds.frameLayout("rotationOffsetFrame", exists=True):
        cmds.deleteUI("rotationOffsetFrame")
    
    cmds.setParent("mainColumn")
    cmds.frameLayout("rotationOffsetFrame", label="Rotation Offset", 
                     collapsable=True, collapse=False, marginHeight=5)
    cmds.columnLayout("rotationOffsetCol", adjustableColumn=True)
    
    # Enable/disable checkbox
    cmds.checkBox("rotationOffsetEnabled", 
                  label="Enable Rotation Offset", 
                  value=export_settings.get("rotationOffset", {}).get("enabled", False),
                  annotation="Enable rotation offset during export",
                  changeCommand=lambda val: update_rotation_offset_setting("enabled", val))
    
    # Joint/Control selection row
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2,
                   columnAttach=[(1,"left",0),(2,"both",5),(3,"right",0)])
    cmds.text(label="Joint/Control:", annotation="Joint or control to apply rotation offset to")
    cmds.textField("rotationOffsetJoint", 
                   text=export_settings.get("rotationOffset", {}).get("joint", ""),
                   placeholderText="Select joint or control",
                   annotation="Joint or control to apply rotation offset to",
                   changeCommand=lambda val: update_rotation_offset_setting("joint", val))
    cmds.button(label="Grab", width=50, height=18,
                command=grab_rotation_offset_joint,
                annotation="Set to currently selected joint or control")
    cmds.setParent("..")
    
    # Rotation values row
    cmds.rowLayout(numberOfColumns=6, adjustableColumn=1,
                   columnAttach=[(1,"left",0),(2,"both",2),(3,"both",2),(4,"both",2),(5,"both",2),(6,"both",2)])
    cmds.text(label="Rotation XYZ:", annotation="Rotation offset values in degrees")
    cmds.floatField("rotationOffsetX", 
                    value=export_settings.get("rotationOffset", {}).get("rotationX", 0.0),
                    width=60, precision=2,
                    annotation="X rotation offset in degrees",
                    changeCommand=lambda val: update_rotation_offset_setting("rotationX", val))
    cmds.floatField("rotationOffsetY", 
                    value=export_settings.get("rotationOffset", {}).get("rotationY", 0.0),
                    width=60, precision=2,
                    annotation="Y rotation offset in degrees",
                    changeCommand=lambda val: update_rotation_offset_setting("rotationY", val))
    cmds.floatField("rotationOffsetZ", 
                    value=export_settings.get("rotationOffset", {}).get("rotationZ", 0.0),
                    width=60, precision=2,
                    annotation="Z rotation offset in degrees",
                    changeCommand=lambda val: update_rotation_offset_setting("rotationZ", val))
    cmds.text(label="degrees", font="smallObliqueLabelFont")
    cmds.setParent("..")
    
    cmds.setParent("..")
    cmds.setParent("..")

def update_rotation_offset_setting(key, value):
    """Update a rotation offset setting and save to scene data."""
    if "rotationOffset" not in export_settings:
        export_settings["rotationOffset"] = default_export_settings["rotationOffset"].copy()
    export_settings["rotationOffset"][key] = value
    save_scene_data()
    log_message("Updated rotation offset setting: %s = %s" % (key, value))

def grab_rotation_offset_joint(*args):
    """Set the rotation offset joint to the currently selected object."""
    try:
        sel = cmds.ls(selection=True)
        if sel:
            joint_name = sel[0]
            cmds.textField("rotationOffsetJoint", edit=True, text=joint_name)
            update_rotation_offset_setting("joint", joint_name)
            log_message("Set rotation offset joint to: %s" % joint_name)
        else:
            # Clear the field if nothing is selected
            cmds.textField("rotationOffsetJoint", edit=True, text="")
            update_rotation_offset_setting("joint", "")
            log_message("Cleared rotation offset joint")
    except Exception as e:
        error_msg = "Error grabbing rotation offset joint: %s" % str(e)
        cmds.warning(error_msg)
        log_message(error_msg)

# --- UI Creation/Refresh ---
def build_anim_layers_ui():
    global anim_layer_checkboxes
    # Remove old UI if exists
    if cmds.frameLayout("animLayersFrame", exists=True):
        cmds.deleteUI("animLayersFrame")
    cmds.setParent("mainColumn")
    cmds.frameLayout("animLayersFrame", label="Animation Layers", collapsable=True, collapse=False, marginHeight=5)
    cmds.columnLayout("animLayersCol", adjustableColumn=True)
    # Always add Base Animation first
    cmds.checkBox("animLayer_Base Animation", label="Base Animation", value=True, enable=False,
                  annotation="Base Animation layer is always enabled")
    # Get layers in order
    layers = get_ordered_anim_layers()
    # Merge with saved state
    saved = anim_layer_checkboxes.copy()
    # Add any new layers (default to enabled)
    for l in layers:
        if l not in saved:
            saved[l] = True
    # Remove any missing layers
    for l in list(saved.keys()):
        if l != "Base Animation" and l not in layers:
            del saved[l]
    anim_layer_checkboxes = saved
    # Add checkboxes for each layer
    for l in layers:
        normalized = l.strip().replace(' ', '').replace('_', '').lower()
        if normalized == "baseanimation":
            continue  # Skip duplicate or variants
        
        # Check if this layer contains "Base Animation" (from any namespace)
        is_base_animation_variant = "base animation" in l.lower() or "baseanimation" in l.lower()
        
        def make_cb(layer_name):
            def cb(val):
                anim_layer_checkboxes[layer_name] = val
                save_anim_layer_states_to_node()
            return cb
        
        if is_base_animation_variant:
            # Create disabled checkbox without changeCommand
            cmds.checkBox("animLayer_" + l, 
                          label=l, 
                          value=anim_layer_checkboxes.get(l, True), 
                          enable=False)
        else:
            # Create enabled checkbox with changeCommand
            cmds.checkBox("animLayer_" + l, 
                          label=l, 
                          value=anim_layer_checkboxes.get(l, True), 
                          changeCommand=make_cb(l))
    cmds.setParent("..")
    cmds.setParent("..")

# --- UI Integration ---
# In create_ui, after mainColumn and before settingsFrame:
# build_anim_layers_ui()
# In refresh_ui, just before settingsFrame:
# build_anim_layers_ui()

# --- Save/Load Integration ---
# In save_scene_data, after saving other data:
# save_anim_layer_states_to_node()
# In load_scene_data, after loading other data:
# global anim_layer_checkboxes; anim_layer_checkboxes = load_anim_layer_states_from_node()

# --- Export Data Integration ---
# In export_data_command, add anim_layer_checkboxes to the exported text
# In import_text_data, parse and restore anim_layer_checkboxes if present

# --- Export Logic ---
# In export_clips, before exporting, save current anim layer enabled states, set according to anim_layer_checkboxes
# After export, restore original states

if __name__ == "__main__":
    initialize_exporter()
