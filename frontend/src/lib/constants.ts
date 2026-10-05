/** Mirrors serving/config.py MAX_MESSAGE_LENGTH; enforced client-side so users see the limit while typing. */
export const MAX_MESSAGE_LENGTH = 4000

/** Mirrors serving/disclaimer.py NOT_LEGAL_ADVICE_LINE. Crisis answers always contain it; the UI lifts it into a footer. */
export const NOT_LEGAL_ADVICE_LINE =
  'This is not legal advice. For regulatory or legal questions, the client should consult qualified counsel.'

/** Mirrors serving/app.py TRUNCATION_NOTICE, appended when the model hit max_tokens. */
export const TRUNCATION_NOTICE = '[Response truncated — ask a follow-up for more detail.]'
