import numpy as np
import sys

# NOTE: This script generates a .PLY 3D file.
# You do not need matplotlib or plotly.
# You can open the resulting 'cut_simulation.ply' file in:
# - Windows 3D Viewer (Built-in on Windows)
# - Blender
# - MeshLab

def generate_cylinder_mesh(radius=1, height=6, mesh_res=50):
    """
    Generates vertices and faces for a cylinder.
    """
    z_grid = np.linspace(0, height, mesh_res)
    theta_grid = np.linspace(0, 2 * np.pi, mesh_res)
    z_grid, theta_grid = np.meshgrid(z_grid, theta_grid)
    
    x = radius * np.cos(theta_grid).flatten()
    y = radius * np.sin(theta_grid).flatten()
    z = z_grid.flatten()
    
    # Stack into an (N, 3) array
    points = np.vstack((x, y, z)).T
    
    # Calculate normals
    normals = points.copy()
    normals[:, 2] = 0
    norms = np.linalg.norm(normals, axis=1, keepdims=True)
    # Avoid division by zero
    norms[norms == 0] = 1
    normals = normals / norms
    
    # Generate Faces (Quads) for topology
    faces = []
    for r in range(mesh_res - 1):
        for c in range(mesh_res - 1):
            # Calculate vertex indices for a quad
            p1 = r * mesh_res + c
            p2 = r * mesh_res + (c + 1)
            p3 = (r + 1) * mesh_res + (c + 1)
            p4 = (r + 1) * mesh_res + c
            faces.append([p1, p2, p3, p4])
            
    return points, normals, np.array(faces)

def get_colors_based_on_depth(intensities):
    """
    Returns (R, G, B) integer arrays (0-255).
    """
    colors = np.zeros((len(intensities), 3), dtype=np.uint8)
    
    # Skin Color (Beige)
    skin = np.array([205, 160, 130])
    # Muscle Color (Red)
    muscle = np.array([200, 20, 20])
    # Bone/Deep Color (White)
    bone = np.array([240, 240, 240])
    
    for i, val in enumerate(intensities):
        if val > 0.6:
            colors[i] = bone
        elif val > 0.2:
            colors[i] = muscle
        else:
            colors[i] = skin
            
    return colors

def deform_mesh(points, normals, cutter_pos, cut_radius=1.5, depth_factor=0.8):
    """
    Deforms the points inwards based on distance to cutter_pos.
    """
    deformed_points = points.copy()
    intensities = np.zeros(len(points))
    
    for i, point in enumerate(points):
        dist = np.linalg.norm(point - cutter_pos)
        
        if dist < cut_radius:
            intensity = (cut_radius - dist) / cut_radius
            intensities[i] = intensity
            
            # Deform inwards
            push = normals[i] * -1 * intensity * depth_factor
            deformed_points[i] += push
            
    return deformed_points, intensities

def save_to_ply(filename, points, faces, colors):
    """
    Saves the mesh to a PLY file (readable by standard 3D viewers).
    Supports vertex colors.
    """
    header = f"""ply
format ascii 1.0
element vertex {len(points)}
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
element face {len(faces)}
property list uchar int vertex_index
end_header
"""
    print(f"Saving to {filename}...")
    with open(filename, 'w') as f:
        f.write(header)
        # Write Vertices + Colors
        for p, c in zip(points, colors):
            f.write(f"{p[0]:.4f} {p[1]:.4f} {p[2]:.4f} {c[0]} {c[1]} {c[2]}\n")
        
        # Write Faces
        for face in faces:
            f.write(f"4 {face[0]} {face[1]} {face[2]} {face[3]}\n")
            
    print("Done.")

if __name__ == "__main__":
    print("--- Python Surgical Cut Simulator (No External GUI) ---")
    
    # 1. Generate Arm
    print("Generating base mesh...")
    points, normals, faces = generate_cylinder_mesh(radius=1.0, height=5.0, mesh_res=80)
    
    # 2. Input
    try:
        user_in = input("Enter cutter height (0.0 to 5.0) [default 2.5]: ")
        height_val = float(user_in) if user_in.strip() else 2.5
        
        user_depth = input("Enter cut depth strength (0.5 to 2.0) [default 1.2]: ")
        depth_val = float(user_depth) if user_depth.strip() else 1.2
    except ValueError:
        print("Invalid input. Using defaults.")
        height_val = 2.5
        depth_val = 1.2

    cutter_location = np.array([1.1, 0.0, height_val])
    
    # 3. Simulate
    print(f"Cutting at height {height_val} with strength {depth_val}...")
    new_points, intensities = deform_mesh(points, normals, cutter_location, cut_radius=1.5, depth_factor=depth_val)
    
    # 4. Colorize
    colors = get_colors_based_on_depth(intensities)
    
    # 5. Export
    output_filename = "cut_simulation.ply"
    save_to_ply(output_filename, new_points, faces, colors)
    
    print(f"\nSUCCESS! File saved as: {output_filename}")
    print(">> Open this file in Windows 3D Viewer or Blender to see the red muscle and white bone.")