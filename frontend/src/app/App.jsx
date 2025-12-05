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
import ProfilePage from '@/pages/ProfilePage';
import QuizAnalyticsPage from '@/pages/QuizAnalyticsPage';
import ProblemBankAnalysisPage from '@/pages/ProblemBankAnalysisPage';
import GlobalAnalysisPage from '@/pages/GlobalAnalysisPage';

const App = () => (
  <Router>
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/quizzes" element={<QuizzesPage />} />
      <Route path="/quizzes/new" element={<QuizzesPage />} />
      <Route path="/quizzes/:quizId/edit" element={<QuizEditorPage />} />
      <Route path="/quizzes/:quizId/analytics" element={<QuizAnalyticsPage />} />
      <Route path="/problem-banks" element={<ProblemBankManager />} />
      <Route path="/problem-banks/:bankId/analysis" element={<ProblemBankAnalysisPage />} />
      <Route path="/analysis/global" element={<GlobalAnalysisPage />} />
      <Route path="/admin/instructors" element={<AdminInstructorManager />} />
      <Route path="/q/:publicId" element={<PublicQuizLandingPage />} />
      <Route path="/attempts/:attemptToken" element={<QuizAttemptPage />} />
      <Route path="/thank-you" element={<ThankYouPage />} />
    </Routes>
  </Router>
);

export default App;
