import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const Sparkline = ({ points = [], width = '100%', height = 80 }) => {
  if (!points.length) return <div className="h-20 flex items-center justify-center text-sm text-muted-foreground">No data</div>;
  
  const max = Math.max(...points.map((p) => p.count), 1);
  const min = Math.min(...points.map((p) => p.count));
  const range = max - min || 1;
  
  return (
    <div className="relative" style={{ height }}>
      <svg width="100%" height="100%" preserveAspectRatio="none" className="block">
        <defs>
          <linearGradient id="gradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.2" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0.05" />
          </linearGradient>
        </defs>
        {points.map((p, i) => {
          const x = (i / Math.max(points.length - 1, 1)) * 100;
          const y = 100 - ((p.count - min) / range) * 100;
          const barWidth = 100 / points.length * 0.6;
          return (
            <rect
              key={i}
              x={`${x - barWidth / 2}%`}
              y={`${y}%`}
              width={`${barWidth}%`}
              height={`${100 - y}%`}
              fill="url(#gradient)"
              stroke="currentColor"
              strokeWidth="1.5"
              className="text-primary"
            />
          );
        })}
      </svg>
      <div className="absolute bottom-0 left-0 right-0 flex justify-between px-1 text-[10px] text-muted-foreground">
        {points.map((p, i) => (
          i % Math.ceil(points.length / 7) === 0 && (
            <span key={i}>{new Date(p.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
          )
        ))}
      </div>
    </div>
  );
};

const StatCard = ({ title, value, subtitle, isLoading }) => (
  <Card>
    <CardContent className="pt-6">
      {isLoading ? (
        <div className="space-y-3">
          <div className="h-4 w-20 animate-pulse rounded bg-muted" />
          <div className="h-8 w-24 animate-pulse rounded bg-muted" />
        </div>
      ) : (
        <div>
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <p className="mt-2 text-3xl font-bold">{value ?? '—'}</p>
          {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
        </div>
      )}
    </CardContent>
  </Card>
);

const OverviewCards = ({ stats, isLoading }) => {
  const s = stats || {};
  const completionRate = s.attempt_count > 0 ? Math.round((s.completed_attempts / s.attempt_count) * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Key metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Attempts"
          value={s.attempt_count}
          subtitle={`${s.attempts_today ?? 0} today`}
          isLoading={isLoading}
        />
        <StatCard
          title="Active Quizzes"
          value={s.published_quizzes}
          subtitle={`${s.scheduled_quizzes ?? 0} scheduled`}
          isLoading={isLoading}
        />
        <StatCard
          title="Completion Rate"
          value={`${completionRate}%`}
          subtitle={`${s.completed_attempts ?? 0} completed`}
          isLoading={isLoading}
        />
        <StatCard
          title="Problem Banks"
          value={s.problem_bank_count}
          subtitle={`${s.problem_count ?? 0} problems`}
          isLoading={isLoading}
        />
      </div>

      {/* Activity chart */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Activity Trend</CardTitle>
            <p className="text-sm text-muted-foreground">Quiz attempts over the last 7 days</p>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-32 animate-pulse rounded-md bg-muted" />
            ) : (
              <Sparkline points={s.attempts_over_time || []} height={120} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quick Stats</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoading ? (
              <div className="space-y-3">
                <div className="h-12 animate-pulse rounded bg-muted" />
                <div className="h-12 animate-pulse rounded bg-muted" />
              </div>
            ) : (
              <>
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Total Quizzes</span>
                    <span className="text-2xl font-bold">{s.quiz_count ?? 0}</span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {s.slot_count ?? 0} slots • {s.assigned_slots ?? 0} assigned
                  </div>
                </div>
                <div className="border-t pt-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Avg per Quiz</span>
                    <span className="text-2xl font-bold">{s.avg_slots_per_quiz ?? 0}</span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">slots per quiz</div>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Super admin stats */}
      {!isLoading && s.super_admin && s.super_admin_stats && (
        <Card className="border-primary/20 bg-primary/5">
          <CardHeader>
            <CardTitle className="text-base">System Overview</CardTitle>
            <p className="text-sm text-muted-foreground">Platform-wide statistics</p>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <div className="text-2xl font-bold">{s.super_admin_stats.total_instructors}</div>
                <div className="text-sm text-muted-foreground">Total Instructors</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{s.super_admin_stats.admin_instructors}</div>
                <div className="text-sm text-muted-foreground">Admin Instructors</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{s.super_admin_stats.total_quizzes}</div>
                <div className="text-sm text-muted-foreground">All Quizzes</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{s.super_admin_stats.total_problem_banks}</div>
                <div className="text-sm text-muted-foreground">All Banks</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default OverviewCards;
