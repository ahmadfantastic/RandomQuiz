import React, { useEffect, useState } from 'react';
import AppShell from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Modal } from '@/components/ui/modal';
import Avatar from '@/components/ui/Avatar';
import api from '@/lib/api';

const defaultForm = { username: '', email: '', password: '', is_admin_instructor: false };

const AdminInstructorManager = () => {
  const [instructors, setInstructors] = useState([]);
  const [form, setForm] = useState(defaultForm);
  const [errorMessage, setErrorMessage] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);

  const load = () => {
    api.get('/api/instructors/').then((res) => setInstructors(res.data));
  };

  useEffect(() => {
    load();
  }, []);

  const handleChange = (event) => {
    const { name, value, type, checked } = event.target;
    setErrorMessage('');
    setForm({ ...form, [name]: type === 'checkbox' ? checked : value });
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    setErrorMessage('');
    try {
      await api.post('/api/instructors/', form);
      setForm(defaultForm);
      load();
      setIsModalOpen(false);
    } catch (err) {
      const data = err.response?.data;
      const detail =
        (Array.isArray(data?.username) && data.username[0]) ||
        data?.detail ||
        'Could not invite the instructor. Please try again.';
      setErrorMessage(detail);
    }
  };

  const toggleAdmin = async (id, value) => {
    await api.patch(`/api/instructors/${id}/`, { is_admin_instructor: value });
    load();
  };

  const remove = async (id) => {
    await api.delete(`/api/instructors/${id}/`);
    load();
  };

  const isFormValid = form.username.trim() && form.email.trim() && form.password.trim();

  return (
    <AppShell
      title="Team access"
      description="Invite instructors to collaborate on problem banks and quizzes. Manage admin privileges from one place."
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-medium text-muted-foreground">Invite colleagues whenever you need extra help.</p>
        <Button onClick={() => setIsModalOpen(true)}>Add an instructor</Button>
      </div>
      <div className="grid gap-6 lg:grid-cols-1">
        <Card className="min-h-[360px]">
          <CardHeader>
            <CardTitle>Current instructors</CardTitle>
            <CardDescription>Toggle admin status or remove collaborators at any time.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {instructors.length === 0 && <p className="text-sm text-muted-foreground">No instructors yet.</p>}
            {instructors.map((inst) => {
              const isSelf = Boolean(inst.is_self);
              const fullName = [inst.first_name, inst.last_name].filter(Boolean).join(' ');
              return (
                <div key={inst.id} className="rounded-xl border px-4 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <Avatar
                        size={40}
                        name={fullName}
                        src={inst.profile_picture_url}
                        className="flex-shrink-0"
                      />
                      <div>
                        <p className="flex flex-wrap items-center gap-2 font-semibold">
                          {fullName && <span>{fullName}</span>}
                          <span className="text-xs text-muted-foreground">@{inst.username}</span>
                          {isSelf && <span className="text-xs font-medium text-muted-foreground">(You)</span>}
                        </p>
                        <p className="text-sm text-muted-foreground">{inst.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <label className="flex items-center gap-2 text-sm font-medium">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border border-input"
                          checked={inst.is_admin_instructor}
                          onChange={(e) => toggleAdmin(inst.id, e.target.checked)}
                          disabled={isSelf}
                          title={isSelf ? 'You cannot modify your own access' : undefined}
                        />
                        Admin
                      </label>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-destructive hover:text-destructive"
                        onClick={() => remove(inst.id)}
                        disabled={isSelf}
                        title={isSelf ? 'You cannot remove yourself' : undefined}
                      >
                        Remove
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      </div>
      <Modal
        open={isModalOpen}
        onOpenChange={(open) => {
          setIsModalOpen(open);
          if (!open) {
            setErrorMessage('');
          }
        }}
        title="Invite an instructor"
        description="Each instructor gets their own login and permissions."
      >
        <form className="space-y-4" onSubmit={handleCreate}>
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input id="username" name="username" value={form.username} onChange={handleChange} placeholder="jane-doe" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              name="email"
              value={form.email}
              onChange={handleChange}
              placeholder="jane@example.com"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Temporary password</Label>
            <Input
              id="password"
              type="password"
              name="password"
              value={form.password}
              onChange={handleChange}
              placeholder="********"
            />
          </div>
          <label className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium">
            <input
              type="checkbox"
              name="is_admin_instructor"
              checked={form.is_admin_instructor}
              onChange={handleChange}
              className="h-4 w-4 rounded border border-input"
            />
            Grant admin privileges
          </label>
          {errorMessage && (
            <p className="text-sm text-destructive" role="alert">
              {errorMessage}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!isFormValid}>
              Invite instructor
            </Button>
          </div>
        </form>
      </Modal>
    </AppShell>
  );
};

export default AdminInstructorManager;
