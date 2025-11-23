import React, { useState, useMemo, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import SlotInteractionTimeline from './SlotInteractionTimeline';

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
                <h2 className="text-xl font-semibold">Interaction Analysis</h2>
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
                        <div className="-mt-4 -pt-4 border-t-0">
                            <SlotInteractionTimeline
                                interactions={slot.interactions}
                                selectedStudent={selectedStudent}
                            />
                        </div>
                    </CardContent>
                </Card>
            ))}
        </div>
    );
};

export default AllSlotInteractions;
