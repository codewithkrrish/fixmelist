# fixmelist

I kept losing track of the TODOs I left in my own projects. Grep finds them,
but grep also finds every TODO in `node_modules` and in strings that aren't
comments, and it doesn't tell me anything at a glance. So I wrote the small
tool I actually wanted: point it at a folder, get a clean list of every
TODO, FIXME, HACK and XXX comment, grouped by file.

## Example

```
$ fixmelist my-project

src/server.py (3)
  42: [TODO] retry the webhook on 5xx
  118: [FIXME] this leaks a connection on error
  203: [HACK] sleep avoids a race, fix properly
src/utils.py (1)
  7: [TODO] cache this lookup
```

## Install

fixmelist needs Python 3.10 or newer. Until it's on PyPI, install it
straight from GitHub:

```
pip install git+https://github.com/codewithkrrish/fixmelist.git
```

Or clone it and run it without installing:

```
git clone https://github.com/codewithkrrish/fixmelist.git
cd fixmelist
python -m fixmelist path/to/your/project
```

## Usage

```
fixmelist [path] [--tag TAG] [--format text|json|markdown]
          [--output FILE] [--force] [--dry-run]
          [--include-hidden] [--include-vendor]
```

| Flag | What it does |
| ---- | ------------ |
| `path` | Directory to scan (default: current directory) |
| `--tag TAG` | Only report this tag; repeatable |
| `--format` | `text` (default), `json`, or `markdown` |
| `--output FILE` | Write the report to a file instead of stdout |
| `--force` | Overwrite `--output` if it already exists |
| `--dry-run` | Scan and report what would be written, without writing |
| `--include-hidden` | Also scan hidden files and directories |
| `--include-vendor` | Also scan `vendor`, `node_modules`, and `Pods` |

By default, hidden directories and vendored folders (`.git`, `__pycache__`,
`node_modules`, `vendor`, `venv`, `dist`, and friends) are skipped — a
report full of somebody else's TODOs is useless. Binary files are skipped
too.

JSON output is handy for scripts and CI:

```
fixmelist . --format json | python -c "import json,sys; print(json.load(sys.stdin)['total'])"
```

Markdown output pastes nicely into an issue or a pull request when you
want to turn a pile of TODOs into actual tickets.

## What it understands

Line comments and block comments across common languages: `#` for Python
and shell, `//` and `/* */` for C-like languages, `--` for SQL and Lua,
`<!-- -->` for HTML and Markdown, and a generic fallback for anything
else. A tag needs to sit inside a comment — `TODO = 5` in code is not
reported.

## Project structure

```
src/fixmelist/
  scanner.py   # walks the tree, finds markers in comments
  report.py    # renders findings as text, JSON, or Markdown
  cli.py       # argument parsing and output handling
tests/
  test_scanner.py
  test_report.py
  test_cli.py
```

## Limitations, honestly

- This is a line scanner, not a parser. A comment marker inside a string
  literal (like `"# TODO: not a comment"`) will show up as a finding.
- It doesn't understand every language's comment syntax; unknown file
  types get the generic `#`, `//`, `--`, `/* */` set, which is wrong
  sometimes.
- It only finds markers it knows: TODO, FIXME, HACK, XXX by default,
  or whatever you pass with `--tag`. It can't tell you which TODOs
  actually matter — that's still your call.

## Development

```
pip install pytest
python -m pytest
```

## License

MIT — see [LICENSE](LICENSE).

## Author

[Krrish](https://github.com/codewithkrrish)
