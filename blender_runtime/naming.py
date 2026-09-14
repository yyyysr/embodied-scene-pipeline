COLLECTIONS = ("STRUCTURE", "ROOMS", "ASSETS", "TASK", "__REVIEW__")


def object_name(kind: str, semantic_id: str) -> str:
    return f"{kind}__{semantic_id}"

