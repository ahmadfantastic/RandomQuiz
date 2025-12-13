import React, { useState, useMemo, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import SlotInteractionTimeline from './SlotInteractionTimeline';
import CorrelationAnalysis from './CorrelationAnalysis';

const AllSlotInteractions = ({ slots }) => {
    const [selectedStudent, setSelectedStudent] = useState('');

    if (!slots || slots.length === 0) return null;

    // Get unique students across all slots
    const students = useMemo(() => {
        const allStudents = new Set();
        slots.forEach(slot => {
            if (slot.interactions) {
                slot.interactions.forEach(i => allStudents.add(i.student_id));
            }
        });
        return [...allStudents].sort();
    }, [slots]);

    // Set initial student if not set
    useEffect(() => {
        if (!selectedStudent && students.length > 0) {
            setSelectedStudent(students[0]);
        }
    }, [students, selectedStudent]);

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold">Student Interaction Timeline</h2>
                {students.length > 0 && (
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground">Student:</span>
                        <select
                            value={selectedStudent}
                            onChange={(e) => setSelectedStudent(e.target.value)}
                            className="text-sm border rounded px-2 py-1 bg-background"
                        >
                            {students.map(student => (
                                <option key={student} value={student}>
                                    {student}
                                </option>
                            ))}
                        </select>
                    </div>
                )}
            </div>
            {slots.map((slot) => (
                <Card key={slot.id}>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base font-medium">{slot.label}</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {selectedStudent && slot.metrics && slot.metrics[selectedStudent] && slot.response_type !== 'rating' && (
                            <div className="mb-6 rounded-md border text-sm">
                                <div className="grid grid-cols-4 divide-x bg-muted/50 p-2 font-medium text-muted-foreground text-center">
                                    <div>Initial Planning Latency</div>
                                    <div>Revision Ratio</div>
                                    <div>Burstiness (&gt;10s)</div>
                                    <div>WPM</div>
                                </div>
                                <div className="grid grid-cols-4 divide-x p-2 font-semibold text-center">
                                    <div>{slot.metrics[selectedStudent].ipl?.toFixed(2)}s</div>
                                    <div>{slot.metrics[selectedStudent].revision_ratio?.toFixed(4)}</div>
                                    <div>{slot.metrics[selectedStudent].burstiness}</div>
                                    <div>{slot.metrics[selectedStudent].wpm?.toFixed(2)}</div>
                                </div>
                            </div>
                        )}
                        <div className="-mt-4 -pt-4 border-t-0">
                            <SlotInteractionTimeline
                                interactions={slot.interactions}
                                selectedStudent={selectedStudent}
                            />
                        </div>
                        {slot.metric_correlations && slot.response_type !== 'rating' && (
                            <div className="mt-6">
                                <CorrelationAnalysis
                                    data={Object.values(slot.metric_correlations).filter(Boolean)}
                                    title="Usage vs Score Correlations"
                                    description="Correlation between writing metrics and slot score."
                                    xAxisLabel="Metric Value"
                                    yAxisLabel="Score"
                                />
                            </div>
                        )}
                    </CardContent>
                </Card>
            ))}
        </div>
    );
};

export default AllSlotInteractions;
