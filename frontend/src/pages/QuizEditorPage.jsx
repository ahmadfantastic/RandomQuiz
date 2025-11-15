import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import api from '@/lib/api';

const QuizEditorPage = () => {
  const { quizId } = useParams();
  const navigate = useNavigate();
  const [quiz, setQuiz] = useState(null);

  useEffect(() => {
    api.get(`/api/quizzes/${quizId}/`).then((res) => setQuiz(res.data));
  }, [quizId]);

  const handleChange = (e) => {
    setQuiz({ ...quiz, [e.target.name]: e.target.value });
  };

  const handleSave = async () => {
    await api.patch(`/api/quizzes/${quizId}/`, quiz);
    alert('Saved');
  };

  if (!quiz) return <p>Loading...</p>;

  return (
    <div className="page">
      <h2>Edit Quiz</h2>
      <label>
        Title
        <input name="title" value={quiz.title} onChange={handleChange} />
      </label>
      <label>
        Description
        <textarea name="description" value={quiz.description} onChange={handleChange} />
      </label>
      <label>
        Start Time
        <input name="start_time" value={quiz.start_time} onChange={handleChange} />
      </label>
      <label>
        End Time
        <input name="end_time" value={quiz.end_time || ''} onChange={handleChange} />
      </label>
      <p>Public link: {typeof window !== 'undefined' ? `${window.location.origin}/q/${quiz.public_id}` : 'Loading...'}</p>
      <button onClick={handleSave}>Save</button>
      <Link to={`/quizzes/${quizId}/slots`}>Manage Slots</Link>
      <Link to={`/quizzes/${quizId}/allowed-instructors`}>Allowed Instructors</Link>
    </div>
  );
};

export default QuizEditorPage;
