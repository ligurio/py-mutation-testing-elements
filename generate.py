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

# Source: https://mull.readthedocs.io/en/latest/SupportedMutations.html

MUTATION_TYPES = {"cxx_add_assign_to_sub_assign": {"old": "+=", "new": "-="},
				"cxx_add_to_sub": {"old": "+", "new": "-"},
				"cxx_and_assign_to_or_assign": {"old": "&=", "new": "|="},
				"cxx_and_to_or": {"old": "&", "new": "|"},
				"cxx_assign_const": "Replaces ‘a = b’ with ‘a = 42’",
				"cxx_bitwise_not_to_noop": "Replaces ~x with x",
				"cxx_div_assign_to_mul_assign": {"old": "/=", "new": "*="},
				"cxx_div_to_mul": {"old": "/", "new": "*"},
				"cxx_eq_to_ne": {"old": "==", "new": "!="},
				"cxx_ge_to_gt": {"old": ">=", "new": ">"},
				"cxx_ge_to_lt": {"old": ">=", "new": "<"},
				"cxx_gt_to_ge": {"old": ">", "new": ">="},
				"cxx_gt_to_le": {"old": ">", "new": "<="},
				"cxx_init_const": "Replaces ‘T a = b’ with ‘T a = 42’",
				"cxx_le_to_gt": {"old": "<=", "new": ">"},
				"cxx_le_to_lt": {"old": "<=", "new": "<"},
				"cxx_logical_and_to_or": {"old": "&&", "new": "||"},
				"cxx_logical_or_to_and": {"old": "||", "new": "&&"},
				"cxx_lshift_assign_to_rshift_assign": {"old": "<<=", "new": ">>="},
				"cxx_lshift_to_rshift": {"old": "<<", "new": ">>"},
				"cxx_lt_to_ge": {"old": "<", "new": ">="},
				"cxx_lt_to_le": {"old": "<", "new": "<="},
				"cxx_minus_to_noop": "Replaces -x with x",
				"cxx_mul_assign_to_div_assign": {"old": "*=", "new": "/="},
				"cxx_mul_to_div": {"old": "*", "new": "/"},
				"cxx_ne_to_eq": {"old": "!=", "new": "=="},
				"cxx_or_assign_to_and_assign": {"old": "|=", "new": "&="},
				"cxx_or_to_and": {"old": "|", "new": "&"},
				"cxx_post_dec_to_post_inc": "Replaces x– with x++",
				"cxx_post_inc_to_post_dec": "Replaces x++ with x–",
				"cxx_pre_dec_to_pre_inc": "Replaces –x with ++x",
				"cxx_pre_inc_to_pre_dec": "Replaces ++x with –x",
				"cxx_rem_assign_to_div_assign": {"old": "%=", "new": "/="},
				"cxx_rem_to_div": {"old": "%", "new": "/"},
				"cxx_remove_negation": "Replaces !a with a",
				"cxx_rshift_assign_to_lshift_assign": {"old": ">>=", "new": "<<="},
				"cxx_rshift_to_lshift": {"old": "<<", "new": ">>"},
				"cxx_sub_assign_to_add_assign": {"old": "-=", "new": "+="},
				"cxx_sub_to_add": {"old": "-", "new": "+"},
				"cxx_xor_assign_to_or_assign": {"old": "^=", "new": "|="},
				"cxx_xor_to_or": {"old": "^", "new": "|"},
				"negate_mutator": "Negates conditionals !x to x and x to !x",
				"remove_void_function_mutator": "Removes calls to a function returning void",
				"replace_call_mutator": "Replaces call to a function with 42",
				"scalar_value_mutator": "Replaces zeros with 42, and non-zeros with 0",
				}

LIST_STATUSES = [STATUS_KILLED,
                STATUS_SURVIVED,
                STATUS_NO_COVERAGE,
                STATUS_COMPILE_ERROR,
                STATUS_RUNTIME_ERROR,
                STATUS_TIMEOUT,
                STATUS_IGNORED]

SUPPORTED_SCHEMA_VERSIONS = ["1.0"]

INVALID_SYMBOLS = "<>:\"/\|?*. "

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

def escape_invalid_symbols(string, invalid_symbols):
	escaped_string = string
	for char in invalid_symbols:
		escaped_string = escaped_string.replace(char, '-')

	return escaped_string

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


def render_template(json_data, report_mutant_statuses, template):
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


def file_mutant_statuses(file_json_data):
	"""
	json_data: a dict that includes dicts "file" described in
	'mutation-elements' schema.

	returns: statuses, dict with a name of status and
	a number mutants with that status.
	"""

	mutants = file_json_data.get("mutants", None)
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

def file_dict_generator(json_report):
	files_dict = json_report.get("files", None)
	for file_path, properties_dict in files_dict.items():
		yield (file_path, properties_dict)

def mutant_dict_generator(file_dict):
    """
	Generate dicts with structure like below.
        {
          "id": "cxx_post_inc_to_post_dec",
          "location": {
            "end": {
              "column": 14,
              "line": 97
            },
            "start": {
              "column": 2,
              "line": 97
            }
          },
          "mutatorName": "Replaced x++ with x--",
          "replacement": "--",
          "status": "Killed"
        },
	"""
    mutants = file_dict.get("mutants", None)
    for mutant in mutants:
        yield mutant

def generate_patch_with_mutant(source_file_path, mutant_dict):
	"""
	Process a dict with sctructure like below and generate a patch with mutant.

        {
          "id": "cxx_post_inc_to_post_dec",
          "location": {
            "end": {
              "column": 14,
              "line": 97
            },
            "start": {
              "column": 2,
              "line": 97
            }
          },
          "mutatorName": "Replaced x++ with x--",
          "replacement": "--",
          "status": "Killed"
        },
	"""

	replacement = mutant_dict.get("replacement", None)
	if replacement == "":
		print("replacement is not found")
		return ""

	location = mutant_dict.get("location", None)

	loc_start = location.get("start", None)
	loc_end = location.get("end", None)

	start_column = loc_start.get("column", None)
	start_line = loc_start.get("line", None)
	end_column = loc_end.get("column", None)
	end_line = loc_end.get("line", None)

	if end_line != start_line:
		print("Start line and end line is not equal, it is unsupported")
		raise(Exception)

	print(source_file_path)
	source_code_lines = []
	with open(source_file_path, "r") as source_file:
		source_code_lines = [line.rstrip() for line in source_file]

	line_no = start_line - 1
	orig_line = source_code_lines[line_no]
	changed_line = mutate_string(orig_line, replacement, start_column, end_column)
	print("'{}' --> '{}'".format(orig_line, changed_line))
	patch_lines = []

	patch_lines.append("--- {}".format(source_file_path))
	patch_line_start = 0
	patch_line_end = len(source_code_lines)
	if start_line > 3:
		patch_line_start = start_line - 3
	if end_line < len(source_code_lines) - 3:
		patch_line_end = end_line + 3

	patch_lines.append("+++ {}".format(source_file_path))
	patch_lines.append("@@ -{},{} +{},{} @@".format(patch_line_start, start_column, patch_line_end, end_column))
	for l in range(patch_line_start, start_line - 1):
		patch_lines.append(source_code_lines[l])
	patch_lines.append("- {}".format(orig_line))
	patch_lines.append("+ {}".format(changed_line))
	for l in range(end_line, patch_line_end):
		patch_lines.append(source_code_lines[l])

	return "\n".join(patch_lines)


def mutate_string(string, replacement, start_column, end_column):
	print("{} {}, {}".format(replacement, start_column, end_column))
	print(string)
	length = end_column - start_column
	carets = "^" * length
	placeholder = " " * start_column
	print(placeholder, carets)

	return string
	

if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--data", dest="data_path", default="",
			required=True, help="Path to a JSON data (required)")
	parser.add_argument("--report", dest="report_path", default="",
			help="Path to a generated report")
	parser.add_argument("--html", dest="html", action="store_true",
			help="Use HTML in a generated report")
	parser.add_argument("--with-patches", dest="with_patches", action="store_true",
			help="Generate files with patches for each mutant")
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

	files_mutant_statuses = []
	mutant_idx = 0
	for file_path, properties_dict in file_dict_generator(json_data):
		files_mutant_statuses.append({file_path: file_mutant_statuses(properties_dict)})
		if not os.path.exists(file_path):
			print("{} is not found".format(file_path))
			continue
		escaped_source_file_basename = ""
		if args.with_patches:
			source_file_basename = os.path.basename(file_path)
			escaped_source_file_basename = escape_invalid_symbols(source_file_basename, INVALID_SYMBOLS)
		for mutant_dict in mutant_dict_generator(properties_dict):
			mutant_idx += 1
			mutant_status = mutant_dict.get("status", "unknown").lower()
			patch_buf = generate_patch_with_mutant(file_path, mutant_dict)
			if args.with_patches and patch_buf != "":
				patch_file_name = "{:05d}-{}-{}.patch".format(mutant_idx, mutant_status, escaped_source_file_basename)
				with open(patch_file_name, "w") as patch_file:
					patch_file.write(patch_buf)

	report_mutant_statuses = sum_statuses(files_mutant_statuses)

	t = Template(template)
	time = datetime.datetime.now()

	report_data = render_template(json_data, report_mutant_statuses, template)
	if args.report_path:
		with open(args.report_path, "w") as report:
			report.write(report_data)
	else:
		print(report_data)
