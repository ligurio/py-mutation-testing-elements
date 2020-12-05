import json
import os
import pytest
from generate import render_template, DEFAULT_TEXT_TEMPLATE

@pytest.mark.parametrize("data_filename", [("additional-properties-report.json"),
                    ("missing-mutant-location-report.json"),
                    ("missing-replacement-report.json"),
                    ("missing-version-report.json"),
                    ("strict-report.json")])
def test_render_template(data_filename):
    test_path = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(test_path, "static", data_filename) 
    with open(data_path, "r") as f:
        buf = f.read()
        json_buf = json.loads(buf)
        report_buf = render_template(json_buf, DEFAULT_TEXT_TEMPLATE)
