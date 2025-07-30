# STALKER2 Modding Tools

A comprehensive collection of tools and rigs for STALKER 2 modding in Autodesk Maya, including an advanced Maya toolkit and pre-built character rigs.

## STALKER2 Maya Toolkit

A powerful suite of Maya tools designed specifically for STALKER 2 modding workflows with cross-Maya version compatibility and modern UI.

### Key Features

- **Cross-Maya Version Compatibility**: Works with Maya 2025+ (Python 3, PySide6) and earlier versions (Python 2, PySide2)
- **Dark Mode UI**: Modern interface consistent with STALKER 2 aesthetic
- **Drag & Drop Installation**: Simple one-click installation process
- **Custom STALKER 2 Icon**: Professional shelf button with authentic STALKER branding

### Included Tools

#### Material-Texture Matcher
- Automatically assigns textures to materials based on STALKER 2 naming conventions
- Supports `MI_` material prefixes and `T_` texture prefixes
- Handles Diffuse (`_D`) and Normal (`_N`) maps with intelligent matching
- Requires 90%+ similarity for accurate assignments

#### Weapon Importer
- Import weapon skeletons (`SK_` prefix) with automatic mesh constraint setup
- Smart joint analysis and mesh-to-joint matching algorithms
- Auto-creates position and rotation constraints for weapon parts
- Optional grouping into organized `S2_Weapon > S2_Skeleton + S2_Mesh` hierarchies

#### Weapon Rig Tool
- Create control curves for rigged weapons with intelligent automation
- Auto-detects optimal control shapes (sphere/cube/cylinder) based on mesh dimensions
- Smart sizing calculated from mesh bounding boxes
- Complete rig setup with organized hierarchy and constraint systems
- Rig management tools for selecting, deleting, and managing existing weapon rigs

### Installation

#### Method 1: Drag & Drop (Recommended)
1. **Download** or copy all files to your computer
2. **Drag** `Scripts/INSTALL_STALKER2_TOOLKIT.mel` into Maya's viewport
3. **Wait** for installation to complete
4. **Click** the new "STALKER2" icon on your shelf (it looks like the STALKER logo guy)

#### Method 2: Manual Installation
1. Copy the `Scripts` folder to Maya's scripts directory:
   - **Windows**: `Documents/maya/[version]/scripts/`
   - **Mac**: `~/Library/Preferences/Autodesk/maya/[version]/scripts/`
   - **Linux**: `~/maya/[version]/scripts/`
2. Run in Maya's Script Editor:
   ```python
   import stalker2_toolkit
   stalker2_toolkit.show_stalker2_toolkit()
   ```

### Quick Start
1. Open Maya and click the "STALKER2" shelf button (after installation)
2. For textures: Select meshes with `MI_` materials → Material-Texture Matcher → Browse to `T_` texture folder
3. For weapons: Weapon Importer → Select weapon directory with `SK_` skeleton → Import with constraints
4. For animation: Weapon Rig Tool → Create Complete Weapon Rig → Animate using control curves

## 🎭 Advanced Skeleton Rig

Pre-built character rig using Advanced Skeleton system for STALKER 2 character animation.

### Features
- **Complete STALKER 2 Character Rig**: Ready-to-use rig file (`Rig/S2_Rig.mb`)
- **Advanced Skeleton Integration**: Built with professional Advanced Skeleton system
- **Name Matcher Configuration**: Custom STALKER 2 bone mapping (`AdvancedSkeleton/NameMatcher/STALKER2.ma`)
- **Reference-Ready**: Designed to be referenced into animation scenes

### Setup Instructions

#### Prerequisites
1. **Advanced Skeleton Plugin** (Optional): The full Advanced Skeleton toolkit is only required if you want to edit the rig in some way, otherwise just install the picker
2. **Picker Tool (Recommended)**: Download the Advanced Skeleton picker to use the rig
   - **Download**: [SelectorAndPickerOnly.7z](https://www.animationstudios.com.au/download/SelectorAndPickerOnly.7z)
   - Extract and install according to Advanced Skeleton documentation

#### Using the Rig
1. **Create New Scene**: Start with a fresh Maya scene for your animation
2. **Reference the Rig**: 
   - Go to `File > Create Reference`
   - Navigate to `Rig/S2_Rig.mb`
   - Reference (don't import) the rig into your scene
3. **Use Picker Tool**: Load the Advanced Skeleton picker for intuitive character control selection

#### Important Notes
- **⚠️ Never animate directly in `S2_Rig.mb`** - Always reference it into a new scene
- The rig is designed for referencing to maintain file integrity and allow for updates
- Use the picker tool for efficient animator workflow and control selection

## 📁 File Structure (subject to change)

```
STALKER2_ModdingTools/
├── Scripts/                          # Maya Toolkit
│   ├── INSTALL_STALKER2_TOOLKIT.mel  # Drag & drop installer
│   ├── stalker2_toolkit.py           # Main UI toolkit
│   ├── material_texture_matcher.py   # Texture assignment tool
│   ├── weapon_importer.py            # Weapon import automation
│   ├── weapon_rig_tool.py            # Weapon rigging tool
│   └── README_STALKER2_TOOLKIT.md    # Detailed toolkit documentation
├── Rig/                              # Character Rigs
│   └── S2_Rig.mb                     # Main STALKER 2 character rig
├── AdvancedSkeleton/                 # Advanced Skeleton Configuration
│   └── NameMatcher/
│       ├── STALKER2.ma               # Bone mapping configuration
│       └── STALKER2.txt              # Mapping reference
├── Source/                           # Asset Sources
│   ├── Characters/                   # Character meshes and skeletons
│   ├── Player/                       # Player character assets
│   └── Weapons/                      # Weapon assets and references
└── Workspace/                        # Maya workspace directory
```

## 🎯 Workflow Examples

### Character Animation Workflow
1. Reference `Rig/S2_Rig.mb` into new scene
2. Load Advanced Skeleton picker tool
3. Import character meshes and bind to rig
4. Animate using picker controls
5. Select the jnt_root bone and then in the toolbar, go to Select--> Hierarchy to select the entire bone chain
6. Make sure the "ExportLayer" Anim layer is enabled, it will correct the rotation of the hips so that the animation works in-engine
7. Export animation data using the Maya Game Exporter (there will be a custom exporter added soon that is much nicer)

### Weapon Modding Workflow
1. Use Weapon Importer to import weapon skeleton and meshes
2. Apply textures using Material-Texture Matcher
3. Create animation rig using Weapon Rig Tool
4. Animate weapon parts using generated control curves
5. Export completed weapon

### Asset Integration Workflow
1. Import STALKER 2 assets from the Zone Kit to the proper `Source/` directories
2. Use Material-Texture Matcher for automatic texture assignment (just direct it to where you exported the textures)
3. Validate naming conventions in maya and in your source texture folder (`MI_` materials, `T_` textures)
4. Integrate with character or weapon rigs as needed

## 🔧 System Requirements

- **Maya Versions**: 2022 or later (2025+ recommended)
- **Operating Systems**: Windows 10/11, macOS 10.14+, Linux (CentOS 7+, Ubuntu 18.04+)
- **Advanced Skeleton Picker**: Required for character rig functionality
- **Python** (Should be already installed with Maya, any additional libraries will be installed by the S2 Toolkit): Automatic detection (Python 2 for Maya ≤2022, Python 3 for Maya 2025+)

## 📚 Documentation

- **Detailed Toolkit Guide**: See `Scripts/README_STALKER2_TOOLKIT.md` for comprehensive toolkit documentation
- **Troubleshooting**: Common issues and solutions included in toolkit documentation
- **Advanced Skeleton**: Refer to Advanced Skeleton official documentation for rig customization

## 🤝 Community

Developed for the STALKER 2 modding community. These tools follow STALKER 2 asset conventions and naming standards.

---
