// Mirrors serving/mode_config.py's Mode enum values exactly — these strings go
// straight into the ChatRequest.mode field, so they must match the backend's
// Mode(str, Enum) values verbatim.
export const Mode = {
  CHANAKYA: 'chanakya',
  CRISIS: 'crisis',
};

export const MODE_LABEL = {
  [Mode.CHANAKYA]: 'Chanakya',
  [Mode.CRISIS]: 'Crisis Advisor',
};
