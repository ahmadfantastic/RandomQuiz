import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '@/lib/api';

const AllowedInstructorsPage = () => {
  const { quizId } = useParams();
  const [list, setList] = useState([]);
  const [instructorId, setInstructorId] = useState('');

  const load = () => {
    api.get(`/api/quizzes/${quizId}/allowed-instructors/`).then((res) => setList(res.data));
  };

  useEffect(() => {
    load();
  }, [quizId]);

  const handleAdd = async () => {
    await api.post(
      `/api/quizzes/${quizId}/allowed-instructors/`,
      { instructor_id: instructorId },
    );
    setInstructorId('');
    load();
  };

  const handleRemove = async (id) => {
    await api.delete(`/api/quizzes/${quizId}/allowed-instructors/${id}/`);
    load();
  };

  return (
    <div className="page">
      <h3>Allowed Instructors</h3>
      <input value={instructorId} onChange={(e) => setInstructorId(e.target.value)} placeholder="Instructor ID" />
      <button onClick={handleAdd}>Add</button>
      <ul>
        {list.map((inst) => (
          <li key={inst.id}>
            {inst.username} ({inst.email})
            <button onClick={() => handleRemove(inst.id)}>Remove</button>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default AllowedInstructorsPage;
