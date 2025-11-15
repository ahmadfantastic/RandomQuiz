import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const OverviewCards = ({ quizzes, isLoading }) => {
  const totalQuizzes = quizzes.length;
  const scheduled = quizzes.filter((quiz) => Boolean(quiz.start_time)).length;
  const published = quizzes.filter((quiz) => Boolean(quiz.public_id)).length;

  const metrics = [
    { label: 'Total quizzes', value: totalQuizzes },
    { label: 'Scheduled', value: scheduled },
    { label: 'Published links', value: published },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {metrics.map((metric) => (
        <Card key={metric.label}>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">{metric.label}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{isLoading ? '—' : metric.value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
};

export default OverviewCards;
