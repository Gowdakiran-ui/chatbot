// Mirrors two literal strings from the backend exactly — both are matched
// against streamed text by substring, so any drift here silently breaks
// Piece 4's disclaimer-footer/truncation-chip detection.

// serving/disclaimer.py's NOT_LEGAL_ADVICE_LINE. Crisis-mode answers always
// contain this somewhere in the final text (serving/app.py force-appends it
// if the model didn't include it naturally) — split out and rendered as its
// own footer instead of left inline in the answer paragraph.
export const NOT_LEGAL_ADVICE_LINE =
  'This is not legal advice. For regulatory or legal questions, the client should consult qualified counsel.';

// serving/app.py's TRUNCATION_NOTICE, appended to the streamed text when
// OpenRouter's finish_reason reports max_tokens cut the response off. Left
// inline in the answer (it's honest raw output) — its presence just also
// triggers a more visible chip so a user doesn't have to spot the bracketed
// note themselves.
export const TRUNCATION_NOTICE = '\n\n[Response truncated — ask a follow-up for more detail.]';
