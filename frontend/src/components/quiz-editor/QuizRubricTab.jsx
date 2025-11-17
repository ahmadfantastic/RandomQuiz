import React, { useState } from 'react';
import { Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Modal } from '@/components/ui/modal';

const QuizRubricTab = ({
  rubricForm,
  isLoading,
  loadError,
  onReload,
  onFieldChange,
  onAddScaleOption,
  onRemoveScaleOption,
  onAddCriterion,
  onRemoveCriterion,
  onSave,
  isSaving,
  saveError,
  saveSuccess,
}) => {
  const scale = rubricForm?.scale ?? [];
  const criteria = rubricForm?.criteria ?? [];
  const hasScale = scale.length > 0;
  const hasCriteria = criteria.length > 0;
  const isFormReady = hasScale && hasCriteria;
  const [pendingDelete, setPendingDelete] = useState(null);

  const handleOpenDelete = (type, index) => {
    if (type === 'scale' && scale.length <= 1) return;
    if (type === 'criteria' && criteria.length <= 1) return;
    setPendingDelete({ type, index });
  };

  const handleCloseDelete = () => {
    setPendingDelete(null);
  };

  const handleConfirmDelete = () => {
    if (!pendingDelete) return;
    if (pendingDelete.type === 'scale') {
      onRemoveScaleOption(pendingDelete.index);
    } else {
      onRemoveCriterion(pendingDelete.index);
    }
    setPendingDelete(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Rating rubric</h3>
          <p className="text-sm text-muted-foreground">
            Control the rating scale and the criteria students use when giving feedback.
          </p>
        </div>
        <Button variant="outline" onClick={onReload} disabled={isLoading}>
          Refresh
        </Button>
      </div>

      {isLoading && (
        <Card>
          <CardContent className="py-3 text-sm text-muted-foreground">Loading rubric…</CardContent>
        </Card>
      )}

      {loadError && (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="py-3 text-sm text-destructive">{loadError}</CardContent>
        </Card>
      )}

      {saveError && (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="py-3 text-sm text-destructive">{saveError}</CardContent>
        </Card>
      )}

      {saveSuccess && (
        <Card className="border-emerald-400/50 bg-emerald-500/5">
          <CardContent className="py-3 text-sm text-emerald-700">{saveSuccess}</CardContent>
        </Card>
      )}

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr),minmax(0,1fr)]">
        <Card className="space-y-4">
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-base font-semibold">Scale options</p>
                <p className="text-sm text-muted-foreground">Define the numeric ratings students can choose.</p>
              </div>
              <Button size="sm" variant="outline" onClick={onAddScaleOption}>
                Add Option
              </Button>
            </div>
            {!rubricForm && !isLoading ? (
              <p className="text-sm text-muted-foreground">Rubric data is unavailable.</p>
            ) : (
              <div className="space-y-4">
                {scale.map((option, index) => (
                  <div key={`scale-${index}`} className="grid gap-3 sm:grid-cols-[100px,1fr,auto]">
                    <div>
                      <Label htmlFor={`scale-value-${index}`}>Value</Label>
                      <Input
                        id={`scale-value-${index}`}
                        type="number"
                        value={option.value}
                        onChange={(event) => onFieldChange('scale', index, 'value', event.target.value)}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`scale-label-${index}`}>Label</Label>
                      <Input
                        id={`scale-label-${index}`}
                        value={option.label}
                        onChange={(event) => onFieldChange('scale', index, 'label', event.target.value)}
                      />
                    </div>
                    <div className="flex items-end">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-destructive hover:bg-destructive/10 focus-visible:ring-destructive/50"
                        onClick={() => handleOpenDelete('scale', index)}
                        disabled={scale.length <= 1}
                        aria-label="Remove scale option"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
        <Card className="space-y-4">
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-base font-semibold">Criteria</p>
                <p className="text-sm text-muted-foreground">Describe each dimension of the rating scale.</p>
              </div>
              <Button size="sm" variant="outline" onClick={onAddCriterion}>
                Add Criterion
              </Button>
            </div>
            <div className="space-y-4">
              {!rubricForm && !isLoading && (
                <p className="text-sm text-muted-foreground">Rubric data is unavailable.</p>
              )}
              {criteria.map((criterion, index) => (
                <div key={`criterion-${index}`} className="rounded-2xl border bg-background p-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <Label htmlFor={`criterion-id-${index}`}>ID</Label>
                      <Input
                        id={`criterion-id-${index}`}
                        value={criterion.id}
                        onChange={(event) => onFieldChange('criteria', index, 'id', event.target.value)}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`criterion-name-${index}`}>Name</Label>
                      <Input
                        id={`criterion-name-${index}`}
                        value={criterion.name}
                        onChange={(event) => onFieldChange('criteria', index, 'name', event.target.value)}
                      />
                    </div>
                  </div>
                  <div className="mt-3">
                    <Label htmlFor={`criterion-description-${index}`}>Description</Label>
                    <Textarea
                      id={`criterion-description-${index}`}
                      value={criterion.description}
                      onChange={(event) => onFieldChange('criteria', index, 'description', event.target.value)}
                      rows={2}
                    />
                  </div>
                  <div className="mt-3 text-right">
                    <Button
                      size="icon"
                      variant="ghost"
                      className="text-destructive hover:bg-destructive/10 focus-visible:ring-destructive/50"
                      onClick={() => handleOpenDelete('criteria', index)}
                      disabled={criteria.length <= 1}
                      aria-label="Remove criterion"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </section>

      <div className="flex justify-end">
        <Button onClick={onSave} disabled={isSaving || isLoading || !isFormReady}>
          {isSaving ? 'Saving…' : 'Save rubric'}
        </Button>
      </div>
      <Modal
        open={Boolean(pendingDelete)}
        onOpenChange={handleCloseDelete}
        title="Confirm deletion"
        description={`Are you sure you want to remove this ${pendingDelete?.type === 'scale' ? 'scale option' : 'criterion'}? This action cannot be undone.`}
      >
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={handleCloseDelete}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={handleConfirmDelete}>
            Delete
          </Button>
        </div>
      </Modal>
    </div>
  );
};

export default QuizRubricTab;
