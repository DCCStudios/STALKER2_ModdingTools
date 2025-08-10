#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Fallout New Vegas Import Setup Script
This file is executed after importing animation and applying reference pose.
Available variables: cmds, group_name, game_code, print, os
"""

print("// Executing Fallout New Vegas import setup...")

try:
    # Check if the AnimImport group exists
    if cmds.objExists(group_name):
        # Example: Scale the group for Fallout NV (adjust as needed)
        # cmds.setAttr("{}.scaleX".format(group_name), 1.0)
        # cmds.setAttr("{}.scaleY".format(group_name), 1.0)
        # cmds.setAttr("{}.scaleZ".format(group_name), 1.0)
        
        print("// Fallout New Vegas setup complete: No specific transformations applied")
    else:
        print("// Warning: {} group not found for Fallout New Vegas setup".format(group_name))

except Exception as e:
    print("// Error in Fallout New Vegas setup: {}".format(str(e)))