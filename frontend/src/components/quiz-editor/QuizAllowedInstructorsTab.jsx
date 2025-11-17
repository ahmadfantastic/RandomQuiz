import React from 'react';
import { Trash2, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import Avatar from '@/components/ui/Avatar';

const QuizAllowedInstructorsTab = ({
  allowedInstructors,
  instructorId,
  setInstructorId,
  handleAddInstructor,
  handleRemoveInstructor,
  loadInstructors,
  instructorError,
  canManageCollaborators,
}) => (
  <div className="space-y-6">
    <div className="flex items-center justify-between">
      <div>
        <h3 className="text-lg font-semibold">Allowed Instructors</h3>
        <p className="text-sm text-muted-foreground">
          Grant other instructors access to edit this quiz
        </p>
      </div>
      <Button variant="outline" onClick={loadInstructors}>Refresh</Button>
    </div>

    {instructorError && (
      <Card className="border-destructive/30 bg-destructive/5">
        <CardContent className="py-3 text-sm text-destructive">{instructorError}</CardContent>
      </Card>
    )}

    <Card>
      <CardContent className="pt-6 space-y-4">
        <div className="space-y-2">
          <Label htmlFor="instructor-id">Add Instructor by Username</Label>
            <div className="flex gap-2">
              <Input 
                id="instructor-id"
                value={instructorId} 
                onChange={(e) => setInstructorId(e.target.value)} 
                placeholder="Enter instructor username"
                className="flex-1"
              />
            <Button
              onClick={handleAddInstructor}
              disabled={!instructorId.trim() || !canManageCollaborators}
            >
              Add
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Enter the instructor username to grant quiz access
          </p>
          {!canManageCollaborators && (
            <p className="text-xs font-semibold uppercase text-muted-foreground/80">
              Only the quiz owner can manage instructors.
            </p>
          )}
        </div>
      </CardContent>
    </Card>

    {!allowedInstructors.length ? (
      <Card>
        <CardContent className="py-12 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
            <Users className="h-8 w-8 text-muted-foreground" />
          </div>
          <p className="text-lg font-semibold">No collaborators yet</p>
          <p className="text-sm text-muted-foreground">Add instructors above to allow them to edit this quiz</p>
        </CardContent>
      </Card>
    ) : (
      <div className="space-y-3">
        {allowedInstructors.map((inst) => {
          const fullName = [inst.first_name, inst.last_name].filter(Boolean).join(' ');
          return (
            <Card key={inst.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <Avatar
                      size={40}
                      name={fullName || inst.username}
                      src={inst.profile_picture_url}
                      className="flex-shrink-0"
                    />
                    <div>
                      <p className="flex flex-wrap items-center gap-2 font-semibold">
                        {fullName ? <span>{fullName}</span> : <span>{inst.username}</span>}
                        <span className="text-xs text-muted-foreground">@{inst.username}</span>
                        {inst.is_owner && (
                          <span className="rounded-full border border-primary/50 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-primary">
                            Owner
                          </span>
                        )}
                      </p>
                      <p className="text-sm text-muted-foreground">{inst.email}</p>
                    </div>
                  </div>
                  {inst.is_owner ? (
                    <span className="text-xs font-semibold uppercase text-muted-foreground">Owner</span>
                  ) : (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleRemoveInstructor(inst.id)}
                      className="text-destructive hover:text-destructive"
                      disabled={!canManageCollaborators}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    )}
  </div>
);

export default QuizAllowedInstructorsTab;
