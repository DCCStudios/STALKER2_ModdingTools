from __future__ import print_function
import sys
import maya.cmds as cmds

HELP_WINDOW = "HaxExporterHelpWindow"

help_text = [
    '<span style="font-size:14pt; font-weight:bold; color:#2a7ae2;">Hax Game Exporter - Help</span><br><br>',
    '<b style="color:#e67e22;">Presets:</b> <span style="color:#cccccc;">Save and load sets of export settings, root joints, animation layer states, and rotation offset settings. Use the dropdown to select, the Save Preset button to save, and Add/Remove Joints to manage root joints for each preset. When a preset is selected, you can choose to update the current preset or create a new one. When selecting a preset, if any joints use a valid namespace, you will be prompted to set the Namespace dropdown accordingly. <b>Presets are stored in the hax_exporter_data folder in your maya scripts directory and can be shared!</b></span><br><br>',
    '<b style="color:#e67e22;">Namespace Dropdown:</b> <span style="color:#cccccc;">Filter joints by namespace for export. The dropdown only shows namespaces present in both the scene and the reference viewer. Use the Refresh button to update both the Namespace and Preset dropdowns. If a preset contains joints with a valid namespace, you will be prompted to set the Namespace dropdown after the UI is drawn.</span><br><br>',
    '<b style="color:#e67e22;">Animation Clips:</b> <span style="color:#cccccc;">Define multiple animation clips for export. Each clip has a name, start/end frames, FPS, and enable/disable toggle. Use the checkboxes to select which clips to export. Use the up/down arrows to reorder, and the duplicate/delete buttons to manage clips. The <b>Frame</b> button applies the clip\'s frame range to the timeline, while the <b>Set</b> button captures the current timeline range and sets it to the clip.</span><br><br>',
    '<b style="color:#e67e22;">Animation Layers:</b> <span style="color:#cccccc;">Control which animation layers are active during export. Check/uncheck layers to enable or disable them for the export process. The original layer states are restored after export. <b>Base Animation</b> layers (including those from different namespaces) are automatically grayed out and cannot be disabled. Layer states are saved with your scene data and included in presets and text exports.</span><br><br>',
    '<b style="color:#e67e22;">Rotation Offset:</b> <span style="color:#cccccc;">Apply a rotation offset to a specific joint or control during export using an additive animation layer. Enable the checkbox, select a joint/control using the Grab button, and set X/Y/Z rotation values in degrees. The offset is keyed on the first frame, baked during export, and the animation layer is automatically deleted afterward. Rotation offset settings are saved with presets and scene data.</span><br><br>',
    '<b style="color:#e67e22;">Export Path &amp; Prefix:</b> <span style="color:#cccccc;">Set the folder where FBX files will be exported and a filename prefix. The filename preview updates in real time as you edit these fields or the clip name. <b>The prefix is always respected, even after loading a preset or editing the field right before export.</b></span><br><br>',
    '<b style="color:#e67e22;">Overwrite Dialog:</b> <span style="color:#cccccc;">When exporting, if a file already exists, the overwrite confirmation dialog now always shows the full filename (including prefix) for clarity.</span><br><br>',
    '<b style="color:#e67e22;">Export Mode:</b> <span style="color:#cccccc;">Choose between exporting all clips or only the checked (enabled) clips.</span><br><br>',
    '<b style="color:#e67e22;">Settings:</b> <span style="color:#cccccc;">Choose FBX file type (Binary/ASCII), FBX version, and options like Embed Media, Bake Animation, and Move To Origin. <b>Move To Origin</b> now zeroes both translation and rotation of the root joint during export, and restores them after export. <b>Alt Root Control:</b> Use the Grab button to set the control from your current selection, or clear the field if nothing is selected.</span><br><br>',
    '<b style="color:#e67e22;">Import/Export Data:</b> <span style="color:#cccccc;">Import animation clip data from Maya Game Exporter or a text file, and export your current clip data for backup or sharing.</span><br><br>',
    '<b style="color:#e67e22;">Logging:</b> <span style="color:#cccccc;">All actions, errors, and warnings are logged to HaxExporterOutputLog.txt in your Maya project directory. Use the Open Log button to view it. The UI is robust against errors and will log issues instead of showing disruptive dialogs. <b>Note:</b> UI field values are always up-to-date before export, even if you edit them immediately before exporting.</span><br><br>',
    '<b style="color:#e67e22;">Export Confirmation:</b> <span style="color:#cccccc;">After a successful export, you will see a confirmation popup with a random famous anime quote for a bit of fun and motivation!</span><br><br>',
    '<b style="color:#e74c3c;">Tips:</b> <span style="color:#cccccc;">- Double-check your export path and prefix before exporting.<br>- Use presets to quickly switch between different export setups.<br>- Use the Refresh button if you add or remove namespaces or presets.<br>- If you encounter errors, check the log file for details.<br>- When prompted about namespaces, it is usually best to confirm so your export matches the intended joint set.<br>- Use the Set button to quickly capture timeline ranges for clips.<br>- Animation layer states are preserved and restored after export.<br>- Rotation offsets use additive animation layers for clean, non-destructive edits.<br>- The tool is compatible with both Python 2 and 3 in Maya.</span>',
]

help_html = "".join(help_text)


def show_hax_exporter_help():
    if cmds.window(HELP_WINDOW, exists=True):
        cmds.deleteUI(HELP_WINDOW)
    win = cmds.window(HELP_WINDOW, title="Hax Game Exporter Help", widthHeight=(500, 400), sizeable=True)
    cmds.scrollLayout(childResizable=True)
    cmds.separator(height=10, style="none")
    cmds.text(label="", align="left")  # Spacer
    cmds.text(label=help_html, align="left", wordWrap=True, enable=True, useTemplate="", font="boldLabelFont")
    cmds.separator(height=10, style="none")
    cmds.setParent("..")
    cmds.showWindow(win)

show_hax_exporter_help() 