import React, { useEffect, useMemo, useState } from 'react';

import AppShell from '@/components/layout/AppShell';
import Avatar from '@/components/ui/Avatar';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import api from '@/lib/api';

const defaultForm = { first_name: '', last_name: '' };

const ProfilePage = () => {
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState(defaultForm);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [filePreview, setFilePreview] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    api
      .get('/api/instructors/me/')
      .then((res) => {
        if (!isMounted) return;
        setProfile(res.data);
        setForm({
          first_name: res.data.first_name || '',
          last_name: res.data.last_name || '',
        });
      })
      .catch(() => {
        if (!isMounted) return;
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedFile) {
      setFilePreview('');
      return undefined;
    }
    const url = URL.createObjectURL(selectedFile);
    setFilePreview(url);
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [selectedFile]);

  const displayName = useMemo(() => {
    if (!profile) return 'Profile';
    const name = [profile.first_name, profile.last_name].filter(Boolean).join(' ');
    return name || profile.username;
  }, [profile]);

  const handleInputChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    setErrorMessage('');
    setSuccessMessage('');
  };

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
    event.target.value = '';
    setErrorMessage('');
    setSuccessMessage('');
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!profile) return;
    setIsSaving(true);
    setErrorMessage('');
    setSuccessMessage('');

    try {
      const payload = new FormData();
      payload.append('first_name', form.first_name);
      payload.append('last_name', form.last_name);
      if (selectedFile) {
        payload.append('profile_picture', selectedFile);
      }
      const response = await api.patch(`/api/instructors/${profile.id}/`, payload);
      setProfile(response.data);
      setForm({
        first_name: response.data.first_name || '',
        last_name: response.data.last_name || '',
      });
      setSelectedFile(null);
      setSuccessMessage('Profile updated successfully.');
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('profileUpdated', { detail: response.data }));
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      setErrorMessage(detail || 'Unable to save your profile. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const avatarSource = selectedFile ? filePreview : profile?.profile_picture_url;

  return (
    <AppShell title="Profile" description="Keep your display name and picture up to date.">
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Profile Details</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading || !profile ? (
              <p className="text-sm text-muted-foreground">Loading profile…</p>
            ) : (
              <form className="space-y-6" onSubmit={handleSubmit}>
                <div className="flex flex-col gap-4 md:flex-row">
                  <div className="flex-shrink-0">
                    <Avatar size={72} name={displayName} src={avatarSource} />
                  </div>
                  <div className="flex-1 space-y-2">
                    <Label htmlFor="profile-picture">Profile picture</Label>
                    <input
                      id="profile-picture"
                      name="profile-picture"
                      type="file"
                      accept="image/*"
                      onChange={handleFileChange}
                      className="text-sm text-muted-foreground"
                    />
                    <p className="text-xs text-muted-foreground">PNG, JPG, and WEBP files up to 5 MB. A placeholder initial is used by default.</p>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="first_name">First name</Label>
                    <Input
                      id="first_name"
                      name="first_name"
                      placeholder="First name"
                      value={form.first_name}
                      onChange={handleInputChange}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="last_name">Last name</Label>
                    <Input
                      id="last_name"
                      name="last_name"
                      placeholder="Last name"
                      value={form.last_name}
                      onChange={handleInputChange}
                    />
                  </div>
                </div>

                <div className="space-y-1 text-sm text-muted-foreground">
                  <p>
                    <span className="font-semibold text-foreground">Username:</span> {profile.username}
                  </p>
                  <p>
                    <span className="font-semibold text-foreground">Email:</span>{' '}
                    {profile.email || 'Not provided'}
                  </p>
                </div>

                {errorMessage && (
                  <p className="text-sm text-destructive" role="alert">
                    {errorMessage}
                  </p>
                )}
                {successMessage && (
                  <p className="text-sm text-primary" role="status">
                    {successMessage}
                  </p>
                )}

                <div className="flex justify-end">
                  <Button type="submit" disabled={isSaving}>
                    {isSaving ? 'Saving…' : 'Save changes'}
                  </Button>
                </div>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
};

export default ProfilePage;
