# mutation-testing-elements

is a generator of single page reports with mutation testing results using
[schema](https://github.com/stryker-mutator/mutation-testing-elements/tree/master/packages/mutation-testing-report-schema)
written on Python.

Supported schema versions: 1.0

```
$ pip install -r requirements.txt
$ PYTHONPATH=. pytest tests/
$ ./generate.py --data tests/static/additional-properties-report.json
...
```
