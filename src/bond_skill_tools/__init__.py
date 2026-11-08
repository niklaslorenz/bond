"""Ready-made skill tool files for Bond.

Each module in this package is meant to be copied into a skill's ``tools/``
directory (next to the skill's ``SKILL.md``)::

    skills/my-skill/tools/pdf_tools.py

The skill loader discovers ``*_tools.py`` files there automatically and exposes
the exported toolsets under the ``sk:<skill-name>:`` prefix once the skill is
loaded.
"""
