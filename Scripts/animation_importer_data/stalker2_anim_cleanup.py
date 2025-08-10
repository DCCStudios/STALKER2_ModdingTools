#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
STALKER 2 Animation Cleanup Script
This file is executed after MoCap matching for post-processing operations.
Available variables: cmds, game_code, print, os, self
"""

# Import maya.mel for direct MEL execution
import maya.mel

print("// Executing STALKER 2 animation cleanup...")

def find_joint_in_animimport_group(joint_name):
    """Find a joint by name within the AnimImport group or in the scene, handling namespaces"""
    # Check for AnimImport groups including those in namespaces
    group_name = "AnimImport"
    descendants = []
    found_group = False
    
    # First check for direct AnimImport group
    if cmds.objExists(group_name):
        found_group = True
        group_descendants = cmds.listRelatives(group_name, allDescendents=True, type="joint")
        if group_descendants:
            descendants.extend(group_descendants)
            print(f"// Found {len(group_descendants)} joints in AnimImport group")
    
    # Look for AnimImport in all potential namespaces
    # First check for explicit namespaced AnimImport groups
    namespaced_groups = cmds.ls("*:AnimImport")
    for ns_group in namespaced_groups:
        found_group = True
        ns_descendants = cmds.listRelatives(ns_group, allDescendents=True, type="joint")
        if ns_descendants:
            descendants.extend(ns_descendants)
            print(f"// Found {len(ns_descendants)} joints in {ns_group}")
    
    # Check for S2_Animation_Import group specifically
    s2_group = "S2_Animation_Import"
    if cmds.objExists(s2_group):
        found_group = True
        s2_descendants = cmds.listRelatives(s2_group, allDescendents=True, type="joint")
        if s2_descendants:
            descendants.extend(s2_descendants)
            print(f"// Found {len(s2_descendants)} joints in {s2_group}")
            
    # Look for any S2_Animation_Import in namespaces as well
    s2_namespaced_groups = cmds.ls("*:S2_Animation_Import")
    for s2_ns_group in s2_namespaced_groups:
        found_group = True
        s2_ns_descendants = cmds.listRelatives(s2_ns_group, allDescendents=True, type="joint")
        if s2_ns_descendants:
            descendants.extend(s2_ns_descendants)
            print(f"// Found {len(s2_ns_descendants)} joints in {s2_ns_group}")
    
    # If no group found, search all joints
    if not found_group or not descendants:
        print("// Searching for joints in entire scene (No animation import group found)")
        descendants = cmds.ls(type="joint")
        
    if not descendants:
        return None
    
    # First try exact match
    for joint in descendants:
        short_name = joint.split(":")[-1] if ":" in joint else joint
        if short_name == joint_name:
            print("// Found joint match: {} -> {}".format(joint_name, joint))
            return joint
    
    # Then look for jnt_[side]_ pattern vs just 'jnt_' pattern
    l_version = joint_name.replace("jnt_l_", "jnt_left_")
    r_version = joint_name.replace("jnt_r_", "jnt_right_")
    
    variations = [
        joint_name,
        joint_name.replace("jnt_", ""),  # Without jnt_ prefix
        "jnt_" + joint_name if not joint_name.startswith("jnt_") else joint_name,  # With jnt_ prefix
        l_version,
        r_version,
        joint_name.replace("_", "")  # Without underscores
    ]
    
    # Check for all variations
    for variation in variations:
        for joint in descendants:
            short_name = joint.split(":")[-1] if ":" in joint else joint
            if variation == short_name:
                print("// Found joint match: {} -> {} (variation: {})".format(joint_name, joint, variation))
                return joint
    
    # If still not found, try partial matches
    for joint in descendants:
        short_name = joint.split(":")[-1] if ":" in joint else joint
        if joint_name in short_name or short_name in joint_name:
            print("// Found partial joint match: {} -> {}".format(joint_name, joint))
            return joint
    
    print("// Could not find joint: {} (looked through {} joints)".format(joint_name, len(descendants)))
    return None

try:
    # Check if an Advanced Skeleton control is selected
    selection = cmds.ls(selection=True)
    as_control_selected = False
    
    for obj in selection:
        # Check if it's an AS control (FK, IK, etc.)
        if any(prefix in obj for prefix in ["FK", "IK", "Main", "Root"]):
            as_control_selected = True
            break
    
    if not as_control_selected:
        cmds.confirmDialog(
            title="Select Advanced Skeleton Control",
            message="Please select any Advanced Skeleton control first, then run Anim Cleanup again.",
            button=["OK"]
        )
        print("// Please select an Advanced Skeleton control first.")
    else:
        # Perform STALKER 2 specific joint alignments using animation layers
        # Add multiple possible names for the joints to handle naming variations
        alignments = [
            ("FKSpine1_M", "jnt_spine_01"),
            ("FKSpine2_M", "jnt_spine_02"),
            ("FKChest_M", "jnt_spine_03"),
            ("FKScapula_L", "jnt_l_shoulder"),
            ("FKScapula_R", "jnt_r_shoulder"), 
            ("FKShoulder_L", "jnt_l_arm"),
            ("FKShoulder_R", "jnt_r_arm"),
            ("FKArmRoll_R", "jnt_r_arm_roll"),
            ("FKArmRoll_L", "jnt_l_arm_roll"),
            # Use both forearm and fore_arm variations for these joints
            ("FKElbow_L", "jnt_l_fore_arm"),  # Updated to match STALKER2.txt naming
            ("FKElbow_R", "jnt_r_fore_arm"),   # Updated to match STALKER2.txt naming
            ("FKForearm_R", "jnt_r_fore_arm_roll"),   # Updated to match STALKER2.txt naming
            ("FKForearm_L", "jnt_l_fore_arm_roll"),   # Updated to match STALKER2.txt naming
            ("FKForearmLeft_R", "jnt_r_fore_arm_left"),   # Updated to match STALKER2.txt naming
            ("FKForearmDown_R", "jnt_r_fore_arm_down"),   # Updated to match STALKER2.txt naming
            ("FKForearmRight_R", "jnt_r_fore_arm_right"),   # Updated to match STALKER2.txt naming
            ("FKForearmUp_R", "jnt_r_fore_arm_up"),   # Updated to match STALKER2.txt naming
            ("FKForearmLeft_L", "jnt_l_fore_arm_left"),   # Updated to match STALKER2.txt naming
            ("FKForearmDown_L", "jnt_l_fore_arm_down"),   # Updated to match STALKER2.txt naming
            ("FKForearmRight_L", "jnt_l_fore_arm_right"),   # Updated to match STALKER2.txt naming
            ("FKForearmUp_L", "jnt_l_fore_arm_up"),   # Updated to match STALKER2.txt naming
            # Additional joints requested by user
            ("FKWrist_R", "jnt_r_hand"),       # Right hand/wrist alignment
            ("FKWrist_L", "jnt_l_hand"),
            ("FKWeapon_M", "jnt_weapon"),      # Weapon joint alignment - fixed name
            ("FKCamera_M", "jnt_camera"),       # Camera joint alignment
            # Finger joints
            ("FKThumbFinger1_L", "jnt_l_hand_thumb_01"),
            ("FKThumbFinger2_L", "jnt_l_hand_thumb_02"),
            #("FKThumbFinger3_L", "jnt_l_hand_thumb_03"), seems not to line up properly
            ("FKIndexFinger0_L", "jnt_l_hand_index_meta"),
            ("FKIndexFinger1_L", "jnt_l_hand_index_01"),
            ("FKIndexFinger2_L", "jnt_l_hand_index_02"),
            ("FKIndexFinger3_L", "jnt_l_hand_index_03"),
            ("FKMiddleFinger0_L", "jnt_l_hand_middle_meta"),
            ("FKMiddleFinger1_L", "jnt_l_hand_middle_01"),
            ("FKMiddleFinger2_L", "jnt_l_hand_middle_02"),
            ("FKMiddleFinger3_L", "jnt_l_hand_middle_03"),
            ("FKRingFinger0_L", "jnt_l_hand_ring_meta"),
            ("FKRingFinger1_L", "jnt_l_hand_ring_01"),
            ("FKRingFinger2_L", "jnt_l_hand_ring_02"),
            ("FKRingFinger3_L", "jnt_l_hand_ring_03"),
            ("FKPinkyFinger0_L", "jnt_l_hand_pinky_meta"),
            ("FKPinkyFinger1_L", "jnt_l_hand_pinky_01"),
            ("FKPinkyFinger2_L", "jnt_l_hand_pinky_02"),
            ("FKPinkyFinger3_L", "jnt_l_hand_pinky_03"),
            ("FKThumbFinger1_R", "jnt_r_hand_thumb_01"),
            ("FKThumbFinger2_R", "jnt_r_hand_thumb_02"),
            ("FKThumbFinger3_R", "jnt_r_hand_thumb_03"),
            ("FKIndexFinger0_R", "jnt_r_hand_index_meta"),
            ("FKIndexFinger1_R", "jnt_r_hand_index_01"),
            ("FKIndexFinger2_R", "jnt_r_hand_index_02"),
            ("FKIndexFinger3_R", "jnt_r_hand_index_03"),
            ("FKMiddleFinger0_R", "jnt_r_hand_middle_meta"),
            ("FKMiddleFinger1_R", "jnt_r_hand_middle_01"),
            ("FKMiddleFinger2_R", "jnt_r_hand_middle_02"),
            ("FKMiddleFinger3_R", "jnt_r_hand_middle_03"),
            ("FKRingFinger0_R", "jnt_r_hand_ring_meta"),
            ("FKRingFinger1_R", "jnt_r_hand_ring_01"),
            ("FKRingFinger2_R", "jnt_r_hand_ring_02"),
            ("FKRingFinger3_R", "jnt_r_hand_ring_03"),
            ("FKPinkyFinger0_R", "jnt_r_hand_pinky_meta"),
            ("FKPinkyFinger1_R", "jnt_r_hand_pinky_01"),
            ("FKPinkyFinger2_R", "jnt_r_hand_pinky_02"),
            ("FKPinkyFinger3_R", "jnt_r_hand_pinky_03")
        ]
        
        try:
            # Step 1: Create a clean animation layer for the cleanup
            cleanup_layer_name = "Cleanup"  # Using "Cleanup" as shown in the screenshot
            
            # Remove existing layer if it exists
            if cmds.objExists(cleanup_layer_name):
                cmds.delete(cleanup_layer_name)
                print(f"// Removed existing cleanup layer: {cleanup_layer_name}")
                
            # Create a new animation layer in additive mode
            cleanup_layer = cmds.animLayer(cleanup_layer_name)
            cmds.animLayer(cleanup_layer, edit=True, override=False)  # override=False = additive mode
            print(f"// Created new additive animation layer: {cleanup_layer}")
            
            # Step 2: Find all the joints that match our alignment list and valid controls
            valid_alignments = []
            for fk_control, target_joint in alignments:
                # Find the target joint
                target_joint_full = find_joint_in_animimport_group(target_joint)
                
                # Check if the target joint exists
                if not target_joint_full:
                    print(f"// Warning: Could not find target joint: {target_joint}")
                    continue
                    
                # Look for the FK control (direct or in namespaces)
                fk_control_full = None
                
                # First check direct existence
                if cmds.objExists(fk_control):
                    fk_control_full = fk_control
                else:
                    # Look for FK control in namespaces
                    namespaced_controls = cmds.ls("*:" + fk_control)
                    if namespaced_controls:
                        fk_control_full = namespaced_controls[0]
                        print(f"// Found FK control in namespace: {fk_control_full}")
                    else:
                        # Check for more complex namespace patterns (e.g., namespace:group:control)
                        all_matching = cmds.ls("*" + fk_control)
                        possible_controls = [ctrl for ctrl in all_matching if ctrl.endswith(fk_control)]
                        if possible_controls:
                            fk_control_full = possible_controls[0]
                            print(f"// Found FK control with nested namespace: {fk_control_full}")
                
                # Add to valid alignments if both exist
                if fk_control_full:
                    valid_alignments.append((fk_control_full, target_joint_full))
                    print(f"// Valid alignment pair: {fk_control_full} → {target_joint_full}")
                else:
                    print(f"// Warning: FK control not found: {fk_control}")
            
            # Step 3: Add all valid FK controls to the animation layer
            if valid_alignments:
                fk_controls = [pair[0] for pair in valid_alignments]
                cmds.select(fk_controls, r=True)
                cmds.animLayer(cleanup_layer, edit=True, addSelectedObjects=True)
                print(f"// Added {len(fk_controls)} FK controls to the cleanup layer")
                
                # Step 4: Make the cleanup layer active for constraints
                cmds.animLayer(cleanup_layer, edit=True, selected=True)
                print(f"// Set {cleanup_layer} as the active animation layer")
                
                # Step 5: Create point constraints for each control-joint pair
                constraints = []
                for fk_control, target_joint_full in valid_alignments:
                    # Select joint first, then control (order matters for constraint)
                    cmds.select(target_joint_full, fk_control)
                    
                    # Create point constraint with settings from the screenshot:
                    # - Maintain offset: off
                    # - Animation Layer: Cleanup (already active)
                    # - Constraint axes: All (X, Y, Z)
                    # - Weight: 1.0000
                    constraint = cmds.pointConstraint(
                        target_joint_full, fk_control,
                        maintainOffset=False,  # No offset
                        weight=1.0,            # Weight of 1.0
                    )[0]
                    constraints.append(constraint)
                    print(f"// Created point constraint: {target_joint_full} -> {fk_control}")
                
                # Step 6: Set keyframes for cleanup layer weight
                print("// Setting cleanup layer weight keyframes at frames -1 and 0")
                
                # Set weight to 0 at frame -1
                cmds.currentTime(-1)
                cmds.animLayer(cleanup_layer, edit=True, weight=0)
                cmds.setKeyframe(cleanup_layer + ".weight")
                print("// Set layer weight to 0 at frame -1")
                
                # Set weight to 1 at frame 0
                cmds.currentTime(0)
                cmds.animLayer(cleanup_layer, edit=True, weight=1)
                cmds.setKeyframe(cleanup_layer + ".weight")
                print("// Set layer weight to 1 at frame 0")
                
                # Step 7: Merge the layer into base animation
                print("// Merging cleanup layer into base animation")
                
                # First, make sure to select the cleanup layer
                cmds.select(cleanup_layer, r=True)
                
                # Use mergeLayers command with settings from screenshot:
                # - Merge To: Bottom Selected Layer
                # - Layers Hierarchy: Selected
                # - Result Layer Mode: Automatic
                # - Delete Baked Layers: on
                # - Sample by: 1.0
                # - Oversampling Rate: 1
                
                # Make sure to bake both frame -1 (weight 0) and frame 0 (weight 1)
                # This ensures the transition from no effect to full effect is captured
                cmds.bakeResults(
                    fk_controls,
                    time=(-1, 0),  # Explicitly bake frames -1 and 0
                    simulation=True,
                    sampleBy=1.0,
                    oversamplingRate=1,
                    disableImplicitControl=True,
                    preserveOutsideKeys=True,
                    sparseAnimCurveBake=False,
                    removeBakedAttributeFromLayer=True,  # Remove from layer
                    removeBakedAnimFromLayer=True,      # Remove animation
                    bakeOnOverrideLayer=False,
                    minimizeRotation=True,
                    controlPoints=False,
                    shape=True
                )
                
                # Step 7: Delete all constraints after merging
                if constraints:
                    cmds.delete(constraints)
                    print(f"// Removed {len(constraints)} point constraints")
                
                # Cleanup layer should be automatically deleted by bakeResults with removeBakedAnimFromLayer=True
                # but we'll check and delete if still exists
                if cmds.objExists(cleanup_layer):
                    cmds.delete(cleanup_layer)
                    print(f"// Removed cleanup layer: {cleanup_layer}")
                
                # Report success
                print(f"// Successfully aligned {len(valid_alignments)} control-joint pairs")
            else:
                # If no valid alignments, clean up and exit
                print("// No valid control-joint pairs found for cleanup")
                cmds.delete(cleanup_layer)
                print(f"// Deleted cleanup layer: {cleanup_layer_name}")
            
        except Exception as e:
            print(f"// Error in animation cleanup: {str(e)}")
            # Clean up any created layer in case of error
            if 'cleanup_layer' in locals() and cmds.objExists(cleanup_layer):
                cmds.delete(cleanup_layer)
                print(f"// Deleted cleanup layer due to error: {cleanup_layer}")
            # Clean up any constraints in case of error
            if 'constraints' in locals() and constraints:
                try:
                    cmds.delete(constraints)
                    print(f"// Deleted constraints due to error")
                except:
                    pass

except Exception as e:
    print("// Error in STALKER 2 animation cleanup: {}".format(str(e)))