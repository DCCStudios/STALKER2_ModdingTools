#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
STALKER 2 Import Setup Script
This file is executed after importing animation and applying reference pose.
Available variables: cmds, group_name, game_code, print, os
"""

print("// Executing STALKER 2 import setup...")

try:
    # Check if the AnimImport group exists
    if cmds.objExists(group_name):
        # Rotate the group -90 degrees in Y axis for STALKER 2
        cmds.setAttr("{}.rotateY".format(group_name), -90)
        print("// STALKER 2 setup complete: Rotated {} group -90 degrees in Y axis".format(group_name))
    else:
        print("// Warning: {} group not found for STALKER 2 setup".format(group_name))

except Exception as e:
    print("// Error in STALKER 2 setup: {}".format(str(e)))