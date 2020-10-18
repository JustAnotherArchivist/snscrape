This is snscrape's integration test suite. It is designed to catch regressions in snscrape as well as changes on the social networks being scraped.

* The same code is used for capturing the current data and for running regression and live tests against that data.
* Be warned that the test suite makes a lot of requests against the target services. You may get banned if you run it too frequently.
* The data is stored in one file per test in the `data/` subdirectory (configurable with the `SNSCRAPE_TEST_DATA_DIR` environment variable).
* The test suite is based around unittest. Execute `python3 -m unittest discover` in this directory to run it.
* To generate the data files, define the `SNSCRAPE_TEST_CAPTURE` environment variable (with any value).
* For coverage data, replace `python3` with `coverage run` in the above command, then use `coverage report --show-missing` for display.
  * If using venv, pyenv, or similar, you probably want to run `coverage report --include "$(python3 -c 'import os.path, snscrape; print(os.path.dirname(snscrape.__file__))')/*" --show-missing` instead to filter out snscrape's dependencies. Cf. [coverage issue #876](https://github.com/nedbat/coveragepy/issues/876).
* To look at the data files without suddenly feeling an inexplicable urge to gouge your own eyes out, use `python3 base.py decode FILENAME`.
