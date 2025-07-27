# STALKER 2 Toolkit for Maya

A comprehensive toolkit designed specifically for STALKER 2 modding workflows in Autodesk Maya.

## Features

- **Cross-Maya Version Compatibility**: Works with Maya 2025+ (Python 3, PySide6) and earlier versions (Python 2, PySide2)
- **Dark Mode UI**: Modern interface consistent with STALKER 2 aesthetic
- **Drag & Drop Installation**: Simple one-click installation process
- **Custom STALKER 2 Icon**: Professional shelf button with authentic STALKER branding
- **Modular Design**: Easy to expand with additional tools

## Current Tools

### Material-Texture Matcher
Automatically assigns textures to materials based on strict naming conventions:
- **Material Prefix**: `MI_` (e.g., `MI_arm_ban_06_a`)
- **Texture Prefix**: `T_` (e.g., `T_arm_ban_06_a_D.png`)
- **Supported Textures**: 
  - `_D` (Diffuse/Albedo)
  - `_N` (Normal maps)
- **Ignored Textures**: `_RMA` and other types
- **Strict Matching**: 90%+ similarity required to prevent incorrect assignments

### Weapon Importer
Import weapon skeletons and automatically constrain associated mesh parts:
- **Skeleton Files**: `SK_` prefix (e.g., `SK_AK74.FBX`)
- **Mesh Parts**: Any FBX files without `SK_` prefix
- **Joint Analysis**: Extracts joints with `jnt_` prefix from skeleton
- **Smart Matching**: Intelligent algorithm matches mesh files to joints based on naming
- **Auto-Constraints**: Creates position and rotation constraints automatically
- **Organization**: Optional grouping into `S2_Weapon > S2_Skeleton + S2_Mesh`

### Weapon Rig Tool
Create control curves for rigged weapons with intelligent automation:
- **Scene Analysis**: Automatically detects joint-mesh constraints from Weapon Importer
- **Control Shapes**: Auto-detects optimal shapes (sphere/cube/cylinder) based on mesh dimensions
- **Smart Sizing**: Calculates appropriate control scale from mesh bounding boxes
- **Transform Matching**: Controls inherit joint positions/rotations for seamless animation transfer
- **Complete Rigs**: Full rig setup with organized hierarchy and constraint systems
- **Rig Management**: Tools to select, delete, and manage existing weapon rigs

## Installation

### Method 1: Drag & Drop (Recommended)
1. **Download** or copy all files to your computer
2. **Drag** `INSTALL_STALKER2_TOOLKIT.mel` into Maya's viewport
3. **Wait** for installation to complete
4. **Click** the new "STALKER2" button on your shelf

### Method 2: Manual Installation
1. Copy the `Scripts` folder to Maya's scripts directory:
   - **Windows**: `Documents/maya/[version]/scripts/`
   - **Mac**: `~/Library/Preferences/Autodesk/maya/[version]/scripts/`
   - **Linux**: `~/maya/[version]/scripts/`
2. Run in Maya's Script Editor:
   ```python
   import stalker2_toolkit
   stalker2_toolkit.show_stalker2_toolkit()
   ```

## Usage

### Opening the Toolkit
- **Shelf Button**: Click the "STALKER2" button on your shelf
- **Script Editor**: Run `import stalker2_toolkit; stalker2_toolkit.show_stalker2_toolkit()`

### Using Material-Texture Matcher
1. **Select** mesh objects with materials assigned (materials must have `MI_` prefix)
2. **Open** STALKER 2 Toolkit from shelf button
3. **Click** "Material-Texture Matcher" button
4. **Browse** to directory containing textures (with `T_` prefix)
5. **Click** "Assign Textures"
6. **Review** results in the popup dialog

### Using Weapon Importer
1. **Prepare** weapon files in directory with `SK_` skeleton and mesh FBX files
2. **Open** STALKER 2 Toolkit from shelf button  
3. **Click** "Weapon Importer" button
4. **Set** master path to your STALKER2_ModdingTools directory
5. **Select** weapon category and specific weapon
6. **Review** joint-mesh associations in the analysis panel
7. **Click** "Import Weapon" to import with automatic constraints
8. **Optional**: Use "Create Weapon Directory" to set up folder structure

### Using Weapon Rig Tool
1. **Import** a weapon first using the Weapon Importer
2. **Open** STALKER 2 Toolkit and click "Weapon Rig Tool"
3. **Review** scene analysis showing detected joint-mesh constraints
4. **Choose** control options (auto-shape detection recommended)
5. **Click** "Create Complete Weapon Rig" for full setup
6. **Animate** using the generated control curves instead of joints directly

### Example Naming Convention
```
Materials:          Textures:
MI_arm_ban_06_a  →  T_arm_ban_06_a_D.png  (Diffuse)
                 →  T_arm_ban_06_a_N.png  (Normal)

Weapons:            Structure:
SK_AK74.FBX      →  Skeleton file
SM_ak_mag_full.FBX → Magazine mesh
SM_wpn_ak74_trigger.FBX → Trigger mesh

MI_glo_gen_01_b  →  T_glo_gen_01_b_01_D.png
                 →  T_glo_gen_01_b_01_N.png
```

## File Structure

```
STALKER2_ModdingTools/
└── Scripts/
    ├── INSTALL_STALKER2_TOOLKIT.mel     # Drag & drop installer
    ├── README_STALKER2_TOOLKIT.md       # This file
    ├── stalker2_toolkit.py              # Main UI toolkit
    ├── material_texture_matcher.py      # Material-Texture Matcher
    ├── weapon_importer.py               # Weapon Importer
    ├── weapon_rig_tool.py               # Weapon Rig Tool
    └── STAT_Icon.png                    # Custom STALKER 2 shelf icon
```

## Compatibility

### Maya Versions
- **Maya 2025+**: Python 3 + PySide6 + shiboken6
- **Maya 2022 and earlier**: Python 2 + PySide2 + Shiboken2

### Operating Systems
- Windows 10/11
- macOS 10.14+
- Linux (CentOS 7+, Ubuntu 18.04+)

## Troubleshooting

### Installation Issues

**Problem**: "Could not find installer script"
- **Solution**: Ensure all toolkit files are in the Scripts directory with `INSTALL_STALKER2_TOOLKIT.mel`

**Problem**: "PySide is not available"
- **Solution**: This is expected in some Maya configurations. The toolkit will still work, but without UI dialogs.

**Problem**: Shelf button not created
- **Solution**: Run manually: `import stalker2_toolkit; stalker2_toolkit.show_stalker2_toolkit()`

### Usage Issues

**Problem**: "No materials found on selected objects"
- **Solution**: Ensure objects have materials assigned and materials start with `MI_` prefix

**Problem**: "No textures found in selected directory"
- **Solution**: Ensure texture files start with `T_` prefix and are valid image formats (.png, .jpg, .tif, .exr)

**Problem**: Materials not matching textures
- **Solution**: Check naming conventions. The tool requires 90%+ similarity between material and texture names (excluding prefixes and suffixes)

**Problem**: "No skeleton file found in weapon directory"
- **Solution**: Ensure the weapon directory contains an `SK_` prefixed FBX file

**Problem**: "No joint-mesh constraints found"
- **Solution**: Import a weapon using the Weapon Importer first, which creates the necessary constraints for the Rig Tool

**Problem**: Control curves not appearing at correct size
- **Solution**: Adjust the "Control Scale Multiplier" in the Weapon Rig Tool options

**Problem**: "Could not constrain joint to control"
- **Solution**: Ensure joints and controls exist and are not locked. Check Maya's constraint system for conflicts

### Performance

**Problem**: Slow texture assignment
- **Solution**: This is normal for large numbers of materials. Check console output for progress.

**Problem**: Weapon import taking long time
- **Solution**: This is normal for complex weapons with many mesh parts. Joint analysis includes FBX import which can be slow.

## Uninstalling

To remove the toolkit:
```python
import install_stalker2_toolkit
install_stalker2_toolkit.uninstall_stalker2_toolkit()
```

Or manually:
1. Delete the `STALKER2_Toolkit` folder from Maya's scripts directory
2. Remove the "STALKER2" button from your shelf

## Future Updates

Planned features for upcoming releases:
- **UV Tools**: UV mapping and optimization utilities
- **Mesh Utilities**: Mesh processing and validation tools
- **Animation Tools**: Animation import/export helpers
- **Asset Validation**: STALKER 2 asset compliance checking
- **Batch Processing**: Bulk operations for multiple files

## Support

### Common Workflows

1. **Importing STALKER 2 Assets**:
   - Import meshes and materials
   - Use Material-Texture Matcher to auto-assign textures
   - Validate UV mapping with UV Tools (coming soon)

2. **Working with Weapons**:
   - Use Weapon Importer to import skeletons and meshes with automatic constraints
   - Use Weapon Rig Tool to create animation-ready control rigs
   - Animate weapon parts using control curves instead of joints directly

3. **Creating New Assets**:
   - Follow STALKER 2 naming conventions
   - Use mesh utilities for optimization (coming soon)
   - Export with animation tools (coming soon)

### Best Practices

- Always use proper naming conventions (`MI_` for materials, `T_` for textures, `SK_` for skeletons)
- Keep texture variants numbered consistently (`_01`, `_02`, etc.)
- Organize textures in dedicated folders
- Test assignments on small sets before processing large batches
- For weapons: Import with Weapon Importer first, then use Weapon Rig Tool for animation
- Use auto-shape detection in Weapon Rig Tool for optimal control curve shapes
- Always organize imported assets using the grouping options for cleaner scenes

### Error Reporting

If you encounter issues:
1. Check Maya's Script Editor for detailed error messages
2. Verify file and folder permissions
3. Ensure all files are in correct locations
4. Check Maya version compatibility

## Development

This toolkit is designed for expansion. To add new tools:

1. Create your tool script in the `Scripts` folder
2. Add the tool to `stalker2_toolkit.py` in the appropriate section
3. Update the installer's `script_files` list if needed
4. Follow the existing dark mode styling conventions

### API Example

```python
# Adding a new tool to the main UI
new_section = self.create_section("Your Tool Category", [
    ("Tool Name", "Tool description", self.your_callback_function),
])
```

---

**Developed for the STALKER 2 modding community**

*Version 1.0 - Compatible with all Maya versions* 