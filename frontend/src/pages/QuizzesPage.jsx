import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import AppShell from '@/components/layout/AppShell';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Modal } from '@/components/ui/modal';
import QuizStatusIcon from '@/components/quiz/QuizStatusIcon';
import api from '@/lib/api';
import { hasAuthFlag } from '@/lib/auth';
import { getQuizStatus } from '@/lib/quizStatus';
import { renderProblemMarkupHtml } from '@/lib/markdown';
import MDEditor from '@uiw/react-md-editor';
import '@uiw/react-markdown-preview/markdown.css';
import '@uiw/react-md-editor/markdown-editor.css';

const defaultCreateForm = {
  title: '',
  description: '',
};

const QuizzesPage = () => {
  const [quizzes, setQuizzes] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [createForm, setCreateForm] = useState(() => ({ ...defaultCreateForm }));
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (!hasAuthFlag()) {
      setError('Sign in to view your quizzes.');
      setIsLoading(false);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    api
      .get('/api/quizzes/')
      .then((res) => {
        if (!isMounted) return;
        setQuizzes(res.data || []);
        setError('');
      })
      .catch((err) => {
        if (!isMounted) return;
        if (err.response?.status === 403) {
          setError('You need to be signed in to access quizzes.');
        } else {
          setError('Unable to load quizzes at the moment.');
        }
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (location.pathname === '/quizzes/new') {
      setIsCreateModalOpen(true);
      setCreateForm({ ...defaultCreateForm });
      setCreateError('');
    }
  }, [location.pathname]);

  const openCreateModal = () => {
    setCreateForm({ ...defaultCreateForm });
    setCreateError('');
    setIsCreateModalOpen(true);
  };

  const closeCreateModal = () => {
    setIsCreateModalOpen(false);
    setCreateError('');
    setCreateForm({ ...defaultCreateForm });
    if (location.pathname === '/quizzes/new') {
      navigate('/quizzes', { replace: true });
    }
  };

  const handleCreateChange = (event) => {
    const { name, value } = event.target;
    setCreateForm((prev) => ({ ...prev, [name]: value }));
    setCreateError('');
  };

  const handleCreateDescriptionChange = (value) => {
    setCreateForm((prev) => ({ ...prev, description: value ?? '' }));
    setCreateError('');
  };

  const isCreateFormValid = Boolean(createForm.title.trim());

  const handleCreateSubmit = async (event) => {
    event.preventDefault();
    if (!isCreateFormValid || isCreating) return;
    setIsCreating(true);
    setCreateError('');

    try {
      const payload = {
        title: createForm.title.trim(),
        description: createForm.description.trim(),
      };
      const response = await api.post('/api/quizzes/', payload);
      navigate(`/quizzes/${response.data.id}`, { state: { created: true } });
    } catch (err) {
      const data = err.response?.data;
      const detail = (Array.isArray(data?.title) && data.title[0]) || data?.detail || 'Could not create the quiz. Please try again.';
      setCreateError(detail);
    } finally {
      setIsCreating(false);
    }
  };

  const sortedQuizzes = useMemo(
    () =>
      [...quizzes].sort((a, b) => {
        const aDate = a.start_time ? new Date(a.start_time).getTime() : 0;
        const bDate = b.start_time ? new Date(b.start_time).getTime() : 0;
        return bDate - aDate;
      }),
    [quizzes]
  );

  const renderBody = () => {
    if (isLoading) {
      return (
        <div className="grid gap-6 sm:grid-cols-2">
          {[1, 2, 3, 4].map((index) => (
            <Card key={index} className="animate-pulse">
              <CardHeader className="space-y-3">
                <div className="h-5 w-32 rounded bg-muted/70" />
                <div className="h-3 w-16 rounded bg-muted/60" />
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="h-3 w-24 rounded bg-muted/60" />
                <div className="h-3 w-16 rounded bg-muted/60" />
              </CardContent>
            </Card>
          ))}
        </div>
      );
    }

    if (!sortedQuizzes.length) {
      return (
        <div className="rounded-2xl border border-dashed border-border/80 bg-muted/10 p-6 text-center text-sm font-semibold text-muted-foreground">
          <p>No quizzes yet.</p>
          <p className="mt-1 text-xs font-normal text-muted-foreground/70">
            Create a quiz to start assigning content to students.
          </p>
          <Button size="sm" variant="outline" className="mt-4" onClick={openCreateModal}>
            Create quiz
          </Button>
        </div>
      );
    }

    return (
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {sortedQuizzes.map((quiz) => {
          const status = getQuizStatus(quiz);
          const description = quiz.description?.trim();
          const descriptionMarkup = description ? renderProblemMarkupHtml(description) : '';
          return (
            <Card key={quiz.id} className="flex flex-col border border-border/80 bg-card/70 shadow-sm">
              <CardHeader className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <CardTitle className="truncate">{quiz.title}</CardTitle>
                    <CardDescription className="text-sm mt-4 text-muted-foreground">
                      {quiz.public_id && (
                        <a
                          href={`/q/${quiz.public_id}`}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center gap-1 font-semibold text-blue-500 hover:underline"
                        >
                          <span className="font-mono text-xs tracking-tight">/q/{quiz.public_id}</span>
                        </a>
                      )}
                    </CardDescription>
                  </div>
                  <span
                    className={`flex shrink-0 items-center gap-1 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${status.tone}`}
                  >
                    <QuizStatusIcon statusKey={status.key} className="h-4 w-4 text-current" />
                    {status.label}
                  </span>
                </div>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col justify-between gap-4 pt-1">
                <div className="space-y-3 text-sm">
                  {descriptionMarkup ? (
                    <div
                      className="prose max-w-none text-sm text-muted-foreground"
                      dangerouslySetInnerHTML={{ __html: descriptionMarkup }}
                    />
                  ) : (
                    description
                  )}
                  <div className="flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                    {quiz.allowed_instructors?.length > 0 && (
                      <span className="rounded-full border border-border/80 px-2 py-1">Shared with others</span>
                    )}
                    <span className="rounded-full border border-border/80 px-2 py-1">ID {quiz.id}</span>
                  </div>
                </div>
              </CardContent>
              <div className="p-6 pt-0">
                <Button size="sm" variant="outline" to={`/quizzes/${quiz.id}`} className="w-full">
                  Open quiz
                </Button>
              </div>
            </Card>
          );
        })}
      </div>
    );
  };

  return (
    <>
      <Modal
        open={isCreateModalOpen}
        onOpenChange={(open) => {
          if (!open) closeCreateModal();
        }}
        title="Create quiz"
        description="Give your quiz a title and description before moving on to the editor."
      >
        <form className="space-y-6" onSubmit={handleCreateSubmit}>
          <div className="space-y-2">
            <Label htmlFor="quiz-title">Quiz title</Label>
            <Input
              id="quiz-title"
              name="title"
              value={createForm.title}
              onChange={handleCreateChange}
              placeholder="Weekly comprehension check"
              maxLength={120}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="quiz-description">Description</Label>
            <MDEditor
              value={createForm.description ?? ''}
              onChange={(value) => handleCreateDescriptionChange(value)}
              height={200}
              preview="edit"
              textareaProps={{
                id: 'quiz-description',
                name: 'description',
                placeholder: 'Outline instructions, allowed materials, or grading weight.',
              }}
            />
            <p className="text-xs text-muted-foreground">
              Format instructions with Markdown; preview updates live as you type.
            </p>
          </div>
          {createError && (
            <p className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
              {createError}
            </p>
          )}
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="outline" type="button" onClick={closeCreateModal}>
              Cancel
            </Button>
            <Button type="submit" disabled={!isCreateFormValid || isCreating}>
              {isCreating ? 'Creating…' : 'Create quiz'}
            </Button>
          </div>
        </form>
      </Modal>
      <AppShell
        title="Quizzes"
        description="Browse every quiz so you can jump straight into editing or publishing."
        actions={<Button onClick={openCreateModal}>New quiz</Button>}
      >
        <div className="space-y-6">
          {error && (
            <p className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-2 text-sm text-destructive">
              {error}
            </p>
          )}
          {renderBody()}
        </div>
      </AppShell>
    </>
  );
};

export default QuizzesPage;
