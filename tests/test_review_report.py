from embodied_scene.review import new_report


def test_new_report_passes_without_findings() -> None:
    report = new_report("demo")
    assert report["status"] == "pass"
    assert report["findings"] == []

