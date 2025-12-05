import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import LoginForm from '@/components/auth/LoginForm';
import { hasAuthFlag } from '@/lib/auth';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

const LoginPage = () => {
  const navigate = useNavigate();

  useEffect(() => {
    if (hasAuthFlag()) {
      navigate('/dashboard', { replace: true });
    }
  }, [navigate]);

  return (
    <div className="min-h-screen bg-muted/30">
      <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col justify-center px-4 py-12 lg:flex-row lg:items-center lg:gap-16">
        <div className="flex-1 space-y-6 text-center lg:text-left">
          <p className="text-sm font-semibold tracking-[0.2em] text-muted-foreground">RANDOM QUIZ PLATFORM</p>
          <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            Welcome back, instructor
          </h1>
          <p className="text-lg text-muted-foreground">
            Sign in to orchestrate quizzes, curate problem banks, and keep your students on track.
          </p>
        </div>
        <div className="flex-1">
          <Card className="mx-auto max-w-md">
            <CardHeader className="space-y-2">
              <CardTitle>Instructor login</CardTitle>
              <CardDescription>Use your campus credentials to access the dashboard.</CardDescription>
            </CardHeader>
            <CardContent>
              <LoginForm />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
