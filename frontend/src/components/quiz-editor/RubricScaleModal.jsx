import React, { useState } from 'react';
import { Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Modal } from '@/components/ui/modal';

const RubricScaleModal = ({
    open,
    onOpenChange,
    rubricForm,
    onFieldChange,
    onAddScaleOption,
    onRemoveScaleOption,
    onSave,
    isSaving,
    saveError,
    saveSuccess,
}) => {
    const scale = rubricForm?.scale ?? [];
    const [pendingDelete, setPendingDelete] = useState(null);

    const handleOpenDelete = (index) => {
        if (scale.length <= 1) return;
        setPendingDelete(index);
    };

    const handleCloseDelete = () => {
        setPendingDelete(null);
    };

    const handleConfirmDelete = () => {
        if (pendingDelete === null) return;
        onRemoveScaleOption(pendingDelete);
        setPendingDelete(null);
    };

    return (
        <>
            <Modal
                open={open}
                onOpenChange={onOpenChange}
                title="Scale options"
                description="Define the numeric ratings students can choose."
                className="max-w-2xl"
            >
                <div className="space-y-6">
                    <div className="flex justify-end">
                        <Button size="sm" variant="outline" onClick={onAddScaleOption}>
                            Add Option
                        </Button>
                    </div>

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
                                        onClick={() => handleOpenDelete(index)}
                                        disabled={scale.length <= 1}
                                        aria-label="Remove scale option"
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className="space-y-4">
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
                description="Are you sure you want to remove this scale option? This action cannot be undone."
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

export default RubricScaleModal;
