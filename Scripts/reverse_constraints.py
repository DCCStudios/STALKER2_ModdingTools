#!/usr/bin/env python
"""
Reverse Constraints Tool

This script:
1. Detects if curves or joints are selected
2. If curves are selected:
   - Bakes any animation on those curves for the entire frame range
   - Removes existing constraints
   - Creates new constraints from the curves to the joints
3. If joints are selected:
   - Creates constraints from joints to curves

Author: Claude AI assistant
"""

import maya.cmds as cmds
from maya.cmds import confirmDialog

def reverse_constraints():
    """
    Main function to reverse constraints between curves and joints.
    Handles baking animation and reversing constraint directions.
    """
    # Get selection
    selection = cmds.ls(selection=True)
    if not selection:
        cmds.warning("Nothing selected. Please select curves or joints.")
        return
    
    # Log to collect operation results
    log_messages = []
    log_messages.append(f"Processing {len(selection)} selected objects")
    
    # Determine if we have curves or joints
    joints_selected = []
    curves_selected = []
    
    for obj in selection:
        if cmds.objectType(obj) == 'joint':
            joints_selected.append(obj)
        elif '_ctrl' in obj:
            curves_selected.append(obj)
    
    log_messages.append(f"Found {len(joints_selected)} joints and {len(curves_selected)} curves in selection")
    
    # Process based on selection type
    if len(curves_selected) > 0:
        # User selected curves
        log_messages.append("Curves selected - will bake animation and constrain joints TO curves")
        process_selected_curves(curves_selected, log_messages)
    elif len(joints_selected) > 0:
        # User selected joints
        log_messages.append("Joints selected - constraining joints TO curves (no baking)")
        process_selected_joints(joints_selected, log_messages)
    else:
        error_msg = "Please select joints or control curves (with '_ctrl' in name)."
        log_messages.append(f"ERROR: {error_msg}")
        cmds.warning(error_msg)

    # Show log popup with results
    show_log_popup(log_messages)

def process_selected_curves(curves_selected, log_messages):
    """
    Process when control curves are selected:
    1. Bake animation onto curves
    2. Remove constraints from curves
    3. Create constraints from curves to joints
    4. Remove all animation from joints
    """
    # Get frame range
    start_time = cmds.playbackOptions(query=True, min=True)
    end_time = cmds.playbackOptions(query=True, max=True)
    log_messages.append(f"Using frame range: {start_time} to {end_time}")
    
    # First, match curves to joints
    matched_pairs = []
    for curve in curves_selected:
        # Find matching joint name
        joint_name = find_matching_joint(curve)
        if joint_name:
            matched_pairs.append((curve, joint_name))
            log_messages.append(f"Matched curve {curve} to joint {joint_name}")
        else:
            log_messages.append(f"Could not find matching joint for {curve}")
    
    # Bake animation on the curves before modifying constraints
    if matched_pairs:
        curves_to_bake = [pair[0] for pair in matched_pairs]
        log_messages.append(f"Baking animation on {len(curves_to_bake)} curves...")
        
        try:
            # Bake animation on curves
            cmds.bakeResults(
                curves_to_bake,
                time=(start_time, end_time),
                simulation=True,
                sampleBy=1,
                oversamplingRate=1,
                disableImplicitControl=True,
                preserveOutsideKeys=True,
                sparseAnimCurveBake=False,
                removeBakedAttributeFromLayer=False,
                removeBakedAnimFromLayer=False,
                bakeOnOverrideLayer=False,
                minimizeRotation=True,
                at=["translate", "rotate", "scale"]
            )
            log_messages.append(f"Successfully baked animation on curves from frame {start_time} to {end_time}")
        except Exception as e:
            error_msg = f"Error baking animation: {str(e)}"
            log_messages.append(error_msg)
    
        # Now remove existing constraints and create new ones
        for curve, joint in matched_pairs:
            # Remove existing constraints
            delete_existing_constraints(curve, joint, log_messages)
            
            # Create constraint from curve to joint
            create_constraint(curve, joint, log_messages)
        
        # Remove all animation from the joints
        joints_to_clean = [pair[1] for pair in matched_pairs]
        log_messages.append(f"Removing animation from {len(joints_to_clean)} joints...")
        
        try:
            remove_animation_from_joints(joints_to_clean, log_messages)
            log_messages.append("Successfully removed all animation from joints")
        except Exception as e:
            error_msg = f"Error removing joint animation: {str(e)}"
            log_messages.append(error_msg)

def process_selected_joints(joints_selected, log_messages):
    """
    Process when joints are selected:
    1. Find matching curves
    2. Remove constraints
    3. Create constraints from joints to curves
    """
    for joint in joints_selected:
        # Find matching curve
        curve_name = find_matching_curve(joint)
        if curve_name:
            log_messages.append(f"Matched joint {joint} to curve {curve_name}")
            
            # Remove existing constraints
            delete_existing_constraints(joint, curve_name, log_messages)
            
            # Create constraint from joint to curve
            create_constraint(joint, curve_name, log_messages)
        else:
            log_messages.append(f"Could not find matching curve for {joint}")

def find_matching_joint(curve):
    """Find the matching joint for a control curve"""
    # Get base name by removing _ctrl suffix
    base_name = curve
    if curve.endswith("_ctrl"):
        base_name = curve[:-5]  # Remove "_ctrl" suffix
    elif "_ctrl" in curve:
        base_name = curve.split("_ctrl")[0]
    
    # If curve has namespace, preserve it
    namespace = ""
    if ":" in curve:
        namespace_parts = curve.split(":")
        base_short_name = namespace_parts[-1]
        if base_short_name.endswith("_ctrl"):
            base_short_name = base_short_name[:-5]
        elif "_ctrl" in base_short_name:
            base_short_name = base_short_name.split("_ctrl")[0]
        
        namespace = ":".join(namespace_parts[:-1]) + ":"
        base_name = namespace + base_short_name
    
    # Check if joint exists
    if cmds.objExists(base_name):
        return base_name
    
    # Try alternative approach: search for joint with similar name
    all_joints = cmds.ls(type="joint")
    for joint in all_joints:
        if joint == base_name or joint.endswith(":" + base_name.split(":")[-1]):
            return joint
    
    return None

def find_matching_curve(joint):
    """Find the matching curve for a joint"""
    # Add _ctrl suffix to joint name
    curve_name = joint + "_ctrl"
    
    # If joint has namespace, preserve it
    if ":" in joint:
        namespace_parts = joint.split(":")
        base_name = namespace_parts[-1]
        namespace = ":".join(namespace_parts[:-1]) + ":"
        curve_name = namespace + base_name + "_ctrl"
    
    # Check if curve exists
    if cmds.objExists(curve_name):
        return curve_name
    
    # Try alternative approach: search for curve with similar name
    all_curves = cmds.ls("*_ctrl")
    for curve in all_curves:
        # Remove _ctrl suffix for comparison
        if curve.endswith("_ctrl"):
            curve_base = curve[:-5]
        elif "_ctrl" in curve:
            curve_base = curve.split("_ctrl")[0]
        else:
            continue
            
        # Compare with joint name
        if curve_base == joint or curve_base.endswith(":" + joint.split(":")[-1]):
            return curve
    
    return None

def delete_existing_constraints(obj1, obj2, log_messages):
    """Delete constraints between two objects in either direction"""
    # More reliable approach to find constraints between objects
    constraints_to_delete = []
    
    # Check constraints on obj1
    log_messages.append(f"Looking for constraints between {obj1} and {obj2}...")
    
    # Directly check all parent constraints in the scene
    all_constraints = cmds.ls(type="parentConstraint") or []
    log_messages.append(f"Found {len(all_constraints)} parent constraints in scene")
    
    for constraint in all_constraints:
        try:
            # Get the constraint's parent - this is the constrained object
            parent_nodes = cmds.listRelatives(constraint, parent=True, path=True) or []
            if not parent_nodes:
                continue
                
            constrained_node = parent_nodes[0]
            
            # Get the constraint's targets
            target_connections = cmds.listConnections(constraint + ".target", source=True, destination=False) or []
            target_transforms = []
            
            # Get the actual transform nodes that are targets
            for target_conn in target_connections:
                if cmds.objectType(target_conn) != "parentConstraint":
                    target_transforms.append(target_conn)
            
            # Alternatively, try using the targetList attribute
            if not target_transforms:
                try:
                    target_transforms = cmds.parentConstraint(constraint, query=True, targetList=True) or []
                except:
                    pass
                    
            # Debug info
            short_obj1 = obj1.split("|")[-1]
            short_obj2 = obj2.split("|")[-1]
            short_constrained = constrained_node.split("|")[-1]
            
            log_messages.append(f"Constraint: {constraint}")
            log_messages.append(f"  - Constrained: {short_constrained}")
            log_messages.append(f"  - Targets: {target_transforms}")
            
            # Check if our objects are involved (in either direction)
            if ((short_obj1 in target_transforms and short_obj2 == short_constrained) or 
                (short_obj2 in target_transforms and short_obj1 == short_constrained) or
                (short_obj1 in str(target_transforms) and short_obj2 == short_constrained) or
                (short_obj2 in str(target_transforms) and short_obj1 == short_constrained)):
                constraints_to_delete.append(constraint)
                log_messages.append(f"  - MATCH FOUND! Will delete this constraint")
        except Exception as e:
            log_messages.append(f"  - Error inspecting constraint {constraint}: {str(e)}")
    
    # Delete all found constraints
    for constraint in constraints_to_delete:
        try:
            cmds.delete(constraint)
            log_messages.append(f"Deleted constraint: {constraint}")
        except Exception as e:
            log_messages.append(f"Error deleting constraint {constraint}: {str(e)}")
    
    if not constraints_to_delete:
        log_messages.append(f"No constraints found between {obj1} and {obj2}")

def create_constraint(source, target, log_messages):
    """Create parent constraint from source to target"""
    try:
        parent_constraint = cmds.parentConstraint(
            source, target,
            maintainOffset=True,
            weight=1.0
        )[0]
        log_messages.append(f"Created parent constraint with offset maintained: {source} → {target}")
        return parent_constraint
    except Exception as e:
        error_msg = f"Error creating constraint: {str(e)}"
        log_messages.append(error_msg)
        print(error_msg)
        return None
        
def remove_animation_from_joints(joints, log_messages):
    """
    Remove all animation/keyframes from the specified joints
    """
    if not joints:
        log_messages.append("No joints provided to remove animation from")
        return
        
    log_messages.append(f"Removing animation from {len(joints)} joints...")
    
    # Attributes to check for animation (translate, rotate, scale in all axes)
    attrs_to_check = [
        "translateX", "translateY", "translateZ",
        "rotateX", "rotateY", "rotateZ",
        "scaleX", "scaleY", "scaleZ"
    ]
    
    animation_curves_removed = 0
    
    # Process each joint
    for joint in joints:
        try:
            # For each attribute, remove any animation curves
            for attr in attrs_to_check:
                full_attr = f"{joint}.{attr}"
                
                # Check if attribute exists and has animation
                if cmds.objExists(full_attr):
                    # Get connected animation curves
                    connections = cmds.listConnections(
                        full_attr, 
                        source=True, 
                        destination=False, 
                        type="animCurve"
                    ) or []
                    
                    if connections:
                        # Delete the animation curves
                        cmds.delete(connections)
                        animation_curves_removed += len(connections)
                        log_messages.append(f"Removed {len(connections)} animation curves from {full_attr}")
                    
            # Additional check using cutKey command as a backup
            try:
                cmds.cutKey(joint, clear=True)
                log_messages.append(f"Cleared all remaining keys on {joint}")
            except Exception as e:
                log_messages.append(f"Note: Could not clear keys using cutKey on {joint}: {str(e)}")
                
        except Exception as e:
            log_messages.append(f"Error removing animation from {joint}: {str(e)}")
    
    log_messages.append(f"Total animation curves removed: {animation_curves_removed}")
    
    return animation_curves_removed

def show_log_popup(log_messages):
    """Show a popup with all log messages"""
    # Prepare the message content
    if len(log_messages) > 20:
        # If too many messages, show summary with option to print full log
        message = f"Completed {len(log_messages)} operations.\n\nLatest actions:\n"
        message += "\n".join(log_messages[-15:])
        message += f"\n\n(Full log has {len(log_messages)} entries - check script editor for details)"
        
        # Print full log to script editor
        print("\n=== REVERSE CONSTRAINTS LOG ===")
        for msg in log_messages:
            print(msg)
        print("=== END OF LOG ===\n")
    else:
        message = "\n".join(log_messages)
    
    # Show the dialog
    confirmDialog(
        title='Constraint Reversal Results',
        message=message,
        button=['OK'],
        defaultButton='OK',
        dismissString='OK'
    )

# Run the script when executed directly
if __name__ == "__main__":
    reverse_constraints()