export const RESPONSE_TYPE_OPTIONS = [
  { value: 'open_text', label: 'Open-ended answer' },
  { value: 'rating', label: 'Problem rating' },
];

export const getResponseTypeLabel = (value) => {
  const match = RESPONSE_TYPE_OPTIONS.find((option) => option.value === value);
  return match ? match.label : 'Open-ended answer';
};
