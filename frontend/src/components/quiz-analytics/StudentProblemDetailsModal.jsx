import React, { useEffect, useState } from 'react';
import { Modal } from '@/components/ui/modal';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table';
import { Loader2 } from 'lucide-react';
import api from '@/lib/api';
import { useParams } from 'react-router-dom';
import RatingChart from './RatingChart';

const StudentProblemDetailsModal = ({ isOpen, onClose, slotId, problem }) => {
    const { quizId } = useParams();
    const [loading, setLoading] = useState(false);
    const [students, setStudents] = useState([]);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchStudents = async () => {
            if (!isOpen || !problem || !quizId || !slotId) return;

            try {
                setLoading(true);
                setError(null);
                const response = await api.get(
                    `/api/quizzes/${quizId}/analytics/slots/${slotId}/problems/${problem.problem_id}/students/`
                );
                setStudents(response.data);
            } catch (err) {
                console.error('Failed to fetch student details:', err);
                setError('Failed to load student data.');
            } finally {
                setLoading(false);
            }
        };

        fetchStudents();
    }, [isOpen, problem, quizId, slotId]);

    const showTimeColumn = students.some(s => s.time_taken > 0);

    return (
        <Modal
            open={isOpen}
            onOpenChange={onClose}
            title={`Student Details: ${problem?.label}`}
            className="max-w-4xl max-h-[80vh] overflow-y-auto"
        >
            {loading ? (
                <div className="flex justify-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                </div>
            ) : error ? (
                <div className="text-destructive text-center py-4">{error}</div>
            ) : (
                <div className="space-y-6">
                    {problem && problem.criteria_distributions && problem.criteria_distributions.length > 0 && (
                        <div className="border rounded-md p-4 bg-muted/20">
                            <h4 className="text-sm font-semibold mb-4">Rating Distribution</h4>
                            <RatingChart data={{ criteria: problem.criteria_distributions }} />
                        </div>
                    )}

                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Student</TableHead>
                                <TableHead className="text-right">Score</TableHead>
                                {showTimeColumn && <TableHead className="text-right">Time Taken</TableHead>}
                                <TableHead className="text-right">Word Count</TableHead>
                                <TableHead className="text-right">Ratings</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {students.map((student) => (
                                <TableRow key={student.attempt_id}>
                                    <TableCell className="font-medium">
                                        {student.student_identifier}
                                    </TableCell>
                                    <TableCell className="text-right">
                                        {student.score}
                                    </TableCell>
                                    {showTimeColumn && (
                                        <TableCell className="text-right">
                                            {student.time_taken ? `${student.time_taken.toFixed(1)} min` : '-'}
                                        </TableCell>
                                    )}
                                    <TableCell className="text-right">
                                        {student.word_count}
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <div className="inline-flex items-end gap-1">
                                            {Object.entries(student.ratings).map(([cId, score]) => (
                                                <span key={cId} className="text-xs text-muted-foreground">
                                                    {cId}: {score},
                                                </span>
                                            ))}
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            )}
        </Modal >
    );
};

export default StudentProblemDetailsModal;
