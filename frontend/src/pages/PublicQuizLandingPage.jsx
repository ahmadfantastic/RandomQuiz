import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '@/lib/api';

const PublicQuizLandingPage = () => {
  const { publicId } = useParams();
  const [quiz, setQuiz] = useState(null);
  const [identifier, setIdentifier] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    api.get(`/api/public/quizzes/${publicId}/`).then((res) => setQuiz(res.data));
  }, [publicId]);

  const handleStart = async () => {
    const res = await api.post(`/api/public/quizzes/${publicId}/start/`, { student_identifier: identifier });
    navigate(`/attempts/${res.data.attempt_id}`, { state: { slots: res.data.slots, attemptId: res.data.attempt_id } });
  };

  if (!quiz) return <p>Loading...</p>;

  return (
    <div className="page">
      <h1>{quiz.title}</h1>
      <p>{quiz.description}</p>
      {!quiz.is_open && <p>This quiz is not open yet.</p>}
      <input placeholder="Your email or ID" value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
      <button disabled={!quiz.is_open} onClick={handleStart}>
        Start Quiz
      </button>
    </div>
  );
};

export default PublicQuizLandingPage;
