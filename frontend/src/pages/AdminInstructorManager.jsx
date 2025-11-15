import React, { useEffect, useState } from 'react';
import api from '@/lib/api';

const AdminInstructorManager = () => {
  const [instructors, setInstructors] = useState([]);
  const [form, setForm] = useState({ username: '', email: '', password: '', is_admin_instructor: false });

  const load = () => {
    api.get('/api/instructors/').then((res) => setInstructors(res.data));
  };

  useEffect(() => {
    load();
  }, []);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm({ ...form, [name]: type === 'checkbox' ? checked : value });
  };

  const handleCreate = async () => {
    await api.post('/api/instructors/', form);
    setForm({ username: '', email: '', password: '', is_admin_instructor: false });
    load();
  };

  const toggleAdmin = async (id, value) => {
    await api.patch(`/api/instructors/${id}/`, { is_admin_instructor: value });
    load();
  };

  const remove = async (id) => {
    await api.delete(`/api/instructors/${id}/`);
    load();
  };

  return (
    <div className="page">
      <h2>Instructor Administration</h2>
      <div>
        <input name="username" placeholder="Username" value={form.username} onChange={handleChange} />
        <input name="email" placeholder="Email" value={form.email} onChange={handleChange} />
        <input name="password" type="password" placeholder="Password" value={form.password} onChange={handleChange} />
        <label>
          Admin?
          <input type="checkbox" name="is_admin_instructor" checked={form.is_admin_instructor} onChange={handleChange} />
        </label>
        <button onClick={handleCreate}>Create Instructor</button>
      </div>
      <ul>
        {instructors.map((inst) => (
          <li key={inst.id}>
            {inst.username} ({inst.email})
            <label>
              Admin
              <input
                type="checkbox"
                checked={inst.is_admin_instructor}
                onChange={(e) => toggleAdmin(inst.id, e.target.checked)}
              />
            </label>
            <button onClick={() => remove(inst.id)}>Delete</button>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default AdminInstructorManager;
