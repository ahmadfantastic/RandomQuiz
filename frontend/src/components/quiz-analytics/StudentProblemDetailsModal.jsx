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
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Student</TableHead>
                            <TableHead className="text-right">Score</TableHead>
                            <TableHead className="text-right">Time Taken</TableHead>
                            <TableHead className="text-right">Word Count</TableHead>
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
                                <TableCell className="text-right">
                                    {student.time_taken ? `${student.time_taken.toFixed(1)} min` : '-'}
                                </TableCell>
                                <TableCell className="text-right">
                                    {student.word_count}
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            )}
        </Modal>
    );
};

export default StudentProblemDetailsModal;
