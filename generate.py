#!/usr/bin/env python

import argparse
import datetime
import json
import os
from junit_xml import TestSuite, TestCase
from jinja2 import Template

FORMAT_TEXT = "text"
FORMAT_HTML = "html"
FORMAT_JUNIT = "junit"

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

{% set undetected = killed + no_coverage -%}
{% set detected = killed + no_coverage -%}
{% set covered = detected + survived -%}
{% set valid = detected + undetected -%}
{% set invalid = compile_error + runtime_error -%}
{% set total = valid + invalid + ignored -%}
{% set score = detected / valid * 100 -%}
{% set score_covered = detected / covered * 100 -%}

{% set mutant_index = namespace(value=0) %}

Mutation score:{{ score }}
Mutation score based on covered code: {{ score_covered }}

{% for filename, properties in files.items() %}
Filename: {{ filename }}\n
Mutants:
{% for mutant in properties['mutants'] -%}
{% set mutant_index.value = mutant_index.value + 1 %}
#{{ mutant_index.value }} {{mutant['status']}}, {{mutant['mutatorName']}}
{%- endfor %}
{% endfor %}

Schema version: {{ json_data['schemaVersion'] }}
"""

DEFAULT_HTML_TEMPLATE = """
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
    <meta http-equiv="X-UA-Compatible" content="IE=9"/>
    <meta name="description" content="Mutation testing results">
    <title>Mutation testing results</title>
    <style>
        h1 {text-align: center;}
		body {
			background-color: #f3f2f2;
			font-size: 13pt;
			font-family: Verdana, Arial, Helvetica, Sans-Serif;
		}
		table {
			font-family: arial, sans-serif;
			border-collapse: collapse;
			align: left;
			width: 30%;
		}
		td, th {
			border: 1px solid #dddddd;
			text-align: center;
			vertical-align: middle;
			padding: 8px;
		}
		tr:nth-child(even) {
			background-color: #dddddd;
		}
		.label {
			font-size: 12pt;
			padding: 6px;
			border-radius: 10%;
			margin-right: 2px;
		}
		.footer {
			position: absolute;
			left: 50%;
			margin-left: -100px;
			text-align: center;
		}
        .metric {font-weight: bold;}
        .status {font-weight: bold;}
        .status_killed {color: green;}
        .status_survived {color: red;}
        .status_no_coverage {color: red;}
        .status_timeout {color: red;}
        .status_runtime_error {color: green;}
        .status_compile_error {color: green;}
        .status_ignored {color: red;}
    </style>
</head>

<body>
<h1>Mutation testing results</h1>
<div>
<h2>Mutation states</h2>

<table>
  <tr>
	<!-- When at least one test failed while this mutant was active, the mutant is killed. -->
    <td class="status_killed status">Killed</td>
    <td>{{ killed }}</td>
  </tr>
  <tr>
	<!-- When all tests passed while this mutant was active, the mutant survived. You're
	missing a test for it. -->
    <td class="status_survived status">Survived</td>
    <td>{{ survived }}</td>
  </tr>
  <tr>
	<!-- No tests were executed for this mutant. It probably is located in a part of the
	code not hit by any of your tests. This means the mutant survived and you are
	missing a test case for it. -->
    <td class="status_no_coverage status">No coverage</td>
    <td>{{ no_coverage }}</td>
  </tr>
  <tr>
	<!-- The running of tests with this mutant active resulted in a timeout. For
	example, the mutant resulted in an infinite loop in your code. Don't spend too
	much attention to this mutant. It is counted as "detected". The logic here is
	that if this mutant were to be injected in your code, your CI build would
	detect it because the tests will never complete. -->
    <td class="status_timeout status">Timeout</td>
    <td>{{ timeout }}</td>
  </tr>
  <tr>
	<!-- The running of the tests resulted in an error (rather than a failed test). This
	can happen when the testrunner fails. For example, when a testrunner throws an
	OutOfMemoryError or for dynamic languages where the mutant resulted in
	unparsable code. Don't spend too much attention looking at this mutant. It is
	not represented in your mutation score. -->
    <td class="status_runtime_error status">Runtime error</td>
    <td>{{ runtime_error }}</td>
  </tr>
  <tr>
	<!-- The mutant resulted in a compiler error. This can happen in compiled languages.
	Don't spend too much attention looking at this mutant. It is not represented in
	your mutation score. -->
    <td class="status_compile_error status">Compile error</td>
    <td>{{ compile_error }}</td>
  </tr>
  <tr>
	<!-- The mutant was not tested because the config of the user asked for it to be
	ignored. This will not count against your mutation score but will show up in
	reports. -->
    <td class="status_ignored status">Ignored</td>
    <td>{{ runtime_error }}</td>
  </tr>
</table>
</div>

<div>
<h2>Mutation metrics</h2>

{% set undetected = killed + no_coverage -%}
{% set detected = killed + no_coverage -%}
{% set covered = detected + survived -%}
{% set valid = detected + undetected -%}
{% set invalid = compile_error + runtime_error -%}
{% set total = valid + invalid + ignored -%}
{% set score = detected / valid * 100 -%}
{% set score_covered = detected / covered * 100 -%}

<table>
<tr>
<!--  (killed + timeout) -->
<td class="metric">Detected</td>
<td>{{undetected}}</td>
<td>The number of mutants detected by your tests</td>
</tr>
<tr>
<!--  (survived + no coverage) -->
<td class="metric">Undetected</td>
<td>{{undetected}}</td>
<td>The number of mutants that are not detected by your tests.</td>
</tr>
<tr>
<!-- (detected + survived) -->
<td class="metric">Covered</td>
<td>{{ covered }}</td>
<td>The number of mutants that your tests produce code coverage for</td>
</tr>
<tr>
<!--  (detected + undetected) -->
<td class="metric">Valid</td>
<td>{{ valid }}</td>
<td>The number of valid mutants. They didn't result in a compile error or runtime error.</td>
</tr>
<tr>
<!--  (runtime errors + compile errors) -->
<td class="metric">Invalid</div>
<td>{{ invalid }}</td>
<td>The number of invalid mutants. They couldn't be tested because they produce
either a compile error or a runtime error.</td>
</tr>
<tr>
<!--  (valid + invalid + ignored) -->
<td class="metric">Total mutants</td>
<td>{{ total }}</td>
<td>All mutants.</td>
</tr>
<tr>
<!--  (detected / valid * 100) -->
<td class="metric">Mutation score</td>
<td>{{ score }}</td>
<td>The total percentage of mutants that were killed.</td>
</tr>
<tr>
<!-- (detected / covered * 100) -->
<td class="metric">Mutation score based on covered code</div>
<td>{{ score_covered }}</td>
<td>The total percentage of mutants that were killed based on the code coverage results.</td>
</tr>
</table>

<h2>Mutants</h2>

{% set files = json_data['files'] %}
{% set mutant_index = namespace(value=0) %}

{% for filename, properties in files.items() %}
<p>Filename: {{ filename }}</p>
<table>
{% for mutant in properties['mutants'] %}
{% set mutant_index.value = mutant_index.value + 1 %}
<tr>
<td>
<a name="#{{ mutant_index.value }}">
<a href="#{{ mutant_index.value }}">#{{ loop.index }}</a>
</td>
{% if mutant['status'] == "Killed" %}
{% elif mutant['status'] == "Survived" %}
{% endif %}
<td>{{mutant['status']}}</td>
</div>
<td>{{mutant['mutatorName']}}</td>
</tr>
{% endfor %}
</table>
{% endfor %}

<div class="footer">Schema version: {{ json_data['schemaVersion'] }}, 
Time of generation: {{ current_time.strftime('%d-%m-%Y %H:%M') }},
Generated by <a href="https://github.com/ligurio/py-mutation-testing-elements">py-mutation-testing-elements</a>
</div>
</body>
</html>
"""

def to_junit(json_data):
        suites = []
        for file_name, properties in json_data["files"].items():
            source_code = properties.get("source", None)
            test_cases = []
            for mutants in properties["mutants"]:
                    # mutatorName = mutants.get("mutatorName", None)
                    mutant_id = mutants["id"]
                    replacement = mutants.get("replacement", None)
                    status = mutants.get("status", None)
                    stderr = ""
                    stdout = ""
                    if status == STATUS_SURVIVED:
                        stderr = replacement
                        stdout = replacement
                    test_case = TestCase(mutant_id, stderr, 0, stdout, stderr)
                    test_cases.append(test_case)
            suites.append(TestSuite(file_name, test_cases))

        return TestSuite.to_xml_string(suites)

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
	parser.add_argument("--format", dest="format", default=FORMAT_TEXT,
			help="Format of generated report")
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

	report_data = ""
	if args.format == FORMAT_TEXT:
		report_data = render_template(json_data, DEFAULT_TEXT_TEMPLATE)
	elif args.format == FORMAT_HTML:
		report_data = render_template(json_data, DEFAULT_HTML_TEMPLATE)
	elif args.format == FORMAT_JUNIT:
		report_data = to_junit(json_data)
	else:
		print("Unknown report format '{}'.".format(args.format))
		exit(1)

	if args.report_path:
		with open(args.report_path, "w") as report:
			report.write(report_data)
	else:
		print(report_data)
