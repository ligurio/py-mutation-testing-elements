#!/usr/bin/env python

import argparse
import datetime
import json
import os

from jinja2 import Template

STATUS_KILLED = "Killed"
STATUS_SURVIVED = "Survived"
STATUS_NO_COVERAGE = "NoCoverage"
STATUS_COMPILE_ERROR = "CompileError"
STATUS_RUNTIME_ERROR = "RuntimeError"
STATUS_TIMEOUT = "Timeout"
STATUS_IGNORED = "Ignored"

LIST_STATUSES = [STATUS_KILLED,
                STATUS_SURVIVED,
                STATUS_NO_COVERAGE,
                STATUS_COMPILE_ERROR,
                STATUS_RUNTIME_ERROR,
                STATUS_TIMEOUT,
                STATUS_IGNORED]

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

Schema version: {{ json_data['schemaVersion'] }}
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
<div>Killed</div> - {{ killed }}
When at least one test failed while this mutant was active, the mutant is
killed.
</div>

<div>
<div>Survived</div> - {{ survived }}
When all tests passed while this mutant was active, the mutant survived. You're
missing a test for it.
</div>

<div>
<div>No coverage</div> - {{ no_coverage }}
No tests were executed for this mutant. It probably is located in a part of the
code not hit by any of your tests. This means the mutant survived and you are
missing a test case for it.
</div>

<div>
<div>Timeout</div> - {{ timeout }}
The running of tests with this mutant active resulted in a timeout. For
example, the mutant resulted in an infinite loop in your code. Don't spend too
much attention to this mutant. It is counted as "detected". The logic here is
that if this mutant were to be injected in your code, your CI build would
detect it because the tests will never complete.
</div>

<div>
<div>Runtime error</div> - {{ runtime_error }}
The running of the tests resulted in an error (rather than a failed test). This
can happen when the testrunner fails. For example, when a testrunner throws an
OutOfMemoryError or for dynamic languages where the mutant resulted in
unparsable code. Don't spend too much attention looking at this mutant. It is
not represented in your mutation score.
</div>

<div>
<div>Compile error</div> - {{ compile_error }}
The mutant resulted in a compiler error. This can happen in compiled languages.
Don't spend too much attention looking at this mutant. It is not represented in
your mutation score.
</div>

<div>
<div>Ignored</div> - {{ ignored }}
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

Schema version: {{ json_data['schemaVersion'] }}
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
	files_mutant_statuses = []
	for file_name, properties in json_data.get("files", None).items():
		files_mutant_statuses.append({file_name: file_mutant_statuses(properties)})
	report_mutant_statuses = sum_statuses(files_mutant_statuses)

	t = Template(template)
	time = datetime.datetime.now()

	return t.render(json_data=json_data,
                    killed=report_mutant_statuses[STATUS_KILLED],
                    survived=report_mutant_statuses[STATUS_SURVIVED],
                    no_coverage=report_mutant_statuses[STATUS_NO_COVERAGE],
                    compile_error=report_mutant_statuses[STATUS_COMPILE_ERROR],
                    runtime_error=report_mutant_statuses[STATUS_RUNTIME_ERROR],
                    timeout=report_mutant_statuses[STATUS_TIMEOUT],
                    ignored=report_mutant_statuses[STATUS_IGNORED],
                    current_time=time)


def dict_statuses():
	statuses = {STATUS_KILLED: 0,
                STATUS_SURVIVED: 0,
                STATUS_NO_COVERAGE: 0,
                STATUS_COMPILE_ERROR: 0,
                STATUS_RUNTIME_ERROR: 0,
                STATUS_TIMEOUT: 0,
                STATUS_IGNORED: 0}

	return statuses


def file_mutant_statuses(json_data):
	"""
	json_data: a dict that includes dicts "file" described in
	'mutation-elements' schema.

	returns: statuses, dict with a name of status and
	a number mutants with that status.
	"""

	mutants = json_data.get("mutants", None)
	statuses = dict_statuses()
	for mutant in mutants:
		status = mutant.get("status", None)
		if not status: 
			raise Exception("status is None")

		if status == STATUS_KILLED:
			statuses[STATUS_KILLED] += 1
		elif status == STATUS_SURVIVED:
			statuses[STATUS_SURVIVED] += 1
		elif status == STATUS_NO_COVERAGE:
			statuses[STATUS_NO_COVERAGE] += 1
		elif status == STATUS_COMPILE_ERROR:
			statuses[STATUS_COMPILE_ERROR] += 1
		elif status == STATUS_RUNTIME_ERROR:
			statuses[STATUS_RUNTIME_ERROR] += 1
		elif status == STATUS_TIMEOUT:
			statuses[STATUS_TIMEOUT] += 1
		elif status == STATUS_IGNORED:
			statuses[STATUS_IGNORED] += 1

	return statuses


def sum_statuses(list_of_statuses_per_file):
	"""
	list_of_statuses: list of dicts {file_name: dict with statuses}
	"""
	total_num_statuses = dict_statuses()
	statuses = []
	for d in list_of_statuses_per_file:
		statuses += list(d.values())
	for st in LIST_STATUSES:
		total_num_statuses[st] = sum(d[st] for d in statuses)
	
	return total_num_statuses


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
