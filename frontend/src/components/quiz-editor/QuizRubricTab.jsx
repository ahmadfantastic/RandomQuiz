import React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';

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

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-base font-semibold">Scale options</p>
            <p className="text-sm text-muted-foreground">Define the numeric ratings students can choose.</p>
          </div>
          <Button size="sm" variant="outline" onClick={onAddScaleOption}>
            Add option
          </Button>
        </div>
        {!rubricForm && !isLoading ? (
          <p className="text-sm text-muted-foreground">Rubric data is unavailable.</p>
        ) : (
          scale.map((option, index) => (
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
                  size="sm"
                  onClick={() => onRemoveScaleOption(index)}
                  disabled={scale.length <= 1}
                >
                  Remove
                </Button>
              </div>
            </div>
          ))
        )}
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-base font-semibold">Criteria</p>
            <p className="text-sm text-muted-foreground">Describe each dimension of the rating scale.</p>
          </div>
          <Button size="sm" variant="outline" onClick={onAddCriterion}>
            Add criterion
          </Button>
        </div>
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
                rows={3}
              />
            </div>
            <div className="mt-3 text-right">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => onRemoveCriterion(index)}
                disabled={criteria.length <= 1}
              >
                Remove
              </Button>
            </div>
          </div>
        ))}
      </section>

      <div className="flex justify-end">
        <Button onClick={onSave} disabled={isSaving || isLoading || !isFormReady}>
          {isSaving ? 'Saving…' : 'Save rubric'}
        </Button>
      </div>
    </div>
  );
};

export default QuizRubricTab;
