import { useCallback, useRef, useState } from 'react';
import api from '@/lib/api';

const useProblemStatements = () => {
  const [statements, setStatements] = useState({});
  const loadingIds = useRef(new Set());

  const loadStatement = useCallback(async (problemId) => {
    if (loadingIds.current.has(problemId)) {
      return;
    }
    loadingIds.current.add(problemId);
    setStatements((prev) => ({
      ...prev,
      [problemId]: { ...(prev[problemId] || {}), loading: true, error: null },
    }));
    try {
      const response = await api.get(`/api/problems/${problemId}/`);
      const statement = response.data?.statement ?? '';
      setStatements((prev) => ({
        ...prev,
        [problemId]: { statement },
      }));
      return statement;
    } catch (error) {
      const detail = error?.response?.data?.detail || 'Unable to load this problem statement right now.';
      setStatements((prev) => ({
        ...prev,
        [problemId]: { error: detail },
      }));
      return undefined;
    } finally {
      loadingIds.current.delete(problemId);
    }
  }, []);

  const resetStatements = useCallback(() => {
    loadingIds.current.clear();
    setStatements({});
  }, []);

  return { statements, loadStatement, resetStatements };
};

export default useProblemStatements;
