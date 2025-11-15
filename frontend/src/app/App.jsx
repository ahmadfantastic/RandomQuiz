import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import LoginPage from '@/features/auth/pages/LoginPage';
import DashboardPage from '@/features/dashboard/pages/DashboardPage';
import QuizEditorPage from '@/pages/QuizEditorPage';
import AllowedInstructorsPage from '@/pages/AllowedInstructorsPage';
import SlotsManagerPage from '@/pages/SlotsManagerPage';
import ProblemBankManager from '@/pages/ProblemBankManager';
import AdminInstructorManager from '@/pages/AdminInstructorManager';
import PublicQuizLandingPage from '@/pages/PublicQuizLandingPage';
import QuizAttemptPage from '@/pages/QuizAttemptPage';
import ThankYouPage from '@/pages/ThankYouPage';

const App = () => (
  <Router>
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
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
