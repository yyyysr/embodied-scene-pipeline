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


def test_reference_registration_preserves_entity_boundary(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, 'bpy', SimpleNamespace())
    monkeypatch.syspath_prepend(str(Path.cwd()))
    from blender_runtime.context import BuildContext

    monkeypatch.setattr(BuildContext, '_move_to_collection', staticmethod(lambda *args: None))
    context = BuildContext(tmp_path, {'id': 'test'})
    root = {'name': 'entity'}
    visual = {'name': 'visual'}
    proxy = {'name': 'proxy', 'parent': root}
    context.register(root, 'entity', 'task', members=[visual])
    context.register_reference(proxy, 'proxy', owner='entity')
    assert set(context.registry) == {'entity'}
    assert context.references['proxy'] is proxy
    assert proxy['semantic_owner'] == visual['semantic_owner'] == 'entity'
    assert 'semantic_role' not in proxy and 'semantic_role' not in visual
    assert 'semantic_id' not in proxy
    assert proxy['parent'] is root
