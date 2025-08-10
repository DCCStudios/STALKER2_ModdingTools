#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dungeon Crawler Import Setup Script
This file is executed after importing animation and applying reference pose.
Available variables: cmds, group_name, game_code, print, os
"""

print("// Executing Dungeon Crawler import setup...")

try:
    # Check if the AnimImport group exists
    if cmds.objExists(group_name):
        # Example: Apply Dungeon Crawler-specific transformations
        # cmds.setAttr("{}.rotateY".format(group_name), 180)  # Face opposite direction
        # cmds.setAttr("{}.scaleX".format(group_name), -1)    # Mirror X axis
        
        print("// Dungeon Crawler setup complete: No specific transformations applied")
    else:
        print("// Warning: {} group not found for Dungeon Crawler setup".format(group_name))

except Exception as e:
    print("// Error in Dungeon Crawler setup: {}".format(str(e)))