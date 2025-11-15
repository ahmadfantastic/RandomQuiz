import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '@/lib/api';

const SlotsManagerPage = () => {
  const { quizId } = useParams();
  const [slots, setSlots] = useState([]);
  const [label, setLabel] = useState('');
  const [order, setOrder] = useState('');
  const [problemBank, setProblemBank] = useState('');
  const [banks, setBanks] = useState([]);
  const [bankProblems, setBankProblems] = useState({});

  const loadSlots = () => {
    api.get(`/api/quizzes/${quizId}/slots/`).then((res) => setSlots(res.data));
  };

  useEffect(() => {
    loadSlots();
    api.get('/api/problem-banks/').then((res) => setBanks(res.data));
  }, [quizId]);

  useEffect(() => {
    slots.forEach((slot) => {
      if (slot.problem_bank && !bankProblems[slot.problem_bank]) {
        api
          .get(`/api/problem-banks/${slot.problem_bank}/problems/`)
          .then((res) =>
            setBankProblems((prev) => ({
              ...prev,
              [slot.problem_bank]: res.data,
            }))
          );
      }
    });
  }, [slots, bankProblems]);

  const handleCreate = async () => {
    await api.post(
      `/api/quizzes/${quizId}/slots/`,
      { label, order, problem_bank: problemBank },
    );
    setLabel('');
    setOrder('');
    setProblemBank('');
    loadSlots();
  };

  const toggleProblemSelection = async (slot, problem) => {
    const existing = slot.slot_problems.find((sp) => sp.problem === problem.id);
    if (existing) {
      await api.delete(`/api/slot-problems/${existing.id}/`);
    } else {
      await api.post(
        `/api/slots/${slot.id}/slot-problems/`,
        { problem_ids: [problem.id] },
      );
    }
    loadSlots();
  };

  return (
    <div className="page">
      <h3>Slots</h3>
      <div>
        <input placeholder="Label" value={label} onChange={(e) => setLabel(e.target.value)} />
        <input placeholder="Order" value={order} onChange={(e) => setOrder(e.target.value)} />
        <select value={problemBank} onChange={(e) => setProblemBank(e.target.value)}>
          <option value="">Select bank</option>
          {banks.map((bank) => (
            <option key={bank.id} value={bank.id}>
              {bank.name}
            </option>
          ))}
        </select>
        <button onClick={handleCreate}>Add Slot</button>
      </div>
      {slots.map((slot) => {
        const problems = bankProblems[slot.problem_bank] || [];
        return (
          <div key={slot.id}>
            <h4>
              {slot.label} ({slot.problem_bank_name})
            </h4>
            <p>Select which problems from the bank are eligible for this slot.</p>
            <ul>
              {problems.map((problem) => {
                const linked = slot.slot_problems.find((sp) => sp.problem === problem.id);
                return (
                  <li key={problem.id}>
                    <label>
                      <input
                        type="checkbox"
                        checked={Boolean(linked)}
                        onChange={() => toggleProblemSelection(slot, problem)}
                      />
                      {problem.display_label}: {problem.statement}
                    </label>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </div>
  );
};

export default SlotsManagerPage;
