"""15-shablon 5-slayd fonining barcha takrorlarda saqlanishini sinaydi."""
import io
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from pptx import Presentation

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import build_slide_structure_15


NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
GREEN = "476629"
TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "shablonlar" / "15.pptx"


def visible_slide_paths(pptx_bytes: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(pptx_bytes)) as archive:
        presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
        relationships = ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))

    rel_targets = {
        relation.get("Id"): "ppt/" + relation.get("Target").lstrip("/")
        for relation in relationships.findall(f"{{{REL_NS}}}Relationship")
    }
    return [
        rel_targets[slide_id.get(f"{{{DOC_REL_NS}}}id")]
        for slide_id in presentation.findall(".//p:sldId", NS)
    ]


def background_color(pptx_bytes: bytes, slide_path: str) -> str | None:
    with zipfile.ZipFile(io.BytesIO(pptx_bytes)) as archive:
        xml = archive.read(slide_path)
    root = ET.fromstring(xml)
    color = root.find(".//p:bg/p:bgPr/a:solidFill/a:srgbClr", {
        "p": NS["p"],
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    })
    return color.get("val") if color is not None else None


def rendered_structure(requested: int) -> tuple[bytes, int]:
    presentation = Presentation(TEMPLATE)
    total_content = build_slide_structure_15(presentation, requested)
    assert total_content == requested
    result = io.BytesIO()
    presentation.save(result)
    return result.getvalue(), len(presentation.slides)


def test_repeated_green_backgrounds() -> None:
    for requested in (5, 10, 15, 20, 25, 30):
        output, slide_count = rendered_structure(requested)
        assert slide_count == requested + 3

        # Plan (2), every green fifth content slide, and final conclusion retain
        # the original green background. The repeated locations are 10..30.
        expected_green = {2, *range(5, requested + 1, 5), requested + 3}
        actual_green = {
            position
            for position, slide_path in enumerate(visible_slide_paths(output), start=1)
            if background_color(output, slide_path) == GREEN
        }
        assert actual_green == expected_green, (
            f"requested={requested}: expected green slides {expected_green}, "
            f"got {actual_green}"
        )


if __name__ == "__main__":
    test_repeated_green_backgrounds()
    print("TEMPLATE15_REPEATED_GREEN_BACKGROUND_TEST_OK")
