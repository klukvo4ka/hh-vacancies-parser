# HH Vacancies Parser

A Python tool for searching vacancies through the official [HeadHunter API](https://api.hh.ru) and exporting the results to a formatted Excel file.

## Tech stack

- Python 3.12+
- [httpx](https://www.python-httpx.org/)
- [openpyxl](https://openpyxl.readthedocs.io/)

## Status

The project is under active development.

Currently the tool can query the official HH API vacancy search and load multiple result pages sequentially. The number of loaded vacancies is capped by a configured maximum and by HH's search depth limit (2000 results). Raw API responses are normalized into typed `Vacancy` objects. Excel export is not implemented yet.
