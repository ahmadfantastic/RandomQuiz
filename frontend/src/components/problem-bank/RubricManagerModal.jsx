import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Edit2, Check, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Modal } from '@/components/ui/modal';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import api from '@/lib/api';

const RubricManagerModal = ({ open, onOpenChange, onRubricCreated }) => {
    const [rubrics, setRubrics] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [isCreating, setIsCreating] = useState(false);
    const [editingRubricId, setEditingRubricId] = useState(null);
    const [newRubric, setNewRubric] = useState({
        name: '',
        description: '',
        scale_options: [
            { order: 0, value: 1, label: 'Poor' },
            { order: 1, value: 2, label: 'Fair' },
            { order: 2, value: 3, label: 'Good' },
            { order: 3, value: 4, label: 'Excellent' }
        ],
        criteria: [
            { order: 0, id: 'c1', name: 'Quality', description: 'Overall quality', weight: 1 }
        ]
    });

    const loadRubrics = async () => {
        setIsLoading(true);
        try {
            const res = await api.get('/api/rubrics/');
            setRubrics(res.data);
        } catch (err) {
            setError('Failed to load rubrics.');
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        if (open) {
            loadRubrics();
            resetForm();
            setError('');
        }
    }, [open]);

    const resetForm = () => {
        setIsCreating(false);
        setEditingRubricId(null);
        setNewRubric({
            name: '',
            description: '',
            scale_options: [
                { order: 0, value: 1, label: 'Poor' },
                { order: 1, value: 2, label: 'Fair' },
                { order: 2, value: 3, label: 'Good' },
                { order: 3, value: 4, label: 'Excellent' }
            ],
            criteria: [
                { order: 0, id: 'c1', name: 'Quality', description: 'Overall quality', weight: 1 }
            ]
        });
    };

    const handleCreateOrUpdateRubric = async () => {
        if (!newRubric.name.trim()) {
            setError('Rubric name is required.');
            return;
        }

        try {
            const payload = {
                name: newRubric.name,
                description: newRubric.description,
                scale_options: newRubric.scale_options.map((opt, idx) => ({ ...opt, order: idx })),
                criteria: newRubric.criteria.map((crit, idx) => ({ ...crit, order: idx }))
            };

            if (editingRubricId) {
                await api.put(`/api/rubrics/${editingRubricId}/`, payload);
            } else {
                await api.post('/api/rubrics/', payload);
            }

            await loadRubrics();
            resetForm();
            if (onRubricCreated) onRubricCreated();
        } catch (err) {
            setError('Failed to save rubric. Ensure criteria IDs are unique.');
        }
    };

    const handleEditRubric = (rubric) => {
        setEditingRubricId(rubric.id);
        setNewRubric({
            name: rubric.name,
            description: rubric.description,
            scale_options: rubric.scale_options,
            criteria: rubric.criteria
        });
        setIsCreating(true);
    };

    const handleDeleteRubric = async (id) => {
        if (!window.confirm('Are you sure? This cannot be undone.')) return;
        try {
            await api.delete(`/api/rubrics/${id}/`);
            loadRubrics();
            if (onRubricCreated) onRubricCreated();
        } catch (err) {
            setError('Failed to delete rubric.');
        }
    };

    // Helper to update new rubric state
    const updateNewRubric = (field, value) => {
        setNewRubric(prev => ({ ...prev, [field]: value }));
    };

    const addScaleOption = () => {
        setNewRubric(prev => ({
            ...prev,
            scale_options: [...prev.scale_options, { order: prev.scale_options.length, value: 0, label: '' }]
        }));
    };

    const updateScaleOption = (index, field, value) => {
        setNewRubric(prev => {
            const newScale = [...prev.scale_options];
            newScale[index] = { ...newScale[index], [field]: value };
            return { ...prev, scale_options: newScale };
        });
    };

    const removeScaleOption = (index) => {
        setNewRubric(prev => ({
            ...prev,
            scale_options: prev.scale_options.filter((_, i) => i !== index)
        }));
    };

    const addCriterion = () => {
        setNewRubric(prev => ({
            ...prev,
            criteria: [...prev.criteria, { order: prev.criteria.length, id: `c${Date.now()}`, name: '', description: '', weight: 1 }]
        }));
    };

    const updateCriterion = (index, field, value) => {
        setNewRubric(prev => {
            const newCriteria = [...prev.criteria];
            newCriteria[index] = { ...newCriteria[index], [field]: value };
            return { ...prev, criteria: newCriteria };
        });
    };

    const removeCriterion = (index) => {
        setNewRubric(prev => ({
            ...prev,
            criteria: prev.criteria.filter((_, i) => i !== index)
        }));
    };

    return (
        <Modal
            open={open}
            onOpenChange={onOpenChange}
            title="Manage Rubrics"
            description="Create and manage global rubrics for problem banks."
            className="max-w-4xl"
        >
            <div className="space-y-6 max-h-[70vh] overflow-y-auto pr-2">
                {error && <div className="text-red-500 text-sm">{error}</div>}

                {isCreating ? (
                    <div className="space-y-4 border rounded-lg p-4 bg-muted/10">
                        <div className="flex justify-between items-center">
                            <h3 className="font-medium">{editingRubricId ? 'Edit Rubric' : 'New Rubric'}</h3>
                            <Button variant="ghost" size="sm" onClick={resetForm}><X className="h-4 w-4" /></Button>
                        </div>
                        <div className="space-y-2">
                            <Label>Name</Label>
                            <Input value={newRubric.name} onChange={e => updateNewRubric('name', e.target.value)} placeholder="Rubric Name" />
                        </div>
                        <div className="space-y-2">
                            <Label>Description</Label>
                            <Textarea value={newRubric.description} onChange={e => updateNewRubric('description', e.target.value)} placeholder="Description" />
                        </div>

                        <div className="border-t my-2" />

                        <div className="space-y-2">
                            <div className="flex justify-between items-center">
                                <Label>Scale Options</Label>
                                <Button variant="outline" size="sm" onClick={addScaleOption}><Plus className="h-3 w-3 mr-1" /> Add</Button>
                            </div>
                            <div className="grid gap-2">
                                {newRubric.scale_options.map((opt, idx) => (
                                    <div key={idx} className="flex gap-2 items-center">
                                        <Input type="number" step="0.1" className="w-20" value={opt.value} onChange={e => updateScaleOption(idx, 'value', parseFloat(e.target.value))} placeholder="Val" />
                                        <Input className="flex-1" value={opt.label} onChange={e => updateScaleOption(idx, 'label', e.target.value)} placeholder="Label" />
                                        <Button variant="ghost" size="icon" onClick={() => removeScaleOption(idx)}><Trash2 className="h-4 w-4 text-destructive" /></Button>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="border-t my-2" />

                        <div className="space-y-2">
                            <div className="flex justify-between items-center">
                                <Label>Criteria</Label>
                                <Button variant="outline" size="sm" onClick={addCriterion}><Plus className="h-3 w-3 mr-1" /> Add</Button>
                            </div>
                            <div className="space-y-3">
                                {newRubric.criteria.map((crit, idx) => (
                                    <div key={idx} className="border p-3 rounded-md space-y-2 bg-background">
                                        <div className="flex gap-2">
                                            <Input className="w-1/4" value={crit.id} onChange={e => updateCriterion(idx, 'id', e.target.value)} placeholder="ID" />
                                            <Input className="flex-1" value={crit.name} onChange={e => updateCriterion(idx, 'name', e.target.value)} placeholder="Name" />
                                            <Input type="number" className="w-20" value={crit.weight} onChange={e => updateCriterion(idx, 'weight', parseInt(e.target.value))} placeholder="Wgt" />
                                            <Button variant="ghost" size="icon" onClick={() => removeCriterion(idx)}><Trash2 className="h-4 w-4 text-destructive" /></Button>
                                        </div>
                                        <Input value={crit.description} onChange={e => updateCriterion(idx, 'description', e.target.value)} placeholder="Description" />
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="flex justify-end gap-2 pt-2">
                            <Button variant="outline" onClick={resetForm}>Cancel</Button>
                            <Button onClick={handleCreateOrUpdateRubric}>{editingRubricId ? 'Save Changes' : 'Create Rubric'}</Button>
                        </div>
                    </div>
                ) : (
                    <>
                        <div className="flex justify-between items-center">
                            <p className="text-sm text-muted-foreground">Manage your global rubrics.</p>
                            <Button onClick={() => setIsCreating(true)}><Plus className="h-4 w-4 mr-2" /> New Rubric</Button>
                        </div>
                        <div className="space-y-3">
                            {isLoading ? (
                                <div>Loading...</div>
                            ) : rubrics.length === 0 ? (
                                <div className="text-center text-muted-foreground py-8">No rubrics found. Create one to get started.</div>
                            ) : (
                                rubrics.map(rubric => (
                                    <Card key={rubric.id} className="flex justify-between items-center p-4">
                                        <div>
                                            <h4 className="font-medium">{rubric.name}</h4>
                                            <p className="text-sm text-muted-foreground">{rubric.description || 'No description'}</p>
                                            <div className="text-xs text-muted-foreground mt-1">
                                                {rubric.scale_options.length} scale options, {rubric.criteria.length} criteria
                                            </div>
                                        </div>
                                        <div className="flex gap-2">
                                            <Button variant="ghost" size="icon" onClick={() => handleEditRubric(rubric)}>
                                                <Edit2 className="h-4 w-4" />
                                            </Button>
                                            <Button variant="ghost" size="icon" className="text-destructive" onClick={() => handleDeleteRubric(rubric.id)}>
                                                <Trash2 className="h-4 w-4" />
                                            </Button>
                                        </div>
                                    </Card>
                                ))
                            )}
                        </div>
                    </>
                )}
            </div>
            <div className="flex justify-end pt-4">
                <Button variant="outline" onClick={() => onOpenChange(false)}>Close</Button>
            </div>
        </Modal>
    );
};

export default RubricManagerModal;
