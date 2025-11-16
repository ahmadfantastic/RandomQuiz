export const QUIZ_STATUS_INFO = {
  draft: {
    label: 'Draft',
    tone: 'bg-orange-100 text-orange-800 border-orange-200',
  },
  scheduled: {
    label: 'Scheduled',
    tone: 'bg-blue-100 text-blue-800 border-blue-200',
  },
  published: {
    label: 'Published',
    tone: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  },
  closed: {
    label: 'Closed',
    tone: 'bg-sky-100 text-sky-800 border-sky-200',
  },
};

const parseDate = (value) => {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
};

export const getQuizStatus = (quiz) => {
  const start = parseDate(quiz.start_time);
  const end = parseDate(quiz.end_time);
  const now = Date.now();

  if (!start) {
    return { key: 'draft', ...QUIZ_STATUS_INFO.draft };
  }

  if (start && end) {
    return { key: 'closed', ...QUIZ_STATUS_INFO.closed };
  }

  if (start && start > now) {
    return { key: 'scheduled', ...QUIZ_STATUS_INFO.scheduled };
  }

  return { key: 'published', ...QUIZ_STATUS_INFO.published };
};
