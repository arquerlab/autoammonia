import importlib

def resolve_class(path: str):
    """Dynamically import a class from a string path like 'package.module.Class'."""
    module_path, class_name = path.rsplit('.', 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)