import React, { useState, useEffect } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Modal } from '@/components/ui/modal';
import api from '@/lib/api';

const ProblemBankRubricEditor = ({ open, onOpenChange, bankId, onSaveSuccess }) => {
    const [rubric, setRubric] = useState({ scale: [], criteria: [] });
    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (open && bankId) {
            loadRubric();
        }
    }, [open, bankId]);

    const loadRubric = async () => {
        setIsLoading(true);
        try {
            const res = await api.get(`/api/problem-banks/${bankId}/rubric/`);
            // Ensure structure
            const data = res.data || {};
            setRubric({
                scale: data.scale || [],
                criteria: data.criteria || []
            });
            setError('');
        } catch (err) {
            setError('Unable to load the rubric.');
        } finally {
            setIsLoading(false);
        }
    };

    const handleSave = async () => {
        setIsSaving(true);
        setError('');
        try {
            await api.put(`/api/problem-banks/${bankId}/rubric/`, rubric);
            if (onSaveSuccess) onSaveSuccess();
            onOpenChange(false);
        } catch (err) {
            setError('Failed to save rubric.');
        } finally {
            setIsSaving(false);
        }
    };

    // Scale Management
    const addScaleOption = () => {
        setRubric(prev => ({
            ...prev,
            scale: [
                ...prev.scale,
                { value: 1, label: 'New Option' }
            ]
        }));
    };

    const updateScaleOption = (index, field, value) => {
        setRubric(prev => {
            const newScale = [...prev.scale];
            newScale[index] = { ...newScale[index], [field]: value };
            return { ...prev, scale: newScale };
        });
    };

    const removeScaleOption = (index) => {
        setRubric(prev => ({
            ...prev,
            scale: prev.scale.filter((_, i) => i !== index)
        }));
    };

    // Criteria Management
    const addCriteria = () => {
        setRubric(prev => ({
            ...prev,
            criteria: [
                ...prev.criteria,
                {
                    id: `c${Date.now()}`,
                    name: 'New Criteria',
                    description: ''
                }
            ]
        }));
    };

    const updateCriteria = (index, field, value) => {
        setRubric(prev => {
            const newCriteria = [...prev.criteria];
            newCriteria[index] = { ...newCriteria[index], [field]: value };
            return { ...prev, criteria: newCriteria };
        });
    };

    const removeCriteria = (index) => {
        setRubric(prev => ({
            ...prev,
            criteria: prev.criteria.filter((_, i) => i !== index)
        }));
    };

    return (
        <Modal
            open={open}
            onOpenChange={onOpenChange}
            title="Edit Problem Bank Rubric"
            description="Define criteria and rating scales for instructor ratings."
            className="max-w-4xl"
        >
            <div className="space-y-6 max-h-[70vh] overflow-y-auto pr-2">
                {isLoading ? (
                    <div>Loading...</div>
                ) : (
                    <>
                        {error && <div className="text-red-500 text-sm">{error}</div>}

                        {/* Scale Section */}
                        <div className="space-y-4">
                            <div className="flex justify-between items-center">
                                <h3 className="text-lg font-medium">Rating Scale</h3>
                                <Button variant="outline" size="sm" onClick={addScaleOption}>
                                    <Plus className="h-4 w-4 mr-2" /> Add Option
                                </Button>
                            </div>
                            <div className="grid gap-4">
                                {rubric.scale.map((option, index) => (
                                    <div key={index} className="flex gap-4 items-center bg-muted/30 p-3 rounded-md">
                                        <div className="w-24">
                                            <Label className="text-xs">Value</Label>
                                            <Input
                                                type="number"
                                                step="0.1"
                                                value={option.value}
                                                onChange={(e) => updateScaleOption(index, 'value', parseFloat(e.target.value) || 0)}
                                            />
                                        </div>
                                        <div className="flex-1">
                                            <Label className="text-xs">Label</Label>
                                            <Input
                                                value={option.label}
                                                onChange={(e) => updateScaleOption(index, 'label', e.target.value)}
                                                placeholder="e.g. Easy"
                                            />
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="mt-5 text-muted-foreground hover:text-destructive"
                                            onClick={() => removeScaleOption(index)}
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </Button>
                                    </div>
                                ))}
                                {rubric.scale.length === 0 && (
                                    <div className="text-sm text-muted-foreground italic">No scale options defined.</div>
                                )}
                            </div>
                        </div>

                        <div className="border-t my-4" />

                        {/* Criteria Section */}
                        <div className="space-y-4">
                            <div className="flex justify-between items-center">
                                <h3 className="text-lg font-medium">Rating Criteria</h3>
                                <Button variant="outline" size="sm" onClick={addCriteria}>
                                    <Plus className="h-4 w-4 mr-2" /> Add Criteria
                                </Button>
                            </div>
                            <div className="space-y-4">
                                {rubric.criteria.map((criterion, index) => (
                                    <Card key={index} className="relative border-muted">
                                        <CardHeader className="pb-2 pt-4 px-4">
                                            <div className="flex items-start gap-4">
                                                <div className="flex-1 space-y-2">
                                                    <div className="flex gap-2">
                                                        <div className="w-1/3">
                                                            <Label>ID</Label>
                                                            <Input
                                                                value={criterion.id}
                                                                onChange={(e) => updateCriteria(index, 'id', e.target.value)}
                                                                placeholder="unique_id"
                                                            />
                                                        </div>
                                                        <div className="flex-1">
                                                            <Label>Name</Label>
                                                            <Input
                                                                value={criterion.name}
                                                                onChange={(e) => updateCriteria(index, 'name', e.target.value)}
                                                                placeholder="e.g. Difficulty"
                                                            />
                                                        </div>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            className="text-destructive mt-6"
                                                            onClick={() => removeCriteria(index)}
                                                        >
                                                            <Trash2 className="h-4 w-4" />
                                                        </Button>
                                                    </div>
                                                    <div>
                                                        <Label>Description</Label>
                                                        <Textarea
                                                            value={criterion.description}
                                                            onChange={(e) => updateCriteria(index, 'description', e.target.value)}
                                                            placeholder="Describe this criterion..."
                                                            rows={2}
                                                        />
                                                    </div>
                                                </div>
                                            </div>
                                        </CardHeader>
                                    </Card>
                                ))}
                                {rubric.criteria.length === 0 && (
                                    <div className="text-sm text-muted-foreground italic">No criteria defined.</div>
                                )}
                            </div>
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

export default ProblemBankRubricEditor;
