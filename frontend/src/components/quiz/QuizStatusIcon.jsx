import React from 'react';
import { Pencil, Clock, CheckCircle2, Lock } from 'lucide-react';

const ICONS = {
  draft: Pencil,
  scheduled: Clock,
  published: CheckCircle2,
  closed: Lock,
};

const QuizStatusIcon = ({ statusKey, className }) => {
  const Icon = ICONS[statusKey];
  if (!Icon) return null;
  return <Icon className={className} />;
};

export default QuizStatusIcon;
