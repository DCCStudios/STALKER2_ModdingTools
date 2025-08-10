#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Skyrim Special Edition Import Setup Script
This file is executed after importing animation and applying reference pose.
Available variables: cmds, group_name, game_code, print, os
"""

print("// Executing Skyrim SE import setup...")

try:
    # Check if the AnimImport group exists
    if cmds.objExists(group_name):
        # Example: Apply Skyrim-specific transformations
        # cmds.setAttr("{}.rotateX".format(group_name), 0)
        # cmds.setAttr("{}.rotateY".format(group_name), 0)
        # cmds.setAttr("{}.rotateZ".format(group_name), 0)
        
        print("// Skyrim SE setup complete: No specific transformations applied")
    else:
        print("// Warning: {} group not found for Skyrim SE setup".format(group_name))

except Exception as e:
    print("// Error in Skyrim SE setup: {}".format(str(e)))