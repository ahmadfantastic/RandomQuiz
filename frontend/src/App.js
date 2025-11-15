import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import LoginPage from './components/LoginPage';
import Dashboard from './components/Dashboard';
import QuizEditorPage from './components/QuizEditorPage';
import AllowedInstructorsPage from './components/AllowedInstructorsPage';
import SlotsManagerPage from './components/SlotsManagerPage';
import ProblemBankManager from './components/ProblemBankManager';
import AdminInstructorManager from './components/AdminInstructorManager';
import PublicQuizLandingPage from './components/PublicQuizLandingPage';
import QuizAttemptPage from './components/QuizAttemptPage';
import ThankYouPage from './components/ThankYouPage';

const App = () => (
  <Router>
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/quizzes/:quizId" element={<QuizEditorPage />} />
      <Route path="/quizzes/:quizId/slots" element={<SlotsManagerPage />} />
      <Route path="/quizzes/:quizId/allowed-instructors" element={<AllowedInstructorsPage />} />
      <Route path="/problem-banks" element={<ProblemBankManager />} />
      <Route path="/admin/instructors" element={<AdminInstructorManager />} />
      <Route path="/q/:publicId" element={<PublicQuizLandingPage />} />
      <Route path="/attempts/:attemptId" element={<QuizAttemptPage />} />
      <Route path="/thank-you" element={<ThankYouPage />} />
    </Routes>
  </Router>
);

export default App;
