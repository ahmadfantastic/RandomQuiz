import React, { useEffect, useState } from 'react';
import api from '@/lib/api';

const ProblemBankManager = () => {
  const [banks, setBanks] = useState([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedBank, setSelectedBank] = useState(null);
  const [problemOrder, setProblemOrder] = useState('');
  const [problemStatement, setProblemStatement] = useState('');

  const loadBanks = () => {
    api.get('/api/problem-banks/').then((res) => setBanks(res.data));
  };

  const loadBankDetails = async (bankId) => {
    const res = await api.get(`/api/problem-banks/${bankId}/`);
    const problems = await api.get(`/api/problem-banks/${bankId}/problems/`);
    setSelectedBank({ ...res.data, problems: problems.data });
  };

  useEffect(() => {
    loadBanks();
  }, []);

  const handleCreateBank = async () => {
    await api.post('/api/problem-banks/', { name, description });
    setName('');
    setDescription('');
    loadBanks();
  };

  const handleAddProblem = async () => {
    if (!selectedBank) return;
    await api.post(
      `/api/problem-banks/${selectedBank.id}/problems/`,
      { order_in_bank: problemOrder, statement: problemStatement },
    );
    setProblemOrder('');
    setProblemStatement('');
    loadBankDetails(selectedBank.id);
  };

  return (
    <div className="page">
      <h2>Problem Banks</h2>
      <div>
        <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
        <textarea placeholder="Description" value={description} onChange={(e) => setDescription(e.target.value)} />
        <button onClick={handleCreateBank}>Create Bank</button>
      </div>
      <ul>
        {banks.map((bank) => (
          <li key={bank.id}>
            <button onClick={() => loadBankDetails(bank.id)}>{bank.name}</button>
          </li>
        ))}
      </ul>
      {selectedBank && (
        <div>
          <h3>{selectedBank.name}</h3>
          <ul>
            {selectedBank.problems.map((p) => (
              <li key={p.id}>
                {p.display_label}: {p.statement}
              </li>
            ))}
          </ul>
          <input
            placeholder="Order in bank"
            value={problemOrder}
            onChange={(e) => setProblemOrder(e.target.value)}
          />
          <textarea
            placeholder="Problem statement"
            value={problemStatement}
            onChange={(e) => setProblemStatement(e.target.value)}
          />
          <button onClick={handleAddProblem}>Add Problem</button>
        </div>
      )}
    </div>
  );
};

export default ProblemBankManager;
