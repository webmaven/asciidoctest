import os
import sys

def analyze_repo(path='.'):
    lengths = []
    # Directories to strictly skip
    skip_dirs = {
        'venv', 'env', '__pycache__', 'build', 'dist', 
        'egg-info', 'htmlcov', '.pytest_cache', '.git'
    }
    
    for root, dirs, files in os.walk(path):
        # Modify dirs in-place to prevent walking down skipped paths
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
        
        for f in files:
            if f.endswith('.py') and not f.endswith('.pyi'):
                fp = os.path.join(root, f)
                try:
                    with open(fp, 'r', encoding='utf-8', errors='ignore') as file:
                        lengths.append(sum(1 for _ in file))
                except Exception:
                    pass
                    
    if not lengths:
        print("No Python modules found in the specified path.")
        return
        
    lengths.sort()
    n = len(lengths)
    mean_loc = sum(lengths) / n
    median_loc = lengths[n // 2] if n % 2 != 0 else (lengths[n // 2 - 1] + lengths[n // 2]) / 2
    
    print(f"========================================")
    print(f"  REPOSITORY LINE OF CODE (LoC) METRICS ")
    print(f"========================================")
    print(f"Total Python Files analyzed: {n}")
    print(f"Mean Lines of Code (Average): {mean_loc:.1f}")
    print(f"Median Lines of Code:         {median_loc}")
    print(f"Minimum File Size:            {lengths[0]} lines")
    print(f"Maximum File Size:            {lengths[-1]} lines")
    print(f"========================================")

if __name__ == '__main__':
    target_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    analyze_repo(target_dir)
