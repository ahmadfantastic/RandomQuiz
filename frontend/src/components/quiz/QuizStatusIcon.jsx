import React from 'react';

const ICONS = {
  draft: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor">
      <path
        d="M4.5 9.5l5-5 5 5M9.5 4.5v11"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.5"
      />
    </svg>
  ),
  scheduled: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor">
      <circle cx="10" cy="10" r="6" strokeWidth="1.5" />
      <path d="M10 6.5v4l2 2" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
    </svg>
  ),
  published: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor">
      <path
        d="M6 10l2 2 4-4"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.5"
      />
      <circle cx="10" cy="10" r="5.5" strokeWidth="1.5" />
    </svg>
  ),
  closed: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor">
      <rect x="6" y="8" width="8" height="6" rx="1.5" strokeWidth="1.5" />
      <path d="M8 8V6a2 2 0 1 1 4 0v2" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
    </svg>
  ),
};

const QuizStatusIcon = ({ statusKey, className }) => {
  const node = ICONS[statusKey];
  if (!node) return null;
  return <span className={className}>{node}</span>;
};

export default QuizStatusIcon;
