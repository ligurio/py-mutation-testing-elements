#!/usr/bin/env python

import argparse
import datetime
import json
import os

from jinja2 import Template

SUPPORTED_SCHEMA_VERSIONS = ["1.0"]

DEFAULT_TEXT_TEMPLATE = """
{% set files = json_data['files'] %}

{% for filename, properties in files.items() %}
Filename: {{ filename }}
Mutants:
{% for mutant in properties['mutants'] %}
{{mutant['mutatorName']}}, {{mutant['status']}}
{% endfor %}
{% endfor %}

Schema version: {{ version }}
Time of generation: {{ current_time.strftime('%d-%m-%Y %H:%M') }}
"""

DEFAULT_HTML_TEMPLATE = """
{% set files = json_data['files'] %}

{% for filename, properties in files.items() %}
<p>Filename: {{ filename }}</p>
<p>Mutants:</p>
{% for mutant in properties['mutants'] %}
<ul>
<li>{{mutant['mutatorName']}}, {{mutant['status']}}</li>
</ul>
{% endfor %}
{% endfor %}

<p>Schema version: {{ version }}</p>
<p>Time of generation: {{ current_time.strftime('%d-%m-%Y %H:%M') }}</p>
"""

def print_stdout(json_data):
	schema_version = json_data.get("schemaVersion", None)
	print("Version:", schema_version)
	for file_name, properties in json_data["files"].items():
		print("Filename: {}".format(file_name))
		language = properties.get("language", None)
		source_code = properties.get("source", None)
		# print(language, source_code)
		for mutants in properties["mutants"]:
			id = mutants["id"]
			mutatorName = mutants.get("mutatorName", None)
			replacement = mutants.get("replacement", None)
			status = mutants.get("status", None)
			print("\t{}: {}".format(mutatorName, status))


def render_template(json_data, template):
	t = Template(template)
	time = datetime.datetime.now()
	schema_version = json_data.get("schemaVersion", None)

	return t.render(json_data=json_data, version=schema_version, current_time=time)

if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--data", dest="data_path", default="",
			required=True, help="Path to a JSON data (required)")
	parser.add_argument("--report", dest="report_path", default="",
			help="Path to a generated report")
	parser.add_argument("--html", dest="html", action="store_true",
			help="Use HTML in a generated report")
	args = parser.parse_args()

	if not os.path.exists(args.data_path):
		print("Path {} doesn't exist.".format(args.data_path))
		exit(1)

	raw_data = ""
	with open(args.data_path, "r") as f:
		raw_data = f.read()

	json_data = json.loads(raw_data)
	schema_version = json_data.get("schemaVersion", None)
	if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
		print("Version of schema ({}) used in a report is unsupported.".format(schema_version))
		exit(1)

	template = DEFAULT_TEXT_TEMPLATE
	if args.html:
		template = DEFAULT_HTML_TEMPLATE

	report_data = render_template(json_data, template)
	if args.report_path:
		with open(args.report_path, "w") as report:
			report.write(report_data)
	else:
		print(report_data)
