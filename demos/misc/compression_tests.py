# Rough file to compress some of our .h5 fracture files and see how much space different techniques save. 

import h5py
import numpy as np
import os
import sys
from collections import OrderedDict

def get_file_size_mb(filepath):
    """Get file size in MB"""
    return os.path.getsize(filepath) / (1024 * 1024)

def copy_attributes(source, dest):
    """Copy all attributes from source to destination"""
    for key, val in source.attrs.items():
        dest.attrs[key] = val

def analyze_temporal_variation(data):
    """Analyze how much data varies between timesteps"""
    if data.ndim < 2:
        return None
    
    # Compute differences between consecutive timesteps
    diffs = np.diff(data, axis=0)
    
    avg_abs_change = np.mean(np.abs(diffs))
    max_abs_change = np.max(np.abs(diffs))
    avg_value = np.mean(np.abs(data))
    
    relative_change = avg_abs_change / (avg_value + 1e-10)
    
    return {
        'avg_abs_change': avg_abs_change,
        'max_abs_change': max_abs_change,
        'avg_value': avg_value,
        'relative_change_pct': relative_change * 100
    }

def copy_hdf5_with_temporal_compression(source_group, dest_group, config, path=""):
    """
    Copy HDF5 structure with temporal-aware compression.
    """
    copy_attributes(source_group, dest_group)
    
    for name, item in source_group.items():
        current_path = f"{path}/{name}"
        
        if isinstance(item, h5py.Group):
            subgroup = dest_group.create_group(name)
            copy_hdf5_with_temporal_compression(item, subgroup, config, current_path)
            
        elif isinstance(item, h5py.Dataset):
            data = item[:]
            original_shape = data.shape
            original_dtype = data.dtype
            
            # Check if this is temporal data (first dimension > 1)
            is_temporal = data.ndim >= 2 and data.shape[0] > 1
            
            if is_temporal and config.get('use_delta_encoding', False):
                print(f"    Delta encoding: {current_path} (shape: {data.shape})")
                
                # Analyze variation
                stats = analyze_temporal_variation(data)
                if stats:
                    print(f"      Avg change: {stats['avg_abs_change']:.6f} ({stats['relative_change_pct']:.2f}%)")
                
                # Store first frame as reference
                reference = data[0].copy()
                
                # Compute deltas
                deltas = np.diff(data, axis=0)
                
                # Optional: quantize deltas if specified
                if config.get('delta_quantization'):
                    scale_factor = config['delta_quantization']
                    deltas = np.round(deltas / scale_factor).astype(np.int16)
                    dest_group.attrs[f'{name}_delta_scale'] = scale_factor
                    dest_group.attrs[f'{name}_delta_quantized'] = True
                    print(f"      Quantized deltas to int16 (scale: {scale_factor})")
                
                # Store reference frame
                ref_name = f"{name}_reference"
                dest_group.create_dataset(
                    ref_name,
                    data=reference,
                    compression=config.get('compression', 'gzip'),
                    compression_opts=config.get('compression_opts', 9),
                    shuffle=config.get('shuffle', True)
                )
                
                # Store deltas with optimal chunking (temporal chunks)
                delta_chunks = (min(32, deltas.shape[0]),) + deltas.shape[1:]
                if len(delta_chunks) > 1 and delta_chunks[1] > 128:
                    delta_chunks = (delta_chunks[0], min(128, delta_chunks[1])) + delta_chunks[2:]
                
                dest_group.create_dataset(
                    name,
                    data=deltas,
                    compression=config.get('compression', 'gzip'),
                    compression_opts=config.get('compression_opts', 9),
                    shuffle=config.get('shuffle', True),
                    chunks=delta_chunks
                )
                
                # Store metadata
                dest_group.attrs[f'{name}_is_delta_encoded'] = True
                dest_group.attrs[f'{name}_original_shape'] = original_shape
                
            elif is_temporal and config.get('use_sparse_storage', False):
                print(f"    Sparse storage: {current_path} (shape: {data.shape})")
                
                # Store first frame
                reference = data[0].copy()
                
                # Find frames that differ significantly from previous
                threshold = config.get('sparse_threshold', 1e-6)
                
                # Store which frames are different and their data
                changed_indices = []
                changed_data = []
                
                for i in range(1, data.shape[0]):
                    diff = np.abs(data[i] - data[i-1])
                    if np.mean(diff) > threshold:
                        changed_indices.append(i)
                        changed_data.append(data[i])
                
                print(f"      Storing {len(changed_indices)}/{data.shape[0]} frames that changed")
                
                # Store reference and changed frames
                dest_group.create_dataset(
                    f"{name}_reference",
                    data=reference,
                    compression=config.get('compression', 'gzip'),
                    compression_opts=config.get('compression_opts', 9)
                )
                
                dest_group.create_dataset(
                    f"{name}_changed_indices",
                    data=np.array(changed_indices, dtype=np.int32)
                )
                
                if changed_data:
                    dest_group.create_dataset(
                        name,
                        data=np.array(changed_data),
                        compression=config.get('compression', 'gzip'),
                        compression_opts=config.get('compression_opts', 9)
                    )
                
                dest_group.attrs[f'{name}_is_sparse'] = True
                
            else:
                # Standard compression
                data_to_store = data
                
                # Optional dtype conversion
                if config.get('dtype_convert') and original_dtype in config['dtype_convert']:
                    data_to_store = data.astype(config['dtype_convert'][original_dtype])
                    print(f"    Converting {current_path}: {original_dtype} -> {data_to_store.dtype}")
                
                # Optimal chunking for temporal data
                if is_temporal:
                    chunks = (min(32, data.shape[0]),) + tuple(min(128, s) for s in data.shape[1:])
                else:
                    chunks = True
                
                dest_group.create_dataset(
                    name,
                    data=data_to_store,
                    compression=config.get('compression'),
                    compression_opts=config.get('compression_opts'),
                    shuffle=config.get('shuffle', False),
                    chunks=chunks
                )
            
            # Copy dataset attributes
            copy_attributes(item, dest_group[name])

def compress_h5_file(input_file, compression_configs):
    """Create multiple compressed versions with different strategies."""
    
    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found!")
        return
    
    original_size = get_file_size_mb(input_file)
    print(f"\nOriginal file: {input_file}")
    print(f"Original size: {original_size:.2f} MB")
    
    # Analyze the file structure
    print("\n" + "=" * 80)
    print("ANALYZING FILE STRUCTURE")
    print("=" * 80)
    
    with h5py.File(input_file, 'r') as f:
        def print_structure(group, prefix=""):
            for name, item in group.items():
                if isinstance(item, h5py.Group):
                    print(f"{prefix}📁 {name}/")
                    print_structure(item, prefix + "  ")
                elif isinstance(item, h5py.Dataset):
                    size_mb = item.size * item.dtype.itemsize / (1024 * 1024)
                    print(f"{prefix}📄 {name}: shape={item.shape}, dtype={item.dtype}, size={size_mb:.2f} MB")
                    
                    # Check temporal variation
                    if item.ndim >= 2 and item.shape[0] > 1:
                        data_sample = item[:]
                        stats = analyze_temporal_variation(data_sample)
                        if stats:
                            print(f"{prefix}   └─ Temporal variation: {stats['relative_change_pct']:.2f}% avg change per step")
        
        print_structure(f)
    
    print("\n" + "=" * 80)
    print("TESTING COMPRESSION STRATEGIES")
    print("=" * 80)
    
    results = OrderedDict()
    results['Original'] = {'size_mb': original_size, 'ratio': 1.0}
    
    base_name = os.path.splitext(input_file)[0]
    
    for config in compression_configs:
        output_name = config['name']
        output_file = f"{base_name}_{output_name}.h5"
        
        print(f"\n{'='*80}")
        print(f"Creating: {output_name}")
        print(f"Description: {config['description']}")
        print(f"{'='*80}")
        
        try:
            if os.path.exists(output_file):
                os.remove(output_file)
            
            with h5py.File(input_file, 'r') as f_in:
                with h5py.File(output_file, 'w') as f_out:
                    copy_hdf5_with_temporal_compression(f_in, f_out, config)
            
            compressed_size = get_file_size_mb(output_file)
            ratio = original_size / compressed_size if compressed_size > 0 else 0
            savings_pct = (1 - compressed_size / original_size) * 100
            
            results[output_name] = {
                'size_mb': compressed_size,
                'ratio': ratio,
                'savings_pct': savings_pct,
                'filename': output_file
            }
            
            print(f"\n✓ Complete: {compressed_size:.2f} MB")
            print(f"  Compression ratio: {ratio:.2f}x")
            print(f"  Space savings: {savings_pct:.1f}%")
            
        except Exception as e:
            print(f"\n✗ Failed: {str(e)}")
            import traceback
            traceback.print_exc()
            results[output_name] = {'error': str(e)}
    
    # Print summary
    print("\n" + "=" * 80)
    print("COMPRESSION SUMMARY")
    print("=" * 80)
    print(f"{'Configuration':<40} {'Size (MB)':<12} {'Ratio':<10} {'Savings':<10}")
    print("-" * 80)
    
    for name, result in results.items():
        if 'error' in result:
            print(f"{name:<40} ERROR")
        else:
            size_str = f"{result['size_mb']:.2f}"
            ratio_str = f"{result['ratio']:.2f}x" if result['ratio'] != 1.0 else "-"
            savings_str = f"{result.get('savings_pct', 0):.1f}%" if 'savings_pct' in result else "-"
            print(f"{name:<40} {size_str:<12} {ratio_str:<10} {savings_str:<10}")
    
    print("=" * 80)
    
    # Find best compression
    best = max(
        [(k, v) for k, v in results.items() if 'ratio' in v and k != 'Original'],
        key=lambda x: x[1]['ratio'],
        default=None
    )
    
    if best:
        print(f"\n🏆 BEST COMPRESSION: {best[0]}")
        print(f"   Size: {best[1]['size_mb']:.2f} MB ({best[1]['savings_pct']:.1f}% savings)")
        print(f"   Compression ratio: {best[1]['ratio']:.2f}x")
        print(f"   File: {best[1]['filename']}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python compress_h5_temporal.py <input_file.h5>")
        print("\nExample: python compress_h5_temporal.py simulation_data.h5")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    compression_configs = [
        # Standard approaches (baseline)
        {
            'name': 'gzip9_shuffle_baseline',
            'description': 'GZIP 9 + shuffle (baseline)',
            'compression': 'gzip',
            'compression_opts': 9,
            'shuffle': True,
        },
        
        # Delta encoding approaches
        {
            'name': 'delta_gzip9_shuffle',
            'description': 'Delta encoding + GZIP 9 + shuffle',
            'compression': 'gzip',
            'compression_opts': 9,
            'shuffle': True,
            'use_delta_encoding': True,
        },
        {
            'name': 'delta_lzf_shuffle',
            'description': 'Delta encoding + LZF + shuffle',
            'compression': 'lzf',
            'shuffle': True,
            'use_delta_encoding': True,
        },
        
        # Delta with quantization (lossy but high compression)
        {
            'name': 'delta_quant_1e-6',
            'description': 'Delta encoding + quantization (1e-6) + GZIP 9',
            'compression': 'gzip',
            'compression_opts': 9,
            'shuffle': True,
            'use_delta_encoding': True,
            'delta_quantization': 1e-6,
        },
        {
            'name': 'delta_quant_1e-5',
            'description': 'Delta encoding + quantization (1e-5) + GZIP 9',
            'compression': 'gzip',
            'compression_opts': 9,
            'shuffle': True,
            'use_delta_encoding': True,
            'delta_quantization': 1e-5,
        },
        {
            'name': 'delta_quant_1e-4',
            'description': 'Delta encoding + quantization (1e-4) + GZIP 9',
            'compression': 'gzip',
            'compression_opts': 9,
            'shuffle': True,
            'use_delta_encoding': True,
            'delta_quantization': 1e-4,
        },
        
        # Float precision reduction + delta
        {
            'name': 'float32_delta_gzip9',
            'description': 'Float64→32 + delta encoding + GZIP 9',
            'compression': 'gzip',
            'compression_opts': 9,
            'shuffle': True,
            'use_delta_encoding': True,
            'dtype_convert': {np.float64: np.float32},
        },
        
        # Sparse storage (only store changed frames)
        {
            'name': 'sparse_1e-6',
            'description': 'Sparse storage (threshold 1e-6)',
            'compression': 'gzip',
            'compression_opts': 9,
            'use_sparse_storage': True,
            'sparse_threshold': 1e-6,
        },
    ]
    
    compress_h5_file(input_file, compression_configs)
    
    print("\n" + "=" * 80)
    print("NOTES ON READING COMPRESSED FILES")
    print("=" * 80)
    print("""
For delta-encoded files, reconstruct with:
    with h5py.File('file_delta.h5', 'r') as f:
        reference = f['path/to/data_reference'][:]
        deltas = f['path/to/data'][:]
        reconstructed = np.cumsum(np.vstack([reference[None, ...], deltas]), axis=0)

For sparse files, reconstruct with:
    with h5py.File('file_sparse.h5', 'r') as f:
        reference = f['path/to/data_reference'][:]
        indices = f['path/to/data_changed_indices'][:]
        changed = f['path/to/data'][:]
        # Rebuild full array by filling in changed frames
""")

if __name__ == "__main__":
    main()