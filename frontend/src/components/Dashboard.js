import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';

const Dashboard = () => {
  const [quizzes, setQuizzes] = useState([]);

  useEffect(() => {
    axios.get('/api/quizzes/', { withCredentials: true }).then((res) => setQuizzes(res.data));
  }, []);

  return (
    <div className="page">
      <h1>Your Quizzes</h1>
      <Link to="/problem-banks">Manage Problem Banks</Link>
      <ul>
        {quizzes.map((quiz) => (
          <li key={quiz.id}>
            <Link to={`/quizzes/${quiz.id}`}>{quiz.title}</Link> - public link: /q/{quiz.public_id}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default Dashboard;
