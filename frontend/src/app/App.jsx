import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import LoginPage from '@/features/auth/pages/LoginPage';
import DashboardPage from '@/features/dashboard/pages/DashboardPage';
import QuizEditorPage from '@/pages/QuizEditorPage';
import ProblemBankManager from '@/pages/ProblemBankManager';
import AdminInstructorManager from '@/pages/AdminInstructorManager';
import PublicQuizLandingPage from '@/pages/PublicQuizLandingPage';
import QuizAttemptPage from '@/pages/QuizAttemptPage';
import ThankYouPage from '@/pages/ThankYouPage';
import QuizzesPage from '@/pages/QuizzesPage';

const App = () => (
  <Router>
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/quizzes" element={<QuizzesPage />} />
      <Route path="/quizzes/new" element={<QuizzesPage />} />
      <Route path="/quizzes/:quizId" element={<QuizEditorPage />} />
      <Route path="/problem-banks" element={<ProblemBankManager />} />
      <Route path="/admin/instructors" element={<AdminInstructorManager />} />
      <Route path="/q/:publicId" element={<PublicQuizLandingPage />} />
      <Route path="/attempts/:attemptToken" element={<QuizAttemptPage />} />
      <Route path="/thank-you" element={<ThankYouPage />} />
    </Routes>
  </Router>
);

export default App;
