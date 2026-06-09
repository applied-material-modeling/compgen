import meshio
import numpy as np

def analyze_mesh(filename):
    print(f'\n--- Analyzing {filename} ---')
    try:
        mesh = meshio.read(filename)
        print(f'Points: {len(mesh.points)}')
        
        # Check node ordering and element type
        for cell_block in mesh.cells:
            print(f'Cell block: type={cell_block.type}, count={len(cell_block.data)}')
            # calculate jacobian / element areas to check for inverted elements if they are triangles or quads
            if cell_block.type == 'triangle':
                pts = mesh.points[cell_block.data]
                # Cross product for area/Jacobian (2D)
                # pts is shape (N, 3, 3)
                v1 = pts[:, 1, :2] - pts[:, 0, :2]
                v2 = pts[:, 2, :2] - pts[:, 0, :2]
                areas = 0.5 * (v1[:, 0]*v2[:, 1] - v1[:, 1]*v2[:, 0])
                neg_areas = np.sum(areas < 0)
                print(f'  Negative area triangles (inverted): {neg_areas}')
                print(f'  Min area: {np.min(areas):.4e}, Max area: {np.max(areas):.4e}')
            elif cell_block.type == 'quad':
                pts = mesh.points[cell_block.data]
                # Just a rough check on diagonals or areas
                v1 = pts[:, 1, :2] - pts[:, 0, :2]
                v2 = pts[:, 2, :2] - pts[:, 0, :2]
                areas = v1[:, 0]*v2[:, 1] - v1[:, 1]*v2[:, 0]
                neg_areas = np.sum(areas < 0)
                print(f'  Negative/inverted quads (node ordering check): {neg_areas} (rough estimate)')
        
        print('\nPoint Data Arrays:')
        for k, v in mesh.point_data.items():
            print(f'  {k}: shape={np.array(v).shape}')
            
        print('\nCell Data Arrays:')
        for k, v in mesh.cell_data.items():
            print(f'  {k}: length={len(v)}')
            
        print('\nPoint Sets (Node sets):')
        for k, v in mesh.point_sets.items():
            print(f'  {k}: len={len(v)}')

        print('\nCell Sets (Element blocks/Side sets):')
        for k, v in mesh.cell_sets.items():
            total_cells = sum([len(c) for c in v])
            print(f'  {k}: total_cells={total_cells}')

    except Exception as e:
        print(f'Error reading {filename}: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    analyze_mesh('/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/demos/pff+czm/gold/composite.msh')
    analyze_mesh('/Users/rghill/Documents/projects/JAAI00_AINS_SCMP/compgen-fracture/compgen/demos/pff+czm/gold/mesh.exo')
