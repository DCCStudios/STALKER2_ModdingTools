import maya.cmds as cmds
import json

def get_joint_transform_data(node):
    """
    Get transform data for a joint node.
    
    Args:
        node (str): Joint node to get transform data from
        
    Returns:
        dict: Transform data including translation, rotation, and joint orient
    """
    if not cmds.objectType(node) == 'joint':
        return None
    
    # Get current frame transform values
    translate = cmds.getAttr(node + '.translate')[0]
    rotate = cmds.getAttr(node + '.rotate')[0]
    
    # Get joint orient (this is the "rest" orientation)
    joint_orient = cmds.getAttr(node + '.jointOrient')[0]
    
    # Get scale (sometimes needed)
    scale = cmds.getAttr(node + '.scale')[0]
    
    # Helper function to clean up values
    def clean_value(val):
        # Truncate to 3 decimal places
        val = round(val, 3)
        # Normalize scale values close to 1.0
        if abs(val - 1.0) < 0.01:  # If within 0.01 of 1.0
            val = 1.0
        return val
    
    # Clean up all transform values
    translate_clean = [clean_value(t) for t in translate]
    rotate_clean = [clean_value(r) for r in rotate]
    joint_orient_clean = [clean_value(jo) for jo in joint_orient]
    scale_clean = [clean_value(s) for s in scale]
    
    return {
        'translate': translate_clean,
        'rotate': rotate_clean,
        'jointOrient': joint_orient_clean,
        'scale': scale_clean
    }

def print_hierarchy_with_transforms(node, indent=0, joint_data=None):
    """
    Print the hierarchy of a node and its children, capturing joint transform data.
    
    Args:
        node (str): Node to start from
        indent (int): Current indentation level
        joint_data (dict): Dictionary to store joint transform data
    """
    if joint_data is None:
        joint_data = {}
    
    # Get the short name
    short_name = cmds.ls(node, shortNames=True)[0]
    print('  ' * indent + short_name)
    
    # If this is a joint, capture its transform data
    if cmds.objectType(node) == 'joint':
        transform_data = get_joint_transform_data(node)
        if transform_data:
            joint_data[short_name] = transform_data
            
            # Print transform info for debugging
            t = transform_data['translate']
            r = transform_data['rotate']
            jo = transform_data['jointOrient']
            print('  ' * (indent + 1) + f"T: [{t[0]:.3f}, {t[1]:.3f}, {t[2]:.3f}]")
            print('  ' * (indent + 1) + f"R: [{r[0]:.3f}, {r[1]:.3f}, {r[2]:.3f}]")
            print('  ' * (indent + 1) + f"JO: [{jo[0]:.3f}, {jo[1]:.3f}, {jo[2]:.3f}]")
    
    # Get children
    children = cmds.listRelatives(node, children=True, fullPath=True) or []
    for child in children:
        print_hierarchy_with_transforms(child, indent + 1, joint_data)
    
    return joint_data

def save_reference_pose_data(joint_data, filename="stalker2_reference_pose.json"):
    """
    Save joint transform data to a JSON file.
    
    Args:
        joint_data (dict): Joint transform data
        filename (str): Output filename
    """
    try:
        import os
        # Save to current Maya project directory
        project_dir = cmds.workspace(q=True, rd=True)
        filepath = os.path.join(project_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(joint_data, f, indent=2)
        
        print(f"\n✓ Reference pose data saved to: {filepath}")
        return filepath
    except Exception as e:
        print(f"\n✗ Failed to save reference pose data: {e}")
        return None

def generate_mel_zero_pose_script(joint_data, filename="stalker2_zero_pose.mel"):
    """
    Generate a MEL script that can zero out the skeleton to reference pose.
    
    Args:
        joint_data (dict): Joint transform data
        filename (str): Output MEL script filename
    """
    try:
        import os
        project_dir = cmds.workspace(q=True, rd=True)
        filepath = os.path.join(project_dir, filename)
        
        mel_script = []
        mel_script.append("// STALKER2 Skeleton Zero Pose Script")
        mel_script.append("// Generated automatically from reference pose")
        mel_script.append("// Run this to set skeleton to neutral pose on frame -1")
        mel_script.append("")
        mel_script.append("global proc stalker2ZeroPose()")
        mel_script.append("{")
        mel_script.append("    // Set timeline to frame -1")
        mel_script.append("    currentTime -1;")
        mel_script.append("    ")
        mel_script.append("    // Apply reference pose transforms")
        
        for joint_name, data in joint_data.items():
            t = data['translate']
            r = data['rotate']
            jo = data['jointOrient']
            s = data['scale']
            
            mel_script.append(f"    ")
            mel_script.append(f"    // {joint_name}")
            mel_script.append(f"    if (`objExists \"{joint_name}\"`)")
            mel_script.append(f"    {{")
            mel_script.append(f"        setAttr \"{joint_name}.translate\" {t[0]} {t[1]} {t[2]};")
            mel_script.append(f"        setAttr \"{joint_name}.rotate\" {r[0]} {r[1]} {r[2]};")
            mel_script.append(f"        setAttr \"{joint_name}.jointOrient\" {jo[0]} {jo[1]} {jo[2]};")
            mel_script.append(f"        setAttr \"{joint_name}.scale\" {s[0]} {s[1]} {s[2]};")
            mel_script.append(f"    }}")
        
        mel_script.append("    ")
        mel_script.append("    // Key all transforms on frame -1")
        mel_script.append("    string $joints[] = `ls -type joint`;")
        mel_script.append("    select $joints;")
        mel_script.append("    setKeyframe -time -1 -attribute translate;")
        mel_script.append("    setKeyframe -time -1 -attribute rotate;")
        mel_script.append("    select -clear;")
        mel_script.append("    ")
        mel_script.append("    print \"// STALKER2 skeleton set to reference pose on frame -1\\n\";")
        mel_script.append("}")
        mel_script.append("")
        mel_script.append("// Auto-execute when sourced")
        mel_script.append("// stalker2ZeroPose();")
        
        with open(filepath, 'w') as f:
            f.write('\n'.join(mel_script))
        
        print(f"✓ MEL zero pose script saved to: {filepath}")
        print(f"  To use: source \"{filename}\"; stalker2ZeroPose();")
        return filepath
    except Exception as e:
        print(f"✗ Failed to generate MEL script: {e}")
        return None

# Main execution
selection = cmds.ls(sl=True)
if not selection:
    print("Please select the root joint of the STALKER2 skeleton")
else:
    root_joint = selection[0]
    print(f"\n{'='*60}")
    print(f"STALKER2 Skeleton Reference Pose Capture")
    print(f"{'='*60}")
    print(f"Root Joint: {root_joint}")
    print(f"Current Frame: {cmds.currentTime(q=True)}")
    print(f"{'='*60}")
    
    # Capture hierarchy and transform data
    joint_data = print_hierarchy_with_transforms(root_joint)
    
    print(f"\n{'='*60}")
    print(f"Captured {len(joint_data)} joints")
    print(f"{'='*60}")
    
    # Save data files
    json_file = save_reference_pose_data(joint_data)
    mel_file = generate_mel_zero_pose_script(joint_data)
    
    print(f"\n{'='*60}")
    print(f"USAGE:")
    print(f"{'='*60}")
    print(f"1. The MEL script can be used in your animation importer")
    print(f"2. Run stalker2ZeroPose() to set skeleton to frame -1 reference pose")
    print(f"3. JSON file contains raw transform data for other uses")
    print(f"{'='*60}")