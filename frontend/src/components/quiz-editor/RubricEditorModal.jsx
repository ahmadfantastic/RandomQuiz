import React, { useState, useEffect } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Modal } from '@/components/ui/modal';
import api from '@/lib/api';

const RubricEditorModal = ({ open, onOpenChange, quizId, onSaveSuccess }) => {
    const [rubric, setRubric] = useState({ items: [] });
    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (open && quizId) {
            loadRubric();
        }
    }, [open, quizId]);

    const loadRubric = async () => {
        setIsLoading(true);
        try {
            const res = await api.get(`/api/quizzes/${quizId}/grading-rubric/`);
            setRubric(res.data || { items: [] });
            setError('');
        } catch (err) {
            setError('Unable to load the grading rubric.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleSave = async () => {
        setIsSaving(true);
        setError('');
        try {
            await api.put(`/api/quizzes/${quizId}/grading-rubric/`, rubric);
            if (onSaveSuccess) onSaveSuccess();
            onOpenChange(false);
        } catch (err) {
            setError('Failed to save rubric.');
        } finally {
            setIsSaving(false);
        }
    };

    const addItem = () => {
        setRubric(prev => ({
            ...prev,
            items: [
                ...prev.items,
                {
                    order: prev.items.length,
                    label: 'New Criteria',
                    description: '',
                    levels: [
                        { order: 0, points: 0, label: 'Level 1', description: '' }
                    ]
                }
            ]
        }));
    };

    const updateItem = (index, field, value) => {
        setRubric(prev => {
            const newItems = [...prev.items];
            newItems[index] = { ...newItems[index], [field]: value };
            return { ...prev, items: newItems };
        });
    };

    const removeItem = (index) => {
        setRubric(prev => ({
            ...prev,
            items: prev.items.filter((_, i) => i !== index)
        }));
    };

    const addLevel = (itemIndex) => {
        setRubric(prev => {
            const newItems = [...prev.items];
            const item = newItems[itemIndex];
            newItems[itemIndex] = {
                ...item,
                levels: [
                    ...item.levels,
                    { order: item.levels.length, points: 0, label: 'New Level', description: '' }
                ]
            };
            return { ...prev, items: newItems };
        });
    };

    const updateLevel = (itemIndex, levelIndex, field, value) => {
        setRubric(prev => {
            const newItems = [...prev.items];
            const item = newItems[itemIndex];
            const newLevels = [...item.levels];
            newLevels[levelIndex] = { ...newLevels[levelIndex], [field]: value };
            newItems[itemIndex] = { ...item, levels: newLevels };
            return { ...prev, items: newItems };
        });
    };

    const removeLevel = (itemIndex, levelIndex) => {
        setRubric(prev => {
            const newItems = [...prev.items];
            const item = newItems[itemIndex];
            newItems[itemIndex] = {
                ...item,
                levels: item.levels.filter((_, i) => i !== levelIndex)
            };
            return { ...prev, items: newItems };
        });
    };

    return (
        <Modal
            open={open}
            onOpenChange={onOpenChange}
            title="Edit Grading Rubric"
            description="Define criteria and levels for grading."
            className="max-w-4xl"
        >
            <div className="space-y-4">
                {isLoading ? (
                    <div>Loading...</div>
                ) : (
                    <>
                        {error && <div className="text-red-500 text-sm">{error}</div>}

                        <div className="space-y-4">
                            {rubric.items.map((item, itemIndex) => (
                                <Card key={itemIndex} className="relative border-muted">
                                    <CardHeader className="pb-2 pt-4 px-4">
                                        <div className="flex items-start gap-4">
                                            <div className="flex-1 space-y-2">
                                                <div className="flex gap-2">
                                                    <div className="flex-1">
                                                        <Label>Criteria Name</Label>
                                                        <Input
                                                            value={item.label}
                                                            onChange={(e) => updateItem(itemIndex, 'label', e.target.value)}
                                                            placeholder="e.g. Accuracy"
                                                        />
                                                    </div>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="text-destructive"
                                                        onClick={() => removeItem(itemIndex)}
                                                    >
                                                        <Trash2 className="h-4 w-4" />
                                                    </Button>
                                                </div>
                                                <div>
                                                    <Label>Description</Label>
                                                    <Textarea
                                                        value={item.description}
                                                        onChange={(e) => updateItem(itemIndex, 'description', e.target.value)}
                                                        placeholder="Describe what this criteria evaluates..."
                                                        rows={2}
                                                    />
                                                </div>
                                                <div>
                                                    <Label>Instructor Code</Label>
                                                    <Input
                                                        value={item.instructor_criterion_code || ''}
                                                        onChange={(e) => updateItem(itemIndex, 'instructor_criterion_code', e.target.value)}
                                                        placeholder="e.g. acc (Matches Bank Rubric)"
                                                        className="font-mono text-sm"
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    </CardHeader>
                                    <CardContent className="px-4 pb-4">
                                        <div className="space-y-3 pl-4 border-l-2 border-muted ml-2">
                                            <div className="flex justify-between items-center">
                                                <Label className="text-xs uppercase text-muted-foreground">Levels</Label>
                                                <Button variant="ghost" size="sm" onClick={() => addLevel(itemIndex)}>
                                                    <Plus className="h-3 w-3 mr-1" /> Add Level
                                                </Button>
                                            </div>
                                            {item.levels.map((level, levelIndex) => (
                                                <div key={levelIndex} className="flex gap-3 items-start bg-muted/30 p-3 rounded-md">
                                                    <div className="w-20">
                                                        <Label className="text-xs">Points</Label>
                                                        <Input
                                                            type="number"
                                                            value={level.points}
                                                            onChange={(e) => updateLevel(itemIndex, levelIndex, 'points', parseFloat(e.target.value))}
                                                        />
                                                    </div>
                                                    <div className="w-24">
                                                        <Label className="text-xs">Mapped Value</Label>
                                                        <Input
                                                            type="number"
                                                            value={level.mapped_value || ''}
                                                            onChange={(e) => updateLevel(itemIndex, levelIndex, 'mapped_value', parseFloat(e.target.value))}
                                                            placeholder="e.g. 1.0"
                                                        />
                                                    </div>
                                                    <div className="flex-1 space-y-2">
                                                        <div>
                                                            <Label className="text-xs">Label</Label>
                                                            <Input
                                                                value={level.label}
                                                                onChange={(e) => updateLevel(itemIndex, levelIndex, 'label', e.target.value)}
                                                                placeholder="e.g. Excellent"
                                                            />
                                                        </div>
                                                        <div>
                                                            <Label className="text-xs">Description</Label>
                                                            <Textarea
                                                                value={level.description}
                                                                onChange={(e) => updateLevel(itemIndex, levelIndex, 'description', e.target.value)}
                                                                placeholder="Level description..."
                                                                rows={1}
                                                                className="min-h-[2.5rem]"
                                                            />
                                                        </div>
                                                    </div>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-6 w-6 text-muted-foreground hover:text-destructive mt-6"
                                                        onClick={() => removeLevel(itemIndex, levelIndex)}
                                                    >
                                                        <Trash2 className="h-3 w-3" />
                                                    </Button>
                                                </div>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}

                            <Button variant="outline" className="w-full border-dashed" onClick={addItem}>
                                <Plus className="h-4 w-4 mr-2" /> Add Criteria
                            </Button>
                        </div>
                    </>
                )}
            </div>
            <div className="pt-4 flex justify-end gap-2 border-t mt-4">
                <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                <Button onClick={handleSave} disabled={isSaving}>
                    {isSaving ? 'Saving...' : 'Save Changes'}
                </Button>
            </div>
        </Modal>
    );
};

export default RubricEditorModal;
