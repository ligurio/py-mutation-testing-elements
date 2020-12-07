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
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
    <meta http-equiv="X-UA-Compatible" content="IE=9"/>
    <meta name="description" content="Mutation testing results">
    <title>Mutation testing results</title>
</head>

<body>
<div>
<div>Mutation states</div>
<div>
<div>Killed</div>
When at least one test failed while this mutant was active, the mutant is
killed. This is what you want, good job!
</div>

<div>
<div>Survived</div>
When all tests passed while this mutant was active, the mutant survived. You're
missing a test for it.
</div>

<div>
<div>No coverage</div>
No tests were executed for this mutant. It probably is located in a part of the
code not hit by any of your tests. This means the mutant survived and you are
missing a test case for it.
</div>

<div>
<div>Timeout</div>
The running of tests with this mutant active resulted in a timeout. For
example, the mutant resulted in an infinite loop in your code. Don't spend too
much attention to this mutant. It is counted as "detected". The logic here is
that if this mutant were to be injected in your code, your CI build would
detect it because the tests will never complete.
</div>

<div>
<div>Runtime error</div>
The running of the tests resulted in an error (rather than a failed test). This
can happen when the testrunner fails. For example, when a testrunner throws an
OutOfMemoryError or for dynamic languages where the mutant resulted in
unparsable code. Don't spend too much attention looking at this mutant. It is
not represented in your mutation score.
</div>

<div>
<div>Compile error</div>
The mutant resulted in a compiler error. This can happen in compiled languages.
Don't spend too much attention looking at this mutant. It is not represented in
your mutation score.
</div>

<div>
<div>Ignored</div>
The mutant was not tested because the config of the user asked for it to be
ignored. This will not count against your mutation score but will show up in
reports.
</div>
</div>

<div>
<div>Mutation metrics</div>
<ul>
<li>Detected (killed + timeout) - The number of mutants detected by your tests.
<li>Undetected (survived + no coverage) - The number of mutants that are not
detected by your tests.</li>
<li>Covered (detected + survived) - The number of mutants that your tests
produce code coverage for.</li>
<li>Valid (detected + undetected) - The number of valid mutants. They didn't
result in a compile error or runtime error.</li>
<li>Invalid (runtime errors + compile errors) - The number of invalid mutants.
They couldn't be tested because they produce either a compile error or a
runtime error.</li>
<li>Total mutants (valid + invalid + ignored) - All mutants.</li>
<li>Mutation score (detected / valid * 100) - The total percentage of mutants
that were killed.</li>
<li>Mutation score based on covered code (detected / covered * 100) - The total
percentage of mutants that were killed based on the code coverage results.</li>
</div>

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
</body>
</html>
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
