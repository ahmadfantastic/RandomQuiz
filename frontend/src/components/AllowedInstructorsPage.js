import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useParams } from 'react-router-dom';

const AllowedInstructorsPage = () => {
  const { quizId } = useParams();
  const [list, setList] = useState([]);
  const [instructorId, setInstructorId] = useState('');

  const load = () => {
    axios.get(`/api/quizzes/${quizId}/allowed-instructors/`, { withCredentials: true }).then((res) => setList(res.data));
  };

  useEffect(() => {
    load();
  }, [quizId]);

  const handleAdd = async () => {
    await axios.post(
      `/api/quizzes/${quizId}/allowed-instructors/`,
      { instructor_id: instructorId },
      { withCredentials: true }
    );
    setInstructorId('');
    load();
  };

  const handleRemove = async (id) => {
    await axios.delete(`/api/quizzes/${quizId}/allowed-instructors/${id}/`, { withCredentials: true });
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
