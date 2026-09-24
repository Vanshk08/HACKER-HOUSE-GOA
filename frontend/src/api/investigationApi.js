import { request } from './client';

export async function fetchCases() {
  return request('/api/cases');
}

export async function fetchCase(caseId) {
  return request(`/api/cases/${encodeURIComponent(caseId)}`);
}

export async function startInvestigation(caseId, provider = null) {
  return request('/api/investigate', {
    method: 'POST',
    body: JSON.stringify({ case_id: caseId, provider }),
  });
}

export function subscribeInvestigationStream(caseId, onMessage, onError, onComplete) {
  const url = `/api/investigate/stream/${encodeURIComponent(caseId)}`;
  const eventSource = new EventSource(url);

  eventSource.addEventListener('case_loaded', (e) => {
    try {
      const data = JSON.parse(e.data);
      onMessage({ type: 'case_loaded', data });
    } catch (err) {
      console.error('SSE parse error:', err);
    }
  });

  eventSource.addEventListener('tool_execution', (e) => {
    try {
      const data = JSON.parse(e.data);
      onMessage({ type: 'tool_execution', data });
    } catch (err) {
      console.error('SSE parse error:', err);
    }
  });

  eventSource.addEventListener('assessment', (e) => {
    try {
      const data = JSON.parse(e.data);
      onMessage({ type: 'assessment', data });
    } catch (err) {
      console.error('SSE parse error:', err);
    }
  });

  eventSource.addEventListener('policy', (e) => {
    try {
      const data = JSON.parse(e.data);
      onMessage({ type: 'policy', data });
    } catch (err) {
      console.error('SSE parse error:', err);
    }
  });

  eventSource.addEventListener('complete', (e) => {
    try {
      const data = JSON.parse(e.data);
      onMessage({ type: 'complete', data });
      if (onComplete) onComplete(data);
    } catch (err) {
      console.error('SSE parse error:', err);
    } finally {
      eventSource.close();
    }
  });

  eventSource.onerror = (err) => {
    if (onError) onError(err);
    eventSource.close();
  };

  return () => {
    eventSource.close();
  };
}
