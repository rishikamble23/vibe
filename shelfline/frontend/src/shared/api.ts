import axios from 'axios';

const API_BASE = 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export async function checkBackendHealth() {
  try {
    const res = await apiClient.get('/health');
    return res.data;
  } catch (err) {
    console.warn('Backend not reachable, falling back to offline simulation mode.');
    return null;
  }
}

export async function triggerChaosAction(actionType: string) {
  try {
    const res = await apiClient.post(`/admin/chaos/${actionType}`);
    return res.data;
  } catch (err) {
    console.warn('Chaos endpoint simulated offline');
    return { status: 'simulated', type: actionType };
  }
}

export async function submitBatch(batchData: any) {
  try {
    const res = await apiClient.post('/batches', batchData);
    return res.data;
  } catch (err) {
    console.warn('Batch submission simulated offline');
    return { id: Math.floor(Math.random() * 1000), ...batchData, feasible: true, slackMinutes: 45 };
  }
}
