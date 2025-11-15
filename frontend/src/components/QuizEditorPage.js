import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate, useParams, Link } from 'react-router-dom';

const QuizEditorPage = () => {
  const { quizId } = useParams();
  const navigate = useNavigate();
  const [quiz, setQuiz] = useState(null);

  useEffect(() => {
    axios.get(`/api/quizzes/${quizId}/`, { withCredentials: true }).then((res) => setQuiz(res.data));
  }, [quizId]);

  const handleChange = (e) => {
    setQuiz({ ...quiz, [e.target.name]: e.target.value });
  };

  const handleSave = async () => {
    await axios.patch(`/api/quizzes/${quizId}/`, quiz, { withCredentials: true });
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
