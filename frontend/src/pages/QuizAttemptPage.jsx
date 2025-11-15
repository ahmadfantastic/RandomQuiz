import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import api from '@/lib/api';

const QuizAttemptPage = () => {
  const { attemptId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [slots, setSlots] = useState(location.state?.slots || []);

  useEffect(() => {
    if (!slots.length && location.state?.attemptId) {
      setSlots(location.state.slots);
    }
  }, [slots.length, location.state]);

  const handleSave = async (slotId, answerText) => {
    await api.post(`/api/public/attempts/${attemptId}/slots/${slotId}/answer/`, { answer_text: answerText });
    alert('Saved');
  };

  const handleComplete = async () => {
    await api.post(`/api/public/attempts/${attemptId}/complete/`);
    navigate('/thank-you');
  };

  return (
    <div className="page">
      <h1>Quiz Attempt</h1>
      {slots.map((slot) => (
        <ProblemAnswer key={slot.id} slot={slot} onSave={handleSave} />
      ))}
      <button onClick={handleComplete}>Submit Quiz</button>
    </div>
  );
};

const ProblemAnswer = ({ slot, onSave }) => {
  const [answer, setAnswer] = useState('');
  return (
    <div className="problem-card">
      <h3>
        {slot.slot_label} - {slot.problem_display_label}
      </h3>
      <p>{slot.problem_statement}</p>
      <textarea value={answer} onChange={(e) => setAnswer(e.target.value)} />
      <button onClick={() => onSave(slot.slot, answer)}>Save Answer</button>
    </div>
  );
};

export default QuizAttemptPage;
