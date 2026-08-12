# Third-party skills vendored into flux

Five skill directories in here are verbatim copies of skills from the
[`mattpocock-skills`](https://github.com/mattpocock/skills) plugin, carried rather than
depended on (ADR-0009):

| Directory | Upstream path |
| --- | --- |
| `grilling/` | `skills/productivity/grilling/` |
| `domain-modeling/` | `skills/engineering/domain-modeling/` |
| `prototype/` | `skills/engineering/prototype/` |
| `tdd/` | `skills/engineering/tdd/` |
| `codebase-design/` | `skills/engineering/codebase-design/` |

**Copied from `mattpocock-skills` version 1.2.3.** Each directory is byte-for-byte
upstream — sibling reference files and `agents/openai.yaml` included — so a re-sync is a
diff rather than a reconstruction. Nothing in this repo edits them in place; anything flux
wants to say differently it says in its own skills.

## Fetching a newer copy

Upstream ships through the official marketplace, and installing it puts an unpacked copy
on disk:

    claude plugin install mattpocock-skills@claude-plugins-official
    SRC=~/.claude/plugins/cache/claude-plugins-official/mattpocock-skills/<version>/skills
    diff -r "$SRC/productivity/grilling"          skills/grilling
    diff -r "$SRC/engineering/domain-modeling"    skills/domain-modeling
    diff -r "$SRC/engineering/prototype"          skills/prototype
    diff -r "$SRC/engineering/tdd"                skills/tdd
    diff -r "$SRC/engineering/codebase-design"    skills/codebase-design

Read the diff, copy across what you want, and update the version named above. Upstream
moves without telling us; nothing here checks for a newer release.

## Licence

The five directories listed above are used under the MIT licence:

    MIT License

    Copyright (c) 2026 Matt Pocock

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
