"""Single source of truth for the crisis-mode legal disclaimer line, so
serving/floor.py's refusal text and serving/app.py's enforcement check can't drift
from each other or from prompts/crisis_system.md's own copy (that file keeps its
own copy since it's a markdown instruction loaded by the model, not importable
Python — see CLAUDE.md's "prompts live in files, not code")."""

NOT_LEGAL_ADVICE_LINE = (
    "This is not legal advice. For regulatory or legal questions, the client "
    "should consult qualified counsel."
)
