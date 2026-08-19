// Mirrors serving/config.py's MAX_MESSAGE_LENGTH exactly — enforced
// client-side too so a user discovers the limit while typing, not only after
// the backend rejects an oversized message.
export const MAX_MESSAGE_LENGTH = 4000;
