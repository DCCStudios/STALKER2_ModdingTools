#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
STALKER 2 Toolkit Installation Test Script
=========================================

This script tests whether the STALKER 2 Toolkit has been correctly installed
with the new subfolder structure and can find all required components.

Usage:
1. Run this script in Maya's script editor
2. Check the script editor output for test results

If all tests pass, your installation is working correctly.
"""

import os
import sys
import importlib
import maya.cmds as cmds
import maya.mel as mel

def test_installation():
    """Test the STALKER 2 Toolkit installation"""
    print("\n" + "="*80)
    print("STALKER 2 Toolkit Installation Test")
    print("="*80)
    
    # Test 1: Check if main toolkit path is in sys.path
    maya_app_dir = cmds.internalVar(userAppDir=True)
    toolkit_dir = os.path.join(maya_app_dir, "scripts", "STALKER2_Toolkit")
    subfolder_path = os.path.join(toolkit_dir, "stalker2_toolkit")
    
    print("\n[Test 1] Checking toolkit paths...")
    paths_found = []
    if toolkit_dir in sys.path:
        print("✓ STALKER2_Toolkit directory is in Python path")
        paths_found.append(toolkit_dir)
    else:
        print("✗ STALKER2_Toolkit directory is NOT in Python path")
        print("  - Adding it now...")
        sys.path.insert(0, toolkit_dir)
        paths_found.append(toolkit_dir)
    
    if subfolder_path in sys.path:
        print("✓ stalker2_toolkit subfolder is in Python path")
        paths_found.append(subfolder_path)
    elif os.path.exists(subfolder_path):
        print("✗ stalker2_toolkit subfolder exists but is NOT in Python path")
        print("  - Adding it now...")
        sys.path.insert(0, subfolder_path)
        paths_found.append(subfolder_path)
    else:
        print("✗ stalker2_toolkit subfolder does not exist")
        print("  - Expected location: {}".format(subfolder_path))
    
    if len(paths_found) == 0:
        print("✗ No toolkit paths found! Installation may be corrupted.")
        return False
    
    # Test 2: Check if main module can be imported
    print("\n[Test 2] Testing toolkit module imports...")
    try:
        import stalker2_toolkit
        print("✓ Successfully imported stalker2_toolkit")
        
        # Check version
        if hasattr(stalker2_toolkit, "__version__"):
            print("  - Version: {}".format(stalker2_toolkit.__version__))
    except ImportError as e:
        print("✗ Failed to import stalker2_toolkit: {}".format(str(e)))
        print("  - Is the main file installed correctly?")
        return False
    
    # Test 3: Check all tool modules
    print("\n[Test 3] Testing individual tool modules...")
    tools_to_test = [
        "stalker2_toolkit.material_texture_matcher",
        "stalker2_toolkit.weapon_importer",
        "stalker2_toolkit.weapon_rig_tool",
        "stalker2_toolkit.PrintSkeletonHierarchy",
        "stalker2_toolkit.asAnimationImporter"
    ]
    
    all_tools_passed = True
    for tool_module in tools_to_test:
        try:
            module = importlib.import_module(tool_module)
            print("✓ Successfully imported {}".format(tool_module))
        except ImportError as e:
            print("✗ Failed to import {}: {}".format(tool_module, str(e)))
            print("  - Is this tool installed in the stalker2_toolkit subfolder?")
            all_tools_passed = False
    
    if not all_tools_passed:
        print("\n⚠️ Not all tool modules were found!")
        print("  - The toolkit may work partially but not all features will be available")
    
    # Test 4: Check for animation_importer_data directory
    print("\n[Test 4] Checking for animation data files...")
    anim_data_dir = os.path.join(subfolder_path, "animation_importer_data")
    if os.path.exists(anim_data_dir):
        print("✓ Found animation_importer_data directory")
        
        # Check essential files
        required_files = [
            "stalker2_reference_pose.json",
            "stalker2_zero_pose.mel",
            "stalker2_import_setup.py",
            "stalker2_anim_cleanup.py"
        ]
        
        for file_name in required_files:
            file_path = os.path.join(anim_data_dir, file_name)
            if os.path.exists(file_path):
                print("  ✓ Found {}".format(file_name))
            else:
                print("  ✗ Missing {}".format(file_name))
                all_tools_passed = False
    else:
        print("✗ animation_importer_data directory not found")
        print("  - Expected location: {}".format(anim_data_dir))
        all_tools_passed = False
    
    # Test 5: Try to show the toolkit UI
    print("\n[Test 5] Testing toolkit UI launch...")
    try:
        # Only import, don't show (to avoid disrupting test)
        import stalker2_toolkit
        print("✓ Ready to show toolkit UI")
        launch_ready = True
    except Exception as e:
        print("✗ Error preparing to launch toolkit: {}".format(str(e)))
        launch_ready = False
    
    # Final results
    print("\n" + "="*80)
    if all_tools_passed and launch_ready:
        print("✅ All tests passed! Your STALKER 2 Toolkit installation is working correctly.")
        print("   You can now use the toolkit by running:")
        print("   import stalker2_toolkit; stalker2_toolkit.show_stalker2_toolkit()")
    else:
        print("⚠️ Some tests failed. Your STALKER 2 Toolkit installation may be incomplete.")
        print("   Try reinstalling the toolkit using the INSTALL_STALKER2_TOOLKIT.mel file.")
    print("="*80 + "\n")
    
    return all_tools_passed and launch_ready

# Run the test when script is executed
test_installation()