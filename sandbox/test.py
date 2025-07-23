# Import necessary libraries
# The rich traceback hook provides more informative error messages, which is excellent for debugging.
from rich import traceback
traceback.install(show_locals=True, width=200, code_width=120, indent_guides=True)
from simplecadapi import *
import math

def make_hex_socket_bolt(
    bolt_length: float = 30.0,
    head_height: float = 5.5,
    head_across_flats: float = 13.0,
    shank_diameter: float = 8.0,
    internal_hex_across_flats: float = 4.0,
    internal_hex_depth: float = 4.0,
    thread_pitch: float = 1.0,
):
    """
    Generates a 3D model of a hex socket bolt based on provided parameters.

    Args:
        bolt_length (float): The length of the shank, from under the head.
        head_height (float): The height of the hexagonal head.
        head_across_flats (float): The distance between two parallel faces of the head.
        shank_diameter (float): The nominal diameter of the threaded shank.
        internal_hex_across_flats (float): The across-flats distance for the internal hex socket.
        internal_hex_depth (float): The depth of the internal hex socket.
        thread_pitch (float): The pitch of the metric thread.

    Returns:
        Solid: The final 3D solid model of the bolt.
    """
    print("--- Starting Bolt Creation ---")
    print(f"Parameters: bolt_length={bolt_length}, head_height={head_height}, shank_diameter={shank_diameter}")

    # --- [Step 1] Create Hexagonal Head ---
    print("\n[Step 1] Creating hexagonal head...")
    bolt_head = None
    try:
        # To create a hexagon from its across-flats dimension, we first need its circumradius (distance from center to vertex).
        # The relationship is: circumradius = (across_flats / 2) / cos(30 degrees).
        head_circumradius = (head_across_flats / 2.0) / math.cos(math.radians(30))
        
        head_points = []
        for i in range(6):
            # We generate the 6 vertices of the hexagon by stepping through 60-degree increments.
            angle = math.radians(60 * i)
            x = head_circumradius * math.cos(angle)
            y = head_circumradius * math.sin(angle)
            head_points.append((x, y, 0))
        
        # We work on the default XY plane (origin at 0,0,0).
        with SimpleWorkplane():
            # Create the 2D wire profile of the hexagon.
            head_profile_wire = make_polyline_rwire(head_points, closed=True)
            # Convert the closed wire into a planar face.
            head_profile_face = make_face_from_wire_rface(head_profile_wire)
            # Extrude the face along the positive Z-axis to give the head its height.
            bolt_head = extrude_rsolid(head_profile_face, (0, 0, 1), head_height)
        
        bolt_head = set_tag(bolt_head, "bolt_head")
        print(f"  Hexagonal head created with height {head_height} and across-flats {head_across_flats}.")
        if not isinstance(bolt_head, Solid):
            raise TypeError("Head creation did not return a valid Solid object.")
    except Exception as e:
        print(f"ERROR in Step 1 (line ~{e.__traceback__.tb_lineno}): Failed to create hexagonal head.")
        print(f"  Reason: {e}")
        print("  Suggestion: Check if 'head_across_flats' and 'head_height' are positive numbers.")
        raise

    # --- [Step 2] Create Cylindrical Shank ---
    print("\n[Step 2] Creating cylindrical shank...")
    shank_body = None
    try:
        shank_radius = shank_diameter / 2.0
        # The bolt shank extends from Z=0 downwards to Z=-bolt_length.
        # We create the cylinder with its base at Z=-bolt_length and its axis pointing up.
        shank_body = make_cylinder_rsolid(
            radius=shank_radius,
            height=bolt_length,
            center=(0, 0, -bolt_length), # The center of the cylinder's bottom face.
            axis=(0, 0, 1)               # The direction of the cylinder's height.
        )
        shank_body = set_tag(shank_body, "bolt_shank")
        print(f"  Cylindrical shank created with length {bolt_length} and diameter {shank_diameter}.")
        if not isinstance(shank_body, Solid):
            raise TypeError("Shank creation did not return a valid Solid object.")
    except Exception as e:
        print(f"ERROR in Step 2 (line ~{e.__traceback__.tb_lineno}): Failed to create cylindrical shank.")
        print(f"  Reason: {e}")
        print("  Suggestion: Ensure 'shank_diameter' and 'bolt_length' are positive values.")
        raise

    # --- [Step 3] Merge Head and Shank ---
    print("\n[Step 3] Merging head and shank...")
    bolt_body = None
    try:
        # The base of the head is at Z=0, and the top of the shank is at Z=0. They align perfectly for a union operation.
        bolt_body = union_rsolid(bolt_head, shank_body)
        print("  Head and shank merged successfully into a single solid.")
        if not isinstance(bolt_body, Solid):
            raise TypeError("Union operation failed to return a valid Solid object.")
    except Exception as e:
        print(f"ERROR in Step 3 (line ~{e.__traceback__.tb_lineno}): Failed to merge head and shank.")
        print(f"  Reason: {e}")
        print("  Suggestion: This may indicate an issue with the geometry created in Steps 1 or 2.")
        raise

    # --- [Step 4] Create Internal Hex Socket ---
    print("\n[Step 4] Creating internal hex socket...")
    bolt_body_with_socket = None
    try:
        # The socket is cut from the top face of the head downwards.
        internal_hex_circumradius = (internal_hex_across_flats / 2.0) / math.cos(math.radians(30))
        
        # We will create the cutting tool using a workplane positioned on the top face of the bolt head.
        with SimpleWorkplane(origin=(0, 0, head_height)):
            hex_tool_points = []
            for i in range(6):
                angle = math.radians(60 * i)
                x = internal_hex_circumradius * math.cos(angle)
                y = internal_hex_circumradius * math.sin(angle)
                # Points are defined in the local XY plane of the workplane.
                hex_tool_points.append((x, y, 0))
            
            hex_tool_wire = make_polyline_rwire(hex_tool_points, closed=True)
            hex_tool_face = make_face_from_wire_rface(hex_tool_wire)
            # Extrude downwards (negative Z direction) to create the cutting tool.
            hex_tool_solid = extrude_rsolid(hex_tool_face, (0, 0, -1), internal_hex_depth)

        # The cutting tool is already in the correct global position due to the workplane.
        # Perform the boolean cut operation.
        bolt_body_with_socket = cut_rsolid(bolt_body, hex_tool_solid)
        print(f"  Internal hex socket cut with depth {internal_hex_depth}.")
        if not isinstance(bolt_body_with_socket, Solid):
            raise TypeError("Hex socket cut operation did not return a valid Solid object.")
    except Exception as e:
        print(f"ERROR in Step 4 (line ~{e.__traceback__.tb_lineno}): Failed to create internal hex socket.")
        print(f"  Reason: {e}")
        print("  Suggestion: Check if 'internal_hex_across_flats' and 'internal_hex_depth' are valid and smaller than the head dimensions.")
        raise

    # --- [Step 5] Create Thread and Cut ---
    print("\n[Step 5] Creating thread...")
    final_bolt = None
    try:
        # To create the thread, we will sweep a V-shaped profile along a helix and cut the result from the shank.
        # This profile represents the material to be removed.
        thread_depth = thread_pitch * 0.6134  # ISO metric thread depth calculation.
        
        # We create a triangular cutting profile at the origin. It will be automatically positioned by the sweep function.
        # The profile points inwards, along the negative X-axis, to cut into the shank.
        cutter_depth = thread_depth + 0.05  # Add a small tolerance for a clean cut.
        cutter_width_half = (cutter_depth * math.tan(math.radians(30))) + 0.05 # 60-degree V-angle.
        
        cutter_profile_points = [
            (-cutter_depth, 0, 0),    # The tip of the V-cutter.
            (0, -cutter_width_half, 0), # One corner of the base.
            (0, cutter_width_half, 0),  # The other corner of the base.
        ]
        
        cutter_wire = make_polyline_rwire(cutter_profile_points, closed=True)
        
        # Now, create the helical solid tool.
        thread_cutter = helical_sweep_rsolid(
            profile=cutter_wire,
            pitch=thread_pitch,
            height=bolt_length,
            radius=shank_diameter / 2.0 * 1.02, # The sweep helix is on the outer surface of the shank.
            center=(0, 0, 0),           # The helix starts at Z=0.
            dir=(0, 0, -1)              # The helix proceeds in the negative Z direction.
        )
        
        print(f"  Helical cutting tool created with pitch {thread_pitch}.")
        
        # Cut the thread from the bolt body.
        final_bolt = cut_rsolid(bolt_body_with_socket, thread_cutter)
        print("  Thread successfully cut into the shank.")
        if not isinstance(final_bolt, Solid):
            raise TypeError("Thread cutting operation did not return a valid Solid object.")

    except Exception as e:
        print(f"ERROR in Step 5 (line ~{e.__traceback__.tb_lineno}): Failed to create the thread.")
        print(f"  Reason: {e}")
        print("  Suggestion: This is a complex operation. Check thread parameters ('thread_pitch'). A very small pitch can sometimes cause issues.")
        raise
        
    print("\n--- Bolt Creation Complete ---")
    return final_bolt


if __name__ == "__main__":
    # This block will only run when the script is executed directly.
    print("Executing main script to generate and export the bolt model.")
    
    # Call the main modeling function to create the bolt.
    hex_bolt_model = make_hex_socket_bolt()

    if hex_bolt_model:
        try:
            # Define output filenames.
            stl_filename = "hex_socket_bolt.stl"
            step_filename = "hex_socket_bolt.step"
            
            # Export the final model to STL and STEP file formats.
            print(f"\nExporting model to {stl_filename}...")
            export_stl(hex_bolt_model, stl_filename)
            
            print(f"Exporting model to {step_filename}...")
            export_step(hex_bolt_model, step_filename)
            
            print("\nSuccessfully generated and saved the hex socket bolt model.")
            print(f"Files saved: '{stl_filename}' and '{step_filename}'")
        except Exception as e:
            print(f"\nFATAL ERROR during file export (line ~{e.__traceback__.tb_lineno}): {e}")
    else:
        print("\nModel generation failed. No object to export.")
