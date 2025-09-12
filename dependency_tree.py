import os
import re

PROJECT_ROOT = r"C:\Users\Philip\Documents\GitHub\PocketFlowProject"
ENTRY_FILE = os.path.join(PROJECT_ROOT, "worker", "main.py")

RESOURCE_PATTERNS = [
    r'^\.env.*$',         
    r'^requirements\.txt$',
    r'^config\.ya?ml$',
    r'^README\.md$'
]
EXCLUDE_DIRS = {'venv', '.pytest_cache', '__pycache__', '.git'}

def resolve_relative_import(file_path, import_name):
    """Resolve .db_sync style import to actual file path."""
    dir_path = os.path.dirname(file_path)
    py_path = os.path.join(dir_path, import_name + '.py')
    pkg_path = os.path.join(dir_path, import_name, '__init__.py')
    return py_path, pkg_path

def module_to_path(module):
    """Convert absolute module import to file path(s) in the project."""
    parts = module.split('.')
    py_path = os.path.join(PROJECT_ROOT, *parts) + '.py'
    pkg_path = os.path.join(PROJECT_ROOT, *parts, '__init__.py')
    return py_path, pkg_path

def find_python_dependencies(file_path, checked=None):
    """Recursively find Python file dependencies by analyzing import statements."""
    if checked is None:
        checked = set()
    dependencies = set()
    if file_path in checked or not os.path.isfile(file_path):
        return dependencies
    checked.add(file_path)
    with open(file_path, encoding='utf8') as f:
        lines = f.readlines()
    for line in lines:
        # Match 'from .xxx import ...'
        match_rel = re.match(r'^\s*from\s+\.(\w+)\s+import', line)
        if match_rel:
            rel_mod = match_rel.group(1)
            py_path, pkg_path = resolve_relative_import(file_path, rel_mod)
            if os.path.isfile(py_path):
                dependencies.add(py_path)
                dependencies |= find_python_dependencies(py_path, checked)
            elif os.path.isfile(pkg_path):
                dependencies.add(pkg_path)
                dependencies |= find_python_dependencies(pkg_path, checked)
            continue
        # Match 'import xxx' or 'from xxx import ...'
        match = re.match(r'^\s*(?:from|import)\s+([a-zA-Z0-9_\.]+)', line)
        if match:
            mod = match.group(1)
            py_path, pkg_path = module_to_path(mod)
            if os.path.isfile(py_path):
                dependencies.add(py_path)
                dependencies |= find_python_dependencies(py_path, checked)
            elif os.path.isfile(pkg_path):
                dependencies.add(pkg_path)
                dependencies |= find_python_dependencies(pkg_path, checked)
    return dependencies

def find_resource_files(project_root):
    """Find resource/config files matching patterns in all subfolders, excluding EXCLUDE_DIRS."""
    resource_files = []
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for filename in files:
            for pattern in RESOURCE_PATTERNS:
                if re.match(pattern, filename):
                    resource_files.append(os.path.join(root, filename))
    return resource_files

def build_tree(entry_file, py_deps, resource_files):
    tree = [os.path.relpath(entry_file, PROJECT_ROOT)]
    for dep in sorted(py_deps):
        tree.append('├── ' + os.path.relpath(dep, PROJECT_ROOT))
    for res in sorted(resource_files):
        tree.append('├── ' + os.path.relpath(res, PROJECT_ROOT))
    return tree

def build_list(entry_file, py_deps, resource_files):
    dep_list = [os.path.relpath(entry_file, PROJECT_ROOT)]
    dep_list.extend([os.path.relpath(dep, PROJECT_ROOT) for dep in sorted(py_deps)])
    dep_list.extend([os.path.relpath(res, PROJECT_ROOT) for res in sorted(resource_files)])
    return dep_list

if __name__ == "__main__":
    print("Analyzing dependencies from:", ENTRY_FILE)
    py_deps = find_python_dependencies(ENTRY_FILE)
    resource_files = find_resource_files(PROJECT_ROOT)

    print("\nDependency Tree:")
    tree = build_tree(ENTRY_FILE, py_deps, resource_files)
    for line in tree:
        print(line)

    print("\nDependency List:")
    dep_list = build_list(ENTRY_FILE, py_deps, resource_files)
    for item in dep_list:
        print(item)