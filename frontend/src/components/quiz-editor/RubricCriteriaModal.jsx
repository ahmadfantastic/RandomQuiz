import React, { useState } from 'react';
import { Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Modal } from '@/components/ui/modal';

const RubricCriteriaModal = ({
    open,
    onOpenChange,
    rubricForm,
    onFieldChange,
    onAddCriterion,
    onRemoveCriterion,
    onSave,
    isSaving,
    saveError,
    saveSuccess,
}) => {
    const criteria = rubricForm?.criteria ?? [];
    const [pendingDelete, setPendingDelete] = useState(null);

    const handleOpenDelete = (index) => {
        if (criteria.length <= 1) return;
        setPendingDelete(index);
    };

    const handleCloseDelete = () => {
        setPendingDelete(null);
    };

    const handleConfirmDelete = () => {
        if (pendingDelete === null) return;
        onRemoveCriterion(pendingDelete);
        setPendingDelete(null);
    };

    return (
        <>
            <Modal
                open={open}
                onOpenChange={onOpenChange}
                title="Rubric Criteria"
                description="Describe each dimension of the rating scale."
                className="max-w-3xl"
            >
                <div className="space-y-6">
                    <div className="flex justify-end">
                        <Button size="sm" variant="outline" onClick={onAddCriterion}>
                            Add Criterion
                        </Button>
                    </div>

                    <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-2">
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
                                        onClick={() => handleOpenDelete(index)}
                                        disabled={criteria.length <= 1}
                                        aria-label="Remove criterion"
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className="space-y-4 pt-4">
                        {saveError && (
                            <p className="text-sm text-destructive">{saveError}</p>
                        )}
                        {saveSuccess && (
                            <p className="text-sm text-emerald-600">{saveSuccess}</p>
                        )}
                        <div className="flex justify-end gap-2">
                            <Button variant="outline" onClick={() => onOpenChange(false)}>
                                Cancel
                            </Button>
                            <Button onClick={onSave} disabled={isSaving}>
                                {isSaving ? 'Saving…' : 'Save Changes'}
                            </Button>
                        </div>
                    </div>
                </div>
            </Modal>

            <Modal
                open={pendingDelete !== null}
                onOpenChange={handleCloseDelete}
                title="Confirm deletion"
                description="Are you sure you want to remove this criterion? This action cannot be undone."
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
        </>
    );
};

export default RubricCriteriaModal;
