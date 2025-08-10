# STALKER 2 Toolkit for Maya

A comprehensive toolkit designed specifically for STALKER 2 modding workflows in Autodesk Maya.

## 📥 INSTALLATION

### Quick Installation (Recommended)
1. **Download or clone** this repository to your computer
2. **Drag** `Scripts/INSTALL_STALKER2_TOOLKIT.mel` into Maya's viewport
3. **Follow** the on-screen prompts (including installing the Animation Exporter when prompted)
4. **Access** the toolkit using the new "STALKER2" shelf button

### Manual Installation
1. Copy files from `Scripts` folder to Maya's scripts directory:
   - Windows: `Documents/maya/[version]/scripts/`
   - Mac: `~/Library/Preferences/Autodesk/maya/[version]/scripts/`
2. Ensure `animation_importer_data` and `hax_exporter_data` folders are directly in the scripts directory
3. Launch with: `import stalker2_toolkit; stalker2_toolkit.show_stalker2_toolkit()`

## ⚙️ Tools Overview

### Material-Texture Matcher
- **Purpose**: Automatically assigns textures to materials based on naming conventions
- **Workflow**: Select mesh objects → browse to texture directory → assign textures
- **Naming**: Materials (`MI_*`) → Textures (`T_*_D.png`, `T_*_N.png`)

### Weapon Importer
- **Purpose**: Import weapon skeletons and constrain mesh parts automatically
- **Features**: 
  - Smart joint-mesh association
  - Automatic constraint generation
  - Animation import from FBX files
  - Load completed rigs into the scene
  - Load Animations onto weapon rigs

### Weapon Rig Tool
- **Purpose**: Create animation-ready control rigs for weapons
- **Features**:
  - Smart control shape detection
  - Automatic constraint setup
  - Animation-friendly transform matching
  - Support for all weapon parts

### Animation Importer
- **Purpose**: Import game animations with advanced options for the Character Rig
- **Features**:
  - Reference pose application
  - Automatic frame range setting
  - Advanced Skeleton integration


### Animation Exporter (Highly Recommended)
- **Purpose**: Export animations with proper game-ready settings
- **Features**:
  - Optimized export presets for STALKER 2
  - Animation clip management
  - Batch export capabilities
  - FBX compatibility options

### Animation Retargeting Tool by Joar Engberg
- **Purpose**: Transfer animations between skeletons or from mocap to custom rigs
- **Features**:
  - Weapon animation presets
  - Intelligent joint-control mapping
  - Post-bake operations
  - Support for namespace handling

### Print Skeleton Hierarchy
- **Purpose**: Generate reference pose data for animation workflows
- **Features**:
  - Exports joint data to JSON and MEL
  - Supports Animation Importer configuration
  - Joint transform recording

## 🔧 Usage

### Opening the Toolkit
- **Shelf Button**: Click the "STALKER2" button on your shelf
- **Script Editor**: Run `import stalker2_toolkit; stalker2_toolkit.show_stalker2_toolkit()`

### Typical Workflows

**Weapon Animation Workflow**:
1. Use Weapon Importer to import the weapon model and skeleton
2. Use Weapon Rig Tool to create control curves for animation
3. Use Animation Importer to import animation onto the weapon
4. Use Animation Retargeting Tool for fine-tuning animations
5. Use Animation Exporter to export the final animation

**Material Setup Workflow**:
1. Import mesh with materials (ensure `MI_` prefix on materials)
2. Use Material-Texture Matcher to find and assign textures
3. Review and adjust material settings if needed

## 🔍 Troubleshooting

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

## 🔄 Compatibility

- **Maya Versions**: 2025+ (Python 3, PySide6) and earlier (Python 2, PySide2)
- **Operating Systems**: Windows, macOS, Linux
- **Required Components**: 
  - Animation Exporter (highly recommended)
  - animation_importer_data folder
  - hax_exporter_data folder

## 💻 Development

This toolkit is designed for expansion. To add new tools:

1. Create your tool script in the Scripts folder
2. Add the tool to stalker2_toolkit.py in the appropriate section
3. Update the installer's file lists if needed
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

*Version 1.1 - Compatible with all Maya versions*