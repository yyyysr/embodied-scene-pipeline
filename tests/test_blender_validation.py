import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


def test_free_task_object_does_not_require_hinge(monkeypatch):
    class Object(dict):
        type = 'MESH'
        name = 'cup'
        dimensions = (0.1, 0.1, 0.2)
    cup = Object(semantic_id='cup', semantic_role='task')
    monkeypatch.setitem(sys.modules, 'bpy', SimpleNamespace(data=SimpleNamespace(objects=[cup])))
    spec = importlib.util.spec_from_file_location('blender_validation_test',
        Path('blender_runtime/validate.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.validate_scene('demo', {'cup'})['status'] == 'pass'
    cup['requires_articulation'] = True
    assert module.validate_scene('demo', {'cup'})['status'] == 'needs_repair'
