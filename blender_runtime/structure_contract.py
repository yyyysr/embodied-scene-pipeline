from __future__ import annotations


def _point(value, dimensions: int, label: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != dimensions:
        raise ValueError(f"{label} must contain exactly {dimensions} coordinates")
    return [float(coordinate) for coordinate in value]


def _orientation(first, second, third) -> float:
    return (second[0] - first[0]) * (third[1] - first[1]) - (
        second[1] - first[1]
    ) * (third[0] - first[0])


def _on_segment(first, point, second, tolerance: float = 1e-9) -> bool:
    return (
        min(first[0], second[0]) - tolerance
        <= point[0]
        <= max(first[0], second[0]) + tolerance
        and min(first[1], second[1]) - tolerance
        <= point[1]
        <= max(first[1], second[1]) + tolerance
    )


def _segments_intersect(first, second, third, fourth) -> bool:
    values = (
        _orientation(first, second, third),
        _orientation(first, second, fourth),
        _orientation(third, fourth, first),
        _orientation(third, fourth, second),
    )
    if values[0] * values[1] < 0 and values[2] * values[3] < 0:
        return True
    return any(
        abs(orientation) < 1e-9 and _on_segment(segment_start, point, segment_end)
        for orientation, segment_start, point, segment_end in (
            (values[0], first, third, second),
            (values[1], first, fourth, second),
            (values[2], third, first, fourth),
            (values[3], third, second, fourth),
        )
    )


def _self_intersects(polygon) -> bool:
    count = len(polygon)
    edges = [(polygon[index], polygon[(index + 1) % count]) for index in range(count)]
    for first_index, first_edge in enumerate(edges):
        for second_index in range(first_index + 1, count):
            if second_index in {first_index - 1, first_index + 1}:
                continue
            if first_index == 0 and second_index == count - 1:
                continue
            if _segments_intersect(*first_edge, *edges[second_index]):
                return True
    return False


class StructureContract:
    """Resolved spatial topology emitted by agent-authored structure code."""

    def __init__(self, scene_id: str, source_status: str = "unspecified"):
        self.scene_id = scene_id
        self.source_status = source_status
        self.rooms: dict[str, dict] = {}
        self.walls: dict[str, dict] = {}
        self.openings: dict[str, dict] = {}

    def register_room(
        self,
        room_id: str,
        floor_polygon,
        height: float,
        floor_z: float = 0.0,
        source: str | None = None,
    ) -> None:
        if room_id in self.rooms:
            raise ValueError(f"Duplicate room ID: {room_id}")
        polygon = [_point(point, 2, f"room {room_id} polygon point") for point in floor_polygon]
        if len(polygon) < 3:
            raise ValueError(f"Room {room_id} requires at least three polygon points")
        height = float(height)
        if height <= 0:
            raise ValueError(f"Room {room_id} height must be positive")
        area_twice = sum(
            first[0] * second[1] - second[0] * first[1]
            for first, second in zip(polygon, polygon[1:] + polygon[:1])
        )
        if abs(area_twice) < 1e-9:
            raise ValueError(f"Room {room_id} polygon has zero area")
        if _self_intersects(polygon):
            raise ValueError(f"Room {room_id} polygon is self-intersecting")
        self.rooms[room_id] = {
            "floor_polygon": polygon,
            "floor_z": float(floor_z),
            "ceiling_z": float(floor_z) + height,
            "height": height,
            **({"source": source} if source else {}),
        }

    def register_wall(
        self,
        wall_id: str,
        start,
        end,
        thickness: float,
        height: float,
        adjacent_rooms=(),
    ) -> None:
        if wall_id in self.walls:
            raise ValueError(f"Duplicate wall ID: {wall_id}")
        start_point = _point(start, 2, f"wall {wall_id} start")
        end_point = _point(end, 2, f"wall {wall_id} end")
        if start_point == end_point:
            raise ValueError(f"Wall {wall_id} has zero length")
        if thickness <= 0 or height <= 0:
            raise ValueError(f"Wall {wall_id} thickness and height must be positive")
        rooms = list(adjacent_rooms)
        if len(rooms) > 2:
            raise ValueError(f"Wall {wall_id} can border at most two rooms")
        self.walls[wall_id] = {
            "start": start_point,
            "end": end_point,
            "thickness": float(thickness),
            "height": float(height),
            "adjacent_rooms": rooms,
        }

    def register_opening(
        self,
        opening_id: str,
        connects,
        center,
        width: float,
        height: float,
        wall_id: str | None = None,
    ) -> None:
        if opening_id in self.openings:
            raise ValueError(f"Duplicate opening ID: {opening_id}")
        connected_rooms = list(connects)
        if len(connected_rooms) not in (1, 2):
            raise ValueError("An opening must connect one or two spaces")
        if width <= 0 or height <= 0:
            raise ValueError("Opening width and height must be positive")
        self.openings[opening_id] = {
            "connects": connected_rooms,
            "center": _point(center, 3, f"opening {opening_id} center"),
            "width": float(width),
            "height": float(height),
            **({"wall_id": wall_id} if wall_id else {}),
        }

    def to_dict(self) -> dict:
        for wall_id, wall in self.walls.items():
            missing_rooms = set(wall["adjacent_rooms"]) - set(self.rooms)
            if missing_rooms:
                raise ValueError(
                    f"Wall {wall_id} references unknown rooms: {sorted(missing_rooms)}"
                )
        for opening_id, opening in self.openings.items():
            missing_rooms = set(opening["connects"]) - set(self.rooms)
            if missing_rooms:
                raise ValueError(
                    f"Opening {opening_id} references unknown rooms: {sorted(missing_rooms)}"
                )
            wall_id = opening.get("wall_id")
            if wall_id and wall_id not in self.walls:
                raise ValueError(f"Opening {opening_id} references unknown wall: {wall_id}")
        return {
            "scene_id": self.scene_id,
            "status": "accepted" if self.source_status == "accepted" else "resolved",
            "source_status": self.source_status,
            "coordinate_system": {"units": "meters", "up_axis": "Z"},
            "rooms": self.rooms,
            "walls": self.walls,
            "openings": self.openings,
        }
