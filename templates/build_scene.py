"""Agent-authored Blender scene entry point.

Use bpy, bmesh, modifiers, curves, or local source modules freely. Register
semantic roots with ``context.register`` and resolved room boundaries with
``context.register_room`` so the shared runtime can validate the result.
"""


def build_scene(context, scene_spec):
    raise NotImplementedError("Replace this template with agent-authored Blender geometry")
